"""Pure-object prevalidation core for non-formal pilot manifests.

This module composes the existing schema and scoped-integrity checks over
already supplied Python objects.  It deliberately does not read files, resolve
paths, issue formal validation receipts, or authorize execution.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from .pilot_contracts import validate_pilot_manifest_schema
from .pilot_integrity import (
    CANONICALIZATION_ALGORITHM,
    CANONICALIZATION_VERSION,
    compute_object_hash,
    validate_sha256_hex,
    verify_pilot_scoped_hash_binding,
)


_RESULT_SCOPE = "pure_object_prevalidation"
_RESULT_SCHEMA_VERSION = "pilot-prevalidation-core-v1"
_RESULT_FIELDS = {
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


@dataclass(frozen=True)
class PilotManifestPrevalidationResult:
    """Structured outcome from the inert pure-object prevalidation core."""

    valid: bool
    rejection_reasons: tuple[str, ...]
    status: str
    result_scope: str
    schema_valid: bool
    integrity_valid: bool | None
    failure_layer: str | None
    execution_authorized: bool = False
    gate_p2_closed: bool = False


@dataclass(frozen=True)
class PrevalidationBindingResult:
    """Structured verification result for a prevalidation result object."""

    valid: bool
    rejection_reasons: tuple[str, ...]


@dataclass(frozen=True)
class _CoreEvaluation:
    """One evaluation over a single entry snapshot and its object hashes."""

    validation: PilotManifestPrevalidationResult
    object_hashes: tuple[str | None, str | None, str | None]
    binding_available: bool
    binding_unavailable_reason: str | None


def _rejected(
    reasons: tuple[str, ...],
    *,
    schema_valid: bool,
    integrity_valid: bool | None,
    failure_layer: str,
) -> PilotManifestPrevalidationResult:
    return PilotManifestPrevalidationResult(
        valid=False,
        rejection_reasons=reasons or ("prevalidation_rejected",),
        status="rejected",
        result_scope=_RESULT_SCOPE,
        schema_valid=schema_valid,
        integrity_valid=integrity_valid,
        failure_layer=failure_layer,
    )


def _object_hashes(
    manifest_snapshot: Any,
    family_matrix_snapshot: Any,
    split_rule_snapshot: Any,
) -> tuple[
    tuple[str | None, str | None, str | None],
    str | None,
]:
    try:
        return (
            (
                compute_object_hash(manifest_snapshot),
                compute_object_hash(family_matrix_snapshot),
                compute_object_hash(split_rule_snapshot),
            ),
            None,
        )
    except (TypeError, ValueError) as exc:
        return (None, None, None), f"non_canonical_json: {exc}"


def _inputs_match_snapshots(
    manifest: Any,
    family_matrix: Any,
    split_rule: Any,
    snapshots: tuple[Any, Any, Any],
) -> bool:
    try:
        return (manifest, family_matrix, split_rule) == snapshots
    except Exception:
        return False


def _evaluation(
    manifest: Any,
    *,
    pilot_family_matrix_obj: Any,
    pilot_split_rule_obj: Any,
) -> _CoreEvaluation:
    snapshots = deepcopy(
        (manifest, pilot_family_matrix_obj, pilot_split_rule_obj)
    )
    manifest_snapshot, family_matrix_snapshot, split_rule_snapshot = snapshots

    schema_result = validate_pilot_manifest_schema(manifest)
    if not _inputs_match_snapshots(
        manifest,
        pilot_family_matrix_obj,
        pilot_split_rule_obj,
        snapshots,
    ):
        object_hashes, binding_error = _object_hashes(*snapshots)
        return _CoreEvaluation(
            validation=_rejected(
                ("input_mutated_during_schema_validation",),
                schema_valid=schema_result.valid,
                integrity_valid=None,
                failure_layer="schema",
            ),
            object_hashes=object_hashes,
            binding_available=binding_error is None,
            binding_unavailable_reason=binding_error,
        )

    if not schema_result.valid:
        object_hashes, binding_error = _object_hashes(*snapshots)
        return _CoreEvaluation(
            validation=_rejected(
                tuple(schema_result.rejection_reasons),
                schema_valid=False,
                integrity_valid=None,
                failure_layer="schema",
            ),
            object_hashes=object_hashes,
            binding_available=binding_error is None,
            binding_unavailable_reason=binding_error,
        )

    integrity_result = verify_pilot_scoped_hash_binding(
        manifest,
        pilot_family_matrix_obj,
        pilot_split_rule_obj,
    )
    if not _inputs_match_snapshots(
        manifest,
        pilot_family_matrix_obj,
        pilot_split_rule_obj,
        snapshots,
    ):
        object_hashes, binding_error = _object_hashes(*snapshots)
        return _CoreEvaluation(
            validation=_rejected(
                ("input_mutated_during_integrity_validation",),
                schema_valid=True,
                integrity_valid=False,
                failure_layer="integrity",
            ),
            object_hashes=object_hashes,
            binding_available=binding_error is None,
            binding_unavailable_reason=binding_error,
        )

    object_hashes, binding_error = _object_hashes(*snapshots)
    if not integrity_result.valid:
        return _CoreEvaluation(
            validation=_rejected(
                tuple(integrity_result.rejection_reasons),
                schema_valid=True,
                integrity_valid=False,
                failure_layer="integrity",
            ),
            object_hashes=object_hashes,
            binding_available=binding_error is None,
            binding_unavailable_reason=binding_error,
        )

    if binding_error is not None:
        return _CoreEvaluation(
            validation=_rejected(
                (binding_error,),
                schema_valid=True,
                integrity_valid=False,
                failure_layer="integrity",
            ),
            object_hashes=object_hashes,
            binding_available=False,
            binding_unavailable_reason=binding_error,
        )

    return _CoreEvaluation(
        validation=PilotManifestPrevalidationResult(
            valid=True,
            rejection_reasons=(),
            status="valid",
            result_scope=_RESULT_SCOPE,
            schema_valid=True,
            integrity_valid=True,
            failure_layer=None,
        ),
        object_hashes=object_hashes,
        binding_available=True,
        binding_unavailable_reason=None,
    )


def validate_pilot_manifest_core(
    manifest: Any,
    *,
    pilot_family_matrix_obj: Any,
    pilot_split_rule_obj: Any,
) -> PilotManifestPrevalidationResult:
    """Run schema first, then pure in-memory scoped-integrity validation."""

    return _evaluation(
        manifest,
        pilot_family_matrix_obj=pilot_family_matrix_obj,
        pilot_split_rule_obj=pilot_split_rule_obj,
    ).validation


def _result_body(
    evaluation: _CoreEvaluation,
) -> dict[str, Any]:
    validation = evaluation.validation
    object_hashes = evaluation.object_hashes

    return {
        "prevalidation_schema_version": _RESULT_SCHEMA_VERSION,
        "status": validation.status,
        "result_scope": validation.result_scope,
        "schema_valid": validation.schema_valid,
        "integrity_valid": validation.integrity_valid,
        "failure_layer": validation.failure_layer,
        "rejection_reasons": list(validation.rejection_reasons),
        "manifest_object_hash": object_hashes[0],
        "pilot_family_matrix_object_hash": object_hashes[1],
        "pilot_split_rule_object_hash": object_hashes[2],
        "binding_available": evaluation.binding_available,
        "binding_unavailable_reason": evaluation.binding_unavailable_reason,
        "canonicalization_algorithm": CANONICALIZATION_ALGORITHM,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "execution_authorized": False,
        "gate_p2_closed": False,
    }


def build_pilot_prevalidation_result(
    manifest: Any,
    *,
    pilot_family_matrix_obj: Any,
    pilot_split_rule_obj: Any,
) -> dict[str, Any]:
    """Build a deterministic object-binding result, not a formal receipt."""

    evaluation = _evaluation(
        manifest,
        pilot_family_matrix_obj=pilot_family_matrix_obj,
        pilot_split_rule_obj=pilot_split_rule_obj,
    )
    body = _result_body(evaluation)
    result_id = (
        compute_object_hash(body)
        if evaluation.binding_available
        else None
    )
    return {**body, "prevalidation_result_id": result_id}


def verify_pilot_prevalidation_result(
    manifest: Any,
    result: Any,
    *,
    pilot_family_matrix_obj: Any,
    pilot_split_rule_obj: Any,
) -> PrevalidationBindingResult:
    """Verify deterministic binding to the same three in-memory objects."""

    reasons: list[str] = []
    if type(result) is not dict:
        return PrevalidationBindingResult(False, ("invalid_result_object",))
    if set(result) != _RESULT_FIELDS:
        reasons.append("invalid_result_fields")
    if result.get("status") not in {"valid", "rejected"}:
        reasons.append("invalid_result_status")
    if result.get("result_scope") != _RESULT_SCOPE:
        reasons.append("invalid_result_scope")
    if result.get("execution_authorized") is not False:
        reasons.append("execution_authorization_forbidden")
    if result.get("gate_p2_closed") is not False:
        reasons.append("gate_p2_closure_forbidden")

    binding_available = result.get("binding_available")
    binding_reason = result.get("binding_unavailable_reason")
    if type(binding_available) is not bool:
        reasons.append("invalid_binding_state")
    elif binding_available:
        if binding_reason is not None:
            reasons.append("invalid_binding_state")
        for field in (
            "manifest_object_hash",
            "pilot_family_matrix_object_hash",
            "pilot_split_rule_object_hash",
        ):
            if not validate_sha256_hex(result.get(field)).valid:
                reasons.append("invalid_object_hash")
    else:
        reasons.append("binding_unavailable")
        if type(binding_reason) is not str or not binding_reason:
            reasons.append("invalid_binding_state")
        if any(
            result.get(field) is not None
            for field in (
                "manifest_object_hash",
                "pilot_family_matrix_object_hash",
                "pilot_split_rule_object_hash",
            )
        ):
            reasons.append("invalid_binding_state")

    result_id = result.get("prevalidation_result_id")
    if binding_available is False:
        if result_id is not None:
            reasons.append("invalid_prevalidation_result_id")
    elif not validate_sha256_hex(result_id).valid:
        reasons.append("invalid_prevalidation_result_id")
    else:
        try:
            body = {
                key: value
                for key, value in result.items()
                if key != "prevalidation_result_id"
            }
            if compute_object_hash(body) != result_id:
                reasons.append("prevalidation_result_id_mismatch")
        except (TypeError, ValueError):
            reasons.append("non_canonical_result")

    try:
        expected = build_pilot_prevalidation_result(
            manifest,
            pilot_family_matrix_obj=pilot_family_matrix_obj,
            pilot_split_rule_obj=pilot_split_rule_obj,
        )
    except (TypeError, ValueError):
        reasons.append("non_canonical_input")
    else:
        if result != expected:
            reasons.append("prevalidation_object_binding_mismatch")

    unique_reasons = tuple(dict.fromkeys(reasons))
    return PrevalidationBindingResult(not unique_reasons, unique_reasons)


__all__ = [
    "PilotManifestPrevalidationResult",
    "PrevalidationBindingResult",
    "build_pilot_prevalidation_result",
    "validate_pilot_manifest_core",
    "verify_pilot_prevalidation_result",
]
