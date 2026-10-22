from __future__ import annotations

import builtins
import copy
import glob
import hashlib
import importlib
import json
import os
from pathlib import Path
from types import ModuleType
from typing import Any, Mapping

import pytest


RECEIPT_MODULE = "mrta_rect_coverage.experiments.pilot_validation_receipt"
INTEGRITY_MODULE = "mrta_rect_coverage.experiments.pilot_integrity"
RECEIPT_VERSION = "pilot-validation-receipt-v2"
_MISSING = object()


def _module(name: str) -> ModuleType:
    return importlib.import_module(name)


def _receipt_module() -> ModuleType:
    try:
        return _module(RECEIPT_MODULE)
    except ModuleNotFoundError as exc:
        if exc.name == RECEIPT_MODULE:
            pytest.fail(
                "Phase 6B-T5 RED: raw-manifest-bytes pilot validation "
                "receipt builder/verifier is not implemented"
            )
        raise


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _object_hash(value: Any) -> str:
    return _module(INTEGRITY_MODULE).compute_object_hash(value)


def _receipt_body(receipt: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in receipt.items()
        if key not in {"validation_receipt_id", "signature", "signatures"}
    }


def _expected_receipt_id(receipt: Mapping[str, Any]) -> str:
    return _object_hash(_receipt_body(receipt))


def _manifest_obj() -> dict[str, Any]:
    # The manifest header hash is an artifact-domain self-claim.  T5 must not
    # reuse it as the receipt raw-byte digest.
    return {
        "manifest_type": "pilot_split_manifest",
        "manifest_scope": "pilot_nonformal",
        "matrix_scope": "pilot",
        "objective_version": "objective_v1_prototype",
        "artifact_promotion_allowed": False,
        "manifest_hash": "f" * 64,
        "instances": [
            {
                "instance_id": "pilot-instance-001",
                "family_id": "pilot-family-001",
                "split": "train",
                "file_path": "pilot_train/R2_T6_0.txt",
                "file_hash": "a" * 64,
            }
        ],
    }


def _raw_bytes(
    manifest_obj: Mapping[str, Any],
    *,
    pretty: bool = False,
    sort_keys: bool = False,
) -> bytes:
    if pretty:
        text = json.dumps(
            manifest_obj,
            ensure_ascii=False,
            indent=2,
            sort_keys=sort_keys,
        )
    else:
        text = json.dumps(
            manifest_obj,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=sort_keys,
        )
    return text.encode("utf-8")


def _with_object_id(body: Mapping[str, Any], id_field: str) -> dict[str, Any]:
    result = copy.deepcopy(dict(body))
    result[id_field] = _object_hash(result)
    return result


def _prevalidation_result(
    manifest_obj: Mapping[str, Any],
    *,
    status: str = "valid",
    reasons: tuple[str, ...] = (),
    failure_layer: str | None = None,
) -> dict[str, Any]:
    valid = status == "valid"
    body = {
        "prevalidation_schema_version": "pilot-prevalidation-core-v1",
        "status": status,
        "result_scope": "pure_object_prevalidation",
        "schema_valid": valid or failure_layer != "schema",
        "integrity_valid": True if valid else False,
        "failure_layer": None if valid else (failure_layer or "integrity"),
        "rejection_reasons": list(reasons),
        "manifest_object_hash": _object_hash(manifest_obj),
        "pilot_family_matrix_object_hash": _object_hash(
            {"matrix_scope": "pilot", "families": ["pilot-family-001"]}
        ),
        "pilot_split_rule_object_hash": _object_hash(
            {"matrix_scope": "pilot", "pilot-family-001": "train"}
        ),
        "binding_available": True,
        "binding_unavailable_reason": None,
        "canonicalization_algorithm": "RFC8785-JCS",
        "canonicalization_version": "jcs-v1-safe-int-domain",
        "execution_authorized": False,
        "gate_p2_closed": False,
    }
    return _with_object_id(body, "prevalidation_result_id")


def _binding_unavailable_prevalidation() -> dict[str, Any]:
    return {
        "prevalidation_schema_version": "pilot-prevalidation-core-v1",
        "status": "rejected",
        "result_scope": "pure_object_prevalidation",
        "schema_valid": False,
        "integrity_valid": None,
        "failure_layer": "binding",
        "rejection_reasons": ["non_canonical_json"],
        "manifest_object_hash": None,
        "pilot_family_matrix_object_hash": None,
        "pilot_split_rule_object_hash": None,
        "binding_available": False,
        "binding_unavailable_reason": "unsupported_integer_domain",
        "canonicalization_algorithm": "RFC8785-JCS",
        "canonicalization_version": "jcs-v1-safe-int-domain",
        "execution_authorized": False,
        "gate_p2_closed": False,
        "prevalidation_result_id": None,
    }


def _path_validation_result(
    manifest_obj: Mapping[str, Any],
    *,
    status: str = "valid",
    reasons: tuple[str, ...] = (),
    file_identity_check: str = "supported_pass",
) -> dict[str, Any]:
    body = {
        "path_validation_schema_version": "pilot-path-validation-v1",
        "status": status,
        "result_scope": "path_duplicate_validation",
        "manifest_object_hash": _object_hash(manifest_obj),
        "approved_root_fingerprint": _sha256_bytes(b"synthetic-pilot-root"),
        "duplicate_validation_summary": {
            "instance_id_duplicates": 0,
            "file_hash_duplicates": 0,
            "canonical_path_duplicates": 0,
            "file_identity_duplicates": 0,
            "generation_identity_duplicates": 0,
        },
        "file_identity_check": file_identity_check,
        "rejection_reasons": list(reasons),
        "no_glob_confirmed": True,
        "no_directory_discovery_confirmed": True,
        "execution_authorized": False,
        "gate_p2_closed": False,
    }
    return _with_object_id(body, "path_validation_result_id")


