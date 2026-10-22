from __future__ import annotations

import builtins
import copy
import importlib
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


CORE_MODULE = "mrta_rect_coverage.experiments.pilot_manifest_prevalidator"
CONTRACT_MODULE = "mrta_rect_coverage.experiments.pilot_contracts"
INTEGRITY_MODULE = "mrta_rect_coverage.experiments.pilot_integrity"


def _module(name: str) -> ModuleType:
    return importlib.import_module(name)


def _core() -> ModuleType:
    try:
        return _module(CORE_MODULE)
    except ModuleNotFoundError as exc:
        if exc.name == CORE_MODULE:
            pytest.fail(
                "Phase 6B-T3 RED: pure-object pilot manifest pre-validator "
                "core is not implemented"
            )
        raise


def _assert_valid(result) -> None:
    assert result.valid is True
    assert tuple(result.rejection_reasons) == ()


def _assert_core_valid(result) -> None:
    _assert_valid(result)
    assert result.status == "valid"
    assert result.result_scope == "pure_object_prevalidation"
    assert result.schema_valid is True
    assert result.integrity_valid is True
    assert result.failure_layer is None
    assert result.execution_authorized is False
    assert result.gate_p2_closed is False


def _assert_core_rejected(result, *, failure_layer: str) -> None:
    assert result.valid is False
    assert tuple(result.rejection_reasons)
    assert result.status == "rejected"
    assert result.result_scope == "pure_object_prevalidation"
    assert result.failure_layer == failure_layer
    assert result.execution_authorized is False
    assert result.gate_p2_closed is False


def _pilot_family_matrix() -> dict:
    return {
        "schema_version": "pilot-family-matrix-v1",
        "matrix_scope": "pilot",
        "families": [
            {
                "family_id": "pilot-family-001",
                "robots": 2,
                "tasks": 6,
            }
        ],
    }


def _pilot_split_rule() -> dict:
    return {
        "schema_version": "pilot-split-rule-v1",
        "matrix_scope": "pilot",
        "assignments": {"pilot-family-001": "train"},
    }


def _valid_objects() -> tuple[dict, dict, dict]:
    integrity = _module(INTEGRITY_MODULE)
    family_matrix = _pilot_family_matrix()
    split_rule = _pilot_split_rule()
    family_hash = integrity.compute_object_hash(family_matrix)
    split_hash = integrity.compute_object_hash(split_rule)
    manifest = {
        "manifest_type": "pilot_split_manifest",
        "schema_version": "pilot-manifest-schema-v1",
        "manifest_version": "pilot-manifest-v1",
        "manifest_id": "pilot-manifest-core-001",
        "manifest_scope": "pilot_nonformal",
        "matrix_scope": "pilot",
        "objective_version": "objective_v1_prototype",
        "artifact_promotion_allowed": False,
        "formal_identity_version": "not_applicable",
        "pilot_source_reference": None,
        # Schema evidence only.  The pure-object core must not present this
        # artifact claim as a verified raw-byte manifest hash.
        "manifest_hash": "0" * 64,
        "instance_count": 1,
        "family_count": 1,
        "strata_counts": {"small": 1},
        "exclusion_rule_version": "pilot-exclusion-v1",
        "replacement_seed_rule_version": "pilot-replacement-v1",
        "generator_code_hash": "1" * 64,
        "instance_schema_version": "pilot-instance-v1",
        "family_matrix_hash": family_hash,
        "split_assignment_rule_hash": split_hash,
        "parent_manifest_hash": "",
        "contamination_status": "clean",
        "created_at": "2026-08-14T00:00:00Z",
        "approved_by": "pilot-reviewer",
        "notes": "pure-object prevalidation fixture",
        "audit_history": [
            {
                "event_id": "pilot-event-001",
                "actor_id": "pilot-reviewer",
                "action": "fixture_created",
                "created_at": "2026-08-14T00:00:00Z",
            }
        ],
        "instances": [
            {
                "manifest_version": "pilot-manifest-v1",
                "manifest_scope": "pilot_nonformal",
                "matrix_scope": "pilot",
                "objective_version": "objective_v1_prototype",
                "instance_id": "4" * 64,
                "family_id": "pilot-family-001",
                "split": "train",
                "size_stratum": "small",
                "distribution_stratum": "D1",
                "robots": 2,
                "tasks": 6,
                "sweep_width": 1.0,
                "sweep_speed": 1.0,
                "travel_speed": 2.0,
                "turning_time": 0.5,
                "generation_rule_version": "pilot-generator-v1",
                "generation_seed": 11,
                "replicate_id": 0,
                "file_path": "pilot_train/R2_T6_0.txt",
                "file_hash": "5" * 64,
                "family_matrix_hash": family_hash,
                "split_assignment_rule_hash": split_hash,
                "artifact_promotion_allowed": False,
                "formal_identity_version": "not_applicable",
                "pilot_source_reference": None,
                "contamination_owner": "pilot-reviewer",
                "lockbox_status": "not_applicable",
                "created_at": "2026-08-14T00:00:00Z",
                "approved_by": "pilot-reviewer",
                "notes": "",
            }
        ],
    }
    return manifest, family_matrix, split_rule


