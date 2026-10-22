"""Deterministic, manifest-driven instance/data protocol for R2.

This module only generates and validates instance artifacts. It does not
execute optimization experiments or external services.
"""
from __future__ import annotations

import hashlib
from itertools import combinations
import json
import math
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Iterable

from ..core.instance_loader import load_instance
from ..core.models import Instance, TaskRegion
from ..core.state_generator import generate_all_states
from ..utils.geometry import manhattan_distance

INSTANCE_SCHEMA_VERSION = "mr-rcrp-instance-v2"
DATASET_VERSION = "r2-sanity-v1"
GENERATOR_VERSION = "mr-rcrp-deterministic-generator-v1"
MANIFEST_SCHEMA_VERSION = "mr-rcrp-dataset-manifest-v1"
NEAR_TIE_THRESHOLD = 0.05
_SPLITS = frozenset({"development", "held-out", "final"})
_GEOMETRY = frozenset({"square-ish", "horizontal-elongated", "vertical-elongated", "mixed-aspect"})
_SPATIAL = frozenset({"uniform", "clustered", "multi-cluster", "depot-near", "dispersed"})
_TRAVEL = frozenset({"travel-dominated", "balanced", "coverage-dominated"})
_HV = frozenset({"low-HV-sensitivity", "mixed-HV", "high-HV-sensitivity"})
_MANIFEST_FIELDS = {"manifest_schema_version", "dataset_version", "instance_schema_version", "generator_version", "split", "entries"}
_ENTRY_FIELDS = {
    "dataset_version", "instance_schema_version", "generator_version", "instance_id", "family_id", "split",
    "replicate_id", "generation_seed", "n_robots", "n_tasks", "load_regime", "sweep_width", "sweep_speed", "travel_speed",
    "turning_time", "geometry_regime", "spatial_regime", "travel_coverage_regime", "hv_sensitivity_regime",
    "file_path", "file_hash", "generation_config_hash",
}


@dataclass(frozen=True)
class FamilySpec:
    family_id: str
    split: str
    n_robots: int
    n_tasks: int
    geometry_regime: str
    spatial_regime: str
    travel_coverage_regime: str
    hv_sensitivity_regime: str
    replicate_count: int = 1
    coordinate_scale: float = 80.0
    overlap_policy: str = "non-overlapping"

    def validate(self) -> None:
        if not self.family_id or self.split not in _SPLITS:
            raise ValueError("invalid family identity or split")
        if type(self.n_robots) is not int or self.n_robots <= 0:
            raise ValueError("n_robots must be a positive integer")
        if type(self.n_tasks) is not int or self.n_tasks <= 0:
            raise ValueError("n_tasks must be a positive integer")
        if self.geometry_regime not in _GEOMETRY or self.spatial_regime not in _SPATIAL:
            raise ValueError("unsupported geometry or spatial regime")
        if self.travel_coverage_regime not in _TRAVEL or self.hv_sensitivity_regime not in _HV:
            raise ValueError("unsupported travel/coverage or H/V regime")
        if type(self.replicate_count) is not int or self.replicate_count <= 0:
            raise ValueError("replicate_count must be positive")
        if self.coordinate_scale <= 0 or self.overlap_policy != "non-overlapping":
            raise ValueError("invalid coordinate scale or overlap policy")


