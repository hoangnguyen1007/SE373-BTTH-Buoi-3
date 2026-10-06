import time
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
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
from src.harness.handoff import HumanHandoffManager, HandoffReport
from src.harness.budget import ExecutionBudget
from src.agents.base import BaseFlightAgent, AgentStepTrace, AgentExecutionResult


class PlanStep(BaseModel):
    step_id: int
    description: str
    tool_name: str
    args_template: Dict[str, Any]
    status: str = "PENDING"
    result: Optional[Dict[str, Any]] = None


class ExecutionPlan(BaseModel):
    goal: str
    steps: List[PlanStep]
    estimated_tokens: int = 3500
    approved: bool = False
    review_notes: Optional[str] = None


class PlanThenExecuteFlightAgent(BaseFlightAgent):
    """
    Plan-then-Execute Agent (Slide 22, 23).
    Generates a full plan once, reviews it, and executes sequentially.
    """

    def __init__(
        self,
        constraints: FlightConstraints,
        db: Optional[MockFlightDatabase] = None,
        max_steps: int = 10,
        approval_threshold_price: int = 1500000,
        auto_approve_plan: bool = True,
    ):
        super().__init__(constraints, agent_name="PlanThenExecuteFlightAgent")
        self.db = db or get_default_database()
        self.max_steps = max_steps
        self.auto_approve_plan = auto_approve_plan

        self.constraint_validator = ConstraintValidator(self.constraints)
        self.computational_verifier = ComputationalVerifier(self.constraints, db=self.db)
        self.permission_gatekeeper = PermissionGatekeeper(approval_threshold_price=approval_threshold_price)
        self.budget = ExecutionBudget(max_steps=max_steps)

    def generate_plan(self, user_goal: str) -> ExecutionPlan:
        steps = [
            PlanStep(
                step_id=1,
                description=f"Search flights {self.constraints.origin} -> {self.constraints.destination}",
                tool_name="search_flights",
                args_template={
                    "origin": self.constraints.origin,
                    "destination": self.constraints.destination,
                    "date": self.constraints.date,
                },
            ),
            PlanStep(
                step_id=2,
                description="Check seat availability on matching flight",
                tool_name="check_seat",
                args_template={"flight_id": "$best_flight"},
            ),
            PlanStep(
                step_id=3,
                description="Reserve seat on chosen flight",
                tool_name="book_seat",
                args_template={"flight_id": "$best_flight", "seat_number": "$first_seat"},
            ),
            PlanStep(
                step_id=4,
                description="Process corporate card payment",
                tool_name="pay",
                args_template={"booking_code": "$booking_code", "payment_method": "corp_card"},
            ),
            PlanStep(
                step_id=5,
                description="Verify booking completion",
                tool_name="get_booking",
                args_template={"booking_code": "$booking_code"},
            ),
        ]
        return ExecutionPlan(goal=user_goal, steps=steps, estimated_tokens=3500)

    def review_plan(self, plan: ExecutionPlan) -> bool:
        if not self.auto_approve_plan:
            plan.approved = False
            plan.review_notes = "Plan rejected by reviewer before execution."
            return False

        required_tools = {"search_flights", "check_seat", "book_seat", "pay"}
        planned_tools = {st.tool_name for st in plan.steps}
        if not required_tools.issubset(planned_tools):
            plan.approved = False
            return False

        plan.approved = True
        return True

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

    def run(self, user_goal: str) -> AgentExecutionResult:
        start_time = time.time()
        traces: List[AgentStepTrace] = []
        self.budget.reset()

        plan = self.generate_plan(user_goal)
        traces.append(AgentStepTrace(
            step_index=1,
            thought=f"Generated {len(plan.steps)}-step plan (Plan-then-Execute).",
            tokens_estimate=1200,
            harness_event="Planner generated execution plan.",
        ))

        # Review plan prior to execution (Slide 22)
        if not self.review_plan(plan):
            handoff = HumanHandoffManager.create_failure_handoff(
                reason="Plan not approved by human reviewer",
                attempts=["Plan generated but awaiting review confirmation."],
                question="Do you approve executing this booking plan? [YES/NO]",
            )
            return AgentExecutionResult(
                agent_type="Plan-then-Execute",
                success=False,
                finish_reason="NEED_HUMAN_APPROVAL",
                final_message="Plan rejected or awaiting approval before running.",
                total_steps=1,
                total_tokens=1200,
                duration_seconds=time.time() - start_time,
                trace=traces,
                handoff_report=handoff,
            )

        context_vars = {}
        active_booking_code = None

        for step in plan.steps:
            step_idx = self.budget.current_steps + 1
            tokens_step = 600
            self.budget.record_step(tokens_used=tokens_step)

            actual_args = {}
            for k, v in step.args_template.items():
                if isinstance(v, str) and v.startswith("$"):
                    actual_args[k] = context_vars.get(v[1:])
                else:
                    actual_args[k] = v

            step_trace = AgentStepTrace(
                step_index=step_idx,
                thought=f"Executing Step {step.step_id}: {step.description}",
                action_tool=step.tool_name,
                action_args=actual_args,
                tokens_estimate=tokens_step,
            )

            # Pre-execution check
            if step.tool_name == "book_seat":
                fl_id = actual_args.get("flight_id")
                fl_obj = self.db.flights.get(fl_id)
                if fl_obj:
                    fl_dict = {
                        "flight": fl_obj.flight_id,
                        "price": fl_obj.price,
                        "refundable": fl_obj.refundable,
                        "depart": fl_obj.depart_time,
                        "depart_date": fl_obj.depart_date,
                    }
                    ok_c, reason_c = self.constraint_validator.enforce_before_action(step.tool_name, actual_args, fl_dict)
                    if not ok_c:
                        step_trace.harness_event = f"Constraint blocked: {reason_c}"
                        traces.append(step_trace)
                        return AgentExecutionResult(
                            agent_type="Plan-then-Execute",
                            success=False,
                            finish_reason="CONSTRAINT_VIOLATION",
                            final_message=f"Constraint violation: {reason_c}",
                            total_steps=step_idx,
                            total_tokens=self.budget.current_tokens,
                            duration_seconds=time.time() - start_time,
                            trace=traces,
                        )

            obs = self._invoke_tool(step.tool_name, actual_args)
            step_trace.observation = obs
            step.result = obs

            # Check for failure in static plan (Slide 23: Early failure breaks plan)
            if obs.get("status") in ["error", "invalid_param"]:
                step.status = "FAILED"
                step_trace.harness_event = f"Step {step.step_id} failed: {obs.get('error')}."
                traces.append(step_trace)
                return AgentExecutionResult(
                    agent_type="Plan-then-Execute",
                    success=False,
                    finish_reason="PLAN_EXECUTION_FAILED",
                    final_message=f"Plan failed at step {step.step_id}: {obs.get('error')}",
                    total_steps=step_idx,
                    total_tokens=self.budget.current_tokens,
                    duration_seconds=time.time() - start_time,
                    trace=traces,
                    handoff_report=HumanHandoffManager.create_failure_handoff(
                        reason=f"Plan broken at step {step.step_id}",
                        attempts=[f"Static plan cannot adapt to tool failure: {obs.get('error')}."],
                        question="Switch to Hybrid agent for dynamic replanning?",
                    ),
                )

            if step.tool_name == "search_flights":
                flights = obs.get("flights", [])
                valid = [
                    f for f in flights
                    if f.get("depart") < self.constraints.depart_before and f.get("price") <= self.constraints.max_price
                ]
                if not valid:
                    step_trace.harness_event = "No valid flights found."
                    traces.append(step_trace)
                    return AgentExecutionResult(
                        agent_type="Plan-then-Execute",
                        success=False,
                        finish_reason="STALL_DETECTED",
                        final_message="No flight meets constraints.",
                        total_steps=step_idx,
                        total_tokens=self.budget.current_tokens,
                        duration_seconds=time.time() - start_time,
                        trace=traces,
                    )
                context_vars["best_flight"] = valid[0]["flight"]

            elif step.tool_name == "check_seat":
                seats = obs.get("available_seats", [])
                if not seats:
                    step_trace.harness_event = "No seats left."
                    traces.append(step_trace)
                    return AgentExecutionResult(
                        agent_type="Plan-then-Execute",
                        success=False,
                        finish_reason="PLAN_EXECUTION_FAILED",
                        final_message="No seats available on selected flight.",
                        total_steps=step_idx,
                        total_tokens=self.budget.current_tokens,
                        duration_seconds=time.time() - start_time,
                        trace=traces,
                        handoff_report=HumanHandoffManager.create_failure_handoff(
                            reason=f"Flight {actual_args.get('flight_id')} has no seats",
                            attempts=["Static plan picked flight without runtime fallback."],
                            question="Switch to Hybrid agent to replan?",
                        ),
                    )
                context_vars["first_seat"] = seats[0]

            elif step.tool_name == "book_seat":
                active_booking_code = obs.get("booking_code")
                context_vars["booking_code"] = active_booking_code

            step.status = "COMPLETED"
            traces.append(step_trace)

        if active_booking_code:
            verify_res = self.computational_verifier.verify(active_booking_code)
            if verify_res["achieved"]:
                return AgentExecutionResult(
                    agent_type="Plan-then-Execute",
                    success=True,
                    finish_reason="GOAL_ACHIEVED",
                    final_message=f"Plan executed successfully! PNR: {active_booking_code}.",
                    booking_code=active_booking_code,
                    total_steps=len(plan.steps) + 1,
                    total_tokens=self.budget.current_tokens,
                    duration_seconds=time.time() - start_time,
                    trace=traces,
                )

        return AgentExecutionResult(
            agent_type="Plan-then-Execute",
            success=False,
            finish_reason="GOAL_NOT_VERIFIED",
            final_message="Plan finished without verification.",
            total_steps=len(plan.steps) + 1,
            total_tokens=self.budget.current_tokens,
            duration_seconds=time.time() - start_time,
            trace=traces,
        )
