"""
Cài đặt Agent Mẫu 2: Plan-then-Execute Flight Booking Agent.
Slide 22, 23, 26, 31 Buổi 03:
- Gọi model lập trọn kế hoạch tổng thể (Execution Plan).
- Duyệt kế hoạch (Plan Review) trước khi chạy để ước lượng chi phí và kiểm soát an toàn.
- Thực thi từng bước theo kế hoạch đã chốt.
- Thể hiện rõ đặc tính: Tiết kiệm token, duyệt được trước, nhưng giòn (brittle) khi gặp tình huống bất ngờ.
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
from src.harness.budget import ExecutionBudget
from src.agents.base import BaseFlightAgent, AgentStepTrace, AgentExecutionResult


class PlanStep(BaseModel):
    """Một bước cụ thể trong kế hoạch tổng thể (Slide 22)."""
    step_id: int = Field(description="Số thứ tự bước")
    description: str = Field(description="Mô tả mục tiêu của bước")
    tool_name: str = Field(description="Tên công cụ dự kiến gọi")
    args_template: Dict[str, Any] = Field(description="Tham số cấu hình hoặc tham chiếu")
    status: str = Field(default="PENDING", description="PENDING, COMPLETED, FAILED, SKIPPED")
    result: Optional[Dict[str, Any]] = Field(default=None)


class ExecutionPlan(BaseModel):
    """Bản kế hoạch hoàn chỉnh được sinh trước khi chạy (Slide 22)."""
    goal: str = Field(description="Mục tiêu bài toán")
    steps: List[PlanStep] = Field(description="Danh sách các bước tuần tự")
    estimated_tokens: int = Field(default=3500, description="Ước lượng token toàn bộ kế hoạch")
    approved: bool = Field(default=False, description="Kế hoạch đã được người duyệt chấp thuận hay chưa")
    review_notes: Optional[str] = Field(default=None, description="Ghi chú từ người duyệt")


class PlanThenExecuteFlightAgent(BaseFlightAgent):
    """
    Agent đặt vé máy bay theo kiến trúc Plan-then-Execute.
    """
    def __init__(
        self,
        constraints: FlightConstraints,
        db: Optional[MockFlightDatabase] = None,
        max_steps: int = 10,
        approval_threshold_price: int = 1500000,
        auto_approve_plan: bool = True
    ):
        super().__init__(constraints, agent_name="PlanThenExecuteFlightAgent")
        self.db = db or get_default_database()
        self.max_steps = max_steps
        self.auto_approve_plan = auto_approve_plan

        self.constraint_validator = ConstraintValidator(self.constraints)
        self.computational_verifier = ComputationalVerifier(self.constraints, db=self.db)
        self.permission_gatekeeper = PermissionGatekeeper(approval_threshold_price=approval_threshold_price)
        self.budget = ExecutionBudget(max_steps=max_steps)

    def generate_plan(self, user_goal: str) -> ExecutionPlan:
        """
        Bước 1: Model sinh trọn kế hoạch ban đầu (Slide 22).
        Ưu điểm: Nhìn thấy toàn bộ hành động trước khi tốn tài nguyên gọi tool.
        """
        steps = [
            PlanStep(
                step_id=1,
                description=f"Tìm kiếm chuyến bay từ {self.constraints.origin} đến {self.constraints.destination} ngày {self.constraints.date}",
                tool_name="search_flights",
                args_template={
                    "origin": self.constraints.origin,
                    "destination": self.constraints.destination,
                    "date": self.constraints.date
                }
            ),
            PlanStep(
                step_id=2,
                description="Chọn chuyến bay sáng phù hợp ràng buộc (< 12:00, <= 2.000.000đ) và kiểm tra danh sách ghế trống",
                tool_name="check_seat",
                args_template={"flight_id": "$best_flight"}
            ),
            PlanStep(
                step_id=3,
                description="Đặt giữ chỗ ghế đầu tiên còn khả dụng trên chuyến bay đã chọn",
                tool_name="book_seat",
                args_template={"flight_id": "$best_flight", "seat_number": "$first_seat"}
            ),
            PlanStep(
                step_id=4,
                description="Thanh toán vé bằng thẻ doanh nghiệp corp_card",
                tool_name="pay",
                args_template={"booking_code": "$booking_code", "payment_method": "corp_card"}
            ),
            PlanStep(
                step_id=5,
                description="Truy vấn thông tin đơn vé và kích hoạt kiểm chứng hoàn thành mục tiêu",
                tool_name="get_booking",
                args_template={"booking_code": "$booking_code"}
            )
        ]
        return ExecutionPlan(
            goal=user_goal,
            steps=steps,
            estimated_tokens=3500,
            approved=False
        )

    def review_plan(self, plan: ExecutionPlan) -> bool:
        """
        Bước 2: Người duyệt thẩm định kế hoạch (Slide 22).
        Kiểm tra tính an toàn, số bước, ngân sách dự kiến trước khi bấm 'Đồng ý'.
        """
        if not self.auto_approve_plan:
            plan.approved = False
            plan.review_notes = "Kế hoạch tạm dừng chờ người duyệt bấm xác nhận."
            return False

        # Thẩm định tự động các bước
        required_tools = {"search_flights", "check_seat", "book_seat", "pay"}
        planned_tools = {st.tool_name for st in plan.steps}
        if not required_tools.issubset(planned_tools):
            plan.approved = False
            plan.review_notes = "Từ chối kế hoạch: Thiếu các bước tối thiểu để hoàn thành giao dịch vé."
            return False

        plan.approved = True
        plan.review_notes = "Kế hoạch đã được phê duyệt hợp lệ. Cho phép tiến hành thực thi."
        return True

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

    def run(self, user_goal: str) -> AgentExecutionResult:
        """
        Quy trình chạy Plan-then-Execute: Lập kế hoạch -> Duyệt -> Thực thi từng bước.
        """
        start_time = time.time()
        traces: List[AgentStepTrace] = []
        self.budget.reset()

        # 1. Sinh kế hoạch (Slide 22)
        plan = self.generate_plan(user_goal)
        traces.append(AgentStepTrace(
            step_index=1,
            thought=f"Lập toàn bộ kế hoạch thực thi gồm {len(plan.steps)} bước (Plan-then-Execute).",
            tokens_estimate=1200,
            harness_event="Planner: Đã tạo bản kế hoạch chi tiết."
        ))

        # 2. Duyệt kế hoạch (Người duyệt / Plan Reviewer - Slide 22)
        approved = self.review_plan(plan)
        if not approved:
            handoff = HumanHandoffManager.create_failure_handoff(
                reason="Kế hoạch chưa được phê duyệt trước khi chạy",
                attempts=["Bản kế hoạch 5 bước đã sẵn sàng nhưng cần con người kiểm tra."],
                question="Bạn có đồng ý phê duyệt cho chạy kế hoạch đặt vé này không? [YES/NO]"
            )
            return AgentExecutionResult(
                agent_type="Plan-then-Execute",
                success=False,
                finish_reason="NEED_HUMAN_APPROVAL",
                final_message="Kế hoạch đang chờ con người phê duyệt trước khi thực thi.",
                total_steps=1,
                total_tokens=1200,
                duration_seconds=time.time() - start_time,
                trace=traces,
                handoff_report=handoff
            )

        # 3. Thực thi từng bước theo kế hoạch đã duyệt
        context_vars = {}
        active_booking_code = None

        for step in plan.steps:
            step_idx = self.budget.current_steps + 1
            # Plan-then-execute không gửi lại lịch sử dài sau mỗi vòng -> tiết kiệm token (Slide 23)
            tokens_step = 600
            self.budget.record_step(tokens_used=tokens_step)

            # Phân giải các biến tham chiếu ($best_flight, $booking_code...)
            actual_args = {}
            for k, v in step.args_template.items():
                if isinstance(v, str) and v.startswith("$"):
                    var_name = v[1:]
                    actual_args[k] = context_vars.get(var_name)
                else:
                    actual_args[k] = v

            # Thực thi bước
            step_trace = AgentStepTrace(
                step_index=step_idx,
                thought=f"Thực thi bước {step.step_id}/{len(plan.steps)}: {step.description}",
                action_tool=step.tool_name,
                action_args=actual_args,
                tokens_estimate=tokens_step
            )

            # Kiểm quyền và ràng buộc nếu là bước book_seat
            if step.tool_name == "book_seat":
                fl_id = actual_args.get("flight_id")
                fl_obj = self.db.flights.get(fl_id)
                if fl_obj:
                    fl_dict = {"flight": fl_obj.flight_id, "price": fl_obj.price, "refundable": fl_obj.refundable, "depart": fl_obj.depart_time, "depart_date": fl_obj.depart_date}
                    ok_c, reason_c = self.constraint_validator.enforce_before_action(step.tool_name, actual_args, fl_dict)
                    if not ok_c:
                        step_trace.harness_event = f"Harness chặn bước {step.step_id}: {reason_c}"
                        traces.append(step_trace)
                        return AgentExecutionResult(
                            agent_type="Plan-then-Execute",
                            success=False,
                            finish_reason="CONSTRAINT_VIOLATION",
                            final_message=f"Kế hoạch bị huỷ do vi phạm ràng buộc: {reason_c}",
                            total_steps=step_idx,
                            total_tokens=self.budget.current_tokens,
                            duration_seconds=time.time() - start_time,
                            trace=traces
                        )

            obs = self.execute_tool(step.tool_name, actual_args)
            step_trace.observation = obs
            step.result = obs

            # Kiểm tra lỗi ở bước (Slide 23: Lỗi ở bước đầu sẽ làm hỏng toàn bộ sau)
            if obs.get("status") in ["error", "invalid_param"]:
                step.status = "FAILED"
                step_trace.harness_event = f"BƯỚC {step.step_id} THẤT BẠI: {obs.get('error')}. Kế hoạch tĩnh không thể thích nghi (Slide 23, 26)."
                traces.append(step_trace)
                handoff = HumanHandoffManager.create_failure_handoff(
                    reason=f"Kế hoạch tĩnh bị đổ vỡ tại bước {step.step_id} ({step.tool_name}): {obs.get('error')}",
                    attempts=[f"Bước {step.step_id} thất bại, không có cơ chế replanning trong mẫu Plan-then-Execute thuần."],
                    question="Bạn có muốn chuyển sang mẫu Lai (Hybrid) để tự động lập lại kế hoạch không?"
                )
                return AgentExecutionResult(
                    agent_type="Plan-then-Execute",
                    success=False,
                    finish_reason="PLAN_EXECUTION_FAILED",
                    final_message=f"Kế hoạch gãy tại bước {step.step_id}: {obs.get('error')}",
                    total_steps=step_idx,
                    total_tokens=self.budget.current_tokens,
                    duration_seconds=time.time() - start_time,
                    trace=traces,
                    handoff_report=handoff
                )

            # Cập nhật context vars cho các bước tiếp theo
            if step.tool_name == "search_flights":
                flights = obs.get("flights", [])
                valid_flights = [f for f in flights if f.get("depart") < self.constraints.depart_before and f.get("price") <= self.constraints.max_price]
                if not valid_flights:
                    step_trace.harness_event = "Không tìm thấy chuyến bay thoả mãn yêu cầu."
                    traces.append(step_trace)
                    return AgentExecutionResult(
                        agent_type="Plan-then-Execute",
                        success=False,
                        finish_reason="STALL_DETECTED",
                        final_message="Không có chuyến bay nào đáp ứng điều kiện.",
                        total_steps=step_idx,
                        total_tokens=self.budget.current_tokens,
                        duration_seconds=time.time() - start_time,
                        trace=traces
                    )
                context_vars["best_flight"] = valid_flights[0]["flight"]

            elif step.tool_name == "check_seat":
                seats = obs.get("available_seats", [])
                if not seats:
                    step_trace.harness_event = "Hết ghế trống."
                    traces.append(step_trace)
                    handoff = HumanHandoffManager.create_failure_handoff(
                        reason=f"Chuyến bay {actual_args.get('flight_id')} đã hết ghế trống",
                        attempts=[f"Kế hoạch tĩnh đã chọn {actual_args.get('flight_id')} nhưng thực tế không còn ghế."],
                        question="Bạn có muốn chuyển sang mẫu Lai (Hybrid) để tự động tìm chuyến bay khác không?"
                    )
                    return AgentExecutionResult(
                        agent_type="Plan-then-Execute",
                        success=False,
                        finish_reason="PLAN_EXECUTION_FAILED",
                        final_message="Chuyến bay đã chọn không còn ghế trống.",
                        total_steps=step_idx,
                        total_tokens=self.budget.current_tokens,
                        duration_seconds=time.time() - start_time,
                        trace=traces,
                        handoff_report=handoff
                    )
                context_vars["first_seat"] = seats[0]

            elif step.tool_name == "book_seat":
                active_booking_code = obs.get("booking_code")
                context_vars["booking_code"] = active_booking_code

            step.status = "COMPLETED"
            traces.append(step_trace)

        # Kết thúc toàn bộ các bước trong kế hoạch -> Xác thực code khách quan (Slide 43)
        if active_booking_code:
            verify_res = self.computational_verifier.verify(active_booking_code)
            if verify_res["achieved"]:
                return AgentExecutionResult(
                    agent_type="Plan-then-Execute",
                    success=True,
                    finish_reason="GOAL_ACHIEVED",
                    final_message=f"Hoàn thành kế hoạch đặt vé thành công! Mã PNR: {active_booking_code}.",
                    booking_code=active_booking_code,
                    total_steps=len(plan.steps) + 1,
                    total_tokens=self.budget.current_tokens,
                    duration_seconds=time.time() - start_time,
                    trace=traces
                )

        return AgentExecutionResult(
            agent_type="Plan-then-Execute",
            success=False,
            finish_reason="GOAL_NOT_VERIFIED",
            final_message="Đã chạy hết các bước nhưng kết quả không đạt tiêu chí kiểm chứng.",
            total_steps=len(plan.steps) + 1,
            total_tokens=self.budget.current_tokens,
            duration_seconds=time.time() - start_time,
            trace=traces
        )