@dataclass(frozen=True)
class GeneratedInstance:
    instance: Instance
    instance_id: str
    family_id: str
    split: str
    replicate_id: int
    generation_seed: int
    generation_config_hash: str
    dataset_version: str = DATASET_VERSION

    def manifest_entry(self, file_path: str | Path, *, file_hash: str | None = None) -> dict[str, Any]:
        spec = _spec_from_generated(self)
        return {
            "dataset_version": self.dataset_version,
            "instance_schema_version": INSTANCE_SCHEMA_VERSION,
            "generator_version": GENERATOR_VERSION,
            "instance_id": self.instance_id,
            "family_id": self.family_id,
            "split": self.split,
            "replicate_id": self.replicate_id,
            "generation_seed": self.generation_seed,
            "n_robots": self.instance.robot_count,
            "n_tasks": self.instance.task_count,
            "load_regime": _load_regime(self.instance.task_count / self.instance.robot_count),
            "sweep_width": self.instance.sweep_width,
            "sweep_speed": self.instance.sweep_speed,
            "travel_speed": self.instance.travel_speed,
            "turning_time": self.instance.turning_time,
            "geometry_regime": spec.geometry_regime,
            "spatial_regime": spec.spatial_regime,
            "travel_coverage_regime": spec.travel_coverage_regime,
            "hv_sensitivity_regime": spec.hv_sensitivity_regime,
            "file_path": Path(file_path).as_posix(),
            "file_hash": file_hash or "",
            "generation_config_hash": self.generation_config_hash,
        }


SANITY_FAMILY_MATRIX = (
    FamilySpec("F_DEV_BALANCED", "development", 2, 10, "square-ish", "uniform", "balanced", "mixed-HV"),
    FamilySpec("F_DEV_CLUSTERED", "development", 2, 20, "horizontal-elongated", "clustered", "coverage-dominated", "high-HV-sensitivity"),
    FamilySpec("F_HOLD_DISPERSED", "held-out", 4, 20, "vertical-elongated", "dispersed", "travel-dominated", "mixed-HV"),
    FamilySpec("F_HOLD_DEPOT_NEAR", "held-out", 4, 20, "mixed-aspect", "depot-near", "balanced", "low-HV-sensitivity"),
    FamilySpec("F_FINAL_SCALE", "final", 6, 40, "mixed-aspect", "multi-cluster", "coverage-dominated", "high-HV-sensitivity"),
    FamilySpec("F_FINAL_TRAVEL", "final", 6, 40, "horizontal-elongated", "dispersed", "travel-dominated", "mixed-HV"),
)


def stable_generation_seed(dataset_version: str, family_id: str, replicate_id: int) -> int:
    if type(replicate_id) is not int or replicate_id < 0:
        raise ValueError("replicate_id must be a non-negative integer")
    payload = f"{dataset_version}\0{family_id}\0{replicate_id}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def generate_instance(spec: FamilySpec, replicate_id: int, *, dataset_version: str = DATASET_VERSION) -> GeneratedInstance:
    spec.validate()
    if type(replicate_id) is not int or not 0 <= replicate_id < spec.replicate_count:
        raise ValueError("replicate_id is outside the family replicate range")
    seed = stable_generation_seed(dataset_version, spec.family_id, replicate_id)
    rng = random.Random(seed)
    sweep_width, sweep_speed, travel_speed, turning_time = _service_parameters(spec)
    tasks = _generate_tasks(spec, rng)
    instance = Instance(
        name=f"R{spec.n_robots}_T{spec.n_tasks}_{replicate_id}",
        depot=(0.0, 0.0),
        robot_count=spec.n_robots,
        sweep_speed=sweep_speed,
        travel_speed=travel_speed,
        sweep_width=sweep_width,
        turning_time=turning_time,
        tasks=tasks,
        rep_id=replicate_id,
    )
    config_hash = _hash_json({"dataset_version": dataset_version, "generator_version": GENERATOR_VERSION, "spec": asdict(spec)})
    return GeneratedInstance(instance, f"{spec.family_id}_r{replicate_id}", spec.family_id, spec.split, replicate_id, seed, config_hash, dataset_version)


