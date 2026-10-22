from __future__ import annotations

import builtins
import copy
from datetime import datetime, timezone
import hashlib
import importlib
import json
from pathlib import Path
import re
import struct
from types import ModuleType

import pytest


INTEGRITY_MODULE = "mrta_rect_coverage.experiments.pilot_integrity"
LOWER_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SIGNATURE_FIELDS = {"signature", "signatures"}
JCS_SAFE_INTEGER_MAX = (1 << 53) - 1


def _integrity() -> ModuleType:
    try:
        return importlib.import_module(INTEGRITY_MODULE)
    except ModuleNotFoundError as exc:
        if exc.name == INTEGRITY_MODULE:
            pytest.fail(
                "Phase 6B-T2 RED: pilot scoped-hash integrity module is not implemented"
            )
        raise


def _oracle_canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _oracle_object_hash(value: object) -> str:
    return hashlib.sha256(_oracle_canonical_bytes(value)).hexdigest()


def _oracle_receipt_id(receipt: dict, id_field: str) -> str:
    body = {
        key: value
        for key, value in receipt.items()
        if key != id_field and key not in _SIGNATURE_FIELDS
    }
    return _oracle_object_hash(body)


def _assert_valid(result) -> None:
    assert result.valid is True
    assert tuple(result.rejection_reasons) == ()


def _assert_invalid(result) -> None:
    assert result.valid is False
    assert tuple(result.rejection_reasons)


def _pilot_family_matrix() -> dict:
    return {
        "schema_version": "pilot-family-matrix-v1",
        "matrix_scope": "pilot",
        "families": [
            {
                "family_id": "pilot-family-r2-t6",
                "robots": 2,
                "tasks": 6,
            }
        ],
    }


def _formal_family_matrix() -> dict:
    return {
        "schema_version": "formal-family-matrix-v1",
        "matrix_scope": "formal",
        "families": [
            {
                "family_id": "formal-family-r2-t6",
                "robots": 2,
                "tasks": 6,
            }
        ],
    }


def _pilot_split_rule() -> dict:
    return {
        "schema_version": "pilot-split-rule-v1",
        "matrix_scope": "pilot",
        "assignments": {"pilot-family-r2-t6": "dev"},
    }


def _formal_split_rule() -> dict:
    return {
        "schema_version": "formal-split-rule-v1",
        "matrix_scope": "formal",
        "assignments": {"formal-family-r2-t6": "formal_train"},
    }


def _pilot_manifest() -> dict:
    family_matrix = _pilot_family_matrix()
    split_rule = _pilot_split_rule()
    return {
        "schema_version": "pilot-manifest-schema-v1",
        "manifest_scope": "pilot_nonformal",
        "matrix_scope": "pilot",
        "objective_version": "objective_v1_prototype",
        "family_matrix_hash": _oracle_object_hash(family_matrix),
        "split_assignment_rule_hash": _oracle_object_hash(split_rule),
        "artifact_promotion_allowed": False,
        "formal_identity_version": "pilot-nonformal-v1",
        "pilot_source_reference": None,
        "instances": [
            {
                "instance_id": "pilot-instance-r2-t6-0",
                "family_id": "pilot-family-r2-t6",
                "split": "dev",
                "file_hash": "1" * 64,
                "file_path": "pilot/dev/R2_T6_0.txt",
            }
        ],
    }


def _validation_receipt(manifest: dict) -> dict:
    receipt = {
        "receipt_schema_version": "pilot-validator-v1",
        "status": "validation_valid",
        "manifest_hash": _oracle_object_hash(manifest),
        "manifest_scope": "pilot_nonformal",
        "matrix_scope": "pilot",
        "scope_evidence": {
            "manifest_scope": "pilot_nonformal",
            "matrix_scope": "pilot",
            "decision": "pass",
        },
        "hash_evidence": {
            "manifest_hash_verified": True,
            "family_matrix_hash_verified": True,
            "split_assignment_rule_hash_verified": True,
            "decision": "pass",
        },
    }
    receipt["validation_receipt_id"] = _oracle_receipt_id(
        receipt, "validation_receipt_id"
    )
    return receipt


def _runner_receipt(manifest: dict, validation_receipt: dict) -> dict:
    manifest_hash = _oracle_object_hash(manifest)
    receipt = {
        "receipt_schema_version": "pilot-runner-v1",
        "status": "preflight_validated",
        "accepted_execution": False,
        "manifest_hash": manifest_hash,
        "validation_receipt_id": validation_receipt["validation_receipt_id"],
        "no_real_llm_evidence": {
            "requested_provider_kind": "mock",
            "accepted_provider": "mock",
            "decision": "pass",
        },
        "no_final_test_input_evidence": {
            "final_test_scope_present": False,
            "manifest_scopes_loaded": ["pilot_nonformal"],
            "decision": "pass",
        },
        "no_uncontrolled_glob_evidence": {
            "requested_input_mode": "manifest_file",
            "accepted_input_mode": "manifest_file",
            "glob_detected": False,
            "decision": "pass",
        },
        "manifest_only_evidence": {
            "manifest_hash": manifest_hash,
            "validation_receipt_id": validation_receipt["validation_receipt_id"],
            "decision": "pass",
        },
        "scope_evidence": {
            "manifest_scope": "pilot_nonformal",
            "matrix_scope": "pilot",
            "decision": "pass",
        },
    }
    receipt["runner_receipt_id"] = _oracle_receipt_id(
        receipt, "runner_receipt_id"
    )
    return receipt


