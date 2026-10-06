import time
import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

try:
    from tabulate import tabulate
    HAS_TABULATE = True
except ImportError:
    HAS_TABULATE = False

from src.benchmark.scenarios import BenchmarkScenario, get_standard_scenarios
from src.agents.react_agent import ReActFlightAgent
from src.agents.plan_execute_agent import PlanThenExecuteFlightAgent
from src.agents.hybrid_agent import HybridFlightAgent
from src.agents.base import AgentExecutionResult


class ScenarioEvaluationResult(BaseModel):
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
    timestamp: str
    individual_runs: List[ScenarioEvaluationResult]
    summary_by_agent: Dict[str, Dict[str, Any]]

    def print_markdown_table(self):
        headers = ["Evaluation Metric", "Pattern 1: ReAct", "Pattern 2: Plan-then-Execute", "Pattern 3: Hybrid"]
        rows = [
            [
                "Success Rate",
                f"{self.summary_by_agent.get('ReAct', {}).get('success_rate', 0):.1f}%",
                f"{self.summary_by_agent.get('Plan-then-Execute', {}).get('success_rate', 0):.1f}%",
                f"{self.summary_by_agent.get('Hybrid', {}).get('success_rate', 0):.1f}%",
            ],
            [
                "Average Steps",
                f"{self.summary_by_agent.get('ReAct', {}).get('avg_steps', 0):.1f}",
                f"{self.summary_by_agent.get('Plan-then-Execute', {}).get('avg_steps', 0):.1f}",
                f"{self.summary_by_agent.get('Hybrid', {}).get('avg_steps', 0):.1f}",
            ],
            [
                "Average Tokens",
                f"{self.summary_by_agent.get('ReAct', {}).get('avg_tokens', 0):,}",
                f"{self.summary_by_agent.get('Plan-then-Execute', {}).get('avg_tokens', 0):,}",
                f"{self.summary_by_agent.get('Hybrid', {}).get('avg_tokens', 0):,}",
            ],
            [
                "Handoff / Approvals Triggered",
                f"{self.summary_by_agent.get('ReAct', {}).get('handoff_count', 0)} times",
                f"{self.summary_by_agent.get('Plan-then-Execute', {}).get('handoff_count', 0)} times",
                f"{self.summary_by_agent.get('Hybrid', {}).get('handoff_count', 0)} times",
            ],
            [
                "Drift Resilience (SC2)",
                "Moderate (Dynamic step)",
                "Brittle (Static plan fails)",
                "High (Dynamic replanning)",
            ],
            [
                "Upfront Cost Control (SC5)",
                "None (Runs immediately)",
                "Absolute (Reviewed prior to run)",
                "Roadmap-guided",
            ],
        ]

        output_lines = [
            "\n" + "=" * 80,
            "BENCHMARK EVALUATION REPORT: 3 AGENT ARCHITECTURES",
            "=" * 80,
        ]
        if HAS_TABULATE:
            output_lines.append(tabulate(rows, headers=headers, tablefmt="github"))
        else:
            output_lines.append(f"{headers[0]:<30} | {headers[1]:<18} | {headers[2]:<25} | {headers[3]:<18}")
            output_lines.append("-" * 95)
            for r in rows:
                output_lines.append(f"{r[0]:<30} | {r[1]:<18} | {r[2]:<25} | {r[3]:<18}")
        output_lines.append("=" * 80 + "\n")

        print("\n".join(output_lines))


class AgentBenchmarkRunner:
    def __init__(self, scenarios: Optional[List[BenchmarkScenario]] = None):
        self.scenarios = scenarios or get_standard_scenarios()

    def run_benchmark(self) -> BenchmarkReport:
        individual_results: List[ScenarioEvaluationResult] = []

        agent_constructors = {
            "ReAct": lambda c, db, sc: ReActFlightAgent(c, db=db, auto_approve_human_gate=sc.auto_approve_human_gate),
            "Plan-then-Execute": lambda c, db, sc: PlanThenExecuteFlightAgent(c, db=db, auto_approve_plan=sc.auto_approve_plan),
            "Hybrid": lambda c, db, sc: HybridFlightAgent(c, db=db, auto_approve_human_gate=sc.auto_approve_human_gate),
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
                    handoff_triggered=res.handoff_report is not None,
                )
                individual_results.append(eval_record)

        summary = {}
        for agent_name in ["ReAct", "Plan-then-Execute", "Hybrid"]:
            runs = [r for r in individual_results if r.agent_type == agent_name]
            total_runs = len(runs)
            success_runs = sum(1 for r in runs if r.success)
            total_steps = sum(r.steps for r in runs)
            total_tokens = sum(r.tokens for r in runs)
            handoff_count = sum(1 for r in runs if r.handoff_triggered)

            summary[agent_name] = {
                "total_runs": total_runs,
                "success_runs": success_runs,
                "success_rate": (success_runs / total_runs * 100) if total_runs > 0 else 0.0,
                "avg_steps": (total_steps / total_runs) if total_runs > 0 else 0.0,
                "avg_tokens": int(total_tokens / total_runs) if total_runs > 0 else 0,
                "handoff_count": handoff_count,
            }

        return BenchmarkReport(
            timestamp=datetime.datetime.now().isoformat(),
            individual_runs=individual_results,
            summary_by_agent=summary,
        )
