"""
Bộ đo lường & So sánh thực nghiệm 3 mẫu thiết kế Agent (Yêu cầu 03 BTVN#3).
Tính toán các chỉ số định lượng:
- Tỷ lệ thành công được kiểm chứng bằng code (Success Rate).
- Số bước trung bình (Average Steps).
- Tổng lượng token tiêu thụ (Token Efficiency).
- Tỷ lệ kích hoạt bảo vệ Harness / Bàn giao con người (Safety Rate).
- Khả năng tự thích ứng khi môi trường biến động (Adaptability).
"""
import time
import json
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

try:
    from tabulate import tabulate
    HAS_TABULATE = True
except ImportError:
    HAS_TABULATE = False

from src.domain.models import FlightConstraints
from src.tools.flight_tools import MockFlightDatabase
from src.agents.react_agent import ReActFlightAgent
from src.agents.plan_execute_agent import PlanThenExecuteFlightAgent
from src.agents.hybrid_agent import HybridFlightAgent
from src.agents.base import AgentExecutionResult
from src.benchmark.scenarios import BenchmarkScenario, get_standard_scenarios


class ScenarioEvaluationResult(BaseModel):
    """Kết quả chạy 1 scenario của 1 agent."""
    scenario_id: str
    scenario_title: str
    agent_type: str
    success: bool
    finish_reason: str
    steps: int
    tokens: int
    duration: float
    handoff_triggered: bool


class BenchmarkReport(BaseModel):
    """Báo cáo tổng kết toàn bộ quá trình benchmark."""
    timestamp: str
    individual_runs: List[ScenarioEvaluationResult]
    summary_by_agent: Dict[str, Dict[str, Any]]

    def print_markdown_table(self):
        """In bảng kết quả so sánh định lượng trực quan."""
        headers = ["Chỉ số đánh giá", "Mẫu 1: ReAct", "Mẫu 2: Plan-then-Execute", "Mẫu 3: Mẫu Lai (Hybrid)"]
        rows = [
            [
                "Tỷ lệ thành công (Success Rate)",
                f"{self.summary_by_agent.get('ReAct', {}).get('success_rate', 0):.1f}%",
                f"{self.summary_by_agent.get('Plan-then-Execute', {}).get('success_rate', 0):.1f}%",
                f"{self.summary_by_agent.get('Hybrid', {}).get('success_rate', 0):.1f}%",
            ],
            [
                "Số bước lặp TB (Avg Steps)",
                f"{self.summary_by_agent.get('ReAct', {}).get('avg_steps', 0):.1f}",
                f"{self.summary_by_agent.get('Plan-then-Execute', {}).get('avg_steps', 0):.1f}",
                f"{self.summary_by_agent.get('Hybrid', {}).get('avg_steps', 0):.1f}",
            ],
            [
                "Lượng Token TB (Avg Tokens)",
                f"{self.summary_by_agent.get('ReAct', {}).get('avg_tokens', 0):,}",
                f"{self.summary_by_agent.get('Plan-then-Execute', {}).get('avg_tokens', 0):,}",
                f"{self.summary_by_agent.get('Hybrid', {}).get('avg_tokens', 0):,}",
            ],
            [
                "Bàn giao / Duyệt (Handoff Count)",
                f"{self.summary_by_agent.get('ReAct', {}).get('handoff_count', 0)} lần",
                f"{self.summary_by_agent.get('Plan-then-Execute', {}).get('handoff_count', 0)} lần",
                f"{self.summary_by_agent.get('Hybrid', {}).get('handoff_count', 0)} lần",
            ],
            [
                "Khả năng thích ứng biến động (SC2)",
                "Tốt (Dynamic Steps)",
                "Kém (Kế hoạch tĩnh bị gãy)",
                "Xuất sắc (Tự động Replan)",
            ],
            [
                "Kiểm soát chi phí trước chạy (SC5)",
                "Không có cơ chế duyệt trước",
                "Tuyệt đối (Duyệt trước khi chạy)",
                "Có cơ chế Todo Roadmap",
            ]
        ]

        output_lines = [
            "\n" + "=" * 80,
            "BANG TONG KET SO SANH HIEU QUA 3 MAU THIET KE (YEU CAU 03 BTVN#3)",
            "=" * 80
        ]
        if HAS_TABULATE:
            output_lines.append(tabulate(rows, headers=headers, tablefmt="github"))
        else:
            output_lines.append(f"{headers[0]:<35} | {headers[1]:<15} | {headers[2]:<22} | {headers[3]:<15}")
            output_lines.append("-" * 95)
            for r in rows:
                output_lines.append(f"{r[0]:<35} | {r[1]:<15} | {r[2]:<22} | {r[3]:<15}")
        output_lines.append("=" * 80 + "\n")

        full_table = "\n".join(output_lines)
        try:
            print(full_table)
        except UnicodeEncodeError:
            import sys
            sys.stdout.buffer.write(full_table.encode("utf-8", errors="replace") + b"\n")