def _rejected_runner_receipt(reason: str) -> dict:
    if reason == "real_provider_forbidden":
        receipt = {
            "receipt_schema_version": "pilot-runner-v1",
            "status": "preflight_rejected",
            "accepted_execution": False,
            "rejection_reason": reason,
            "requested_provider_kind": "real",
            "no_real_llm_evidence": {
                "requested_provider_kind": "real",
                "accepted_provider": None,
                "decision": "reject",
            },
        }
    else:
        receipt = {
            "receipt_schema_version": "pilot-runner-v1",
            "status": "preflight_rejected",
            "accepted_execution": False,
            "rejection_reason": "uncontrolled_glob_forbidden",
            "requested_input_mode": "directory_glob",
            "no_uncontrolled_glob_evidence": {
                "requested_input_mode": "directory_glob",
                "accepted_input_mode": None,
                "glob_detected": True,
                "decision": "reject",
            },
        }
    receipt["runner_receipt_id"] = _oracle_receipt_id(
        receipt, "runner_receipt_id"
    )
    return receipt


def test_canonical_json_hash_is_independent_of_object_key_order() -> None:
    integrity = _integrity()
    left = {"b": 2, "a": {"y": 4, "x": 3}}
    right = {"a": {"x": 3, "y": 4}, "b": 2}

    assert integrity.canonical_json_bytes(left) == integrity.canonical_json_bytes(
        right
    )
    assert integrity.compute_object_hash(left) == integrity.compute_object_hash(right)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ({"b": 2, "a": 1}, b'{"a":1,"b":2}'),
        (
            {"z": [3, 2, 1], "a": {"b": True, "a": None}},
            b'{"a":{"a":null,"b":true},"z":[3,2,1]}',
        ),
        (1e-7, b"1e-7"),
        (1e-6, b"0.000001"),
        (4.50, b"4.5"),
        (-0.0, b"0"),
        ({"text": "汉字"}, b'{"text":"\xe6\xb1\x89\xe5\xad\x97"}'),
        ({"text": "line\n\x00"}, b'{"text":"line\\n\\u0000"}'),
    ],
    ids=[
        "sorted_keys_without_whitespace",
        "nested_ordering",
        "small_exponent_without_leading_zero",
        "decimal_threshold",
        "strip_redundant_fraction_zero",
        "negative_zero_is_zero",
        "unicode_is_utf8",
        "control_characters_are_escaped",
    ],
)
def test_canonical_json_matches_handwritten_rfc8785_jcs_vectors(
    value: object, expected: bytes
) -> None:
    """Use independent bytes, not the local json.dumps-based test oracle."""

    integrity = _integrity()

    assert integrity.canonical_json_bytes(value) == expected


def _binary64_from_hex(bit_pattern: str) -> float:
    """Construct an RFC 8785 Appendix-B value without using the implementation."""

    return struct.unpack(">d", bytes.fromhex(bit_pattern))[0]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (-JCS_SAFE_INTEGER_MAX, b"-9007199254740991"),
        (0, b"0"),
        (JCS_SAFE_INTEGER_MAX, b"9007199254740991"),
    ],
    ids=["minimum_safe_integer", "zero", "maximum_safe_integer"],
)
def test_canonical_json_accepts_python_int_at_safe_interoperable_boundary(
    value: int, expected: bytes
) -> None:
    integrity = _integrity()

    assert integrity.canonical_json_bytes(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        -(1 << 53),
        1 << 53,
        -(1 << 68),
        1 << 68,
        -((1 << 100) + 1),
        (1 << 100) + 1,
    ],
    ids=[
        "just_below_safe_minimum",
        "just_above_safe_maximum",
        "negative_appendix_b_2_pow_68",
        "appendix_b_2_pow_68",
        "negative_arbitrary_precision_integer",
        "arbitrary_precision_integer",
    ],
)
def test_canonical_json_rejects_python_int_outside_safe_interoperable_domain(
    value: int,
) -> None:
    integrity = _integrity()

    with pytest.raises((TypeError, ValueError)):
        integrity.canonical_json_bytes(value)


