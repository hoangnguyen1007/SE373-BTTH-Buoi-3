import time
from typing import Dict, Any, Optional, List
from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from src.domain.models import FlightConstraints
from src.tools.flight_tools import (
    MockFlightDatabase,
    FLIGHT_TOOLS,
    get_default_database,
)
from src.harness.constraints import ConstraintValidator
from src.harness.verification import ComputationalVerifier
from src.harness.permission import PermissionGatekeeper
from src.harness.handoff import HumanHandoffManager
from src.harness.detectors import LoopDetector, GroundingSensor
from src.harness.budget import ExecutionBudget
from src.harness.middleware import HarnessMiddleware
from src.agents.base import BaseFlightAgent, AgentStepTrace, AgentExecutionResult
from src.agents.model_provider import get_chat_model


class ReActFlightAgent(BaseFlightAgent):
    """
    ReAct Agent implemented using LangChain create_agent (Slide 29).
    """

    def __init__(
        self,
        constraints: FlightConstraints,
        db: Optional[MockFlightDatabase] = None,
        max_steps: int = 10,
        approval_threshold_price: int = 1500000,
        auto_approve_human_gate: bool = True,
    ):
        super().__init__(constraints, agent_name="ReActFlightAgent")
        self.db = db or get_default_database()
        self.max_steps = max_steps
        self.auto_approve_human_gate = auto_approve_human_gate

        self.constraint_validator = ConstraintValidator(self.constraints)
        self.computational_verifier = ComputationalVerifier(self.constraints, db=self.db)
        self.permission_gatekeeper = PermissionGatekeeper(approval_threshold_price=approval_threshold_price)
        self.loop_detector = LoopDetector(window=6, repeat_k=2, stall_n=5)
        self.grounding_sensor = GroundingSensor()
        self.budget = ExecutionBudget(max_steps=max_steps)

        def flight_lookup(flight_id: str) -> Optional[Dict[str, Any]]:
            fl = self.db.flights.get(flight_id)
            if fl:
                return {
                    "flight": fl.flight_id,
                    "price": fl.price,
                    "refundable": fl.refundable,
                    "depart": fl.depart_time,
                    "depart_date": fl.depart_date,
                }
            return None

        self.harness_middleware = HarnessMiddleware(
            constraint_validator=self.constraint_validator,
            permission_gatekeeper=self.permission_gatekeeper,
            loop_detector=self.loop_detector,
            grounding_sensor=self.grounding_sensor,
            auto_approve_human_gate=auto_approve_human_gate,
            flight_lookup=flight_lookup,
        )

    def run(self, user_goal: str) -> AgentExecutionResult:
        start_time = time.time()
        self.budget.reset()
        self.loop_detector.reset()

        model = get_chat_model(self.constraints)

        # Slide 29: create_agent with ModelCallLimitMiddleware
        agent_graph = create_agent(
            model=model,
            tools=FLIGHT_TOOLS,
            system_prompt="Use tools only to retrieve flight information and perform bookings.",
            middleware=[
                ModelCallLimitMiddleware(run_limit=self.max_steps, exit_behavior="end"),
                self.harness_middleware,
            ],
        )

        try:
            result = agent_graph.invoke({"messages": [HumanMessage(content=user_goal)]})
        except Exception as e:
            handoff = HumanHandoffManager.create_failure_handoff(
                reason=str(e),
                attempts=["Agent execution encountered an unhandled exception."],
                question="Would you like to retry or modify parameters?",
            )
            return AgentExecutionResult(
                agent_type="ReAct",
                success=False,
                finish_reason="EXECUTION_ERROR",
                final_message=str(e),
                duration_seconds=time.time() - start_time,
                handoff_report=handoff,
            )

        messages = result.get("messages", [])
        traces: List[AgentStepTrace] = []
        active_booking_code = None
        step_idx = 0

        for msg in messages:
            if isinstance(msg, AIMessage):
                step_idx += 1
                tokens = 3000 + (step_idx - 1) * 500
                self.budget.record_step(tokens_used=tokens)

                tool_calls = getattr(msg, "tool_calls", [])
                action_name = tool_calls[0]["name"] if tool_calls else None
                action_args = tool_calls[0]["args"] if tool_calls else None

                traces.append(AgentStepTrace(
                    step_index=step_idx,
                    thought=msg.content or (f"Calling {action_name}" if action_name else "Concluded."),
                    action_tool=action_name,
                    action_args=action_args,
                    tokens_estimate=tokens,
                ))

            elif isinstance(msg, ToolMessage):
                if traces:
                    traces[-1].observation = msg.content
                if "4XJ" in str(msg.content):
                    import re
                    match = re.search(r"4XJ\d+", str(msg.content))
                    if match:
                        active_booking_code = match.group(0)

        # Check halted reasons from middleware
        if self.harness_middleware.halted_reason:
            reason = self.harness_middleware.halted_reason
            finish_reason = "NEED_HUMAN_APPROVAL" if "APPROVAL" in reason else "STALL_DETECTED"
            return AgentExecutionResult(
                agent_type="ReAct",
                success=False,
                finish_reason=finish_reason,
                final_message=f"Halted by Harness: {reason}",
                total_steps=step_idx,
                total_tokens=self.budget.current_tokens,
                duration_seconds=time.time() - start_time,
                trace=traces,
                handoff_report=self.harness_middleware.handoff_report,
            )

        # Layer 2: Computational Verification (Slide 43)
        if active_booking_code:
            verify_res = self.computational_verifier.verify(active_booking_code)
            if verify_res["achieved"]:
                return AgentExecutionResult(
                    agent_type="ReAct",
                    success=True,
                    finish_reason="GOAL_ACHIEVED",
                    final_message=f"Flight booked successfully! PNR: {active_booking_code}.",
                    booking_code=active_booking_code,
                    total_steps=step_idx,
                    total_tokens=self.budget.current_tokens,
                    duration_seconds=time.time() - start_time,
                    trace=traces,
                )

        return AgentExecutionResult(
            agent_type="ReAct",
            success=False,
            finish_reason="STALL_DETECTED",
            final_message="No suitable flight found matching constraints.",
            total_steps=step_idx,
            total_tokens=self.budget.current_tokens,
            duration_seconds=time.time() - start_time,
            trace=traces,
            handoff_report=HumanHandoffManager.create_failure_handoff(
                reason="Constraints not satisfied",
                attempts=["Scanned available flights, none met criteria."],
                question="Would you like to relax budget or time constraints?",
            ),
        )
