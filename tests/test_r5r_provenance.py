from __future__ import annotations

import json
import hashlib
from dataclasses import replace
import pytest

from mrta_rect_coverage.experiments.r3_diagnostics import state_chain_diff
from mrta_rect_coverage.llm.operator_evolution import r5_mock_pipeline as r5


OperatorBehaviorProfile = r5.OperatorBehaviorProfile


def _profile() -> OperatorBehaviorProfile:
    return OperatorBehaviorProfile(
        baseline_makespan=100.0, candidate_makespan=90.0,
        absolute_improvement=10.0, relative_improvement=0.1,
        success_rate=1.0, assignment_change_count=1,
        tasks_moved_out_of_bottleneck=1, tasks_moved_into_bottleneck=0,
        bottleneck_relief_mean=1.0, bottleneck_relief_rate=1.0,
        max_route_cost_change=-1.0, route_cost_cv_change=0.0,
        # Deliberately false self-declared DP metrics.
        dp_state_switch_fraction=0.99, hv_mode_switch_fraction=0.99,
        entry_corner_switch_fraction=0.99, exit_corner_switch_fraction=0.99,
        dp_cascade_count=99, dp_cascade_ratio=0.99,
        travel_time_change=0.0, coverage_time_change=0.0,
        turning_time_change=0.0, valid_solution_rate=1.0,
        runtime_error_rate=0.0, timeout_rate=0.0, fallback_rate=0.0,
        contract_rejection_rate=0.0, candidate_runtime=1.0,
        route_dp_evaluation_count=1, cache_hit_rate=0.0,
    )


def test_r5_profile_uses_canonical_r3_state_chain_metrics_not_fixture_values() -> None:
    before = {
        1: ("H", "LB", "RT"),
        2: ("H", "LB", "RT"),
        3: ("V", "LT", "RB"),
    }
    after = {
        1: ("V", "LB", "RT"),  # direct task: mode switch
        2: ("H", "RB", "RT"),  # indirect task: entry switch
        3: ("V", "LT", "LB"),  # indirect task: exit switch
    }
    expected = state_chain_diff(
        before, after,
        affected_task_ids={1, 2, 3},
        directly_moved_task_ids={1},
    )
    bound = r5.bind_dp_behavior_metrics(
        _profile(), before=before, after=after,
        affected_task_ids={1, 2, 3}, directly_moved_task_ids={1},
    )
    assert bound.dp_state_switch_fraction == pytest.approx(expected["state_changed_fraction"])
    assert bound.hv_mode_switch_fraction == pytest.approx(expected["mode_switch_fraction"])
    assert bound.entry_corner_switch_fraction == pytest.approx(
        expected["entry_corner_changed_count"] / 3
    )
    assert bound.exit_corner_switch_fraction == pytest.approx(
        expected["exit_corner_changed_count"] / 3
    )
    assert bound.dp_cascade_count == expected["cascade_count"]
    assert bound.dp_cascade_ratio == pytest.approx(expected["dp_cascade_ratio"])
    assert bound.dp_cascade_ratio != pytest.approx(0.99)


def test_intrinsic_regime_mapping_is_versioned_and_deterministic() -> None:
    features = {
        "task_robot_ratio": 3.0,
        "heavy_task_ratio": 1.0,
        "spatial_dispersion": 2.0,
        "hv_gap": 0.2,
        "travel_coverage_ratio": 0.5,
    }
    first = r5.derive_structural_regimes(features)
    second = r5.derive_structural_regimes(dict(features))
    assert first == second
    assert first == (
        "load:low", "heavy:low", "spatial:compact", "hv:low", "coverage-dominated"
    )


def test_candidate_declared_regime_cannot_override_intrinsic_regime() -> None:
    features = {
        "task_robot_ratio": 3.0,
        "heavy_task_ratio": 1.0,
        "spatial_dispersion": 2.0,
        "hv_gap": 0.2,
        "travel_coverage_ratio": 0.5,
    }
    profile = _profile()
    profile.regime_context = features
    with pytest.raises(ValueError, match="intrinsic structural regimes"):
        r5.OperatorCandidate(
            candidate_id="spoofed-regime",
            operator_type="repair",
            source_hash="a" * 64,
            generation=0,
            generation_seed=0,
            parent_operator_ids=(),
            prompt_version="r5r-test-v1",
            creation_mode="scripted_fixture",
            split="selection-validation",
            profile=profile,
            structural_regimes=("hv:high",),
        )


