"""
Cài đặt Agent Mẫu 3: Mẫu Lai "ReAct + Plan" (Hybrid Dynamic Replanning Agent).
Slide 24, 26 Buổi 03:
- Sơ đồ trục mẫu lai: Lập kế hoạch -> Thực thi k bước -> Observation đổi đáng kể? -> Lập lại kế hoạch (Replanning).
- Tích hợp tư tưởng TodoListMiddleware (LangChain 1.x) quản lý danh sách công việc động.
- Cân bằng giữa khả năng định hướng dài hạn (Plan) và khả năng ứng biến linh hoạt (ReAct).
"""
import time
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
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


class TodoItem(BaseModel):
    """Một mục công việc trong Todo List của Mẫu Lai (Slide 24)."""
    id: int = Field(description="Mã thứ tự công việc")
    title: str = Field(description="Mô tả công việc cần làm")
    tool: str = Field(description="Công cụ phụ trách")
    args: Dict[str, Any] = Field(default_factory=dict, description="Tham số công cụ")
    status: str = Field(default="pending", description="'pending', 'in_progress', 'completed', 'failed'")
    observation: Optional[Dict[str, Any]] = Field(default=None)


class HybridFlightAgent(BaseFlightAgent):
    """
    Agent mẫu lai ReAct + Plan với cơ chế Re-planning khi có biến động môi trường.
    """
    def __init__(
        self,
        constraints: FlightConstraints,
        db: Optional[MockFlightDatabase] = None,
        max_steps: int = 12,
        approval_threshold_price: int = 1500000,
        auto_approve_human_gate: bool = True
    ):
        super().__init__(constraints, agent_name="HybridFlightAgent")
        self.db = db or get_default_database()
        self.max_steps = max_steps
        self.auto_approve_human_gate = auto_approve_human_gate

        self.constraint_validator = ConstraintValidator(self.constraints)
        self.computational_verifier = ComputationalVerifier(self.constraints, db=self.db)
        self.permission_gatekeeper = PermissionGatekeeper(approval_threshold_price=approval_threshold_price)
        self.loop_detector = LoopDetector(window=6, repeat_k=2, stall_n=5)
        self.grounding_sensor = GroundingSensor()
        self.budget = ExecutionBudget(max_steps=max_steps)

        self.todos: List[TodoItem] = []
        self.replan_count = 0

    def init_initial_todos(self):
        """Khởi tạo danh sách Todo List ban đầu (Slide 24)."""
        self.todos = [
            TodoItem(
                id=1,
                title=f"Tìm kiếm chuyến bay {self.constraints.origin} -> {self.constraints.destination} ngày {self.constraints.date}",
                tool="search_flights",
                args={"origin": self.constraints.origin, "destination": self.constraints.destination, "date": self.constraints.date}
            ),
            TodoItem(
                id=2,
                title="Kiểm tra tình trạng ghế của chuyến bay tối ưu nhất",
                tool="check_seat",
                args={"flight_id": "$target_flight"}
            ),
            TodoItem(
                id=3,
                title="Giữ chỗ ghế trống phù hợp",
                tool="book_seat",
                args={"flight_id": "$target_flight", "seat_number": "$target_seat"}
            ),
            TodoItem(
                id=4,
                title="Thanh toán đơn hàng qua thẻ doanh nghiệp corp_card",
                tool="pay",
                args={"booking_code": "$booking_code", "payment_method": "corp_card"}
            ),
            TodoItem(
                id=5,
                title="Xác thực hoàn tất tác vụ bằng tiêu chí kiểm chứng",
                tool="get_booking",
                args={"booking_code": "$booking_code"}
            )
        ]

    def execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Thực thi tool trên Mock Flight Database."""
        if tool_name == "search_flights":
            return search_flights(origin=args.get("origin", ""), destination=args.get("destination", ""), date=args.get("date", ""), db=self.db)
        elif tool_name == "check_seat":
            return check_seat(flight_id=args.get("flight_id", ""), db=self.db)
        elif tool_name == "book_seat":
            return book_seat(flight_id=args.get("flight_id", ""), seat_number=args.get("seat_number", ""), db=self.db)
        elif tool_name == "pay":
            return pay(booking_code=args.get("booking_code", ""), payment_method=args.get("payment_method", "corp_card"), db=self.db)
        elif tool_name == "get_booking":
            return get_booking(booking_code=args.get("booking_code", ""), db=self.db)
        return {"status": "error", "error": "unknown_tool"}

    def is_observation_drifted(self, step: TodoItem, obs: Dict[str, Any]) -> bool:
        """
        Kiểm tra 'Observation đổi đáng kể?' (Sơ đồ trục Slide 24).
        Ví dụ:
        - Chuyến bay dự kiến đã hết ghế trống (available_seats == []).
        - Tool trả về lỗi hệ thống hoặc không có chuyến bay.
        - Giá vé hoặc thông tin bay không như kỳ vọng.
        """
        if obs.get("status") in ["error", "invalid_param", "denied"]:
            return True

        if step.tool == "check_seat":
            seats = obs.get("available_seats", [])
            if not seats:
                # Chuyến bay đã hết chỗ -> Môi trường biến động, cần replan ngay
                return True

        if step.tool == "search_flights":
            flights = obs.get("flights", [])
            valid_flights = [f for f in flights if f.get("depart") < self.constraints.depart_before and f.get("price") <= self.constraints.max_price]
            if not valid_flights:
                return True

        return False

    def replan_on_drift(self, failed_step: TodoItem, obs: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """
        Cơ chế Lập lại kế hoạch (Replanning - Slide 24).
        Tự động tìm kiếm giải pháp thay thế dựa trên quan sát mới mà không làm hỏng toàn bộ luồng.
        """
        self.replan_count += 1
        failed_step.status = "failed"
        failed_step.observation = obs

        # Tình huống: Chuyến bay vừa kiểm tra đã hết ghế
        if failed_step.tool == "check_seat":
            all_flights = context.get("all_search_flights", [])
            tried_flights = context.get("tried_flights", set())
            tried_flights.add(failed_step.args.get("flight_id"))
            context["tried_flights"] = tried_flights

            # Tìm chuyến bay khả dĩ tiếp theo
            next_alternatives = [
                f for f in all_flights
                if f["flight"] not in tried_flights
                and f["depart"] < self.constraints.depart_before
                and f["price"] <= self.constraints.max_price
            ]

            if next_alternatives:
                alt_flight = next_alternatives[0]["flight"]
                context["target_flight"] = alt_flight
                # Cập nhật lại các bước sau trong Todo List (Slide 24)
                self.todos = [
                    TodoItem(
                        id=10 + self.replan_count * 2,
                        title=f"[REPLAN] Kiểm tra ghế chuyến bay thay thế {alt_flight}",
                        tool="check_seat",
                        args={"flight_id": alt_flight}
                    ),
                    TodoItem(
                        id=11 + self.replan_count * 2,
                        title=f"[REPLAN] Đặt giữ chỗ trên chuyến thay thế {alt_flight}",
                        tool="book_seat",
                        args={"flight_id": alt_flight, "seat_number": "$target_seat"}
                    ),
                    TodoItem(
                        id=12 + self.replan_count * 2,
                        title="[REPLAN] Thanh toán đơn hàng thay thế",
                        tool="pay",
                        args={"booking_code": "$booking_code", "payment_method": "corp_card"}
                    )
                ]
                return True

        return False

    def run(self, user_goal: str) -> AgentExecutionResult:
        """
        Chạy vòng lặp Mẫu Lai ReAct + Plan có kiểm soát và Re-planning (Slide 24).
        """
        start_time = time.time()
        traces: List[AgentStepTrace] = []
        self.budget.reset()
        self.init_initial_todos()

        context_vars = {"tried_flights": set()}
        active_booking_code = None

        while self.todos:
            # Lấy công việc tiếp theo trong danh sách todo
            current_todo = self.todos.pop(0)
            step_idx = self.budget.current_steps + 1
            # Chi phí token của mẫu lai ở mức vừa phải (Slide 23, 26)
            tokens_step = 1200 + (self.replan_count * 500)
            self.budget.record_step(tokens_used=tokens_step)

            # Phân giải tham số động
            actual_args = {}
            for k, v in current_todo.args.items():
                if isinstance(v, str) and v.startswith("$"):
                    var_name = v[1:]
                    actual_args[k] = context_vars.get(var_name)
                else:
                    actual_args[k] = v

            current_todo.status = "in_progress"
            step_trace = AgentStepTrace(
                step_index=step_idx,
                thought=f"[Todo #{current_todo.id}] {current_todo.title}",
                action_tool=current_todo.tool,
                action_args=actual_args,
                tokens_estimate=tokens_step
            )

            # Kiểm quyền trước khi gọi tool (#0 trong checklist - Slide 35, 41)
            flight_ctx = None
            if current_todo.tool == "book_seat":
                fl_id = actual_args.get("flight_id")
                fl_obj = self.db.flights.get(fl_id)
                if fl_obj:
                    flight_ctx = {
                        "flight": fl_obj.flight_id,
                        "price": fl_obj.price,
                        "refundable": fl_obj.refundable,
                        "depart": fl_obj.depart_time,
                        "depart_date": fl_obj.depart_date
                    }
                    # Kiểm tra ràng buộc là dữ liệu (Slide 63)
                    ok_c, reason_c = self.constraint_validator.enforce_before_action(current_todo.tool, actual_args, flight_ctx)
                    if not ok_c:
                        step_trace.harness_event = f"Harness chặn vi phạm ràng buộc: {reason_c}"
                        traces.append(step_trace)
                        # Kích hoạt replan do vi phạm ràng buộc
                        if not self.replan_on_drift(current_todo, {"status": "denied", "error": reason_c}, context_vars):
                            handoff = HumanHandoffManager.create_failure_handoff(
                                reason=reason_c,
                                attempts=["Chuyến bay vi phạm tiêu chuẩn ràng buộc ban đầu."],
                                question="Bạn có muốn điều chỉnh yêu cầu không?"
                            )
                            return AgentExecutionResult(
                                agent_type="Hybrid",
                                success=False,
                                finish_reason="CONSTRAINT_VIOLATION",
                                final_message=f"Dừng do vi phạm ràng buộc: {reason_c}",
                                total_steps=step_idx,
                                total_tokens=self.budget.current_tokens,
                                duration_seconds=time.time() - start_time,
                                trace=traces,
                                handoff_report=handoff
                            )
                        continue

                    # Kiểm quyền (Slide 41)
                    perm = self.permission_gatekeeper.inspect_tool_call(current_todo.tool, actual_args, flight_ctx)
                    if perm.requires_approval and not self.auto_approve_human_gate:
                        handoff = HumanHandoffManager.create_approval_handoff(
                            flight_id=perm.flight_id,
                            depart_time=flight_ctx.get("depart", ""),
                            price=perm.price,
                            refundable=perm.refundable,
                            seat=perm.seat_number,
                            reasons=[perm.reason]
                        )
                        step_trace.harness_event = f"CẦN PHÊ DUYỆT CON NGƯỜI: {perm.reason}"
                        traces.append(step_trace)
                        return AgentExecutionResult(
                            agent_type="Hybrid",
                            success=False,
                            finish_reason="NEED_HUMAN_APPROVAL",
                            final_message=f"Tạm dừng chờ phê duyệt con người: {perm.reason}",
                            total_steps=step_idx,
                            total_tokens=self.budget.current_tokens,
                            duration_seconds=time.time() - start_time,
                            trace=traces,
                            handoff_report=handoff
                        )

            # Thực thi tool
            obs = self.execute_tool(current_todo.tool, actual_args)
            step_trace.observation = obs
            current_todo.observation = obs

            # Sensor chống ảo giác ghi nhận
            self.grounding_sensor.ingest_tool_observation(current_todo.tool, actual_args, obs)

            # Đánh giá: Observation đổi đáng kể? (Slide 24)
            if self.is_observation_drifted(current_todo, obs):
                step_trace.harness_event = f"QUAN SÁT ĐỔI ĐÁNG KỂ (Observation Drift): Kích hoạt Replanning lần {self.replan_count + 1}."
                traces.append(step_trace)

                can_replan = self.replan_on_drift(current_todo, obs, context_vars)
                if can_replan:
                    continue
                else:
                    # Bế tắc không thể lập lại kế hoạch
                    handoff = HumanHandoffManager.create_failure_handoff(
                        reason="Bế tắc sau khi lập lại kế hoạch không còn giải pháp thay thế",
                        attempts=[f"Đã thử các phương án nhưng môi trường không đáp ứng ràng buộc."],
                        question="Bạn có muốn huỷ lệnh hay nới lỏng ngân sách?"
                    )
                    return AgentExecutionResult(
                        agent_type="Hybrid",
                        success=False,
                        finish_reason="STALL_DETECTED",
                        final_message="Mẫu Lai dừng do không thể tái lập kế hoạch khả thi.",
                        total_steps=step_idx,
                        total_tokens=self.budget.current_tokens,
                        duration_seconds=time.time() - start_time,
                        trace=traces,
                        handoff_report=handoff
                    )

            # Cập nhật context vars
            if current_todo.tool == "search_flights":
                flights = obs.get("flights", [])
                context_vars["all_search_flights"] = flights
                valid_flights = [f for f in flights if f.get("depart") < self.constraints.depart_before and f.get("price") <= self.constraints.max_price]
                context_vars["target_flight"] = valid_flights[0]["flight"]

            elif current_todo.tool == "check_seat":
                seats = obs.get("available_seats", [])
                context_vars["target_seat"] = seats[0]

            elif current_todo.tool == "book_seat":
                active_booking_code = obs.get("booking_code")
                context_vars["booking_code"] = active_booking_code

            current_todo.status = "completed"
            traces.append(step_trace)

            # Kiểm tra ngân sách cứng
            budget_res = self.budget.is_exhausted()
            if budget_res["exhausted"]:
                return AgentExecutionResult(
                    agent_type="Hybrid",
                    success=False,
                    finish_reason="BUDGET_EXHAUSTED",
                    final_message=f"Chạm trần ngân sách: {budget_res['reason']}",
                    total_steps=step_idx,
                    total_tokens=self.budget.current_tokens,
                    duration_seconds=time.time() - start_time,
                    trace=traces
                )

        # Kiểm chứng hoàn thành bằng code (Slide 43)
        if active_booking_code:
            verify_res = self.computational_verifier.verify(active_booking_code)
            if verify_res["achieved"]:
                return AgentExecutionResult(
                    agent_type="Hybrid",
                    success=True,
                    finish_reason="GOAL_ACHIEVED",
                    final_message=f"Mẫu Lai hoàn thành xuất sắc! Mã PNR: {active_booking_code}.",
                    booking_code=active_booking_code,
                    total_steps=self.budget.current_steps,
                    total_tokens=self.budget.current_tokens,
                    duration_seconds=time.time() - start_time,
                    trace=traces
                )

        return AgentExecutionResult(
            agent_type="Hybrid",
            success=False,
            finish_reason="GOAL_NOT_VERIFIED",
            final_message="Tác vụ kết thúc nhưng không đạt kiểm chứng hoàn thành.",
            total_steps=self.budget.current_steps,
            total_tokens=self.budget.current_tokens,
            duration_seconds=time.time() - start_time,
            trace=traces
        )
