"""
Unit tests cho Plan-then-Execute Flight Booking Agent (Commit 4).
Kiểm thử tính năng duyệt trước và đặc tính nhạy cảm khi có biến cố (Slide 22, 23).
"""
import unittest
from src.domain.models import FlightConstraints
from src.tools.flight_tools import MockFlightDatabase
from src.agents.plan_execute_agent import PlanThenExecuteFlightAgent


class TestPlanExecuteAgent(unittest.TestCase):

    def setUp(self):
        self.db = MockFlightDatabase()
        self.constraints = FlightConstraints(
            origin="SGN",
            destination="DAD",
            date="2026-10-07",
            depart_before="12:00",
            max_price=2000000
        )

    def test_plan_execute_happy_path(self):
        """Kế hoạch được duyệt -> Thực thi tuần tự thành công -> Kiểm chứng bằng code."""
        agent = PlanThenExecuteFlightAgent(
            constraints=self.constraints,
            db=self.db,
            auto_approve_plan=True
        )

        result = agent.run("Đặt vé máy bay SGN -> DAD sáng 07/10 theo kế hoạch.")

        self.assertTrue(result.success)
        self.assertEqual(result.finish_reason, "GOAL_ACHIEVED")
        self.assertIsNotNone(result.booking_code)
        # Plan-then-execute dùng ít token hơn ReAct (Slide 23)
        self.assertTrue(result.total_tokens < 20000)

    def test_plan_review_rejection_safety(self):
        """Slide 22: Người duyệt từ chối kế hoạch trước khi chạy -> 0 tool thực thi."""
        agent = PlanThenExecuteFlightAgent(
            constraints=self.constraints,
            db=self.db,
            auto_approve_plan=False # Không duyệt
        )

        result = agent.run("Đặt vé máy bay SGN -> DAD sáng 07/10.")

        self.assertFalse(result.success)
        self.assertEqual(result.finish_reason, "NEED_HUMAN_APPROVAL")
        self.assertIsNotNone(result.handoff_report)
        self.assertIn("phê duyệt", result.handoff_report.specific_question.lower())
        # Không có booking nào được tạo trong DB
        self.assertEqual(len(self.db.bookings), 0)

    def test_plan_fragility_on_environment_change(self):
        """Slide 23: Lỗi ở bước đầu làm hỏng toàn bộ sau (Kế hoạch tĩnh bị gãy khi hết ghế)."""
        # Giả lập tình huống: Chuyến VN122 bị ai đó đặt hết sạch ghế trước
        self.db.flights["VN122"].available_seats.clear()

        agent = PlanThenExecuteFlightAgent(
            constraints=self.constraints,
            db=self.db,
            auto_approve_plan=True
        )

        result = agent.run("Đặt vé máy bay SGN -> DAD.")

        self.assertFalse(result.success)
        self.assertEqual(result.finish_reason, "PLAN_EXECUTION_FAILED")
        self.assertIsNotNone(result.handoff_report)


if __name__ == "__main__":
    unittest.main()