def _real_upstream_prevalidation_fixture() -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a valid object/result pair emitted by the real T3 builder."""
    integrity = _module(INTEGRITY_MODULE)
    family_matrix = {
        "schema_version": "pilot-family-matrix-v1",
        "matrix_scope": "pilot",
        "families": [
            {"family_id": "pilot-family-001", "robots": 2, "tasks": 6}
        ],
    }
    split_rule = {
        "schema_version": "pilot-split-rule-v1",
        "matrix_scope": "pilot",
        "assignments": {"pilot-family-001": "train"},
    }
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
        "notes": "T5R2 real upstream positive control",
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
    prevalidator = _module(
        "mrta_rect_coverage.experiments.pilot_manifest_prevalidator"
    )
    result = prevalidator.build_pilot_prevalidation_result(
        manifest,
        pilot_family_matrix_obj=family_matrix,
        pilot_split_rule_obj=split_rule,
    )
    assert type(result) is dict
    return manifest, result


_REAL_PREVALIDATION_FIELDS = {
    "prevalidation_schema_version",
    "prevalidation_result_id",
    "status",
    "result_scope",
    "schema_valid",
    "integrity_valid",
    "failure_layer",
    "rejection_reasons",
    "manifest_object_hash",
    "pilot_family_matrix_object_hash",
    "pilot_split_rule_object_hash",
    "binding_available",
    "binding_unavailable_reason",
    "canonicalization_algorithm",
    "canonicalization_version",
    "execution_authorized",
    "gate_p2_closed",
}


_REAL_PREVALIDATION_VERSION = "pilot-prevalidation-core-v1"


def _build(
    *,
    raw_manifest_bytes: Any = _MISSING,
    manifest_obj: Any = _MISSING,
    prevalidation_result: Any = _MISSING,
    path_validation_result: Any = _MISSING,
    validator_identity: Any = "pilot-validator-test-v1",
) -> dict[str, Any]:
    module = _receipt_module()
    manifest = _manifest_obj() if manifest_obj is _MISSING else manifest_obj
    raw = _raw_bytes(manifest) if raw_manifest_bytes is _MISSING else raw_manifest_bytes
    prevalidation = (
        _prevalidation_result(manifest)
        if prevalidation_result is _MISSING
        else prevalidation_result
    )
    path_result = (
        _path_validation_result(manifest)
        if path_validation_result is _MISSING
        else path_validation_result
    )
    result = module.build_pilot_validation_receipt(
        raw_manifest_bytes=raw,
        manifest_obj=manifest,
        prevalidation_result=prevalidation,
        path_validation_result=path_result,
        validator_identity=validator_identity,
    )
    assert type(result) is dict
    return result


def _verify(
    receipt: Mapping[str, Any],
    *,
    raw_manifest_bytes: Any = _MISSING,
    manifest_obj: Any = _MISSING,
    prevalidation_result: Any = _MISSING,
    path_validation_result: Any = _MISSING,
):
    module = _receipt_module()
    manifest = _manifest_obj() if manifest_obj is _MISSING else manifest_obj
    raw = _raw_bytes(manifest) if raw_manifest_bytes is _MISSING else raw_manifest_bytes
    prevalidation = (
        _prevalidation_result(manifest)
        if prevalidation_result is _MISSING
        else prevalidation_result
    )
    path_result = (
        _path_validation_result(manifest)
        if path_validation_result is _MISSING
        else path_validation_result
    )
    return module.verify_pilot_validation_receipt(
        receipt,
        raw_manifest_bytes=raw,
        manifest_obj=manifest,
        prevalidation_result=prevalidation,
        path_validation_result=path_result,
    )


def _result_field(result: Any, name: str, default: Any = _MISSING) -> Any:
    if isinstance(result, Mapping):
        if default is _MISSING:
            return result[name]
        return result.get(name, default)
    if default is _MISSING:
        return getattr(result, name)
    return getattr(result, name, default)


def _assert_verify_valid(result: Any) -> None:
    assert _result_field(result, "valid") is True
    assert tuple(_result_field(result, "rejection_reasons", ())) == ()


def _assert_verify_rejected(result: Any, *tokens: str) -> None:
    assert _result_field(result, "valid") is False
    reasons = tuple(str(value) for value in _result_field(result, "rejection_reasons", ()))
    assert reasons
    if tokens:
        joined = " ".join(reasons).lower()
        assert any(token.lower() in joined for token in tokens), reasons


def _reason_pairs(receipt: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
    values = receipt.get("rejection_reasons", [])
    assert type(values) is list
    pairs: list[tuple[str, str]] = []
    for value in values:
        assert type(value) is dict
        assert set(value) == {"layer", "reason"}
        assert type(value["layer"]) is str and value["layer"]
        assert type(value["reason"]) is str and value["reason"]
        pairs.append((value["layer"], value["reason"]))
    return tuple(pairs)


def _assert_valid_receipt(receipt: Mapping[str, Any]) -> None:
    assert receipt["status"] == "valid"
    assert receipt["receipt_scope"] == "pilot_validation"
    assert receipt["receipt_version"] == RECEIPT_VERSION
    assert receipt["rejection_reasons"] == []
    assert receipt["execution_authorized"] is False
    assert receipt["gate_p2_closed"] is False
    assert receipt["formal_evidence_eligible"] is False
    assert receipt["prevalidation_status"] == "valid"
    assert receipt["path_validation_status"] == "valid"


def _assert_rejected_receipt(
    receipt: Mapping[str, Any],
    *tokens: str,
) -> None:
    assert receipt["status"] == "rejected"
    assert receipt["execution_authorized"] is False
    assert receipt["gate_p2_closed"] is False
    pairs = _reason_pairs(receipt)
    assert pairs
    if tokens:
        joined = " ".join(f"{layer}:{reason}" for layer, reason in pairs).lower()
        assert any(token.lower() in joined for token in tokens), pairs


def _recompute_result_id(result: dict[str, Any], id_field: str) -> dict[str, Any]:
    updated = copy.deepcopy(result)
    updated.pop(id_field, None)
    updated[id_field] = _object_hash(updated)
    return updated


def _recompute_receipt_id(receipt: dict[str, Any]) -> dict[str, Any]:
    updated = copy.deepcopy(receipt)
    updated["validation_receipt_id"] = _expected_receipt_id(updated)
    return updated


def _all_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if type(value) is dict:
        for key, nested in value.items():
            keys.add(str(key))
            keys.update(_all_keys(nested))
    elif type(value) is list:
        for nested in value:
            keys.update(_all_keys(nested))
    return keys


# Raw bytes and object hash domains ----------------------------------------


def test_valid_receipt_separates_raw_bytes_and_object_hash_domains() -> None:
    manifest = _manifest_obj()
    raw = _raw_bytes(manifest, pretty=True)

    receipt = _build(raw_manifest_bytes=raw, manifest_obj=manifest)

    _assert_valid_receipt(receipt)
    assert receipt["manifest_hash"] == _sha256_bytes(raw)
    assert receipt["raw_manifest_bytes_hash"] == receipt["manifest_hash"]
    assert receipt["manifest_object_hash"] == _object_hash(manifest)
    assert receipt["manifest_hash"] != receipt["manifest_object_hash"]


def test_raw_formatting_changes_raw_hash_and_receipt_id_not_object_hash() -> None:
    manifest = _manifest_obj()
    raw_compact = _raw_bytes(manifest, sort_keys=False)
    raw_pretty_sorted = _raw_bytes(manifest, pretty=True, sort_keys=True)

    compact = _build(raw_manifest_bytes=raw_compact, manifest_obj=manifest)
    pretty = _build(raw_manifest_bytes=raw_pretty_sorted, manifest_obj=manifest)

    assert compact["manifest_hash"] != pretty["manifest_hash"]
    assert compact["manifest_object_hash"] == pretty["manifest_object_hash"]
    assert compact["validation_receipt_id"] != pretty["validation_receipt_id"]
    _assert_verify_rejected(
        _verify(compact, raw_manifest_bytes=raw_pretty_sorted, manifest_obj=manifest),
        "manifest_hash",
        "raw_manifest",
    )


def test_artifact_header_hash_is_not_copied_into_receipt_raw_hash() -> None:
    manifest = _manifest_obj()
    raw = _raw_bytes(manifest)
    assert manifest["manifest_hash"] != _sha256_bytes(raw)

    receipt = _build(raw_manifest_bytes=raw, manifest_obj=manifest)

    assert receipt["manifest_hash"] == _sha256_bytes(raw)
    assert receipt["manifest_hash"] != manifest["manifest_hash"]


@pytest.mark.parametrize(
    ("target_field", "wrong_value"),
    [
        ("manifest_hash", "object_hash"),
        ("manifest_object_hash", "raw_hash"),
    ],
)
def test_hash_domains_cannot_be_swapped_even_with_recomputed_receipt_id(
    target_field: str,
    wrong_value: str,
) -> None:
    manifest = _manifest_obj()
    raw = _raw_bytes(manifest, pretty=True)
    receipt = _build(raw_manifest_bytes=raw, manifest_obj=manifest)
    tampered = copy.deepcopy(receipt)
    tampered[target_field] = (
        _object_hash(manifest) if wrong_value == "object_hash" else _sha256_bytes(raw)
    )
    tampered = _recompute_receipt_id(tampered)

    _assert_verify_rejected(
        _verify(tampered, raw_manifest_bytes=raw, manifest_obj=manifest),
        target_field,
        "hash_domain",
    )


# Raw parsing and object consistency --------------------------------------


@pytest.mark.parametrize(
    "raw_value",
    ["{}", Path("never-read.json"), {}, [], None, 0, True],
)
def test_raw_manifest_input_must_be_literal_bytes(raw_value: Any) -> None:
    try:
        receipt = _build(raw_manifest_bytes=raw_value)
    except (TypeError, ValueError):
        return
    _assert_rejected_receipt(receipt, "raw_manifest", "type")


@pytest.mark.parametrize(
    ("raw", "reason"),
    [
        (b"\xff\xfe", "utf"),
        (b"not json", "parse"),
        (b'{"a":1} trailing', "parse"),
        (b'{"duplicate":1,"duplicate":2}', "duplicate"),
    ],
)
def test_invalid_or_ambiguous_raw_json_is_rejected(raw: bytes, reason: str) -> None:
    receipt = _build(raw_manifest_bytes=raw)
    _assert_rejected_receipt(receipt, "raw_manifest", reason)
    assert receipt["manifest_hash"] == _sha256_bytes(raw)


@pytest.mark.parametrize(
    "raw",
    [b"[]", b'"text"', b"7", b"null", b"true"],
)
def test_raw_json_top_level_must_be_an_object(raw: bytes) -> None:
    receipt = _build(raw_manifest_bytes=raw)
    _assert_rejected_receipt(receipt, "raw_manifest", "object")


def test_raw_parsed_object_must_equal_supplied_manifest_object() -> None:
    manifest = _manifest_obj()
    different = copy.deepcopy(manifest)
    different["objective_version"] = "different-objective"
    raw = _raw_bytes(different)

    receipt = _build(raw_manifest_bytes=raw, manifest_obj=manifest)

    _assert_rejected_receipt(receipt, "raw_manifest_object_mismatch")
    assert receipt["manifest_hash"] == _sha256_bytes(raw)
    assert receipt["manifest_object_hash"] == _object_hash(manifest)


def test_unsupported_integer_in_raw_object_fails_closed() -> None:
    manifest = {"manifest_scope": "pilot_nonformal", "n": 2**68}
    raw = b'{"manifest_scope":"pilot_nonformal","n":295147905179352825856}'

    receipt = _build(
        raw_manifest_bytes=raw,
        manifest_obj=manifest,
        prevalidation_result=_binding_unavailable_prevalidation(),
        path_validation_result={
            "status": "rejected",
            "result_scope": "path_duplicate_validation",
            "manifest_object_hash": None,
            "rejection_reasons": ["binding_unavailable"],
            "execution_authorized": False,
            "gate_p2_closed": False,
            "path_validation_result_id": None,
        },
    )

    _assert_rejected_receipt(
        receipt,
        "unsupported_integer",
        "non_canonical",
        "binding_unavailable",
    )
    assert receipt.get("manifest_object_hash") is None


def test_verifier_does_not_ignore_raw_parse_failure() -> None:
    receipt = _build()

    _assert_verify_rejected(
        _verify(receipt, raw_manifest_bytes=b"not json"),
        "raw_manifest",
        "parse",
    )


# Receipt identity ---------------------------------------------------------


def test_validation_receipt_id_is_lowercase_non_self_referential_hash() -> None:
    receipt = _build()

    receipt_id = receipt["validation_receipt_id"]
    assert type(receipt_id) is str
    assert len(receipt_id) == 64
    assert receipt_id == receipt_id.lower()
    assert all(character in "0123456789abcdef" for character in receipt_id)
    assert receipt_id == _expected_receipt_id(receipt)


@pytest.mark.parametrize(
    "field",
    [
        "manifest_hash",
        "raw_manifest_bytes_hash",
        "manifest_object_hash",
        "validator_identity",
        "receipt_version",
    ],
)
def test_changing_top_level_bound_field_invalidates_old_receipt_id(field: str) -> None:
    receipt = _build()
    tampered = copy.deepcopy(receipt)
    tampered[field] = "b" * 64 if field.endswith("hash") else f"changed-{field}"

    _assert_verify_rejected(_verify(tampered), "receipt_id", "receipt_hash")


@pytest.mark.parametrize(
    ("evidence_field", "nested_field"),
    [
        ("prevalidation_evidence", "prevalidation_result_id"),
        ("path_validation_evidence", "path_validation_result_id"),
    ],
)
def test_changing_bound_evidence_id_invalidates_old_receipt_id(
    evidence_field: str,
    nested_field: str,
) -> None:
    receipt = _build()
    tampered = copy.deepcopy(receipt)
    tampered[evidence_field][nested_field] = "b" * 64

    _assert_verify_rejected(_verify(tampered), "receipt_id", "receipt_hash")


def test_signature_fields_are_excluded_from_receipt_id_preimage() -> None:
    receipt = _build()
    with_signature = copy.deepcopy(receipt)
    with_signature["signature"] = "illustrative-signature-a"
    with_signature["signatures"] = ["illustrative-signature-b"]

    assert _expected_receipt_id(with_signature) == receipt["validation_receipt_id"]
    _assert_verify_valid(_verify(with_signature))


@pytest.mark.parametrize(
    "invalid_id",
    [None, "", "not-a-hash", "A" * 64, "a" * 63, "a" * 65, 7, False],
)
def test_invalid_validation_receipt_id_fails_closed(invalid_id: Any) -> None:
    receipt = _build()
    receipt["validation_receipt_id"] = invalid_id

    _assert_verify_rejected(_verify(receipt), "validation_receipt_id", "receipt_id")


# Prevalidation evidence binding ------------------------------------------


def test_receipt_binds_complete_prevalidation_evidence() -> None:
    manifest = _manifest_obj()
    prevalidation = _prevalidation_result(manifest)

    receipt = _build(manifest_obj=manifest, prevalidation_result=prevalidation)

    evidence = receipt["prevalidation_evidence"]
    for field in (
        "prevalidation_result_id",
        "status",
        "result_scope",
        "manifest_object_hash",
        "pilot_family_matrix_object_hash",
        "pilot_split_rule_object_hash",
        "canonicalization_algorithm",
        "canonicalization_version",
        "binding_available",
        "binding_unavailable_reason",
    ):
        assert evidence[field] == prevalidation[field]


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("status", "rejected"),
        ("result_scope", "wrong_scope"),
        ("manifest_object_hash", "b" * 64),
        ("pilot_family_matrix_object_hash", "b" * 64),
        ("pilot_split_rule_object_hash", "b" * 64),
        ("canonicalization_algorithm", "not-jcs"),
        ("canonicalization_version", "wrong-version"),
        ("binding_available", False),
        ("binding_unavailable_reason", "changed"),
    ],
)
def test_changed_prevalidation_evidence_cannot_verify_old_receipt(
    field: str,
    replacement: Any,
) -> None:
    manifest = _manifest_obj()
    original = _prevalidation_result(manifest)
    receipt = _build(manifest_obj=manifest, prevalidation_result=original)
    changed = copy.deepcopy(original)
    changed[field] = replacement
    changed = _recompute_result_id(changed, "prevalidation_result_id")

    _assert_verify_rejected(
        _verify(receipt, manifest_obj=manifest, prevalidation_result=changed),
        "prevalidation",
        "evidence",
        "binding",
    )


def test_prevalidation_result_id_must_match_supplied_result_body() -> None:
    manifest = _manifest_obj()
    prevalidation = _prevalidation_result(manifest)
    prevalidation["prevalidation_result_id"] = "b" * 64

    receipt = _build(manifest_obj=manifest, prevalidation_result=prevalidation)

    _assert_rejected_receipt(receipt, "prevalidation_result_id", "binding")


# Path validation evidence binding ----------------------------------------


def test_receipt_binds_complete_path_validation_evidence() -> None:
    manifest = _manifest_obj()
    path_result = _path_validation_result(manifest)

    receipt = _build(manifest_obj=manifest, path_validation_result=path_result)

    evidence = receipt["path_validation_evidence"]
    for field in (
        "path_validation_result_id",
        "status",
        "result_scope",
        "manifest_object_hash",
        "approved_root_fingerprint",
        "duplicate_validation_summary",
        "file_identity_check",
        "rejection_reasons",
        "no_glob_confirmed",
        "no_directory_discovery_confirmed",
        "execution_authorized",
        "gate_p2_closed",
    ):
        assert evidence[field] == path_result[field]


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("status", "rejected"),
        ("result_scope", "wrong_scope"),
        ("manifest_object_hash", "b" * 64),
        ("approved_root_fingerprint", "b" * 64),
        ("file_identity_check", "unsupported_file_identity_check"),
        ("rejection_reasons", ["path_escape"]),
        ("no_glob_confirmed", False),
        ("no_directory_discovery_confirmed", False),
        ("execution_authorized", True),
        ("gate_p2_closed", True),
    ],
)
def test_changed_path_evidence_cannot_verify_old_receipt(
    field: str,
    replacement: Any,
) -> None:
    manifest = _manifest_obj()
    original = _path_validation_result(manifest)
    receipt = _build(manifest_obj=manifest, path_validation_result=original)
    changed = copy.deepcopy(original)
    changed[field] = replacement
    changed = _recompute_result_id(changed, "path_validation_result_id")

    _assert_verify_rejected(
        _verify(receipt, manifest_obj=manifest, path_validation_result=changed),
        "path_validation",
        "evidence",
        "binding",
    )


def test_path_validation_result_id_must_match_supplied_result_body() -> None:
    manifest = _manifest_obj()
    path_result = _path_validation_result(manifest)
    path_result["path_validation_result_id"] = "b" * 64

    receipt = _build(manifest_obj=manifest, path_validation_result=path_result)

    _assert_rejected_receipt(receipt, "path_validation_result_id", "binding")


# Status composition and rejection taxonomy -------------------------------


@pytest.mark.parametrize(
    ("pre_status", "path_status", "expected_status"),
    [
        ("valid", "valid", "valid"),
        ("rejected", "valid", "rejected"),
        ("valid", "rejected", "rejected"),
        ("rejected", "rejected", "rejected"),
    ],
)
def test_receipt_status_composes_prevalidation_and_path_statuses(
    pre_status: str,
    path_status: str,
    expected_status: str,
) -> None:
    manifest = _manifest_obj()
    prevalidation = _prevalidation_result(
        manifest,
        status=pre_status,
        reasons=() if pre_status == "valid" else ("schema_invalid",),
        failure_layer=None if pre_status == "valid" else "schema",
    )
    path_result = _path_validation_result(
        manifest,
        status=path_status,
        reasons=() if path_status == "valid" else ("path_escape",),
    )

    receipt = _build(
        manifest_obj=manifest,
        prevalidation_result=prevalidation,
        path_validation_result=path_result,
    )

    assert receipt["status"] == expected_status
    assert receipt["execution_authorized"] is False
    assert receipt["gate_p2_closed"] is False
    if expected_status == "valid":
        assert receipt["rejection_reasons"] == []
    else:
        pairs = _reason_pairs(receipt)
        if pre_status == "rejected":
            assert ("schema", "schema_invalid") in pairs
        if path_status == "rejected":
            assert ("path", "path_escape") in pairs


@pytest.mark.parametrize(
    ("layer", "reason"),
    [
        ("schema", "schema_invalid"),
        ("integrity", "integrity_invalid"),
        ("binding", "binding_unavailable"),
        ("path", "path_escape"),
        ("path", "path_toctou_detected"),
        ("duplicate", "duplicate_instance_id"),
        ("duplicate", "duplicate_file_hash"),
        ("duplicate", "duplicate_canonical_path"),
        ("duplicate", "duplicate_file_identity"),
        ("duplicate", "duplicate_generation_identity"),
        ("scope", "formal_scope_forbidden"),
        ("scope", "final_test_marker_forbidden"),
        ("scope", "artifact_promotion_forbidden"),
        ("path", "glob_forbidden"),
        ("path", "unsupported_file_identity_check"),
        ("integrity", "non_canonical_json"),
    ],
)
def test_rejected_receipt_preserves_source_qualified_evidence_reason(
    layer: str,
    reason: str,
) -> None:
    manifest = _manifest_obj()
    if layer in {"schema", "integrity", "binding"}:
        prevalidation = _prevalidation_result(
            manifest,
            status="rejected",
            reasons=(reason,),
            failure_layer=layer,
        )
        path_result = _path_validation_result(manifest)
    else:
        prevalidation = _prevalidation_result(manifest)
        path_result = _path_validation_result(
            manifest,
            status="rejected",
            reasons=(reason,),
            file_identity_check=(
                "unsupported_file_identity_check"
                if reason == "unsupported_file_identity_check"
                else "supported_pass"
            ),
        )

    receipt = _build(
        manifest_obj=manifest,
        prevalidation_result=prevalidation,
        path_validation_result=path_result,
    )

    pairs = _reason_pairs(receipt)
    assert (layer, reason) in pairs
    assert all(item_reason != "generic_invalid" for _, item_reason in pairs)
    assert all("success" not in item_reason for _, item_reason in pairs)


@pytest.mark.parametrize(
    ("raw", "expected_reason"),
    [
        (b"not json", "raw_manifest_parse_error"),
        (b'{"different":true}', "raw_manifest_object_mismatch"),
    ],
)
def test_raw_manifest_rejection_reason_is_source_qualified(
    raw: bytes,
    expected_reason: str,
) -> None:
    receipt = _build(raw_manifest_bytes=raw)
    pairs = _reason_pairs(receipt)
    assert ("raw_manifest", expected_reason) in pairs


def test_raw_manifest_hash_mismatch_is_source_qualified() -> None:
    receipt = _build()
    receipt["manifest_hash"] = "b" * 64
    receipt = _recompute_receipt_id(receipt)

    result = _verify(receipt)

    _assert_verify_rejected(result, "raw_manifest_hash_mismatch", "manifest_hash")


# Schema/status and inert semantics ---------------------------------------


@pytest.mark.parametrize(
    "forbidden_status",
    [
        "validation_valid",
        "validation_rejected",
        "preflight_validated",
        "preflight_rejected",
        "scheduled",
        "running",
        "completed",
        "executed",
    ],
)
def test_only_valid_or_rejected_receipt_status_is_allowed(
    forbidden_status: str,
) -> None:
    receipt = _build()
    receipt["status"] = forbidden_status
    receipt = _recompute_receipt_id(receipt)

    _assert_verify_rejected(_verify(receipt), "status")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("execution_authorized", True),
        ("gate_p2_closed", True),
        ("formal_evidence_eligible", True),
        ("receipt_scope", "formal_validation"),
        ("receipt_scope", "final_test_validation"),
    ],
)
def test_receipt_cannot_claim_execution_gate_or_formal_authority(
    field: str,
    value: Any,
) -> None:
    receipt = _build()
    receipt[field] = value
    receipt = _recompute_receipt_id(receipt)

    _assert_verify_rejected(
        _verify(receipt),
        "execution",
        "gate_p2",
        "formal",
        "scope",
    )


@pytest.mark.parametrize(
    "forbidden_field",
    [
        "accepted_execution",
        "runner_receipt_id",
        "scheduled_run_id",
        "provider_invocation_result",
        "candidate_execution_result",
        "pilot_execution_result",
        "real_llm_provider_used",
        "provider_name",
        "provider_model",
        "candidate_id",
        "run_id",
        "formal_final_test_lockbox_validated",
        "formal_experiment_ready",
        "runner_execution_authorized",
    ],
)
def test_valid_receipt_contains_no_runner_provider_or_execution_fields(
    forbidden_field: str,
) -> None:
    receipt = _build()

    assert forbidden_field not in _all_keys(receipt)


def test_rejected_receipt_still_binds_available_raw_and_object_hashes() -> None:
    manifest = _manifest_obj()
    raw = _raw_bytes(manifest, pretty=True)
    path_result = _path_validation_result(
        manifest,
        status="rejected",
        reasons=("path_escape",),
    )

    receipt = _build(
        raw_manifest_bytes=raw,
        manifest_obj=manifest,
        path_validation_result=path_result,
    )

    _assert_rejected_receipt(receipt, "path_escape")
    assert receipt["manifest_hash"] == _sha256_bytes(raw)
    assert receipt["raw_manifest_bytes_hash"] == receipt["manifest_hash"]
    assert receipt["manifest_object_hash"] == _object_hash(manifest)


def test_unsupported_file_identity_is_not_overclaimed() -> None:
    manifest = _manifest_obj()
    path_result = _path_validation_result(
        manifest,
        status="rejected",
        reasons=("unsupported_file_identity_check",),
        file_identity_check="unsupported_file_identity_check",
    )

    receipt = _build(manifest_obj=manifest, path_validation_result=path_result)

    _assert_rejected_receipt(receipt, "unsupported_file_identity_check")
    assert receipt["path_validation_evidence"]["file_identity_check"] == (
        "unsupported_file_identity_check"
    )
    assert receipt.get("full_file_identity_supported", False) is False


# No path/file access ------------------------------------------------------


def _forbidden_call(name: str):
    def fail(*_args: Any, **_kwargs: Any):
        pytest.fail(f"T5 receipt must not call {name}")

    return fail


def test_builder_and_verifier_use_explicit_bytes_without_path_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Import before installing file-I/O sentinels so import machinery itself is
    # not confused with T5 behavior.
    _receipt_module()
    manifest = _manifest_obj()
    raw = _raw_bytes(manifest)
    prevalidation = _prevalidation_result(manifest)
    path_result = _path_validation_result(manifest)

    monkeypatch.setattr(builtins, "open", _forbidden_call("builtins.open"))
    monkeypatch.setattr(Path, "open", _forbidden_call("Path.open"))
    monkeypatch.setattr(Path, "read_bytes", _forbidden_call("Path.read_bytes"))
    monkeypatch.setattr(glob, "glob", _forbidden_call("glob.glob"))
    monkeypatch.setattr(Path, "glob", _forbidden_call("Path.glob"))
    monkeypatch.setattr(os, "walk", _forbidden_call("os.walk"))

    receipt = _build(
        raw_manifest_bytes=raw,
        manifest_obj=manifest,
        prevalidation_result=prevalidation,
        path_validation_result=path_result,
    )
    _assert_valid_receipt(receipt)
    _assert_verify_valid(
        _verify(
            receipt,
            raw_manifest_bytes=raw,
            manifest_obj=manifest,
            prevalidation_result=prevalidation,
            path_validation_result=path_result,
        )
    )


def test_path_like_raw_input_is_rejected_without_reading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _receipt_module()
    monkeypatch.setattr(builtins, "open", _forbidden_call("builtins.open"))
    monkeypatch.setattr(Path, "open", _forbidden_call("Path.open"))
    monkeypatch.setattr(Path, "read_bytes", _forbidden_call("Path.read_bytes"))

    try:
        receipt = _build(raw_manifest_bytes=Path("final-test-never-read.json"))
    except (TypeError, ValueError):
        return
    _assert_rejected_receipt(receipt, "raw_manifest", "type")


def test_builder_api_does_not_accept_manifest_path() -> None:
    module = _receipt_module()
    manifest = _manifest_obj()
    raw = _raw_bytes(manifest)

    with pytest.raises(TypeError):
        module.build_pilot_validation_receipt(
            raw_manifest_bytes=raw,
            manifest_obj=manifest,
            prevalidation_result=_prevalidation_result(manifest),
            path_validation_result=_path_validation_result(manifest),
            validator_identity="pilot-validator-test-v1",
            manifest_path=Path("must-not-be-read.json"),
        )


def test_receipt_does_not_overclaim_instance_file_verification() -> None:
    receipt = _build()
    path_evidence = receipt["path_validation_evidence"]

    assert receipt.get("instance_file_hashes_verified") in {None, False}
    assert path_evidence["duplicate_validation_summary"] == (
        _path_validation_result(_manifest_obj())["duplicate_validation_summary"]
    )
    assert receipt["execution_authorized"] is False
    assert receipt["gate_p2_closed"] is False


# Phase 6B-T5R: malformed/self-hashed upstream evidence --------------------


def _self_hashed_without(
    result: Mapping[str, Any],
    field: str,
    id_field: str,
) -> dict[str, Any]:
    malformed = copy.deepcopy(dict(result))
    malformed.pop(field, None)
    if field == id_field:
        malformed.pop(id_field, None)
        return malformed
    return _recompute_result_id(malformed, id_field)


def _self_hashed_with(
    result: Mapping[str, Any],
    field: str,
    value: Any,
    id_field: str,
) -> dict[str, Any]:
    malformed = copy.deepcopy(dict(result))
    malformed[field] = copy.deepcopy(value)
    return _recompute_result_id(malformed, id_field)


def _assert_malformed_upstream_fails_closed(
    receipt: Mapping[str, Any],
    *,
    branch: str,
    prevalidation_result: Any = _MISSING,
    path_validation_result: Any = _MISSING,
) -> None:
    kwargs: dict[str, Any] = {}
    if prevalidation_result is not _MISSING:
        kwargs["prevalidation_result"] = prevalidation_result
    if path_validation_result is not _MISSING:
        kwargs["path_validation_result"] = path_validation_result
    verification = _verify(receipt, **kwargs)

    builder_rejected = receipt["status"] == "rejected"
    builder_inert = (
        receipt.get("execution_authorized") is False
        and receipt.get("gate_p2_closed") is False
    )
    builder_pairs = _reason_pairs(receipt) if builder_rejected else ()
    builder_reasons = " ".join(
        f"{layer}:{reason}" for layer, reason in builder_pairs
    ).lower()
    builder_reasoned = bool(builder_pairs) and all(
        reason != "generic_invalid" for _, reason in builder_pairs
    ) and any(
        token in builder_reasons
        for token in (branch, "malformed", "invalid", "missing", "binding")
    )

    verifier_valid = _result_field(verification, "valid")
    verifier_reasons = tuple(
        str(value)
        for value in _result_field(verification, "rejection_reasons", ())
    )
    verifier_rejected = verifier_valid is False and bool(verifier_reasons)

    # Evaluate both API paths before asserting so a builder bypass cannot hide
    # a verifier bypass (or vice versa).
    assert builder_rejected and builder_inert and builder_reasoned and verifier_rejected, (
        "exact upstream envelope/version validation is missing",
        {
            "builder_rejected": builder_rejected,
            "builder_reasoned": builder_reasoned,
            "verifier_rejected": verifier_rejected,
            "receipt": receipt,
            "verification": verification,
        },
    )


@pytest.mark.parametrize(
    "missing_field",
    [
        "prevalidation_result_id",
        "status",
        "result_scope",
        "manifest_object_hash",
        "pilot_family_matrix_object_hash",
        "pilot_split_rule_object_hash",
        "canonicalization_algorithm",
        "canonicalization_version",
        "binding_available",
        "schema_valid",
        "integrity_valid",
        "failure_layer",
        "rejection_reasons",
        "execution_authorized",
        "gate_p2_closed",
    ],
)
def test_self_hashed_valid_prevalidation_missing_required_field_fails_closed(
    missing_field: str,
) -> None:
    manifest = _manifest_obj()
    malformed = _self_hashed_without(
        _prevalidation_result(manifest),
        missing_field,
        "prevalidation_result_id",
    )

    receipt = _build(manifest_obj=manifest, prevalidation_result=malformed)

    _assert_malformed_upstream_fails_closed(
        receipt,
        branch="prevalidation",
        prevalidation_result=malformed,
    )


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("manifest_object_hash", None),
        ("manifest_object_hash", ""),
        ("manifest_object_hash", "A" * 64),
        ("manifest_object_hash", "not-a-hash"),
        ("manifest_object_hash", "a" * 63),
        ("pilot_family_matrix_object_hash", "A" * 64),
        ("pilot_family_matrix_object_hash", "not-a-hash"),
        ("pilot_split_rule_object_hash", "A" * 64),
        ("pilot_split_rule_object_hash", "a" * 65),
    ],
)
def test_self_hashed_valid_prevalidation_invalid_hash_field_fails_closed(
    field: str,
    invalid_value: Any,
) -> None:
    manifest = _manifest_obj()
    malformed = _self_hashed_with(
        _prevalidation_result(manifest),
        field,
        invalid_value,
        "prevalidation_result_id",
    )

    receipt = _build(manifest_obj=manifest, prevalidation_result=malformed)

    _assert_malformed_upstream_fails_closed(
        receipt,
        branch="prevalidation",
        prevalidation_result=malformed,
    )


@pytest.mark.parametrize(
    "invalid_id",
    [None, "", "not-a-hash", "A" * 64, "a" * 63, "a" * 65, 1, False],
)
def test_invalid_prevalidation_result_id_never_produces_verifiable_receipt(
    invalid_id: Any,
) -> None:
    manifest = _manifest_obj()
    malformed = _prevalidation_result(manifest)
    malformed["prevalidation_result_id"] = invalid_id

    receipt = _build(manifest_obj=manifest, prevalidation_result=malformed)

    _assert_malformed_upstream_fails_closed(
        receipt,
        branch="prevalidation",
        prevalidation_result=malformed,
    )


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("schema_valid", False),
        ("integrity_valid", False),
        ("failure_layer", "schema"),
        ("failure_layer", "integrity"),
        ("rejection_reasons", ["schema_invalid"]),
        ("binding_available", False),
        ("binding_unavailable_reason", "unexpected_binding_failure"),
        ("result_scope", "wrong_prevalidation_scope"),
        ("execution_authorized", True),
        ("gate_p2_closed", True),
    ],
)
def test_self_hashed_valid_prevalidation_branch_conflict_fails_closed(
    field: str,
    invalid_value: Any,
) -> None:
    manifest = _manifest_obj()
    malformed = _self_hashed_with(
        _prevalidation_result(manifest),
        field,
        invalid_value,
        "prevalidation_result_id",
    )

    receipt = _build(manifest_obj=manifest, prevalidation_result=malformed)

    _assert_malformed_upstream_fails_closed(
        receipt,
        branch="prevalidation",
        prevalidation_result=malformed,
    )


@pytest.mark.parametrize(
    "mutations",
    [
        {
            "status": "rejected",
            "schema_valid": False,
            "integrity_valid": False,
            "failure_layer": "schema",
            "rejection_reasons": [],
        },
        {
            "status": "rejected",
            "schema_valid": False,
            "integrity_valid": False,
            "failure_layer": None,
            "rejection_reasons": [],
        },
        {
            "status": "rejected",
            "schema_valid": False,
            "integrity_valid": False,
            "failure_layer": None,
            "rejection_reasons": [],
            "binding_available": True,
            "binding_unavailable_reason": None,
        },
        {"status": "validation_valid"},
        {"status": "preflight_validated"},
        {"status": "completed"},
    ],
)
def test_self_hashed_malformed_prevalidation_rejected_or_invalid_branch_fails_closed(
    mutations: Mapping[str, Any],
) -> None:
    manifest = _manifest_obj()
    malformed = copy.deepcopy(_prevalidation_result(manifest))
    malformed.update(copy.deepcopy(dict(mutations)))
    malformed = _recompute_result_id(malformed, "prevalidation_result_id")

    receipt = _build(manifest_obj=manifest, prevalidation_result=malformed)

    _assert_malformed_upstream_fails_closed(
        receipt,
        branch="prevalidation",
        prevalidation_result=malformed,
    )


@pytest.mark.parametrize(
    "missing_field",
    [
        "path_validation_result_id",
        "status",
        "result_scope",
        "manifest_object_hash",
        "approved_root_fingerprint",
        "duplicate_validation_summary",
        "file_identity_check",
        "rejection_reasons",
        "execution_authorized",
        "gate_p2_closed",
        "no_glob_confirmed",
        "no_directory_discovery_confirmed",
    ],
)
def test_self_hashed_valid_path_evidence_missing_required_field_fails_closed(
    missing_field: str,
) -> None:
    manifest = _manifest_obj()
    malformed = _self_hashed_without(
        _path_validation_result(manifest),
        missing_field,
        "path_validation_result_id",
    )

    receipt = _build(manifest_obj=manifest, path_validation_result=malformed)

    _assert_malformed_upstream_fails_closed(
        receipt,
        branch="path",
        path_validation_result=malformed,
    )


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("approved_root_fingerprint", None),
        ("approved_root_fingerprint", []),
        ("approved_root_fingerprint", "A" * 64),
        ("duplicate_validation_summary", "ok"),
        (
            "duplicate_validation_summary",
            {
                "instance_id_duplicates": 0,
                "file_hash_duplicates": 0,
                "canonical_path_duplicates": 0,
                "file_identity_duplicates": 1,
                "generation_identity_duplicates": 0,
            },
        ),
        ("file_identity_check", "unknown_identity_state"),
        ("rejection_reasons", None),
        ("rejection_reasons", "path_escape"),
        ("execution_authorized", "false"),
        ("gate_p2_closed", "false"),
    ],
)
def test_self_hashed_valid_path_evidence_wrong_type_or_enum_fails_closed(
    field: str,
    invalid_value: Any,
) -> None:
    manifest = _manifest_obj()
    malformed = _self_hashed_with(
        _path_validation_result(manifest),
        field,
        invalid_value,
        "path_validation_result_id",
    )

    receipt = _build(manifest_obj=manifest, path_validation_result=malformed)

    _assert_malformed_upstream_fails_closed(
        receipt,
        branch="path",
        path_validation_result=malformed,
    )


@pytest.mark.parametrize(
    "invalid_id",
    [None, "", "not-a-hash", "A" * 64, "a" * 63, "a" * 65, 1, False],
)
def test_invalid_path_validation_result_id_never_produces_verifiable_receipt(
    invalid_id: Any,
) -> None:
    manifest = _manifest_obj()
    malformed = _path_validation_result(manifest)
    malformed["path_validation_result_id"] = invalid_id

    receipt = _build(manifest_obj=manifest, path_validation_result=malformed)

    _assert_malformed_upstream_fails_closed(
        receipt,
        branch="path",
        path_validation_result=malformed,
    )


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("rejection_reasons", ["path_escape"]),
        (
            "duplicate_validation_summary",
            {
                "instance_id_duplicates": 1,
                "file_hash_duplicates": 0,
                "canonical_path_duplicates": 0,
                "file_identity_duplicates": 0,
                "generation_identity_duplicates": 0,
            },
        ),
        ("file_identity_check", "unsupported_file_identity_check"),
        ("file_identity_check", "unsupported"),
        ("result_scope", "wrong_path_scope"),
        ("execution_authorized", True),
        ("gate_p2_closed", True),
        ("no_glob_confirmed", False),
        ("no_directory_discovery_confirmed", False),
        ("rejection_reasons", ["final_test_marker_forbidden"]),
        ("rejection_reasons", ["path_toctou_detected"]),
        ("rejection_reasons", ["artifact_promotion_forbidden"]),
    ],
)
def test_self_hashed_valid_path_branch_conflict_fails_closed(
    field: str,
    invalid_value: Any,
) -> None:
    manifest = _manifest_obj()
    malformed = _self_hashed_with(
        _path_validation_result(manifest),
        field,
        invalid_value,
        "path_validation_result_id",
    )

    receipt = _build(manifest_obj=manifest, path_validation_result=malformed)

    _assert_malformed_upstream_fails_closed(
        receipt,
        branch="path",
        path_validation_result=malformed,
    )


@pytest.mark.parametrize(
    "mutations",
    [
        {"status": "rejected", "rejection_reasons": []},
        {
            "status": "rejected",
            "rejection_reasons": [],
            "file_identity_check": "supported_pass",
        },
        {"status": "validation_valid"},
        {"status": "scheduled"},
        {"status": "completed"},
    ],
)
def test_self_hashed_malformed_path_rejected_or_invalid_branch_fails_closed(
    mutations: Mapping[str, Any],
) -> None:
    manifest = _manifest_obj()
    malformed = copy.deepcopy(_path_validation_result(manifest))
    malformed.update(copy.deepcopy(dict(mutations)))
    malformed = _recompute_result_id(malformed, "path_validation_result_id")

    receipt = _build(manifest_obj=manifest, path_validation_result=malformed)

    _assert_malformed_upstream_fails_closed(
        receipt,
        branch="path",
        path_validation_result=malformed,
    )


def test_self_hashed_prevalidation_branch_attack_cannot_produce_valid_receipt() -> None:
    manifest = _manifest_obj()
    malformed = _self_hashed_with(
        _prevalidation_result(manifest),
        "schema_valid",
        False,
        "prevalidation_result_id",
    )

    receipt = _build(manifest_obj=manifest, prevalidation_result=malformed)

    _assert_malformed_upstream_fails_closed(
        receipt,
        branch="prevalidation",
        prevalidation_result=malformed,
    )


def test_self_hashed_path_branch_attack_cannot_produce_valid_receipt() -> None:
    manifest = _manifest_obj()
    malformed = _self_hashed_with(
        _path_validation_result(manifest),
        "rejection_reasons",
        ["path_escape"],
        "path_validation_result_id",
    )

    receipt = _build(manifest_obj=manifest, path_validation_result=malformed)

    _assert_malformed_upstream_fails_closed(
        receipt,
        branch="path",
        path_validation_result=malformed,
    )


def test_receipt_id_is_checked_before_malformed_upstream_semantics() -> None:
    manifest = _manifest_obj()
    malformed = _self_hashed_with(
        _prevalidation_result(manifest),
        "schema_valid",
        False,
        "prevalidation_result_id",
    )
    receipt = _build(manifest_obj=manifest, prevalidation_result=malformed)
    receipt["validation_receipt_id"] = "b" * 64

    _assert_verify_rejected(
        _verify(receipt, manifest_obj=manifest, prevalidation_result=malformed),
        "receipt_id",
        "receipt_hash",
    )


def test_rejected_receipt_cannot_omit_malformed_evidence_reason() -> None:
    manifest = _manifest_obj()
    malformed = _self_hashed_with(
        _prevalidation_result(manifest),
        "binding_available",
        False,
        "prevalidation_result_id",
    )
    receipt = _build(manifest_obj=manifest, prevalidation_result=malformed)
    receipt["status"] = "rejected"
    receipt["rejection_reasons"] = []
    receipt = _recompute_receipt_id(receipt)

    _assert_verify_rejected(
        _verify(receipt, manifest_obj=manifest, prevalidation_result=malformed),
        "binding",
        "receipt_body",
        "evidence",
    )


def test_validator_identity_is_content_only_not_authenticated_authority() -> None:
    first = _build(validator_identity="pilot-validator-content-a")
    second = _build(validator_identity="pilot-validator-content-b")

    assert first["validator_identity"] == "pilot-validator-content-a"
    assert second["validator_identity"] == "pilot-validator-content-b"
    assert first["validation_receipt_id"] != second["validation_receipt_id"]
    for forbidden_field in (
        "validator_authorized",
        "trusted_validator",
        "signature_verified",
        "validator_identity_authenticated",
        "validator_authority_proof",
    ):
        assert forbidden_field not in _all_keys(first)
        assert forbidden_field not in _all_keys(second)


# Phase 6B-T5R2: exact upstream evidence-envelope compatibility ------------


def test_real_t3_prevalidation_builder_is_the_positive_control() -> None:
    manifest, upstream = _real_upstream_prevalidation_fixture()

    assert set(upstream) == _REAL_PREVALIDATION_FIELDS
    assert upstream["prevalidation_schema_version"] == _REAL_PREVALIDATION_VERSION
    assert type(upstream["prevalidation_schema_version"]) is str
    assert upstream["prevalidation_result_id"] == _object_hash(
        {
            key: value
            for key, value in upstream.items()
            if key != "prevalidation_result_id"
        }
    )

    receipt = _build(
        manifest_obj=manifest,
        prevalidation_result=upstream,
    )
    _assert_valid_receipt(receipt)
    _assert_verify_valid(
        _verify(
            receipt,
            manifest_obj=manifest,
            prevalidation_result=upstream,
        )
    )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda result: result.pop("prevalidation_schema_version"),
        lambda result: result.__setitem__(
            "prevalidation_schema_version", "pilot-prevalidation-v1"
        ),
        lambda result: result.__setitem__(
            "prevalidation_schema_version", "pilot-prevalidation-core-v0"
        ),
        lambda result: result.__setitem__(
            "prevalidation_schema_version", "pilot-prevalidation-core-v1 "
        ),
        lambda result: result.__setitem__("prevalidation_schema_version", None),
        lambda result: result.__setitem__("prevalidation_schema_version", 1),
        lambda result: result.__setitem__("prevalidation_schema_version", []),
        lambda result: result.__setitem__("prevalidation_schema_version", True),
    ],
    ids=[
        "missing",
        "old_helper_version",
        "wrong_version",
        "trailing_space",
        "none",
        "integer",
        "list",
        "boolean",
    ],
)
def test_real_prevalidation_version_is_required_and_exact(
    mutation: Any,
) -> None:
    manifest, upstream = _real_upstream_prevalidation_fixture()
    malformed = copy.deepcopy(upstream)
    mutation(malformed)
    malformed = _recompute_result_id(malformed, "prevalidation_result_id")

    receipt = _build(manifest_obj=manifest, prevalidation_result=malformed)
    _assert_malformed_upstream_fails_closed(
        receipt,
        branch="prevalidation",
        prevalidation_result=malformed,
    )


@pytest.mark.parametrize(
    "alias",
    [
        "schema_version",
        "validation_schema_version",
        "prevalidation_version",
        "prevalidation_schema_verison",
    ],
)
def test_prevalidation_schema_aliases_and_near_miss_keys_fail_closed(
    alias: str,
) -> None:
    manifest, upstream = _real_upstream_prevalidation_fixture()
    malformed = copy.deepcopy(upstream)
    malformed.pop("prevalidation_schema_version")
    malformed[alias] = _REAL_PREVALIDATION_VERSION
    malformed = _recompute_result_id(malformed, "prevalidation_result_id")

    receipt = _build(manifest_obj=manifest, prevalidation_result=malformed)
    _assert_malformed_upstream_fails_closed(
        receipt,
        branch="prevalidation",
        prevalidation_result=malformed,
    )


@pytest.mark.parametrize(
    "extra_field",
    ["unexpected_upstream_field", "prevalidation_schema_verison"],
)
def test_self_hashed_prevalidation_unknown_fields_fail_closed(
    extra_field: str,
) -> None:
    manifest, upstream = _real_upstream_prevalidation_fixture()
    malformed = copy.deepcopy(upstream)
    malformed[extra_field] = "still-upstream-data"
    malformed = _recompute_result_id(malformed, "prevalidation_result_id")

    receipt = _build(manifest_obj=manifest, prevalidation_result=malformed)
    _assert_malformed_upstream_fails_closed(
        receipt,
        branch="prevalidation",
        prevalidation_result=malformed,
    )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda result: result.pop("path_validation_schema_version"),
        lambda result: result.__setitem__(
            "path_validation_schema_version", "pilot-path-validation-v0"
        ),
        lambda result: result.__setitem__(
            "path_validation_schema_version", "pilot-path-validation-v1 "
        ),
        lambda result: result.__setitem__("path_validation_schema_version", None),
        lambda result: result.__setitem__("path_validation_schema_version", 1),
    ],
    ids=["missing", "wrong_version", "trailing_space", "none", "integer"],
)
def test_path_schema_version_and_type_are_not_silently_ignored(
    mutation: Any,
) -> None:
    manifest = _manifest_obj()
    malformed = copy.deepcopy(_path_validation_result(manifest))
    mutation(malformed)
    malformed = _recompute_result_id(malformed, "path_validation_result_id")

    receipt = _build(manifest_obj=manifest, path_validation_result=malformed)
    _assert_malformed_upstream_fails_closed(
        receipt,
        branch="path",
        path_validation_result=malformed,
    )


@pytest.mark.parametrize(
    "alias",
    [
        "schema_version",
        "validation_schema_version",
        "path_validation_version",
        "path_validation_schema_verison",
    ],
)
def test_path_schema_aliases_and_near_miss_keys_fail_closed(alias: str) -> None:
    manifest = _manifest_obj()
    malformed = copy.deepcopy(_path_validation_result(manifest))
    malformed.pop("path_validation_schema_version")
    malformed[alias] = "pilot-path-validation-v1"
    malformed = _recompute_result_id(malformed, "path_validation_result_id")

    receipt = _build(manifest_obj=manifest, path_validation_result=malformed)
    _assert_malformed_upstream_fails_closed(
        receipt,
        branch="path",
        path_validation_result=malformed,
    )


@pytest.mark.parametrize(
    "extra_field",
    ["unexpected_path_evidence_field", "path_validation_schema_verison"],
)
def test_self_hashed_path_unknown_fields_fail_closed(extra_field: str) -> None:
    manifest = _manifest_obj()
    malformed = copy.deepcopy(_path_validation_result(manifest))
    malformed[extra_field] = "still-path-evidence"
    malformed = _recompute_result_id(malformed, "path_validation_result_id")

    receipt = _build(manifest_obj=manifest, path_validation_result=malformed)
    _assert_malformed_upstream_fails_closed(
        receipt,
        branch="path",
        path_validation_result=malformed,
    )
