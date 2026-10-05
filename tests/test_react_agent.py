"""
Unit tests cho ReAct Flight Booking Agent (Commit 3).
"""
import unittest
from src.domain.models import FlightConstraints
from src.tools.flight_tools import MockFlightDatabase
from src.agents.react_agent import ReActFlightAgent


class TestReActAgent(unittest.TestCase):

    def setUp(self):
        self.db = MockFlightDatabase()
        self.constraints = FlightConstraints(
            origin="SGN",
            destination="DAD",
            date="2026-10-07",
            depart_before="12:00",
            max_price=2000000
        )

    def test_react_happy_path_success(self):
        """ReAct Agent hoàn thành chu trình đặt vé tự động và được kiểm chứng bằng code."""
        agent = ReActFlightAgent(
            constraints=self.constraints,
            db=self.db,
            auto_approve_human_gate=True
        )

        result = agent.run("Đặt vé máy bay SGN đến DAD sáng 07/10 dưới 2 triệu.")

        self.assertTrue(result.success)
        self.assertEqual(result.finish_reason, "GOAL_ACHIEVED")
        self.assertIsNotNone(result.booking_code)
        self.assertTrue(result.total_steps >= 4)
        self.assertTrue(result.total_tokens > 0)
        self.assertIn("thành công", result.final_message.lower())

    def test_react_human_approval_pause(self):
        """ReAct Agent dừng chờ con người phê duyệt khi chạm hành động vượt quyền (Slide 41)."""
        agent = ReActFlightAgent(
            constraints=self.constraints,
            db=self.db,
            approval_threshold_price=1500000,
            auto_approve_human_gate=False # Kích hoạt dừng để hỏi người
        )

        result = agent.run("Đặt vé máy bay SGN đến DAD sáng 07/10 dưới 2 triệu.")

        self.assertFalse(result.success)
        self.assertEqual(result.finish_reason, "NEED_HUMAN_APPROVAL")
        self.assertIsNotNone(result.handoff_report)
        self.assertIn("phê duyệt", result.handoff_report.specific_question.lower())

    def test_react_impossible_constraints_stall(self):
        """Khi yêu cầu mức giá phi thực tế (dưới 500k), Agent không bịa đặt mà dừng an toàn."""
        impossible_constraints = FlightConstraints(
            origin="SGN",
            destination="DAD",
            date="2026-10-07",
            depart_before="12:00",
            max_price=500000 # Không có chuyến nào dưới 500k
        )
        agent = ReActFlightAgent(
            constraints=impossible_constraints,
            db=self.db,
            auto_approve_human_gate=True
        )

        result = agent.run("Đặt vé máy bay SGN đến DAD sáng 07/10 dưới 500 nghìn.")

        self.assertFalse(result.success)
        self.assertEqual(result.finish_reason, "STALL_DETECTED")
        self.assertIsNone(result.booking_code)


if __name__ == "__main__":
    unittest.main()
