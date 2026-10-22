"""Controlled path and duplicate validation for non-formal pilot inputs.

The validator examines only paths explicitly supplied in a manifest.  It does
not discover files, schedule work, invoke providers, or authorize execution.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path, PureWindowsPath
import re
import stat
from typing import Any

from mrta_rect_coverage.experiments.pilot_integrity import (
    compute_object_hash,
    validate_sha256_hex,
)


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GLOB_CHARS = frozenset("*?[]")
_FORMAL_MARKERS = (
    "final_test",
    "formal_train",
    "formal_dev",
    "formal_final_test",
)
_GENERATION_IDENTITY_FIELDS = (
    "generation_rule_version",
    "generation_seed",
    "robots",
    "tasks",
    "size_stratum",
    "distribution_stratum",
    "sweep_width",
    "sweep_speed",
    "travel_speed",
    "turning_time",
)
_FORMAL_SCOPE_VALUES = frozenset(
    {"formal_train", "formal_dev", "formal_final_test"}
)
_ACTIVE_STABLE_READ: ContextVar[tuple[str, dict[str, Any]] | None] = ContextVar(
    "pilot_path_validator_active_stable_read",
    default=None,
)
_PATH_VALIDATION_SCHEMA_VERSION = "pilot-path-validation-v1"
_APPROVED_ROOT_FINGERPRINT_SCHEMA = "pilot-approved-root-fingerprint-v1"
_DUPLICATE_SUMMARY_FIELDS = (
    "instance_id_duplicates",
    "file_hash_duplicates",
    "canonical_path_duplicates",
    "file_identity_duplicates",
    "generation_identity_duplicates",
)


@dataclass(frozen=True)
class PilotPathValidationResult:
    """Inert outcome from the controlled path/duplicate validator."""

    valid: bool
    rejection_reasons: tuple[str, ...]
    result_scope: str = "path_duplicate_validation"
    file_identity_check: str = "not_reached"
    execution_authorized: bool = False
    gate_p2_closed: bool = False


@dataclass(frozen=True)
class _PathValidationEvaluation:
    result: PilotPathValidationResult
    canonical_root: Path | None
    duplicate_validation_summary: dict[str, int]
    no_glob_confirmed: bool


class _Issues:
    def __init__(self) -> None:
        self._values: list[str] = []

    def add(self, reason: str) -> None:
        if reason not in self._values:
            self._values.append(reason)

    def result(self, *, file_identity_check: str) -> PilotPathValidationResult:
        reasons = tuple(self._values)
        return PilotPathValidationResult(
            valid=not reasons,
            rejection_reasons=reasons,
            file_identity_check=file_identity_check,
        )


def _normal_marker_text(value: str) -> str:
    return value.replace("\\", "/").lower().replace("-", "_")


def _contains_formal_marker(value: Any) -> bool:
    if type(value) is not str:
        return False
    normalized = _normal_marker_text(value)
    return any(marker in normalized for marker in _FORMAL_MARKERS)


def _check_pilot_only_metadata(
    value: Any,
    issues: _Issues,
    *,
    location: str = "manifest",
) -> None:
    """Reject explicit formal/promotion markers anywhere in supplied data."""

    if type(value) is dict:
        for key, child in value.items():
            key_text = str(key)
            child_location = f"{location}.{key_text}"
            normalized_key = _normal_marker_text(key_text)
            if normalized_key == "artifact_promotion_allowed" and child is not False:
                issues.add(f"artifact_promotion_forbidden[{child_location}]")
            if normalized_key == "matrix_scope" and child == "formal":
                issues.add(f"formal_matrix_scope_forbidden[{child_location}]")
            if normalized_key in {"split", "manifest_scope"} and child in _FORMAL_SCOPE_VALUES:
                issues.add(f"formal_scope_or_split_forbidden[{child_location}]")
            if _contains_formal_marker(child):
                issues.add(
                    f"formal_or_final_test_marker_forbidden[{child_location}]"
                )
            _check_pilot_only_metadata(child, issues, location=child_location)
        return
    if type(value) is list:
        for index, child in enumerate(value):
            _check_pilot_only_metadata(
                child,
                issues,
                location=f"{location}[{index}]",
            )


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _is_link_or_reparse(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except OSError:
        return False
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(reparse_flag and attributes & reparse_flag)


def _has_link_component(path: Path, root: Path) -> bool:
    current = path
    while True:
        if _is_link_or_reparse(current):
            return True
        if current == root:
            return False
        parent = current.parent
        if parent == current:
            return False
        current = parent


def _lexical_candidate(path_value: str, approved_root: Path) -> tuple[Path | None, str | None]:
    if "\x00" in path_value:
        return None, "forbidden_path_syntax"
    normalized = path_value.replace("\\", "/")
    if "://" in normalized:
        return None, "uri_scheme_path_syntax_forbidden"
    if normalized.startswith("//"):
        return None, "unc_network_path_syntax_forbidden"
    if any(part == ".." for part in normalized.split("/")):
        return None, "parent_traversal_forbidden"
    if any(char in path_value for char in _GLOB_CHARS):
        return None, "glob_wildcard_path_syntax_forbidden"

    supplied = Path(path_value)
    windows_path = PureWindowsPath(path_value)
    if windows_path.drive and not supplied.is_absolute():
        return None, "drive_like_path_syntax_forbidden"
    candidate = supplied if supplied.is_absolute() else approved_root / supplied
    try:
        lexical_absolute = Path(os.path.abspath(candidate))
    except (OSError, ValueError):
        return None, "forbidden_path_syntax"
    if not _is_relative_to(lexical_absolute, approved_root):
        return None, "path_outside_approved_root"
    return lexical_absolute, None


def _file_identity(path: Path) -> tuple[int, int] | None:
    try:
        info = path.stat()
        device = getattr(info, "st_dev", None)
        inode = getattr(info, "st_ino", None)
    except OSError:
        return None
    if type(device) is not int or type(inode) is not int or inode == 0:
        return None
    return device, inode


def _identity_from_stat(info: os.stat_result) -> tuple[int, int] | None:
    device = getattr(info, "st_dev", None)
    inode = getattr(info, "st_ino", None)
    if type(device) is not int or type(inode) is not int or inode == 0:
        return None
    return device, inode


def _select_snapshot_change_timestamp(
    info: os.stat_result,
    *,
    platform_name: str | None = None,
) -> int | None:
    """Select the platform's stable-snapshot metadata-change timestamp."""

    platform_name = os.name if platform_name is None else platform_name
    ctime_ns = getattr(info, "st_ctime_ns", None)
    if platform_name != "nt":
        return ctime_ns if type(ctime_ns) is int else None

    birthtime_ns = getattr(info, "st_birthtime_ns", None)
    if type(birthtime_ns) is int:
        return birthtime_ns
    return ctime_ns if type(ctime_ns) is int else None


