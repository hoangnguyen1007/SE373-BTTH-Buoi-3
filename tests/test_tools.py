"""
Unit tests cho hệ sinh thái Mock Tools (Commit 1).
Kiểm thử các kịch bản thành công và các ca biên theo bài giảng Slide 03.
"""
import unittest
from src.tools.flight_tools import (
    MockFlightDatabase,
    search_flights,
    check_seat,
    book_seat,
    pay,
    get_booking,
)
from src.domain.models import FlightConstraints


class TestFlightTools(unittest.TestCase):

    def setUp(self):
        self.mock_db = MockFlightDatabase()

    def test_search_flights_invalid_date_format(self):
        """Slide 56: Báo lỗi định dạng ngày kèm gợi ý YYYY-MM-DD."""
        result = search_flights("SGN", "DAD", "07/10", db=self.mock_db)
        self.assertEqual(result["status"], "invalid_param")
        self.assertEqual(result["param"], "date")
        self.assertIn("hint", result)
        self.assertIn("2026-10-07", result["hint"])

    def test_search_flights_empty_results(self):
        """Slide 66: Tool phải trả structured JSON rõ ràng, flights=[] khi không có chuyến."""
        result = search_flights("SGN", "PQC", "2026-10-07", db=self.mock_db)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["flights"], [])

    def test_search_flights_valid(self):
        """Tìm chuyến bay SGN -> DAD ngày 2026-10-07 thành công."""
        result = search_flights("SGN", "DAD", "2026-10-07", db=self.mock_db)
        self.assertEqual(result["status"], "ok")
        flight_ids = [f["flight"] for f in result["flights"]]
        self.assertIn("VN122", flight_ids)
        self.assertIn("QH118", flight_ids)

    def test_check_seat_and_booking_flow(self):
        """Kiểm tra quy trình check ghế -> book -> pay -> get_booking (Slide 37)."""
        # 1. Check seat
        seat_info = check_seat("VN122", db=self.mock_db)
        self.assertEqual(seat_info["status"], "ok")
        self.assertIn("12A", seat_info["available_seats"])
        self.assertEqual(seat_info["price"], 1850000)

        # 2. Book seat
        book_res = book_seat("VN122", "12A", db=self.mock_db)
        self.assertEqual(book_res["status"], "held")
        booking_code = book_res["booking_code"]

        # Ghế 12A không còn khả dụng
        seat_info_after = check_seat("VN122", db=self.mock_db)
        self.assertNotIn("12A", seat_info_after["available_seats"])

        # 3. Pay
        pay_res = pay(booking_code, "corp_card", db=self.mock_db)
        self.assertEqual(pay_res["status"], "paid")

        # 4. Get booking
        booking = get_booking(booking_code, db=self.mock_db)
        self.assertEqual(booking["status"], "confirmed")
        self.assertTrue(booking["paid"])
        self.assertEqual(booking["price"], 1850000)
        self.assertEqual(booking["flight"], "VN122")
        self.assertEqual(booking["seat"], "12A")

    def test_flight_constraints_verification(self):
        """Slide 63: Kiểm tra ràng buộc là dữ liệu (FlightConstraints.is_ok)."""
        constraints = FlightConstraints(
            origin="SGN",
            destination="DAD",
            date="2026-10-07",
            depart_before="12:00",
            max_price=2000000
        )

        flight_vn122 = self.mock_db.flights["VN122"]  # 08:10, 1.850.000 -> OK
        self.assertTrue(constraints.is_ok(flight_vn122))

        flight_qh118 = self.mock_db.flights["QH118"]  # 15:40, 1.640.000 -> Sai giờ (> 12:00)
        self.assertFalse(constraints.is_ok(flight_qh118))

        flight_vj604 = self.mock_db.flights["VJ604"]  # 10:15, 2.080.000 -> Sai giá (> 2.000.000)
        self.assertFalse(constraints.is_ok(flight_vj604))


if __name__ == "__main__":
    unittest.main()

