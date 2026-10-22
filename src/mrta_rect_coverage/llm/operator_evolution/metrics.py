"""Metrics definitions and aggregation for candidate operators."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from .schemas import OperatorMetricsSummary


@dataclass
class TrialMetric:
    makespan_delta: float
    relative_improvement: float
    runtime_ms: float
    success: bool
    timeout: bool
    error: bool
    invalid_solution: bool


def summarize_trials(trials: Iterable[TrialMetric]) -> OperatorMetricsSummary:
    rows = list(trials)
    if not rows:
        return OperatorMetricsSummary(
            avg_makespan_delta=0.0,
            avg_relative_improvement=0.0,
            success_rate=0.0,
            avg_runtime_ms=0.0,
            timeout_rate=0.0,
            error_rate=0.0,
            invalid_solution_rate=0.0,
        )

    n = len(rows)
    return OperatorMetricsSummary(
        avg_makespan_delta=sum(r.makespan_delta for r in rows) / n,
        avg_relative_improvement=sum(r.relative_improvement for r in rows) / n,
        success_rate=sum(1.0 for r in rows if r.success) / n,
        avg_runtime_ms=sum(r.runtime_ms for r in rows) / n,
        timeout_rate=sum(1.0 for r in rows if r.timeout) / n,
        error_rate=sum(1.0 for r in rows if r.error) / n,
        invalid_solution_rate=sum(1.0 for r in rows if r.invalid_solution) / n,
    )