def _snapshot_from_stat(
    info: os.stat_result,
) -> tuple[int, int, int, int, int] | None:
    identity = _identity_from_stat(info)
    size = getattr(info, "st_size", None)
    mtime_ns = getattr(info, "st_mtime_ns", None)
    identity_time_ns = _select_snapshot_change_timestamp(info)
    if (
        identity is None
        or type(size) is not int
        or type(mtime_ns) is not int
        or type(identity_time_ns) is not int
    ):
        return None
    return identity[0], identity[1], size, mtime_ns, identity_time_ns


def _file_snapshot(path: Path) -> tuple[int, int, int, int, int] | None:
    try:
        return _snapshot_from_stat(path.stat())
    except OSError:
        return None


def _hash_explicit_file(path: Path) -> str:
    digest = hashlib.sha256()
    active = _ACTIVE_STABLE_READ.get()
    canonical = os.path.normcase(str(path))
    if active is not None and active[0] == canonical:
        state = active[1]
        stream = state["stream"]
        try:
            stream.seek(0)
            for block in iter(lambda: stream.read(64 * 1024), b""):
                digest.update(block)
        finally:
            try:
                state["snapshot_after"] = _snapshot_from_stat(
                    os.fstat(stream.fileno())
                )
            finally:
                # Close immediately after hashing.  The bytes were read from
                # the verified handle; releasing it here also permits the
                # caller's post-read pathname identity check on Windows.
                stream.close()
        return digest.hexdigest()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(64 * 1024), b""):
            digest.update(block)
        return digest.hexdigest()