@pytest.mark.parametrize(
    "value",
    [
        {"unsafe_integer": 1 << 53},
        ["nested", {"unsafe_integer": -(1 << 68)}],
    ],
    ids=["object_member", "nested_array_object_member"],
)
def test_canonical_json_rejects_nested_python_int_outside_safe_domain(
    value: object,
) -> None:
    integrity = _integrity()

    with pytest.raises((TypeError, ValueError)):
        integrity.canonical_json_bytes(value)


@pytest.mark.parametrize(
    ("ieee754_hex", "expected"),
    [
        ("0000000000000000", b"0"),
        ("8000000000000000", b"0"),
        ("0000000000000001", b"5e-324"),
        ("8000000000000001", b"-5e-324"),
        ("7fefffffffffffff", b"1.7976931348623157e+308"),
        ("ffefffffffffffff", b"-1.7976931348623157e+308"),
        ("4340000000000000", b"9007199254740992"),
        ("c340000000000000", b"-9007199254740992"),
        ("4430000000000000", b"295147905179352830000"),
        ("44b52d02c7e14af5", b"9.999999999999997e+22"),
        ("44b52d02c7e14af6", b"1e+23"),
        ("44b52d02c7e14af7", b"1.0000000000000001e+23"),
        ("444b1ae4d6e2ef4e", b"999999999999999700000"),
        ("444b1ae4d6e2ef4f", b"999999999999999900000"),
        ("444b1ae4d6e2ef50", b"1e+21"),
        ("3eb0c6f7a0b5ed8c", b"9.999999999999997e-7"),
        ("3eb0c6f7a0b5ed8d", b"0.000001"),
        ("43143ff3c1cb0959", b"1424953923781206.2"),
    ],
    ids=[
        "zero",
        "negative_zero",
        "minimum_positive_number",
        "minimum_negative_number",
        "maximum_positive_number",
        "maximum_negative_number",
        "positive_2_pow_53",
        "negative_2_pow_53",
        "approximately_2_pow_68",
        "below_1e23",
        "exact_1e23",
        "above_1e23",
        "fixed_notation_lower_neighbor",
        "fixed_notation_upper_neighbor",
        "scientific_notation_threshold",
        "below_fixed_decimal_threshold",
        "fixed_decimal_threshold",
        "round_to_even",
    ],
)
def test_canonical_json_matches_rfc8785_appendix_b_binary64_vectors(
    ieee754_hex: str, expected: bytes
) -> None:
    integrity = _integrity()

    assert integrity.canonical_json_bytes(_binary64_from_hex(ieee754_hex)) == expected


def test_canonical_json_preserves_array_order_in_hash() -> None:
    integrity = _integrity()

    assert integrity.compute_object_hash(["a", "b"]) != integrity.compute_object_hash(
        ["b", "a"]
    )


@pytest.mark.parametrize(
    ("left", "right"),
    [
        (1, "1"),
        (True, "true"),
        ({"value": None}, {}),
    ],
)
def test_canonical_hash_preserves_json_type_and_missing_field_distinctions(
    left: object, right: object
) -> None:
    integrity = _integrity()

    assert integrity.compute_object_hash(left) != integrity.compute_object_hash(right)


@pytest.mark.parametrize(
    "invalid_value",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
        b"bytes-are-not-json",
        {"set-member"},
        ("tuple",),
        object(),
        datetime(2026, 8, 12, tzinfo=timezone.utc),
    ],
    ids=[
        "nan",
        "infinity",
        "negative_infinity",
        "bytes",
        "set",
        "tuple",
        "object",
        "datetime",
    ],
)
def test_canonical_json_rejects_non_json_or_nonfinite_values(
    invalid_value: object,
) -> None:
    integrity = _integrity()

    with pytest.raises((TypeError, ValueError)):
        integrity.canonical_json_bytes(invalid_value)


def test_sha256_hex_bytes_returns_canonical_lowercase_digest() -> None:
    integrity = _integrity()

    digest = integrity.sha256_hex_bytes(b"pilot-scoped-hash")

    assert LOWER_SHA256_RE.fullmatch(digest)
    assert digest == hashlib.sha256(b"pilot-scoped-hash").hexdigest()


@pytest.mark.parametrize(
    "invalid_digest",
    ["", "A" * 64, "g" * 64, "a" * 63],
    ids=["empty", "uppercase", "non_hex", "wrong_length"],
)
def test_sha256_format_validation_fails_closed(invalid_digest: str) -> None:
    integrity = _integrity()

    _assert_invalid(integrity.validate_sha256_hex(invalid_digest))


def test_valid_pilot_manifest_binds_pilot_matrix_and_split_rule_hashes() -> None:
    integrity = _integrity()

    result = integrity.verify_pilot_scoped_hash_binding(
        _pilot_manifest(), _pilot_family_matrix(), _pilot_split_rule()
    )

    _assert_valid(result)


