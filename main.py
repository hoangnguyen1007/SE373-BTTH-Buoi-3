import argparse
from src.domain.models import FlightConstraints
from src.tools.flight_tools import MockFlightDatabase
from src.agents.react_agent import ReActFlightAgent
from src.agents.plan_execute_agent import PlanThenExecuteFlightAgent
from src.agents.hybrid_agent import HybridFlightAgent
from src.benchmark.evaluator import AgentBenchmarkRunner


def parse_args():
    parser = argparse.ArgumentParser(
        description="SE373 Flight Booking Agent & Harness System."
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Run comprehensive benchmark comparing the 3 agent patterns across 5 scenarios.",
    )
    parser.add_argument(
        "--agent",
        choices=["react", "plan", "hybrid"],
        default="hybrid",
        help="Choose agent pattern for interactive run (default: hybrid).",
    )
    parser.add_argument("--origin", default="SGN", help="Origin airport code.")
    parser.add_argument("--destination", default="DAD", help="Destination airport code.")
    parser.add_argument("--date", default="2026-10-07", help="Flight departure date (YYYY-MM-DD).")
    parser.add_argument("--max-price", type=int, default=2000000, help="Max budget in VND.")
    parser.add_argument("--depart-before", default="12:00", help="Departure time ceiling (HH:MM).")
    parser.add_argument(
        "--require-approval",
        action="store_true",
        help="Enforce human approval halt on high-value or non-refundable tickets (Slide 41).",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.benchmark:
        print("\n[+] Starting Benchmark across ReAct, Plan-then-Execute, and Hybrid agents...")
        runner = AgentBenchmarkRunner()
        report = runner.run_benchmark()
        report.print_markdown_table()
        print("[+] Benchmark completed successfully.\n")
        return

    constraints = FlightConstraints(
        origin=args.origin,
        destination=args.destination,
        date=args.date,
        depart_before=args.depart_before,
        max_price=args.max_price,
    )
    db = MockFlightDatabase()

    prompt = (
        f"Book a flight from {args.origin} to {args.destination} on {args.date} "
        f"departing before {args.depart_before} within budget {args.max_price:,} VND."
    )

    print("\n" + "=" * 70)
    print(f"INITIALIZING FLIGHT AGENT: {args.agent.upper()}")
    print(f"Goal: {prompt}")
    print(f"Constraints: Origin={constraints.origin}, Dest={constraints.destination}, Date={constraints.date}, Before={constraints.depart_before}, MaxPrice={constraints.max_price:,} VND")
    print("=" * 70 + "\n")

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
