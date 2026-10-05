"""
Mock Tools cho nghiệp vụ Đặt vé máy bay (Flight Booking System).
Được thiết kế theo đúng chuẩn thực hành SE373 Buổi 03:
- Output có cấu trúc JSON (Slide 13, 66)
- Báo lỗi chi tiết có gợi ý (Hint) giúp agent tự sửa sai thay vì lặp (Slide 54, 56)
- Chặn các failure modes kinh điển (Không trả dict rỗng hay dữ liệu mơ hồ - Slide 64, 66)
"""
import re
from typing import Dict, Any, List, Optional
from src.domain.models import Flight, Booking, BookingStatus


class MockFlightDatabase:
    """
    Cơ sở dữ liệu chuyến bay giả lập trong bộ nhớ.
    Dữ liệu được chuẩn hoá theo các tình huống trong slide bài giảng.
    """
    def __init__(self):
        self.flights: Dict[str, Flight] = {}
        self.bookings: Dict[str, Booking] = {}
        self._booking_counter = 1
        self.seed_data()

    def seed_data(self):
        """Khởi tạo dữ liệu chuyến bay mẫu."""
        initial_flights = [
            Flight(
                flight_id="VN122",
                origin="SGN",
                destination="DAD",
                depart_date="2026-10-07",
                depart_time="08:10",
                price=1850000,
                refundable=False, # Vé không hoàn tiền, giá > 1.500.000 (Slide 41: cần kiểm quyền)
                available_seats=["12A", "12B", "12C"]
            ),
            Flight(
                flight_id="QH118",
                origin="SGN",
                destination="DAD",
                depart_date="2026-10-07",
                depart_time="15:40", # Buổi chiều (Slide 58, 62: vi phạm ràng buộc sáng)
                price=1640000,
                refundable=True,
                available_seats=["14A", "14B"]
            ),
            Flight(
                flight_id="VJ604",
                origin="SGN",
                destination="DAD",
                depart_date="2026-10-07",
                depart_time="10:15",
                price=2080000, # Vượt ngân sách 2.000.000 (Slide 38)
                refundable=True,
                available_seats=["16A"]
            ),
            Flight(
                flight_id="VN134",
                origin="SGN",
                destination="DAD",
                depart_date="2026-10-07",
                depart_time="09:30",
                price=2190000, # Vượt ngân sách (Slide 38)
                refundable=True,
                available_seats=["18A", "18B"]
            ),
            Flight(
                flight_id="VJ612",
                origin="SGN",
                destination="DAD",
                depart_date="2026-10-07",
                depart_time="19:20",
                price=2450000,
                refundable=True,
                available_seats=["20A"]
            ),
            Flight(
                flight_id="VN202",
                origin="SGN",
                destination="HAN",
                depart_date="2026-10-07",
                depart_time="07:30",
                price=1900000,
                refundable=True,
                available_seats=["5A", "5B"]
            )
        ]
        self.flights = {f.flight_id: f for f in initial_flights}
        self.bookings.clear()
        self._booking_counter = 1

    def reset(self):
        """Khôi phục lại trạng thái ban đầu."""
        self.seed_data()


# Đối tượng DB dùng chung mặc định
_GLOBAL_DB = MockFlightDatabase()


def get_default_database() -> MockFlightDatabase:
    """Trả về đối tượng database mặc định."""
    return _GLOBAL_DB


def search_flights(origin: str, destination: str, date: str, db: Optional[MockFlightDatabase] = None) -> Dict[str, Any]:
    """
    Tìm kiếm chuyến bay theo điểm đi, điểm đến và ngày bay.
    - Kiểm tra định dạng ngày: Nếu không phải YYYY-MM-DD (ví dụ '07/10'), trả lỗi rõ ràng kèm hint (Slide 56).
    - Trả kết quả chuẩn JSON (Slide 13, 66).
    """
    database = db or _GLOBAL_DB

    # Kiểm tra format ngày bằng regex YYYY-MM-DD
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        return {
            "status": "invalid_param",
            "param": "date",
            "error": f"Định dạng ngày '{date}' không hợp lệ.",
            "hint": "Dùng YYYY-MM-DD, ví dụ 2026-10-07"
        }

    matches = []
    for f in database.flights.values():
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
                "available_seat_count": len(f.available_seats)
            })

    # Slide 66: {"status": "ok", "flights": []} khi không có chuyến
    return {
        "status": "ok",
        "flights": matches
    }


