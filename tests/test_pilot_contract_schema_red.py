from __future__ import annotations

import copy
import importlib
import json
from pathlib import Path
from types import ModuleType

import pytest


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "pilot_contracts"
CONTRACT_MODULE = "mrta_rect_coverage.experiments.pilot_contracts"


def _fixture(name: str) -> dict:
    payload = json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _contracts() -> ModuleType:
    try:
        return importlib.import_module(CONTRACT_MODULE)
    except ModuleNotFoundError as exc:
        if exc.name == CONTRACT_MODULE:
            pytest.fail(
                "Phase 6B-T1 RED: pilot schema contract module is not implemented"
            )
        raise


def _assert_valid(result) -> None:
    assert result.valid is True
    assert tuple(result.rejection_reasons) == ()


def _assert_rejected(result, expected_reason: str) -> None:
    assert result.valid is False
    assert expected_reason in tuple(result.rejection_reasons)


def _assert_invalid(result) -> None:
    assert result.valid is False


def test_schema_fixtures_are_json_objects() -> None:
    fixture_names = {
        "valid_pilot_manifest.json",
        "valid_manifest_validation_receipt.json",
        "rejected_manifest_validation_receipt.json",
        "preflight_validated_runner_receipt.json",
        "rejected_glob_runner_receipt.json",
    }

    assert {path.name for path in FIXTURE_ROOT.glob("*.json")} == fixture_names
    assert all(_fixture(name) for name in fixture_names)


def test_valid_pilot_manifest_fixture_is_accepted() -> None:
    result = _contracts().validate_pilot_manifest_schema(
        _fixture("valid_pilot_manifest.json")
    )
    _assert_valid(result)


@pytest.mark.parametrize(
    "field_name",
    [
        "manifest_scope",
        "matrix_scope",
        "artifact_promotion_allowed",
        "family_matrix_hash",
        "split_assignment_rule_hash",
        "instances",
    ],
)
def test_manifest_missing_required_header_field_is_rejected(field_name: str) -> None:
    payload = _fixture("valid_pilot_manifest.json")
    payload.pop(field_name)

    result = _contracts().validate_pilot_manifest_schema(payload)

    _assert_rejected(result, "missing_required_field")


@pytest.mark.parametrize(
    "field_name",
    [
        "instance_id",
        "family_id",
        "split",
        "travel_speed",
        "artifact_promotion_allowed",
        "file_hash",
    ],
)
def test_manifest_missing_required_instance_field_is_rejected(
    field_name: str,
) -> None:
    payload = _fixture("valid_pilot_manifest.json")
    payload["instances"][0].pop(field_name)

    result = _contracts().validate_pilot_manifest_schema(payload)

    _assert_rejected(result, "missing_required_field")


@pytest.mark.parametrize("location", ["header", "instance"])
def test_manifest_unknown_field_is_rejected(location: str) -> None:
    payload = _fixture("valid_pilot_manifest.json")
    target = payload if location == "header" else payload["instances"][0]
    target["unexpected_field"] = "must fail closed"

    result = _contracts().validate_pilot_manifest_schema(payload)

    _assert_rejected(result, "unknown_field")


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("manifest_scope", 1),
        ("matrix_scope", ["pilot"]),
        ("instance_count", True),
        ("family_matrix_hash", None),
    ],
)
def test_manifest_header_wrong_json_type_is_rejected(
    field_name: str, invalid_value
) -> None:
    payload = _fixture("valid_pilot_manifest.json")
    payload[field_name] = invalid_value

    result = _contracts().validate_pilot_manifest_schema(payload)

    _assert_rejected(result, "invalid_field_type")


@pytest.mark.parametrize(
    ("field_name", "invalid_value", "expected_reason"),
    [
        ("robots", True, "invalid_field_type"),
        ("tasks", "6", "invalid_field_type"),
        ("travel_speed", 0.0, "invalid_field_value"),
        ("turning_time", -1.0, "invalid_field_value"),
        ("replicate_id", -1, "invalid_field_value"),
        ("artifact_promotion_allowed", None, "artifact_promotion_forbidden"),
    ],
)
def test_manifest_instance_wrong_type_or_numeric_domain_is_rejected(
    field_name: str, invalid_value, expected_reason: str
) -> None:
    payload = _fixture("valid_pilot_manifest.json")
    payload["instances"][0][field_name] = invalid_value

    result = _contracts().validate_pilot_manifest_schema(payload)

    _assert_rejected(result, expected_reason)


