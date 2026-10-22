"""Fail-closed policy helpers for generated operator lifecycle gates."""
from __future__ import annotations

import math
from typing import Any, Mapping

from .candidate_execution import (
    CandidateProxy,
    TRUSTED_EXECUTOR_IDENTITY,
    TRUSTED_EXECUTOR_SANDBOX_LEVEL,
)


REAL_PROVIDER = "langchain_openai_compatible"
REAL_PROVIDERS = frozenset({REAL_PROVIDER, "real_provider"})
GENERATED_ARTIFACT_TYPE = "generated_frozen_operator"
ALLOWED_RUNTIME_AUTHORIZATION_SOURCES = frozenset(
    {
        "current_config",
        "current_runtime_config",
        "current_session",
        "operator_evolution_runner_policy",
    }
)
ALLOWED_SANDBOX_LEVELS = frozenset(
    {"timeout_only", "restricted_subprocess", "capability_sandbox"}
)
REQUIRED_FAILURE_RATE_FIELDS = (
    "error_rate",
    "timeout_rate",
    "invalid_solution_rate",
    "validation_failed_rate",
    "execution_blocked_rate",
)


def parse_strict_bool(value: Any, *, field_name: str) -> bool:
    """Accept only literal ``True`` or ``False``; reject truthy substitutes."""
    if type(value) is not bool:
        raise TypeError(f"{field_name} must be a literal boolean")
    return value


def candidate_is_execution_eligible(
    validation: Any,
    callable_obj: Any,
    allow_unsafe_candidate_execution: Any,
) -> bool:
    """Return whether a validated callable has complete execution evidence."""
    if type(allow_unsafe_candidate_execution) is not bool:
        return False
    if not isinstance(callable_obj, CandidateProxy):
        return False
    if (
        getattr(validation, "validation_status", None) != "valid"
        or getattr(validation, "execution_status", None) != "success"
        or getattr(validation, "failure_type", None) != "success"
        or getattr(validation, "safe_to_execute", None) is not True
        or getattr(validation, "requires_human_risk_ack", None) is not False
    ):
        return False

    code_hash = getattr(validation, "code_hash", None)
    provider = getattr(validation, "source", None)
    sandbox_level = getattr(validation, "sandbox_level", None)
    claimed_sandbox_level = getattr(
        validation,
        "claimed_sandbox_level",
        sandbox_level,
    )
    effective_sandbox_level = getattr(
        validation,
        "effective_sandbox_level",
        None,
    )
    executor_identity = getattr(
        validation,
        "executor_identity",
        None,
    )
    runtime_authorization_source = getattr(
        validation, "runtime_authorization_source", None
    )
    deployment_allow = getattr(
        validation, "allow_real_provider_frozen_deployment", None
    )
    explicit_runtime_risk_ack = getattr(
        validation, "explicit_runtime_risk_ack", None
    )
    if not isinstance(code_hash, str) or not code_hash:
        return False
    if not isinstance(provider, str) or not provider:
        return False
    if sandbox_level not in ALLOWED_SANDBOX_LEVELS:
        return False
    if claimed_sandbox_level not in ALLOWED_SANDBOX_LEVELS:
        return False
    if claimed_sandbox_level != sandbox_level:
        return False
    if (
        claimed_sandbox_level != TRUSTED_EXECUTOR_SANDBOX_LEVEL
        or effective_sandbox_level != TRUSTED_EXECUTOR_SANDBOX_LEVEL
        or executor_identity != TRUSTED_EXECUTOR_IDENTITY
    ):
        return False
    if runtime_authorization_source not in ALLOWED_RUNTIME_AUTHORIZATION_SOURCES:
        return False
    if type(deployment_allow) is not bool or type(explicit_runtime_risk_ack) is not bool:
        return False
    if provider in REAL_PROVIDERS and (
        allow_unsafe_candidate_execution is not True
        or deployment_allow is not True
        or explicit_runtime_risk_ack is not True
    ):
        return False
    return True


