import unittest
from src.benchmark.evaluator import AgentBenchmarkRunner
from src.benchmark.scenarios import get_standard_scenarios


class TestBenchmarkFramework(unittest.TestCase):

    def test_benchmark_runner_execution(self):
        scenarios = get_standard_scenarios()
        self.assertEqual(len(scenarios), 5)

        runner = AgentBenchmarkRunner(scenarios=scenarios)
        report = runner.run_benchmark()

        self.assertEqual(len(report.individual_runs), 15)
        self.assertIn("ReAct", report.summary_by_agent)
        self.assertIn("Plan-then-Execute", report.summary_by_agent)
        self.assertIn("Hybrid", report.summary_by_agent)

        react = report.summary_by_agent["ReAct"]
        plan = report.summary_by_agent["Plan-then-Execute"]
        self.assertTrue(react["avg_tokens"] > plan["avg_tokens"])

        report.print_markdown_table()


if __name__ == "__main__":
    unittest.main()