def _validate(core: ModuleType, manifest: dict, matrix: dict, split_rule: dict):
    return core.validate_pilot_manifest_core(
        manifest,
        pilot_family_matrix_obj=matrix,
        pilot_split_rule_obj=split_rule,
    )


def _build(core: ModuleType, manifest: dict, matrix: dict, split_rule: dict) -> dict:
    result = core.build_pilot_prevalidation_result(
        manifest,
        pilot_family_matrix_obj=matrix,
        pilot_split_rule_obj=split_rule,
    )
    assert type(result) is dict
    return result


def _verify(
    core: ModuleType,
    manifest: dict,
    result: dict,
    matrix: dict,
    split_rule: dict,
):
    return core.verify_pilot_prevalidation_result(
        manifest,
        result,
        pilot_family_matrix_obj=matrix,
        pilot_split_rule_obj=split_rule,
    )


def test_in_memory_baseline_satisfies_existing_schema_and_integrity() -> None:
    """Control: RED failures must not come from malformed in-memory fixtures."""

    manifest, family_matrix, split_rule = _valid_objects()

    _assert_valid(
        _module(CONTRACT_MODULE).validate_pilot_manifest_schema(manifest)
    )
    _assert_valid(
        _module(INTEGRITY_MODULE).verify_pilot_scoped_hash_binding(
            manifest, family_matrix, split_rule
        )
    )


def test_core_calls_schema_before_scoped_integrity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    core = _core()
    manifest, family_matrix, split_rule = _valid_objects()
    calls: list[str] = []

    def schema_validator(_manifest: dict):
        calls.append("schema")
        return SimpleNamespace(valid=True, rejection_reasons=())

    def integrity_validator(_manifest: dict, _matrix: dict, _split: dict):
        calls.append("integrity")
        return SimpleNamespace(valid=True, rejection_reasons=())

    monkeypatch.setattr(core, "validate_pilot_manifest_schema", schema_validator)
    monkeypatch.setattr(
        core, "verify_pilot_scoped_hash_binding", integrity_validator
    )

    _assert_core_valid(_validate(core, manifest, family_matrix, split_rule))
    assert calls == ["schema", "integrity"]