def _evaluate_pilot_paths_and_duplicates(
    manifest_obj: Any,
    *,
    approved_root: Path,
) -> _PathValidationEvaluation:
    """Validate explicit pilot file inputs inside ``approved_root``.

    The function is deliberately fail-closed and non-recursive with respect to
    directory contents: only manifest records are inspected.
    """

    issues = _Issues()
    identity_supported = True
    identity_reached = False
    canonical_root: Path | None = None
    duplicate_counts = {field: 0 for field in _DUPLICATE_SUMMARY_FIELDS}
    no_glob_confirmed = True

    def evaluation(*, file_identity_check: str) -> _PathValidationEvaluation:
        return _PathValidationEvaluation(
            result=issues.result(file_identity_check=file_identity_check),
            canonical_root=canonical_root,
            duplicate_validation_summary=dict(duplicate_counts),
            no_glob_confirmed=no_glob_confirmed,
        )

    if type(manifest_obj) is not dict:
        issues.add("invalid_manifest_object")
        return evaluation(file_identity_check="not_reached")

    if manifest_obj.get("manifest_scope") != "pilot_nonformal":
        issues.add("formal_manifest_scope_forbidden")
    if manifest_obj.get("matrix_scope") != "pilot":
        issues.add("formal_matrix_scope_forbidden")
    if manifest_obj.get("artifact_promotion_allowed") is not False:
        issues.add("artifact_promotion_missing_or_forbidden")
    _check_pilot_only_metadata(manifest_obj, issues)

    records = manifest_obj.get("instances")
    if type(records) is not list or not records:
        issues.add("empty_manifest_instance_records")
        return evaluation(file_identity_check="not_reached")

    try:
        root = Path(approved_root).resolve(strict=True)
    except (OSError, TypeError, ValueError):
        issues.add("invalid_approved_root")
        return evaluation(file_identity_check="not_reached")
    canonical_root = root
    if not root.is_dir():
        issues.add("invalid_approved_root_directory")
        return evaluation(file_identity_check="not_reached")
    if _is_link_or_reparse(Path(approved_root)):
        issues.add("approved_root_symlink_or_reparse_forbidden")

    instance_ids: set[Any] = set()
    canonical_paths: set[str] = set()
    declared_hashes: set[str] = set()
    file_identities: set[tuple[int, int]] = set()
    family_splits: dict[Any, Any] = {}
    generation_identities: set[tuple[Any, ...]] = set()

    for index, record in enumerate(records):
        if type(record) is not dict:
            issues.add(f"invalid_instance_record[{index}]")
            continue

        instance_id = record.get("instance_id")
        try:
            if instance_id in instance_ids:
                issues.add("duplicate_instance_id")
                duplicate_counts["instance_id_duplicates"] += 1
            else:
                instance_ids.add(instance_id)
        except TypeError:
            issues.add("invalid_instance_id")

        family_id = record.get("family_id")
        split = record.get("split")
        try:
            if family_id in family_splits and family_splits[family_id] != split:
                issues.add("family_split_conflict")
            else:
                family_splits[family_id] = split
        except TypeError:
            issues.add("invalid_family_id")

        generation_identity = tuple(
            record.get(field) for field in _GENERATION_IDENTITY_FIELDS
        )
        try:
            if generation_identity in generation_identities:
                issues.add("duplicate_generation_identity")
                duplicate_counts["generation_identity_duplicates"] += 1
            else:
                generation_identities.add(generation_identity)
        except TypeError:
            issues.add("invalid_generation_identity")

        if _contains_formal_marker(record.get("lockbox_status")):
            issues.add("final_test_lockbox_forbidden")

        if "file_path" not in record:
            issues.add("missing_file_path")
            continue
        path_value = record.get("file_path")
        if type(path_value) is not str:
            issues.add("invalid_file_path_type")
            continue
        if not path_value:
            issues.add("missing_file_path")
            continue
        if any(char in path_value for char in _GLOB_CHARS):
            no_glob_confirmed = False
        if _contains_formal_marker(path_value):
            issues.add("formal_or_final_test_path_marker_forbidden")

        if "file_hash" not in record:
            issues.add("missing_file_hash")
            continue
        declared_hash = record.get("file_hash")
        if type(declared_hash) is not str or _SHA256_RE.fullmatch(declared_hash) is None:
            issues.add("invalid_file_hash")
        else:
            if declared_hash in declared_hashes:
                issues.add("duplicate_file_hash")
                duplicate_counts["file_hash_duplicates"] += 1
            else:
                declared_hashes.add(declared_hash)

        candidate, path_error = _lexical_candidate(path_value, root)
        if path_error is not None:
            issues.add(path_error)
            continue
        assert candidate is not None

        if _has_link_component(candidate, root):
            issues.add("symlink_or_reparse_alias_forbidden")
            continue

        try:
            resolved = candidate.resolve(strict=True)
        except FileNotFoundError:
            issues.add("missing_file_path_target")
            continue
        except (OSError, RuntimeError, ValueError):
            issues.add("file_path_resolution_failed")
            continue
        if not _is_relative_to(resolved, root):
            issues.add("resolved_path_root_escape")
            continue
        if not resolved.is_file():
            issues.add("directory_file_path_forbidden")
            continue

        canonical = os.path.normcase(str(resolved))
        if canonical in canonical_paths:
            issues.add("duplicate_canonical_path")
            duplicate_counts["canonical_path_duplicates"] += 1
        else:
            canonical_paths.add(canonical)

        identity_reached = True
        pre_snapshot = _file_snapshot(resolved)
        identity = _file_identity(resolved)
        if identity is None or pre_snapshot is None:
            identity_supported = False
            continue

        # The public test seam above may expose a replacement immediately after
        # the pre-open identity check.  Recheck links before opening and bind all
        # reads to the opened handle rather than reopening the pathname.
        if _is_link_or_reparse(resolved):
            issues.add("path_toctou_detected_symlink_root_escape")
            continue

        actual_hash: str | None = None
        stable_identity: tuple[int, int] | None = None
        try:
            with resolved.open("rb") as stable_stream:
                handle_before = os.fstat(stable_stream.fileno())
                stable_identity = _identity_from_stat(handle_before)
                handle_snapshot_before = _snapshot_from_stat(handle_before)
                if (
                    stable_identity is None
                    or handle_snapshot_before is None
                    or stable_identity != identity
                    or handle_snapshot_before != pre_snapshot
                ):
                    issues.add(
                        "path_toctou_detected_file_identity_changed_"
                        "stable_handle_mismatch"
                    )
                    continue

                stable_state: dict[str, Any] = {"stream": stable_stream}
                token = _ACTIVE_STABLE_READ.set((canonical, stable_state))
                try:
                    actual_hash = _hash_explicit_file(resolved)
                finally:
                    _ACTIVE_STABLE_READ.reset(token)

                if stable_state.get("snapshot_after") != handle_snapshot_before:
                    issues.add(
                        "path_toctou_detected_file_identity_changed_"
                        "stable_handle_modified_during_read"
                    )
                    continue
        except OSError:
            issues.add("explicit_file_read_failed")
            continue

        if _is_link_or_reparse(resolved):
            issues.add("path_toctou_detected_post_read_symlink_root_escape")
            continue
        post_snapshot = _file_snapshot(resolved)
        if (
            stable_identity is None
            or post_snapshot is None
            or post_snapshot[:2] != stable_identity
            or post_snapshot != pre_snapshot
        ):
            issues.add(
                "path_toctou_detected_post_read_identity_file_identity_changed"
            )
            continue

        if stable_identity in file_identities:
            issues.add("duplicate_file_identity_hardlink")
            duplicate_counts["file_identity_duplicates"] += 1
        else:
            file_identities.add(stable_identity)

        if type(declared_hash) is str and _SHA256_RE.fullmatch(declared_hash):
            if actual_hash != declared_hash:
                issues.add("file_hash_mismatch")

    if not identity_reached:
        identity_status = "not_reached"
    elif identity_supported:
        identity_status = "supported_pass"
    else:
        identity_status = "unsupported_file_identity_check"
        issues.add("unsupported_file_identity_check")
    return evaluation(file_identity_check=identity_status)