def test_pilot_family_matrix_hash_mismatch_is_rejected() -> None:
    integrity = _integrity()
    manifest = _pilot_manifest()
    manifest["family_matrix_hash"] = "2" * 64

    _assert_invalid(
        integrity.verify_pilot_scoped_hash_binding(
            manifest, _pilot_family_matrix(), _pilot_split_rule()
        )
    )


def test_formal_family_matrix_cannot_satisfy_pilot_hash_binding() -> None:
    integrity = _integrity()
    manifest = _pilot_manifest()
    formal_matrix = _formal_family_matrix()
    manifest["family_matrix_hash"] = _oracle_object_hash(formal_matrix)

    _assert_invalid(
        integrity.verify_pilot_scoped_hash_binding(
            manifest, formal_matrix, _pilot_split_rule()
        )
    )


def test_pilot_manifest_with_formal_matrix_scope_is_rejected() -> None:
    integrity = _integrity()
    manifest = _pilot_manifest()
    manifest["matrix_scope"] = "formal"

    _assert_invalid(
        integrity.verify_pilot_scoped_hash_binding(
            manifest, _pilot_family_matrix(), _pilot_split_rule()
        )
    )


def test_pilot_split_assignment_rule_hash_mismatch_is_rejected() -> None:
    integrity = _integrity()
    manifest = _pilot_manifest()
    manifest["split_assignment_rule_hash"] = "3" * 64

    _assert_invalid(
        integrity.verify_pilot_scoped_hash_binding(
            manifest, _pilot_family_matrix(), _pilot_split_rule()
        )
    )


def test_formal_split_rule_cannot_satisfy_pilot_hash_binding() -> None:
    integrity = _integrity()
    manifest = _pilot_manifest()
    formal_rule = _formal_split_rule()
    manifest["split_assignment_rule_hash"] = _oracle_object_hash(formal_rule)

    _assert_invalid(
        integrity.verify_pilot_scoped_hash_binding(
            manifest, _pilot_family_matrix(), formal_rule
        )
    )


@pytest.mark.parametrize(
    "forbidden_field",
    [
        "full_formal_family_matrix_hash",
        "formal_family_matrix_hash",
        "formal_split_assignment_rule_hash",
        "final_test_manifest_hash",
    ],
)
def test_pilot_manifest_rejects_formal_scoped_hash_fields(
    forbidden_field: str,
) -> None:
    integrity = _integrity()
    manifest = _pilot_manifest()
    manifest[forbidden_field] = "4" * 64

    _assert_invalid(
        integrity.verify_pilot_scoped_hash_binding(
            manifest, _pilot_family_matrix(), _pilot_split_rule()
        )
    )


@pytest.mark.parametrize(
    ("field_path", "marker"),
    [
        (("instances", 0, "split"), "formal_final_test"),
        (("instances", 0, "family_id"), "formal-final-test-family-r2-t6"),
        (("final_test_hash_marker",), "5" * 64),
    ],
)
def test_pilot_manifest_rejects_formal_or_final_test_markers(
    field_path: tuple, marker: str
) -> None:
    integrity = _integrity()
    manifest = _pilot_manifest()
    target = manifest
    for part in field_path[:-1]:
        target = target[part]
    target[field_path[-1]] = marker

    _assert_invalid(
        integrity.verify_pilot_scoped_hash_binding(
            manifest, _pilot_family_matrix(), _pilot_split_rule()
        )
    )


@pytest.mark.parametrize("formal_split", ["formal_train", "formal_dev"])
def test_pilot_manifest_rejects_formal_split_in_instance_record(
    formal_split: str,
) -> None:
    integrity = _integrity()
    manifest = _pilot_manifest()
    manifest["instances"][0]["split"] = formal_split

    _assert_invalid(
        integrity.verify_pilot_scoped_hash_binding(
            manifest, _pilot_family_matrix(), _pilot_split_rule()
        )
    )


@pytest.mark.parametrize(
    ("semantic_field", "formal_marker"),
    [
        ("manifest_scope", "formal_train"),
        ("split", "formal_dev"),
        ("lockbox_scope", "formal_final_test"),
    ],
)
def test_pilot_manifest_rejects_nested_formal_scope_semantics(
    semantic_field: str, formal_marker: str
) -> None:
    integrity = _integrity()
    manifest = _pilot_manifest()
    manifest["instances"][0]["scope_metadata"] = {
        semantic_field: formal_marker
    }

    _assert_invalid(
        integrity.verify_pilot_scoped_hash_binding(
            manifest, _pilot_family_matrix(), _pilot_split_rule()
        )
    )


@pytest.mark.parametrize("formal_scope", ["formal_train", "formal_dev"])
def test_top_level_pilot_manifest_rejects_formal_manifest_scope(
    formal_scope: str,
) -> None:
    integrity = _integrity()
    manifest = _pilot_manifest()
    manifest["manifest_scope"] = formal_scope

    _assert_invalid(
        integrity.verify_pilot_scoped_hash_binding(
            manifest, _pilot_family_matrix(), _pilot_split_rule()
        )
    )


