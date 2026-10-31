"""P2 feedback payloads and prompt injection: budgets, ties, determinism."""
from __future__ import annotations

import json

import pytest

from mrta_rect_coverage.llm.operator_evolution import prompt_builder
from mrta_rect_coverage.llm.operator_evolution.feedback_builder import (
    FORBIDDEN_FIELDS,
    assert_no_forbidden_fields,
    build_paired_contrast,
    build_state_regret_feedback,
    summarize_degeneracy,
)


def _positions(gaps, *, informative_flags=None, tied=1):
    positions = []
    for index, gap in enumerate(gaps):
        informative = True if informative_flags is None else informative_flags[index]
        mode = "H" if gap < 0 else ("V" if gap > 0 else "equivalent")
        positions.append(
            {
                "position": index,
                "task_id": index + 1,
                "chosen_state_id": 10 + index,
                "chosen_rank": 1,
                "min_alternative_regret": abs(gap),
                "near_tie_count": tied - 1,
                "tied_state_count": tied,
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
    route_costs=None,
    load_excess=None,
    shares=(0.79, 0.05, 0.16),
    degeneracy=True,
    name="E10_HV-GEOM_r0",
    **extra,
):
    transfer, turning, coverage = shares
    costs = route_costs or [makespan, 900.0, 880.0, 870.0]
    excess = load_excess if load_excess is not None else makespan - sum(costs) / len(costs)
    routes = []
    for route_id, cost in enumerate(costs):
        routes.append(
            {
                "route_id": route_id,
                "task_order": [],
                "cost_split": {
                    "coverage": coverage * cost,
                    "turning": turning * cost,
                    "transfer": transfer * cost,
                    "total": cost,
                    "coverage_share": coverage,
                    "turning_share": turning,
                    "transfer_share": transfer,
                },
                **({"regret_table": positions} if route_id == 0 else {}),
            }
        )
    report = {
        "instance": {
            "name": name,
            "robot_count": len(costs),
            "task_count": sum(len(r["task_order"]) for r in routes) or len(positions),
        },
        "makespan": makespan,
        "per_robot_costs": costs,
        "route_load_excess": excess,
        "bottleneck_routes": [0],
        "objective": {
            "mean_processing": coverage * makespan,
            "mean_transfer": transfer * makespan,
            "load_excess": excess,
            "makespan": makespan,
        },
        "routes": routes,
    }
    if degeneracy:
        informed = sum(1 for p in positions if p["informative"])
        tied_count = sum(1 for p in positions if p["tied_state_count"] > 1)
        report["state_degeneracy"] = {
            "position_count": len(positions),
            "tied_position_count": tied_count,
            "all_equal_position_count": 0,
            "informative_position_count": informed,
            "mode_gap_abs_median": 24.0,
            "mode_gap_abs_max": 140.0,
            "mode_preference_counts": {"H": 1, "V": 2, "equivalent": 0, "unknown": 0},
        }
    report.update(extra)
    return report


def test_fb1_forbidden_field_is_detected_anywhere():
    assert "hv_mode_switch_fraction" in FORBIDDEN_FIELDS
    with pytest.raises(ValueError, match="forbidden E5 field"):
        assert_no_forbidden_fields({"a": [{"hv_mode_switch_fraction": 0.3}]})
    with pytest.raises(ValueError, match="forbidden E5 field"):
        assert_no_forbidden_fields({"nested": {"deep": {"mean_regret": 1.0}}})
    assert_no_forbidden_fields({"regime": {"regime": "mixed"}, "cost": 1.0})


def test_fb2_payload_contains_no_forbidden_field_name():
    report = _report(_positions([40.0, -60.0, 20.0]))
    payload = build_state_regret_feedback(report)
    serialized = json.dumps(payload, sort_keys=True)
    for name in FORBIDDEN_FIELDS:
        assert name not in serialized
    assert payload["feedback_mode"] == "F2_state_v2"


def test_fb3_notes_only_hold_informative_non_tied_positions():
    positions = _positions(
        [40.0, -60.0, 0.5, 30.0],
        informative_flags=[True, True, True, True],
    )
    positions[2]["tied_state_count"] = 4  # tied but (inconsistently) flagged informative
    report = _report(positions)
    payload = build_state_regret_feedback(report)
    assert payload["position_notes"], "expected at least one note"
    for note in payload["position_notes"]:
        assert note["tied_state_count"] == 1
        assert note["task_id"] != positions[2]["task_id"]
    assert payload["degeneracy"]["tied_position_fraction"] == pytest.approx(0.25)


def test_fb4_every_note_discloses_gap_as_makespan_ratio():
    report = _report(_positions([40.0, -60.0]), makespan=1000.0)
    payload = build_state_regret_feedback(report)
    for note in payload["position_notes"]:
        assert note["gap_ratio_of_makespan"] == pytest.approx(
            abs(note["mode_gap"]) / 1000.0
        )


def test_fb5_byte_size_matches_serialization_and_budget():
    report = _report(_positions([40.0, -60.0, 20.0, 25.0, 30.0]))
    payload = build_state_regret_feedback(report, budget_bytes=4000)
    probe = dict(payload)
    probe["byte_size"] = 0
    actual = len(json.dumps(probe, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    assert payload["byte_size"] == actual
    assert payload["byte_size"] <= 4000


def test_fb6_tight_budget_degrades_notes_but_keeps_headline():
    report = _report(_positions([140.0, -120.0, 100.0, 90.0, 80.0, 70.0]))
    full = build_state_regret_feedback(report, budget_bytes=4000)
    tight = build_state_regret_feedback(report, budget_bytes=2200)
    assert full["byte_size"] > 2200
    assert tight["byte_size"] <= 2200
    assert len(tight["position_notes"]) < len(full["position_notes"])
    assert tight["cost_structure"] == full["cost_structure"]
    assert tight["limitations"] == full["limitations"]
    assert tight["degeneracy"]["limitation_line"] == full["degeneracy"]["limitation_line"]
    # A budget smaller than the irreducible payload must fail loudly, not silently
    # truncate the headline evidence.
    with pytest.raises(ValueError, match="cannot fit"):
        build_state_regret_feedback(report, budget_bytes=1200)


def test_fb7_payload_is_byte_deterministic():
    report = _report(_positions([40.0, -60.0, 20.0]))
    first = json.dumps(build_state_regret_feedback(report), sort_keys=True)
    second = json.dumps(build_state_regret_feedback(report), sort_keys=True)
    assert first == second


def test_fb8_missing_degeneracy_is_unavailable_not_zero():
    report = _report(_positions([40.0]), degeneracy=False)
    assert summarize_degeneracy(report)["availability"] == "unavailable"
    payload = build_state_regret_feedback(report)
    assert payload["degeneracy"]["availability"] == "unavailable"
    assert payload["degeneracy"]["tied_position_fraction"] is None
    assert payload["degeneracy"]["informative_position_count"] is None
    assert any(item.startswith("degeneracy:") for item in payload["unavailable_evidence"])


def test_fb9_contrast_requires_a_paired_input():
    parent = _report(_positions([40.0]), input_id="I1", fixed_destroy_hash="h1", solver_seed=0)
    child = _report(_positions([30.0]), input_id="I1", fixed_destroy_hash="h2", solver_seed=0)
    with pytest.raises(ValueError, match="paired input"):
        build_paired_contrast(parent, child)


def test_fb10_verdict_uses_makespan_tolerance():
    parent = _report(_positions([40.0]), input_id="I1", fixed_destroy_hash="h1", solver_seed=0)
    tie_child = _report(
        _positions([40.0]), makespan=1000.0, input_id="I1",
        fixed_destroy_hash="h1", solver_seed=0,
    )
    assert build_paired_contrast(parent, tie_child)["verdict"] == "tie"
    worse = _report(
        _positions([40.0]), makespan=1100.0, route_costs=[1100.0, 990.0, 968.0, 957.0],
        input_id="I1", fixed_destroy_hash="h1", solver_seed=0,
    )
    assert build_paired_contrast(parent, worse)["verdict"] == "degraded"


def test_fb11_observations_follow_measured_sign_only():
    parent = _report(_positions([40.0]), input_id="I1", fixed_destroy_hash="h1", solver_seed=0)
    child = _report(
        _positions([40.0]), makespan=1100.0, route_costs=[1100.0, 990.0, 968.0, 957.0],
        shares=(0.90, 0.02, 0.08), input_id="I1", fixed_destroy_hash="h1", solver_seed=0,
    )
    payload = build_paired_contrast(parent, child)
    assert "transfer_down" not in payload["observations"]
    assert payload["delta_mean_transfer"] > 0


def test_fb12_contrast_case_is_small_and_never_asserts_causation():
    parent = _report(_positions([40.0]), input_id="I1", fixed_destroy_hash="h1", solver_seed=0)
    child = _report(
        _positions([40.0]), makespan=950.0, route_costs=[950.0, 900.0, 880.0, 870.0],
        input_id="I1", fixed_destroy_hash="h1", solver_seed=0,
    )
    payload = build_paired_contrast(parent, child)
    assert payload["verdict"] == "improved"
    assert payload["byte_size"] <= 800
    serialized = json.dumps(payload, sort_keys=True).lower()
    for phrase in ("caused by", "due to", "because"):
        assert phrase not in serialized


def _summary():
    return {"count": 4, "eligible_count": 3}


def _operators():
    return [{"operator_id": "R1", "avg_relative_improvement": 0.05}]


def test_pb1_evidence_none_is_byte_identical_to_pre_p2(monkeypatch):
    for rich in (False, True):
        monkeypatch.setattr(prompt_builder, "use_rich_prompts", rich)
        baseline = prompt_builder.build_revision_prompt(
            operator_type="repair", round_id=2,
            previous_summary=_summary(), top_operators=_operators(),
            weak_operators=_operators(),
        )
        with_none = prompt_builder.build_revision_prompt(
            operator_type="repair", round_id=2,
            previous_summary=_summary(), top_operators=_operators(),
            weak_operators=_operators(), evidence=None,
        )
        assert baseline == with_none


def test_pb2_evidence_renders_three_sections_in_fixed_order():
    report = _report(_positions([140.0, -120.0]))
    payload = build_state_regret_feedback(report)
    text = prompt_builder.build_revision_prompt(
        operator_type="repair", round_id=1,
        previous_summary=_summary(), top_operators=_operators(),
        weak_operators=_operators(), evidence=payload,
    )
    structure = text.index("[STRUCTURE]")
    contrast = text.index("[CONTRAST]")
    limits = text.index("[LIMITS]")
    assert structure < contrast < limits
    assert "position_notes (only informative, non-tied):" in text
    assert "of makespan" in text


def test_pb3_unavailable_evidence_keeps_the_heading():
    report = _report(_positions([40.0]), degeneracy=False)
    payload = build_state_regret_feedback(report)
    text = prompt_builder.build_revision_prompt(
        operator_type="repair", round_id=1,
        previous_summary=_summary(), top_operators=_operators(),
        weak_operators=_operators(), evidence=payload,
    )
    assert "[CONTRAST]" in text
    assert "unavailable:" in text
    assert "state evidence degenerate" not in text


def test_pb4_rendering_needs_no_provider(monkeypatch):
    calls = []
    monkeypatch.setattr(
        prompt_builder, "_rich_rev",
        lambda **kwargs: calls.append(kwargs) or "rich-base",
    )
    monkeypatch.setattr(prompt_builder, "use_rich_prompts", True)
    payload = build_state_regret_feedback(_report(_positions([40.0])))
    text = prompt_builder.build_revision_prompt(
        operator_type="destroy", round_id=1,
        previous_summary=_summary(), top_operators=_operators(),
        weak_operators=_operators(), evidence=payload,
    )
    assert len(calls) == 1
    assert text.startswith("rich-base")
    assert "[STRUCTURE]" in text


# --- dataset-level F2 evidence (B2: evolution sees the panel, not one report) ---

from mrta_rect_coverage.llm.operator_evolution.feedback_builder import (
    build_dataset_evidence,
)


def _panel():
    return [
        _report(_positions([-36.0, 36.0, -19.0]), name="R2_T10_0"),
        _report(_positions([0.0, 0.0], tied=4), makespan=2000.0, name="R4_T40_0"),
        _report(_positions([-140.0]), makespan=4000.0, load_excess=800.0, name="HV_GEOM_1"),
    ]


def test_fb13_dataset_payload_is_panel_level_and_within_budget():
    payload = build_dataset_evidence(_panel(), budget_bytes=2500)
    assert payload["feedback_mode"] == "F2_state_v2_dataset"
    assert payload["instance_count"] == 3
    assert payload["dominant_regime"]
    assert set(payload["cost_structure"]) >= {
        "mean_transfer_share",
        "mean_coverage_share",
        "mean_turning_share",
        "mean_load_excess_ratio",
    }
    assert payload["byte_size"] <= 2500
    assert payload["byte_size"] == len(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    )


def test_fb14_dataset_notes_are_masked_and_carry_instance_and_scale():
    payload = build_dataset_evidence(_panel())
    notes = payload["position_notes"]
    assert notes, "expected at least one qualifying position"
    for note in notes:
        assert note["tied_state_count"] == 1
        assert note["mode_gap"] is not None
        assert note["instance"] and note["n_tasks"] is not None
    ratios = [n["gap_ratio_of_makespan"] for n in notes]
    assert ratios == sorted(ratios, reverse=True)


def test_fb15_dataset_payload_has_no_forbidden_field_and_no_placeholder():
    payload = build_dataset_evidence(_panel())
    assert_no_forbidden_fields(payload)
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    assert "{tied_fraction}" not in text
    assert "{informative_fraction}" not in text
    assert "one Exact Route-DP report" not in text


def test_fb16_dataset_payload_is_deterministic():
    first = build_dataset_evidence(_panel())
    second = build_dataset_evidence(_panel())
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_fb17_dataset_payload_rejects_an_empty_panel():
    with pytest.raises(ValueError):
        build_dataset_evidence([])


def test_pb5_dataset_payload_renders_panel_summary_not_per_report_fields():
    payload = build_dataset_evidence(_panel())
    text = prompt_builder.build_revision_prompt(
        operator_type="destroy", round_id=1,
        previous_summary=_summary(), top_operators=_operators(),
        weak_operators=_operators(), evidence=payload,
    )
    assert "panel: 3 instances" in text
    assert "cost shares (panel mean)" in text
    assert "scale: n_tasks" in text
    for section in ("[STRUCTURE]", "[CONTRAST]", "[LIMITS]"):
        assert section in text
    assert text.index("[STRUCTURE]") < text.index("[CONTRAST]") < text.index("[LIMITS]")
    assert "makespan=None" not in text


def test_pb6_dataset_limits_do_not_duplicate_the_tied_sentence():
    payload = build_dataset_evidence(_panel())
    text = prompt_builder.build_revision_prompt(
        operator_type="repair", round_id=1,
        previous_summary=_summary(), top_operators=_operators(),
        weak_operators=_operators(), evidence=payload,
    )
    assert text.count("state evidence is degenerate at") == 0
    assert "read-only aggregation of Exact Route-DP reports" in text
    assert "one Exact Route-DP report" not in text
