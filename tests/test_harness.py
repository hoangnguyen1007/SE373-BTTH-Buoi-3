"""
Unit tests cho tầng Harness bảo vệ (Commit 2).
Kiểm thử toàn diện 4 lớp Harness bắt buộc và các Sensors theo Slide Buổi 03.
"""
import unittest
from src.domain.models import FlightConstraints, Flight, Booking, BookingStatus
from src.tools.flight_tools import MockFlightDatabase, book_seat, pay
from src.harness.constraints import ConstraintValidator
from src.harness.verification import ComputationalVerifier
from src.harness.permission import PermissionGatekeeper
from src.harness.handoff import HumanHandoffManager
from src.harness.detectors import LoopDetector, GroundingSensor
from src.harness.budget import ExecutionBudget


class TestHarnessArchitecture(unittest.TestCase):

    def setUp(self):
        self.db = MockFlightDatabase()
        self.constraints = FlightConstraints(
            origin="SGN",
            destination="DAD",
            date="2026-10-07",
            depart_before="12:00",
            max_price=2000000
        )

    def test_layer1_constraint_validator(self):
        """Lớp 1: Ràng buộc là dữ liệu (Slide 61, 63)."""
        validator = ConstraintValidator(self.constraints)

        # Chuyến VN122 (08:10, 1.850.000) -> Thỏa mãn
        ok, reason = validator.check_flight({
            "flight": "VN122",
            "depart": "08:10",
            "price": 1850000,
            "depart_date": "2026-10-07"
        })
        self.assertTrue(ok)
        self.assertIsNone(reason)

        # Chuyến QH118 (15:40, 1.640.000) -> Vi phạm giờ bay (> 12:00)
        ok_qh, reason_qh = validator.check_flight({
            "flight": "QH118",
            "depart": "15:40",
            "price": 1640000,
            "depart_date": "2026-10-07"
        })
        self.assertFalse(ok_qh)
        self.assertIn("12:00", reason_qh)

        # Chặn tại tầng trước khi thực thi
        enforce_ok, enforce_reason = validator.enforce_before_action(
            "book_seat",
            {"flight_id": "QH118", "seat_number": "14A"},
            flight_data={"flight": "QH118", "depart": "15:40", "price": 1640000}
        )
        self.assertFalse(enforce_ok)
        self.assertIn("Harness chặn hành động", enforce_reason)

    def test_layer2_computational_verifier(self):
        """Lớp 2: Tiêu chí hoàn thành kiểm bằng code (Slide 43, 44)."""
        verifier = ComputationalVerifier(self.constraints, db=self.db)

        # Chưa book mã nào: Báo chưa đạt
        res_empty = verifier.verify("NON_EXIST")
        self.assertFalse(res_empty["achieved"])

        # Tạo booking nhưng chưa trả tiền (chỉ 'held')
        book_res = book_seat("VN122", "12A", db=self.db)
        code = book_res["booking_code"]

        res_held = verifier.verify(code)
        self.assertFalse(res_held["achieved"])
        self.assertIn("chưa phải 'confirmed'", res_held["reason"])

        # Trả tiền thành công -> Hoàn thành mục tiêu 100%
        pay(code, "corp_card", db=self.db)
        res_done = verifier.verify(code)
        self.assertTrue(res_done["achieved"])
        self.assertIn("thành công 100%", res_done["reason"])

    def test_layer3_permission_gatekeeper(self):
        """Lớp 3: Kiểm quyền trước khi gọi tool (Slide 35, 41)."""
        gatekeeper = PermissionGatekeeper(approval_threshold_price=1500000, allow_non_refundable=False)

        # Chuyến VN122: 1.850.000 VNĐ (> 1.500.000) và vé không hoàn tiền -> Cần phê duyệt
        decision = gatekeeper.inspect_tool_call(
            "book_seat",
            {"flight_id": "VN122", "seat_number": "12A"},
            flight_details={"flight": "VN122", "price": 1850000, "refundable": False}
        )
        self.assertFalse(decision.allowed)
        self.assertTrue(decision.requires_approval)
        self.assertIn("vượt hạn mức", decision.reason)
        self.assertIn("không hoàn tiền", decision.reason)

        # Chuyến giá rẻ và hoàn tiền được -> Cho phép ngay
        normal_decision = gatekeeper.inspect_tool_call(
            "book_seat",
            {"flight_id": "CHEAP1", "seat_number": "1A"},
            flight_details={"flight": "CHEAP1", "price": 1200000, "refundable": True}
        )
        self.assertTrue(normal_decision.allowed)
        self.assertFalse(normal_decision.requires_approval)

    def test_layer4_human_handoff_manager(self):
        """Lớp 4: Bàn giao cho con người chuẩn 30 giây (Slide 48)."""
        report = HumanHandoffManager.create_approval_handoff(
            flight_id="VN122",
            depart_time="08:10",
            price=1850000,
            refundable=False,
            seat="12A",
            reasons=["Vượt hạn mức 1.500.000đ", "Vé không hoàn tiền"]
        )
        self.assertIn("VN122", report.current_status)
        self.assertIn("08:10", report.current_status)
        self.assertTrue(len(report.tried_attempts) >= 2)
        self.assertIn("phê duyệt đặt ghế 12A", report.specific_question)

        view = report.format_30s_view()
        self.assertIn("30s HANDOFF", view)
        self.assertIn("[1. TRẠNG THÁI HIỆN TẠI]", view)
        self.assertIn("[4. CÂU HỎI QUYẾT ĐỊNH CỤ THỂ]", view)

    def test_loop_detector_slide_46(self):
        """Kiểm tra Bộ phát hiện lặp đúng thuật toán Slide 46."""
        detector = LoopDetector(window=6, repeat_k=2, stall_n=3)

        # Gọi lần 1
        res1 = detector.check("search_flights", {"date": "2026-10-07"}, progress=1)
        self.assertIsNone(res1)

        # Gọi lần 2 cùng action -> Báo "LOOP" vì repeat_k=2
        res2 = detector.check("search_flights", {"date": "2026-10-07"}, progress=1)
        self.assertEqual(res2, "LOOP")

        # Kiểm tra bế tắc STALL: đổi tool nhưng progress không đổi qua stall_n=2 lần không đổi
        detector.reset()
        detector.n = 2
        detector.check("tool_a", {"x": 1}, progress=10) # last=10, stall=0
        detector.check("tool_b", {"x": 2}, progress=10) # stall=1
        stall_res = detector.check("tool_c", {"x": 3}, progress=10) # stall=2 >= n -> STALL
        self.assertEqual(stall_res, "STALL")

    def test_grounding_sensor_anti_hallucination(self):
        """Sensor chống ảo giác: phát hiện bịa đặt số liệu/mã vé (Slide 57, 59)."""
        sensor = GroundingSensor()

        # Giả sử tool trả về chuyến VN122, ghế 12A, giá 1.850.000
        sensor.ingest_tool_observation(
            "check_seat",
            {"flight_id": "VN122"},
            {"status": "ok", "flight": "VN122", "price": 1850000, "available_seats": ["12A", "12B"]}
        )

        # Khẳng định đúng dữ liệu thực tế -> Grounded
        check_valid = sensor.check_claim(flight_id="VN122", seat="12A", price=1850000)
        self.assertTrue(check_valid["grounded"])

        # Agent bịa ra chuyến VN999, ghế 5C, giá 1.200.000 (Slide 58) -> Bị phát hiện vi phạm
        check_fake = sensor.check_claim(flight_id="VN999", seat="5C", price=1200000)
        self.assertFalse(check_fake["grounded"])
        self.assertTrue(len(check_fake["violations"]) >= 3)

    def test_execution_budget(self):
        """Kiểm tra ngân sách vòng lặp và bước (Slide 15, 38)."""
        budget = ExecutionBudget(max_steps=3, timeout_seconds=10.0)
        self.assertFalse(budget.is_exhausted()["exhausted"])

        budget.record_step(500)
        budget.record_step(500)
        self.assertFalse(budget.is_exhausted()["exhausted"])

        budget.record_step(500)
        exhausted_res = budget.is_exhausted()
        self.assertTrue(exhausted_res["exhausted"])
        self.assertEqual(exhausted_res["type"], "MAX_STEPS_EXCEEDED")


if __name__ == "__main__":
    unittest.main()
