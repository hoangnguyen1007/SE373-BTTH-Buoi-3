"""
Unit tests cho Mẫu Lai ReAct + Plan (Hybrid Dynamic Replanning Agent - Commit 5).
Kiểm thử tính năng tự thích ứng và Re-planning khi môi trường thay đổi (Slide 24, 26).
"""
import unittest
from src.domain.models import FlightConstraints, Flight
from src.tools.flight_tools import MockFlightDatabase
from src.agents.hybrid_agent import HybridFlightAgent


class TestHybridAgent(unittest.TestCase):

    def setUp(self):
        self.db = MockFlightDatabase()
        self.constraints = FlightConstraints(
            origin="SGN",
            destination="DAD",
            date="2026-10-07",
            depart_before="12:00",
            max_price=2000000
        )

    def test_hybrid_happy_path_success(self):
        """Mẫu lai chạy theo Todo List hoàn thành và được kiểm chứng độc lập."""
        agent = HybridFlightAgent(
            constraints=self.constraints,
            db=self.db,
            auto_approve_human_gate=True
        )

        result = agent.run("Đặt vé máy bay sáng 07/10 SGN -> DAD.")

        self.assertTrue(result.success)
        self.assertEqual(result.finish_reason, "GOAL_ACHIEVED")
        self.assertIsNotNone(result.booking_code)
        # Token của mẫu lai cân bằng giữa ReAct (20.000) và Plan-then-Execute (3.000)
        self.assertTrue(3000 <= result.total_tokens <= 15000)

    def test_hybrid_dynamic_replanning_on_drift(self):
        """
        Chứng minh ưu thế quyết định của Mẫu Lai (Slide 24, 26):
        Khi chuyến bay ưu tiên 1 (VN122) bất ngờ hết ghế,
        Mẫu Lai tự động phát hiện 'Observation đổi đáng kể' -> Kích hoạt Replanner
        để chuyển hướng đặt chuyến bay thay thế (VN124) thành công!
        Trong khi Plan-then-Execute tĩnh đã bị gãy hoàn toàn trong tình huống này.
        """
        # Thêm chuyến bay thay thế hợp lệ VN124 vào DB
        self.db.flights["VN124"] = Flight(
            flight_id="VN124",
            origin="SGN",
            destination="DAD",
            depart_date="2026-10-07",
            depart_time="09:15",
            price=1890000,
            refundable=True,
            available_seats=["10A", "10B"]
        )
        # Giả lập chuyến bay đầu tiên VN122 bị hết sạch ghế
        self.db.flights["VN122"].available_seats.clear()

        agent = HybridFlightAgent(
            constraints=self.constraints,
            db=self.db,
            auto_approve_human_gate=True
        )

        result = agent.run("Đặt vé máy bay SGN -> DAD.")

        # Mẫu Lai phải thành công nhờ tính năng Replanning
        self.assertTrue(result.success)
        self.assertEqual(result.finish_reason, "GOAL_ACHIEVED")
        self.assertTrue(agent.replan_count >= 1)

        # Kiểm tra xem có trace ghi nhận Replanning không
        replan_events = [t for t in result.trace if t.harness_event and "QUAN SÁT ĐỔI ĐÁNG KỂ" in t.harness_event]
        self.assertTrue(len(replan_events) >= 1)

    def test_hybrid_human_approval_pause(self):
        """Mẫu lai tôn trọng kiểm quyền và dừng chờ duyệt con người (Slide 41)."""
        agent = HybridFlightAgent(
            constraints=self.constraints,
            db=self.db,
            approval_threshold_price=1500000,
            auto_approve_human_gate=False # Bắt buộc dừng hỏi người
        )

        result = agent.run("Đặt vé máy bay SGN -> DAD.")

        self.assertFalse(result.success)
        self.assertEqual(result.finish_reason, "NEED_HUMAN_APPROVAL")
        self.assertIsNotNone(result.handoff_report)


if __name__ == "__main__":
    unittest.main()
