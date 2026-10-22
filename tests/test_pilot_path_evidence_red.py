from __future__ import annotations

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


PATH_MODULE = "mrta_rect_coverage.experiments.pilot_path_validator"
INTEGRITY_MODULE = "mrta_rect_coverage.experiments.pilot_integrity"
RECEIPT_MODULE = "mrta_rect_coverage.experiments.pilot_validation_receipt"
PATH_SCHEMA_VERSION = "pilot-path-validation-v1"
PATH_FIELDS = {
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
}
DUPLICATE_FIELDS = {
    "instance_id_duplicates",
    "file_hash_duplicates",
    "canonical_path_duplicates",
    "file_identity_duplicates",
    "generation_identity_duplicates",
}


def _module(name: str) -> ModuleType:
    return importlib.import_module(name)


def _path_module() -> ModuleType:
    module = _module(PATH_MODULE)
    if not hasattr(module, "build_pilot_path_validation_evidence"):
        pytest.fail(
            "Phase 6B-T4E RED: canonical T4 path evidence producer "
            "is not implemented"
        )
    return module


def _object_hash(value: Any) -> str:
    return _module(INTEGRITY_MODULE).compute_object_hash(value)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write(root: Path, name: str, content: bytes) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _record(
    file_path: str,
    *,
    file_hash: str,
    instance_id: str,
    family_id: str,
    generation_seed: int,
) -> dict[str, Any]:
    return {
        "instance_id": instance_id,
        "family_id": family_id,
        "split": "train",
        "file_path": file_path,
        "file_hash": file_hash,
        "generation_rule_version": "pilot-generator-v1",
        "generation_seed": generation_seed,
        "replicate_id": 0,
        "robots": 2,
        "tasks": 6,
        "size_stratum": "small",
        "distribution_stratum": "D1",
        "sweep_width": 1.0,
        "sweep_speed": 1.0,
        "travel_speed": 2.0,
        "turning_time": 0.5,
        "lockbox_status": "not_applicable",
    }


def _manifest(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "manifest_scope": "pilot_nonformal",
        "matrix_scope": "pilot",
        "artifact_promotion_allowed": False,
        "instances": records,
    }


def _single_manifest(root: Path) -> dict[str, Any]:
    content = b"T4E explicit pilot record\n"
    _write(root, "pilot/a.txt", content)
    return _manifest(
        [
            _record(
                "pilot/a.txt",
                file_hash=_sha256_bytes(content),
                instance_id="pilot-instance-a",
                family_id="pilot-family-a",
                generation_seed=11,
            )
        ]
    )


def _evidence(manifest: dict[str, Any], root: Path) -> dict[str, Any]:
    evidence = _path_module().build_pilot_path_validation_evidence(
        manifest,
        approved_root=root,
        manifest_object_hash=_object_hash(manifest),
    )
    assert type(evidence) is dict
    return evidence


def _body(evidence: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(value)
        for key, value in evidence.items()
        if key != "path_validation_result_id"
    }


def _prevalidation(manifest: Mapping[str, Any]) -> dict[str, Any]:
    body = {
        "prevalidation_schema_version": "pilot-prevalidation-core-v1",
        "status": "valid",
        "result_scope": "pure_object_prevalidation",
        "schema_valid": True,
        "integrity_valid": True,
        "failure_layer": None,
        "rejection_reasons": [],
        "manifest_object_hash": _object_hash(manifest),
        "pilot_family_matrix_object_hash": _object_hash({"matrix_scope": "pilot"}),
        "pilot_split_rule_object_hash": _object_hash({"assignments": {}}),
        "binding_available": True,
        "binding_unavailable_reason": None,
        "canonicalization_algorithm": "RFC8785-JCS",
        "canonicalization_version": "jcs-v1-safe-int-domain",
        "execution_authorized": False,
        "gate_p2_closed": False,
    }
    return {**body, "prevalidation_result_id": _object_hash(body)}