def validate_pilot_paths_and_duplicates(
    manifest_obj: Any,
    *,
    approved_root: Path,
) -> PilotPathValidationResult:
    """Validate explicit pilot file inputs inside ``approved_root``."""

    return _evaluate_pilot_paths_and_duplicates(
        manifest_obj,
        approved_root=approved_root,
    ).result


def build_pilot_path_validation_evidence(
    manifest_obj: Any,
    *,
    approved_root: Path,
    manifest_object_hash: str,
) -> dict[str, Any]:
    """Build the exact versioned path-evidence envelope consumed by T5."""

    if not validate_sha256_hex(manifest_object_hash).valid:
        raise ValueError("manifest_object_hash must be lowercase SHA-256 hex")

    evaluation = _evaluate_pilot_paths_and_duplicates(
        manifest_obj,
        approved_root=approved_root,
    )
    if evaluation.canonical_root is None:
        raise ValueError(
            "path evidence requires an approved root reached by T4 validation"
        )

    canonical_root = os.path.normcase(str(evaluation.canonical_root))
    approved_root_fingerprint = compute_object_hash(
        {
            "schema": _APPROVED_ROOT_FINGERPRINT_SCHEMA,
            "canonical_approved_root": canonical_root,
        }
    )
    result = evaluation.result
    body: dict[str, Any] = {
        "path_validation_schema_version": _PATH_VALIDATION_SCHEMA_VERSION,
        "status": "valid" if result.valid else "rejected",
        "result_scope": result.result_scope,
        "manifest_object_hash": manifest_object_hash,
        "approved_root_fingerprint": approved_root_fingerprint,
        "duplicate_validation_summary": dict(
            evaluation.duplicate_validation_summary
        ),
        "file_identity_check": result.file_identity_check,
        "rejection_reasons": list(result.rejection_reasons),
        "no_glob_confirmed": evaluation.no_glob_confirmed,
        # This producer path consumes only caller-supplied explicit records.
        "no_directory_discovery_confirmed": True,
        "execution_authorized": result.execution_authorized,
        "gate_p2_closed": result.gate_p2_closed,
    }
    return {
        **body,
        "path_validation_result_id": compute_object_hash(body),
    }


__all__ = [
    "PilotPathValidationResult",
    "build_pilot_path_validation_evidence",
    "validate_pilot_paths_and_duplicates",
]
