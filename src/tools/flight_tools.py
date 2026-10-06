import re
from typing import Dict, Any, List, Optional
from langchain_core.tools import tool
from src.domain.models import Flight, Booking, BookingStatus


class MockFlightDatabase:
    """In-memory flight database matching course slide cases."""

    def __init__(self):
        self.flights: Dict[str, Flight] = {}
        self.bookings: Dict[str, Booking] = {}
        self._booking_counter = 1
        self.seed_data()

    def seed_data(self):
        initial_flights = [
            Flight(
                flight_id="VN122",
                origin="SGN",
                destination="DAD",
                depart_date="2026-10-07",
                depart_time="08:10",
                price=1850000,
                refundable=False,
                available_seats=["12A", "12B", "12C"],
            ),
            Flight(
                flight_id="QH118",
                origin="SGN",
                destination="DAD",
                depart_date="2026-10-07",
                depart_time="15:40",
                price=1640000,
                refundable=True,
                available_seats=["14A", "14B"],
            ),
            Flight(
                flight_id="VJ604",
                origin="SGN",
                destination="DAD",
                depart_date="2026-10-07",
                depart_time="10:15",
                price=2080000,
                refundable=True,
                available_seats=["16A"],
            ),
            Flight(
                flight_id="VN134",
                origin="SGN",
                destination="DAD",
                depart_date="2026-10-07",
                depart_time="09:30",
                price=2190000,
                refundable=True,
                available_seats=["18A", "18B"],
            ),
            Flight(
                flight_id="VJ612",
                origin="SGN",
                destination="DAD",
                depart_date="2026-10-07",
                depart_time="19:20",
                price=2450000,
                refundable=True,
                available_seats=["20A"],
            ),
        ]
        self.flights = {f.flight_id: f for f in initial_flights}
        self.bookings.clear()
        self._booking_counter = 1

    def reset(self):
        self.seed_data()


_GLOBAL_DB = MockFlightDatabase()


def get_default_database() -> MockFlightDatabase:
    return _GLOBAL_DB


@tool
def search_flights(origin: str, destination: str, date: str) -> Dict[str, Any]:
    """Search for available flights by origin, destination and date (YYYY-MM-DD)."""
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        return {
            "status": "invalid_param",
            "param": "date",
            "error": f"Invalid date format '{date}'.",
            "hint": "Use YYYY-MM-DD, e.g. 2026-10-07",
        }

    matches = []
    for f in _GLOBAL_DB.flights.values():
        if (
            f.origin.upper() == origin.upper()
            and f.destination.upper() == destination.upper()
            and f.depart_date == date
        ):
            matches.append({
                "flight": f.flight_id,
                "depart": f.depart_time,
                "price": f.price,
                "refundable": f.refundable,
                "available_seat_count": len(f.available_seats),
            })

    return {"status": "ok", "flights": matches}


@tool
def check_seat(flight_id: str) -> Dict[str, Any]:
    """Check seat availability and details for a given flight ID."""
    flight = _GLOBAL_DB.flights.get(flight_id)
    if not flight:
        return {
            "status": "error",
            "error": "flight_not_found",
            "hint": f"Flight '{flight_id}' not found.",
        }

    return {
        "status": "ok",
        "flight": flight.flight_id,
        "origin": flight.origin,
        "destination": flight.destination,
        "depart_date": flight.depart_date,
        "depart_time": flight.depart_time,
        "price": flight.price,
        "refundable": flight.refundable,
        "available_seats": list(flight.available_seats),
    }


@tool
def book_seat(flight_id: str, seat_number: str) -> Dict[str, Any]:
    """Reserve a seat on a flight and generate a booking code."""
    flight = _GLOBAL_DB.flights.get(flight_id)
    if not flight:
        return {"status": "error", "error": "flight_not_found"}

    if seat_number not in flight.available_seats:
        return {
            "status": "error",
            "error": "seat_not_available",
            "hint": f"Seat '{seat_number}' unavailable. Remaining: {flight.available_seats}",
        }

    flight.available_seats.remove(seat_number)
    code = f"4XJ{_GLOBAL_DB._booking_counter}"
    _GLOBAL_DB._booking_counter += 1

    booking = Booking(
        booking_code=code,
        flight_id=flight.flight_id,
        seat_number=seat_number,
        price=flight.price,
        depart_date=flight.depart_date,
        depart_time=flight.depart_time,
        refundable=flight.refundable,
        status=BookingStatus.HELD,
        paid=False,
    )
    _GLOBAL_DB.bookings[code] = booking

    return {
        "status": "held",
        "booking_code": code,
        "flight": flight.flight_id,
        "seat": seat_number,
        "price": flight.price,
        "refundable": flight.refundable,
    }


@tool
def pay(booking_code: str, payment_method: str = "corp_card") -> Dict[str, Any]:
    """Process payment for an existing held booking."""
    booking = _GLOBAL_DB.bookings.get(booking_code)
    if not booking:
        return {"status": "error", "error": "booking_not_found"}

    if booking.paid:
        return {"status": "ok", "booking_code": booking_code, "message": "Already paid."}

    booking.status = BookingStatus.CONFIRMED
    booking.paid = True
    booking.payment_method = payment_method

    return {"status": "paid", "booking_code": booking_code}


@tool
def get_booking(booking_code: str) -> Dict[str, Any]:
    """Fetch booking status and verification details."""
    booking = _GLOBAL_DB.bookings.get(booking_code)
    if not booking:
        return {"status": "not_found", "error": f"Booking '{booking_code}' not found."}

    return {
        "status": booking.status.value,
        "booking_code": booking.booking_code,
        "flight": booking.flight_id,
        "seat": booking.seat_number,
        "price": booking.price,
        "depart_date": booking.depart_date,
        "depart_time": booking.depart_time,
        "refundable": booking.refundable,
        "paid": booking.paid,
        "payment_method": booking.payment_method,
    }


FLIGHT_TOOLS = [search_flights, check_seat, book_seat, pay, get_booking]
