"""Pure schema validation for non-formal pilot contract objects.

This module deliberately validates already-parsed JSON-compatible Python data
only.  It does not read paths, inspect files, recompute hashes, schedule work,
or invoke providers or generated candidates.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any, Iterable


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

_MANIFEST_TYPE = "pilot_split_manifest"
_MANIFEST_SCHEMA_VERSION = "pilot-manifest-schema-v1"
_MANIFEST_VERSION = "pilot-manifest-v1"
_PILOT_OBJECTIVE_VERSION = "objective_v1_prototype"
_PILOT_MANIFEST_SCOPE = "pilot_nonformal"
_PILOT_MATRIX_SCOPE = "pilot"
_VALIDATOR_RECEIPT_VERSION = "pilot-validator-v1"
_RUNNER_RECEIPT_VERSION = "pilot-runner-v1"


@dataclass(frozen=True)
class SchemaValidationResult:
    """Result returned by every pilot contract schema validator."""

    valid: bool
    rejection_reasons: tuple[str, ...]


class _Issues:
    def __init__(self) -> None:
        self._reasons: list[str] = []

    def add(self, reason: str) -> None:
        if reason not in self._reasons:
            self._reasons.append(reason)

    def result(self) -> SchemaValidationResult:
        return SchemaValidationResult(not self._reasons, tuple(self._reasons))


def _check_object(
    value: Any,
    *,
    required: set[str],
    allowed: set[str],
    issues: _Issues,
    evidence_fields: Iterable[str] = (),
) -> bool:
    if type(value) is not dict:
        issues.add("invalid_field_type")
        return False
    evidence = set(evidence_fields)
    for field in required - value.keys():
        issues.add("missing_evidence_object" if field in evidence else "missing_required_field")
    if value.keys() - allowed:
        issues.add("unknown_field")
    return True


def _is_string(value: Any, *, nullable: bool = False) -> bool:
    return (nullable and value is None) or type(value) is str


def _is_bool(value: Any) -> bool:
    return type(value) is bool


def _is_int(value: Any, *, minimum: int | None = None) -> bool:
    if type(value) is not int:
        return False
    return minimum is None or value >= minimum


def _is_number(value: Any, *, minimum: float | None = None, strict: bool = False) -> bool:
    if type(value) not in (int, float) or not math.isfinite(value):
        return False
    if minimum is None:
        return True
    return value > minimum if strict else value >= minimum


def _is_string_list(value: Any, *, unique: bool = False) -> bool:
    if type(value) is not list or any(type(item) is not str for item in value):
        return False
    return not unique or len(value) == len(set(value))


def _check_type(value: Any, predicate: bool, issues: _Issues) -> None:
    if not predicate:
        issues.add("invalid_field_type")


def _check_enum(value: Any, allowed: set[str], issues: _Issues) -> None:
    if type(value) is not str:
        issues.add("invalid_field_type")
    elif value not in allowed:
        issues.add("invalid_field_value")


def _check_hash(value: Any, issues: _Issues, *, nullable: bool = False, empty: bool = False) -> None:
    if nullable and value is None:
        return
    if empty and value == "":
        return
    if type(value) is not str:
        issues.add("invalid_field_type")
    elif _SHA256_RE.fullmatch(value) is None:
        issues.add("invalid_field_value")


_MANIFEST_FIELDS = {
    "manifest_type", "schema_version", "manifest_version", "manifest_id",
    "manifest_scope", "matrix_scope", "objective_version",
    "artifact_promotion_allowed", "formal_identity_version",
    "pilot_source_reference", "manifest_hash", "instance_count", "family_count",
    "strata_counts", "exclusion_rule_version", "replacement_seed_rule_version",
    "generator_code_hash", "instance_schema_version", "family_matrix_hash",
    "split_assignment_rule_hash", "parent_manifest_hash", "contamination_status",
    "created_at", "approved_by", "notes", "audit_history", "instances",
}

_INSTANCE_FIELDS = {
    "manifest_version", "manifest_scope", "matrix_scope", "objective_version",
    "instance_id", "family_id", "split", "size_stratum", "distribution_stratum",
    "robots", "tasks", "sweep_width", "sweep_speed", "travel_speed",
    "turning_time", "generation_rule_version", "generation_seed", "replicate_id",
    "file_path", "file_hash", "family_matrix_hash", "split_assignment_rule_hash",
    "artifact_promotion_allowed", "formal_identity_version", "pilot_source_reference",
    "contamination_owner", "lockbox_status", "created_at", "approved_by", "notes",
}

_AUDIT_FIELDS = {"event_id", "actor_id", "action", "created_at"}


def validate_pilot_manifest_schema(payload: Any) -> SchemaValidationResult:
    """Validate the pure JSON shape of a ``pilot_nonformal`` manifest."""

    issues = _Issues()
    if not _check_object(payload, required=_MANIFEST_FIELDS, allowed=_MANIFEST_FIELDS, issues=issues):
        return issues.result()

    for field in (
        "manifest_id", "formal_identity_version", "exclusion_rule_version",
        "replacement_seed_rule_version", "instance_schema_version",
        "contamination_status", "created_at", "approved_by", "notes",
    ):
        if field in payload:
            _check_type(payload[field], _is_string(payload[field]), issues)

    for field, expected in (
        ("manifest_type", _MANIFEST_TYPE),
        ("schema_version", _MANIFEST_SCHEMA_VERSION),
        ("manifest_version", _MANIFEST_VERSION),
        ("objective_version", _PILOT_OBJECTIVE_VERSION),
    ):
        if field in payload:
            _check_enum(payload[field], {expected}, issues)

    if "manifest_scope" in payload:
        scope = payload["manifest_scope"]
        if type(scope) is not str:
            issues.add("invalid_field_type")
        elif scope != _PILOT_MANIFEST_SCOPE:
            issues.add("forbidden_manifest_scope")
    if "matrix_scope" in payload:
        matrix_scope = payload["matrix_scope"]
        if type(matrix_scope) is not str:
            issues.add("invalid_field_type")
        elif payload.get("manifest_scope") == _PILOT_MANIFEST_SCOPE and matrix_scope != _PILOT_MATRIX_SCOPE:
            issues.add("invalid_scope_combination")
        elif matrix_scope not in {"pilot", "formal"}:
            issues.add("invalid_field_value")

    if "artifact_promotion_allowed" in payload and payload["artifact_promotion_allowed"] is not False:
        issues.add("artifact_promotion_forbidden")
    if "pilot_source_reference" in payload and payload["pilot_source_reference"] is not None:
        issues.add("invalid_field_value")

    for field in ("instance_count", "family_count"):
        if field in payload:
            value = payload[field]
            if type(value) is not int:
                issues.add("invalid_field_type")
            elif value < 0:
                issues.add("invalid_field_value")

    for field in ("manifest_hash", "generator_code_hash", "family_matrix_hash", "split_assignment_rule_hash"):
        if field in payload:
            _check_hash(payload[field], issues)
    if "parent_manifest_hash" in payload:
        _check_hash(payload["parent_manifest_hash"], issues, empty=True)

    if "strata_counts" in payload:
        strata = payload["strata_counts"]
        if type(strata) is not dict:
            issues.add("invalid_field_type")
        elif any(type(key) is not str or not _is_int(value, minimum=0) for key, value in strata.items()):
            issues.add("invalid_field_type")

    if "audit_history" in payload:
        audit_history = payload["audit_history"]
        if type(audit_history) is not list:
            issues.add("invalid_field_type")
        else:
            for audit in audit_history:
                if not _check_object(audit, required=_AUDIT_FIELDS, allowed=_AUDIT_FIELDS, issues=issues):
                    continue
                for field in _AUDIT_FIELDS:
                    if field in audit:
                        _check_type(audit[field], _is_string(audit[field]), issues)

    if "instances" in payload:
        instances = payload["instances"]
        if type(instances) is not list:
            issues.add("invalid_field_type")
        else:
            for record in instances:
                _validate_instance_record(record, payload, issues)

    return issues.result()


def _validate_instance_record(record: Any, header: dict[str, Any], issues: _Issues) -> None:
    if not _check_object(record, required=_INSTANCE_FIELDS, allowed=_INSTANCE_FIELDS, issues=issues):
        return

    string_fields = {
        "instance_id", "family_id", "split",
        "size_stratum", "distribution_stratum", "generation_rule_version", "file_path",
        "formal_identity_version", "contamination_owner", "lockbox_status", "created_at",
        "approved_by", "notes",
    }
    for field in string_fields:
        if field in record:
            _check_type(record[field], _is_string(record[field]), issues)

    for field, expected in (
        ("manifest_version", _MANIFEST_VERSION),
        ("objective_version", _PILOT_OBJECTIVE_VERSION),
    ):
        if field in record:
            _check_enum(record[field], {expected}, issues)

    for field in ("robots", "tasks", "generation_seed", "replicate_id"):
        if field not in record:
            continue
        value = record[field]
        minimum = 1 if field in {"robots", "tasks"} else 0
        if type(value) is not int:
            issues.add("invalid_field_type")
        elif value < minimum:
            issues.add("invalid_field_value")

    for field in ("sweep_width", "sweep_speed", "travel_speed"):
        if field not in record:
            continue
        value = record[field]
        if type(value) not in (int, float) or not math.isfinite(value):
            issues.add("invalid_field_type")
        elif value <= 0:
            issues.add("invalid_field_value")
    if "turning_time" in record:
        value = record["turning_time"]
        if type(value) not in (int, float) or not math.isfinite(value):
            issues.add("invalid_field_type")
        elif value < 0:
            issues.add("invalid_field_value")

    if "manifest_scope" in record:
        if type(record["manifest_scope"]) is not str:
            issues.add("invalid_field_type")
        elif record["manifest_scope"] != _PILOT_MANIFEST_SCOPE:
            issues.add("forbidden_manifest_scope")
    if "matrix_scope" in record:
        if type(record["matrix_scope"]) is not str:
            issues.add("invalid_field_type")
        elif record["matrix_scope"] != _PILOT_MATRIX_SCOPE:
            issues.add("invalid_scope_combination")
    if "split" in record and type(record["split"]) is str and record["split"] not in {"smoke", "train", "dev"}:
        issues.add("invalid_field_value")
    if "artifact_promotion_allowed" in record and record["artifact_promotion_allowed"] is not False:
        issues.add("artifact_promotion_forbidden")
    if "pilot_source_reference" in record and record["pilot_source_reference"] is not None:
        issues.add("invalid_field_value")

    for field in ("instance_id", "file_hash", "family_matrix_hash", "split_assignment_rule_hash"):
        if field in record:
            _check_hash(record[field], issues)

    for field in ("manifest_version", "objective_version", "manifest_scope", "matrix_scope", "family_matrix_hash", "split_assignment_rule_hash"):
        if field in record and field in header and record[field] != header[field]:
            issues.add("invalid_scope_combination")


_VALIDATOR_RECEIPT_FIELDS = {
    "receipt_schema_version", "receipt_type", "validation_receipt_id", "status",
    "manifest_path_input_hash", "manifest_hash", "canonical_manifest_hash",
    "manifest_scope", "matrix_scope", "pilot_family_matrix_hash",
    "pilot_split_assignment_rule_hash", "validator_policy_version",
    "validator_code_hash", "approved_pilot_data_root_id", "checks_performed",
    "checks_not_reached", "rejection_reasons", "accepted_record_count",
    "file_identity_check", "file_identity_reason", "no_final_test_input_proof",
    "no_uncontrolled_glob_proof", "formal_evidence_eligible", "started_at",
    "ended_at", "wall_time_ms",
}


def validate_manifest_validation_receipt_schema(payload: Any) -> SchemaValidationResult:
    """Validate either branch of the pilot manifest-validation receipt union."""

    issues = _Issues()
    evidence = {"no_final_test_input_proof", "no_uncontrolled_glob_proof"}
    if not _check_object(
        payload,
        required=_VALIDATOR_RECEIPT_FIELDS,
        allowed=_VALIDATOR_RECEIPT_FIELDS,
        issues=issues,
        evidence_fields=evidence,
    ):
        return issues.result()

    for field in (
        "validator_policy_version",
        "approved_pilot_data_root_id", "file_identity_check", "started_at", "ended_at",
    ):
        if field in payload:
            _check_type(payload[field], _is_string(payload[field]), issues)
    if "receipt_schema_version" in payload:
        _check_enum(payload["receipt_schema_version"], {_VALIDATOR_RECEIPT_VERSION}, issues)
    if "receipt_type" in payload:
        _check_enum(
            payload["receipt_type"],
            {"pilot_manifest_validation_receipt", "pilot_manifest_rejection_receipt"},
            issues,
        )
    if "status" in payload:
        _check_enum(payload["status"], {"valid", "rejected"}, issues)
    for field in ("manifest_scope", "matrix_scope", "file_identity_reason"):
        if field in payload:
            _check_type(payload[field], _is_string(payload[field], nullable=True), issues)

    for field in ("validation_receipt_id", "manifest_path_input_hash", "manifest_hash", "validator_code_hash"):
        if field in payload:
            _check_hash(payload[field], issues)
    for field in ("canonical_manifest_hash", "pilot_family_matrix_hash", "pilot_split_assignment_rule_hash"):
        if field in payload:
            _check_hash(payload[field], issues, nullable=True)

    for field in ("checks_performed", "checks_not_reached", "rejection_reasons"):
        if field in payload:
            _check_type(payload[field], _is_string_list(payload[field]), issues)
    if "accepted_record_count" in payload:
        _check_type(payload["accepted_record_count"], _is_int(payload["accepted_record_count"], minimum=0), issues)
    if "formal_evidence_eligible" in payload:
        _check_type(payload["formal_evidence_eligible"], _is_bool(payload["formal_evidence_eligible"]), issues)
        if payload["formal_evidence_eligible"] is not False:
            issues.add("invalid_field_value")
    if "wall_time_ms" in payload:
        _check_type(payload["wall_time_ms"], _is_number(payload["wall_time_ms"], minimum=0), issues)

    receipt_type = payload.get("receipt_type")
    status = payload.get("status")
    valid_pairs = {
        ("pilot_manifest_validation_receipt", "valid"),
        ("pilot_manifest_rejection_receipt", "rejected"),
    }
    if type(receipt_type) is str and type(status) is str and (receipt_type, status) not in valid_pairs:
        issues.add("receipt_type_status_mismatch")

    if status == "valid":
        required_hashes = (
            "manifest_hash",
            "canonical_manifest_hash",
            "pilot_family_matrix_hash",
            "pilot_split_assignment_rule_hash",
        )
        if (
            payload.get("rejection_reasons") != []
            or payload.get("manifest_scope") != _PILOT_MANIFEST_SCOPE
            or payload.get("matrix_scope") != _PILOT_MATRIX_SCOPE
            or any(
                type(payload.get(field)) is not str
                or _SHA256_RE.fullmatch(payload[field]) is None
                for field in required_hashes
            )
            or not _is_int(payload.get("accepted_record_count"), minimum=1)
        ):
            issues.add("invalid_receipt_state")
        for proof_name in ("no_final_test_input_proof", "no_uncontrolled_glob_proof"):
            proof = payload.get(proof_name)
            if type(proof) is not dict or proof.get("status") != "pass":
                issues.add("invalid_receipt_state")
    elif status == "rejected":
        rejection_reasons = payload.get("rejection_reasons")
        if (
            type(rejection_reasons) is not list
            or not rejection_reasons
            or payload.get("accepted_record_count") != 0
        ):
            issues.add("invalid_receipt_state")

    if "no_final_test_input_proof" in payload:
        _validate_variable_evidence(
            payload["no_final_test_input_proof"],
            {"pass": {"status", "scope"}, "fail": {"status", "reason"}, "not_reached": {"status"}},
            issues,
        )
    if "no_uncontrolled_glob_proof" in payload:
        _validate_variable_evidence(
            payload["no_uncontrolled_glob_proof"],
            {"pass": {"status", "input_kind"}, "fail": {"status", "reason"}, "not_reached": {"status"}},
            issues,
        )

    return issues.result()


def _validate_variable_evidence(value: Any, shapes: dict[str, set[str]], issues: _Issues) -> None:
    if type(value) is not dict:
        issues.add("invalid_field_type")
        return
    if "status" not in value:
        issues.add("missing_required_field")
        return
    status = value["status"]
    if type(status) is not str:
        issues.add("invalid_field_type")
        return
    if status not in shapes:
        issues.add("invalid_field_value")
        return
    fields = shapes[status]
    _check_object(value, required=fields, allowed=fields, issues=issues)
    for field in fields - {"status"}:
        if field in value:
            _check_type(value[field], _is_string(value[field]), issues)


_RUNNER_FIELDS = {
    "receipt_schema_version", "runner_receipt_id", "requested_provider",
    "requested_provider_kind", "artifact_claimed_provider", "requested_input_mode",
    "requested_manifest_scope", "requested_paths", "requested_command_intent",
    "accepted_provider", "accepted_input_mode", "accepted_manifest_scope",
    "accepted_execution", "rejection_reason", "gate_p2_authorization_id", "status",
    "manifest_hash", "canonical_manifest_hash", "matrix_scope", "objective_version",
    "code_snapshot_hash", "validation_receipt_id", "validation_receipt_hash",
    "scheduled_run_ids", "output_paths", "failure_summaries", "accounting_summary_id",
    "no_real_llm_evidence", "no_final_test_input_evidence",
    "no_uncontrolled_glob_evidence", "manifest_only_evidence", "scope_evidence",
    "started_at", "ended_at", "wall_time_ms", "reviewer_notes", "non_formal_evidence",
}

_RUNNER_EVIDENCE_FIELDS = {
    "no_real_llm_evidence", "no_final_test_input_evidence",
    "no_uncontrolled_glob_evidence", "manifest_only_evidence", "scope_evidence",
}

_NO_REAL_FIELDS = {
    "requested_provider", "requested_provider_kind", "accepted_provider",
    "provider_adapter_identity", "provider_allowlist", "decision", "checked_at",
}
_NO_FINAL_FIELDS = {
    "manifests_loaded", "manifest_scopes_loaded", "paths_scanned_or_loaded",
    "final_test_scope_present", "decision", "checked_at",
}
_NO_GLOB_FIELDS = {
    "requested_input_mode", "accepted_input_mode", "glob_detected", "glob_pattern",
    "decision", "checked_at",
}
_MANIFEST_ONLY_FIELDS = {
    "manifest_path", "manifest_hash", "validation_receipt_id", "decision", "checked_at",
}
_SCOPE_FIELDS = {
    "manifest_scope", "matrix_scope", "pilot_nonformal_confirmed",
    "formal_final_test_rejected", "decision", "checked_at",
}


def validate_runner_receipt_schema(payload: Any) -> SchemaValidationResult:
    """Validate the pure JSON shape and branch invariants of a runner receipt."""

    issues = _Issues()
    if not _check_object(
        payload,
        required=_RUNNER_FIELDS,
        allowed=_RUNNER_FIELDS,
        issues=issues,
        evidence_fields=_RUNNER_EVIDENCE_FIELDS,
    ):
        return issues.result()

    string_fields = {
        "requested_provider", "requested_command_intent", "code_snapshot_hash",
        "ended_at", "reviewer_notes",
    }
    nullable_strings = {
        "artifact_claimed_provider", "requested_manifest_scope", "accepted_provider",
        "accepted_input_mode", "accepted_manifest_scope", "rejection_reason",
        "gate_p2_authorization_id", "manifest_hash", "canonical_manifest_hash",
        "matrix_scope", "objective_version", "validation_receipt_id",
        "validation_receipt_hash", "accounting_summary_id", "started_at",
    }
    for field in string_fields:
        if field in payload:
            _check_type(payload[field], _is_string(payload[field]), issues)
    for field in nullable_strings:
        if field in payload:
            _check_type(payload[field], _is_string(payload[field], nullable=True), issues)

    if "receipt_schema_version" in payload:
        _check_enum(payload["receipt_schema_version"], {_RUNNER_RECEIPT_VERSION}, issues)

    if "requested_provider_kind" in payload:
        _check_enum(payload["requested_provider_kind"], {"mock", "file", "real", "unknown"}, issues)
    if "requested_input_mode" in payload:
        _check_enum(
            payload["requested_input_mode"],
            {"manifest_file", "single_file", "directory_glob", "implicit_default_glob", "unknown"},
            issues,
        )
    if payload.get("accepted_provider") is not None and payload.get("accepted_provider") not in {"mock", "file"}:
        issues.add("invalid_field_value")
    if payload.get("accepted_input_mode") is not None and payload.get("accepted_input_mode") != "manifest_file":
        issues.add("invalid_field_value")
    if payload.get("accepted_manifest_scope") is not None and payload.get("accepted_manifest_scope") != "pilot_nonformal":
        issues.add("invalid_field_value")
    if payload.get("requested_manifest_scope") is not None:
        _check_enum(
            payload["requested_manifest_scope"],
            {"pilot_nonformal", "formal_train", "formal_dev", "formal_final_test"},
            issues,
        )
    if payload.get("matrix_scope") is not None:
        _check_enum(payload["matrix_scope"], {_PILOT_MATRIX_SCOPE}, issues)
    if payload.get("objective_version") is not None:
        _check_enum(payload["objective_version"], {_PILOT_OBJECTIVE_VERSION}, issues)

    # This schema version is deliberately preflight-only.  Execution lifecycle
    # receipts require a future, separately authorized schema after Gate P2.
    statuses = {"preflight_rejected", "preflight_validated"}
    if "status" in payload:
        _check_enum(payload["status"], statuses, issues)
    reasons = {
        "real_provider_forbidden", "unknown_provider", "uncontrolled_glob_forbidden",
        "final_test_scope_forbidden", "manifest_scope_forbidden",
    }
    if payload.get("rejection_reason") is not None and payload.get("rejection_reason") not in reasons:
        issues.add("invalid_field_value")

    for field in ("accepted_execution", "non_formal_evidence"):
        if field in payload:
            _check_type(payload[field], _is_bool(payload[field]), issues)
    if payload.get("non_formal_evidence") is not True:
        issues.add("invalid_field_value")
    if "requested_paths" in payload:
        _check_type(payload["requested_paths"], _is_string_list(payload["requested_paths"]), issues)
    if "scheduled_run_ids" in payload:
        _check_type(payload["scheduled_run_ids"], _is_string_list(payload["scheduled_run_ids"], unique=True), issues)
    if "failure_summaries" in payload:
        _validate_failure_summaries(payload["failure_summaries"], issues)
    if "output_paths" in payload:
        output_paths = payload["output_paths"]
        if type(output_paths) is not list:
            issues.add("invalid_field_type")
        elif output_paths:
            # T1R has no approved output-record schema.  Fail closed rather
            # than treating arbitrary path-like artifact data as valid.
            issues.add("invalid_field_value")
    if "wall_time_ms" in payload:
        _check_type(payload["wall_time_ms"], _is_number(payload["wall_time_ms"], minimum=0), issues)

    for field in ("runner_receipt_id", "code_snapshot_hash"):
        if field in payload:
            _check_hash(payload[field], issues)
    for field in ("manifest_hash", "canonical_manifest_hash", "validation_receipt_id", "validation_receipt_hash"):
        if field in payload:
            _check_hash(payload[field], issues, nullable=True)

    _validate_runner_evidence(payload, issues)
    _validate_runner_evidence_consistency(payload, issues)
    _validate_runner_state(payload, issues)
    return issues.result()


def _validate_failure_summaries(value: Any, issues: _Issues) -> None:
    if type(value) is not list:
        issues.add("invalid_field_type")
        return
    fields = {"failure_type", "count", "denominator"}
    for summary in value:
        if not _check_object(summary, required=fields, allowed=fields, issues=issues):
            continue
        if "failure_type" in summary:
            _check_type(summary["failure_type"], _is_string(summary["failure_type"]), issues)
        for field in ("count", "denominator"):
            if field not in summary:
                continue
            if type(summary[field]) is not int:
                issues.add("invalid_field_type")
            elif summary[field] < 0:
                issues.add("invalid_field_value")


def _validate_runner_evidence(payload: dict[str, Any], issues: _Issues) -> None:
    specs = {
        "no_real_llm_evidence": _NO_REAL_FIELDS,
        "no_final_test_input_evidence": _NO_FINAL_FIELDS,
        "no_uncontrolled_glob_evidence": _NO_GLOB_FIELDS,
        "manifest_only_evidence": _MANIFEST_ONLY_FIELDS,
        "scope_evidence": _SCOPE_FIELDS,
    }
    for name, fields in specs.items():
        if name not in payload:
            continue
        value = payload[name]
        if not _check_object(value, required=fields, allowed=fields, issues=issues):
            continue
        if "decision" in value:
            _check_enum(value["decision"], {"pass", "reject", "not_reached"}, issues)
        if "checked_at" in value:
            _check_type(value["checked_at"], _is_string(value["checked_at"]), issues)

    no_real = payload.get("no_real_llm_evidence")
    if type(no_real) is dict:
        for field in ("requested_provider",):
            if field in no_real:
                _check_type(no_real[field], _is_string(no_real[field]), issues)
        if "requested_provider_kind" in no_real:
            _check_enum(no_real["requested_provider_kind"], {"mock", "file", "real", "unknown"}, issues)
        for field in ("accepted_provider", "provider_adapter_identity"):
            if field in no_real:
                _check_type(no_real[field], _is_string(no_real[field], nullable=True), issues)
        if "provider_allowlist" in no_real:
            if not _is_string_list(no_real["provider_allowlist"], unique=True):
                issues.add("invalid_field_type")
            elif any(item not in {"mock", "file"} for item in no_real["provider_allowlist"]):
                issues.add("invalid_field_value")

    no_final = payload.get("no_final_test_input_evidence")
    if type(no_final) is dict:
        for field in ("manifests_loaded", "manifest_scopes_loaded", "paths_scanned_or_loaded"):
            if field in no_final:
                _check_type(no_final[field], _is_string_list(no_final[field]), issues)
        if "final_test_scope_present" in no_final:
            _check_type(no_final["final_test_scope_present"], _is_bool(no_final["final_test_scope_present"]), issues)

    no_glob = payload.get("no_uncontrolled_glob_evidence")
    if type(no_glob) is dict:
        if "requested_input_mode" in no_glob:
            _check_enum(
                no_glob["requested_input_mode"],
                {"manifest_file", "single_file", "directory_glob", "implicit_default_glob", "unknown"},
                issues,
            )
        for field in ("accepted_input_mode", "glob_pattern"):
            if field in no_glob:
                _check_type(no_glob[field], _is_string(no_glob[field], nullable=True), issues)
        if "glob_detected" in no_glob:
            _check_type(no_glob["glob_detected"], _is_bool(no_glob["glob_detected"]), issues)

    manifest_only = payload.get("manifest_only_evidence")
    if type(manifest_only) is dict:
        for field in ("manifest_path", "validation_receipt_id"):
            if field in manifest_only:
                _check_type(manifest_only[field], _is_string(manifest_only[field], nullable=True), issues)
        if "manifest_hash" in manifest_only:
            _check_hash(manifest_only["manifest_hash"], issues, nullable=True)

    scope = payload.get("scope_evidence")
    if type(scope) is dict:
        for field in ("manifest_scope", "matrix_scope"):
            if field in scope:
                _check_type(scope[field], _is_string(scope[field], nullable=True), issues)
        for field in ("pilot_nonformal_confirmed", "formal_final_test_rejected"):
            if field in scope:
                _check_type(scope[field], _is_bool(scope[field]), issues)


def _validate_runner_evidence_consistency(
    payload: dict[str, Any], issues: _Issues
) -> None:
    no_real = payload.get("no_real_llm_evidence")
    no_glob = payload.get("no_uncontrolled_glob_evidence")
    manifest_only = payload.get("manifest_only_evidence")
    scope = payload.get("scope_evidence")

    comparisons = (
        (payload.get("requested_provider"), no_real, "requested_provider"),
        (payload.get("requested_provider_kind"), no_real, "requested_provider_kind"),
        (payload.get("accepted_provider"), no_real, "accepted_provider"),
        (payload.get("requested_input_mode"), no_glob, "requested_input_mode"),
        (payload.get("accepted_input_mode"), no_glob, "accepted_input_mode"),
        (payload.get("accepted_manifest_scope"), scope, "manifest_scope"),
    )
    for top_value, evidence, evidence_field in comparisons:
        if type(evidence) is dict and evidence_field in evidence:
            if top_value != evidence[evidence_field]:
                issues.add("invalid_receipt_state")

    for top_field, evidence_field in (
        ("manifest_hash", "manifest_hash"),
        ("validation_receipt_id", "validation_receipt_id"),
    ):
        top_value = payload.get(top_field)
        if (
            top_value is not None
            and type(manifest_only) is dict
            and manifest_only.get(evidence_field) is not None
            and top_value != manifest_only[evidence_field]
        ):
            issues.add("invalid_receipt_state")


def _contains_final_test_marker(values: Any) -> bool:
    if type(values) is not list:
        return False
    return any(
        type(value) is str
        and "final_test" in value.lower().replace("-", "_")
        for value in values
    )


def _rejection_is_supported(
    reason: Any,
    no_real: Any,
    no_final: Any,
    no_glob: Any,
    scope: Any,
) -> bool:
    if reason == "real_provider_forbidden":
        return (
            type(no_real) is dict
            and no_real.get("requested_provider_kind") == "real"
            and no_real.get("accepted_provider") is None
            and no_real.get("decision") == "reject"
        )
    if reason == "unknown_provider":
        return (
            type(no_real) is dict
            and no_real.get("requested_provider_kind") == "unknown"
            and no_real.get("accepted_provider") is None
            and no_real.get("decision") == "reject"
        )
    if reason == "uncontrolled_glob_forbidden":
        return (
            type(no_glob) is dict
            and no_glob.get("requested_input_mode")
            in {"directory_glob", "implicit_default_glob"}
            and no_glob.get("glob_detected") is True
            and no_glob.get("accepted_input_mode") is None
            and no_glob.get("decision") == "reject"
        )
    if reason == "final_test_scope_forbidden":
        final_test_detected = (
            type(no_final) is dict
            and (
                no_final.get("final_test_scope_present") is True
                or _contains_final_test_marker(no_final.get("manifest_scopes_loaded"))
                or _contains_final_test_marker(no_final.get("manifests_loaded"))
                or _contains_final_test_marker(no_final.get("paths_scanned_or_loaded"))
            )
            and no_final.get("decision") == "reject"
        )
        scope_rejected = (
            type(scope) is dict
            and scope.get("formal_final_test_rejected") is True
            and scope.get("decision") == "reject"
        )
        return final_test_detected or scope_rejected
    if reason == "manifest_scope_forbidden":
        return (
            type(scope) is dict
            and scope.get("decision") == "reject"
            and (
                scope.get("manifest_scope") in {
                    "formal_train",
                    "formal_dev",
                    "formal_final_test",
                }
                or scope.get("formal_final_test_rejected") is True
                or scope.get("pilot_nonformal_confirmed") is False
            )
        )
    # No generic fallback: a reason without an explicit predicate is
    # unsupported by this schema version and therefore fails closed.
    return False


def _validate_runner_state(payload: dict[str, Any], issues: _Issues) -> None:
    status = payload.get("status")
    accepted_execution = payload.get("accepted_execution")
    scheduled = payload.get("scheduled_run_ids")
    rejection_reason = payload.get("rejection_reason")
    requested_kind = payload.get("requested_provider_kind")
    accepted_provider = payload.get("accepted_provider")

    no_real = payload.get("no_real_llm_evidence")
    no_final = payload.get("no_final_test_input_evidence")
    no_glob = payload.get("no_uncontrolled_glob_evidence")
    manifest_only = payload.get("manifest_only_evidence")
    scope = payload.get("scope_evidence")

    if status == "preflight_validated":
        if (
            accepted_execution is not False
            or scheduled != []
            or rejection_reason is not None
            or payload.get("gate_p2_authorization_id") is not None
            or payload.get("started_at") is not None
            or requested_kind not in {"mock", "file"}
            or payload.get("requested_input_mode") != "manifest_file"
            or accepted_provider not in {"mock", "file"}
            or payload.get("accepted_input_mode") != "manifest_file"
            or payload.get("accepted_manifest_scope") != _PILOT_MANIFEST_SCOPE
            or any(
                type(payload.get(field)) is not str
                or not payload[field]
                for field in (
                    "manifest_hash",
                    "canonical_manifest_hash",
                    "objective_version",
                    "validation_receipt_id",
                    "validation_receipt_hash",
                )
            )
            or payload.get("matrix_scope") != _PILOT_MATRIX_SCOPE
            or type(no_real) is not dict
            or no_real.get("decision") != "pass"
            or no_real.get("requested_provider_kind") not in {"mock", "file"}
            or no_real.get("accepted_provider") not in {"mock", "file"}
            or type(no_final) is not dict
            or no_final.get("decision") != "pass"
            or no_final.get("final_test_scope_present") is not False
            or _contains_final_test_marker(no_final.get("manifest_scopes_loaded"))
            or _contains_final_test_marker(no_final.get("manifests_loaded"))
            or _contains_final_test_marker(no_final.get("paths_scanned_or_loaded"))
            or type(no_glob) is not dict
            or no_glob.get("decision") != "pass"
            or no_glob.get("glob_detected") is not False
            or no_glob.get("requested_input_mode") != "manifest_file"
            or no_glob.get("accepted_input_mode") != "manifest_file"
            or type(manifest_only) is not dict
            or manifest_only.get("decision") != "pass"
            or not _is_string(manifest_only.get("manifest_path"))
            or not _is_string(manifest_only.get("manifest_hash"))
            or not _is_string(manifest_only.get("validation_receipt_id"))
            or type(scope) is not dict
            or scope.get("decision") != "pass"
            or scope.get("manifest_scope") != _PILOT_MANIFEST_SCOPE
            or scope.get("matrix_scope") != _PILOT_MATRIX_SCOPE
            or scope.get("pilot_nonformal_confirmed") is not True
            or scope.get("formal_final_test_rejected") is not False
        ):
            issues.add("invalid_receipt_state")
    elif status == "preflight_rejected":
        if (
            accepted_execution is not False
            or accepted_provider is not None
            or payload.get("accepted_input_mode") is not None
            or payload.get("accepted_manifest_scope") is not None
            or scheduled != []
            or not _is_string(rejection_reason)
            or not _rejection_is_supported(
                rejection_reason,
                no_real,
                no_final,
                no_glob,
                scope,
            )
        ):
            issues.add("invalid_receipt_state")

    if requested_kind in {"real", "unknown"}:
        allowed_reasons = (
            {"real_provider_forbidden"}
            if requested_kind == "real"
            else {"unknown_provider"}
        )
        if (
            status != "preflight_rejected"
            or accepted_provider is not None
            or accepted_execution is not False
            or rejection_reason not in allowed_reasons
            or type(no_real) is not dict
            or no_real.get("decision") != "reject"
        ):
            issues.add("invalid_receipt_state")


__all__ = [
    "SchemaValidationResult",
    "validate_manifest_validation_receipt_schema",
    "validate_pilot_manifest_schema",
    "validate_runner_receipt_schema",
]
