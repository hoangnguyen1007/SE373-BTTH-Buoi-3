"""
Định nghĩa 5 kịch bản Benchmark thực nghiệm kiểm định 3 mẫu thiết kế Agent.
Dựa trên các tình huống đặc trưng được trình bày trong Slide Buổi 03:
1. Happy Path: Luồng chuẩn hoàn thành nhiệm vụ.
2. Environmental Drift / Out-of-stock: Biến động môi trường đột ngột (hết ghế ưu tiên).
3. Permission Gatekeeper: Chạm trần kiểm quyền (Slide 41).
4. Impossible Constraints: Ràng buộc bất khả thi để thử thách bế tắc (Slide 61-63).
5. Loop Detection: Thử thách cơ chế ngắt vòng lặp vô hạn (Slide 45, 46).
"""
from typing import List, Callable, Optional, Dict, Any
from pydantic import BaseModel, Field
from src.domain.models import FlightConstraints, Flight
from src.tools.flight_tools import MockFlightDatabase


class BenchmarkScenario(BaseModel):
    """Một kịch bản thử nghiệm đánh giá chất lượng Agent."""
    scenario_id: str = Field(description="Mã kịch bản (vd: SC1, SC2...)")
    title: str = Field(description="Tên kịch bản")
    description: str = Field(description="Mô tả bối cảnh và mục đích kiểm thử")
    goal_prompt: str = Field(description="Câu lệnh yêu cầu gửi cho Agent")
    constraints: FlightConstraints = Field(description="Ràng buộc nghiệp vụ")
    auto_approve_human_gate: bool = Field(default=True, description="Tự động duyệt cổng kiểm quyền hay dừng hỏi")
    auto_approve_plan: bool = Field(default=True, description="Tự động duyệt kế hoạch Plan-then-Execute hay không")

    def create_database(self) -> MockFlightDatabase:
        """Tạo cơ sở dữ liệu môi trường riêng biệt cho kịch bản."""
        db = MockFlightDatabase()
        if self.scenario_id == "SC2_OUT_OF_STOCK_DRIFT":
            # Thêm chuyến bay thay thế VN124 lúc 09:15
            db.flights["VN124"] = Flight(
                flight_id="VN124",
                origin="SGN",
                destination="DAD",
                depart_date="2026-10-07",
                depart_time="09:15",
                price=1890000,
                refundable=True,
                available_seats=["10A", "10B"]
            )
            # Làm chuyến bay VN122 hết sạch ghế trống để tạo độ lệch quan sát
            db.flights["VN122"].available_seats.clear()

        return db


def get_standard_scenarios() -> List[BenchmarkScenario]:
    """Trả về tập 5 kịch bản chuẩn cho đợt đánh giá so sánh."""
    return [
        BenchmarkScenario(
            scenario_id="SC1_HAPPY_PATH",
            title="Kịch bản 1: Luồng chuẩn thành công (Happy Path)",
            description="Tìm chuyến bay sáng SGN -> DAD dưới 2 triệu, ghế 12A chuyến VN122 khả dụng.",
            goal_prompt="Đặt giúp tôi 1 vé máy bay từ SGN đến DAD sáng 07/10/2026, giá dưới 2 triệu.",
            constraints=FlightConstraints(
                origin="SGN",
                destination="DAD",
                date="2026-10-07",
                depart_before="12:00",
                max_price=2000000
            ),
            auto_approve_human_gate=True,
            auto_approve_plan=True
        ),
        BenchmarkScenario(
            scenario_id="SC2_OUT_OF_STOCK_DRIFT",
            title="Kịch bản 2: Biến động môi trường (Chuyến đầu hết ghế)",
            description="Chuyến bay ưu tiên 1 (VN122) bất ngờ hết ghế. Kiểm tra khả năng tự thích ứng của Mẫu Lai và ReAct so với sự đổ vỡ của Plan-then-Execute.",
            goal_prompt="Đặt vé máy bay sáng 07/10/2026 SGN đến DAD dưới 2 triệu.",
            constraints=FlightConstraints(
                origin="SGN",
                destination="DAD",
                date="2026-10-07",
                depart_before="12:00",
                max_price=2000000
            ),
            auto_approve_human_gate=True,
            auto_approve_plan=True
        ),
        BenchmarkScenario(
            scenario_id="SC3_PERMISSION_APPROVAL_GATE",
            title="Kịch bản 3: Kiểm quyền & Điểm dừng phê duyệt (Slide 41)",
            description="Chuyến VN122 có giá 1.850.000 VNĐ (> 1.500.000) và vé không hoàn tiền. Agent bắt buộc phải dừng lại và xuất báo cáo bàn giao 30s.",
            goal_prompt="Đặt vé máy bay SGN -> DAD sáng 07/10.",
            constraints=FlightConstraints(
                origin="SGN",
                destination="DAD",
                date="2026-10-07",
                depart_before="12:00",
                max_price=2000000
            ),
            auto_approve_human_gate=False, # Tắt tự duyệt để kích hoạt Handoff
            auto_approve_plan=True
        ),
        BenchmarkScenario(
            scenario_id="SC4_IMPOSSIBLE_CONSTRAINTS",
            title="Kịch bản 4: Ràng buộc bất khả thi & Chống ảo giác (Slide 57, 63)",
            description="Ngân sách 500.000 VNĐ không có chuyến nào đáp ứng. Agent phải báo dừng bế tắc thay vì bịa đặt chuyến bay ảo.",
            goal_prompt="Tìm và đặt vé máy bay SGN -> DAD sáng 07/10 với giá tối đa 500.000 VNĐ.",
            constraints=FlightConstraints(
                origin="SGN",
                destination="DAD",
                date="2026-10-07",
                depart_before="12:00",
                max_price=500000
            ),
            auto_approve_human_gate=True,
            auto_approve_plan=True
        ),
        BenchmarkScenario(
            scenario_id="SC5_PLAN_REJECTION_SAFETY",
            title="Kịch bản 5: An toàn chi phí duyệt trước (Slide 22)",
            description="Người duyệt từ chối kế hoạch của Plan-then-Execute trước khi chạy -> 0 tool nào được gọi, bảo toàn ngân sách.",
            goal_prompt="Lập kế hoạch đặt vé máy bay SGN -> DAD.",
            constraints=FlightConstraints(
                origin="SGN",
                destination="DAD",
                date="2026-10-07",
                depart_before="12:00",
                max_price=2000000
            ),
            auto_approve_human_gate=True,
            auto_approve_plan=False # Người duyệt từ chối kế hoạch
        )
    ]
