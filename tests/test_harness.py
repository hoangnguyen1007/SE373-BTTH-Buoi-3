import unittest
from src.domain.models import FlightConstraints
from src.tools.flight_tools import _GLOBAL_DB, book_seat, pay
from src.harness.constraints import ConstraintValidator
from src.harness.verification import ComputationalVerifier
from src.harness.permission import PermissionGatekeeper
from src.harness.handoff import HumanHandoffManager
from src.harness.detectors import LoopDetector, GroundingSensor
from src.harness.budget import ExecutionBudget


class TestHarnessArchitecture(unittest.TestCase):

    def setUp(self):
        _GLOBAL_DB.reset()
        self.constraints = FlightConstraints(
            origin="SGN",
            destination="DAD",
            date="2026-10-07",
            depart_before="12:00",
            max_price=2000000,
        )

    def test_layer1_constraint_validator(self):
        validator = ConstraintValidator(self.constraints)

        ok, reason = validator.check_flight({
            "flight": "VN122",
            "depart": "08:10",
            "price": 1850000,
            "depart_date": "2026-10-07",
        })
        self.assertTrue(ok)
        self.assertIsNone(reason)

        ok_qh, reason_qh = validator.check_flight({
            "flight": "QH118",
            "depart": "15:40",
            "price": 1640000,
            "depart_date": "2026-10-07",
        })
        self.assertFalse(ok_qh)
        self.assertIn("12:00", reason_qh)

        enforce_ok, enforce_reason = validator.enforce_before_action(
            "book_seat",
            {"flight_id": "QH118", "seat_number": "14A"},
            flight_data={"flight": "QH118", "depart": "15:40", "price": 1640000},
        )
        self.assertFalse(enforce_ok)
        self.assertIn("Harness blocked", enforce_reason)

    def test_layer2_computational_verifier(self):
        verifier = ComputationalVerifier(self.constraints, db=_GLOBAL_DB)

        res_empty = verifier.verify("NON_EXIST")
        self.assertFalse(res_empty["achieved"])

        book_res = book_seat.invoke({"flight_id": "VN122", "seat_number": "12A"})
        code = book_res["booking_code"]

        res_held = verifier.verify(code)
        self.assertFalse(res_held["achieved"])

        pay.invoke({"booking_code": code, "payment_method": "corp_card"})
        res_done = verifier.verify(code)
        self.assertTrue(res_done["achieved"])

    def test_layer3_permission_gatekeeper(self):
        gatekeeper = PermissionGatekeeper(approval_threshold_price=1500000, allow_non_refundable=False)

        decision = gatekeeper.inspect_tool_call(
            "book_seat",
            {"flight_id": "VN122", "seat_number": "12A"},
            flight_details={"flight": "VN122", "price": 1850000, "refundable": False},
        )
        self.assertFalse(decision.allowed)
        self.assertTrue(decision.requires_approval)

        normal = gatekeeper.inspect_tool_call(
            "book_seat",
            {"flight_id": "CHEAP1", "seat_number": "1A"},
            flight_details={"flight": "CHEAP1", "price": 1200000, "refundable": True},
        )
        self.assertTrue(normal.allowed)
        self.assertFalse(normal.requires_approval)

    def test_layer4_human_handoff_manager(self):
        report = HumanHandoffManager.create_approval_handoff(
            flight_id="VN122",
            depart_time="08:10",
            price=1850000,
            refundable=False,
            seat="12A",
            reasons=["Price exceeds 1.5M threshold", "Non-refundable ticket"],
        )
        self.assertIn("VN122", report.current_status)
        self.assertTrue(len(report.tried_attempts) >= 2)
        view = report.format_30s_view()
        self.assertIn("30s HUMAN HANDOFF", view)

    def test_loop_detector_slide_46(self):
        detector = LoopDetector(window=6, repeat_k=2, stall_n=2)

        res1 = detector.check("search_flights", {"date": "2026-10-07"}, progress=1)
        self.assertIsNone(res1)

        res2 = detector.check("search_flights", {"date": "2026-10-07"}, progress=1)
        self.assertEqual(res2, "LOOP")

        detector.reset()
        detector.n = 2
        detector.check("tool_a", {"x": 1}, progress=10)
        detector.check("tool_b", {"x": 2}, progress=10)
        stall = detector.check("tool_c", {"x": 3}, progress=10)
        self.assertEqual(stall, "STALL")

    def test_grounding_sensor_anti_hallucination(self):
        sensor = GroundingSensor()
        sensor.ingest_tool_observation(
            "check_seat",
            {"flight_id": "VN122"},
            {"status": "ok", "flight": "VN122", "price": 1850000, "available_seats": ["12A", "12B"]},
        )

        valid = sensor.check_claim(flight_id="VN122", seat="12A", price=1850000)
        self.assertTrue(valid["grounded"])

        fake = sensor.check_claim(flight_id="VN999", seat="5C", price=1200000)
        self.assertFalse(fake["grounded"])

    def test_execution_budget(self):
        budget = ExecutionBudget(max_steps=3, timeout_seconds=10.0)
        self.assertFalse(budget.is_exhausted()["exhausted"])

        budget.record_step(500)
        budget.record_step(500)
        budget.record_step(500)
        self.assertTrue(budget.is_exhausted()["exhausted"])


if __name__ == "__main__":
    unittest.main()
