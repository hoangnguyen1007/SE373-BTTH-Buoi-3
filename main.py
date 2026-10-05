"""
SE373 - BTVN#3: Flight Booking Agent & Harness System.
File khởi chạy chính (Unified CLI Runner).
Cho phép:
1. Chạy đánh giá so sánh thực nghiệm 3 mẫu thiết kế Agent (--benchmark).
2. Chạy tương tác từng mẫu Agent cụ thể (--agent react|plan|hybrid).
"""
import sys
import argparse
from src.domain.models import FlightConstraints
from src.tools.flight_tools import MockFlightDatabase
from src.agents.react_agent import ReActFlightAgent
from src.agents.plan_execute_agent import PlanThenExecuteFlightAgent
from src.agents.hybrid_agent import HybridFlightAgent
from src.benchmark.evaluator import AgentBenchmarkRunner


def parse_args():
    parser = argparse.ArgumentParser(
        description="SE373 Buổi 03: Flight Booking Agent với 3 mẫu thiết kế và Harness 4 lớp."
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Chạy toàn bộ 5 kịch bản thử nghiệm so sánh 3 mẫu Agent (Yêu cầu 03 BTVN#3)."
    )
    parser.add_argument(
        "--agent",
        choices=["react", "plan", "hybrid"],
        default="hybrid",
        help="Chọn loại Agent để chạy tương tác (mặc định: hybrid)."
    )
    parser.add_argument(
        "--origin",
        default="SGN",
        help="Điểm đi (mặc định: SGN)."
    )
    parser.add_argument(
        "--destination",
        default="DAD",
        help="Điểm đến (mặc định: DAD)."
    )
    parser.add_argument(
        "--date",
        default="2026-10-07",
        help="Ngày khởi hành (mặc định: 2026-10-07)."
    )
    parser.add_argument(
        "--max-price",
        type=int,
        default=2000000,
        help="Ngân sách tối đa VNĐ (mặc định: 2.000.000)."
    )
    parser.add_argument(
        "--depart-before",
        default="12:00",
        help="Giờ khởi hành trước mốc này (mặc định: 12:00)."
    )
    parser.add_argument(
        "--require-approval",
        action="store_true",
        help="Yêu cầu người duyệt bấm xác nhận khi có hành động vượt quyền (Slide 41)."
    )
    return parser.parse_args()


def safe_print(text: str):
    """In an toàn không phụ thuộc bảng mã terminal."""
    try:
        print(text)
    except UnicodeEncodeError:
        import sys
        sys.stdout.buffer.write(text.encode("utf-8", errors="replace") + b"\n")


def main():
    args = parse_args()

    if args.benchmark:
        safe_print("\n[+] Bat dau chay Benchmark so sanh thuc nghiem 3 mau thiet ke Agent...")
        runner = AgentBenchmarkRunner()
        report = runner.run_benchmark()
        report.print_markdown_table()
        safe_print("[+] Hoan thanh Benchmark thanh cong!\n")
        return

    # Chạy tương tác một Agent
    constraints = FlightConstraints(
        origin=args.origin,
        destination=args.destination,
        date=args.date,
        depart_before=args.depart_before,
        max_price=args.max_price
    )
    db = MockFlightDatabase()

    prompt = (
        f"Đặt giúp tôi 1 vé máy bay từ {args.origin} đến {args.destination} "
        f"vào ngày {args.date}, trước {args.depart_before}, ngân sách tối đa {args.max_price:,} VNĐ."
    )

    safe_print(f"\n======================================================================")
    safe_print(f"KHOI TAO HE THONG AGENT DAT VE MAY BAY: {args.agent.upper()}")
    safe_print(f"Yeu cau: {prompt}")
    safe_print(f"Rang buoc: Origin={constraints.origin}, Dest={constraints.destination}, Date={constraints.date}, Before={constraints.depart_before}, MaxPrice={constraints.max_price:,}d")
    safe_print(f"======================================================================\n")

    auto_approve = not args.require_approval

    if args.agent == "react":
        agent = ReActFlightAgent(constraints, db=db, auto_approve_human_gate=auto_approve)
    elif args.agent == "plan":
        agent = PlanThenExecuteFlightAgent(constraints, db=db, auto_approve_plan=auto_approve)
    else:
        agent = HybridFlightAgent(constraints, db=db, auto_approve_human_gate=auto_approve)

    result = agent.run(prompt)
    result.print_trace_summary()


if __name__ == "__main__":
    main()