def test_pilot_artifact_promotion_flag_true_is_rejected() -> None:
    integrity = _integrity()
    manifest = _pilot_manifest()
    manifest["artifact_promotion_allowed"] = True

    _assert_invalid(
        integrity.verify_pilot_scoped_hash_binding(
            manifest, _pilot_family_matrix(), _pilot_split_rule()
        )
    )


def test_relabeling_pilot_manifest_as_formal_does_not_promote_same_identity() -> None:
    integrity = _integrity()
    relabeled = _pilot_manifest()
    relabeled["manifest_scope"] = "formal_train"
    relabeled["instances"][0]["split"] = "formal_train"

    _assert_invalid(
        integrity.verify_pilot_scoped_hash_binding(
            relabeled, _pilot_family_matrix(), _pilot_split_rule()
        )
    )


def test_formal_artifact_with_pilot_source_reference_is_rejected() -> None:
    integrity = _integrity()
    formal = _pilot_manifest()
    formal["manifest_scope"] = "formal_train"
    formal["matrix_scope"] = "formal"
    formal["pilot_source_reference"] = "pilot-manifest-001"

    _assert_invalid(
        integrity.verify_pilot_scoped_hash_binding(
            formal, _pilot_family_matrix(), _pilot_split_rule()
        )
    )


def test_formal_artifact_cannot_reuse_pilot_audit_hash_fields() -> None:
    integrity = _integrity()
    formal = _pilot_manifest()
    formal["manifest_scope"] = "formal_train"
    formal["matrix_scope"] = "formal"
    formal["pilot_family_matrix_hash"] = formal["family_matrix_hash"]
    formal["pilot_split_assignment_rule_hash"] = formal[
        "split_assignment_rule_hash"
    ]

    _assert_invalid(
        integrity.verify_pilot_scoped_hash_binding(
            formal, _pilot_family_matrix(), _pilot_split_rule()
        )
    )


def test_validator_receipt_binds_current_manifest_canonical_hash() -> None:
    integrity = _integrity()
    manifest = _pilot_manifest()
    receipt = _validation_receipt(manifest)

    _assert_valid(integrity.verify_manifest_receipt_binding(manifest, receipt))


def test_changed_manifest_invalidates_unchanged_validator_receipt() -> None:
    integrity = _integrity()
    manifest = _pilot_manifest()
    receipt = _validation_receipt(manifest)
    changed = copy.deepcopy(manifest)
    changed["instances"][0]["file_hash"] = "6" * 64

    _assert_invalid(integrity.verify_manifest_receipt_binding(changed, receipt))


def test_validator_receipt_manifest_hash_mismatch_is_rejected() -> None:
    integrity = _integrity()
    manifest = _pilot_manifest()
    receipt = _validation_receipt(manifest)
    receipt["manifest_hash"] = "7" * 64
    receipt["validation_receipt_id"] = _oracle_receipt_id(
        receipt, "validation_receipt_id"
    )

    _assert_invalid(integrity.verify_manifest_receipt_binding(manifest, receipt))


def test_validator_receipt_missing_manifest_hash_is_rejected() -> None:
    integrity = _integrity()
    manifest = _pilot_manifest()
    receipt = _validation_receipt(manifest)
    receipt.pop("manifest_hash")

    _assert_invalid(integrity.verify_manifest_receipt_binding(manifest, receipt))


def test_validation_receipt_id_excludes_id_and_signature_fields() -> None:
    integrity = _integrity()
    receipt = _validation_receipt(_pilot_manifest())
    receipt["signature"] = "detached-signature"
    receipt["signatures"] = ["secondary-signature"]
    expected = _oracle_receipt_id(receipt, "validation_receipt_id")

    assert integrity.compute_validation_receipt_id(receipt) == expected


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("status", "validation_rejected"),
        ("scope_evidence", {"decision": "reject", "manifest_scope": "formal_train"}),
    ],
)
def test_validation_receipt_body_change_invalidates_old_id(
    field: str, value: object
) -> None:
    integrity = _integrity()
    manifest = _pilot_manifest()
    receipt = _validation_receipt(manifest)
    receipt[field] = value

    _assert_invalid(integrity.verify_manifest_receipt_binding(manifest, receipt))


def test_validation_receipt_id_cannot_include_itself_in_hash_preimage() -> None:
    integrity = _integrity()
    manifest = _pilot_manifest()
    receipt = _validation_receipt(manifest)
    receipt["validation_receipt_id"] = _oracle_object_hash(receipt)

    _assert_invalid(integrity.verify_manifest_receipt_binding(manifest, receipt))


def test_runner_receipt_binds_validator_receipt_and_manifest() -> None:
    integrity = _integrity()
    manifest = _pilot_manifest()
    validator = _validation_receipt(manifest)
    runner = _runner_receipt(manifest, validator)

    _assert_valid(integrity.verify_runner_receipt_binding(validator, runner))


