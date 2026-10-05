"""
Unit tests cho Khung Benchmark & Đánh giá so sánh thực nghiệm (Commit 6).
"""
import unittest
from src.benchmark.evaluator import AgentBenchmarkRunner
from src.benchmark.scenarios import get_standard_scenarios


class TestBenchmarkFramework(unittest.TestCase):

    def test_benchmark_runner_execution(self):
        """Khung benchmark chạy đầy đủ 5 scenarios trên cả 3 agent thành công."""
        scenarios = get_standard_scenarios()
        self.assertEqual(len(scenarios), 5)

        runner = AgentBenchmarkRunner(scenarios=scenarios)
        report = runner.run_benchmark()

        # Tổng cộng 5 kịch bản x 3 loại agent = 15 lần chạy
        self.assertEqual(len(report.individual_runs), 15)

        # Kiểm tra tổng hợp số liệu
        self.assertIn("ReAct", report.summary_by_agent)
        self.assertIn("Plan-then-Execute", report.summary_by_agent)
        self.assertIn("Hybrid", report.summary_by_agent)

        react_summary = report.summary_by_agent["ReAct"]
        plan_summary = report.summary_by_agent["Plan-then-Execute"]
        hybrid_summary = report.summary_by_agent["Hybrid"]

        # Kiểm chứng nguyên lý lý thuyết Slide 14 & 23:
        # ReAct nạp lại toàn bộ lịch sử nên tốn nhiều token hơn Plan-then-Execute
        self.assertTrue(react_summary["avg_tokens"] > plan_summary["avg_tokens"])

        # Kiểm tra in bảng không gây lỗi
        report.print_markdown_table()


if __name__ == "__main__":
    unittest.main()