def write_generated_instance(generated: GeneratedInstance, output_dir: str | Path, *, overwrite: bool = False) -> Path:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    path = output / f"{generated.instance.name}.txt"
    if path.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite existing instance: {path}")
    instance = generated.instance
    lines = [
        f"{instance.task_count} {instance.robot_count}",
        f"{instance.sweep_width:.17g} {instance.sweep_speed:.17g} {instance.travel_speed:.17g} {instance.turning_time:.17g}",
        " ".join(f"{task.x_left:.17g}" for task in instance.tasks),
        " ".join(f"{task.x_right:.17g}" for task in instance.tasks),
        " ".join(f"{task.y_bottom:.17g}" for task in instance.tasks),
        " ".join(f"{task.y_top:.17g}" for task in instance.tasks),
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    if load_instance(path) != instance:
        raise ValueError("generated instance failed production-loader round trip")
    return path


def extract_intrinsic_features(instance: Instance) -> dict[str, float | int]:
    if not isinstance(instance, Instance):
        raise TypeError("instance must be an Instance")
    widths = [task.width for task in instance.tasks]
    heights = [task.height for task in instance.tasks]
    centers = [((task.x_left + task.x_right) / 2, (task.y_bottom + task.y_top) / 2) for task in instance.tasks]
    h_values = [_processing_time(task, "H", instance) for task in instance.tasks]
    v_values = [_processing_time(task, "V", instance) for task in instance.tasks]
    gaps = [abs(h - v) for h, v in zip(h_values, v_values)]
    relative_gaps = [gap / max(h, v) for gap, h, v in zip(gaps, h_values, v_values)]
    minimum_processing = [min(h, v) for h, v in zip(h_values, v_values)]
    cx, cy = mean(x for x, _ in centers), mean(y for _, y in centers)
    distances = [abs(x - instance.depot[0]) + abs(y - instance.depot[1]) for x, y in centers]
    pairwise_distances = [manhattan_distance(first, second) for first, second in combinations(centers, 2)]
    spans_x = max(task.x_right for task in instance.tasks) - min(task.x_left for task in instance.tasks)
    spans_y = max(task.y_top for task in instance.tasks) - min(task.y_bottom for task in instance.tasks)
    travel_pressure = (spans_x + spans_y) / instance.travel_speed
    coverage_pressure = sum(minimum_processing)
    processing_load_lb = coverage_pressure / instance.robot_count

    states_by_task = generate_all_states(instance)
    isolated_spreads: list[float] = []
    entry_spreads: list[float] = []
    exit_spreads: list[float] = []
    processing_spreads: list[float] = []
    for states in states_by_task.values():
        isolated_costs = [
            manhattan_distance(instance.depot, state.entry_point) / instance.travel_speed
            + state.processing_time
            + manhattan_distance(state.exit_point, instance.depot) / instance.travel_speed
            for state in states
        ]
        isolated_spreads.append(max(isolated_costs) - min(isolated_costs))
        processing_times = [state.processing_time for state in states]
        processing_spreads.append(max(processing_times) - min(processing_times))
        entry_points = list(dict.fromkeys(state.entry_point for state in states))
        exit_points = list(dict.fromkeys(state.exit_point for state in states))
        entry_spreads.append(_max_pairwise_distance(entry_points))
        exit_spreads.append(_max_pairwise_distance(exit_points))

    h_preferred = sum(h + 1e-9 < v for h, v in zip(h_values, v_values))
    v_preferred = sum(v + 1e-9 < h for h, v in zip(h_values, v_values))
    near_ties = sum(gap <= NEAR_TIE_THRESHOLD for gap in relative_gaps)
    aspect_ratios = [w / h for w, h in zip(widths, heights)]
    return {
        "n_tasks": instance.task_count, "n_robots": instance.robot_count, "task_robot_ratio": instance.task_count / instance.robot_count,
        "coordinate_span_x": spans_x, "coordinate_span_y": spans_y,
        "task_centroid_x": cx, "task_centroid_y": cy,
        "centroid_distance_to_depot": abs(cx - instance.depot[0]) + abs(cy - instance.depot[1]),
        "centroid_distance_mean": mean(distances), "centroid_distance_max": max(distances),
        "spatial_dispersion": pstdev(distances) if len(distances) > 1 else 0.0,
        "pairwise_distance_mean": mean(pairwise_distances) if pairwise_distances else 0.0,
        "pairwise_distance_std": pstdev(pairwise_distances) if len(pairwise_distances) > 1 else 0.0,
        "pairwise_distance_max": max(pairwise_distances, default=0.0),
        "width_mean": mean(widths), "width_std": pstdev(widths) if len(widths) > 1 else 0.0, "width_min": min(widths), "width_max": max(widths),
        "height_mean": mean(heights), "height_std": pstdev(heights) if len(heights) > 1 else 0.0, "height_min": min(heights), "height_max": max(heights),
        "aspect_ratio_mean": mean(aspect_ratios),
        "aspect_ratio_std": pstdev(aspect_ratios) if len(aspect_ratios) > 1 else 0.0,
        "aspect_ratio_min": min(aspect_ratios), "aspect_ratio_max": max(aspect_ratios),
        "processing_h_mean": mean(h_values), "processing_v_mean": mean(v_values),
        "hv_gap_mean": mean(gaps), "hv_gap_std": pstdev(gaps) if len(gaps) > 1 else 0.0, "hv_gap_max": max(gaps),
        "relative_hv_gap_mean": mean(relative_gaps),
        "relative_hv_gap_std": pstdev(relative_gaps) if len(relative_gaps) > 1 else 0.0,
        "relative_hv_gap_max": max(relative_gaps),
        "fraction_H_preferred": h_preferred / instance.task_count,
        "fraction_V_preferred": v_preferred / instance.task_count,
        "fraction_near_tie": near_ties / instance.task_count,
        "near_tie_threshold": NEAR_TIE_THRESHOLD,
        "sum_p_min": coverage_pressure, "mean_p_min": mean(minimum_processing),
        "std_p_min": pstdev(minimum_processing) if len(minimum_processing) > 1 else 0.0,
        "max_p_min": max(minimum_processing), "processing_load_lb": processing_load_lb,
        "heavy_task_ratio": max(minimum_processing) / processing_load_lb if processing_load_lb else 0.0,
        "processing_time_spread_mean": mean(processing_spreads),
        "entry_corner_geometric_spread_mean": mean(entry_spreads),
        "exit_corner_geometric_spread_mean": mean(exit_spreads),
        "state_variability_mean": mean(isolated_spreads),
        "state_variability_std": pstdev(isolated_spreads) if len(isolated_spreads) > 1 else 0.0,
        "state_variability_max": max(isolated_spreads),
        "sweep_speed": instance.sweep_speed, "travel_speed": instance.travel_speed, "turning_time": instance.turning_time,
        "estimated_travel_pressure": travel_pressure, "estimated_coverage_pressure": coverage_pressure,
    }


def _max_pairwise_distance(points: list[tuple[float, float]]) -> float:
    return max(
        (manhattan_distance(first, second) for first, second in combinations(points, 2)),
        default=0.0,
    )


def write_manifest(manifest: dict[str, Any], path: str | Path) -> Path:
    _validate_manifest(manifest)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite existing manifest: {destination}")
    destination.write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
    return destination


def load_manifest(path: str | Path, *, expected_split: str | None = None, document: dict[str, Any] | None = None) -> dict[str, Any]:
    manifest = document if document is not None else json.loads(Path(path).read_text(encoding="utf-8"))
    _validate_manifest(manifest)
    if expected_split is not None and manifest["split"] != expected_split:
        raise ValueError("manifest split does not match expected split")
    return manifest


def load_manifest_instances(manifest_path: str | Path, *, expected_split: str) -> list[Instance]:
    manifest_file = Path(manifest_path)
    manifest = load_manifest(manifest_file, expected_split=expected_split)
    root = manifest_file.parent.parent
    instances: list[Instance] = []
    for entry in manifest["entries"]:
        if entry["split"] != expected_split:
            raise ValueError("entry split does not match manifest split")
        instance_path = (root / entry["file_path"]).resolve()
        try:
            instance_path.relative_to(root.resolve())
        except ValueError as exc:
            raise ValueError("manifest path escapes dataset root") from exc
        if not instance_path.is_file():
            raise ValueError("manifest instance file is missing")
        if hashlib.sha256(instance_path.read_bytes()).hexdigest() != entry["file_hash"]:
            raise ValueError("manifest file hash mismatch")
        instance = load_instance(instance_path)
        if instance.robot_count != entry["n_robots"] or instance.task_count != entry["n_tasks"]:
            raise ValueError("manifest metadata does not match instance")
        instances.append(instance)
    return instances


def build_sanity_dataset(root: str | Path, *, overwrite: bool = False) -> dict[str, Path]:
    root_path = Path(root)
    output: dict[str, Path] = {}
    for split in sorted(_SPLITS):
        entries: list[dict[str, Any]] = []
        for spec in SANITY_FAMILY_MATRIX:
            if spec.split != split:
                continue
            for replicate_id in range(spec.replicate_count):
                generated = generate_instance(spec, replicate_id)
                path = write_generated_instance(generated, root_path / "data" / "r2_sanity" / split / spec.family_id, overwrite=overwrite)
                rel_path = path.relative_to(root_path).as_posix()
                entry = generated.manifest_entry(rel_path, file_hash=hashlib.sha256(path.read_bytes()).hexdigest())
                entries.append(entry)
        manifest = {"manifest_schema_version": MANIFEST_SCHEMA_VERSION, "dataset_version": DATASET_VERSION,
                    "instance_schema_version": INSTANCE_SCHEMA_VERSION, "generator_version": GENERATOR_VERSION,
                    "split": split, "entries": sorted(entries, key=lambda item: item["instance_id"])}
        manifest_path = root_path / "manifests" / f"{DATASET_VERSION}_{split}.json"
        if manifest_path.exists() and not overwrite:
            raise FileExistsError(f"refusing to overwrite existing manifest: {manifest_path}")
        if overwrite and manifest_path.exists():
            manifest_path.unlink()
        output[split] = write_manifest(manifest, manifest_path)
    return output


def _validate_manifest(manifest: Any) -> None:
    if type(manifest) is not dict or set(manifest) != _MANIFEST_FIELDS:
        raise ValueError("manifest has unknown or missing fields")
    if manifest["manifest_schema_version"] != MANIFEST_SCHEMA_VERSION:
        raise ValueError("unsupported manifest schema version")
    if manifest["dataset_version"] != DATASET_VERSION or manifest["instance_schema_version"] != INSTANCE_SCHEMA_VERSION or manifest["generator_version"] != GENERATOR_VERSION:
        raise ValueError("manifest version mismatch")
    if manifest["split"] not in _SPLITS or type(manifest["entries"]) is not list:
        raise ValueError("invalid manifest split or entries")
    seen: set[str] = set()
    for entry in manifest["entries"]:
        if type(entry) is not dict or set(entry) != _ENTRY_FIELDS:
            raise ValueError("manifest entry has unknown or missing fields")
        if entry["instance_id"] in seen:
            raise ValueError("duplicate instance_id in manifest")
        seen.add(entry["instance_id"])
        if entry["split"] != manifest["split"]:
            raise ValueError("entry split mismatch")
        if type(entry["file_hash"]) is not str or len(entry["file_hash"]) != 64 or any(c not in "0123456789abcdef" for c in entry["file_hash"]):
            raise ValueError("invalid file hash")


def _hash_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


def _service_parameters(spec: FamilySpec) -> tuple[float, float, float, float]:
    if spec.travel_coverage_regime == "travel-dominated":
        return 2.0, 2.0, 0.45, 0.1
    if spec.travel_coverage_regime == "coverage-dominated":
        return 1.5, 0.65, 2.5, 0.8
    return 1.5, 1.0, 1.0, 0.4


def _load_regime(load_ratio: float) -> str:
    if load_ratio < 5.0:
        return "low"
    if load_ratio <= 8.0:
        return "medium"
    return "high"


def _generate_tasks(spec: FamilySpec, rng: random.Random) -> list[TaskRegion]:
    scale_factor = 3.0 if spec.n_tasks >= 40 else (1.8 if spec.n_tasks >= 20 else 1.0)
    if spec.spatial_regime == "dispersed":
        scale_factor *= 1.6
    scale = spec.coordinate_scale * scale_factor
    tasks: list[TaskRegion] = []
    for task_id in range(1, spec.n_tasks + 1):
        width, height = _rectangle_dimensions(spec.geometry_regime, rng)
        for _ in range(5000):
            x, y = _candidate_center(spec.spatial_regime, scale, task_id, spec.n_tasks, rng)
            candidate = TaskRegion(task_id, x - width / 2, y - height / 2, x + width / 2, y + height / 2)
            if all(not _overlaps(candidate, existing) for existing in tasks):
                tasks.append(candidate)
                break
        else:
            raise RuntimeError(f"unable to place non-overlapping task {task_id}")
    return tasks


def _rectangle_dimensions(regime: str, rng: random.Random) -> tuple[float, float]:
    if regime == "square-ish":
        side = rng.uniform(4.0, 7.0)
        return side, side * rng.uniform(0.85, 1.15)
    if regime == "horizontal-elongated":
        return rng.uniform(8.0, 14.0), rng.uniform(2.5, 4.5)
    if regime == "vertical-elongated":
        return rng.uniform(2.5, 4.5), rng.uniform(8.0, 14.0)
    if rng.random() < 0.5:
        return rng.uniform(8.0, 14.0), rng.uniform(2.5, 4.5)
    return rng.uniform(2.5, 4.5), rng.uniform(8.0, 14.0)


def _candidate_center(spatial: str, scale: float, task_id: int, task_count: int, rng: random.Random) -> tuple[float, float]:
    if spatial == "depot-near":
        return rng.uniform(8.0, scale * 0.45), rng.uniform(8.0, scale * 0.45)
    if spatial in {"clustered", "multi-cluster"}:
        centers = [(scale * 0.25, scale * 0.3), (scale * 0.72, scale * 0.7)]
        cx, cy = centers[(task_id - 1) % len(centers)]
        return rng.uniform(cx - scale * 0.28, cx + scale * 0.28), rng.uniform(cy - scale * 0.28, cy + scale * 0.28)
    return rng.uniform(7.0, scale - 7.0), rng.uniform(7.0, scale - 7.0)


def _overlaps(first: TaskRegion, second: TaskRegion) -> bool:
    return not (first.x_right <= second.x_left or second.x_right <= first.x_left or first.y_top <= second.y_bottom or second.y_top <= first.y_bottom)


def _processing_time(task: TaskRegion, mode: str, instance: Instance) -> float:
    sweeps = max(1, math.ceil((task.height if mode == "H" else task.width) / instance.sweep_width))
    length = task.width if mode == "H" else task.height
    return sweeps * length / instance.sweep_speed + (sweeps - 1) * instance.turning_time


def _spec_from_generated(generated: GeneratedInstance) -> FamilySpec:
    for spec in SANITY_FAMILY_MATRIX:
        if spec.family_id == generated.family_id:
            return spec
    raise ValueError(f"unknown generated family: {generated.family_id}")


__all__ = [
    "DATASET_VERSION", "GENERATOR_VERSION", "INSTANCE_SCHEMA_VERSION", "MANIFEST_SCHEMA_VERSION", "NEAR_TIE_THRESHOLD",
    "FamilySpec", "GeneratedInstance", "SANITY_FAMILY_MATRIX", "stable_generation_seed", "generate_instance",
    "write_generated_instance", "extract_intrinsic_features", "write_manifest", "load_manifest", "load_manifest_instances",
    "build_sanity_dataset",
]
