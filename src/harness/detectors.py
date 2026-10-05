"""
Bộ phát hiện lặp, bế tắc (LoopDetector) & Sensor chống ảo giác (GroundingSensor).
Slide 45, 46, 57, 59 Buổi 03:
- LoopDetector: So (tool, args) trong cửa sổ trượt và kiểm tra đại lượng tiến triển (progress).
- GroundingSensor: Đối chiếu chéo dữ liệu đầu ra với lịch sử tool observations để ngăn chặn việc bịa đặt mã chuyến bay/giá/số ghế.
"""
from collections import deque
from typing import Dict, Any, Optional, Set, List


class LoopDetector:
    """
    Cài đặt nguyên bản theo mã nguồn giảng dạy ở Slide 46 Buổi 03:
    - window: Cửa sổ quan sát gần nhất (mặc định 6 vòng).
    - repeat_k: Ngưỡng số lần trùng cùng action (tool, args) để báo lỗi 'LOOP' (mặc định 2 hoặc 3).
    - stall_n: Số vòng tiến triển (progress) đứng yên để báo lỗi 'STALL' (mặc định 5).
    """
    def __init__(self, window: int = 6, repeat_k: int = 2, stall_n: int = 5):
        self.recent = deque(maxlen=window)  # chỉ so cửa sổ gần
        self.k = repeat_k
        self.n = stall_n
        self.last = None
        self.stall = 0

    def check(self, tool: str, args: Dict[str, Any], progress: Any) -> Optional[str]:
        """
        Kiểm tra action sắp gọi có trùng lặp hoặc bài toán đang bị bế tắc hay không.
        Slide 46:
        fp = (tool, repr(sorted(args.items())))
        if self.recent.count(fp) + 1 >= self.k: return "LOOP"
        self.recent.append(fp)
        self.stall = self.stall + 1 if progress == self.last else 0
        self.last = progress
        return "STALL" if self.stall >= self.n else None
        """
        # Chuẩn hoá arguments thành tuple có thứ tự để so sánh chính xác
        fp = (tool, repr(sorted(args.items())))
        if self.recent.count(fp) + 1 >= self.k:
            return "LOOP"

        self.recent.append(fp)
        self.stall = self.stall + 1 if progress == self.last else 0
        self.last = progress

        return "STALL" if self.stall >= self.n else None

    def reset(self):
        """Khôi phục trạng thái bộ phát hiện."""
        self.recent.clear()
        self.last = None
        self.stall = 0


class GroundingSensor:
    """
    Sensor đối chiếu dữ liệu với kết quả thực tế từ Tools (Anti-Hallucination).
    Slide 57, 58, 59 Buổi 03:
    Kiểm tra chéo toàn bộ mã chuyến bay, số ghế, giá vé, mã đặt chỗ mà Agent khẳng định
    với tập dữ liệu thật mà các tools đã từng trả về trong phiên chạy.
    """
    def __init__(self):
        self.observed_flights: Set[str] = set()
        self.observed_seats: Set[str] = set()
        self.observed_prices: Set[int] = set()
        self.observed_bookings: Set[str] = set()
        self.has_called_book_seat: bool = False
        self.has_called_pay: bool = False

    def ingest_tool_observation(self, tool_name: str, args: Dict[str, Any], result: Dict[str, Any]):
        """Ghi nhận dữ liệu thực tế từ output của tool vào kho tri thức kiểm chứng."""
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
            self.has_called_book_seat = True
            self.observed_bookings.add(result.get("booking_code"))
            self.observed_flights.add(result.get("flight"))
            self.observed_seats.add(result.get("seat"))
            self.observed_prices.add(result.get("price"))

        elif tool_name == "pay" and result.get("status") == "paid":
            self.has_called_pay = True
            self.observed_bookings.add(result.get("booking_code"))

    def check_claim(
        self,
        flight_id: Optional[str] = None,
        seat: Optional[str] = None,
        price: Optional[int] = None,
        booking_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Kiểm tra tính xác thực của thông tin do Agent đưa ra.
        Slide 59:
        'VN999' -> không có nguồn X
        'seat 5C' -> không có nguồn X
        '1,200,000' -> không có nguồn X
        'Booked' -> không có lời gọi book_seat / pay X
        """
        hallucinations: List[str] = []

        if flight_id and flight_id not in self.observed_flights:
            hallucinations.append(f"Mã chuyến bay '{flight_id}' không có trong dữ liệu quan sát từ tool.")

        if seat and seat not in self.observed_seats:
            hallucinations.append(f"Số ghế '{seat}' chưa từng xuất hiện trong danh sách ghế còn trống.")

        if price and price not in self.observed_prices:
            hallucinations.append(f"Giá vé '{price:,} VNĐ' không tồn tại trong kết quả báo giá của các chuyến.")

        if booking_code and booking_code not in self.observed_bookings:
            hallucinations.append(f"Mã đặt chỗ '{booking_code}' là thông tin giả lập, chưa từng được hệ thống cấp.")

        return {
            "grounded": len(hallucinations) == 0,
            "violations": hallucinations
        }
