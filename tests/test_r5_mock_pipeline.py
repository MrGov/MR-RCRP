from __future__ import annotations

import json
from pathlib import Path

import pytest

from mrta_rect_coverage.llm.operator_evolution.r5_mock_pipeline import (
    FEEDBACK_MODES,
    Counterexample,
    OperatorBehaviorProfile,
    OperatorCandidate,
    OperatorArchive,
    SelectionConfig,
    TrustedFixtureFileProvider,
    TrustedFixtureEntry,
    TrustedFixtureRegistry,
    aggregate_yields,
    build_counterexample_feedback,
    build_r5_split_manifests,
    build_structured_feedback,
    build_trusted_fixtures,
    deploy_operator,
    derive_structural_regimes,
    dp_behavior_distance,
    run_mock_pipeline,
    select_complementary_set,
    validate_split_manifests,
)


def _candidate(
    candidate_id: str = "a",
    *,
    quality: float = 0.5,
    regimes: tuple[str, ...] = ("load:medium",),
    generation: int = 0,
    parents: tuple[str, ...] = (),
    split: str = "selection-validation",
    **status,
) -> OperatorCandidate:
    profile = OperatorBehaviorProfile(
        baseline_makespan=100.0,
        candidate_makespan=100.0 - quality * 10.0,
        absolute_improvement=quality * 10.0,
        relative_improvement=quality,
        success_rate=1.0,
        assignment_change_count=1,
        tasks_moved_out_of_bottleneck=1,
        tasks_moved_into_bottleneck=0,
        bottleneck_relief_mean=quality,
        bottleneck_relief_rate=1.0,
        max_route_cost_change=-quality,
        route_cost_cv_change=-quality / 2,
        dp_state_switch_fraction=0.1 + quality,
        hv_mode_switch_fraction=0.2 + quality / 2,
        entry_corner_switch_fraction=0.1,
        exit_corner_switch_fraction=0.1,
        dp_cascade_count=1,
        dp_cascade_ratio=0.1 + quality / 2,
        travel_time_change=-quality,
        coverage_time_change=-quality / 2,
        turning_time_change=0.0,
        valid_solution_rate=1.0,
        runtime_error_rate=0.0,
        timeout_rate=0.0,
        fallback_rate=0.0,
        contract_rejection_rate=0.0,
        candidate_runtime=10.0,
        route_dp_evaluation_count=3,
        cache_hit_rate=0.5,
        regime_context={"task_robot_ratio": 5.0, "spatial_dispersion": 2.0},
    )
    return OperatorCandidate(
        candidate_id=candidate_id,
        operator_type="repair",
        source_hash=f"hash-{candidate_id}",
        generation=generation,
        generation_seed=7,
        parent_operator_ids=parents,
        parent_source_hashes=tuple(f"hash-{parent}" for parent in parents),
        prompt_version="r5-test-v1",
        creation_mode="scripted_fixture",
        split=split,
        profile=profile,
        structural_regimes=regimes,
        syntax_valid=status.pop("syntax_valid", True),
        contract_valid=status.pop("contract_valid", True),
        feasible=status.pop("feasible", True),
        deployable=status.pop("deployable", True),
        timeout_heavy=status.pop("timeout_heavy", False),
        fallback_heavy=status.pop("fallback_heavy", False),
        runtime_acceptable=status.pop("runtime_acceptable", True),
        **status,
    )


def test_profile_is_versioned_and_contains_exact_dp_fields() -> None:
    profile = _candidate().profile
    payload = profile.to_dict()
    assert payload["schema_version"] == "r5-operator-behavior-v1"
    assert payload["dp_state_switch_fraction"] == pytest.approx(0.6)
    assert payload["dp_cascade_ratio"] > 0
    assert "travel_time_change" in payload


@pytest.mark.parametrize("mode", FEEDBACK_MODES)
def test_feedback_modes_have_explicit_evidence_boundaries(mode: str) -> None:
    rows = [_candidate("a"), _candidate("b", quality=0.2)]
    payload = build_structured_feedback(rows, mode=mode)
    assert payload["schema_version"] == "r5-structured-feedback-v1"
    assert payload["mode"] == mode
    encoded = json.dumps(payload, sort_keys=True)
    if mode == "F0":
        assert "dp_state_switch_fraction" not in encoded
        assert "counterexamples" not in payload
    elif mode == "F1":
        assert "top_operators" in payload and "weak_operators" in payload
        assert "dp_state_switch_fraction" not in encoded
    elif mode == "F2":
        assert "behavior_profiles" in payload
        assert "dp_state_switch_fraction" in encoded
        assert "counterexamples" not in payload
    else:
        assert "behavior_profiles" in payload and "counterexamples" in payload


