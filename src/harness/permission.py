"""
Lớp 3 Harness: Kiểm quyền & Điểm dừng phê duyệt (Permission & Human Approval).
Slide 35, 41, 44 Buổi 03:
- Kiểm quyền chạy TRƯỚC KHI thực thi tool (#0 trong checklist).
- Agent chạm tới hành động vượt thẩm quyền thì dừng lại chờ phê duyệt con người.
- Quy tắc ví dụ: Vé không hoàn tiền (non-refundable) hoặc giá > 1.500.000 VNĐ cần người duyệt.
"""
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class PermissionDecision(BaseModel):
    """Quyết định kiểm quyền từ Harness."""
    allowed: bool = Field(description="Cho phép thực thi ngay hay không")
    requires_approval: bool = Field(default=False, description="Có yêu cầu con người phê duyệt hay không")
    reason: Optional[str] = Field(default=None, description="Lý do cụ thể")
    flight_id: Optional[str] = Field(default=None)
    seat_number: Optional[str] = Field(default=None)
    price: Optional[int] = Field(default=None)
    refundable: Optional[bool] = Field(default=None)


class PermissionGatekeeper:
    """
    Cổng gác quyền hạn cho Agent.
    Được gọi ở bước #0 trước khi bất kỳ lệnh book_seat hoặc pay nào được thực thi.
    """
    def __init__(self, approval_threshold_price: int = 1_500_000, allow_non_refundable: bool = False):
        self.approval_threshold_price = approval_threshold_price
        self.allow_non_refundable = allow_non_refundable

    def inspect_tool_call(
        self,
        tool_name: str,
        args: Dict[str, Any],
        flight_details: Optional[Dict[str, Any]] = None
    ) -> PermissionDecision:
        """
        Kiểm tra quyền hạn của hành động sắp làm.
        Slide 41: V3 model định gọi book_seat("VN122","12A") · 1.950.000đ · không hoàn
        -> Hỏi vì sao: vượt hạn mức 1.500.000đ và không hoàn được.
        """
        if tool_name == "book_seat":
            if flight_details:
                price = flight_details.get("price", 0)
                refundable = flight_details.get("refundable", True)
                flight_id = flight_details.get("flight") or args.get("flight_id")
                seat = args.get("seat_number")

                # Kiểm tra 2 điều kiện cần phê duyệt:
                needs_approval = False
                reasons = []

                if price > self.approval_threshold_price:
                    needs_approval = True
                    reasons.append(f"Giá vé ({price:,} VNĐ) vượt hạn mức tự duyệt ({self.approval_threshold_price:,} VNĐ)")

                if not refundable and not self.allow_non_refundable:
                    needs_approval = True
                    reasons.append("Vé thuộc loại không hoàn tiền (non-refundable)")

                if needs_approval:
                    return PermissionDecision(
                        allowed=False,
                        requires_approval=True,
                        reason=" & ".join(reasons),
                        flight_id=flight_id,
                        seat_number=seat,
                        price=price,
                        refundable=refundable
                    )

        # Mặc định các hành động khác hợp lệ trong phạm vi thẩm quyền
        return PermissionDecision(allowed=True, requires_approval=False)
