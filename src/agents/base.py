"""
Cấu trúc nền tảng cho các kiến trúc Agent đặt vé máy bay.
Slide 10, 11, 20 Buổi 03:
- Sơ đồ trục vòng lặp AI Agent.
- Bộ lưu vết (Trace log) từng vòng để chẩn đoán và phân tích lỗi.
- Định dạng kết quả thực thi và bàn giao thống nhất.
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from src.domain.models import FlightConstraints
from src.harness.handoff import HandoffReport


class AgentStepTrace(BaseModel):
    """Lưu vết từng bước thực thi trong vòng lặp Agent (Slide 20, 52)."""
    step_index: int = Field(description="Số thứ tự vòng lặp (1, 2, 3...)")
    thought: str = Field(description="Suy luận (Reasoning) của Agent tại bước này")
    action_tool: Optional[str] = Field(default=None, description="Tên công cụ được gọi")
    action_args: Optional[Dict[str, Any]] = Field(default=None, description="Tham số truyền vào công cụ")
    observation: Optional[Dict[str, Any]] = Field(default=None, description="Kết quả quan sát nhận được từ tool")
    harness_event: Optional[str] = Field(default=None, description="Sự kiện từ Harness (nếu có)")
    tokens_estimate: int = Field(default=0, description="Số token ước tính cho vòng này")


class AgentExecutionResult(BaseModel):
    """Kết quả hoàn thành phiên làm việc của Agent."""
    agent_type: str = Field(description="Loại kiến trúc Agent: ReAct, Plan-then-Execute, hoặc Hybrid")
    success: bool = Field(description="Mục tiêu được kiểm chứng hoàn thành thành công hay không")
    finish_reason: str = Field(description="Lý do dừng: GOAL_ACHIEVED, NEED_HUMAN_APPROVAL, LOOP_DETECTED, STALL_DETECTED, BUDGET_EXHAUSTED")
    final_message: str = Field(description="Thông điệp kết luận gửi tới người dùng")
    booking_code: Optional[str] = Field(default=None, description="Mã đặt chỗ thành công (nếu có)")
    total_steps: int = Field(default=0, description="Tổng số vòng lặp thực hiện")
    total_tokens: int = Field(default=0, description="Tổng lượng token tiêu thụ")
    duration_seconds: float = Field(default=0.0, description="Thời gian thực thi")
    trace: List[AgentStepTrace] = Field(default_factory=list, description="Toàn bộ nhật ký trace từng bước")
    handoff_report: Optional[HandoffReport] = Field(default=None, description="Báo cáo bàn giao con người (nếu cần)")

    def print_trace_summary(self):
        """In bảng tóm tắt trace trực quan, an toàn với mọi bảng mã console."""
        lines = [
            "=" * 70,
            f"BÁO CÁO THỰC THI AGENT: {self.agent_type.upper()}",
            f"Trạng thái: {'THÀNH CÔNG (100% Verified)' if self.success else 'DỪNG BẤT THƯỜNG / CHỜ DUYỆT'}",
            f"Lý do kết thúc: {self.finish_reason}",
            f"Tổng số bước: {self.total_steps} | Tổng token ước tính: {self.total_tokens:,}",
            f"Thời gian: {self.duration_seconds:.2f}s"
        ]
        if self.booking_code:
            lines.append(f"Mã đặt chỗ PNR: {self.booking_code}")
        lines.append("=" * 70)
        lines.append("NHẬT KÝ CHI TIẾT TỪNG VÒNG (TRACE LOG):")
        for st in self.trace:
            lines.append(f"\n--- [VÒNG {st.step_index}] ---")
            lines.append(f"  Thought: {st.thought}")
            if st.action_tool:
                lines.append(f"  Action: {st.action_tool}({st.action_args})")
            if st.observation:
                obs_status = st.observation.get("status")
                lines.append(f"  Observation ({obs_status}): {st.observation}")
            if st.harness_event:
                lines.append(f"  Harness Event: {st.harness_event}")
        if self.handoff_report:
            lines.append(f"\n{self.handoff_report.format_30s_view()}")
        lines.append("=" * 70)

        full_output = "\n".join(lines)
        try:
            print(full_output)
        except UnicodeEncodeError:
            # Fallback an toàn cho console Windows cp1252
            import sys
            sys.stdout.buffer.write(full_output.encode("utf-8", errors="replace") + b"\n")


class BaseFlightAgent:
    """Lớp cơ sở cho các kiến trúc Agent đặt vé máy bay."""
    def __init__(self, constraints: FlightConstraints, agent_name: str = "FlightAgent"):
        self.constraints = constraints
        self.agent_name = agent_name
