"""
Lớp 4 Harness: Bàn giao cho con người (Human Handoff).
Slide 48 Buổi 03:
- "Bàn giao tốt là bàn giao mà người nhận trả lời được trong 30 giây."
- Gồm 3 thành phần bắt buộc:
  1. Trạng thái: Đã làm tới đâu, hành động nào đã gây tác dụng phụ.
  2. Những gì đã thử: Hướng nào đã hỏng và vì sao.
  3. Câu hỏi cụ thể: Đi thẳng vào vấn đề để người nhận quyết định ngay.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class HandoffReport(BaseModel):
    """Báo cáo bàn giao ngữ cảnh cho con người chuẩn 30 giây."""
    current_status: str = Field(description="Đã làm tới đâu, tác dụng phụ hiện tại")
    tried_attempts: List[str] = Field(description="Các hướng đã thử, lý do thất bại")
    specific_question: str = Field(description="Câu hỏi cụ thể để người nhận chốt quyết định")
    recommendation: Optional[str] = Field(default=None, description="Đề xuất tối ưu của Agent")

    def format_30s_view(self) -> str:
        """Định dạng trực quan giúp đọc và hiểu trong 30 giây."""
        attempts_str = "\n".join([f"  - {attempt}" for attempt in self.tried_attempts])
        return (
            "====================== BÀN GIAO NGỮ CẢNH (30s HANDOFF) ======================\n"
            f"[1. TRẠNG THÁI HIỆN TẠI]:\n{self.current_status}\n\n"
            f"[2. NHỮNG GÌ ĐÃ THỬ]:\n{attempts_str}\n\n"
            f"[3. ĐỀ XUẤT CỦA AGENT]:\n{self.recommendation or 'Chờ người duyệt chỉ định hướng tiếp theo.'}\n\n"
            f"[4. CÂU HỎI QUYẾT ĐỊNH CỤ THỂ]:\n👉 {self.specific_question}\n"
            "=============================================================================="
        )


class HumanHandoffManager:
    """Quản lý việc tạo báo cáo bàn giao khi Agent dừng bất thường hoặc cần phê duyệt."""

    @staticmethod
    def create_approval_handoff(
        flight_id: str,
        depart_time: str,
        price: int,
        refundable: bool,
        seat: str,
        reasons: List[str]
    ) -> HandoffReport:
        status_desc = (
            f"Đã tìm thấy chuyến {flight_id} lúc {depart_time} phù hợp khung giờ sáng. "
            f"Ghế định chọn: {seat}. Chưa trừ tiền tài khoản."
        )
        tried = [
            f"Đã quét các chuyến bay trong ngày: các chuyến khác vượt quá ngân sách hoặc bay vào buổi chiều.",
            f"Chuyến {flight_id} thoả mãn giờ ({depart_time}) và ngân sách ({price:,} VNĐ), nhưng gặp ràng buộc quyền hạn: {', '.join(reasons)}."
        ]
        question = (
            f"Bạn có đồng ý phê duyệt đặt ghế {seat} chuyến {flight_id} với giá {price:,} VNĐ "
            f"({'Vé không hoàn tiền' if not refundable else 'Vé có hoàn tiền'}) hay không? [YES/NO]"
        )
        return HandoffReport(
            current_status=status_desc,
            tried_attempts=tried,
            specific_question=question,
            recommendation=f"Nên phê duyệt vì đây là chuyến duy nhất thoả mãn giờ bay sáng trước 12:00."
        )

    @staticmethod
    def create_failure_handoff(
        reason: str,
        attempts: List[str],
        question: str
    ) -> HandoffReport:
        return HandoffReport(
            current_status=f"Tác vụ bị tạm dừng do: {reason}",
            tried_attempts=attempts,
            specific_question=question,
            recommendation="Xem xét mở rộng khoảng giá hoặc nới lỏng khung giờ bay."
        )