def configure_candidate_preexecution_policy(
    validation: Any,
    allow_unsafe_candidate_execution: Any,
) -> None:
    """Populate runtime-owned gate evidence before any smoke execution."""
    allowed = parse_strict_bool(
        allow_unsafe_candidate_execution,
        field_name="allow_unsafe_candidate_execution",
    )
    provider = getattr(validation, "source", None)
    validation.sandbox_level = TRUSTED_EXECUTOR_SANDBOX_LEVEL
    validation.claimed_sandbox_level = TRUSTED_EXECUTOR_SANDBOX_LEVEL
    validation.effective_sandbox_level = TRUSTED_EXECUTOR_SANDBOX_LEVEL
    validation.executor_identity = TRUSTED_EXECUTOR_IDENTITY
    validation.runtime_authorization_source = "operator_evolution_runner_policy"
    validation.allow_real_provider_frozen_deployment = (
        provider in REAL_PROVIDERS and allowed is True
    )
    validation.explicit_runtime_risk_ack = (
        provider in REAL_PROVIDERS and allowed is True
    )
    validation.validation_status = "valid"
    validation.safe_to_execute = provider not in REAL_PROVIDERS or allowed is True
    validation.requires_human_risk_ack = (
        provider in REAL_PROVIDERS and allowed is not True
    )
    if validation.requires_human_risk_ack:
        validation.execution_status = "risk_ack_required"
        validation.failure_type = "risk_ack_required"
        validation.error_message = (
            "Real-provider candidate execution is blocked: timeout_only is not a "
            "capability sandbox and explicit risk acknowledgement is absent"
        )
    else:
        validation.execution_status = "success"
        validation.failure_type = "success"
        validation.error_message = ""


def mark_candidate_execution_blocked(validation: Any, reason: str) -> None:
    validation.safe_to_execute = False
    validation.execution_status = "execution_blocked"
    validation.failure_type = "execution_blocked"
    validation.error_message = reason


def candidate_is_benchmark_eligible(
    validation: Any,
    callable_obj: Any,
    allow_unsafe_candidate_execution: Any,
) -> bool:
    """Benchmark uses the same execution evidence as the smoke-test boundary."""
    return candidate_is_execution_eligible(
        validation,
        callable_obj,
        allow_unsafe_candidate_execution,
    )


def candidate_is_selection_eligible(row: Any) -> bool:
    """Require complete success and failure evidence before best selection."""
    return _artifact_failure_reason(row) is None


def candidate_is_freeze_eligible(row: Any) -> bool:
    """Require selection evidence plus a finite positive execution timeout."""
    if _artifact_failure_reason(row) is not None:
        return False
    try:
        parse_positive_finite_timeout(row.get("timeout_ms"))
    except (TypeError, ValueError):
        return False
    return True


def build_generated_artifact_metadata(
    *,
    claimed_source_provider: Any,
    round_id: Any,
    code_hash: Any,
) -> dict[str, Any]:
    """Build audit-only provenance metadata for a generated candidate.

    This metadata records an artifact claim.  It is deliberately not a trusted
    provider receipt and never grants deployment authority.
    """
    provider = (
        claimed_source_provider
        if isinstance(claimed_source_provider, str) and claimed_source_provider
        else "unknown"
    )
    try:
        normalized_round = int(round_id)
    except (TypeError, ValueError):
        normalized_round = 0
    generation_run_id = f"generation-run-round-{normalized_round:03d}"
    identity_hash = code_hash if isinstance(code_hash, str) and code_hash else "unknown"
    return {
        "artifact_type": GENERATED_ARTIFACT_TYPE,
        "source_provider": provider,
        "claimed_source_provider": provider,
        "provider_provenance": {
            "trust_level": "artifact_claim",
            "claimed_provider": provider,
            "authority": "artifact_metadata",
        },
        "provider_provenance_source": "artifact_metadata",
        "generation_run_id": generation_run_id,
        "artifact_identity": f"generated:{identity_hash}",
        "lineage": {
            "generation_run_id": generation_run_id,
            "parent_operator_ids": [],
        },
    }