def _raw(manifest: Mapping[str, Any]) -> bytes:
    return json.dumps(
        manifest,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def test_real_t4_valid_path_produces_exact_versioned_evidence(tmp_path: Path) -> None:
    root = tmp_path / "pilot-root"
    root.mkdir()
    manifest = _single_manifest(root)

    evidence = _evidence(manifest, root)

    assert set(evidence) == PATH_FIELDS
    assert evidence["path_validation_schema_version"] == PATH_SCHEMA_VERSION
    assert evidence["status"] == "valid"
    assert evidence["result_scope"] == "path_duplicate_validation"
    assert evidence["manifest_object_hash"] == _object_hash(manifest)
    assert evidence["duplicate_validation_summary"] == {
        "instance_id_duplicates": 0,
        "file_hash_duplicates": 0,
        "canonical_path_duplicates": 0,
        "file_identity_duplicates": 0,
        "generation_identity_duplicates": 0,
    }
    assert evidence["file_identity_check"] == "supported_pass"
    assert evidence["rejection_reasons"] == []
    assert evidence["no_glob_confirmed"] is True
    assert evidence["no_directory_discovery_confirmed"] is True
    assert evidence["execution_authorized"] is False
    assert evidence["gate_p2_closed"] is False
    assert evidence["path_validation_result_id"] == _object_hash(_body(evidence))


def test_approved_root_fingerprint_uses_canonical_path_identity_only(
    tmp_path: Path,
) -> None:
    root = tmp_path / "pilot-root"
    root.mkdir()
    manifest = _single_manifest(root)

    first = _evidence(manifest, root)
    same = _evidence(manifest, root / ".")
    _write(root, "unlisted.txt", b"must not enter root fingerprint\n")
    with_unlisted_content = _evidence(manifest, root)

    canonical_root = os.path.normcase(str(root.resolve(strict=True)))
    expected = _object_hash(
        {
            "schema": "pilot-approved-root-fingerprint-v1",
            "canonical_approved_root": canonical_root,
        }
    )
    assert first["approved_root_fingerprint"] == expected
    assert same["approved_root_fingerprint"] == expected
    assert with_unlisted_content["approved_root_fingerprint"] == expected
    assert len(expected) == 64 and expected == expected.lower()


def test_different_canonical_roots_change_fingerprint_and_result_id(
    tmp_path: Path,
) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_root.mkdir()
    second_root.mkdir()
    first_manifest = _single_manifest(first_root)
    second_manifest = _single_manifest(second_root)

    first = _evidence(first_manifest, first_root)
    second = _evidence(second_manifest, second_root)

    assert first["approved_root_fingerprint"] != second["approved_root_fingerprint"]
    assert first["path_validation_result_id"] != second["path_validation_result_id"]


def test_duplicate_summary_counts_additional_records_not_reason_codes(
    tmp_path: Path,
) -> None:
    root = tmp_path / "pilot-root"
    root.mkdir()
    records: list[dict[str, Any]] = []
    for index in range(3):
        content = f"unique-{index}\n".encode()
        name = f"{index}.txt"
        _write(root, name, content)
        records.append(
            _record(
                name,
                file_hash=_sha256_bytes(content),
                instance_id="shared-instance",
                family_id=f"family-{index}",
                generation_seed=index,
            )
        )

    evidence = _evidence(_manifest(records), root)

    assert evidence["status"] == "rejected"
    assert evidence["duplicate_validation_summary"] == {
        "instance_id_duplicates": 2,
        "file_hash_duplicates": 0,
        "canonical_path_duplicates": 0,
        "file_identity_duplicates": 0,
        "generation_identity_duplicates": 0,
    }
    assert evidence["rejection_reasons"].count("duplicate_instance_id") == 1


def test_one_record_can_increment_all_duplicate_dimensions(tmp_path: Path) -> None:
    root = tmp_path / "pilot-root"
    root.mkdir()
    content = b"same explicit file\n"
    _write(root, "same.txt", content)
    digest = _sha256_bytes(content)
    first = _record(
        "same.txt",
        file_hash=digest,
        instance_id="same-instance",
        family_id="family-a",
        generation_seed=11,
    )
    second = copy.deepcopy(first)
    second["family_id"] = "family-b"

    evidence = _evidence(_manifest([first, second]), root)

    assert evidence["duplicate_validation_summary"] == {
        "instance_id_duplicates": 1,
        "file_hash_duplicates": 1,
        "canonical_path_duplicates": 1,
        "file_identity_duplicates": 1,
        "generation_identity_duplicates": 1,
    }


def test_hardlink_duplicate_increments_file_identity_counter(tmp_path: Path) -> None:
    root = tmp_path / "pilot-root"
    root.mkdir()
    content = b"hardlink identity\n"
    source = _write(root, "source.txt", content)
    alias = root / "alias.txt"
    try:
        os.link(source, alias)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"hardlink unsupported in isolated tmp_path: {exc}")
    digest = _sha256_bytes(content)
    manifest = _manifest(
        [
            _record(
                "source.txt",
                file_hash=digest,
                instance_id="source-instance",
                family_id="source-family",
                generation_seed=11,
            ),
            _record(
                "alias.txt",
                file_hash=digest,
                instance_id="alias-instance",
                family_id="alias-family",
                generation_seed=12,
            ),
        ]
    )

    evidence = _evidence(manifest, root)

    assert evidence["duplicate_validation_summary"]["file_identity_duplicates"] == 1


