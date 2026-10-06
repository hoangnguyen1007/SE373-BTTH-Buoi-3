from collections import deque
from typing import Dict, Any, Optional, Set, List


class LoopDetector:
    """
    Loop and stall detector from Slide 46.
    """

    def __init__(self, window: int = 6, repeat_k: int = 2, stall_n: int = 5):
        self.recent = deque(maxlen=window)
        self.k, self.n, self.last, self.stall = repeat_k, stall_n, None, 0

    def check(self, tool: str, args: Dict[str, Any], progress: Any) -> Optional[str]:
        fp = (tool, repr(sorted(args.items())))
        if self.recent.count(fp) + 1 >= self.k:
            return "LOOP"
        self.recent.append(fp)
        self.stall = self.stall + 1 if progress == self.last else 0
        self.last = progress
        return "STALL" if self.stall >= self.n else None

    def reset(self):
        self.recent.clear()
        self.last = None
        self.stall = 0


class GroundingSensor:
    """
    Sensor validating agent claims against actual tool outputs (Slide 57, 59).
    """

    def __init__(self):
        self.observed_flights: Set[str] = set()
        self.observed_seats: Set[str] = set()
        self.observed_prices: Set[int] = set()
        self.observed_bookings: Set[str] = set()

    def ingest_tool_observation(self, tool_name: str, args: Dict[str, Any], result: Dict[str, Any]):
        if tool_name == "search_flights" and result.get("status") == "ok":
            for f in result.get("flights", []):
                self.observed_flights.add(f.get("flight"))
                self.observed_prices.add(f.get("price"))
        elif tool_name == "check_seat" and result.get("status") == "ok":
            self.observed_flights.add(result.get("flight"))
            self.observed_prices.add(result.get("price"))
            for seat in result.get("available_seats", []):
                self.observed_seats.add(seat)
        elif tool_name == "book_seat" and result.get("status") == "held":
            self.observed_bookings.add(result.get("booking_code"))
            self.observed_flights.add(result.get("flight"))
            self.observed_seats.add(result.get("seat"))
            self.observed_prices.add(result.get("price"))
        elif tool_name == "pay" and result.get("status") == "paid":
            self.observed_bookings.add(result.get("booking_code"))

    def check_claim(
        self,
        flight_id: Optional[str] = None,
        seat: Optional[str] = None,
        price: Optional[int] = None,
        booking_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        violations: List[str] = []
        if flight_id and flight_id not in self.observed_flights:
            violations.append(f"Flight ID '{flight_id}' has no source in tool outputs.")
        if seat and seat not in self.observed_seats:
            violations.append(f"Seat '{seat}' not observed in tool outputs.")
        if price and price not in self.observed_prices:
            violations.append(f"Price '{price:,}' not observed in tool outputs.")
        if booking_code and booking_code not in self.observed_bookings:
            violations.append(f"Booking code '{booking_code}' not issued by system.")

        return {
            "grounded": len(violations) == 0,
            "violations": violations,
        }
