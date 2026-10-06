from typing import Dict, Any, Optional
from src.domain.models import FlightConstraints
from src.tools.flight_tools import get_booking, MockFlightDatabase


class ComputationalVerifier:
    """Layer 2: Objective computational verification by code (Slide 43, 44)."""

    def __init__(self, constraints: FlightConstraints, db: Optional[MockFlightDatabase] = None):
        self.constraints = constraints
        self.db = db

    def verify(self, booking_code: str) -> Dict[str, Any]:
        """
        Slide 43 predicate:
        get_booking(code).status == "confirmed" and paid == True
        and price <= max_price and depart_date == date and depart_time < depart_before
        """
        booking_info = get_booking.invoke({"booking_code": booking_code}) if hasattr(get_booking, "invoke") else get_booking(booking_code)
        if booking_info.get("status") == "not_found":
            return {"achieved": False, "reason": f"Booking '{booking_code}' not found."}

        if booking_info.get("status") != "confirmed":
            return {"achieved": False, "reason": f"Status is '{booking_info.get('status')}', not confirmed."}

        if not booking_info.get("paid"):
            return {"achieved": False, "reason": "Booking is not paid."}

        price = booking_info.get("price", 0)
        if price > self.constraints.max_price:
            return {"achieved": False, "reason": f"Price {price:,} VND exceeds budget."}

        depart_date = booking_info.get("depart_date")
        if depart_date != self.constraints.date:
            return {"achieved": False, "reason": f"Date '{depart_date}' does not match '{self.constraints.date}'."}

        depart_time = booking_info.get("depart_time")
        if depart_time >= self.constraints.depart_before:
            return {"achieved": False, "reason": f"Departure '{depart_time}' is not before '{self.constraints.depart_before}'."}

        return {
            "achieved": True,
            "reason": "100% verified by computational code predicate.",
            "booking": booking_info,
        }
