import unittest
from src.domain.models import FlightConstraints
from src.tools.flight_tools import _GLOBAL_DB
from src.agents.react_agent import ReActFlightAgent


class TestReActAgent(unittest.TestCase):

    def setUp(self):
        _GLOBAL_DB.reset()
        self.constraints = FlightConstraints(
            origin="SGN",
            destination="DAD",
            date="2026-10-07",
            depart_before="12:00",
            max_price=2000000,
        )

    def test_react_happy_path_success(self):
        agent = ReActFlightAgent(
            constraints=self.constraints,
            db=_GLOBAL_DB,
            auto_approve_human_gate=True,
        )
        result = agent.run("Book a flight from SGN to DAD on 2026-10-07.")
        self.assertTrue(result.success)
        self.assertEqual(result.finish_reason, "GOAL_ACHIEVED")
        self.assertIsNotNone(result.booking_code)

    def test_react_human_approval_pause(self):
        agent = ReActFlightAgent(
            constraints=self.constraints,
            db=_GLOBAL_DB,
            approval_threshold_price=1500000,
            auto_approve_human_gate=False,
        )
        result = agent.run("Book a flight from SGN to DAD.")
        self.assertFalse(result.success)
        self.assertEqual(result.finish_reason, "NEED_HUMAN_APPROVAL")
        self.assertIsNotNone(result.handoff_report)

    def test_react_impossible_constraints_stall(self):
        impossible = FlightConstraints(
            origin="SGN",
            destination="DAD",
            date="2026-10-07",
            depart_before="12:00",
            max_price=500000,
        )
        agent = ReActFlightAgent(constraints=impossible, db=_GLOBAL_DB)
        result = agent.run("Book flight under 500k.")
        self.assertFalse(result.success)
        self.assertEqual(result.finish_reason, "STALL_DETECTED")


if __name__ == "__main__":
    unittest.main()