def test_lineage_requires_parent_source_hash_binding() -> None:
    parent = r5.build_trusted_fixtures()[0]
    archive = r5.OperatorArchive()
    archive.add(parent)
    child = r5.OperatorCandidate(
        candidate_id="child-with-wrong-parent-hash",
        operator_type=parent.operator_type,
        source_hash="b" * 64,
        generation=1,
        generation_seed=1,
        parent_operator_ids=(parent.candidate_id,),
        parent_source_hashes=("wrong-parent-hash",),
        prompt_version="r5r-test-v1",
        creation_mode="revision",
        split=parent.split,
        profile=parent.profile,
        structural_regimes=parent.structural_regimes,
    )
    with pytest.raises(ValueError, match="parent source hash"):
        archive.add(child)


def test_replaced_parent_source_under_same_id_is_rejected() -> None:
    parent = r5.build_trusted_fixtures()[0]
    archive = r5.OperatorArchive()
    archive.add(parent)
    archive._records[parent.candidate_id] = replace(parent, source_hash="d" * 64)
    child = replace(
        parent,
        candidate_id="child-after-parent-replacement",
        source_hash="e" * 64,
        generation=1,
        generation_seed=1,
        parent_operator_ids=(parent.candidate_id,),
        parent_source_hashes=(parent.source_hash,),
        creation_mode="revision",
    )
    with pytest.raises(ValueError, match="parent source hash"):
        archive.add(child)


def test_elite_retention_event_requires_real_parent_reuse() -> None:
    result = r5.run_mock_pipeline(r5.build_trusted_fixtures(), generations=2, set_size=2)
    assert result.elite_retention_events
    assert r5.validate_elite_retention_events(result.archive, result.elite_retention_events)
    false_event = r5.EliteRetentionEvent(
        evolution_run_id="r5-mock-run-000",
        generation_from=0,
        generation_to=1,
        elite_candidate_id="not-reused",
        elite_source_hash="c" * 64,
        retention_mode="selected_as_parent",
    )
    with pytest.raises(ValueError, match="elite"):
        r5.validate_elite_retention_events(result.archive, [false_event])


def test_evaluation_hierarchy_is_persisted_with_deterministic_identity(tmp_path) -> None:
    result = r5.run_mock_pipeline(r5.build_trusted_fixtures()[:2], generations=2, set_size=1, output_dir=tmp_path)
    records = [
        r5.EvaluationAddress.from_dict(json.loads(line))
        for line in (tmp_path / "evaluation_records.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert records
    assert all(record.evaluation_id for record in records)
    assert all(record.instance_replicate_id for record in records)
    assert all(record.evolution_run_id and record.candidate_id for record in records)
    aggregate = r5.aggregate_evaluation_results(records)
    assert aggregate[records[0].candidate_id]["trial_count"] == 1.0
    assert aggregate[records[0].candidate_id]["mean_relative_improvement"] == pytest.approx(
        records[0].result["relative_improvement"]
    )
    with pytest.raises(ValueError, match="duplicate evaluation"):
        result.budget_ledger.record_evaluation(records[0])


def test_file_provider_requires_registered_fixture_and_exact_hash(tmp_path) -> None:
    fixture_root = tmp_path / "trusted"
    fixture_root.mkdir()
    fixture = fixture_root / "safe.json"
    fixture.write_text('{"fixture_id":"safe"}\n', encoding="utf-8")
    digest = hashlib.sha256(fixture.read_bytes()).hexdigest()
    registry = r5.TrustedFixtureRegistry(
        fixture_root,
        [r5.TrustedFixtureEntry(
            fixture_id="safe", relative_path="safe.json", expected_sha256=digest,
            fixture_type="json", schema_version="r5-fixture-manifest-v1",
        )],
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "schema_version": "r5-fixture-manifest-v1",
        "fixtures": [{"fixture_id": "safe", "operator_type": "repair", "source_hash": digest}],
    }), encoding="utf-8")
    provider = r5.TrustedFixtureFileProvider(manifest, registry=registry, dry_run=True)
    assert provider.load_fixture_ids() == ["safe"]
    fixture.write_text('{"fixture_id":"tampered"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="hash"):
        provider.load_fixture_ids()


def test_file_provider_rejects_unregistered_substitution_and_traversal(tmp_path) -> None:
    root = tmp_path / "trusted"
    root.mkdir()
    safe = root / "safe.json"
    safe.write_text("{}", encoding="utf-8")
    digest = hashlib.sha256(safe.read_bytes()).hexdigest()
    registry = r5.TrustedFixtureRegistry(root, [r5.TrustedFixtureEntry(
        "safe", "safe.json", digest, "json", "r5-fixture-manifest-v1"
    )])
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="registered"):
        registry.resolve("unknown")
    with pytest.raises(ValueError, match="confined"):
        registry.validate_path("../outside.json")