@pytest.mark.parametrize(
    "case",
    [
        "unknown_field",
        "wrong_json_type",
        "manifest_scope_formal_train",
        "manifest_scope_formal_dev",
        "manifest_scope_formal_final_test",
        "matrix_scope_formal",
        "artifact_promotion_true",
        "split_formal_train",
        "split_formal_dev",
        "split_formal_final_test",
    ],
)
def test_schema_rejection_short_circuits_integrity(
    case: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    core = _core()
    manifest, family_matrix, split_rule = _valid_objects()
    if case == "unknown_field":
        manifest["unknown_field"] = "reject"
    elif case == "wrong_json_type":
        manifest["instances"] = "not-an-array"
    elif case.startswith("manifest_scope_"):
        manifest["manifest_scope"] = case.removeprefix("manifest_scope_")
    elif case == "matrix_scope_formal":
        manifest["matrix_scope"] = "formal"
    elif case == "artifact_promotion_true":
        manifest["artifact_promotion_allowed"] = True
    else:
        manifest["instances"][0]["split"] = case.removeprefix("split_")

    integrity_called = False

    def forbidden_integrity(*_args, **_kwargs):
        nonlocal integrity_called
        integrity_called = True
        raise AssertionError("integrity must not run after schema rejection")

    monkeypatch.setattr(
        core, "verify_pilot_scoped_hash_binding", forbidden_integrity
    )

    result = _validate(core, manifest, family_matrix, split_rule)

    _assert_core_rejected(result, failure_layer="schema")
    assert result.schema_valid is False
    assert result.integrity_valid is None
    assert integrity_called is False


@pytest.mark.parametrize(
    "case",
    [
        "family_matrix_hash_mismatch",
        "split_assignment_rule_hash_mismatch",
        "nested_formal_train_leakage",
        "unsupported_integer",
        "hidden_final_test_path",
    ],
)
def test_schema_valid_integrity_failure_is_structured_rejection(case: str) -> None:
    core = _core()
    manifest, family_matrix, split_rule = _valid_objects()
    if case == "family_matrix_hash_mismatch":
        manifest["family_matrix_hash"] = "a" * 64
        manifest["instances"][0]["family_matrix_hash"] = "a" * 64
    elif case == "split_assignment_rule_hash_mismatch":
        manifest["split_assignment_rule_hash"] = "b" * 64
        manifest["instances"][0]["split_assignment_rule_hash"] = "b" * 64
    elif case == "nested_formal_train_leakage":
        manifest["instances"][0]["notes"] = "formal_train"
    elif case == "unsupported_integer":
        manifest["instances"][0]["generation_seed"] = 1 << 68
    else:
        manifest["instances"][0]["file_path"] = (
            "pilot/formal_final_test/hidden.txt"
        )

    schema_result = _module(CONTRACT_MODULE).validate_pilot_manifest_schema(
        manifest
    )
    _assert_valid(schema_result)

    result = _validate(core, manifest, family_matrix, split_rule)

    _assert_core_rejected(result, failure_layer="integrity")
    assert result.schema_valid is True
    assert result.integrity_valid is False


def test_valid_pure_object_manifest_returns_inert_core_result() -> None:
    core = _core()
    manifest, family_matrix, split_rule = _valid_objects()

    result = _validate(core, manifest, family_matrix, split_rule)

    _assert_core_valid(result)


def test_prevalidation_result_binds_only_canonical_in_memory_objects() -> None:
    core = _core()
    integrity = _module(INTEGRITY_MODULE)
    manifest, family_matrix, split_rule = _valid_objects()

    result = _build(core, manifest, family_matrix, split_rule)

    assert result["status"] == "valid"
    assert result["result_scope"] == "pure_object_prevalidation"
    assert result["manifest_object_hash"] == integrity.compute_object_hash(manifest)
    assert result["pilot_family_matrix_object_hash"] == integrity.compute_object_hash(
        family_matrix
    )
    assert result["pilot_split_rule_object_hash"] == integrity.compute_object_hash(
        split_rule
    )
    assert result["canonicalization_algorithm"] == "RFC8785-JCS"
    assert result["canonicalization_version"] == "jcs-v1-safe-int-domain"
    assert result["gate_p2_closed"] is False
    assert result["execution_authorized"] is False


def test_prevalidation_result_does_not_impersonate_full_validation_receipt() -> None:
    core = _core()
    manifest, family_matrix, split_rule = _valid_objects()

    result = _build(core, manifest, family_matrix, split_rule)

    forbidden_fields = {
        "receipt_schema_version",
        "receipt_type",
        "validation_receipt_id",
        "manifest_hash",
        "raw_bytes_manifest_hash",
        "canonical_manifest_hash",
        "instance_file_hash_verified",
        "path_normalized",
        "file_identity_checked",
        "accepted_execution",
        "runner_receipt_id",
        "scheduled_run_id",
        "scheduled_run_ids",
        "provider_invocation_result",
        "candidate_execution_result",
    }
    assert forbidden_fields.isdisjoint(result)
    assert result["status"] in {"valid", "rejected"}
    assert result["status"] != "validation_valid"
    assert "prevalidation_result_id" in result


@pytest.mark.parametrize(
    "changed_input",
    ["manifest", "family_matrix", "split_rule", "result_evidence"],
)
def test_prevalidation_binding_rejects_post_build_mutation(
    changed_input: str,
) -> None:
    core = _core()
    manifest, family_matrix, split_rule = _valid_objects()
    result = _build(core, manifest, family_matrix, split_rule)
    changed_manifest = copy.deepcopy(manifest)
    changed_matrix = copy.deepcopy(family_matrix)
    changed_split = copy.deepcopy(split_rule)
    changed_result = copy.deepcopy(result)
    if changed_input == "manifest":
        changed_manifest["notes"] = "changed after prevalidation"
    elif changed_input == "family_matrix":
        changed_matrix["families"][0]["tasks"] = 7
    elif changed_input == "split_rule":
        changed_split["assignments"]["pilot-family-001"] = "dev"
    else:
        changed_result["manifest_object_hash"] = "f" * 64

    verification = _verify(
        core,
        changed_manifest,
        changed_result,
        changed_matrix,
        changed_split,
    )

    assert verification.valid is False
    assert tuple(verification.rejection_reasons)


@pytest.mark.parametrize("forbidden_status", ["validation_valid", "validation_rejected"])
def test_prevalidation_status_rejects_full_validator_style_values(
    forbidden_status: str,
) -> None:
    core = _core()
    manifest, family_matrix, split_rule = _valid_objects()
    result = _build(core, manifest, family_matrix, split_rule)
    result["status"] = forbidden_status

    verification = _verify(core, manifest, result, family_matrix, split_rule)

    assert verification.valid is False
    assert tuple(verification.rejection_reasons)


def _forbid_file_access(*_args, **_kwargs):
    raise AssertionError("pure-object prevalidation must not access a path")


def _block_file_reads(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(builtins, "open", _forbid_file_access)
    monkeypatch.setattr(Path, "open", _forbid_file_access)
    monkeypatch.setattr(Path, "read_bytes", _forbid_file_access)
    monkeypatch.setattr(Path, "read_text", _forbid_file_access)


def test_valid_manifest_file_path_is_never_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    core = _core()
    manifest, family_matrix, split_rule = _valid_objects()
    _block_file_reads(monkeypatch)

    _assert_core_valid(_validate(core, manifest, family_matrix, split_rule))


def test_final_test_path_marker_is_rejected_without_file_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    core = _core()
    manifest, family_matrix, split_rule = _valid_objects()
    manifest["instances"][0]["file_path"] = (
        "formal_final_test/locked-instance.txt"
    )
    _block_file_reads(monkeypatch)

    result = _validate(core, manifest, family_matrix, split_rule)

    _assert_core_rejected(result, failure_layer="integrity")


def test_core_never_calls_execution_or_provider_symbols(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    core = _core()
    manifest, family_matrix, split_rule = _valid_objects()
    calls: list[str] = []

    def forbidden_capability(name: str):
        def invoke(*_args, **_kwargs):
            calls.append(name)
            raise AssertionError(f"prevalidation must not invoke {name}")

        return invoke

    for symbol in (
        "invoke_provider",
        "run_candidate",
        "run_pilot",
        "schedule_runner",
    ):
        monkeypatch.setattr(
            core, symbol, forbidden_capability(symbol), raising=False
        )

    _assert_core_valid(_validate(core, manifest, family_matrix, split_rule))
    assert calls == []


def _schema_invalid_manifest(marker: str) -> tuple[dict, dict, dict]:
    manifest, family_matrix, split_rule = _valid_objects()
    manifest["unknown_field"] = marker
    return manifest, family_matrix, split_rule


def _integrity_invalid_manifest(marker: str) -> tuple[dict, dict, dict]:
    manifest, family_matrix, split_rule = _valid_objects()
    manifest["family_matrix_hash"] = "a" * 64
    manifest["instances"][0]["family_matrix_hash"] = "a" * 64
    manifest["notes"] = marker
    return manifest, family_matrix, split_rule


def _assert_lowercase_sha256(value) -> None:
    assert type(value) is str
    assert len(value) == 64
    assert all(character in "0123456789abcdef" for character in value)


def test_schema_rejected_result_cannot_verify_different_invalid_manifest() -> None:
    core = _core()
    manifest_a, family_matrix, split_rule = _schema_invalid_manifest("invalid-a")
    manifest_b, _, _ = _schema_invalid_manifest("invalid-b")
    result_a = _build(core, manifest_a, family_matrix, split_rule)
    result_b = _build(core, manifest_b, family_matrix, split_rule)

    assert result_a["status"] == "rejected"
    assert result_a["rejection_reasons"] == result_b["rejection_reasons"]
    assert result_a["execution_authorized"] is False
    assert result_a["gate_p2_closed"] is False
    assert "validation_receipt_id" not in result_a
    assert "runner_receipt_id" not in result_a

    verification = _verify(
        core, manifest_b, result_a, family_matrix, split_rule
    )

    assert verification.valid is False
    assert tuple(verification.rejection_reasons)


def test_schema_rejected_result_id_changes_with_invalid_manifest_content() -> None:
    core = _core()
    manifest_a, family_matrix, split_rule = _schema_invalid_manifest("invalid-a")
    manifest_b, _, _ = _schema_invalid_manifest("invalid-b")

    result_a = _build(core, manifest_a, family_matrix, split_rule)
    result_b = _build(core, manifest_b, family_matrix, split_rule)

    assert result_a["rejection_reasons"] == result_b["rejection_reasons"]
    assert result_a["prevalidation_result_id"] != result_b["prevalidation_result_id"]


def test_integrity_rejected_result_cannot_verify_different_invalid_manifest() -> None:
    core = _core()
    manifest_a, family_matrix, split_rule = _integrity_invalid_manifest("invalid-a")
    manifest_b, _, _ = _integrity_invalid_manifest("invalid-b")
    result_a = _build(core, manifest_a, family_matrix, split_rule)
    result_b = _build(core, manifest_b, family_matrix, split_rule)

    assert result_a["status"] == "rejected"
    assert result_a["rejection_reasons"] == result_b["rejection_reasons"]

    verification = _verify(
        core, manifest_b, result_a, family_matrix, split_rule
    )

    assert verification.valid is False
    assert tuple(verification.rejection_reasons)


def test_integrity_rejected_result_id_changes_with_invalid_manifest_content() -> None:
    core = _core()
    manifest_a, family_matrix, split_rule = _integrity_invalid_manifest("invalid-a")
    manifest_b, _, _ = _integrity_invalid_manifest("invalid-b")

    result_a = _build(core, manifest_a, family_matrix, split_rule)
    result_b = _build(core, manifest_b, family_matrix, split_rule)

    assert result_a["rejection_reasons"] == result_b["rejection_reasons"]
    assert result_a["prevalidation_result_id"] != result_b["prevalidation_result_id"]


def test_integrity_rejected_result_binds_changed_family_matrix() -> None:
    core = _core()
    manifest, family_matrix_a, split_rule = _integrity_invalid_manifest("same")
    family_matrix_b = copy.deepcopy(family_matrix_a)
    family_matrix_b["families"][0]["tasks"] = 7
    result_a = _build(core, manifest, family_matrix_a, split_rule)

    verification = _verify(
        core, manifest, result_a, family_matrix_b, split_rule
    )

    assert verification.valid is False
    assert tuple(verification.rejection_reasons)


def test_integrity_rejected_result_binds_changed_split_rule() -> None:
    core = _core()
    manifest, family_matrix, split_rule_a = _valid_objects()
    manifest["split_assignment_rule_hash"] = "b" * 64
    manifest["instances"][0]["split_assignment_rule_hash"] = "b" * 64
    split_rule_b = copy.deepcopy(split_rule_a)
    split_rule_b["assignments"]["pilot-family-001"] = "dev"
    result_a = _build(core, manifest, family_matrix, split_rule_a)

    verification = _verify(
        core, manifest, result_a, family_matrix, split_rule_b
    )

    assert verification.valid is False
    assert tuple(verification.rejection_reasons)


@pytest.mark.parametrize("failure_layer", ["schema", "integrity"])
def test_canonicalizable_rejected_result_contains_all_object_hashes(
    failure_layer: str,
) -> None:
    core = _core()
    if failure_layer == "schema":
        manifest, family_matrix, split_rule = _schema_invalid_manifest("invalid")
    else:
        manifest, family_matrix, split_rule = _integrity_invalid_manifest("invalid")

    result = _build(core, manifest, family_matrix, split_rule)

    assert result["status"] == "rejected"
    assert result["failure_layer"] == failure_layer
    for field in (
        "manifest_object_hash",
        "pilot_family_matrix_object_hash",
        "pilot_split_rule_object_hash",
    ):
        _assert_lowercase_sha256(result[field])


@pytest.mark.parametrize(
    "hash_field",
    [
        "manifest_object_hash",
        "pilot_family_matrix_object_hash",
        "pilot_split_rule_object_hash",
    ],
)
def test_rejected_result_id_covers_each_object_hash(hash_field: str) -> None:
    core = _core()
    manifest, family_matrix, split_rule = _schema_invalid_manifest("invalid")
    result = _build(core, manifest, family_matrix, split_rule)
    result[hash_field] = "f" * 64

    verification = _verify(core, manifest, result, family_matrix, split_rule)

    assert verification.valid is False
    assert tuple(verification.rejection_reasons)


def _noncanonical_rejected_objects(
    failure_layer: str,
) -> tuple[dict, dict, dict]:
    manifest, family_matrix, split_rule = _valid_objects()
    manifest["instances"][0]["generation_seed"] = 1 << 68
    if failure_layer == "schema":
        manifest["unknown_field"] = "schema rejection before binding"
    return manifest, family_matrix, split_rule


@pytest.mark.parametrize("failure_layer", ["schema", "integrity"])
def test_noncanonical_rejected_result_marks_binding_unavailable(
    failure_layer: str,
) -> None:
    core = _core()
    manifest, family_matrix, split_rule = _noncanonical_rejected_objects(
        failure_layer
    )

    result = _build(core, manifest, family_matrix, split_rule)

    assert result["status"] == "rejected"
    assert result["result_scope"] == "pure_object_prevalidation"
    assert result.get("binding_available") is False
    binding_reason = result.get("binding_error") or result.get(
        "binding_unavailable_reason"
    )
    assert type(binding_reason) is str
    assert any(
        token in binding_reason
        for token in (
            "canonicalization_integer_domain",
            "non_canonical_json",
            "unsupported_integer_domain",
        )
    )
    assert result["execution_authorized"] is False
    assert result["gate_p2_closed"] is False


@pytest.mark.parametrize("failure_layer", ["schema", "integrity"])
def test_noncanonical_rejected_result_cannot_verify_as_bound(
    failure_layer: str,
) -> None:
    core = _core()
    manifest, family_matrix, split_rule = _noncanonical_rejected_objects(
        failure_layer
    )
    result = _build(core, manifest, family_matrix, split_rule)

    verification = _verify(core, manifest, result, family_matrix, split_rule)

    assert verification.valid is False
    assert tuple(verification.rejection_reasons)


@pytest.mark.parametrize("mutation_stage", ["after_schema", "after_integrity"])
def test_build_uses_one_manifest_snapshot_or_rejects_mid_build_mutation(
    mutation_stage: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    core = _core()
    integrity = _module(INTEGRITY_MODULE)
    manifest, family_matrix, split_rule = _valid_objects()
    original_manifest_hash = integrity.compute_object_hash(manifest)

    if mutation_stage == "after_schema":
        original_schema = core.validate_pilot_manifest_schema

        def schema_then_mutate(current_manifest: dict):
            validation = original_schema(current_manifest)
            current_manifest["notes"] = "mutated after schema"
            return validation

        monkeypatch.setattr(
            core, "validate_pilot_manifest_schema", schema_then_mutate
        )
    else:
        original_integrity = core.verify_pilot_scoped_hash_binding

        def integrity_then_mutate(
            current_manifest: dict,
            current_matrix: dict,
            current_split_rule: dict,
        ):
            validation = original_integrity(
                current_manifest, current_matrix, current_split_rule
            )
            current_manifest["notes"] = "mutated after integrity"
            return validation

        monkeypatch.setattr(
            core, "verify_pilot_scoped_hash_binding", integrity_then_mutate
        )

    result = _build(core, manifest, family_matrix, split_rule)

    assert "mutated" in manifest["notes"]
    assert (
        result["status"] == "rejected"
        or result["manifest_object_hash"] == original_manifest_hash
    )
