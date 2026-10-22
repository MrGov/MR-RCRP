from __future__ import annotations

import glob
import hashlib
import importlib
import os
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


PATH_VALIDATOR_MODULE = "mrta_rect_coverage.experiments.pilot_path_validator"
_MISSING = object()


def _validator() -> ModuleType:
    try:
        return importlib.import_module(PATH_VALIDATOR_MODULE)
    except ModuleNotFoundError as exc:
        if exc.name == PATH_VALIDATOR_MODULE:
            pytest.fail(
                "Phase 6B-T4 RED: controlled pilot path/duplicate "
                "validator is not implemented"
            )
        raise


def _write(root: Path, relative_path: str, content: bytes) -> Path:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _record(
    file_path: Any,
    *,
    file_hash: Any = "a" * 64,
    instance_id: str = "pilot-instance-001",
    family_id: str = "pilot-family-001",
    split: str = "train",
    generation_seed: int = 11,
    generation_rule_version: str = "pilot-generator-v1",
    replicate_id: int = 0,
    lockbox_status: str = "not_applicable",
) -> dict[str, Any]:
    return {
        "instance_id": instance_id,
        "family_id": family_id,
        "split": split,
        "file_path": file_path,
        "file_hash": file_hash,
        "generation_rule_version": generation_rule_version,
        "generation_seed": generation_seed,
        "replicate_id": replicate_id,
        "robots": 2,
        "tasks": 6,
        "size_stratum": "small",
        "distribution_stratum": "D1",
        "sweep_width": 1.0,
        "sweep_speed": 1.0,
        "travel_speed": 2.0,
        "turning_time": 0.5,
        "lockbox_status": lockbox_status,
    }


def _manifest(
    records: list[dict[str, Any]],
    *,
    manifest_scope: str = "pilot_nonformal",
    matrix_scope: str = "pilot",
) -> dict[str, Any]:
    return {
        "manifest_scope": manifest_scope,
        "matrix_scope": matrix_scope,
        "artifact_promotion_allowed": False,
        "instances": records,
    }


def _result_field(result: Any, name: str, default: Any = _MISSING) -> Any:
    if isinstance(result, dict):
        if default is _MISSING:
            return result[name]
        return result.get(name, default)
    if default is _MISSING:
        return getattr(result, name)
    return getattr(result, name, default)


def _reasons(result: Any) -> tuple[str, ...]:
    reasons = _result_field(result, "rejection_reasons", ())
    return tuple(str(reason) for reason in reasons)


def _assert_valid(result: Any) -> None:
    assert _result_field(result, "valid") is True
    assert _reasons(result) == ()
    assert _result_field(result, "execution_authorized", False) is False
    assert _result_field(result, "gate_p2_closed", False) is False


def _assert_rejected(result: Any, *reason_tokens: str) -> None:
    assert _result_field(result, "valid") is False
    reasons = _reasons(result)
    assert reasons
    if reason_tokens:
        joined = " ".join(reasons).lower()
        assert any(token.lower() in joined for token in reason_tokens), reasons
    assert _result_field(result, "execution_authorized", False) is False
    assert _result_field(result, "gate_p2_closed", False) is False


def _validate(manifest: dict[str, Any], approved_root: Path):
    return _validator().validate_pilot_paths_and_duplicates(
        manifest,
        approved_root=approved_root,
    )


def _single_valid_manifest(root: Path) -> dict[str, Any]:
    content = b"synthetic pilot-only instance\n"
    _write(root, "pilot_train/R2_T6_0.txt", content)
    return _manifest(
        [
            _record(
                "pilot_train/R2_T6_0.txt",
                file_hash=_sha256_bytes(content),
            )
        ]
    )


# Approved-root confinement -------------------------------------------------


def test_regular_relative_file_inside_approved_root_is_valid(tmp_path: Path) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()

    result = _validate(_single_valid_manifest(root), root)

    _assert_valid(result)


