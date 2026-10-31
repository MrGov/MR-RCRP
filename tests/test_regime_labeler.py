"""P2 regime labeller: frozen rules, mutual exclusivity, missing evidence."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mrta_rect_coverage.llm.operator_evolution.regime_labeler import (
    REGIME_THRESHOLDS,
    informative_positions,
    label_regime,
    route_cost_shares,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PARENTS_DIR = PROJECT_ROOT / "outputs" / "e14_state_regret_instrument" / "parents"


def _positions(gaps, *, tied_state_count=1, informative=True):
    positions = []
    for index, gap in enumerate(gaps):
        mode = "H" if gap < 0 else ("V" if gap > 0 else "equivalent")
        positions.append(
            {
                "position": index,
                "task_id": index + 1,
                "chosen_state_id": 10 + index,
                "chosen_rank": 1,
                "min_alternative_regret": abs(gap),
                "near_tie_count": tied_state_count - 1,
                "tied_state_count": tied_state_count,
                "informative": informative,
                "best_h_q": 0.0,
                "best_v_q": 0.0,
                "mode_gap": gap,
                "mode_preference": mode,
                "options": [],
            }
        )
    return positions


def _report(
    positions,
    *,
    makespan=1000.0,
    load_excess=0.0,
    shares=(0.50, 0.01, 0.49),
    include_regret=True,
):
    transfer, turning, coverage = shares
    route = {
        "route_id": 0,
        "task_order": [p["task_id"] for p in positions],
        "cost_split": {
            "coverage": coverage * makespan,
            "turning": turning * makespan,
            "transfer": transfer * makespan,
            "total": makespan,
            "coverage_share": coverage,
            "turning_share": turning,
            "transfer_share": transfer,
        },
    }
    if include_regret:
        route["regret_table"] = positions
    return {
        "instance": {"name": "TEST_0", "robot_count": 1},
        "makespan": makespan,
        "per_robot_costs": [makespan],
        "route_load_excess": load_excess,
        "bottleneck_routes": [0],
        "objective": {
            "mean_processing": coverage * makespan,
            "mean_transfer": transfer * makespan,
            "load_excess": load_excess,
            "makespan": makespan,
        },
        "routes": [route],
    }


def test_reg1_hv_geometry_share_reaches_mode_sensitive():
    # 8 of 10 informative positions carry a gap >= 1% of makespan.
    report = _report(_positions([40.0, -50.0, 60.0, -70.0, 80.0, 90.0, -30.0, 25.0, 1.0, -2.0]))
    result = label_regime(report)
    assert result["regime"] == "mode_sensitive"
    assert result["evidence"]["large_gap_position_count"] == 8
    assert result["evidence"]["informative_count"] == 10
    assert result["evidence"]["threshold"] == REGIME_THRESHOLDS["mode_sensitive_position_share"]


def test_reg2_balance_dominated_by_load_excess_ratio():
    report = _report(_positions([1.0, -2.0, 3.0]), load_excess=200.0)
    result = label_regime(report)
    assert result["regime"] == "balance_dominated"
    assert result["evidence"]["ratio"] == pytest.approx(0.2)


def test_reg3_turn_heavy_by_mean_turning_share():
    report = _report(_positions([1.0]), shares=(0.60, 0.08, 0.32), load_excess=10.0)
    result = label_regime(report)
    assert result["regime"] == "turn_heavy"
    assert result["evidence"]["mean_turning_share"] == pytest.approx(0.08)


def test_reg4_transfer_dominated_by_mean_transfer_share():
    report = _report(_positions([1.0]), shares=(0.80, 0.02, 0.18), load_excess=10.0)
    result = label_regime(report)
    assert result["regime"] == "transfer_dominated"
    assert result["evidence"]["mean_transfer_share"] == pytest.approx(0.80)


def test_reg5_no_rule_reaches_its_threshold_gives_mixed():
    report = _report(_positions([1.0, -1.0]), shares=(0.50, 0.01, 0.49), load_excess=10.0)
    result = label_regime(report)
    assert result["regime"] == "mixed"
    candidates = result["evidence"]["candidates"]
    assert candidates["mode_sensitive"]["availability"] == "ok"
    assert candidates["mode_sensitive"]["share"] == 0.0
    assert candidates["balance_dominated"]["ratio"] == pytest.approx(0.01)
    assert candidates["turn_heavy"]["mean_turning_share"] == pytest.approx(0.01)
    assert candidates["transfer_dominated"]["mean_transfer_share"] == pytest.approx(0.50)


def test_reg6_rules_are_mutually_exclusive_and_ordered():
    # Satisfies both mode_sensitive and balance_dominated; order decides.
    report = _report(
        _positions([40.0, -50.0, 60.0, -70.0, 80.0]), load_excess=400.0
    )
    result = label_regime(report)
    assert result["regime"] == "mode_sensitive"


def test_reg7_missing_regret_table_skips_rule_one_without_zero():
    report = _report(_positions([1.0]), include_regret=False, load_excess=200.0)
    assert label_regime(report)["regime"] == "balance_dominated"
    single = _report(_positions([1.0]), include_regret=False, shares=(0.50, 0.01, 0.49))
    result = label_regime(single)
    assert result["regime"] == "mixed"
    evidence = result["evidence"]["candidates"]["mode_sensitive"]
    assert evidence["availability"] == "unavailable"
    assert "share" not in evidence


def test_reg8_real_parent_reports_match_family_labels():
    if not PARENTS_DIR.is_dir():
        pytest.skip("run e14 --stage parents to materialise parent reports")
    paths = sorted(PARENTS_DIR.glob("*.json"))
    if not paths:
        pytest.skip("no parent reports on disk")
    for path in paths:
        report = json.loads(path.read_text(encoding="utf-8"))
        name = report["instance"]["name"]
        regime = label_regime(report)["regime"]
        if "HV-GEOM" in name:
            assert regime == "mode_sensitive", (name, regime)
        else:
            assert regime != "mode_sensitive", (name, regime)


def test_helpers_are_pure_and_consistent():
    report = _report(_positions([10.0, 0.0, -20.0]))
    positions = informative_positions(report)
    assert len(positions) == 3
    assert positions[0]["route_id"] == 0
    assert positions[1]["route_position"] == 1
    shares = route_cost_shares(report)
    assert shares["route_count"] == 1
    assert shares["mean_transfer_share"] == pytest.approx(0.50)
    # No mutation of the caller's dict.
    assert "route_id" not in report["routes"][0]["regret_table"][0]