@pytest.mark.parametrize(
    "forbidden_scope", ["formal_train", "formal_dev", "formal_final_test"]
)
def test_pilot_validator_rejects_formal_manifest_scope(
    forbidden_scope: str,
) -> None:
    payload = _fixture("valid_pilot_manifest.json")
    payload["manifest_scope"] = forbidden_scope

    result = _contracts().validate_pilot_manifest_schema(payload)

    _assert_rejected(result, "forbidden_manifest_scope")


def test_pilot_scope_requires_pilot_matrix_scope() -> None:
    payload = _fixture("valid_pilot_manifest.json")
    payload["matrix_scope"] = "formal"

    result = _contracts().validate_pilot_manifest_schema(payload)

    _assert_rejected(result, "invalid_scope_combination")


@pytest.mark.parametrize("promotion_value", [True, "true", 1, None])
def test_pilot_artifact_promotion_is_always_rejected(promotion_value) -> None:
    payload = _fixture("valid_pilot_manifest.json")
    payload["artifact_promotion_allowed"] = promotion_value

    result = _contracts().validate_pilot_manifest_schema(payload)

    _assert_rejected(result, "artifact_promotion_forbidden")


@pytest.mark.parametrize(
    "fixture_name",
    [
        "valid_manifest_validation_receipt.json",
        "rejected_manifest_validation_receipt.json",
    ],
)
def test_validator_receipt_union_accepts_both_schema_branches(
    fixture_name: str,
) -> None:
    result = _contracts().validate_manifest_validation_receipt_schema(
        _fixture(fixture_name)
    )
    _assert_valid(result)


def test_validator_receipt_type_and_status_must_match() -> None:
    payload = _fixture("valid_manifest_validation_receipt.json")
    payload["status"] = "rejected"

    result = _contracts().validate_manifest_validation_receipt_schema(payload)

    _assert_rejected(result, "receipt_type_status_mismatch")


@pytest.mark.parametrize(
    "evidence_field",
    ["no_final_test_input_proof", "no_uncontrolled_glob_proof"],
)
def test_validator_receipt_requires_named_evidence_objects(
    evidence_field: str,
) -> None:
    payload = _fixture("valid_manifest_validation_receipt.json")
    payload.pop(evidence_field)

    result = _contracts().validate_manifest_validation_receipt_schema(payload)

    _assert_rejected(result, "missing_evidence_object")


@pytest.mark.parametrize(
    "fixture_name",
    ["preflight_validated_runner_receipt.json", "rejected_glob_runner_receipt.json"],
)
def test_runner_receipt_schema_accepts_validated_and_rejected_branches(
    fixture_name: str,
) -> None:
    result = _contracts().validate_runner_receipt_schema(_fixture(fixture_name))
    _assert_valid(result)


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
def test_runner_receipt_requires_all_named_evidence_objects(
    evidence_field: str,
) -> None:
    payload = _fixture("rejected_glob_runner_receipt.json")
    payload.pop(evidence_field)

    result = _contracts().validate_runner_receipt_schema(payload)

    _assert_rejected(result, "missing_evidence_object")


def test_runner_receipt_preserves_requested_intent_separately_from_acceptance() -> None:
    payload = _fixture("rejected_glob_runner_receipt.json")

    result = _contracts().validate_runner_receipt_schema(payload)

    _assert_valid(result)
    assert payload["requested_input_mode"] == "directory_glob"
    assert payload["accepted_input_mode"] is None
    assert payload["accepted_execution"] is False


