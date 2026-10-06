from typing import List, Optional
from pydantic import BaseModel, Field


class HandoffReport(BaseModel):
    """Standardized 30-second human handoff format (Slide 48)."""
    current_status: str
    tried_attempts: List[str]
    specific_question: str
    recommendation: Optional[str] = None

    def format_30s_view(self) -> str:
        attempts_str = "\n".join([f"  - {attempt}" for attempt in self.tried_attempts])
        return (
            "====================== 30s HUMAN HANDOFF REPORT ======================\n"
            f"[1. CURRENT STATUS]:\n{self.current_status}\n\n"
            f"[2. TRIED ATTEMPTS]:\n{attempts_str}\n\n"
            f"[3. AGENT RECOMMENDATION]:\n{self.recommendation or 'Awaiting human decision.'}\n\n"
            f"[4. SPECIFIC DECISION QUESTION]:\n>> {self.specific_question}\n"
            "======================================================================="
        )


class HumanHandoffManager:
    """Manages creation of standardized handoff reports (Slide 48)."""

    @staticmethod
    def create_approval_handoff(
        flight_id: str,
        depart_time: str,
        price: int,
        refundable: bool,
        seat: str,
        reasons: List[str],
    ) -> HandoffReport:
        status_desc = (
            f"Identified flight {flight_id} departing at {depart_time}. "
            f"Seat selected: {seat}. Total: {price:,} VND. No funds charged."
        )
        tried = [
            "Queried flights matching morning constraint (< 12:00).",
            f"Flight {flight_id} matches criteria but requires permission: {', '.join(reasons)}.",
        ]
        question = (
            f"Do you approve booking seat {seat} on {flight_id} for {price:,} VND "
            f"({'Non-refundable' if not refundable else 'Refundable'})? [YES/NO]"
        )
        return HandoffReport(
            current_status=status_desc,
            tried_attempts=tried,
            specific_question=question,
            recommendation="Approval recommended: Only available morning flight within budget.",
        )

    @staticmethod
    def create_failure_handoff(
        reason: str,
        attempts: List[str],
        question: str,
    ) -> HandoffReport:
        return HandoffReport(
            current_status=f"Execution halted: {reason}",
            tried_attempts=attempts,
            specific_question=question,
            recommendation="Consider relaxing constraints or choosing alternative flight windows.",
        )
