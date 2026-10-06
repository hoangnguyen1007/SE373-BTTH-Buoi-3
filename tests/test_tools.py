import unittest
from src.tools.flight_tools import (
    MockFlightDatabase,
    search_flights,
    check_seat,
    book_seat,
    pay,
    get_booking,
    _GLOBAL_DB,
)
from src.domain.models import FlightConstraints


class TestFlightTools(unittest.TestCase):

    def setUp(self):
        _GLOBAL_DB.reset()

    def test_search_flights_invalid_date_format(self):
        result = search_flights.invoke({"origin": "SGN", "destination": "DAD", "date": "07/10"})
        self.assertEqual(result["status"], "invalid_param")
        self.assertEqual(result["param"], "date")
        self.assertIn("hint", result)
        self.assertIn("2026-10-07", result["hint"])

    def test_search_flights_empty_results(self):
        result = search_flights.invoke({"origin": "SGN", "destination": "PQC", "date": "2026-10-07"})
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["flights"], [])

    def test_search_flights_valid(self):
        result = search_flights.invoke({"origin": "SGN", "destination": "DAD", "date": "2026-10-07"})
        self.assertEqual(result["status"], "ok")
        flight_ids = [f["flight"] for f in result["flights"]]
        self.assertIn("VN122", flight_ids)
        self.assertIn("QH118", flight_ids)

    def test_check_seat_and_booking_flow(self):
        seat_info = check_seat.invoke({"flight_id": "VN122"})
        self.assertEqual(seat_info["status"], "ok")
        self.assertIn("12A", seat_info["available_seats"])
        self.assertEqual(seat_info["price"], 1850000)

        book_res = book_seat.invoke({"flight_id": "VN122", "seat_number": "12A"})
        self.assertEqual(book_res["status"], "held")
        booking_code = book_res["booking_code"]

        seat_info_after = check_seat.invoke({"flight_id": "VN122"})
        self.assertNotIn("12A", seat_info_after["available_seats"])

        pay_res = pay.invoke({"booking_code": booking_code, "payment_method": "corp_card"})
        self.assertEqual(pay_res["status"], "paid")

        booking = get_booking.invoke({"booking_code": booking_code})
        self.assertEqual(booking["status"], "confirmed")
        self.assertTrue(booking["paid"])
        self.assertEqual(booking["price"], 1850000)
        self.assertEqual(booking["flight"], "VN122")
        self.assertEqual(booking["seat"], "12A")

    def test_flight_constraints_verification(self):
        constraints = FlightConstraints(
            origin="SGN",
            destination="DAD",
            date="2026-10-07",
            depart_before="12:00",
            max_price=2000000,
        )

        flight_vn122 = _GLOBAL_DB.flights["VN122"]
        self.assertTrue(constraints.is_ok(flight_vn122))

        flight_qh118 = _GLOBAL_DB.flights["QH118"]
        self.assertFalse(constraints.is_ok(flight_qh118))

        flight_vj604 = _GLOBAL_DB.flights["VJ604"]
        self.assertFalse(constraints.is_ok(flight_vj604))


if __name__ == "__main__":
    unittest.main()
