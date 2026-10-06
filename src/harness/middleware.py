from typing import Any, Callable, Dict, Optional
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage
from src.harness.constraints import ConstraintValidator
from src.harness.permission import PermissionGatekeeper, PermissionDecision
from src.harness.detectors import LoopDetector, GroundingSensor
from src.harness.handoff import HumanHandoffManager, HandoffReport


class HarnessMiddleware(AgentMiddleware):
    """
    Native LangChain AgentMiddleware implementing the course Harness layers (Slide 10, 11, 29).
    """

    def __init__(
        self,
        constraint_validator: ConstraintValidator,
        permission_gatekeeper: PermissionGatekeeper,
        loop_detector: LoopDetector,
        grounding_sensor: GroundingSensor,
        auto_approve_human_gate: bool = True,
        flight_lookup: Optional[Callable[[str], Optional[Dict[str, Any]]]] = None,
    ):
        super().__init__()
        self.constraint_validator = constraint_validator
        self.permission_gatekeeper = permission_gatekeeper
        self.loop_detector = loop_detector
        self.grounding_sensor = grounding_sensor
        self.auto_approve_human_gate = auto_approve_human_gate
        self.flight_lookup = flight_lookup
        self.halted_reason: Optional[str] = None
        self.handoff_report: Optional[HandoffReport] = None

    def wrap_tool_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
        tool_call = getattr(request, "tool_call", {}) or {}
        tool_name = tool_call.get("name") or getattr(request, "name", "")
        args = tool_call.get("args") or getattr(request, "args", {}) or {}
        tool_call_id = tool_call.get("id") or getattr(request, "id", "call_default")

        # Step #0: Pre-execution permission check (Slide 35, 41)
        flight_ctx = self.flight_lookup(args.get("flight_id")) if self.flight_lookup else None
        if tool_name == "book_seat" and flight_ctx:
            ok, reason = self.constraint_validator.enforce_before_action(tool_name, args, flight_ctx)
            if not ok:
                self.halted_reason = f"CONSTRAINT_VIOLATION: {reason}"
                return ToolMessage(tool_call_id=tool_call_id, content=f'{{"status": "denied", "reason": "{reason}"}}')

            decision: PermissionDecision = self.permission_gatekeeper.inspect_tool_call(tool_name, args, flight_ctx)
            if decision.requires_approval and not self.auto_approve_human_gate:
                self.halted_reason = f"NEED_HUMAN_APPROVAL: {decision.reason}"
                self.handoff_report = HumanHandoffManager.create_approval_handoff(
                    flight_id=decision.flight_id or args.get("flight_id", ""),
                    depart_time=flight_ctx.get("depart", ""),
                    price=decision.price or 0,
                    refundable=decision.refundable if decision.refundable is not None else False,
                    seat=decision.seat_number or args.get("seat_number", ""),
                    reasons=[decision.reason or "Requires authorization"],
                )
                return ToolMessage(tool_call_id=tool_call_id, content=f'{{"status": "needs_approval", "reason": "{decision.reason}"}}')

        # Execute tool
        result = handler(request)

        # Ingest into grounding sensor and check loop (Slide 45, 46, 59)
        output_data = getattr(result, "content", None) or result
        if isinstance(output_data, dict):
            self.grounding_sensor.ingest_tool_observation(tool_name, args, output_data)
            loop_signal = self.loop_detector.check(tool_name, args, progress=tool_name)
            if loop_signal:
                self.halted_reason = f"{loop_signal}_DETECTED"

        return result
