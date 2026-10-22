from __future__ import annotations

from pathlib import Path

import pytest

from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.heuristics.alns_solver import ALNSConfig, solve_with_alns
from mrta_rect_coverage.llm.mock_advisor import MockAdvisor


def _load_instance():
    project_root = Path(__file__).resolve().parents[1]
    return load_instance(project_root / "data" / "R2_T6_0.txt")


def test_dp_aware_insertion_cannot_be_enabled_as_independent_operator() -> None:
    instance = _load_instance()
    with pytest.raises(ValueError, match="not an independent"):
        solve_with_alns(
            instance,
            config=ALNSConfig(
                iterations=20,
                use_dp_aware_insertion=True,
                random_seed=1,
            ),
        )


def test_operator_scoring_updates() -> None:
    instance = _load_instance()
    result = solve_with_alns(
        instance,
        config=ALNSConfig(iterations=12, acceptance="simulated_annealing", random_seed=2),
    )

    destroy_uses = sum(rec.uses for rec in result.operator_usage_stats["destroy"].values())
    repair_uses = sum(rec.uses for rec in result.operator_usage_stats["repair"].values())
    assert destroy_uses == 12
    assert repair_uses == 12
    assert len(result.iteration_history) == 12


def test_alns_with_mock_advisor_runs() -> None:
    instance = _load_instance()
    result = solve_with_alns(
        instance,
        config=ALNSConfig(iterations=8, random_seed=3),
        advisor=MockAdvisor(),
    )
    assert result.best_evaluation.makespan >= 0
    assert len(result.iteration_history) == 8