def validate_registry_metadata(row: Any) -> tuple[bool, str, float | None]:
    """Validate all frozen deployment evidence and return a parsed timeout."""
    reason = _artifact_failure_reason(row)
    if reason is not None:
        return False, reason, None
    try:
        timeout_ms = parse_positive_finite_timeout(row.get("timeout_ms"))
    except (TypeError, ValueError):
        return False, "invalid_timeout_ms", None
    return True, "", timeout_ms


def validate_frozen_deployment_authorization(
    row: Any,
    *,
    allow_real_provider_frozen_deployment: Any,
    explicit_runtime_risk_ack: Any,
    allow_generated_frozen_deployment: Any = False,
    explicit_runtime_deployment_ack: Any = False,
    runtime_authorization_source: Any,
    effective_sandbox_level: Any,
    executor_identity: Any,
) -> tuple[bool, str, str]:
    """Authorize any generated frozen deployment using runtime evidence only.

    Provider labels and artifact safety/risk fields are audit-only.  Until a
    trusted provider receipt exists, every generated artifact requires explicit
    current-runtime deployment authorization regardless of its claimed provider.
    """
    if not isinstance(row, Mapping):
        return (
            False,
            "generated_artifact_deployment_blocked",
            "generated_artifact_deployment_blocked: registry row is not an object",
        )

    try:
        legacy_allow = parse_strict_bool(
            allow_real_provider_frozen_deployment,
            field_name="allow_real_provider_frozen_deployment",
        )
        legacy_ack = parse_strict_bool(
            explicit_runtime_risk_ack,
            field_name="explicit_runtime_risk_ack",
        )
        generated_allow = parse_strict_bool(
            allow_generated_frozen_deployment,
            field_name="allow_generated_frozen_deployment",
        )
        deployment_ack = parse_strict_bool(
            explicit_runtime_deployment_ack,
            field_name="explicit_runtime_deployment_ack",
        )
    except TypeError as exc:
        return (
            False,
            "generated_artifact_deployment_blocked",
            "missing_runtime_authorization: "
            f"generated_artifact_deployment_blocked: {exc}",
        )

    authorized = (
        generated_allow is True and deployment_ack is True
    ) or (legacy_allow is True and legacy_ack is True)
    if (
        not authorized
        or runtime_authorization_source not in ALLOWED_RUNTIME_AUTHORIZATION_SOURCES
    ):
        return (
            False,
            "missing_runtime_deployment_authorization",
            "missing_runtime_authorization: missing_runtime_deployment_authorization; "
            "generated frozen deployment "
            "requires current runtime allow, explicit deployment ack, and authorization source",
        )
    if (
        effective_sandbox_level != TRUSTED_EXECUTOR_SANDBOX_LEVEL
        or executor_identity != TRUSTED_EXECUTOR_IDENTITY
    ):
        return (
            False,
            "generated_artifact_deployment_blocked",
            "generated_artifact_deployment_blocked: runtime executor authority mismatch",
        )
    return True, "success", ""