@pytest.mark.parametrize(
    (
        "requested_provider",
        "requested_kind",
        "artifact_claim",
        "rejection_reason",
        "evidence_decision",
    ),
    [
        ("langchain_openai_compatible", "real", None, "real_provider_forbidden", "reject"),
        ("unsupported-alias", "unknown", None, "unknown_provider", "reject"),
    ],
)
def test_runner_rejection_schema_can_record_provider_negative_paths(
    requested_provider: str,
    requested_kind: str,
    artifact_claim: str | None,
    rejection_reason: str,
    evidence_decision: str,
) -> None:
    payload = copy.deepcopy(_fixture("rejected_glob_runner_receipt.json"))
    payload["requested_provider"] = requested_provider
    payload["requested_provider_kind"] = requested_kind
    payload["artifact_claimed_provider"] = artifact_claim
    payload["requested_input_mode"] = "manifest_file"
    payload["requested_paths"] = ["pilot_manifest.json"]
    payload["rejection_reason"] = rejection_reason
    payload["failure_summaries"] = [
        {"failure_type": rejection_reason, "count": 1, "denominator": 1}
    ]
    payload["no_real_llm_evidence"]["requested_provider"] = requested_provider
    payload["no_real_llm_evidence"]["requested_provider_kind"] = requested_kind
    payload["no_real_llm_evidence"]["decision"] = evidence_decision
    payload["no_uncontrolled_glob_evidence"] = {
        "requested_input_mode": "manifest_file",
        "accepted_input_mode": None,
        "glob_detected": False,
        "glob_pattern": None,
        "decision": "pass",
        "checked_at": "2026-08-11T00:00:00Z",
    }

    result = _contracts().validate_runner_receipt_schema(payload)

    _assert_valid(result)


def test_preflight_validated_receipt_cannot_claim_execution_authorization() -> None:
    payload = _fixture("preflight_validated_runner_receipt.json")
    payload["accepted_execution"] = True

    result = _contracts().validate_runner_receipt_schema(payload)

    _assert_rejected(result, "invalid_receipt_state")


def test_runner_receipt_rejects_unknown_nested_evidence_field() -> None:
    payload = _fixture("preflight_validated_runner_receipt.json")
    payload["scope_evidence"]["narrative_override"] = True

    result = _contracts().validate_runner_receipt_schema(payload)

    _assert_rejected(result, "unknown_field")


@pytest.mark.parametrize(
    ("requested_provider", "requested_kind"),
    [
        ("langchain_openai_compatible", "real"),
        ("unsupported-alias", "unknown"),
    ],
)
def test_nonmock_provider_cannot_use_preflight_validated_branch(
    requested_provider: str, requested_kind: str
) -> None:
    payload = _fixture("preflight_validated_runner_receipt.json")
    payload["requested_provider"] = requested_provider
    payload["requested_provider_kind"] = requested_kind
    payload["no_real_llm_evidence"]["requested_provider"] = requested_provider
    payload["no_real_llm_evidence"]["requested_provider_kind"] = requested_kind

    result = _contracts().validate_runner_receipt_schema(payload)

    _assert_invalid(result)


@pytest.mark.parametrize(
    ("requested_provider", "requested_kind", "rejection_reason"),
    [
        ("langchain_openai_compatible", "real", "real_provider_forbidden"),
        ("unsupported-alias", "unknown", "unknown_provider"),
    ],
)
def test_nonmock_provider_rejection_cannot_retain_accepted_provider(
    requested_provider: str, requested_kind: str, rejection_reason: str
) -> None:
    payload = _fixture("rejected_glob_runner_receipt.json")
    payload["requested_provider"] = requested_provider
    payload["requested_provider_kind"] = requested_kind
    payload["requested_input_mode"] = "manifest_file"
    payload["accepted_provider"] = "mock"
    payload["rejection_reason"] = rejection_reason
    payload["no_real_llm_evidence"]["requested_provider"] = requested_provider
    payload["no_real_llm_evidence"]["requested_provider_kind"] = requested_kind
    payload["no_real_llm_evidence"]["accepted_provider"] = "mock"

    result = _contracts().validate_runner_receipt_schema(payload)

    _assert_invalid(result)


@pytest.mark.parametrize(
    ("requested_provider", "requested_kind", "wrong_reason"),
    [
        ("langchain_openai_compatible", "real", "unknown_provider"),
        ("unsupported-alias", "unknown", "real_provider_forbidden"),
    ],
)
def test_nonmock_provider_requires_matching_rejection_reason(
    requested_provider: str, requested_kind: str, wrong_reason: str
) -> None:
    payload = _fixture("rejected_glob_runner_receipt.json")
    payload["requested_provider"] = requested_provider
    payload["requested_provider_kind"] = requested_kind
    payload["requested_input_mode"] = "manifest_file"
    payload["rejection_reason"] = wrong_reason
    payload["no_real_llm_evidence"]["requested_provider"] = requested_provider
    payload["no_real_llm_evidence"]["requested_provider_kind"] = requested_kind

    result = _contracts().validate_runner_receipt_schema(payload)

    _assert_invalid(result)