def test_archive_requires_real_parent_and_retains_elite() -> None:
    archive = OperatorArchive()
    parent = _candidate("parent")
    archive.add(parent)
    child = _candidate("child", generation=1, parents=("parent",))
    archive.add(child)
    archive.retain_elite("parent", generation=0)
    assert archive.elites_for_generation(0) == ("parent",)
    assert archive.get("child").parent_operator_ids == ("parent",)
    with pytest.raises(ValueError, match="parent"):
        archive.add(_candidate("orphan", generation=1, parents=("missing",)))


def test_eligibility_and_quality_floor_are_hard_gates() -> None:
    rows = [
        _candidate("good", quality=0.8, regimes=("load:high",)),
        _candidate("weak", quality=0.1),
        _candidate("invalid", quality=0.9, contract_valid=False),
        _candidate("timeout", quality=0.9, timeout_heavy=True),
    ]
    result = select_complementary_set(rows, SelectionConfig(minimum_quality_floor=0.5, set_size=2))
    assert [row.candidate_id for row in result.selected] == ["good"]
    assert any("invalid" in line and "ineligible" in line for line in result.trace)
    assert any("weak" in line and "quality floor" in line for line in result.trace)


def test_profile_failure_rates_are_stage_one_reliability_gates() -> None:
    candidate = _candidate("runtime-failure")
    candidate.profile.runtime_error_rate = 0.1
    result = select_complementary_set([candidate], SelectionConfig(set_size=1))
    assert result.selected == []
    assert "runtime-error" in " ".join(result.trace)


def test_lexicographic_selection_uses_regime_then_dp_tie_break_and_k1_anchor() -> None:
    anchor = _candidate("anchor", quality=0.9, regimes=("load:medium",))
    regime = _candidate("regime", quality=0.5, regimes=("hv:high",))
    dp_a = _candidate("dp-a", quality=0.5, regimes=("hv:high",))
    dp_b = _candidate("dp-b", quality=0.5, regimes=("hv:high",))
    dp_b.profile.dp_state_switch_fraction = 0.0
    one = select_complementary_set([anchor, regime], SelectionConfig(set_size=1))
    assert [item.candidate_id for item in one.selected] == ["anchor"]
    result = select_complementary_set([anchor, dp_a, dp_b], SelectionConfig(set_size=2))
    assert [item.candidate_id for item in result.selected] == ["anchor", "dp-b"]
    assert any("marginal" in line for line in result.trace)


def test_deployment_policies_are_bounded_and_deterministic() -> None:
    rows = [_candidate("a", quality=0.2), _candidate("b", quality=0.8, regimes=("hv:high",))]
    assert deploy_operator(rows, policy="P0").candidate_id == "b"
    assert deploy_operator(rows, policy="P1", seed=1).candidate_id in {"a", "b"}
    assert deploy_operator(rows, policy="P2", instance_regimes=("hv:high",)).candidate_id == "b"
    with pytest.raises(ValueError):
        deploy_operator(rows, policy="P3")


def test_counterexample_modes_preserve_structured_payload_without_execution() -> None:
    item = Counterexample(
        failure_axis="optimization",
        failure_code="bottleneck_regression",
        comparator="baseline",
        regime_context={"load_pressure": "high"},
        structural_evidence={"tasks_moved_out_of_bottleneck": -1},
        expected_invariant="bottleneck relief must not regress",
    )
    none = build_counterexample_feedback(item, mode="C0")
    assert none["mode"] == "C0"
    assert none["schema_version"] == "r5-counterexample-v1"
    assert "counterexample" not in none
    structured = build_counterexample_feedback(item, mode="C2")
    assert structured["counterexample"]["failure_code"] == "bottleneck_regression"
    shuffled = build_counterexample_feedback(item, mode="C3")
    assert shuffled["mode"] == "C3" and "counterexample" in shuffled


