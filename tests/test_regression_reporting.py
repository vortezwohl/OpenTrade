"""
回归脚本的失败分类与报告证据测试。

该测试聚焦 `scripts/regression_reporting.py` 及其在两个真实回归
执行器中的最小契约，确保四类失败分层、路由证据归一化与
汇总字段不会被再次改回旧口径。
"""

from __future__ import annotations

import unittest

from scripts.regression_reporting import (
    classify_regression_failure,
    detect_auto_fallback,
    normalize_backend_meta,
)
from scripts.run_incremental_full_regression import build_summary as build_incremental_summary
from scripts.run_third_full_regression import summarize as build_third_summary


class RegressionReportingTest(unittest.TestCase):
    def test_classify_sample_mismatch_for_cli_argument_errors(self) -> None:
        failure_class, reason = classify_regression_failure(
            command_path="stock leaderboard daily",
            requested_backend="efinance",
            stdout="",
            stderr="Error: Invalid value for '--date': should be in YYYYMMDD",
            returncode=2,
            status="fail",
            backend_meta={},
            artifact_reports=[],
        )

        self.assertEqual(failure_class, "sample_mismatch")
        self.assertIn("Error", reason or "")

    def test_classify_adapter_gap_for_shared_provider_semantic_conflict(self) -> None:
        failure_class, _ = classify_regression_failure(
            command_path="market price live",
            requested_backend="efinance",
            stdout="",
            stderr="provider does not support shared market semantics for market=A_stock fs=m:0+t:6",
            returncode=1,
            status="fail",
            backend_meta={},
            artifact_reports=[],
        )

        self.assertEqual(failure_class, "adapter_gap")

    def test_classify_upstream_instability_for_timeout_and_rate_limit(self) -> None:
        timeout_class, _ = classify_regression_failure(
            command_path="quote price latest",
            requested_backend="auto",
            stdout="",
            stderr="TIMEOUT after 45s",
            returncode=None,
            status="timeout",
            backend_meta={"planned_candidates": ["efinance", "yfinance"]},
            artifact_reports=[],
        )
        rate_limit_class, _ = classify_regression_failure(
            command_path="quote price latest",
            requested_backend="yfinance",
            stdout="",
            stderr="YFRateLimitError: Too Many Requests",
            returncode=1,
            status="fail",
            backend_meta={},
            artifact_reports=[],
        )

        self.assertEqual(timeout_class, "upstream_instability")
        self.assertEqual(rate_limit_class, "upstream_instability")

    def test_classify_product_defect_for_missing_artifact(self) -> None:
        failure_class, _ = classify_regression_failure(
            command_path="fund reports download",
            requested_backend="efinance",
            stdout="{}",
            stderr="",
            returncode=0,
            status="degraded",
            backend_meta={"final_backend": "efinance"},
            artifact_reports=[{"exists": False}],
        )

        self.assertEqual(failure_class, "product_defect")

    def test_normalize_backend_meta_preserves_routing_and_limit_evidence(self) -> None:
        metadata = normalize_backend_meta(
            {
                "requested_backend": "auto",
                "resolved_backend": "auto",
                "candidate_chain": ["efinance", "yfinance"],
                "attempted_candidates": ["efinance"],
                "final_backend": "yfinance",
                "limit_strategy": "provider-request",
                "limit_effect": "execution-aware",
                "display_limit_applied": True,
                "execution_limit_applied": True,
            }
        )

        self.assertEqual(metadata["planned_candidates"], ["efinance", "yfinance"])
        self.assertEqual(metadata["attempted_candidates"], ["efinance"])
        self.assertEqual(metadata["final_backend"], "yfinance")
        self.assertEqual(metadata["limit_strategy"], "provider-request")
        self.assertEqual(metadata["limit_effect"], "execution-aware")
        self.assertTrue(metadata["display_limit_applied"])
        self.assertTrue(metadata["execution_limit_applied"])
        self.assertTrue(detect_auto_fallback("auto", metadata))

    def test_incremental_summary_counts_failure_classifications(self) -> None:
        summary = build_incremental_summary(
            [
                {
                    "status": "pass",
                    "duration_seconds": 0.2,
                    "requested_backend": "efinance",
                    "category": "stock",
                    "mode_tags": [],
                    "auto_fallback_used": False,
                    "failure_class": None,
                },
                {
                    "status": "fail",
                    "duration_seconds": 0.4,
                    "requested_backend": "auto",
                    "category": "quote",
                    "mode_tags": ["view-raw"],
                    "auto_fallback_used": True,
                    "failure_class": "adapter_gap",
                },
            ],
            total_cases=3,
        )

        self.assertEqual(summary["failure_class_counter"], {"adapter_gap": 1})
        self.assertEqual(summary["failure_counter"], {"adapter_gap": 1})
        self.assertEqual(summary["auto_stats"]["fallback_used"], 1)

    def test_third_summary_counts_failure_classifications(self) -> None:
        summary = build_third_summary(
            [
                {
                    "status": "PASS",
                    "duration_seconds": 0.2,
                    "requested_backend": "efinance",
                    "category": "stock",
                    "backend_meta": {"final_backend": "efinance"},
                    "auto_fallback_used": False,
                    "failure_class": None,
                },
                {
                    "status": "FAIL",
                    "duration_seconds": 0.5,
                    "requested_backend": "auto",
                    "category": "quote",
                    "backend_meta": {"final_backend": None},
                    "auto_fallback_used": False,
                    "failure_class": "upstream_instability",
                },
            ],
            {"mode_tags": []},
        )

        self.assertEqual(summary["failure_class_counter"], {"upstream_instability": 1})
        self.assertEqual(summary["auto_stats"]["all_failed_without_final_backend"], 1)


if __name__ == "__main__":
    unittest.main()
