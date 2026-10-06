from typing import Tuple, Optional, Dict, Any
from src.domain.models import FlightConstraints


class ConstraintValidator:
    """Layer 1: Enforces user constraints as data (Slide 61, 63)."""

    def __init__(self, constraints: FlightConstraints):
        self.constraints = constraints

    def check_flight(self, flight_info: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        depart_date = flight_info.get("depart_date")
        if depart_date and depart_date != self.constraints.date:
            return False, f"Departure date '{depart_date}' does not match required '{self.constraints.date}'."

        depart_time = flight_info.get("depart") or flight_info.get("depart_time")
        if depart_time and depart_time >= self.constraints.depart_before:
            return False, f"Departure time '{depart_time}' is not before '{self.constraints.depart_before}'."

        price = flight_info.get("price")
        if price and price > self.constraints.max_price:
            return False, f"Price {price:,} VND exceeds budget {self.constraints.max_price:,} VND."

        return True, None

    def enforce_before_action(
        self,
        tool_name: str,
        args: Dict[str, Any],
        flight_data: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Optional[str]]:
        if tool_name in ["book_seat", "pay"] and flight_data:
            ok, reason = self.check_flight(flight_data)
            if not ok:
                return False, f"Harness blocked '{tool_name}': {reason}"
        return True, None
