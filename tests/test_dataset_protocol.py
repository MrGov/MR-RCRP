from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from mrta_rect_coverage.experiments.dataset_protocol import (
    DATASET_VERSION,
    INSTANCE_SCHEMA_VERSION,
    MANIFEST_SCHEMA_VERSION,
    SANITY_FAMILY_MATRIX,
    build_sanity_dataset,
    extract_intrinsic_features,
    generate_instance,
    load_manifest,
    load_manifest_instances,
    stable_generation_seed,
    write_generated_instance,
    write_manifest,
)


def test_seed_and_generated_instance_are_order_independent() -> None:
    spec = SANITY_FAMILY_MATRIX[0]
    first = generate_instance(spec, replicate_id=0)
    second = generate_instance(spec, replicate_id=0)

    assert first.generation_seed == stable_generation_seed(DATASET_VERSION, spec.family_id, 0)
    assert first.instance_id == second.instance_id
    assert first.generation_config_hash == second.generation_config_hash
    assert first.instance == second.instance


def test_generated_file_round_trips_through_production_loader(tmp_path: Path) -> None:
    generated = generate_instance(SANITY_FAMILY_MATRIX[0], replicate_id=0)
    path = write_generated_instance(generated, tmp_path)

    from mrta_rect_coverage.core.instance_loader import load_instance

    loaded = load_instance(path)
    assert loaded == generated.instance
    assert path.name == "R2_T10_0.txt"


def test_intrinsic_features_are_solver_free_and_deterministic() -> None:
    generated = generate_instance(SANITY_FAMILY_MATRIX[0], replicate_id=0)
    features = extract_intrinsic_features(generated.instance)
    assert features == extract_intrinsic_features(generated.instance)
    assert features["n_tasks"] == 10
    assert features["n_robots"] == 2
    assert features["task_robot_ratio"] == pytest.approx(5.0)
    for key in (
        "coordinate_span_x",
        "coordinate_span_y",
        "centroid_distance_to_depot",
        "spatial_dispersion",
        "width_mean",
        "width_std",
        "height_mean",
        "height_std",
        "aspect_ratio_mean",
        "aspect_ratio_std",
        "processing_h_mean",
        "processing_v_mean",
        "hv_gap_mean",
        "hv_gap_std",
        "hv_gap_max",
        "sweep_speed",
        "travel_speed",
        "turning_time",
        "estimated_travel_pressure",
        "estimated_coverage_pressure",
    ):
        assert key in features


def test_manifest_is_versioned_hashed_and_excludes_solver_results(tmp_path: Path) -> None:
    generated = generate_instance(SANITY_FAMILY_MATRIX[0], replicate_id=0)
    data_dir = tmp_path / "development"
    path = write_generated_instance(generated, data_dir)
    entry = generated.manifest_entry(path.relative_to(tmp_path.parent), file_hash=hashlib.sha256(path.read_bytes()).hexdigest())
    manifest = {"manifest_schema_version": MANIFEST_SCHEMA_VERSION, "dataset_version": DATASET_VERSION,
                "instance_schema_version": INSTANCE_SCHEMA_VERSION, "generator_version": "mr-rcrp-deterministic-generator-v1",
                "split": "development", "entries": [entry]}
    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest, manifest_path)

    loaded = load_manifest(manifest_path, expected_split="development")
    assert loaded["instance_schema_version"] == INSTANCE_SCHEMA_VERSION
    assert loaded["entries"][0]["file_hash"] == hashlib.sha256(path.read_bytes()).hexdigest()
    serialized = json.dumps(loaded, sort_keys=True)
    assert "makespan" not in serialized
    assert "solver" not in serialized
    assert "baseline" not in serialized


def test_manifest_loader_is_split_scoped_and_hash_verified(tmp_path: Path) -> None:
    generated = generate_instance(SANITY_FAMILY_MATRIX[0], replicate_id=0)
    root = tmp_path / "dataset"
    path = write_generated_instance(generated, root / "development")
    entry = generated.manifest_entry(path.relative_to(root), file_hash=hashlib.sha256(path.read_bytes()).hexdigest())
    manifest = {"manifest_schema_version": MANIFEST_SCHEMA_VERSION, "dataset_version": DATASET_VERSION,
                "instance_schema_version": INSTANCE_SCHEMA_VERSION, "generator_version": "mr-rcrp-deterministic-generator-v1",
                "split": "development", "entries": [entry]}
    manifest_path = root / "manifests" / "development.json"
    write_manifest(manifest, manifest_path)

    loaded = load_manifest_instances(manifest_path, expected_split="development")
    assert [instance.name for instance in loaded] == ["R2_T10_0"]
    with pytest.raises(ValueError, match="split"):
        load_manifest_instances(manifest_path, expected_split="final")

    path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="hash"):
        load_manifest_instances(manifest_path, expected_split="development")


def test_manifest_rejects_unknown_fields_and_uncontrolled_glob(tmp_path: Path) -> None:
    manifest = {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "dataset_version": DATASET_VERSION,
        "instance_schema_version": INSTANCE_SCHEMA_VERSION,
        "generator_version": "mr-rcrp-deterministic-generator-v1",
        "split": "development",
        "entries": [],
        "unknown": True,
    }
    with pytest.raises(ValueError, match="unknown"):
        load_manifest(tmp_path / "bad.json", document=manifest)


def test_small_sanity_dataset_has_two_manifested_instances_per_split(tmp_path: Path) -> None:
    paths = build_sanity_dataset(tmp_path)
    assert set(paths) == {"development", "held-out", "final"}
    for split, manifest_path in paths.items():
        manifest = load_manifest(manifest_path, expected_split=split)
        assert len(manifest["entries"]) == 2
        assert len(load_manifest_instances(manifest_path, expected_split=split)) == 2