def test_split_manifests_are_fresh_disjoint_and_final_locked() -> None:
    manifests = build_r5_split_manifests()
    validate_split_manifests(manifests)
    ids = [entry for manifest in manifests for entry in manifest.entry_ids]
    assert len(ids) == len(set(ids))
    assert all(manifest.split != "final-test" for manifest in manifests)
    with pytest.raises(ValueError, match="diagnostic-heldout-consumed"):
        validate_split_manifests(manifests + build_r5_split_manifests(consumed=True))


def test_budget_and_yield_metrics_are_equal_budget() -> None:
    fixtures = build_trusted_fixtures()
    result = run_mock_pipeline(fixtures[:4], generations=2, set_size=2)
    assert result.budget_ledger.assert_equal_budget()
    yields = aggregate_yields(result.archive.records())
    assert yields["syntax_valid_yield"] == 1.0
    assert 0.0 < yields["quality_conditioned_yield"] <= 1.0
    assert len(result.budget_ledger.evaluations) == 2 * 4
    assert all(address.instance_id == "r5-fixture-instance-001" for address in result.budget_ledger.evaluations)


def test_trusted_file_provider_is_dry_run_and_never_imports_python(tmp_path: Path) -> None:
    manifest = tmp_path / "fixtures.json"
    manifest.write_text(json.dumps({"schema_version": "r5-fixture-manifest-v1", "fixtures": [
        {"fixture_id": "safe", "operator_type": "repair", "source_hash": "hash-safe"}
    ]}), encoding="utf-8")
    (tmp_path / "evil.py").write_text("raise RuntimeError('must not execute')\n", encoding="utf-8")
    fixture_path = tmp_path / "safe.json"
    fixture_path.write_text("{}", encoding="utf-8")
    registry = TrustedFixtureRegistry(tmp_path, [TrustedFixtureEntry(
        "safe", "safe.json", __import__("hashlib").sha256(fixture_path.read_bytes()).hexdigest(), "json", "r5-fixture-manifest-v1"
    )])
    manifest.write_text(json.dumps({"schema_version": "r5-fixture-manifest-v1", "fixtures": [
        {"fixture_id": "safe", "operator_type": "repair", "source_hash": registry.resolve("safe").expected_sha256}
    ]}), encoding="utf-8")
    provider = TrustedFixtureFileProvider(manifest, registry=registry, dry_run=True)
    assert provider.load_fixture_ids() == ["safe"]
    assert provider.executed_source_paths == []
    with pytest.raises(ValueError, match="dry_run"):
        TrustedFixtureFileProvider(manifest, registry=registry, dry_run=False)


def test_intrinsic_regime_binning_and_dp_distance_are_deterministic() -> None:
    regimes = derive_structural_regimes({
        "task_robot_ratio": 10.0,
        "heavy_task_ratio": 2.0,
        "spatial_dispersion": 8.0,
        "hv_gap": 2.0,
        "travel_coverage_ratio": 1.5,
    })
    assert regimes == ("load:high", "heavy:high", "spatial:dispersed", "hv:high", "travel-dominated")
    left, right = _candidate("left"), _candidate("right", quality=0.2)
    assert dp_behavior_distance(left, left) == 0.0
    assert dp_behavior_distance(left, right) > 0.0


def test_output_artifacts_include_archive_profiles_trace_and_budget(tmp_path: Path) -> None:
    result = run_mock_pipeline(build_trusted_fixtures(), generations=2, set_size=2, output_dir=tmp_path)
    for relative in (
        "metadata.json", "evolution_runs.jsonl", "candidate_archive.jsonl",
        "behavior_profiles.jsonl", "budget_ledger.csv", "yield_summary.json",
        "operator_sets.json", "selection_traces/selection.json",
    ):
        assert (tmp_path / relative).is_file()
    assert result.selection_trace


def test_end_to_end_scenarios_a_to_d() -> None:
    result = run_mock_pipeline(build_trusted_fixtures(), generations=2, set_size=2)
    assert result.scenarios == {"A": True, "B": True, "C": True, "D": True}
    assert result.selected_set
    assert result.output_contract["real_provider_used"] is False
    assert result.output_contract["untrusted_candidate_executed"] is False
