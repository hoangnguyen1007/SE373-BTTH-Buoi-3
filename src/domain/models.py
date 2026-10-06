from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class BookingStatus(str, Enum):
    HELD = "held"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class Flight(BaseModel):
    flight_id: str = Field(description="Flight code (e.g. VN122)")
    origin: str = Field(description="Departure airport code (e.g. SGN)")
    destination: str = Field(description="Arrival airport code (e.g. DAD)")
    depart_date: str = Field(description="Departure date (YYYY-MM-DD)")
    depart_time: str = Field(description="Departure time (HH:MM)")
    price: int = Field(description="Flight fare in VND")
    refundable: bool = Field(default=True, description="Whether ticket is refundable")
    available_seats: List[str] = Field(default_factory=list, description="Available seat identifiers")


class Booking(BaseModel):
    booking_code: str = Field(description="Unique PNR booking code (e.g. 4XJ2)")
    flight_id: str
    seat_number: str
    price: int
    depart_date: str
    depart_time: str
    refundable: bool = True
    status: BookingStatus = BookingStatus.HELD
    paid: bool = False
    payment_method: Optional[str] = None


class FlightConstraints(BaseModel):
    """
    User requirements encoded as data (Slide 63).
    """
    origin: str = "SGN"
    destination: str = "DAD"
    date: str = "2026-10-07"
    depart_before: str = "12:00"
    max_price: int = 2_000_000

    def is_ok(self, flight: Flight) -> bool:
        """Validate flight against hard constraints."""
        if flight.origin != self.origin:
            return False
        if flight.destination != self.destination:
            return False
        if flight.depart_date != self.date:
            return False
        if flight.depart_time >= self.depart_before:
            return False
        if flight.price > self.max_price:
            return False
        return True


class ToolResponse(BaseModel):
    """Standardized tool response schema (Slide 13, 66)."""
    status: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    param: Optional[str] = None
    hint: Optional[str] = None
