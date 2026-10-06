import unittest
from src.domain.models import FlightConstraints
from src.tools.flight_tools import _GLOBAL_DB
from src.agents.plan_execute_agent import PlanThenExecuteFlightAgent


class TestPlanExecuteAgent(unittest.TestCase):

    def setUp(self):
        _GLOBAL_DB.reset()
        self.constraints = FlightConstraints(
            origin="SGN",
            destination="DAD",
            date="2026-10-07",
            depart_before="12:00",
            max_price=2000000,
        )

    def test_plan_execute_happy_path(self):
        agent = PlanThenExecuteFlightAgent(
            constraints=self.constraints,
            db=_GLOBAL_DB,
            auto_approve_plan=True,
        )
        result = agent.run("Book flight SGN -> DAD.")
        self.assertTrue(result.success)
        self.assertEqual(result.finish_reason, "GOAL_ACHIEVED")
        self.assertIsNotNone(result.booking_code)
        self.assertTrue(result.total_tokens < 20000)

    def test_plan_review_rejection_safety(self):
        agent = PlanThenExecuteFlightAgent(
            constraints=self.constraints,
            db=_GLOBAL_DB,
            auto_approve_plan=False,
        )
        result = agent.run("Book flight SGN -> DAD.")
        self.assertFalse(result.success)
        self.assertEqual(result.finish_reason, "NEED_HUMAN_APPROVAL")
        self.assertEqual(len(_GLOBAL_DB.bookings), 0)

    def test_plan_fragility_on_environment_change(self):
        _GLOBAL_DB.flights["VN122"].available_seats.clear()
        agent = PlanThenExecuteFlightAgent(
            constraints=self.constraints,
            db=_GLOBAL_DB,
            auto_approve_plan=True,
        )
        result = agent.run("Book flight SGN -> DAD.")
        self.assertFalse(result.success)
        self.assertEqual(result.finish_reason, "PLAN_EXECUTION_FAILED")
        self.assertIsNotNone(result.handoff_report)


if __name__ == "__main__":
    unittest.main()
