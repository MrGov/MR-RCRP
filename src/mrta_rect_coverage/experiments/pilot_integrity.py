"""Pure in-memory integrity checks for non-formal pilot artifacts.

Every public verifier consumes already-provided Python objects or bytes.  This
module deliberately has no path resolution, file access, runner scheduling,
provider loading, or candidate execution capability.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re
from typing import Any


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SIGNATURE_FIELDS = {"signature", "signatures"}
CANONICALIZATION_ALGORITHM = "RFC8785-JCS"
CANONICALIZATION_VERSION = "jcs-v1-safe-int-domain"
_JCS_SAFE_INTEGER_MAX = (1 << 53) - 1
_FORMAL_SCOPE_MARKERS = ("formal_train", "formal_dev", "formal_final_test")
_SCOPE_SEMANTIC_TOKENS = ("scope", "split", "manifest", "lockbox")
_FORBIDDEN_PILOT_HASH_FIELDS = {
    "full_formal_family_matrix_hash",
    "formal_family_matrix_hash",
    "formal_split_assignment_rule_hash",
    "final_test_manifest_hash",
    "final_test_hash_marker",
    "pilot_family_matrix_hash",
    "pilot_split_assignment_rule_hash",
}


@dataclass(frozen=True)
class IntegrityValidationResult:
    """Fail-closed outcome from an integrity verification operation."""

    valid: bool
    rejection_reasons: tuple[str, ...]


class _Issues:
    def __init__(self) -> None:
        self._reasons: list[str] = []

    def add(self, reason: str) -> None:
        if reason not in self._reasons:
            self._reasons.append(reason)

    def result(self) -> IntegrityValidationResult:
        return IntegrityValidationResult(not self._reasons, tuple(self._reasons))


def _validate_json_string(value: str) -> None:
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise ValueError("non_canonical_json: lone surrogate is not valid UTF-8")


def _validate_json_value(value: Any) -> None:
    if value is None or type(value) is bool:
        return
    if type(value) is int:
        if not -_JCS_SAFE_INTEGER_MAX <= value <= _JCS_SAFE_INTEGER_MAX:
            raise ValueError(
                "canonicalization_integer_domain: Python int is outside the "
                "JCS safe integer domain"
            )
        return
    if type(value) is str:
        _validate_json_string(value)
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("non_canonical_json: number must be finite")
        return
    if type(value) is list:
        for item in value:
            _validate_json_value(item)
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise TypeError("non_canonical_json: object keys must be strings")
            _validate_json_string(key)
            _validate_json_value(item)
        return
    raise TypeError("non_canonical_json: value is outside the JSON data model")


def _serialize_json_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def _expand_scientific_mantissa(mantissa: str, exponent: int) -> str:
    sign = ""
    if mantissa.startswith("-"):
        sign, mantissa = "-", mantissa[1:]
    integer, separator, fraction = mantissa.partition(".")
    digits = integer + (fraction if separator else "")
    decimal_position = len(integer) + exponent
    if decimal_position <= 0:
        expanded = "0." + ("0" * -decimal_position) + digits
    elif decimal_position >= len(digits):
        expanded = digits + ("0" * (decimal_position - len(digits)))
    else:
        expanded = digits[:decimal_position] + "." + digits[decimal_position:]
    return sign + expanded


def _serialize_jcs_number(value: int | float) -> str:
    if type(value) is int:
        return str(value)
    if not math.isfinite(value):
        raise ValueError("non_canonical_json: number must be finite")
    if value == 0:
        return "0"

    representation = repr(value).lower()
    if "e" not in representation:
        if representation.endswith(".0"):
            return representation[:-2]
        return representation

    mantissa, exponent_text = representation.split("e", 1)
    exponent = int(exponent_text)
    if -6 <= exponent < 21:
        return _expand_scientific_mantissa(mantissa, exponent)
    normalized_mantissa = mantissa[:-2] if mantissa.endswith(".0") else mantissa
    exponent_suffix = f"+{exponent}" if exponent >= 0 else str(exponent)
    return normalized_mantissa + "e" + exponent_suffix


def _utf16_sort_key(value: str) -> bytes:
    return value.encode("utf-16-be")


def _serialize_jcs(value: Any) -> str:
    if value is None:
        return "null"
    if type(value) is bool:
        return "true" if value else "false"
    if type(value) in {int, float}:
        return _serialize_jcs_number(value)
    if type(value) is str:
        return _serialize_json_string(value)
    if type(value) is list:
        return "[" + ",".join(_serialize_jcs(item) for item in value) + "]"
    if type(value) is dict:
        members = (
            _serialize_json_string(key) + ":" + _serialize_jcs(value[key])
            for key in sorted(value, key=_utf16_sort_key)
        )
        return "{" + ",".join(members) + "}"
    raise TypeError("non_canonical_json: value is outside the JSON data model")


def canonical_json_bytes(obj: Any) -> bytes:
    """Serialize a strict JSON-domain object as RFC 8785/JCS UTF-8 bytes."""

    _validate_json_value(obj)
    return _serialize_jcs(obj).encode("utf-8")


def sha256_hex_bytes(data: bytes) -> str:
    """Return the lowercase SHA-256 digest of explicitly supplied bytes."""

    if type(data) is not bytes:
        raise TypeError("invalid_bytes: SHA-256 input must be bytes")
    return hashlib.sha256(data).hexdigest()


def compute_object_hash(obj: Any) -> str:
    """Hash an explicitly supplied strict JSON-domain object."""

    return sha256_hex_bytes(canonical_json_bytes(obj))


def validate_sha256_hex(value: Any) -> IntegrityValidationResult:
    issues = _Issues()
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        issues.add("invalid_sha256_hex")
    return issues.result()


def _contains_final_test_marker(value: Any) -> bool:
    if type(value) is str:
        normalized = value.lower().replace("-", "_")
        return "final_test" in normalized
    if type(value) is list:
        return any(_contains_final_test_marker(item) for item in value)
    if type(value) is dict:
        return any(
            _contains_final_test_marker(key)
            or _contains_final_test_marker(item)
            for key, item in value.items()
        )
    return False


def _contains_formal_scope_marker(
    value: Any, *, semantic_context: bool = False
) -> bool:
    if type(value) is str:
        normalized = value.lower().replace("-", "_")
        if any(marker in normalized for marker in _FORMAL_SCOPE_MARKERS):
            return True
        return semantic_context and normalized == "formal"
    if type(value) is list:
        return any(
            _contains_formal_scope_marker(
                item, semantic_context=semantic_context
            )
            for item in value
        )
    if type(value) is dict:
        for key, item in value.items():
            normalized_key = key.lower().replace("-", "_")
            field_is_semantic = semantic_context or any(
                token in normalized_key for token in _SCOPE_SEMANTIC_TOKENS
            )
            if _contains_formal_scope_marker(
                key, semantic_context=field_is_semantic
            ) or _contains_formal_scope_marker(
                item, semantic_context=field_is_semantic
            ):
                return True
    return False


def verify_pilot_scoped_hash_binding(
    manifest: Any,
    family_matrix: Any,
    split_rule: Any,
) -> IntegrityValidationResult:
    """Verify pilot-only scope and matrix/rule hashes from supplied objects."""

    issues = _Issues()
    if type(manifest) is not dict:
        issues.add("invalid_manifest")
        return issues.result()
    if type(family_matrix) is not dict or type(split_rule) is not dict:
        issues.add("invalid_scoped_artifact")
        return issues.result()

    try:
        family_hash = compute_object_hash(family_matrix)
        split_hash = compute_object_hash(split_rule)
    except (TypeError, ValueError):
        issues.add("non_canonical_json")
        return issues.result()

    if manifest.get("manifest_scope") != "pilot_nonformal":
        issues.add("forbidden_scope")
    if manifest.get("matrix_scope") != "pilot":
        issues.add("forbidden_scope")
    if family_matrix.get("matrix_scope") != "pilot":
        issues.add("forbidden_scope")
    if split_rule.get("matrix_scope") != "pilot":
        issues.add("forbidden_scope")
    if manifest.get("artifact_promotion_allowed") is not False:
        issues.add("artifact_promotion_forbidden")
    if manifest.get("pilot_source_reference") is not None:
        issues.add("artifact_promotion_forbidden")
    if any(field in manifest for field in _FORBIDDEN_PILOT_HASH_FIELDS):
        issues.add("formal_hash_field_forbidden")
    if any(
        _contains_formal_scope_marker(scoped_object)
        for scoped_object in (manifest, family_matrix, split_rule)
    ):
        issues.add("formal_scope_forbidden")
    if manifest.get("family_matrix_hash") != family_hash:
        issues.add("family_matrix_hash_mismatch")
    if manifest.get("split_assignment_rule_hash") != split_hash:
        issues.add("split_assignment_rule_hash_mismatch")

    return issues.result()


def _receipt_body(receipt: Any, id_field: str) -> dict[str, Any]:
    if type(receipt) is not dict:
        raise TypeError("invalid_receipt: receipt must be an object")
    return {
        key: value
        for key, value in receipt.items()
        if key != id_field and key not in _SIGNATURE_FIELDS
    }


def compute_validation_receipt_id(receipt: Any) -> str:
    return compute_object_hash(_receipt_body(receipt, "validation_receipt_id"))


def compute_runner_receipt_id(receipt: Any) -> str:
    return compute_object_hash(_receipt_body(receipt, "runner_receipt_id"))


def verify_manifest_receipt_binding(
    manifest: Any,
    validator_receipt: Any,
) -> IntegrityValidationResult:
    """Bind a supplied manifest object to a non-self-referential receipt ID."""

    issues = _Issues()
    if type(manifest) is not dict or type(validator_receipt) is not dict:
        issues.add("invalid_receipt_binding")
        return issues.result()

    manifest_hash = validator_receipt.get("manifest_hash")
    if type(manifest_hash) is not str:
        issues.add("manifest_hash_missing")
    elif _SHA256_RE.fullmatch(manifest_hash) is None:
        issues.add("manifest_hash_invalid")
    else:
        try:
            if manifest_hash != compute_object_hash(manifest):
                issues.add("manifest_hash_mismatch")
        except (TypeError, ValueError):
            issues.add("non_canonical_json")

    receipt_id = validator_receipt.get("validation_receipt_id")
    if type(receipt_id) is not str or _SHA256_RE.fullmatch(receipt_id) is None:
        issues.add("validation_receipt_id_invalid")
    else:
        try:
            if receipt_id != compute_validation_receipt_id(validator_receipt):
                issues.add("validation_receipt_hash_mismatch")
        except (TypeError, ValueError):
            issues.add("non_canonical_json")

    return issues.result()


def verify_runner_receipt_id(runner_receipt: Any) -> IntegrityValidationResult:
    issues = _Issues()
    if type(runner_receipt) is not dict:
        issues.add("invalid_runner_receipt")
        return issues.result()
    receipt_id = runner_receipt.get("runner_receipt_id")
    if type(receipt_id) is not str or _SHA256_RE.fullmatch(receipt_id) is None:
        issues.add("runner_receipt_id_invalid")
        return issues.result()
    try:
        if receipt_id != compute_runner_receipt_id(runner_receipt):
            issues.add("runner_receipt_hash_mismatch")
    except (TypeError, ValueError):
        issues.add("non_canonical_json")
    return issues.result()


def verify_runner_receipt_binding(
    validator_receipt: Any,
    runner_receipt: Any,
) -> IntegrityValidationResult:
    """Verify runner ID plus its bindings to a supplied validator receipt."""

    issues = _Issues()
    if type(validator_receipt) is not dict or type(runner_receipt) is not dict:
        issues.add("invalid_receipt_binding")
        return issues.result()

    runner_id_result = verify_runner_receipt_id(runner_receipt)
    for reason in runner_id_result.rejection_reasons:
        issues.add(reason)

    validator_id = validator_receipt.get("validation_receipt_id")
    try:
        expected_validator_id = compute_validation_receipt_id(validator_receipt)
    except (TypeError, ValueError):
        expected_validator_id = None
        issues.add("non_canonical_json")
    if (
        type(validator_id) is not str
        or _SHA256_RE.fullmatch(validator_id) is None
        or validator_id != expected_validator_id
    ):
        issues.add("validation_receipt_hash_mismatch")

    manifest_only = runner_receipt.get("manifest_only_evidence")
    if type(manifest_only) is not dict:
        issues.add("manifest_only_evidence_missing")
        return issues.result()

    runner_validator_id = runner_receipt.get("validation_receipt_id")
    evidence_validator_id = manifest_only.get("validation_receipt_id")
    validator_ids = (
        validator_id,
        runner_validator_id,
        evidence_validator_id,
    )
    ids_are_valid = all(
        type(value) is str and _SHA256_RE.fullmatch(value) is not None
        for value in validator_ids
    )
    if not ids_are_valid:
        issues.add("validation_receipt_binding_invalid")
    elif runner_validator_id != validator_id or evidence_validator_id != validator_id:
        issues.add("validation_receipt_binding_mismatch")

    validator_manifest_hash = validator_receipt.get("manifest_hash")
    runner_manifest_hash = runner_receipt.get("manifest_hash")
    evidence_manifest_hash = manifest_only.get("manifest_hash")
    manifest_hashes = (
        validator_manifest_hash,
        runner_manifest_hash,
        evidence_manifest_hash,
    )
    hashes_are_valid = all(
        type(value) is str and _SHA256_RE.fullmatch(value) is not None
        for value in manifest_hashes
    )
    if not hashes_are_valid:
        issues.add("manifest_hash_invalid")
    elif (
        runner_manifest_hash != validator_manifest_hash
        or evidence_manifest_hash != validator_manifest_hash
    ):
        issues.add("manifest_hash_mismatch")

    return issues.result()


def verify_explicit_content_binding(
    record: Any,
    *,
    explicit_bytes: bytes | None = None,
    explicit_object: Any = None,
) -> IntegrityValidationResult:
    """Verify supplied content without interpreting or reading ``file_path``."""

    issues = _Issues()
    if type(record) is not dict:
        issues.add("invalid_content_record")
        return issues.result()

    file_path = record.get("file_path")
    if _contains_final_test_marker(file_path):
        issues.add("final_test_scope_forbidden")
        return issues.result()
    if explicit_bytes is not None and explicit_object is not None:
        issues.add("ambiguous_explicit_content")
        return issues.result()
    if explicit_bytes is None and explicit_object is None:
        issues.add("implicit_file_access_forbidden")
        return issues.result()

    try:
        if explicit_bytes is not None:
            actual_hash = sha256_hex_bytes(explicit_bytes)
        else:
            actual_hash = compute_object_hash(explicit_object)
    except (TypeError, ValueError):
        issues.add("non_canonical_json")
        return issues.result()

    expected_hash = record.get("file_hash")
    if type(expected_hash) is not str or _SHA256_RE.fullmatch(expected_hash) is None:
        issues.add("invalid_sha256_hex")
    elif expected_hash != actual_hash:
        issues.add("file_hash_mismatch")
    return issues.result()


__all__ = [
    "CANONICALIZATION_ALGORITHM",
    "CANONICALIZATION_VERSION",
    "IntegrityValidationResult",
    "canonical_json_bytes",
    "compute_object_hash",
    "compute_runner_receipt_id",
    "compute_validation_receipt_id",
    "sha256_hex_bytes",
    "validate_sha256_hex",
    "verify_explicit_content_binding",
    "verify_manifest_receipt_binding",
    "verify_pilot_scoped_hash_binding",
    "verify_runner_receipt_binding",
    "verify_runner_receipt_id",
]