def test_runner_top_level_and_manifest_evidence_receipt_ids_must_match() -> None:
    integrity = _integrity()
    manifest = _pilot_manifest()
    validator = _validation_receipt(manifest)
    runner = _runner_receipt(manifest, validator)
    runner["manifest_only_evidence"]["validation_receipt_id"] = "8" * 64
    runner["runner_receipt_id"] = _oracle_receipt_id(runner, "runner_receipt_id")

    _assert_invalid(integrity.verify_runner_receipt_binding(validator, runner))


def test_changed_validator_receipt_invalidates_runner_reference_to_old_id() -> None:
    integrity = _integrity()
    manifest = _pilot_manifest()
    validator = _validation_receipt(manifest)
    runner = _runner_receipt(manifest, validator)
    changed_validator = copy.deepcopy(validator)
    changed_validator["hash_evidence"]["decision"] = "reject"

    _assert_invalid(
        integrity.verify_runner_receipt_binding(changed_validator, runner)
    )


def test_runner_and_validator_manifest_hashes_must_match() -> None:
    integrity = _integrity()
    manifest = _pilot_manifest()
    validator = _validation_receipt(manifest)
    runner = _runner_receipt(manifest, validator)
    runner["manifest_hash"] = "9" * 64
    runner["manifest_only_evidence"]["manifest_hash"] = "9" * 64
    runner["runner_receipt_id"] = _oracle_receipt_id(runner, "runner_receipt_id")

    _assert_invalid(integrity.verify_runner_receipt_binding(validator, runner))


_MISSING = object()


@pytest.mark.parametrize(
    "invalid_manifest_hash",
    [_MISSING, None, "", "not-a-hash", "A" * 64, "a" * 63],
    ids=["missing", "null", "empty", "non_hex", "uppercase", "wrong_length"],
)
def test_cross_receipt_binding_rejects_equal_but_invalid_manifest_hashes(
    invalid_manifest_hash: object,
) -> None:
    integrity = _integrity()
    manifest = _pilot_manifest()
    validator = _validation_receipt(manifest)
    runner = _runner_receipt(manifest, validator)

    if invalid_manifest_hash is _MISSING:
        validator.pop("manifest_hash")
        runner.pop("manifest_hash")
        runner["manifest_only_evidence"].pop("manifest_hash")
    else:
        validator["manifest_hash"] = invalid_manifest_hash
        runner["manifest_hash"] = invalid_manifest_hash
        runner["manifest_only_evidence"]["manifest_hash"] = invalid_manifest_hash

    validator["validation_receipt_id"] = _oracle_receipt_id(
        validator, "validation_receipt_id"
    )
    runner["validation_receipt_id"] = validator["validation_receipt_id"]
    runner["manifest_only_evidence"]["validation_receipt_id"] = validator[
        "validation_receipt_id"
    ]
    runner["runner_receipt_id"] = _oracle_receipt_id(runner, "runner_receipt_id")

    _assert_invalid(integrity.verify_runner_receipt_binding(validator, runner))


@pytest.mark.parametrize(
    "invalid_receipt_id",
    [_MISSING, None, "", "not-a-hash"],
    ids=["missing", "null", "empty", "non_hex"],
)
def test_runner_top_level_validation_receipt_id_fails_closed_even_when_evidence_matches(
    invalid_receipt_id: object,
) -> None:
    integrity = _integrity()
    manifest = _pilot_manifest()
    validator = _validation_receipt(manifest)
    runner = _runner_receipt(manifest, validator)

    if invalid_receipt_id is _MISSING:
        runner.pop("validation_receipt_id")
        runner["manifest_only_evidence"].pop("validation_receipt_id")
    else:
        runner["validation_receipt_id"] = invalid_receipt_id
        runner["manifest_only_evidence"]["validation_receipt_id"] = (
            invalid_receipt_id
        )
    runner["runner_receipt_id"] = _oracle_receipt_id(runner, "runner_receipt_id")

    _assert_invalid(integrity.verify_runner_receipt_binding(validator, runner))


@pytest.mark.parametrize(
    "invalid_evidence_receipt_id",
    [_MISSING, None, "", "not-a-hash"],
    ids=["missing", "null", "empty", "non_hex"],
)
def test_manifest_only_evidence_validation_receipt_id_fails_closed(
    invalid_evidence_receipt_id: object,
) -> None:
    integrity = _integrity()
    manifest = _pilot_manifest()
    validator = _validation_receipt(manifest)
    runner = _runner_receipt(manifest, validator)

    if invalid_evidence_receipt_id is _MISSING:
        runner["manifest_only_evidence"].pop("validation_receipt_id")
    else:
        runner["manifest_only_evidence"]["validation_receipt_id"] = (
            invalid_evidence_receipt_id
        )
    runner["runner_receipt_id"] = _oracle_receipt_id(runner, "runner_receipt_id")

    _assert_invalid(integrity.verify_runner_receipt_binding(validator, runner))


