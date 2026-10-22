"""Pure in-memory PIV-04 pilot validation receipt construction.

This module binds caller-supplied raw manifest bytes, the corresponding JSON
object, and two already-produced validation evidence objects.  It deliberately
does not acquire paths, inspect files, invoke providers, schedule work, execute
candidates, or authorize a pilot.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
from typing import Any, Mapping

from .pilot_integrity import (
    CANONICALIZATION_ALGORITHM,
    CANONICALIZATION_VERSION,
    compute_object_hash,
    sha256_hex_bytes,
    validate_sha256_hex,
)


RECEIPT_VERSION = "pilot-validation-receipt-v2"
RECEIPT_SCOPE = "pilot_validation"
_PREVALIDATION_SCHEMA_VERSION = "pilot-prevalidation-core-v1"
_PATH_VALIDATION_SCHEMA_VERSION = "pilot-path-validation-v1"

_SIGNATURE_FIELDS = frozenset({"signature", "signatures"})
_PREVALIDATION_FIELDS = (
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
    "canonicalization_algorithm",
    "canonicalization_version",
    "binding_available",
    "binding_unavailable_reason",
    "execution_authorized",
    "gate_p2_closed",
)
_PATH_VALIDATION_FIELDS = (
    "path_validation_schema_version",
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
)
_REQUIRED_RECEIPT_FIELDS = frozenset(
    {
        "receipt_version",
        "receipt_scope",
        "validation_receipt_id",
        "status",
        "manifest_hash",
        "raw_manifest_bytes_hash",
        "manifest_object_hash",
        "validator_identity",
        "prevalidation_status",
        "path_validation_status",
        "prevalidation_evidence",
        "path_validation_evidence",
        "rejection_reasons",
        "formal_evidence_eligible",
        "execution_authorized",
        "gate_p2_closed",
    }
)
_ALLOWED_RECEIPT_FIELDS = _REQUIRED_RECEIPT_FIELDS | _SIGNATURE_FIELDS

_PREVALIDATION_REQUIRED_FIELDS = frozenset(_PREVALIDATION_FIELDS)
_PATH_VALIDATION_REQUIRED_FIELDS = frozenset(_PATH_VALIDATION_FIELDS)
_DUPLICATE_SUMMARY_FIELDS = frozenset(
    {
        "instance_id_duplicates",
        "file_hash_duplicates",
        "canonical_path_duplicates",
        "file_identity_duplicates",
        "generation_identity_duplicates",
    }
)
_PREVALIDATION_FAILURE_LAYERS = frozenset(
    {"schema", "integrity", "binding", "raw_manifest", "canonicalization"}
)
_REJECTED_FILE_IDENTITY_STATES = frozenset(
    {
        "supported_pass",
        "unsupported_file_identity_check",
        "unsupported",
        "not_reached",
        "failed",
    }
)


@dataclass(frozen=True)
class ValidationResult:
    """Fail-closed verification result for an inert receipt."""

    valid: bool
    rejection_reasons: tuple[str, ...]


class _ReasonCollector:
    def __init__(self) -> None:
        self._reasons: list[dict[str, str]] = []

    def add(self, layer: str, reason: str) -> None:
        item = {"layer": layer, "reason": reason}
        if item not in self._reasons:
            self._reasons.append(item)

    @property
    def values(self) -> list[dict[str, str]]:
        return deepcopy(self._reasons)

    def __bool__(self) -> bool:
        return bool(self._reasons)


def _duplicate_key_rejected(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def _reject_nonstandard_number(value: str) -> None:
    raise ValueError(f"non_canonical_json_number: {value}")


def _parse_raw_manifest(
    raw_manifest_bytes: Any,
    reasons: _ReasonCollector,
) -> dict[str, Any] | None:
    if type(raw_manifest_bytes) is not bytes:
        raise TypeError("raw_manifest_type_invalid: raw_manifest_bytes must be bytes")

    try:
        text = raw_manifest_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        reasons.add("raw_manifest", "utf8_decode_error")
        return None

    try:
        parsed = json.loads(
            text,
            object_pairs_hook=_duplicate_key_rejected,
            parse_constant=_reject_nonstandard_number,
        )
    except ValueError as exc:
        reason = (
            "duplicate_json_key"
            if "duplicate_json_key" in str(exc)
            else "raw_manifest_parse_error"
        )
        reasons.add("raw_manifest", reason)
        return None

    if type(parsed) is not dict:
        reasons.add("raw_manifest", "raw_manifest_not_object")
        return None

    try:
        compute_object_hash(parsed)
    except (TypeError, ValueError) as exc:
        message = str(exc).lower()
        if "integer" in message:
            reasons.add("raw_manifest", "unsupported_integer_domain")
        reasons.add("raw_manifest", "non_canonical_json")
        return parsed
    return parsed


def _safe_object_hash(
    manifest_obj: Any,
    reasons: _ReasonCollector,
) -> str | None:
    if type(manifest_obj) is not dict:
        reasons.add("binding", "manifest_object_type_invalid")
        return None
    try:
        return compute_object_hash(manifest_obj)
    except (TypeError, ValueError) as exc:
        message = str(exc).lower()
        if "integer" in message:
            reasons.add("binding", "unsupported_integer_domain")
        reasons.add("binding", "non_canonical_json")
        return None


def _result_id_matches(result: Any, id_field: str) -> bool:
    if type(result) is not dict:
        return False
    supplied_id = result.get(id_field)
    if not validate_sha256_hex(supplied_id).valid:
        return False
    body = {key: value for key, value in result.items() if key != id_field}
    try:
        return supplied_id == compute_object_hash(body)
    except (TypeError, ValueError):
        return False


def _copy_evidence(
    result: Any,
    fields: tuple[str, ...],
) -> dict[str, Any]:
    if type(result) is not dict:
        return {field: None for field in fields}
    return {field: deepcopy(result.get(field)) for field in fields}


def _mark_malformed(
    reasons: _ReasonCollector,
    branch: str,
    reason: str,
) -> None:
    reasons.add("binding", f"malformed_{branch}_evidence")
    reasons.add("binding", reason)


def _is_string_list(value: Any, *, allow_empty: bool) -> bool:
    return (
        type(value) is list
        and (allow_empty or bool(value))
        and all(type(item) is str and bool(item) for item in value)
    )


def _is_nonnegative_integer(value: Any) -> bool:
    return type(value) is int and value >= 0


def _prevalidation_evidence(
    result: Any,
    manifest_object_hash: str | None,
    reasons: _ReasonCollector,
) -> tuple[dict[str, Any], str | None, bool]:
    evidence = _copy_evidence(result, _PREVALIDATION_FIELDS)
    malformed = False

    def reject(reason: str) -> None:
        nonlocal malformed
        malformed = True
        _mark_malformed(reasons, "prevalidation", reason)

    if type(result) is not dict:
        reject("prevalidation_result_invalid")
        return evidence, None, malformed

    if set(result) != _PREVALIDATION_REQUIRED_FIELDS:
        reject("prevalidation_evidence_fields_invalid")
        for field in sorted(
            set(result) - _PREVALIDATION_REQUIRED_FIELDS,
            key=lambda value: repr(value),
        ):
            reject(f"unknown_prevalidation_field:{field}")
    missing_fields = _PREVALIDATION_REQUIRED_FIELDS - set(result)
    for field in sorted(missing_fields):
        reject(f"missing_prevalidation_field:{field}")

    schema_version = result.get("prevalidation_schema_version")
    if type(schema_version) is not str:
        reject("prevalidation_schema_version_type_invalid")
    elif schema_version != _PREVALIDATION_SCHEMA_VERSION:
        reject("prevalidation_schema_version_invalid")

    status = result.get("status")
    if status not in {"valid", "rejected"}:
        reject("prevalidation_status_invalid")
    if result.get("result_scope") != "pure_object_prevalidation":
        reject("prevalidation_scope_invalid")

    for field in ("schema_valid", "integrity_valid", "binding_available"):
        if type(result.get(field)) is not bool:
            reject(f"prevalidation_{field}_type_invalid")
    for field in ("execution_authorized", "gate_p2_closed"):
        if type(result.get(field)) is not bool:
            reject(f"prevalidation_{field}_type_invalid")

    if not _result_id_matches(result, "prevalidation_result_id"):
        reject("prevalidation_result_id_invalid_or_mismatch")
    if result.get("execution_authorized") is not False:
        reject("prevalidation_execution_authorization_forbidden")
    if result.get("gate_p2_closed") is not False:
        reject("prevalidation_gate_p2_closure_forbidden")

    binding_available = result.get("binding_available")
    if binding_available is False:
        reasons.add("binding", "binding_unavailable")
    binding_reason = result.get("binding_unavailable_reason")
    if binding_reason is not None and (
        type(binding_reason) is not str or not binding_reason
    ):
        reject("prevalidation_binding_unavailable_reason_type_invalid")
    if binding_available is True and binding_reason is not None:
        reject("prevalidation_binding_state_invalid")
    if binding_available is False and (
        type(binding_reason) is not str or not binding_reason
    ):
        reject("prevalidation_binding_unavailable_reason_missing")

    if result.get("canonicalization_algorithm") != CANONICALIZATION_ALGORITHM:
        reject("canonicalization_algorithm_mismatch")
    if result.get("canonicalization_version") != CANONICALIZATION_VERSION:
        reject("canonicalization_version_mismatch")

    object_hash_fields = (
        "manifest_object_hash",
        "pilot_family_matrix_object_hash",
        "pilot_split_rule_object_hash",
    )
    for field in object_hash_fields:
        value = result.get(field)
        if binding_available is False and status == "rejected" and value is None:
            continue
        if not validate_sha256_hex(value).valid:
            reject(f"prevalidation_{field}_invalid")

    if (
        manifest_object_hash is not None
        and result.get("manifest_object_hash") != manifest_object_hash
    ):
        reject("prevalidation_manifest_object_hash_mismatch")

    source_reasons = result.get("rejection_reasons")
    if not _is_string_list(source_reasons, allow_empty=True):
        reject("prevalidation_rejection_reasons_invalid")
        source_reasons = []

    failure_layer = result.get("failure_layer")
    if failure_layer is not None and (
        type(failure_layer) is not str or not failure_layer
    ):
        reject("prevalidation_failure_layer_type_invalid")

    if status == "valid":
        if result.get("schema_valid") is not True:
            reject("prevalidation_valid_requires_schema_valid")
        if result.get("integrity_valid") is not True:
            reject("prevalidation_valid_requires_integrity_valid")
        if failure_layer not in {None, ""}:
            reject("prevalidation_valid_failure_layer_forbidden")
        if source_reasons != []:
            reject("prevalidation_valid_with_rejection_reasons")
        if binding_available is not True:
            reject("prevalidation_valid_requires_binding")
    elif status == "rejected":
        if failure_layer not in _PREVALIDATION_FAILURE_LAYERS:
            reject("prevalidation_rejected_failure_layer_invalid")
        if not source_reasons:
            reject("prevalidation_rejected_without_reason")
        for reason in source_reasons:
            reasons.add(
                failure_layer
                if failure_layer in _PREVALIDATION_FAILURE_LAYERS
                else "binding",
                reason,
            )

    return evidence, status if type(status) is str else None, malformed


def _path_reason_layer(reason: str) -> str:
    if reason.startswith("duplicate_"):
        return "duplicate"
    if (
        "formal" in reason
        or "final_test" in reason
        or "artifact_promotion" in reason
        or "lockbox" in reason
    ):
        return "scope"
    return "path"


def _path_validation_evidence(
    result: Any,
    manifest_object_hash: str | None,
    reasons: _ReasonCollector,
) -> tuple[dict[str, Any], str | None, bool]:
    evidence = _copy_evidence(result, _PATH_VALIDATION_FIELDS)
    malformed = False

    def reject(reason: str) -> None:
        nonlocal malformed
        malformed = True
        _mark_malformed(reasons, "path", reason)

    if type(result) is not dict:
        reject("path_validation_result_invalid")
        return evidence, None, malformed

    if set(result) != _PATH_VALIDATION_REQUIRED_FIELDS:
        reject("path_validation_evidence_fields_invalid")
        for field in sorted(
            set(result) - _PATH_VALIDATION_REQUIRED_FIELDS,
            key=lambda value: repr(value),
        ):
            reject(f"unknown_path_validation_field:{field}")
    missing_fields = _PATH_VALIDATION_REQUIRED_FIELDS - set(result)
    for field in sorted(missing_fields):
        reject(f"missing_path_validation_field:{field}")

    schema_version = result.get("path_validation_schema_version")
    if type(schema_version) is not str:
        reject("path_validation_schema_version_type_invalid")
    elif schema_version != _PATH_VALIDATION_SCHEMA_VERSION:
        reject("path_validation_schema_version_invalid")

    status = result.get("status")
    if status not in {"valid", "rejected"}:
        reject("path_validation_status_invalid")
    if result.get("result_scope") != "path_duplicate_validation":
        reject("path_validation_scope_invalid")
    if not _result_id_matches(result, "path_validation_result_id"):
        reject("path_validation_result_id_invalid_or_mismatch")

    for field in (
        "execution_authorized",
        "gate_p2_closed",
        "no_glob_confirmed",
        "no_directory_discovery_confirmed",
    ):
        if type(result.get(field)) is not bool:
            reject(f"path_{field}_type_invalid")

    if result.get("execution_authorized") is not False:
        reject("path_execution_authorization_forbidden")
    if result.get("gate_p2_closed") is not False:
        reject("path_gate_p2_closure_forbidden")
    if result.get("no_glob_confirmed") is not True:
        reject("glob_forbidden")
    if result.get("no_directory_discovery_confirmed") is not True:
        reject("directory_discovery_forbidden")

    if not validate_sha256_hex(result.get("manifest_object_hash")).valid:
        reject("path_manifest_object_hash_invalid")
    if not validate_sha256_hex(result.get("approved_root_fingerprint")).valid:
        reject("path_approved_root_fingerprint_invalid")

    if (
        manifest_object_hash is not None
        and result.get("manifest_object_hash") != manifest_object_hash
    ):
        reject("path_manifest_object_hash_mismatch")

    duplicate_summary = result.get("duplicate_validation_summary")
    if type(duplicate_summary) is not dict:
        reject("path_duplicate_validation_summary_invalid")
        duplicate_summary = {}
    elif set(duplicate_summary) != _DUPLICATE_SUMMARY_FIELDS:
        reject("path_duplicate_validation_summary_fields_invalid")
    for field in _DUPLICATE_SUMMARY_FIELDS:
        if not _is_nonnegative_integer(duplicate_summary.get(field)):
            reject(f"path_duplicate_count_invalid:{field}")

    identity_state = result.get("file_identity_check")
    if type(identity_state) is not str or identity_state not in _REJECTED_FILE_IDENTITY_STATES:
        reject("path_file_identity_check_invalid")

    source_reasons = result.get("rejection_reasons")
    if not _is_string_list(source_reasons, allow_empty=True):
        reject("path_rejection_reasons_invalid")
        source_reasons = []

    if status == "rejected":
        if source_reasons:
            for reason in source_reasons:
                reasons.add(_path_reason_layer(reason), reason)
        else:
            reject("path_validation_rejected_without_reason")
    elif status == "valid":
        if source_reasons != []:
            reject("path_valid_with_rejection_reasons")
        if any(
            _is_nonnegative_integer(duplicate_summary.get(field))
            and duplicate_summary.get(field) != 0
            for field in _DUPLICATE_SUMMARY_FIELDS
        ):
            reject("path_valid_with_duplicate_findings")
        if identity_state != "supported_pass":
            reject("path_valid_without_supported_file_identity")

    return evidence, status if type(status) is str else None, malformed


def _receipt_body(receipt: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(value)
        for key, value in receipt.items()
        if key != "validation_receipt_id" and key not in _SIGNATURE_FIELDS
    }


def _compute_receipt_id(receipt: Mapping[str, Any]) -> str:
    return compute_object_hash(_receipt_body(receipt))


def _build_from_snapshots(
    *,
    raw_manifest_bytes: bytes,
    manifest_obj: Any,
    prevalidation_result: Any,
    path_validation_result: Any,
    validator_identity: Any,
    validation_state: dict[str, bool] | None = None,
) -> dict[str, Any]:
    reasons = _ReasonCollector()
    raw_hash = sha256_hex_bytes(raw_manifest_bytes)
    parsed_manifest = _parse_raw_manifest(raw_manifest_bytes, reasons)
    manifest_object_hash = _safe_object_hash(manifest_obj, reasons)

    if parsed_manifest is not None and parsed_manifest != manifest_obj:
        reasons.add("raw_manifest", "raw_manifest_object_mismatch")
    if parsed_manifest is not None and manifest_object_hash is not None:
        try:
            parsed_hash = compute_object_hash(parsed_manifest)
        except (TypeError, ValueError):
            parsed_hash = None
        if parsed_hash is None:
            reasons.add("raw_manifest", "non_canonical_json")
        elif parsed_hash != manifest_object_hash:
            reasons.add("raw_manifest", "raw_manifest_object_mismatch")

    if type(validator_identity) is not str or not validator_identity:
        reasons.add("binding", "validator_identity_invalid")

    (
        prevalidation_evidence,
        prevalidation_status,
        prevalidation_malformed,
    ) = _prevalidation_evidence(
        prevalidation_result,
        manifest_object_hash,
        reasons,
    )
    path_evidence, path_status, path_malformed = _path_validation_evidence(
        path_validation_result,
        manifest_object_hash,
        reasons,
    )
    if validation_state is not None:
        validation_state["upstream_evidence_malformed"] = (
            prevalidation_malformed or path_malformed
        )

    status = (
        "valid"
        if not reasons
        and prevalidation_status == "valid"
        and path_status == "valid"
        else "rejected"
    )
    body: dict[str, Any] = {
        "receipt_version": RECEIPT_VERSION,
        "receipt_scope": RECEIPT_SCOPE,
        "status": status,
        "manifest_hash": raw_hash,
        "raw_manifest_bytes_hash": raw_hash,
        "manifest_object_hash": manifest_object_hash,
        "validator_identity": validator_identity,
        "prevalidation_status": prevalidation_status,
        "path_validation_status": path_status,
        "prevalidation_evidence": prevalidation_evidence,
        "path_validation_evidence": path_evidence,
        "rejection_reasons": reasons.values,
        "formal_evidence_eligible": False,
        "execution_authorized": False,
        "gate_p2_closed": False,
    }
    return {**body, "validation_receipt_id": compute_object_hash(body)}


def build_pilot_validation_receipt(
    *,
    raw_manifest_bytes: bytes,
    manifest_obj: Mapping[str, Any],
    prevalidation_result: Mapping[str, Any],
    path_validation_result: Mapping[str, Any],
    validator_identity: str,
) -> dict[str, Any]:
    """Build an inert receipt from explicit in-memory inputs only."""

    if type(raw_manifest_bytes) is not bytes:
        raise TypeError("raw_manifest_type_invalid: raw_manifest_bytes must be bytes")
    snapshots = deepcopy(
        (
            raw_manifest_bytes,
            manifest_obj,
            prevalidation_result,
            path_validation_result,
            validator_identity,
        )
    )
    raw, manifest, prevalidation, path_validation, identity = snapshots
    return _build_from_snapshots(
        raw_manifest_bytes=raw,
        manifest_obj=manifest,
        prevalidation_result=prevalidation,
        path_validation_result=path_validation,
        validator_identity=identity,
    )


def _verification_failure(*reasons: str) -> ValidationResult:
    unique: list[str] = []
    for reason in reasons:
        if reason not in unique:
            unique.append(reason)
    return ValidationResult(False, tuple(unique or ["receipt_verification_failed"]))


def verify_pilot_validation_receipt(
    receipt_obj: Mapping[str, Any],
    *,
    raw_manifest_bytes: bytes,
    manifest_obj: Mapping[str, Any],
    prevalidation_result: Mapping[str, Any],
    path_validation_result: Mapping[str, Any],
) -> ValidationResult:
    """Verify receipt identity and all explicit input/evidence bindings."""

    if type(receipt_obj) is not dict:
        return _verification_failure("invalid_receipt_object")
    if type(raw_manifest_bytes) is not bytes:
        return _verification_failure("raw_manifest_type_invalid")

    try:
        receipt = deepcopy(receipt_obj)
        raw = deepcopy(raw_manifest_bytes)
        manifest = deepcopy(manifest_obj)
        prevalidation = deepcopy(prevalidation_result)
        path_validation = deepcopy(path_validation_result)
    except Exception:
        return _verification_failure("input_snapshot_failed")

    actual_fields = set(receipt)
    if not _REQUIRED_RECEIPT_FIELDS.issubset(actual_fields):
        return _verification_failure("missing_receipt_fields")
    if not actual_fields.issubset(_ALLOWED_RECEIPT_FIELDS):
        return _verification_failure("unknown_receipt_fields")

    # Establish receipt integrity before interpreting its semantic branch.
    # This distinguishes an old-ID tamper from a coherently re-signed but
    # contract-invalid receipt.
    receipt_id = receipt.get("validation_receipt_id")
    if not validate_sha256_hex(receipt_id).valid:
        return _verification_failure("validation_receipt_id_invalid")
    try:
        if receipt_id != _compute_receipt_id(receipt):
            return _verification_failure("validation_receipt_id_hash_mismatch")
    except (TypeError, ValueError):
        return _verification_failure("validation_receipt_non_canonical_json")

    if receipt.get("receipt_version") != RECEIPT_VERSION:
        return _verification_failure("invalid_receipt_version")
    if receipt.get("receipt_scope") != RECEIPT_SCOPE:
        return _verification_failure("invalid_receipt_scope_formal_forbidden")
    if receipt.get("status") not in {"valid", "rejected"}:
        return _verification_failure("invalid_receipt_status")
    if receipt.get("execution_authorized") is not False:
        return _verification_failure("execution_authorization_forbidden")
    if receipt.get("gate_p2_closed") is not False:
        return _verification_failure("gate_p2_closure_forbidden")
    if receipt.get("formal_evidence_eligible") is not False:
        return _verification_failure("formal_evidence_forbidden")

    validator_identity = receipt.get("validator_identity")
    validation_state: dict[str, bool] = {}
    try:
        expected = _build_from_snapshots(
            raw_manifest_bytes=raw,
            manifest_obj=manifest,
            prevalidation_result=prevalidation,
            path_validation_result=path_validation,
            validator_identity=validator_identity,
            validation_state=validation_state,
        )
    except (TypeError, ValueError):
        return _verification_failure("raw_manifest_or_binding_invalid")

    if validation_state.get("upstream_evidence_malformed", True):
        return _verification_failure("malformed_upstream_evidence")

    supplied_body = _receipt_body(receipt)
    expected_body = _receipt_body(expected)
    mismatch_reasons: list[str] = []
    if receipt.get("manifest_hash") != expected.get("manifest_hash"):
        mismatch_reasons.append("raw_manifest_hash_mismatch")
    if receipt.get("raw_manifest_bytes_hash") != expected.get(
        "raw_manifest_bytes_hash"
    ):
        mismatch_reasons.append("raw_manifest_bytes_hash_mismatch")
    if receipt.get("manifest_object_hash") != expected.get("manifest_object_hash"):
        mismatch_reasons.append("manifest_object_hash_mismatch")
    if receipt.get("prevalidation_evidence") != expected.get(
        "prevalidation_evidence"
    ):
        mismatch_reasons.append("prevalidation_evidence_binding_mismatch")
    if receipt.get("path_validation_evidence") != expected.get(
        "path_validation_evidence"
    ):
        mismatch_reasons.append("path_validation_evidence_binding_mismatch")
    if supplied_body != expected_body:
        mismatch_reasons.append("receipt_body_binding_mismatch")
    if mismatch_reasons:
        return _verification_failure(*mismatch_reasons)
    return ValidationResult(True, ())


__all__ = [
    "RECEIPT_SCOPE",
    "RECEIPT_VERSION",
    "ValidationResult",
    "build_pilot_validation_receipt",
    "verify_pilot_validation_receipt",
]
