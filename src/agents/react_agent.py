"""
Cài đặt Agent Mẫu 1: ReAct Flight Booking Agent.
Slide 10, 11, 18-21, 29 Buổi 03:
- Vòng lặp ReAct: Reasoning -> Acting -> Observation liên tục.
- Mỗi vòng nạp lại toàn bộ lịch sử hội thoại.
- Tích hợp lớp Harness 5 chặng: Dựng ngữ cảnh, Đề xuất tool, Kiểm quyền & Gọi tool, Ghi kết quả, Xét điều kiện dừng.
"""
import time
from typing import Dict, Any, Optional, List
from src.domain.models import FlightConstraints
from src.tools.flight_tools import (
    MockFlightDatabase,
    search_flights,
    check_seat,
    book_seat,
    pay,
    get_booking,
    get_default_database,
)
from src.harness.constraints import ConstraintValidator
from src.harness.verification import ComputationalVerifier
from src.harness.permission import PermissionGatekeeper
from src.harness.handoff import HumanHandoffManager, HandoffReport
from src.harness.detectors import LoopDetector, GroundingSensor
from src.harness.budget import ExecutionBudget
from src.agents.base import BaseFlightAgent, AgentStepTrace, AgentExecutionResult


class ReActFlightAgent(BaseFlightAgent):
    """
    Agent đặt vé máy bay theo mẫu ReAct (Reasoning + Acting + Observation).
    Bao bọc chặt chẽ bởi lớp Harness kỹ thuật hệ thống.
    """
    def __init__(
        self,
        constraints: FlightConstraints,
        db: Optional[MockFlightDatabase] = None,
        max_steps: int = 10,
        approval_threshold_price: int = 1500000,
        auto_approve_human_gate: bool = True
    ):
        super().__init__(constraints, agent_name="ReActFlightAgent")
        self.db = db or get_default_database()
        self.max_steps = max_steps
        self.auto_approve_human_gate = auto_approve_human_gate

        # Khởi tạo các thành phần Harness bảo vệ
        self.constraint_validator = ConstraintValidator(self.constraints)
        self.computational_verifier = ComputationalVerifier(self.constraints, db=self.db)
        self.permission_gatekeeper = PermissionGatekeeper(approval_threshold_price=approval_threshold_price)
        self.loop_detector = LoopDetector(window=6, repeat_k=2, stall_n=5)
        self.grounding_sensor = GroundingSensor()
        self.budget = ExecutionBudget(max_steps=max_steps)

    def execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Thực thi tool an toàn trên môi trường Mock Database."""
        if tool_name == "search_flights":
            return search_flights(
                origin=args.get("origin", ""),
                destination=args.get("destination", ""),
                date=args.get("date", ""),
                db=self.db
            )
        elif tool_name == "check_seat":
            return check_seat(flight_id=args.get("flight_id", ""), db=self.db)
        elif tool_name == "book_seat":
            return book_seat(flight_id=args.get("flight_id", ""), seat_number=args.get("seat_number", ""), db=self.db)
        elif tool_name == "pay":
            return pay(booking_code=args.get("booking_code", ""), payment_method=args.get("payment_method", "corp_card"), db=self.db)
        elif tool_name == "get_booking":
            return get_booking(booking_code=args.get("booking_code", ""), db=self.db)
        else:
            return {
                "status": "error",
                "error": "unknown_tool",
                "hint": f"Công cụ '{tool_name}' không tồn tại trong danh mục cho phép (Slide 60)."
            }

    def _decide_react_step(self, step_idx: int, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Khối suy luận ReAct (Model Decision Logic).
        Phân tích ngữ cảnh tích luỹ để quyết định Thought và Action tiếp theo.
        Slide 21: Agent quay vòng cho tới khi xong, mỗi vòng gửi lại toàn bộ lịch sử.
        """
        # Nếu chưa tìm kiếm chuyến bay
        has_searched = any(h["tool"] == "search_flights" and h["result"].get("status") == "ok" for h in history)
        if not has_searched:
            return {
                "thought": (
                    f"Người dùng muốn đặt vé từ {self.constraints.origin} đến {self.constraints.destination} "
                    f"vào ngày {self.constraints.date}, trước {self.constraints.depart_before}, ngân sách <= {self.constraints.max_price:,} VNĐ. "
                    f"Tôi cần tìm danh sách các chuyến bay phù hợp bằng search_flights."
                ),
                "action": "search_flights",
                "args": {
                    "origin": self.constraints.origin,
                    "destination": self.constraints.destination,
                    "date": self.constraints.date
                }
            }

        # Đã search, tìm chuyến bay hợp lệ
        search_obs = next(h["result"] for h in history if h["tool"] == "search_flights" and h["result"].get("status") == "ok")
        available_flights = search_obs.get("flights", [])

        # Lọc các chuyến thoả mãn giờ bay sáng và giá vé
        valid_flights = [
            f for f in available_flights
            if f.get("depart") < self.constraints.depart_before and f.get("price") <= self.constraints.max_price
        ]

        if not valid_flights:
            return {
                "thought": "Sau khi quan sát kết quả tìm kiếm, không có chuyến bay nào thoả mãn cả khung giờ sáng và ngân sách. Tôi cần thông báo bế tắc.",
                "action": None,
                "args": None,
                "conclude_failed": True
            }

        target_flight = valid_flights[0]
        target_flight_id = target_flight["flight"]

        # Kiểm tra xem đã check seat chuyến này chưa
        has_checked_seat = any(
            h["tool"] == "check_seat" and h["args"].get("flight_id") == target_flight_id for h in history
        )
        if not has_checked_seat:
            return {
                "thought": (
                    f"Chuyến bay {target_flight_id} lúc {target_flight['depart']} có giá {target_flight['price']:,} VNĐ thoả mãn yêu cầu. "
                    f"Tôi cần kiểm tra danh sách ghế trống bằng check_seat."
                ),
                "action": "check_seat",
                "args": {"flight_id": target_flight_id}
            }

        # Đã check seat, chọn ghế để book
        seat_obs = next(h["result"] for h in history if h["tool"] == "check_seat" and h["args"].get("flight_id") == target_flight_id)
        available_seats = seat_obs.get("available_seats", [])

        has_booked = any(h["tool"] == "book_seat" and h["result"].get("status") == "held" for h in history)
        if not has_booked:
            if not available_seats:
                return {
                    "thought": f"Chuyến {target_flight_id} đã hết sạch ghế trống.",
                    "action": None,
                    "args": None,
                    "conclude_failed": True
                }
            chosen_seat = available_seats[0]
            return {
                "thought": f"Ghế {chosen_seat} trên chuyến {target_flight_id} còn trống. Tôi chọn đặt ghế này.",
                "action": "book_seat",
                "args": {"flight_id": target_flight_id, "seat_number": chosen_seat}
            }

        # Đã book, lấy mã booking_code để thanh toán
        book_obs = next(h["result"] for h in history if h["tool"] == "book_seat" and h["result"].get("status") == "held")
        booking_code = book_obs["booking_code"]

        has_paid = any(h["tool"] == "pay" and h["result"].get("status") == "paid" for h in history)
        if not has_paid:
            return {
                "thought": f"Đã giữ chỗ thành công với mã {booking_code}. Bây giờ tôi tiến hành thanh toán qua thẻ corp_card.",
                "action": "pay",
                "args": {"booking_code": booking_code, "payment_method": "corp_card"}
            }

        # Đã pay, kết thúc
        return {
            "thought": f"Vé đã được thanh toán hoàn tất cho mã {booking_code}. Tôi hoàn thành tác vụ.",
            "action": None,
            "args": None,
            "conclude_success": True,
            "booking_code": booking_code
        }

    def run(self, user_goal: str) -> AgentExecutionResult:
        """
        Chạy vòng lặp ReAct hoàn chỉnh có giám sát bởi 4 lớp Harness (Slide 10, 35).
        """
        start_time = time.time()
        traces: List[AgentStepTrace] = []
        history: List[Dict[str, Any]] = []
        progress_metric = 0 # Đại lượng tiến triển (Slide 45, 46)

        self.budget.reset()
        self.loop_detector.reset()

        active_booking_code = None

        while True:
            step_idx = self.budget.current_steps + 1
            # Ước tính token nạp lại toàn bộ lịch sử (Slide 14: 3000 token nền + 500 token/vòng)
            tokens_this_step = 3000 + (step_idx - 1) * 500
            self.budget.record_step(tokens_used=tokens_this_step)

            # -------------------------------------------------------------
            # BƯỚC 01 & 02: DỰNG NGỮ CẢNH & MODEL ĐỀ XUẤT TOOL (SLIDE 10)
            # -------------------------------------------------------------
            decision = self._decide_react_step(step_idx, history)
            thought = decision.get("thought", "")
            action_tool = decision.get("action")
            action_args = decision.get("args") or {}

            # Nếu model không gọi tool nữa (Model tự tuyên bố xong hoặc bế tắc)
            if not action_tool:
                if decision.get("conclude_success") and active_booking_code:
                    # Chạy sensor computational độc lập xác nhận (Slide 43)
                    verify_res = self.computational_verifier.verify(active_booking_code)
                    if verify_res["achieved"]:
                        traces.append(AgentStepTrace(
                            step_index=step_idx,
                            thought=thought,
                            tokens_estimate=tokens_this_step,
                            harness_event="Sensor Computational: Xác nhận mục tiêu thành công 100% bằng code (Exit 0)."
                        ))
                        return AgentExecutionResult(
                            agent_type="ReAct",
                            success=True,
                            finish_reason="GOAL_ACHIEVED",
                            final_message=f"Đặt vé thành công! Mã PNR: {active_booking_code}.",
                            booking_code=active_booking_code,
                            total_steps=step_idx,
                            total_tokens=self.budget.current_tokens,
                            duration_seconds=time.time() - start_time,
                            trace=traces
                        )
                # Bế tắc không thể đi tiếp
                traces.append(AgentStepTrace(
                    step_index=step_idx,
                    thought=thought,
                    tokens_estimate=tokens_this_step,
                    harness_event="Bế tắc: Model không tìm ra bước hành động hợp lệ."
                ))
                handoff = HumanHandoffManager.create_failure_handoff(
                    reason="Không tìm thấy chuyến bay thoả mãn ràng buộc",
                    attempts=[f"Đã duyệt lịch sử tìm kiếm nhưng các chuyến đều vượt giờ hoặc ngân sách."],
                    question="Bạn có muốn nới lỏng ngân sách hoặc chọn chuyến bay chiều không?"
                )
                return AgentExecutionResult(
                    agent_type="ReAct",
                    success=False,
                    finish_reason="STALL_DETECTED",
                    final_message="Không tìm thấy chuyến bay phù hợp ràng buộc.",
                    total_steps=step_idx,
                    total_tokens=self.budget.current_tokens,
                    duration_seconds=time.time() - start_time,
                    trace=traces,
                    handoff_report=handoff
                )

            # -------------------------------------------------------------
            # BƯỚC 03: HARNESS KIỂM QUYỀN TRƯỚC KHI GỌI TOOL (#0 TRONG CHECKLIST - SLIDE 35, 41)
            # -------------------------------------------------------------
            flight_ctx = None
            if action_tool == "book_seat":
                fl_id = action_args.get("flight_id")
                fl_obj = self.db.flights.get(fl_id)
                if fl_obj:
                    flight_ctx = {
                        "flight": fl_obj.flight_id,
                        "price": fl_obj.price,
                        "refundable": fl_obj.refundable,
                        "depart": fl_obj.depart_time,
                        "depart_date": fl_obj.depart_date
                    }

            # Lớp 1: Kiểm tra vi phạm ràng buộc dữ liệu (Slide 63)
            if flight_ctx:
                ok_constraint, reason_c = self.constraint_validator.enforce_before_action(action_tool, action_args, flight_ctx)
                if not ok_constraint:
                    traces.append(AgentStepTrace(
                        step_index=step_idx,
                        thought=thought,
                        action_tool=action_tool,
                        action_args=action_args,
                        harness_event=f"VI PHẠM RÀNG BUỘC CỨNG: {reason_c}"
                    ))
                    # Đưa cảnh báo về làm observation để agent đổi hướng (Slide 63)
                    history.append({"tool": action_tool, "args": action_args, "result": {"status": "denied", "reason": reason_c}})
                    continue

            # Lớp 3: Kiểm tra quyền hạn và yêu cầu duyệt con người (Slide 41)
            perm_decision = self.permission_gatekeeper.inspect_tool_call(action_tool, action_args, flight_ctx)
            if perm_decision.requires_approval and not self.auto_approve_human_gate:
                handoff = HumanHandoffManager.create_approval_handoff(
                    flight_id=perm_decision.flight_id,
                    depart_time=flight_ctx.get("depart", ""),
                    price=perm_decision.price,
                    refundable=perm_decision.refundable,
                    seat=perm_decision.seat_number,
                    reasons=[perm_decision.reason]
                )
                traces.append(AgentStepTrace(
                    step_index=step_idx,
                    thought=thought,
                    action_tool=action_tool,
                    action_args=action_args,
                    harness_event=f"CẦN PHÊ DUYỆT CON NGƯỜI (Slide 41): {perm_decision.reason}",
                    tokens_estimate=tokens_this_step
                ))
                return AgentExecutionResult(
                    agent_type="ReAct",
                    success=False,
                    finish_reason="NEED_HUMAN_APPROVAL",
                    final_message=f"Tạm dừng chờ phê duyệt con người do: {perm_decision.reason}",
                    total_steps=step_idx,
                    total_tokens=self.budget.current_tokens,
                    duration_seconds=time.time() - start_time,
                    trace=traces,
                    handoff_report=handoff
                )

            # Thực thi tool
            obs = self.execute_tool(action_tool, action_args)
            if action_tool == "book_seat" and obs.get("status") == "held":
                active_booking_code = obs.get("booking_code")
                progress_metric = 2 # Đã giữ chỗ thành công
            elif action_tool == "pay" and obs.get("status") == "paid":
                progress_metric = 3 # Đã thanh toán thành công
            elif action_tool == "search_flights" and obs.get("status") == "ok":
                progress_metric = 1 # Đã tìm thấy chuyến

            # -------------------------------------------------------------
            # BƯỚC 04: GHI KẾT QUẢ VÀ SENSOR CHỐNG ẢO GIÁC (SLIDE 10, 59)
            # -------------------------------------------------------------
            self.grounding_sensor.ingest_tool_observation(action_tool, action_args, obs)
            history.append({"tool": action_tool, "args": action_args, "result": obs})

            step_trace = AgentStepTrace(
                step_index=step_idx,
                thought=thought,
                action_tool=action_tool,
                action_args=action_args,
                observation=obs,
                tokens_estimate=tokens_this_step
            )
            traces.append(step_trace)

            # -------------------------------------------------------------
            # BƯỚC 05: XÉT ĐIỀU KIỆN DỪNG THEO CHECKLIST (SLIDE 35)
            # #1: Tiêu chí hoàn thành (bằng code)
            # #2: Phát hiện lặp (LoopDetector)
            # #3: Bế tắc
            # #4: Hết ngân sách (kiểm cuối cùng)
            # -------------------------------------------------------------
            # #2 & #3: Kiểm tra LoopDetector (Slide 46)
            loop_signal = self.loop_detector.check(action_tool, action_args, progress=progress_metric)
            if loop_signal == "LOOP":
                step_trace.harness_event = "PHÁT HIỆN LẶP (LOOP DETECTED - Slide 45, 46)"
                handoff = HumanHandoffManager.create_failure_handoff(
                    reason="Phát hiện hành động gọi tool lặp lại vô ích",
                    attempts=[f"Agent liên tục gọi {action_tool} với cùng tham số."],
                    question="Hệ thống có sự cố phản hồi hoặc lỗi dịch vụ, bạn có muốn thử lại sau không?"
                )
                return AgentExecutionResult(
                    agent_type="ReAct",
                    success=False,
                    finish_reason="LOOP_DETECTED",
                    final_message="Dừng khẩn cấp do phát hiện vòng lặp vô hạn.",
                    total_steps=step_idx,
                    total_tokens=self.budget.current_tokens,
                    duration_seconds=time.time() - start_time,
                    trace=traces,
                    handoff_report=handoff
                )
            elif loop_signal == "STALL":
                step_trace.harness_event = "PHÁT HIỆN BẾ TẮC (STALL DETECTED - Slide 45, 46)"
                handoff = HumanHandoffManager.create_failure_handoff(
                    reason="Phát hiện bế tắc: Tiến độ không thay đổi qua nhiều vòng",
                    attempts=[f"Đã thử đổi nhiều công cụ nhưng không tiến triển thêm."],
                    question="Bạn có muốn huỷ tác vụ hay chỉ định phương án cụ thể?"
                )
                return AgentExecutionResult(
                    agent_type="ReAct",
                    success=False,
                    finish_reason="STALL_DETECTED",
                    final_message="Dừng do bài toán bế tắc không tiến triển.",
                    total_steps=step_idx,
                    total_tokens=self.budget.current_tokens,
                    duration_seconds=time.time() - start_time,
                    trace=traces,
                    handoff_report=handoff
                )

            # #4: Hết ngân sách (Slide 38)
            budget_res = self.budget.is_exhausted()
            if budget_res["exhausted"]:
                step_trace.harness_event = f"HẾT NGÂN SÁCH (Slide 38): {budget_res['reason']}"
                handoff = HumanHandoffManager.create_failure_handoff(
                    reason=budget_res["reason"],
                    attempts=[f"Đã thực hiện hết giới hạn trần cứng {self.max_steps} vòng."],
                    question="Có cho phép tăng ngân sách để tiếp tục thực hiện không?"
                )
                return AgentExecutionResult(
                    agent_type="ReAct",
                    success=False,
                    finish_reason="BUDGET_EXHAUSTED",
                    final_message=f"Agent chạm trần ngân sách: {budget_res['reason']}",
                    total_steps=step_idx,
                    total_tokens=self.budget.current_tokens,
                    duration_seconds=time.time() - start_time,
                    trace=traces,
                    handoff_report=handoff
                )