@pytest.mark.parametrize("requested_kind", ["real", "unknown"])
def test_nonmock_provider_cannot_claim_execution_acceptance(
    requested_kind: str,
) -> None:
    payload = _fixture("preflight_validated_runner_receipt.json")
    payload["requested_provider_kind"] = requested_kind
    payload["no_real_llm_evidence"]["requested_provider_kind"] = requested_kind
    payload["accepted_execution"] = True

    result = _contracts().validate_runner_receipt_schema(payload)

    _assert_invalid(result)


@pytest.mark.parametrize(
    ("field_name", "accepted_value"),
    [
        ("accepted_provider", "mock"),
        ("accepted_input_mode", "manifest_file"),
        ("accepted_manifest_scope", "pilot_nonformal"),
    ],
)
def test_preflight_rejected_receipt_has_no_accepted_fields(
    field_name: str, accepted_value: str
) -> None:
    payload = _fixture("rejected_glob_runner_receipt.json")
    payload[field_name] = accepted_value

    result = _contracts().validate_runner_receipt_schema(payload)

    _assert_invalid(result)


def test_preflight_rejected_receipt_cannot_accept_execution() -> None:
    payload = _fixture("rejected_glob_runner_receipt.json")
    payload["accepted_execution"] = True

    result = _contracts().validate_runner_receipt_schema(payload)

    _assert_invalid(result)


def test_preflight_rejected_receipt_requires_rejection_reason() -> None:
    payload = _fixture("rejected_glob_runner_receipt.json")
    payload["rejection_reason"] = None

    result = _contracts().validate_runner_receipt_schema(payload)

    _assert_invalid(result)


def test_preflight_validated_receipt_cannot_have_rejection_reason() -> None:
    payload = _fixture("preflight_validated_runner_receipt.json")
    payload["rejection_reason"] = "validation_receipt_invalid"

    result = _contracts().validate_runner_receipt_schema(payload)

    _assert_invalid(result)


@pytest.mark.parametrize(
    "field_name",
    ["accepted_provider", "accepted_input_mode", "accepted_manifest_scope"],
)
def test_preflight_validated_receipt_requires_accepted_decision_fields(
    field_name: str,
) -> None:
    payload = _fixture("preflight_validated_runner_receipt.json")
    payload[field_name] = None

    result = _contracts().validate_runner_receipt_schema(payload)

    _assert_invalid(result)


@pytest.mark.parametrize(
    "field_name",
    [
        "manifest_hash",
        "canonical_manifest_hash",
        "matrix_scope",
        "objective_version",
        "validation_receipt_id",
        "validation_receipt_hash",
    ],
)
def test_preflight_validated_receipt_requires_non_null_bindings(
    field_name: str,
) -> None:
    payload = _fixture("preflight_validated_runner_receipt.json")
    payload[field_name] = None

    result = _contracts().validate_runner_receipt_schema(payload)

    _assert_invalid(result)


@pytest.mark.parametrize(
    ("evidence_field", "mutations"),
    [
        (
            "scope_evidence",
            {
                "manifest_scope": None,
                "matrix_scope": None,
                "pilot_nonformal_confirmed": False,
            },
        ),
        (
            "manifest_only_evidence",
            {
                "manifest_path": None,
                "manifest_hash": None,
                "validation_receipt_id": None,
            },
        ),
    ],
)
def test_preflight_validated_receipt_requires_positive_evidence_values(
    evidence_field: str, mutations: dict
) -> None:
    payload = _fixture("preflight_validated_runner_receipt.json")
    payload[evidence_field].update(mutations)

    result = _contracts().validate_runner_receipt_schema(payload)

    _assert_invalid(result)