def test_absolute_file_inside_approved_root_stays_confined(tmp_path: Path) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    content = b"absolute but confined\n"
    path = _write(root, "pilot_train/R2_T6_0.txt", content)
    manifest = _manifest(
        [_record(str(path.resolve()), file_hash=_sha256_bytes(content))]
    )

    result = _validate(manifest, root)

    _assert_valid(result)


@pytest.mark.parametrize(
    "path_value",
    [
        "../outside.txt",
        "nested/../../outside.txt",
        "..\\outside.txt",
        r"C:\temp\x.txt",
    ],
)
def test_parent_or_drive_like_path_is_rejected(
    tmp_path: Path,
    path_value: str,
) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"outside\n")
    manifest = _manifest(
        [_record(path_value, file_hash=_sha256_bytes(b"outside\n"))]
    )

    result = _validate(manifest, root)

    _assert_rejected(result, "traversal", "root", "path_syntax", "drive")


def test_absolute_path_outside_approved_root_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    content = b"outside absolute\n"
    outside.write_bytes(content)
    manifest = _manifest(
        [_record(str(outside.resolve()), file_hash=_sha256_bytes(content))]
    )

    result = _validate(manifest, root)

    _assert_rejected(result, "outside", "root_escape", "approved_root")


@pytest.mark.parametrize("path_value", ["", None, 7, False, [], {}])
def test_empty_null_or_non_string_path_is_rejected(
    tmp_path: Path,
    path_value: Any,
) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    manifest = _manifest([_record(path_value)])

    result = _validate(manifest, root)

    _assert_rejected(result, "file_path", "path_type", "missing_path")


# Symlink/reparse boundary -------------------------------------------------


def _make_symlink_or_skip(
    link: Path,
    target: Path,
    *,
    target_is_directory: bool = False,
) -> None:
    try:
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(target, target_is_directory=target_is_directory)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"symlink creation unsupported in isolated tmp_path: {exc}")


def test_symlink_inside_root_to_outside_file_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    content = b"outside symlink target\n"
    outside.write_bytes(content)
    link = root / "alias.txt"
    _make_symlink_or_skip(link, outside)
    manifest = _manifest(
        [_record("alias.txt", file_hash=_sha256_bytes(content))]
    )

    result = _validate(manifest, root)

    _assert_rejected(result, "symlink", "alias", "root_escape", "reparse")


def test_symlink_inside_root_to_inside_file_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    content = b"inside symlink target\n"
    target = _write(root, "target.txt", content)
    link = root / "alias.txt"
    _make_symlink_or_skip(link, target)
    manifest = _manifest(
        [_record("alias.txt", file_hash=_sha256_bytes(content))]
    )

    result = _validate(manifest, root)

    _assert_rejected(result, "symlink", "alias", "reparse")


def test_symlink_directory_traversal_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    outside_dir = tmp_path / "outside_dir"
    outside_dir.mkdir()
    content = b"outside through directory link\n"
    (outside_dir / "instance.txt").write_bytes(content)
    _make_symlink_or_skip(
        root / "linked_dir",
        outside_dir,
        target_is_directory=True,
    )
    manifest = _manifest(
        [
            _record(
                "linked_dir/instance.txt",
                file_hash=_sha256_bytes(content),
            )
        ]
    )

    result = _validate(manifest, root)

    _assert_rejected(result, "symlink", "alias", "root_escape", "reparse")


def test_dangling_symlink_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    link = root / "dangling.txt"
    _make_symlink_or_skip(link, root / "missing.txt")
    manifest = _manifest([_record("dangling.txt")])

    result = _validate(manifest, root)

    _assert_rejected(result, "symlink", "dangling", "missing", "reparse")


# Duplicate paths, content, and file identity ------------------------------


def _two_file_manifest(
    root: Path,
    *,
    content_a: bytes = b"pilot-a\n",
    content_b: bytes = b"pilot-b\n",
) -> dict[str, Any]:
    _write(root, "a.txt", content_a)
    _write(root, "b.txt", content_b)
    return _manifest(
        [
            _record(
                "a.txt",
                file_hash=_sha256_bytes(content_a),
                instance_id="pilot-instance-a",
                family_id="pilot-family-a",
                generation_seed=11,
            ),
            _record(
                "b.txt",
                file_hash=_sha256_bytes(content_b),
                instance_id="pilot-instance-b",
                family_id="pilot-family-b",
                generation_seed=12,
            ),
        ]
    )