def test_no_glob_is_an_input_fact_independent_of_overall_status(tmp_path: Path) -> None:
    root = tmp_path / "pilot-root"
    root.mkdir()
    content = b"duplicate content\n"
    _write(root, "a.txt", content)
    _write(root, "b.txt", content)
    digest = _sha256_bytes(content)
    duplicate_manifest = _manifest(
        [
            _record(
                "a.txt",
                file_hash=digest,
                instance_id="a",
                family_id="a",
                generation_seed=11,
            ),
            _record(
                "b.txt",
                file_hash=digest,
                instance_id="b",
                family_id="b",
                generation_seed=12,
            ),
        ]
    )
    glob_manifest = _manifest(
        [
            _record(
                "*.txt",
                file_hash=digest,
                instance_id="glob",
                family_id="glob",
                generation_seed=13,
            )
        ]
    )

    duplicate_evidence = _evidence(duplicate_manifest, root)
    glob_evidence = _evidence(glob_manifest, root)

    assert duplicate_evidence["status"] == "rejected"
    assert duplicate_evidence["no_glob_confirmed"] is True
    assert glob_evidence["status"] == "rejected"
    assert glob_evidence["no_glob_confirmed"] is False


def test_canonical_evidence_path_does_not_discover_directory_contents(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "pilot-root"
    root.mkdir()
    manifest = _single_manifest(root)

    def forbidden(*_args: Any, **_kwargs: Any):
        raise AssertionError("T4 evidence path must not discover directory contents")

    monkeypatch.setattr(glob, "glob", forbidden)
    monkeypatch.setattr(Path, "glob", forbidden)
    monkeypatch.setattr(Path, "rglob", forbidden)
    monkeypatch.setattr(os, "walk", forbidden)
    monkeypatch.setattr(os, "scandir", forbidden)
    monkeypatch.setattr(os, "listdir", forbidden)

    evidence = _evidence(manifest, root)

    assert evidence["no_directory_discovery_confirmed"] is True


def test_evidence_identity_binds_each_new_provenance_field(tmp_path: Path) -> None:
    root = tmp_path / "pilot-root"
    root.mkdir()
    evidence = _evidence(_single_manifest(root), root)

    mutations = {
        "approved_root_fingerprint": "b" * 64,
        "duplicate_validation_summary": {
            **evidence["duplicate_validation_summary"],
            "instance_id_duplicates": 1,
        },
        "no_glob_confirmed": False,
        "no_directory_discovery_confirmed": False,
    }
    for field, value in mutations.items():
        changed = copy.deepcopy(evidence)
        changed[field] = value
        assert _object_hash(_body(changed)) != evidence["path_validation_result_id"]


def test_real_t4_evidence_builds_and_verifies_valid_t5_receipt(tmp_path: Path) -> None:
    root = tmp_path / "pilot-root"
    root.mkdir()
    manifest = _single_manifest(root)
    evidence = _evidence(manifest, root)
    prevalidation = _prevalidation(manifest)
    raw = _raw(manifest)
    receipt_module = _module(RECEIPT_MODULE)

    receipt = receipt_module.build_pilot_validation_receipt(
        raw_manifest_bytes=raw,
        manifest_obj=manifest,
        prevalidation_result=prevalidation,
        path_validation_result=evidence,
        validator_identity="t4e-real-integration-v1",
    )
    verification = receipt_module.verify_pilot_validation_receipt(
        receipt,
        raw_manifest_bytes=raw,
        manifest_obj=manifest,
        prevalidation_result=prevalidation,
        path_validation_result=evidence,
    )

    assert receipt["status"] == "valid"
    assert receipt["path_validation_evidence"] == evidence
    assert verification.valid is True
    assert verification.rejection_reasons == ()


def test_real_rejected_t4_evidence_cannot_become_valid_receipt(tmp_path: Path) -> None:
    root = tmp_path / "pilot-root"
    root.mkdir()
    content = b"same\n"
    _write(root, "a.txt", content)
    _write(root, "b.txt", content)
    digest = _sha256_bytes(content)
    manifest = _manifest(
        [
            _record(
                "a.txt",
                file_hash=digest,
                instance_id="a",
                family_id="a",
                generation_seed=11,
            ),
            _record(
                "b.txt",
                file_hash=digest,
                instance_id="b",
                family_id="b",
                generation_seed=12,
            ),
        ]
    )
    evidence = _evidence(manifest, root)
    prevalidation = _prevalidation(manifest)
    raw = _raw(manifest)
    receipt_module = _module(RECEIPT_MODULE)

    receipt = receipt_module.build_pilot_validation_receipt(
        raw_manifest_bytes=raw,
        manifest_obj=manifest,
        prevalidation_result=prevalidation,
        path_validation_result=evidence,
        validator_identity="t4e-real-rejected-integration-v1",
    )
    verification = receipt_module.verify_pilot_validation_receipt(
        receipt,
        raw_manifest_bytes=raw,
        manifest_obj=manifest,
        prevalidation_result=prevalidation,
        path_validation_result=evidence,
    )

    assert evidence["status"] == "rejected"
    assert receipt["status"] == "rejected"
    assert verification.valid is True