def test_runner_receipt_id_excludes_id_and_signature_fields() -> None:
    integrity = _integrity()
    manifest = _pilot_manifest()
    validator = _validation_receipt(manifest)
    runner = _runner_receipt(manifest, validator)
    runner["signature"] = "detached-signature"
    runner["signatures"] = ["secondary-signature"]
    expected = _oracle_receipt_id(runner, "runner_receipt_id")

    assert integrity.compute_runner_receipt_id(runner) == expected


@pytest.mark.parametrize(
    "evidence_field",
    [
        "no_real_llm_evidence",
        "no_final_test_input_evidence",
        "no_uncontrolled_glob_evidence",
        "manifest_only_evidence",
        "scope_evidence",
    ],
)
def test_every_runner_evidence_object_is_bound_into_receipt_id(
    evidence_field: str,
) -> None:
    integrity = _integrity()
    manifest = _pilot_manifest()
    validator = _validation_receipt(manifest)
    runner = _runner_receipt(manifest, validator)
    runner[evidence_field]["audit_mutation"] = "changed-after-id-was-issued"

    _assert_invalid(integrity.verify_runner_receipt_id(runner))


def test_runner_receipt_cannot_hash_only_top_level_state() -> None:
    integrity = _integrity()
    manifest = _pilot_manifest()
    validator = _validation_receipt(manifest)
    runner = _runner_receipt(manifest, validator)
    top_level_only = {
        key: value
        for key, value in runner.items()
        if not key.endswith("_evidence") and key != "runner_receipt_id"
    }
    runner["runner_receipt_id"] = _oracle_object_hash(top_level_only)

    _assert_invalid(integrity.verify_runner_receipt_id(runner))


@pytest.mark.parametrize(
    ("reason", "mutation_path", "mutated_value"),
    [
        ("real_provider_forbidden", ("requested_provider_kind",), "mock"),
        (
            "uncontrolled_glob_forbidden",
            ("no_uncontrolled_glob_evidence", "glob_detected"),
            False,
        ),
    ],
)
def test_rejected_runner_receipt_body_changes_invalidate_old_id(
    reason: str, mutation_path: tuple[str, ...], mutated_value: object
) -> None:
    integrity = _integrity()
    runner = _rejected_runner_receipt(reason)
    target = runner
    for part in mutation_path[:-1]:
        target = target[part]
    target[mutation_path[-1]] = mutated_value

    _assert_invalid(integrity.verify_runner_receipt_id(runner))


def _forbid_file_access(*args, **kwargs):
    raise AssertionError("T2 integrity verification must not read a file path")


