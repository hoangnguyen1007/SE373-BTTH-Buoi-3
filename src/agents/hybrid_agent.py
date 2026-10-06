import time
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from langchain.agents.middleware import TodoListMiddleware
from src.domain.models import FlightConstraints
from src.tools.flight_tools import (
    MockFlightDatabase,
    FLIGHT_TOOLS,
    search_flights,
    check_seat,
    book_seat,
    pay,
    get_booking,
    get_default_database,
)
from src.harness.constraints import ConstraintValidator
from src.harness.verification import ComputationalVerifier
from src.harness.permission import PermissionGatekeeper
from src.harness.handoff import HumanHandoffManager
from src.harness.detectors import LoopDetector, GroundingSensor
from src.harness.budget import ExecutionBudget
from src.agents.base import BaseFlightAgent, AgentStepTrace, AgentExecutionResult


class TodoItem(BaseModel):
    id: int
    title: str
    tool: str
    args: Dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"
    observation: Optional[Dict[str, Any]] = None


class HybridFlightAgent(BaseFlightAgent):
    """
    Hybrid Agent: ReAct + Plan with Dynamic Replanning (Slide 24, 26).
    Employs Todo list concept supported by LangChain 1.x TodoListMiddleware.
    """

    def __init__(
        self,
        constraints: FlightConstraints,
        db: Optional[MockFlightDatabase] = None,
        max_steps: int = 12,
        approval_threshold_price: int = 1500000,
        auto_approve_human_gate: bool = True,
    ):
        super().__init__(constraints, agent_name="HybridFlightAgent")
        self.db = db or get_default_database()
        self.max_steps = max_steps
        self.auto_approve_human_gate = auto_approve_human_gate

        self.constraint_validator = ConstraintValidator(self.constraints)
        self.computational_verifier = ComputationalVerifier(self.constraints, db=self.db)
        self.permission_gatekeeper = PermissionGatekeeper(approval_threshold_price=approval_threshold_price)
        self.loop_detector = LoopDetector(window=6, repeat_k=2, stall_n=5)
        self.grounding_sensor = GroundingSensor()
        self.budget = ExecutionBudget(max_steps=max_steps)

        # LangChain TodoListMiddleware instance (Slide 24)
        self.todo_middleware = TodoListMiddleware()
        self.todos: List[TodoItem] = []
        self.replan_count = 0

    def init_initial_todos(self):
        self.todos = [
            TodoItem(
                id=1,
                title=f"Search flights {self.constraints.origin} -> {self.constraints.destination}",
                tool="search_flights",
                args={"origin": self.constraints.origin, "destination": self.constraints.destination, "date": self.constraints.date},
            ),
            TodoItem(
                id=2,
                title="Check seat availability on optimal flight",
                tool="check_seat",
                args={"flight_id": "$target_flight"},
            ),
            TodoItem(
                id=3,
                title="Hold available seat",
                tool="book_seat",
                args={"flight_id": "$target_flight", "seat_number": "$target_seat"},
            ),
            TodoItem(
                id=4,
                title="Pay via corporate card",
                tool="pay",
                args={"booking_code": "$booking_code", "payment_method": "corp_card"},
            ),
            TodoItem(
                id=5,
                title="Verify booking status",
                tool="get_booking",
                args={"booking_code": "$booking_code"},
            ),
        ]

    def _invoke_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        tool_map = {
            "search_flights": search_flights,
            "check_seat": check_seat,
            "book_seat": book_seat,
            "pay": pay,
            "get_booking": get_booking,
        }
        t = tool_map.get(tool_name)
        if not t:
            return {"status": "error", "error": "unknown_tool"}
        return t.invoke(args) if hasattr(t, "invoke") else t(**args)

    def is_observation_drifted(self, step: TodoItem, obs: Dict[str, Any]) -> bool:
        """Evaluate if observation drifted significantly (Slide 24)."""
        if obs.get("status") in ["error", "invalid_param", "denied"]:
            return True

        if step.tool == "check_seat":
            seats = obs.get("available_seats", [])
            if not seats:
                return True

        if step.tool == "search_flights":
            flights = obs.get("flights", [])
            valid = [
                f for f in flights
                if f.get("depart") < self.constraints.depart_before and f.get("price") <= self.constraints.max_price
            ]
            if not valid:
                return True

        return False

    def replan_on_drift(self, failed_step: TodoItem, obs: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Dynamic replanning triggered by significant observation drift (Slide 24)."""
        self.replan_count += 1
        failed_step.status = "failed"
        failed_step.observation = obs

        if failed_step.tool == "check_seat":
            all_flights = context.get("all_search_flights", [])
            tried = context.get("tried_flights", set())
            tried.add(failed_step.args.get("flight_id"))
            context["tried_flights"] = tried

            next_candidates = [
                f for f in all_flights
                if f["flight"] not in tried
                and f["depart"] < self.constraints.depart_before
                and f["price"] <= self.constraints.max_price
            ]

            if next_candidates:
                alt = next_candidates[0]["flight"]
                context["target_flight"] = alt
                self.todos = [
                    TodoItem(
                        id=10 + self.replan_count * 2,
                        title=f"[REPLAN] Check seat on alternative flight {alt}",
                        tool="check_seat",
                        args={"flight_id": alt},
                    ),
                    TodoItem(
                        id=11 + self.replan_count * 2,
                        title=f"[REPLAN] Reserve seat on flight {alt}",
                        tool="book_seat",
                        args={"flight_id": alt, "seat_number": "$target_seat"},
                    ),
                    TodoItem(
                        id=12 + self.replan_count * 2,
                        title="[REPLAN] Process payment",
                        tool="pay",
                        args={"booking_code": "$booking_code", "payment_method": "corp_card"},
                    ),
                ]
                return True

        return False

    def run(self, user_goal: str) -> AgentExecutionResult:
        start_time = time.time()
        traces: List[AgentStepTrace] = []
        self.budget.reset()
        self.init_initial_todos()

        context_vars = {"tried_flights": set()}
        active_booking_code = None

        while self.todos:
            current_todo = self.todos.pop(0)
            step_idx = self.budget.current_steps + 1
            tokens_step = 1200 + (self.replan_count * 500)
            self.budget.record_step(tokens_used=tokens_step)

            actual_args = {}
            for k, v in current_todo.args.items():
                if isinstance(v, str) and v.startswith("$"):
                    actual_args[k] = context_vars.get(v[1:])
                else:
                    actual_args[k] = v

            current_todo.status = "in_progress"
            step_trace = AgentStepTrace(
                step_index=step_idx,
                thought=f"[Todo #{current_todo.id}] {current_todo.title}",
                action_tool=current_todo.tool,
                action_args=actual_args,
                tokens_estimate=tokens_step,
            )

            # Pre-execution check
            flight_ctx = None
            if current_todo.tool == "book_seat":
                fl_id = actual_args.get("flight_id")
                fl_obj = self.db.flights.get(fl_id)
                if fl_obj:
                    flight_ctx = {
                        "flight": fl_obj.flight_id,
                        "price": fl_obj.price,
                        "refundable": fl_obj.refundable,
                        "depart": fl_obj.depart_time,
                        "depart_date": fl_obj.depart_date,
                    }
                    ok_c, reason_c = self.constraint_validator.enforce_before_action(current_todo.tool, actual_args, flight_ctx)
                    if not ok_c:
                        step_trace.harness_event = f"Constraint blocked: {reason_c}"
                        traces.append(step_trace)
                        if not self.replan_on_drift(current_todo, {"status": "denied", "error": reason_c}, context_vars):
                            handoff = HumanHandoffManager.create_failure_handoff(
                                reason=reason_c,
                                attempts=["Flight violates constraints."],
                                question="Would you like to relax constraints?",
                            )
                            return AgentExecutionResult(
                                agent_type="Hybrid",
                                success=False,
                                finish_reason="CONSTRAINT_VIOLATION",
                                final_message=f"Halted: {reason_c}",
                                total_steps=step_idx,
                                total_tokens=self.budget.current_tokens,
                                duration_seconds=time.time() - start_time,
                                trace=traces,
                                handoff_report=handoff,
                            )
                        continue

                    perm = self.permission_gatekeeper.inspect_tool_call(current_todo.tool, actual_args, flight_ctx)
                    if perm.requires_approval and not self.auto_approve_human_gate:
                        handoff = HumanHandoffManager.create_approval_handoff(
                            flight_id=perm.flight_id,
                            depart_time=flight_ctx.get("depart", ""),
                            price=perm.price,
                            refundable=perm.refundable,
                            seat=perm.seat_number,
                            reasons=[perm.reason],
                        )
                        step_trace.harness_event = f"Approval required: {perm.reason}"
                        traces.append(step_trace)
                        return AgentExecutionResult(
                            agent_type="Hybrid",
                            success=False,
                            finish_reason="NEED_HUMAN_APPROVAL",
                            final_message=f"Pending approval: {perm.reason}",
                            total_steps=step_idx,
                            total_tokens=self.budget.current_tokens,
                            duration_seconds=time.time() - start_time,
                            trace=traces,
                            handoff_report=handoff,
                        )

            obs = self._invoke_tool(current_todo.tool, actual_args)
            step_trace.observation = obs
            current_todo.observation = obs
            self.grounding_sensor.ingest_tool_observation(current_todo.tool, actual_args, obs)

            # Observation drift check (Slide 24)
            if self.is_observation_drifted(current_todo, obs):
                step_trace.harness_event = f"Observation drift detected. Replanning (attempt {self.replan_count + 1})."
                traces.append(step_trace)
                if self.replan_on_drift(current_todo, obs, context_vars):
                    continue
                else:
                    return AgentExecutionResult(
                        agent_type="Hybrid",
                        success=False,
                        finish_reason="STALL_DETECTED",
                        final_message="Replanning exhausted with no alternative flights.",
                        total_steps=step_idx,
                        total_tokens=self.budget.current_tokens,
                        duration_seconds=time.time() - start_time,
                        trace=traces,
                        handoff_report=HumanHandoffManager.create_failure_handoff(
                            reason="No viable flight alternatives after replanning",
                            attempts=["Tried alternative options; none met criteria."],
                            question="Would you like to modify budget or date?",
                        ),
                    )

            if current_todo.tool == "search_flights":
                flights = obs.get("flights", [])
                context_vars["all_search_flights"] = flights
                valid = [
                    f for f in flights
                    if f.get("depart") < self.constraints.depart_before and f.get("price") <= self.constraints.max_price
                ]
                context_vars["target_flight"] = valid[0]["flight"]

            elif current_todo.tool == "check_seat":
                seats = obs.get("available_seats", [])
                context_vars["target_seat"] = seats[0]

            elif current_todo.tool == "book_seat":
                active_booking_code = obs.get("booking_code")
                context_vars["booking_code"] = active_booking_code

            current_todo.status = "completed"
            traces.append(step_trace)

            budget_res = self.budget.is_exhausted()
            if budget_res["exhausted"]:
                return AgentExecutionResult(
                    agent_type="Hybrid",
                    success=False,
                    finish_reason="BUDGET_EXHAUSTED",
                    final_message=f"Budget exhausted: {budget_res['reason']}",
                    total_steps=step_idx,
                    total_tokens=self.budget.current_tokens,
                    duration_seconds=time.time() - start_time,
                    trace=traces,
                )

        if active_booking_code:
            verify_res = self.computational_verifier.verify(active_booking_code)
            if verify_res["achieved"]:
                return AgentExecutionResult(
                    agent_type="Hybrid",
                    success=True,
                    finish_reason="GOAL_ACHIEVED",
                    final_message=f"Hybrid agent achieved goal! PNR: {active_booking_code}.",
                    booking_code=active_booking_code,
                    total_steps=self.budget.current_steps,
                    total_tokens=self.budget.current_tokens,
                    duration_seconds=time.time() - start_time,
                    trace=traces,
                )

        return AgentExecutionResult(
            agent_type="Hybrid",
            success=False,
            finish_reason="GOAL_NOT_VERIFIED",
            final_message="Execution completed without computational verification.",
            total_steps=self.budget.current_steps,
            total_tokens=self.budget.current_tokens,
            duration_seconds=time.time() - start_time,
            trace=traces,
        )
