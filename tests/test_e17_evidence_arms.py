"""E17 arm bookkeeping: best-candidate selection and summary statistics."""
from __future__ import annotations

import json
from pathlib import Path

from mrta_rect_coverage.experiments import e17_evidence_arms as e17


def _row(operator_id, operator_type, improvement, *, success=1.0, delta=0.0, round_id="0"):
    return {
        "operator_id": operator_id,
        "operator_type": operator_type,
        "avg_relative_improvement": str(improvement),
        "avg_makespan_delta": str(delta),
        "success_rate": str(success),
        "execution_status": "success",
        "round_id": round_id,
    }


def test_best_by_type_picks_the_highest_improvement_per_type():
    rows = [
        _row("d0", "destroy", 0.10),
        _row("d1", "destroy", 0.21),
        _row("r0", "repair", -0.02),
        _row("r1", "repair", 0.03),
        _row("x0", "something_else", 9.99),
    ]
    best = e17._best_by_type(rows)
    assert best["destroy"]["operator_id"] == "d1"
    assert best["repair"]["operator_id"] == "r1"
    assert set(best) == {"destroy", "repair"}


def test_best_by_type_ignores_unparseable_rows_and_missing_types():
    rows = [
        {"operator_id": "bad", "operator_type": "destroy", "avg_relative_improvement": ""},
        _row("d0", "destroy", 0.05),
    ]
    best = e17._best_by_type(rows)
    assert best["destroy"]["operator_id"] == "d0"
    assert best["repair"] is None


def test_describe_reports_spread():
    described = e17._describe([0.1, 0.2, 0.6])
    assert described["n"] == 3
    assert described["median"] == 0.2
    assert described["min"] == 0.1 and described["max"] == 0.6


def test_describe_handles_an_empty_arm():
    assert e17._describe([]) == {"n": 0}


def test_arm_config_differs_only_in_the_evidence_block(tmp_path: Path):
    common = dict(
        repetition=0,
        output_root=tmp_path,
        instances=e17.DEFAULT_INSTANCES,
        evidence_glob=e17.DEFAULT_EVIDENCE_GLOB,
    )
    scalar = e17._arm_config(arm="F1_scalar", **common)
    dataset = e17._arm_config(arm="F2_dataset", **common)
    assert scalar.evidence_report_glob == ""
    assert dataset.evidence_report_glob == e17.DEFAULT_EVIDENCE_GLOB
    for field in (
        "round_count",
        "repair_candidates_per_round",
        "destroy_candidates_per_round",
        "benchmark_instance_list",
        "seeds",
        "timeout_ms",
        "provider_name",
        "use_rich_prompts",
        "evidence_budget_bytes",
    ):
        assert getattr(scalar, field) == getattr(dataset, field), field


def test_stage_analyze_writes_summary_and_report(tmp_path: Path, monkeypatch):
    runs = [
        {"arm": "F1_scalar", "repetition": 0, "destroy": {"avg_relative_improvement": 0.10,
                                                          "success_rate": 1.0, "round_id": 0},
         "repair": {"avg_relative_improvement": 0.01, "success_rate": 0.3, "round_id": 0}},
        {"arm": "F2_dataset", "repetition": 0, "destroy": {"avg_relative_improvement": 0.20,
                                                           "success_rate": 1.0, "round_id": 1},
         "repair": {"avg_relative_improvement": 0.02, "success_rate": 0.3, "round_id": 1}},
    ]
    (tmp_path / "runs.json").write_text(json.dumps(runs), encoding="utf-8")
    e17.stage_analyze(tmp_path)
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary["arms"]["F2_dataset"]["destroy"]["median"] == 0.20
    assert summary["delta_f2_minus_f1"]["destroy"]["median"] > 0.09
    report = (tmp_path / "REPORT.md").read_text(encoding="utf-8")
    assert "F1_scalar" in report and "F2_dataset" in report
    assert "cannot show" in report