@pytest.mark.parametrize(
    ("top_field", "top_value", "evidence_field", "evidence_key", "evidence_value"),
    [
        (
            "requested_provider_kind",
            "mock",
            "no_real_llm_evidence",
            "requested_provider_kind",
            "real",
        ),
        (
            "accepted_provider",
            "mock",
            "no_real_llm_evidence",
            "accepted_provider",
            "file",
        ),
        (
            "requested_input_mode",
            "manifest_file",
            "no_uncontrolled_glob_evidence",
            "requested_input_mode",
            "directory_glob",
        ),
        (
            "accepted_input_mode",
            "manifest_file",
            "no_uncontrolled_glob_evidence",
            "accepted_input_mode",
            None,
        ),
        (
            "accepted_manifest_scope",
            "pilot_nonformal",
            "scope_evidence",
            "manifest_scope",
            "formal_final_test",
        ),
        (
            "manifest_hash",
            "0" * 64,
            "manifest_only_evidence",
            "manifest_hash",
            "1" * 64,
        ),
        (
            "validation_receipt_id",
            "6" * 64,
            "manifest_only_evidence",
            "validation_receipt_id",
            "7" * 64,
        ),
    ],
)
def test_runner_top_level_and_evidence_values_must_match(
    top_field: str,
    top_value,
    evidence_field: str,
    evidence_key: str,
    evidence_value,
) -> None:
    payload = _fixture("preflight_validated_runner_receipt.json")
    payload[top_field] = top_value
    payload[evidence_field][evidence_key] = evidence_value

    result = _contracts().validate_runner_receipt_schema(payload)

    _assert_invalid(result)


def test_manifest_rejects_unsupported_schema_version() -> None:
    payload = _fixture("valid_pilot_manifest.json")
    payload["schema_version"] = "pilot-manifest-schema-v999"

    result = _contracts().validate_pilot_manifest_schema(payload)

    _assert_invalid(result)


def test_manifest_rejects_unsupported_manifest_version() -> None:
    payload = _fixture("valid_pilot_manifest.json")
    payload["manifest_version"] = "pilot-manifest-v999"
    payload["instances"][0]["manifest_version"] = "pilot-manifest-v999"

    result = _contracts().validate_pilot_manifest_schema(payload)

    _assert_invalid(result)


def test_manifest_rejects_unsupported_objective_version() -> None:
    payload = _fixture("valid_pilot_manifest.json")
    payload["objective_version"] = "objective-v999"
    payload["instances"][0]["objective_version"] = "objective-v999"

    result = _contracts().validate_pilot_manifest_schema(payload)

    _assert_invalid(result)


@pytest.mark.parametrize(
    ("fixture_name", "validator_name"),
    [
        ("valid_manifest_validation_receipt.json", "validate_manifest_validation_receipt_schema"),
        ("preflight_validated_runner_receipt.json", "validate_runner_receipt_schema"),
    ],
)
def test_receipts_reject_unsupported_schema_version(
    fixture_name: str, validator_name: str
) -> None:
    payload = _fixture(fixture_name)
    payload["receipt_schema_version"] = "unsupported-receipt-v999"

    result = getattr(_contracts(), validator_name)(payload)

    _assert_invalid(result)


def test_runner_rejects_unsupported_requested_manifest_scope() -> None:
    payload = _fixture("preflight_validated_runner_receipt.json")
    payload["requested_manifest_scope"] = "unsupported_scope"

    result = _contracts().validate_runner_receipt_schema(payload)

    _assert_invalid(result)


def test_runner_rejects_unsupported_matrix_scope() -> None:
    payload = _fixture("preflight_validated_runner_receipt.json")
    payload["matrix_scope"] = "unsupported_matrix"

    result = _contracts().validate_runner_receipt_schema(payload)

    _assert_invalid(result)


@pytest.mark.parametrize(
    ("field_name", "unsupported_value"),
    [
        ("manifest_scope", "unsupported_scope"),
        ("matrix_scope", "unsupported_matrix"),
    ],
)
def test_manifest_rejects_unsupported_scope_enum(
    field_name: str, unsupported_value: str
) -> None:
    payload = _fixture("valid_pilot_manifest.json")
    payload[field_name] = unsupported_value

    result = _contracts().validate_pilot_manifest_schema(payload)

    _assert_invalid(result)


def test_runner_rejects_unsupported_status() -> None:
    payload = _fixture("preflight_validated_runner_receipt.json")
    payload["status"] = "validation_valid"

    result = _contracts().validate_runner_receipt_schema(payload)

    _assert_invalid(result)


def test_valid_validation_receipt_has_no_rejection_reasons() -> None:
    payload = _fixture("valid_manifest_validation_receipt.json")
    payload["rejection_reasons"] = ["unexpected_failure"]

    result = _contracts().validate_manifest_validation_receipt_schema(payload)

    _assert_invalid(result)


