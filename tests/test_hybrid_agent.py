import unittest
from src.domain.models import FlightConstraints, Flight
from src.tools.flight_tools import _GLOBAL_DB
from src.agents.hybrid_agent import HybridFlightAgent


class TestHybridAgent(unittest.TestCase):

    def setUp(self):
        _GLOBAL_DB.reset()
        self.constraints = FlightConstraints(
            origin="SGN",
            destination="DAD",
            date="2026-10-07",
            depart_before="12:00",
            max_price=2000000,
        )

    def test_hybrid_happy_path_success(self):
        agent = HybridFlightAgent(
            constraints=self.constraints,
            db=_GLOBAL_DB,
            auto_approve_human_gate=True,
        )
        result = agent.run("Book flight SGN -> DAD.")
        self.assertTrue(result.success)
        self.assertEqual(result.finish_reason, "GOAL_ACHIEVED")
        self.assertIsNotNone(result.booking_code)

    def test_hybrid_dynamic_replanning_on_drift(self):
        _GLOBAL_DB.flights["VN124"] = Flight(
            flight_id="VN124",
            origin="SGN",
            destination="DAD",
            depart_date="2026-10-07",
            depart_time="09:15",
            price=1890000,
            refundable=True,
            available_seats=["10A", "10B"],
        )
        _GLOBAL_DB.flights["VN122"].available_seats.clear()

        agent = HybridFlightAgent(
            constraints=self.constraints,
            db=_GLOBAL_DB,
            auto_approve_human_gate=True,
        )
        result = agent.run("Book flight SGN -> DAD.")
        self.assertTrue(result.success)
        self.assertEqual(result.finish_reason, "GOAL_ACHIEVED")
        self.assertTrue(agent.replan_count >= 1)

    def test_hybrid_human_approval_pause(self):
        agent = HybridFlightAgent(
            constraints=self.constraints,
            db=_GLOBAL_DB,
            approval_threshold_price=1500000,
            auto_approve_human_gate=False,
        )
        result = agent.run("Book flight SGN -> DAD.")
        self.assertFalse(result.success)
        self.assertEqual(result.finish_reason, "NEED_HUMAN_APPROVAL")
        self.assertIsNotNone(result.handoff_report)


if __name__ == "__main__":
    unittest.main()
