"""
Lớp 2 Harness: Tiêu chí hoàn thành kiểm bằng code (Computational Verification).
Slide 43, 44 Buổi 03:
- Tiêu chí hoàn thành là quy tắc lập trình khách quan độc lập với model.
- Không tin lời tuyên bố chủ quan của model ('Tôi đã hoàn thành').
- Sensor computational: Chạy trong mili giây, không tốn token.
"""
from typing import Dict, Any, Optional
from src.domain.models import FlightConstraints
from src.tools.flight_tools import get_booking, MockFlightDatabase


class ComputationalVerifier:
    """
    Bộ kiểm chứng hoàn thành mục tiêu bằng logic code máy móc.
    """
    def __init__(self, constraints: FlightConstraints, db: Optional[MockFlightDatabase] = None):
        self.constraints = constraints
        self.db = db

    def verify(self, booking_code: str) -> Dict[str, Any]:
        """
        Kiểm tra trực tiếp từ database thật của hệ sinh thái:
        get_booking(code).status == "confirmed" and paid == True
        and price <= 2_000_000 and depart_date == "2026-10-07" and depart_time < "12:00"
        (Đúng nguyên văn slide 43).
        """
        booking_info = get_booking(booking_code, db=self.db)
        if booking_info.get("status") == "not_found":
            return {
                "achieved": False,
                "reason": f"Mã đặt chỗ '{booking_code}' không tồn tại trong hệ thống."
            }

        # 1. Trạng thái phải là confirmed
        if booking_info.get("status") != "confirmed":
            return {
                "achieved": False,
                "reason": f"Trạng thái đơn hàng là '{booking_info.get('status')}', chưa phải 'confirmed'."
            }

        # 2. Đã thanh toán thực tế
        if not booking_info.get("paid"):
            return {
                "achieved": False,
                "reason": "Đơn hàng chưa được thanh toán thành công (paid == False)."
            }

        # 3. Giá vé không vượt trần ngân sách
        price = booking_info.get("price", 0)
        if price > self.constraints.max_price:
            return {
                "achieved": False,
                "reason": f"Giá vé thực tế {price:,} VNĐ vượt quá ngân sách {self.constraints.max_price:,} VNĐ."
            }

        # 4. Đúng ngày khởi hành
        depart_date = booking_info.get("depart_date")
        if depart_date != self.constraints.date:
            return {
                "achieved": False,
                "reason": f"Ngày bay '{depart_date}' không khớp yêu cầu '{self.constraints.date}'."
            }

        # 5. Đúng khung giờ khởi hành
        depart_time = booking_info.get("depart_time")
        if depart_time >= self.constraints.depart_before:
            return {
                "achieved": False,
                "reason": f"Giờ bay '{depart_time}' không thoả mãn trước {self.constraints.depart_before}."
            }

        return {
            "achieved": True,
            "reason": "Mọi tiêu chí hoàn thành được kiểm chứng độc lập bằng code thành công 100%.",
            "booking": booking_info
        }