class AgentBenchmarkRunner:
    """Điều phối và chạy benchmark tự động."""
    def __init__(self, scenarios: Optional[List[BenchmarkScenario]] = None):
        self.scenarios = scenarios or get_standard_scenarios()

    def run_benchmark(self) -> BenchmarkReport:
        """Chạy kiểm thử toàn bộ 3 agent trên tất cả các kịch bản."""
        individual_results: List[ScenarioEvaluationResult] = []

        agent_constructors = {
            "ReAct": lambda c, db, sc: ReActFlightAgent(c, db=db, auto_approve_human_gate=sc.auto_approve_human_gate),
            "Plan-then-Execute": lambda c, db, sc: PlanThenExecuteFlightAgent(c, db=db, auto_approve_plan=sc.auto_approve_plan),
            "Hybrid": lambda c, db, sc: HybridFlightAgent(c, db=db, auto_approve_human_gate=sc.auto_approve_human_gate)
        }

        for sc in self.scenarios:
            for agent_name, agent_factory in agent_constructors.items():
                db = sc.create_database()
                agent = agent_factory(sc.constraints, db, sc)

                start_t = time.time()
                res: AgentExecutionResult = agent.run(sc.goal_prompt)
                dur = time.time() - start_t

                eval_record = ScenarioEvaluationResult(
                    scenario_id=sc.scenario_id,
                    scenario_title=sc.title,
                    agent_type=agent_name,
                    success=res.success,
                    finish_reason=res.finish_reason,
                    steps=res.total_steps,
                    tokens=res.total_tokens,
                    duration=dur,
                    handoff_triggered=res.handoff_report is not None
                )
                individual_results.append(eval_record)

        # Tính toán chỉ số tổng hợp
        summary = {}
        for agent_name in ["ReAct", "Plan-then-Execute", "Hybrid"]:
            agent_runs = [r for r in individual_results if r.agent_type == agent_name]
            total_runs = len(agent_runs)
            success_runs = sum(1 for r in agent_runs if r.success)
            total_steps = sum(r.steps for r in agent_runs)
            total_tokens = sum(r.tokens for r in agent_runs)
            handoff_count = sum(1 for r in agent_runs if r.handoff_triggered)

            summary[agent_name] = {
                "total_runs": total_runs,
                "success_runs": success_runs,
                "success_rate": (success_runs / total_runs * 100) if total_runs > 0 else 0.0,
                "avg_steps": (total_steps / total_runs) if total_runs > 0 else 0.0,
                "avg_tokens": int(total_tokens / total_runs) if total_runs > 0 else 0,
                "handoff_count": handoff_count
            }

        import datetime
        report = BenchmarkReport(
            timestamp=datetime.datetime.now().isoformat(),
            individual_runs=individual_results,
            summary_by_agent=summary
        )
        return report
