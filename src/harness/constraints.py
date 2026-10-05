"""
Lớp 1 Harness: Ràng buộc là dữ liệu (Data Constraints).
Slide 61, 63 Buổi 03:
- Giữ yêu cầu ở một chỗ cố định dưới dạng cấu trúc dữ liệu.
- Kiểm tra cơ học trước khi gọi hành động book/pay để chống lỗi quên yêu cầu ban đầu.
"""
from typing import Tuple, Optional, Dict, Any
from src.domain.models import FlightConstraints, Flight


class ConstraintValidator:
    """
    Bộ xác thực ràng buộc nghiệp vụ.
    Ngăn chặn Agent tự ý đặt vé sai giờ, sai ngày, hoặc vượt quá ngân sách đã yêu cầu.
    """
    def __init__(self, constraints: FlightConstraints):
        self.constraints = constraints

    def check_flight(self, flight_info: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Kiểm tra một chuyến bay có đáp ứng ràng buộc ban đầu hay không.
        Trả về: (hợp lệ: bool, lý do vi phạm nếu có: str)
        """
        # Kiểm tra ngày bay nếu có
        depart_date = flight_info.get("depart_date")
        if depart_date and depart_date != self.constraints.date:
            return False, f"Ngày bay '{depart_date}' không khớp ngày yêu cầu '{self.constraints.date}'."

        # Kiểm tra giờ bay
        depart_time = flight_info.get("depart") or flight_info.get("depart_time")
        if depart_time and depart_time >= self.constraints.depart_before:
            return False, (
                f"Giờ khởi hành '{depart_time}' không thoả mãn yêu cầu "
                f"phải bay trước {self.constraints.depart_before}."
            )

        # Kiểm tra giá vé
        price = flight_info.get("price")
        if price and price > self.constraints.max_price:
            return False, (
                f"Giá vé {price:,} VNĐ vượt quá ngân sách cho phép "
                f"{self.constraints.max_price:,} VNĐ."
            )

        return True, None

    def enforce_before_action(self, tool_name: str, args: Dict[str, Any], flight_data: Optional[Dict[str, Any]] = None) -> Tuple[bool, Optional[str]]:
        """
        Chặn tại tầng Harness trước khi cho phép gọi tool book_seat hoặc pay.
        Slide 63: if not CONSTRAINTS.is_ok(flight): return {"status": "denied"}
        """
        if tool_name in ["book_seat", "pay"] and flight_data:
            ok, reason = self.check_flight(flight_data)
            if not ok:
                return False, f"Harness chặn hành động '{tool_name}': {reason}"
        return True, None