def check_seat(flight_id: str, db: Optional[MockFlightDatabase] = None) -> Dict[str, Any]:
    """
    Kiểm tra danh sách ghế trống và thông tin chi tiết của một chuyến bay cụ thể.
    """
    database = db or _GLOBAL_DB
    flight = database.flights.get(flight_id)
    if not flight:
        return {
            "status": "error",
            "error": "flight_not_found",
            "hint": f"Không tìm thấy chuyến bay '{flight_id}'. Vui lòng gọi search_flights để lấy danh sách chuyến bay hợp lệ."
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
        "available_seats": list(flight.available_seats)
    }


def book_seat(flight_id: str, seat_number: str, db: Optional[MockFlightDatabase] = None) -> Dict[str, Any]:
    """
    Giữ chỗ một ghế trên chuyến bay.
    Trả về trạng thái 'held' và mã đặt chỗ PNR (vd: '4XJ2').
    """
    database = db or _GLOBAL_DB
    flight = database.flights.get(flight_id)
    if not flight:
        return {
            "status": "error",
            "error": "flight_not_found",
            "hint": f"Chuyến bay '{flight_id}' không tồn tại."
        }

    if seat_number not in flight.available_seats:
        return {
            "status": "error",
            "error": "seat_not_available",
            "hint": f"Ghế '{seat_number}' không còn trống trên chuyến {flight_id}. Các ghế còn: {flight.available_seats}"
        }

    # Giữ ghế
    flight.available_seats.remove(seat_number)
    code = f"4XJ{database._booking_counter}"
    database._booking_counter += 1

    booking = Booking(
        booking_code=code,
        flight_id=flight.flight_id,
        seat_number=seat_number,
        price=flight.price,
        depart_date=flight.depart_date,
        depart_time=flight.depart_time,
        refundable=flight.refundable,
        status=BookingStatus.HELD,
        paid=False
    )
    database.bookings[code] = booking

    return {
        "status": "held",
        "booking_code": code,
        "flight": flight.flight_id,
        "seat": seat_number,
        "price": flight.price,
        "refundable": flight.refundable
    }


def pay(booking_code: str, payment_method: str = "corp_card", db: Optional[MockFlightDatabase] = None) -> Dict[str, Any]:
    """
    Thanh toán cho mã đặt chỗ đang ở trạng thái 'held'.
    Cập nhật trạng thái thành 'confirmed' và 'paid = True'.
    """
    database = db or _GLOBAL_DB
    booking = database.bookings.get(booking_code)
    if not booking:
        return {
            "status": "error",
            "error": "booking_not_found",
            "hint": f"Không tìm thấy mã đặt chỗ '{booking_code}'."
        }

    if booking.paid:
        return {
            "status": "ok",
            "booking_code": booking_code,
            "message": "Đơn hàng đã được thanh toán trước đó."
        }

    booking.status = BookingStatus.CONFIRMED
    booking.paid = True
    booking.payment_method = payment_method

    return {
        "status": "paid",
        "booking_code": booking_code
    }


def get_booking(booking_code: str, db: Optional[MockFlightDatabase] = None) -> Dict[str, Any]:
    """
    Truy vấn thông tin chi tiết một mã đặt chỗ.
    Được Harness sử dụng để kiểm chứng độc lập (Sensor Computational) xem tác vụ đã xong chưa.
    Slide 43, 44 Buổi 03:
    get_booking(code).status == 'confirmed' and paid == True ...
    """
    database = db or _GLOBAL_DB
    booking = database.bookings.get(booking_code)
    if not booking:
        return {
            "status": "not_found",
            "error": f"Mã đặt chỗ '{booking_code}' không tồn tại."
        }

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
        "payment_method": booking.payment_method
    }
