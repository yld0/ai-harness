"""Offline DeepEval metric smoke (no LLM / network)."""

from __future__ import annotations

from deepeval import assert_test
from deepeval.metrics import ExactMatchMetric
from deepeval.test_case import LLMTestCase


def test_deepeval_exact_match_offline() -> None:
    case = LLMTestCase(
        input="fixture",
        actual_output="42",
        expected_output="42",
    )
    assert_test(case, [ExactMatchMetric()], run_async=False)