def parse_positive_finite_timeout(value: Any) -> float:
    """Parse a timeout represented by a finite positive int or float."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("timeout_ms must be a finite positive number")
    timeout_ms = float(value)
    if not math.isfinite(timeout_ms) or timeout_ms <= 0.0:
        raise ValueError("timeout_ms must be a finite positive number")
    return timeout_ms


def _artifact_failure_reason(row: Any) -> str | None:
    if not isinstance(row, Mapping):
        return "candidate metadata must be an object"

    required_fields = (
        "artifact_type",
        "validation_status",
        "execution_status",
        "failure_type",
        "safe_to_execute",
        "requires_human_risk_ack",
        "sandbox_level",
        "effective_sandbox_level",
        "executor_identity",
        "source_provider",
        "claimed_source_provider",
        "provider_provenance",
        "generation_run_id",
        "artifact_identity",
        "lineage",
        "code_hash",
        "fallback_used",
        "timeout_ms",
        *REQUIRED_FAILURE_RATE_FIELDS,
    )
    for field_name in required_fields:
        if field_name not in row:
            return f"missing required metadata: {field_name}"

    if row["artifact_type"] != GENERATED_ARTIFACT_TYPE:
        return "invalid artifact_type"

    if row["validation_status"] != "valid":
        return "validation_status is not valid"
    if row["execution_status"] != "success":
        return "execution_status is not success"
    if row["failure_type"] != "success":
        return "failure_type is not success"
    if row["safe_to_execute"] is not True:
        return "safe_to_execute is not true"
    if row["requires_human_risk_ack"] is not False:
        return "requires_human_risk_ack is not false"
    if row["fallback_used"] is not False:
        return "fallback_used is not false"

    sandbox_level = row["sandbox_level"]
    claimed_sandbox_level = row.get("claimed_sandbox_level", sandbox_level)
    if sandbox_level not in ALLOWED_SANDBOX_LEVELS:
        return "invalid sandbox_level"
    if claimed_sandbox_level not in ALLOWED_SANDBOX_LEVELS:
        return "invalid claimed_sandbox_level"
    if claimed_sandbox_level != sandbox_level:
        return "untrusted_sandbox_claim: sandbox claim fields disagree"
    if claimed_sandbox_level != TRUSTED_EXECUTOR_SANDBOX_LEVEL:
        return "untrusted_sandbox_claim: claimed sandbox does not match runtime"
    if row["effective_sandbox_level"] != TRUSTED_EXECUTOR_SANDBOX_LEVEL:
        return "untrusted_sandbox_claim: invalid effective sandbox level"
    if row["executor_identity"] != TRUSTED_EXECUTOR_IDENTITY:
        return "untrusted_sandbox_claim: executor identity mismatch"
    provider = row["source_provider"]
    if not isinstance(provider, str) or not provider:
        return "invalid source_provider"
    claimed_provider = row["claimed_source_provider"]
    if not isinstance(claimed_provider, str) or not claimed_provider:
        return "invalid claimed_source_provider"
    if claimed_provider != provider:
        return "provider provenance mismatch: source provider claims disagree"

    provenance = row["provider_provenance"]
    if not isinstance(provenance, Mapping) or not provenance:
        return "invalid provider provenance"
    if provenance.get("trust_level") != "artifact_claim":
        return "invalid provider provenance trust level"
    if provenance.get("claimed_provider") != claimed_provider:
        return "provider provenance mismatch"
    if provenance.get("authority") != "artifact_metadata":
        return "invalid provider provenance authority"
    trusted_provenance = row.get("trusted_provider_provenance")
    if trusted_provenance not in (None, "unknown"):
        return "untrusted provider provenance elevation"

    generation_run_id = row["generation_run_id"]
    artifact_identity = row["artifact_identity"]
    lineage = row["lineage"]
    if not isinstance(generation_run_id, str) or not generation_run_id:
        return "invalid generation_run_id"
    if not isinstance(artifact_identity, str) or not artifact_identity:
        return "invalid artifact_identity"
    if not isinstance(lineage, Mapping) or not lineage:
        return "invalid lineage"
    if lineage.get("generation_run_id") != generation_run_id:
        return "lineage generation_run_id mismatch"
    if not isinstance(lineage.get("parent_operator_ids"), list):
        return "invalid lineage parent_operator_ids"
    code_hash = row["code_hash"]
    if not isinstance(code_hash, str) or not code_hash:
        return "invalid code_hash"

    for field_name in REQUIRED_FAILURE_RATE_FIELDS:
        if not _is_zero_rate(row[field_name]):
            return f"{field_name} is not zero"
    try:
        parse_positive_finite_timeout(row["timeout_ms"])
    except (TypeError, ValueError):
        return "invalid_timeout_ms"
    return None


def _is_zero_rate(value: Any) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
        and float(value) == 0.0
    )