@pytest.mark.parametrize("manifest_hash_value", [None, ""])
def test_valid_validation_receipt_requires_manifest_hash(
    manifest_hash_value,
) -> None:
    payload = _fixture("valid_manifest_validation_receipt.json")
    payload["manifest_hash"] = manifest_hash_value

    result = _contracts().validate_manifest_validation_receipt_schema(payload)

    _assert_invalid(result)


@pytest.mark.parametrize("field_name", ["manifest_scope", "matrix_scope"])
def test_valid_validation_receipt_requires_non_null_scope(
    field_name: str,
) -> None:
    payload = _fixture("valid_manifest_validation_receipt.json")
    payload[field_name] = None

    result = _contracts().validate_manifest_validation_receipt_schema(payload)

    _assert_invalid(result)


def test_rejected_validation_receipt_requires_rejection_reason() -> None:
    payload = _fixture("rejected_manifest_validation_receipt.json")
    payload["rejection_reasons"] = []

    result = _contracts().validate_manifest_validation_receipt_schema(payload)

    _assert_invalid(result)


def test_rejected_validation_receipt_cannot_accept_records() -> None:
    payload = _fixture("rejected_manifest_validation_receipt.json")
    payload["accepted_record_count"] = 1

    result = _contracts().validate_manifest_validation_receipt_schema(payload)

    _assert_invalid(result)


def test_failure_summaries_must_be_array() -> None:
    payload = _fixture("rejected_glob_runner_receipt.json")
    payload["failure_summaries"] = {"failure_type": "invalid"}

    result = _contracts().validate_runner_receipt_schema(payload)

    _assert_invalid(result)


@pytest.mark.parametrize(
    "failure_summary",
    [
        "not-an-object",
        {"failure_type": "invalid", "count": 1, "denominator": 1, "unknown": True},
        {"failure_type": "invalid", "count": "1", "denominator": 1},
        {"failure_type": "invalid", "count": -1, "denominator": 1},
        {"failure_type": "invalid", "count": 1, "denominator": "1"},
        {"failure_type": "invalid", "count": 1, "denominator": -1},
    ],
)
def test_failure_summary_entries_are_strict_objects(failure_summary) -> None:
    payload = _fixture("rejected_glob_runner_receipt.json")
    payload["failure_summaries"] = [failure_summary]

    result = _contracts().validate_runner_receipt_schema(payload)

    _assert_invalid(result)


def test_output_paths_must_be_array() -> None:
    payload = _fixture("preflight_validated_runner_receipt.json")
    payload["output_paths"] = {"path": "pilot-output/result.json"}

    result = _contracts().validate_runner_receipt_schema(payload)

    _assert_invalid(result)


@pytest.mark.parametrize(
    "output_entry",
    [
        "pilot-output/result.json",
        {"unexpected_field": "must fail closed"},
        {"path": "C:/formal_final_test/result.json", "manifest_scope": "formal_final_test"},
        {"path": 123},
    ],
)
def test_output_path_entries_fail_closed_without_defined_schema(
    output_entry,
) -> None:
    payload = _fixture("preflight_validated_runner_receipt.json")
    payload["output_paths"] = [output_entry]

    result = _contracts().validate_runner_receipt_schema(payload)

    _assert_invalid(result)


@pytest.mark.parametrize(
    "status",
    [
        "scheduled",
        "running",
        "completed",
        "completed_with_failures",
        "aborted",
        "receipt_incomplete",
        "executed",
        "execution_started",
        "execution_completed",
        "pilot_completed",
    ],
)
@pytest.mark.parametrize("accepted_execution", [False, True])
def test_t1_runner_receipt_rejects_all_non_preflight_statuses(
    status: str, accepted_execution: bool
) -> None:
    payload = _fixture("preflight_validated_runner_receipt.json")
    payload["status"] = status
    payload["accepted_execution"] = accepted_execution

    result = _contracts().validate_runner_receipt_schema(payload)

    _assert_invalid(result)


def _manifest_request_rejection(rejection_reason: str) -> dict:
    payload = _fixture("rejected_glob_runner_receipt.json")
    payload["requested_input_mode"] = "manifest_file"
    payload["requested_paths"] = ["pilot_manifest.json"]
    payload["rejection_reason"] = rejection_reason
    payload["no_uncontrolled_glob_evidence"].update(
        {
            "requested_input_mode": "manifest_file",
            "glob_detected": False,
            "glob_pattern": None,
            "decision": "pass",
        }
    )
    return payload


