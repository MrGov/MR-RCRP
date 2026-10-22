from __future__ import annotations

from pathlib import Path

import pytest

from scripts.analyze_r3_diagnostics import (
    load_raw_artifacts,
    normalize_run_identity,
    spearman_correlation,
    summarize_behavior,
    summarize_operators,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_normalize_run_identity_uses_source_and_family_provenance() -> None:
    run = {
        "run_id": "legacy-id",
        "instance_id": "controlled-r0",
        "source_track": "B-development",
        "family_id": "F_CONTROLLED",
        "solver_seed": 2,
        "solver_config_hash": "a" * 64,
    }

    normalized = normalize_run_identity(run)

    assert normalized["run_id"] == "B-development-F_CONTROLLED-seed-2-aaaaaaaaaaaa"
    assert run["run_id"] == "legacy-id"


def test_spearman_correlation_uses_average_ranks_for_ties() -> None:
    assert spearman_correlation([1, 1, 3], [1, 2, 3]) == pytest.approx(
        0.8660254037844387
    )
    assert spearman_correlation([1, 1], [2, 2]) is None


def test_operator_summary_separates_pre_ls_and_frozen_hypothesis_metrics() -> None:
    run = {
        "run_id": "run-1",
        "source_track": "A",
        "instance_id": "instance-1",
        "family_id": None,
        "iterations": [
            {
                "destroy": "random_destroy",
                "repair": "greedy_insertion",
                "accepted": True,
                "repair_gain": 2.0,
                "objective_gain": 5.0,
                "state_changed_fraction": 0.25,
                "dp_cascade_ratio": 0.5,
            }
        ],
    }

    rows = summarize_operators([run])
    destroy = next(row for row in rows if row["operator_type"] == "destroy")

    assert destroy["positive_pre_ls_gain_per_use"] == 2.0
    assert destroy["positive_objective_gain_per_use"] == 5.0


def test_current_raw_artifacts_consolidate_without_identity_collisions() -> None:
    raw_dir = PROJECT_ROOT / "outputs" / "r3_diagnostics" / "raw"

    runs, instance_rows = load_raw_artifacts(raw_dir)
    behavior = summarize_behavior(runs, instance_rows)

    assert len(runs) == 45
    assert len(instance_rows) == 65
    assert len(behavior) == 11
    assert len({run["run_id"] for run in runs}) == 45
    assert all(run["provider_used"] is False for run in runs)
    assert all(run["generated_operator_used"] is False for run in runs)
    assert {
        row["behavior_id"] for row in behavior if row["source_track"] == "B-held-out"
    } == {"B-held-out:F_HOLD_DEPOT_NEAR", "B-held-out:F_HOLD_DISPERSED"}