def test_hardlink_alias_is_rejected_by_file_identity(tmp_path: Path) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    content = b"hardlink target\n"
    source = _write(root, "source.txt", content)
    alias = root / "alias.txt"
    try:
        os.link(source, alias)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"hardlink creation unsupported in isolated tmp_path: {exc}")
    manifest = _manifest(
        [
            _record(
                "source.txt",
                file_hash=_sha256_bytes(content),
                instance_id="pilot-instance-source",
                family_id="pilot-family-source",
                generation_seed=11,
            ),
            _record(
                "alias.txt",
                file_hash=_sha256_bytes(content),
                instance_id="pilot-instance-alias",
                family_id="pilot-family-alias",
                generation_seed=12,
            ),
        ]
    )

    result = _validate(manifest, root)

    _assert_rejected(result, "file_identity", "hardlink")


def test_same_file_hash_at_different_paths_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    content = b"identical exact bytes\n"
    manifest = _two_file_manifest(root, content_a=content, content_b=content)

    result = _validate(manifest, root)

    _assert_rejected(result, "duplicate_file_hash", "duplicate_content")


def test_same_lexical_path_with_different_instance_ids_is_rejected(
    tmp_path: Path,
) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    content = b"same lexical path\n"
    _write(root, "same.txt", content)
    digest = _sha256_bytes(content)
    manifest = _manifest(
        [
            _record(
                "same.txt",
                file_hash=digest,
                instance_id="pilot-instance-a",
                family_id="pilot-family-a",
                generation_seed=11,
            ),
            _record(
                "same.txt",
                file_hash=digest,
                instance_id="pilot-instance-b",
                family_id="pilot-family-b",
                generation_seed=12,
            ),
        ]
    )

    result = _validate(manifest, root)

    _assert_rejected(result, "duplicate_path", "canonical_path")


def test_same_canonical_path_with_different_lexical_forms_is_rejected(
    tmp_path: Path,
) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    content = b"canonical alias\n"
    _write(root, "same.txt", content)
    digest = _sha256_bytes(content)
    manifest = _manifest(
        [
            _record(
                "same.txt",
                file_hash=digest,
                instance_id="pilot-instance-a",
                family_id="pilot-family-a",
                generation_seed=11,
            ),
            _record(
                "./same.txt",
                file_hash=digest,
                instance_id="pilot-instance-b",
                family_id="pilot-family-b",
                generation_seed=12,
            ),
        ]
    )

    result = _validate(manifest, root)

    _assert_rejected(result, "canonical_path", "duplicate_path")


def test_duplicate_instance_id_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    manifest = _two_file_manifest(root)
    manifest["instances"][1]["instance_id"] = manifest["instances"][0][
        "instance_id"
    ]

    result = _validate(manifest, root)

    _assert_rejected(result, "duplicate_instance_id")


def test_same_family_in_incompatible_pilot_splits_is_rejected(
    tmp_path: Path,
) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    manifest = _two_file_manifest(root)
    manifest["instances"][0]["family_id"] = "pilot-family-shared"
    manifest["instances"][1]["family_id"] = "pilot-family-shared"
    manifest["instances"][0]["split"] = "train"
    manifest["instances"][1]["split"] = "dev"

    result = _validate(manifest, root)

    _assert_rejected(result, "family", "split", "duplicate_family")


def test_duplicate_generation_identity_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    manifest = _two_file_manifest(root)
    first, second = manifest["instances"]
    for field in (
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
    ):
        second[field] = first[field]

    result = _validate(manifest, root)

    _assert_rejected(result, "duplicate_generation_identity", "generation")


# Pilot/formal leakage -----------------------------------------------------


