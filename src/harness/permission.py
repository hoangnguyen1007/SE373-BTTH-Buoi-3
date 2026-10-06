from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class PermissionDecision(BaseModel):
    allowed: bool
    requires_approval: bool = False
    reason: Optional[str] = None
    flight_id: Optional[str] = None
    seat_number: Optional[str] = None
    price: Optional[int] = None
    refundable: Optional[bool] = None


class PermissionGatekeeper:
    """Layer 3: Permission & Human Approval check before execution (Slide 35, 41)."""

    def __init__(self, approval_threshold_price: int = 1_500_000, allow_non_refundable: bool = False):
        self.approval_threshold_price = approval_threshold_price
        self.allow_non_refundable = allow_non_refundable

    def inspect_tool_call(
        self,
        tool_name: str,
        args: Dict[str, Any],
        flight_details: Optional[Dict[str, Any]] = None,
    ) -> PermissionDecision:
        if tool_name == "book_seat" and flight_details:
            price = flight_details.get("price", 0)
            refundable = flight_details.get("refundable", True)
            flight_id = flight_details.get("flight") or args.get("flight_id")
            seat = args.get("seat_number")

            needs_approval = False
            reasons = []

            if price > self.approval_threshold_price:
                needs_approval = True
                reasons.append(f"Price ({price:,} VND) exceeds self-approval threshold ({self.approval_threshold_price:,} VND)")

            if not refundable and not self.allow_non_refundable:
                needs_approval = True
                reasons.append("Ticket is non-refundable")

            if needs_approval:
                return PermissionDecision(
                    allowed=False,
                    requires_approval=True,
                    reason=" & ".join(reasons),
                    flight_id=flight_id,
                    seat_number=seat,
                    price=price,
                    refundable=refundable,
                )

        return PermissionDecision(allowed=True, requires_approval=False)
