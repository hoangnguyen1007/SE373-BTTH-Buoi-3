from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from src.domain.models import FlightConstraints
from src.harness.handoff import HandoffReport


class AgentStepTrace(BaseModel):
    step_index: int
    thought: str
    action_tool: Optional[str] = None
    action_args: Optional[Dict[str, Any]] = None
    observation: Optional[Dict[str, Any]] = None
    harness_event: Optional[str] = None
    tokens_estimate: int = 0


class AgentExecutionResult(BaseModel):
    agent_type: str
    success: bool
    finish_reason: str
    final_message: str
    booking_code: Optional[str] = None
    total_steps: int = 0
    total_tokens: int = 0
    duration_seconds: float = 0.0
    trace: List[AgentStepTrace] = Field(default_factory=list)
    handoff_report: Optional[HandoffReport] = None

    def print_trace_summary(self):
        lines = [
            "=" * 70,
            f"AGENT EXECUTION REPORT: {self.agent_type.upper()}",
            f"Status: {'SUCCESS (Verified)' if self.success else 'STOPPED / PENDING'}",
            f"Finish Reason: {self.finish_reason}",
            f"Steps: {self.total_steps} | Tokens Estimate: {self.total_tokens:,}",
            f"Duration: {self.duration_seconds:.2f}s",
        ]
        if self.booking_code:
            lines.append(f"Booking PNR: {self.booking_code}")
        lines.append("=" * 70)
        lines.append("TRACE LOG:")
        for st in self.trace:
            lines.append(f"\n--- [STEP {st.step_index}] ---")
            lines.append(f"  Thought: {st.thought}")
            if st.action_tool:
                lines.append(f"  Action: {st.action_tool}({st.action_args})")
            if st.observation:
                lines.append(f"  Observation: {st.observation}")
            if st.harness_event:
                lines.append(f"  Harness: {st.harness_event}")
        if self.handoff_report:
            lines.append(f"\n{self.handoff_report.format_30s_view()}")
        lines.append("=" * 70)

        output_str = "\n".join(lines)
        try:
            print(output_str)
        except UnicodeEncodeError:
            import sys
            sys.stdout.buffer.write(output_str.encode("utf-8", errors="replace") + b"\n")


class BaseFlightAgent:
    def __init__(self, constraints: FlightConstraints, agent_name: str = "FlightAgent"):
        self.constraints = constraints
        self.agent_name = agent_name