@pytest.mark.parametrize(
    "manifest_scope",
    ["formal_train", "formal_dev", "formal_final_test"],
)
def test_formal_manifest_scope_is_rejected(
    tmp_path: Path,
    manifest_scope: str,
) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    manifest = _single_valid_manifest(root)
    manifest["manifest_scope"] = manifest_scope

    result = _validate(manifest, root)

    _assert_rejected(result, "manifest_scope", "formal")


def test_formal_matrix_scope_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    manifest = _single_valid_manifest(root)
    manifest["matrix_scope"] = "formal"

    result = _validate(manifest, root)

    _assert_rejected(result, "matrix_scope", "formal")


@pytest.mark.parametrize(
    "marker",
    ["final-test", "formal_train", "formal_dev", "formal_final_test"],
)
def test_formal_or_final_test_path_marker_is_rejected(
    tmp_path: Path,
    marker: str,
) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    content = b"synthetic marker-only fixture\n"
    relative_path = f"pilot/{marker}-fixture.txt"
    _write(root, relative_path, content)
    manifest = _manifest(
        [_record(relative_path, file_hash=_sha256_bytes(content))]
    )

    result = _validate(manifest, root)

    _assert_rejected(result, "formal", "final_test", "path_marker")


def test_final_test_lockbox_marker_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    manifest = _single_valid_manifest(root)
    manifest["instances"][0]["lockbox_status"] = "final_test_locked"

    result = _validate(manifest, root)

    _assert_rejected(result, "lockbox", "final_test")


# Explicit no-glob/no-discovery boundary ----------------------------------


def test_directory_path_is_not_an_implicit_glob(tmp_path: Path) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    directory = root / "instances"
    directory.mkdir()
    manifest = _manifest([_record("instances")])

    result = _validate(manifest, root)

    _assert_rejected(result, "directory", "file_path", "glob")


@pytest.mark.parametrize("pattern", ["*.txt", "pilot/**/*.txt", "pilot/?.txt"])
def test_glob_pattern_is_rejected(tmp_path: Path, pattern: str) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    manifest = _manifest([_record(pattern)])

    result = _validate(manifest, root)

    _assert_rejected(result, "glob", "wildcard", "path_syntax")


@pytest.mark.parametrize("missing_field", ["file_path", "file_hash"])
def test_record_missing_explicit_path_or_hash_is_rejected(
    tmp_path: Path,
    missing_field: str,
) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    manifest = _single_valid_manifest(root)
    del manifest["instances"][0][missing_field]

    result = _validate(manifest, root)

    _assert_rejected(result, missing_field, "missing")


def test_empty_manifest_does_not_discover_files(tmp_path: Path) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    _write(root, "unlisted.txt", b"must not be discovered\n")
    manifest = _manifest([])

    result = _validate(manifest, root)

    _assert_rejected(result, "instances", "records", "empty_manifest")