def _block_all_file_reads(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(builtins, "open", _forbid_file_access)
    monkeypatch.setattr(Path, "open", _forbid_file_access)
    monkeypatch.setattr(Path, "read_bytes", _forbid_file_access)
    monkeypatch.setattr(Path, "read_text", _forbid_file_access)


def test_explicit_bytes_binding_does_not_read_file_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _block_all_file_reads(monkeypatch)
    integrity = _integrity()
    content = b"pilot-instance-bytes"
    record = {
        "file_path": "pilot/dev/R2_T6_0.txt",
        "file_hash": hashlib.sha256(content).hexdigest(),
    }

    _assert_valid(
        integrity.verify_explicit_content_binding(record, explicit_bytes=content)
    )


def test_file_path_without_explicit_content_fails_closed_without_reading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _block_all_file_reads(monkeypatch)
    integrity = _integrity()
    record = {
        "file_path": "pilot/dev/R2_T6_0.txt",
        "file_hash": "a" * 64,
    }

    _assert_invalid(integrity.verify_explicit_content_binding(record))


def test_explicit_object_binding_uses_provided_object_not_file_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _block_all_file_reads(monkeypatch)
    integrity = _integrity()
    explicit_object = {"robots": 2, "tasks": 6, "replicate": 0}
    record = {
        "file_path": "pilot/dev/R2_T6_0.json",
        "file_hash": _oracle_object_hash(explicit_object),
    }

    _assert_valid(
        integrity.verify_explicit_content_binding(
            record, explicit_object=explicit_object
        )
    )


def test_final_test_path_marker_fails_closed_without_file_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _block_all_file_reads(monkeypatch)
    integrity = _integrity()
    content = b"must-not-be-read-or-used"
    record = {
        "file_path": "formal_final_test/locked-instance.txt",
        "file_hash": hashlib.sha256(content).hexdigest(),
    }

    _assert_invalid(
        integrity.verify_explicit_content_binding(record, explicit_bytes=content)
    )


# Phase 6B-T2R3 coverage-only closure: these tests directly observe that the
# safe-integer rule reaches every public hash/receipt entry point.  The frozen
# version means RFC 8785/JCS serialization plus fail-closed safe integers; it
# does not implicitly coerce arbitrary Python integers to binary64.
_INTEGER_DOMAIN_ERROR_RE = (
    r"(?i)(canonicalization|integer.?domain|jcs|unsupported.*integer)"
)


@pytest.mark.parametrize(
    "value",
    [
        {"n": 1 << 68},
        [1, 1 << 68],
        {"outer": {"n": 1 << 68}},
    ],
    ids=["object", "array", "nested_object"],
)
def test_compute_object_hash_rejects_unsupported_integer_domain(
    value: object,
) -> None:
    integrity = _integrity()

    with pytest.raises((TypeError, ValueError), match=_INTEGER_DOMAIN_ERROR_RE):
        integrity.compute_object_hash(value)


def test_compute_object_hash_rejects_unsupported_integer_before_digest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    integrity = _integrity()
    digest_started = False

    def _forbid_digest(_data: bytes) -> str:
        nonlocal digest_started
        digest_started = True
        raise AssertionError("digest must not start for a non-canonical preimage")

    monkeypatch.setattr(integrity, "sha256_hex_bytes", _forbid_digest)

    with pytest.raises((TypeError, ValueError), match=_INTEGER_DOMAIN_ERROR_RE):
        integrity.compute_object_hash({"n": 1 << 68})

    assert digest_started is False


@pytest.mark.parametrize(
    "location",
    ["evidence", "status_adjacent", "nested"],
)
def test_validation_receipt_id_preimage_rejects_unsupported_integer(
    location: str,
) -> None:
    integrity = _integrity()
    receipt = _validation_receipt(_pilot_manifest())
    if location == "evidence":
        receipt["scope_evidence"]["unsupported_integer"] = 1 << 68
    elif location == "status_adjacent":
        receipt["status_adjacent_integer"] = 1 << 68
    else:
        receipt["hash_evidence"]["nested"] = {"n": 1 << 68}

    with pytest.raises((TypeError, ValueError), match=_INTEGER_DOMAIN_ERROR_RE):
        integrity.compute_validation_receipt_id(receipt)


@pytest.mark.parametrize(
    "evidence_field",
    [
        "no_real_llm_evidence",
        "no_final_test_input_evidence",
        "no_uncontrolled_glob_evidence",
        "manifest_only_evidence",
        "scope_evidence",
    ],
)
def test_runner_receipt_id_preimage_rejects_unsupported_integer_in_evidence(
    evidence_field: str,
) -> None:
    integrity = _integrity()
    manifest = _pilot_manifest()
    validator = _validation_receipt(manifest)
    runner = _runner_receipt(manifest, validator)
    runner[evidence_field]["unsupported_integer"] = 1 << 68

    with pytest.raises((TypeError, ValueError), match=_INTEGER_DOMAIN_ERROR_RE):
        integrity.compute_runner_receipt_id(runner)


@pytest.mark.parametrize(
    "field",
    ["requested_status_adjacent_integer", "accepted_status_adjacent_integer"],
)
def test_runner_receipt_id_preimage_rejects_unsupported_adjacent_integer(
    field: str,
) -> None:
    integrity = _integrity()
    manifest = _pilot_manifest()
    validator = _validation_receipt(manifest)
    runner = _runner_receipt(manifest, validator)
    runner[field] = 1 << 68

    with pytest.raises((TypeError, ValueError), match=_INTEGER_DOMAIN_ERROR_RE):
        integrity.compute_runner_receipt_id(runner)


@pytest.mark.parametrize(
    "location",
    [
        "validator_body",
        "runner_body",
        "manifest_only_evidence",
        "no_real_llm_evidence",
    ],
)
def test_runner_receipt_binding_structurally_rejects_unsupported_integer(
    location: str,
) -> None:
    integrity = _integrity()
    manifest = _pilot_manifest()
    validator = _validation_receipt(manifest)
    runner = _runner_receipt(manifest, validator)
    if location == "validator_body":
        validator["scope_evidence"]["unsupported_integer"] = 1 << 68
    elif location == "runner_body":
        runner["status_adjacent_integer"] = 1 << 68
    else:
        runner[location]["unsupported_integer"] = 1 << 68

    result = integrity.verify_runner_receipt_binding(validator, runner)

    _assert_invalid(result)
    assert any(
        re.search(
            r"(?i)(non_canonical_json|canonicalization_integer_domain|"
            r"unsupported_integer_domain)",
            reason,
        )
        for reason in result.rejection_reasons
    )


def test_canonicalization_algorithm_and_safe_integer_version_are_frozen() -> None:
    integrity = _integrity()

    assert integrity.CANONICALIZATION_ALGORITHM == "RFC8785-JCS"
    assert isinstance(integrity.CANONICALIZATION_VERSION, str)
    assert integrity.CANONICALIZATION_VERSION
    assert integrity.CANONICALIZATION_VERSION == "jcs-v1-safe-int-domain"