_RUNNER_EVIDENCE_FIELDS = (
    "no_real_llm_evidence",
    "no_final_test_input_evidence",
    "no_uncontrolled_glob_evidence",
    "manifest_only_evidence",
    "scope_evidence",
)


def _rejection_with_only_evidence_reject(
    rejection_reason: str, rejecting_evidence: str | None
) -> dict:
    payload = _manifest_request_rejection(rejection_reason)
    for evidence_field in _RUNNER_EVIDENCE_FIELDS:
        payload[evidence_field]["decision"] = "pass"
    if rejecting_evidence is not None:
        payload[rejecting_evidence]["decision"] = "reject"
    return payload


@pytest.mark.parametrize(
    "unrelated_rejecting_evidence",
    [
        "no_real_llm_evidence",
        "scope_evidence",
        "no_uncontrolled_glob_evidence",
        "no_final_test_input_evidence",
    ],
)
def test_validation_receipt_invalid_rejects_unrelated_evidence_support(
    unrelated_rejecting_evidence: str,
) -> None:
    payload = _rejection_with_only_evidence_reject(
        "validation_receipt_invalid", unrelated_rejecting_evidence
    )

    result = _contracts().validate_runner_receipt_schema(payload)

    _assert_invalid(result)


def test_validation_receipt_invalid_rejects_passed_manifest_evidence() -> None:
    payload = _rejection_with_only_evidence_reject(
        "validation_receipt_invalid", None
    )
    payload["manifest_only_evidence"].update(
        {
            "manifest_path": "pilot_manifest.json",
            "manifest_hash": "a" * 64,
            "validation_receipt_id": "b" * 64,
            "decision": "pass",
        }
    )

    result = _contracts().validate_runner_receipt_schema(payload)

    _assert_invalid(result)


@pytest.mark.parametrize(
    "unrelated_rejecting_evidence",
    ["manifest_only_evidence", "scope_evidence"],
)
def test_runtime_authorization_denied_fails_closed_without_dedicated_evidence(
    unrelated_rejecting_evidence: str,
) -> None:
    payload = _rejection_with_only_evidence_reject(
        "runtime_authorization_denied", unrelated_rejecting_evidence
    )

    result = _contracts().validate_runner_receipt_schema(payload)

    _assert_invalid(result)


@pytest.mark.parametrize(
    ("rejection_reason", "unrelated_rejecting_evidence"),
    [
        ("real_provider_forbidden", "manifest_only_evidence"),
        ("unknown_provider", "scope_evidence"),
        ("uncontrolled_glob_forbidden", "no_real_llm_evidence"),
        ("final_test_scope_forbidden", "no_uncontrolled_glob_evidence"),
        ("manifest_scope_forbidden", "no_final_test_input_evidence"),
    ],
)
def test_rejection_reason_rejects_unrelated_evidence_support(
    rejection_reason: str, unrelated_rejecting_evidence: str
) -> None:
    payload = _rejection_with_only_evidence_reject(
        rejection_reason, unrelated_rejecting_evidence
    )

    result = _contracts().validate_runner_receipt_schema(payload)

    _assert_invalid(result)


def test_provider_claim_mismatch_fails_closed_without_mismatch_evidence() -> None:
    payload = _rejection_with_only_evidence_reject(
        "provider_claim_mismatch", "no_real_llm_evidence"
    )
    payload["artifact_claimed_provider"] = "openai"

    result = _contracts().validate_runner_receipt_schema(payload)

    _assert_invalid(result)


@pytest.mark.parametrize(
    ("requested_provider", "requested_kind", "evidence_decision"),
    [
        ("mock", "mock", "pass"),
        ("langchain_openai_compatible", "real", "pass"),
    ],
)
def test_real_provider_rejection_requires_supporting_provider_evidence(
    requested_provider: str, requested_kind: str, evidence_decision: str
) -> None:
    payload = _manifest_request_rejection("real_provider_forbidden")
    payload["requested_provider"] = requested_provider
    payload["requested_provider_kind"] = requested_kind
    payload["no_real_llm_evidence"].update(
        {
            "requested_provider": requested_provider,
            "requested_provider_kind": requested_kind,
            "decision": evidence_decision,
        }
    )

    result = _contracts().validate_runner_receipt_schema(payload)

    _assert_invalid(result)


