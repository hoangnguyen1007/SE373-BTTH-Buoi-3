"""
Domain models for Flight Booking System.
Định nghĩa các cấu trúc dữ liệu chuẩn hoá cho hệ thống Agent & Harness.
"""
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class BookingStatus(str, Enum):
    """Trạng thái vòng đời của một giao dịch đặt chỗ."""
    HELD = "held"              # Ghế đã giữ tạm thời, chờ thanh toán
    CONFIRMED = "confirmed"    # Đã thanh toán và xuất vé thành công
    CANCELLED = "cancelled"    # Đã huỷ hoặc hết hạn thanh toán


class Flight(BaseModel):
    """Mô hình dữ liệu cho chuyến bay."""
    flight_id: str = Field(description="Mã hiệu chuyến bay (vd: VN122, QH118)")
    origin: str = Field(description="Sân bay đi (vd: SGN)")
    destination: str = Field(description="Sân bay đến (vd: DAD)")
    depart_date: str = Field(description="Ngày khởi hành định dạng YYYY-MM-DD")
    depart_time: str = Field(description="Giờ khởi hành định dạng HH:MM")
    price: int = Field(description="Giá vé niêm yết (VNĐ)")
    refundable: bool = Field(default=True, description="Vé có hoàn tiền được hay không")
    available_seats: List[str] = Field(default_factory=list, description="Danh sách các ghế còn trống")


class Booking(BaseModel):
    """Mô hình dữ liệu chi tiết đặt chỗ."""
    booking_code: str = Field(description="Mã đặt chỗ duy nhất (PNR, vd: 4XJ2)")
    flight_id: str = Field(description="Mã chuyến bay được đặt")
    seat_number: str = Field(description="Số ghế (vd: 12A)")
    price: int = Field(description="Giá tiền vé thực tế (VNĐ)")
    depart_date: str = Field(description="Ngày bay")
    depart_time: str = Field(description="Giờ bay")
    refundable: bool = Field(default=True, description="Tính chất hoàn tiền của vé")
    status: BookingStatus = Field(default=BookingStatus.HELD, description="Trạng thái đặt chỗ")
    paid: bool = Field(default=False, description="Trạng thái thanh toán")
    payment_method: Optional[str] = Field(default=None, description="Phương thức thanh toán đã dùng")


class FlightConstraints(BaseModel):
    """
    Ràng buộc yêu cầu của người dùng dưới dạng dữ liệu (Data Constraints).
    Được dùng bởi Harness để kiểm tra vi phạm trước khi cho phép gọi action nguy hiểm.
    Slide 61, 63 Buổi 03: Ràng buộc là dữ liệu.
    """
    origin: str = Field(default="SGN", description="Điểm xuất phát mong muốn")
    destination: str = Field(default="DAD", description="Điểm đến mong muốn")
    date: str = Field(default="2026-10-07", description="Ngày bay cần tìm (YYYY-MM-DD)")
    depart_before: str = Field(default="12:00", description="Giờ khởi hành phải trước mốc này")
    max_price: int = Field(default=2_000_000, description="Ngân sách tối đa cho vé (VNĐ)")

    def is_ok(self, flight: Flight) -> bool:
        """
        Kiểm tra xem một chuyến bay có thoả mãn đầy đủ các ràng buộc cứng hay không.
        Slide 63 Buổi 03: if not CONSTRAINTS.is_ok(flight): return {"status": "denied"}
        """
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
    """
    Chuẩn hoá cấu trúc phản hồi từ Mock Tools (Slide 13, 56, 66 Buổi 03).
    Bao gồm cả mã lỗi chi tiết và chỉ dẫn sửa lỗi (hint) cho Agent.
    """
    status: str = Field(description="'ok', 'error', 'invalid_param', hoặc 'denied'")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Dữ liệu trả về khi thành công")
    error: Optional[str] = Field(default=None, description="Mã lỗi hệ thống")
    param: Optional[str] = Field(default=None, description="Tham số bị sai (nếu có)")
    hint: Optional[str] = Field(default=None, description="Gợi ý hành động hoặc định dạng đúng cho Agent")