def test_valid_manifest_never_calls_glob_or_directory_walk(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    manifest = _single_valid_manifest(root)
    validator = _validator()

    def forbidden_discovery(*_args: Any, **_kwargs: Any):
        raise AssertionError("path validator must not discover files")

    monkeypatch.setattr(glob, "glob", forbidden_discovery)
    monkeypatch.setattr(Path, "glob", forbidden_discovery)
    monkeypatch.setattr(os, "walk", forbidden_discovery)

    result = validator.validate_pilot_paths_and_duplicates(
        manifest,
        approved_root=root,
    )

    _assert_valid(result)


# Validator-only/no-execution boundary ------------------------------------


def test_valid_result_is_inert_and_not_a_runner_receipt(tmp_path: Path) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    result = _validate(_single_valid_manifest(root), root)

    _assert_valid(result)
    assert _result_field(result, "accepted_execution", False) is False
    assert _result_field(result, "runner_receipt_id", None) is None
    assert _result_field(result, "scheduled_run_id", None) is None
    assert _result_field(result, "provider_invoked", False) is False
    assert _result_field(result, "candidate_executed", False) is False
    assert _result_field(result, "pilot_executed", False) is False


def test_valid_path_validation_does_not_invoke_provider_or_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    manifest = _single_valid_manifest(root)
    provider_factory = importlib.import_module(
        "mrta_rect_coverage.llm.operator_evolution.provider_factory"
    )
    candidate_execution = importlib.import_module(
        "mrta_rect_coverage.llm.operator_evolution.candidate_execution"
    )
    evaluator = importlib.import_module(
        "mrta_rect_coverage.llm.operator_evolution.evaluator"
    )

    def forbidden_execution(*_args: Any, **_kwargs: Any):
        raise AssertionError(
            "path validation must not invoke provider or candidate execution"
        )

    monkeypatch.setattr(provider_factory, "build_provider", forbidden_execution)
    monkeypatch.setattr(
        candidate_execution,
        "execute_candidate_process",
        forbidden_execution,
    )
    monkeypatch.setattr(evaluator, "_invoke_candidate", forbidden_execution)

    result = _validate(manifest, root)

    _assert_valid(result)


def test_rejected_result_is_inert_and_does_not_close_gate_p2(
    tmp_path: Path,
) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    manifest = _manifest([_record("../outside.txt")])

    result = _validate(manifest, root)

    _assert_rejected(result, "traversal", "root")
    assert _result_field(result, "accepted_execution", False) is False
    assert _result_field(result, "runner_receipt_id", None) is None
    assert _result_field(result, "scheduled_run_id", None) is None


# T4R: path-to-read TOCTOU boundary ---------------------------------------


def _toctou_manifest(
    root: Path,
    *,
    expected_content: bytes,
) -> tuple[Path, dict[str, Any]]:
    victim = _write(root, "victim.txt", b"benign pre-check content\n")
    return victim, _manifest(
        [
            _record(
                "victim.txt",
                file_hash=_sha256_bytes(expected_content),
            )
        ]
    )


def test_in_place_content_replacement_after_identity_check_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    replacement_content = b"replacement content after identity check\n"
    victim, manifest = _toctou_manifest(
        root,
        expected_content=replacement_content,
    )
    validator = _validator()
    original_identity = validator._file_identity
    mutation = {"performed": False}

    def mutate_after_identity(path: Path):
        identity = original_identity(path)
        assert path == victim.resolve()
        path.write_bytes(replacement_content)
        mutation["performed"] = True
        return identity

    monkeypatch.setattr(validator, "_file_identity", mutate_after_identity)

    result = validator.validate_pilot_paths_and_duplicates(
        manifest,
        approved_root=root,
    )

    assert mutation["performed"] is True
    _assert_rejected(
        result,
        "path_toctou",
        "file_identity_changed",
        "stable_handle",
    )


def test_rename_swap_after_identity_check_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    replacement_content = b"rename swap replacement\n"
    victim, manifest = _toctou_manifest(
        root,
        expected_content=replacement_content,
    )
    replacement = _write(root, "replacement.txt", replacement_content)
    validator = _validator()
    original_identity = validator._file_identity
    mutation = {"performed": False}

    def swap_after_identity(path: Path):
        identity = original_identity(path)
        assert path == victim.resolve()
        os.replace(replacement, path)
        mutation["performed"] = True
        return identity

    monkeypatch.setattr(validator, "_file_identity", swap_after_identity)

    result = validator.validate_pilot_paths_and_duplicates(
        manifest,
        approved_root=root,
    )

    assert mutation["performed"] is True
    _assert_rejected(
        result,
        "path_toctou",
        "file_identity_changed",
        "stable_handle_mismatch",
    )


def test_regular_file_swapped_to_outside_symlink_before_read_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    probe_target = _write(root, "probe-target.txt", b"probe\n")
    probe_link = root / "probe-link.txt"
    _make_symlink_or_skip(probe_link, probe_target)
    probe_link.unlink()

    outside_content = b"outside target after pre-check\n"
    outside = _write(tmp_path, "outside-target.txt", outside_content)
    victim, manifest = _toctou_manifest(
        root,
        expected_content=outside_content,
    )
    validator = _validator()
    original_identity = validator._file_identity
    mutation = {"performed": False}

    def symlink_after_identity(path: Path):
        identity = original_identity(path)
        assert path == victim.resolve()
        path.unlink()
        path.symlink_to(outside)
        mutation["performed"] = True
        return identity

    monkeypatch.setattr(validator, "_file_identity", symlink_after_identity)

    result = validator.validate_pilot_paths_and_duplicates(
        manifest,
        approved_root=root,
    )

    assert mutation["performed"] is True
    _assert_rejected(
        result,
        "path_toctou",
        "symlink",
        "root_escape",
        "file_identity_changed",
    )


def test_post_read_path_identity_change_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    benign_content = b"benign pre-check content\n"
    victim, manifest = _toctou_manifest(
        root,
        expected_content=benign_content,
    )
    replacement = _write(root, "post-read-replacement.txt", benign_content)
    validator = _validator()
    original_hash = validator._hash_explicit_file
    mutation = {"performed": False}

    def swap_after_read(path: Path) -> str:
        digest = original_hash(path)
        assert path == victim.resolve()
        os.replace(replacement, path)
        mutation["performed"] = True
        return digest

    monkeypatch.setattr(validator, "_hash_explicit_file", swap_after_read)

    result = validator.validate_pilot_paths_and_duplicates(
        manifest,
        approved_root=root,
    )

    assert mutation["performed"] is True
    _assert_rejected(
        result,
        "path_toctou",
        "post_read_identity",
        "file_identity_changed",
    )


# T4R: record/header formal leakage ---------------------------------------


@pytest.mark.parametrize(
    "formal_split",
    ["formal_train", "formal_dev", "formal_final_test"],
)
def test_record_level_formal_split_is_rejected(
    tmp_path: Path,
    formal_split: str,
) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    manifest = _single_valid_manifest(root)
    manifest["instances"][0]["split"] = formal_split

    result = _validate(manifest, root)

    _assert_rejected(result, "formal", "split", "scope")


@pytest.mark.parametrize(
    "container_kind",
    ["record_metadata", "manifest_header"],
)
@pytest.mark.parametrize(
    "formal_split",
    ["formal_train", "formal_dev", "formal_final_test"],
)
def test_nested_record_or_header_formal_split_is_rejected(
    tmp_path: Path,
    container_kind: str,
    formal_split: str,
) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    manifest = _single_valid_manifest(root)
    if container_kind == "record_metadata":
        manifest["instances"][0]["metadata"] = {"split": formal_split}
    else:
        manifest["header"] = {"split": formal_split}

    result = _validate(manifest, root)

    _assert_rejected(result, "formal", "split", "scope", "header")


@pytest.mark.parametrize(
    "formal_scope",
    ["formal_train", "formal_dev", "formal_final_test"],
)
def test_record_level_manifest_scope_is_rejected(
    tmp_path: Path,
    formal_scope: str,
) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    manifest = _single_valid_manifest(root)
    manifest["instances"][0]["manifest_scope"] = formal_scope

    result = _validate(manifest, root)

    _assert_rejected(result, "formal", "manifest_scope", "scope")


@pytest.mark.parametrize(
    "container_kind",
    ["record_metadata", "manifest_header"],
)
@pytest.mark.parametrize(
    "formal_scope",
    ["formal_train", "formal_dev", "formal_final_test"],
)
def test_nested_record_or_header_manifest_scope_is_rejected(
    tmp_path: Path,
    container_kind: str,
    formal_scope: str,
) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    manifest = _single_valid_manifest(root)
    if container_kind == "record_metadata":
        manifest["instances"][0]["metadata"] = {
            "manifest_scope": formal_scope
        }
    else:
        manifest["header"] = {"manifest_scope": formal_scope}

    result = _validate(manifest, root)

    _assert_rejected(result, "formal", "manifest_scope", "scope", "header")


def test_top_level_artifact_promotion_true_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    manifest = _single_valid_manifest(root)
    manifest["artifact_promotion_allowed"] = True

    result = _validate(manifest, root)

    _assert_rejected(result, "artifact_promotion", "promotion", "pilot")


def test_missing_top_level_artifact_promotion_field_is_rejected(
    tmp_path: Path,
) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    manifest = _single_valid_manifest(root)
    del manifest["artifact_promotion_allowed"]

    result = _validate(manifest, root)

    _assert_rejected(result, "artifact_promotion", "promotion", "missing")


def test_record_level_artifact_promotion_true_is_rejected(
    tmp_path: Path,
) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    manifest = _single_valid_manifest(root)
    manifest["instances"][0]["artifact_promotion_allowed"] = True

    result = _validate(manifest, root)

    _assert_rejected(result, "artifact_promotion", "promotion", "pilot")


def test_nested_artifact_promotion_true_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    manifest = _single_valid_manifest(root)
    manifest["header"] = {"artifact_promotion_allowed": True}

    result = _validate(manifest, root)

    _assert_rejected(result, "artifact_promotion", "promotion", "header")


# T4R: URI/UNC and non-path formal marker leakage -------------------------


@pytest.mark.parametrize(
    "uri_path",
    [
        "file://synthetic/pilot.txt",
        "http://synthetic.invalid/pilot.txt",
        "https://synthetic.invalid/pilot.txt",
        "s3://synthetic-bucket/pilot.txt",
        "gs://synthetic-bucket/pilot.txt",
        "ftp://synthetic.invalid/pilot.txt",
        "custom+pilot://synthetic/pilot.txt",
    ],
)
def test_uri_like_file_path_is_rejected_as_syntax_without_reading(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    uri_path: str,
) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    validator = _validator()
    read_attempt = {"performed": False}

    def forbidden_uri_read(_path: Path) -> str:
        read_attempt["performed"] = True
        raise AssertionError("URI-like paths must be rejected before file read")

    monkeypatch.setattr(validator, "_hash_explicit_file", forbidden_uri_read)
    manifest = _manifest([_record(uri_path)])

    result = validator.validate_pilot_paths_and_duplicates(
        manifest,
        approved_root=root,
    )

    assert read_attempt["performed"] is False
    _assert_rejected(result, "uri", "scheme", "path_syntax")


def test_unc_like_file_path_is_rejected_as_syntax_without_reading(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    validator = _validator()
    read_attempt = {"performed": False}

    def forbidden_unc_read(_path: Path) -> str:
        read_attempt["performed"] = True
        raise AssertionError("UNC-like paths must be rejected before file read")

    monkeypatch.setattr(validator, "_hash_explicit_file", forbidden_unc_read)
    manifest = _manifest([_record(r"\\server\share\pilot.txt")])

    result = validator.validate_pilot_paths_and_duplicates(
        manifest,
        approved_root=root,
    )

    assert read_attempt["performed"] is False
    _assert_rejected(result, "unc", "network_path", "path_syntax")


@pytest.mark.parametrize("identity_field", ["family_id", "instance_id"])
@pytest.mark.parametrize(
    "marker",
    ["formal_train", "formal_dev", "formal_final_test", "final_test"],
)
def test_formal_marker_in_record_identity_is_rejected(
    tmp_path: Path,
    identity_field: str,
    marker: str,
) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    manifest = _single_valid_manifest(root)
    manifest["instances"][0][identity_field] = f"pilot-{marker}-identity"

    result = _validate(manifest, root)

    _assert_rejected(result, "formal", "final_test", identity_field, "marker")


def test_final_test_marker_in_file_hash_field_is_rejected_as_leakage(
    tmp_path: Path,
) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    manifest = _single_valid_manifest(root)
    manifest["instances"][0]["file_hash"] = "final-test-hash-marker"

    result = _validate(manifest, root)

    _assert_rejected(result, "final_test", "formal", "marker")


@pytest.mark.parametrize(
    "metadata",
    [
        {"scope": "formal_train"},
        {"lockbox_status": "final_test_locked"},
    ],
)
def test_nested_scope_or_lockbox_marker_is_rejected(
    tmp_path: Path,
    metadata: dict[str, str],
) -> None:
    root = tmp_path / "pilot_root"
    root.mkdir()
    manifest = _single_valid_manifest(root)
    manifest["instances"][0]["metadata"] = metadata

    result = _validate(manifest, root)

    _assert_rejected(result, "formal", "final_test", "scope", "lockbox")