@pytest.mark.parametrize(
    ("requested_provider", "requested_kind", "evidence_decision"),
    [
        ("mock", "mock", "pass"),
        ("unsupported-alias", "unknown", "pass"),
    ],
)
def test_unknown_provider_rejection_requires_supporting_provider_evidence(
    requested_provider: str, requested_kind: str, evidence_decision: str
) -> None:
    payload = _manifest_request_rejection("unknown_provider")
    payload["requested_provider"] = requested_provider
    payload["requested_provider_kind"] = requested_kind
    payload["no_real_llm_evidence"].update(
        {
            "requested_provider": requested_provider,
            "requested_provider_kind": requested_kind,
            "decision": evidence_decision,
        }
    )

    result = _contracts().validate_runner_receipt_schema(payload)

    _assert_invalid(result)


@pytest.mark.parametrize(
    "evidence_mutation",
    [
        {"requested_input_mode": "manifest_file"},
        {"glob_detected": False},
        {"decision": "pass"},
    ],
)
def test_glob_rejection_requires_supporting_glob_evidence(
    evidence_mutation: dict,
) -> None:
    payload = _fixture("rejected_glob_runner_receipt.json")
    if "requested_input_mode" in evidence_mutation:
        payload["requested_input_mode"] = evidence_mutation["requested_input_mode"]
    payload["no_uncontrolled_glob_evidence"].update(evidence_mutation)

    result = _contracts().validate_runner_receipt_schema(payload)

    _assert_invalid(result)


@pytest.mark.parametrize("evidence_decision", ["not_reached", "pass"])
def test_final_test_rejection_requires_detected_final_test_evidence(
    evidence_decision: str,
) -> None:
    payload = _manifest_request_rejection("final_test_scope_forbidden")
    payload["no_final_test_input_evidence"]["decision"] = evidence_decision

    result = _contracts().validate_runner_receipt_schema(payload)

    _assert_invalid(result)


def test_manifest_scope_rejection_requires_forbidden_scope_evidence() -> None:
    payload = _manifest_request_rejection("manifest_scope_forbidden")

    result = _contracts().validate_runner_receipt_schema(payload)

    _assert_invalid(result)


def test_provider_claim_mismatch_requires_mismatching_claim_evidence() -> None:
    payload = _manifest_request_rejection("provider_claim_mismatch")
    payload["artifact_claimed_provider"] = "mock"

    result = _contracts().validate_runner_receipt_schema(payload)

    _assert_invalid(result)


def test_rejected_receipt_cannot_be_supported_only_by_pass_evidence() -> None:
    payload = _manifest_request_rejection("runtime_authorization_denied")
    payload["no_final_test_input_evidence"]["decision"] = "pass"
    payload["manifest_only_evidence"]["decision"] = "pass"
    payload["scope_evidence"]["decision"] = "pass"

    result = _contracts().validate_runner_receipt_schema(payload)

    _assert_invalid(result)


@pytest.mark.parametrize(
    ("evidence_field", "evidence_mutations"),
    [
        (
            "no_final_test_input_evidence",
            {"final_test_scope_present": True},
        ),
        (
            "no_final_test_input_evidence",
            {"manifest_scopes_loaded": ["pilot_nonformal", "formal_final_test"]},
        ),
        (
            "no_final_test_input_evidence",
            {"manifests_loaded": ["formal_final_test_manifest"]},
        ),
        (
            "scope_evidence",
            {"manifest_scope": "formal_final_test"},
        ),
        (
            "no_final_test_input_evidence",
            {
                "manifest_scopes_loaded": ["formal_final_test"],
                "final_test_scope_present": False,
            },
        ),
        (
            "no_uncontrolled_glob_evidence",
            {"glob_detected": True},
        ),
        (
            "no_real_llm_evidence",
            {
                "requested_provider": "langchain_openai_compatible",
                "requested_provider_kind": "real",
            },
        ),
    ],
)
def test_preflight_validated_rejects_semantically_contradictory_evidence(
    evidence_field: str, evidence_mutations: dict
) -> None:
    payload = _fixture("preflight_validated_runner_receipt.json")
    if evidence_field == "no_real_llm_evidence":
        payload["requested_provider"] = evidence_mutations["requested_provider"]
        payload["requested_provider_kind"] = evidence_mutations[
            "requested_provider_kind"
        ]
    payload[evidence_field].update(evidence_mutations)

    result = _contracts().validate_runner_receipt_schema(payload)

    _assert_invalid(result)
