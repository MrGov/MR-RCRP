"""Deterministic instance/data protocol for R2 and paired E10 development data.

This module generates and validates instance artifacts. Optional explicit E10
smoke validation runs a few B1 solves; generation never invokes optimization.
"""
from __future__ import annotations

import argparse
import csv
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
    structural_scenario: str | None = None

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
        if self.structural_scenario is not None and (
            self.structural_scenario not in STRUCTURAL_SCENARIOS or (self.n_robots,self.n_tasks)!=(4,40)
        ):
            raise ValueError("structural scenarios require the E10 R4/T40 design")


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
            "generator_version": STRUCTURAL_GENERATOR_VERSION if self.dataset_version==STRUCTURAL_VERSION else GENERATOR_VERSION,
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

STRUCTURAL_VERSION = "e10-structural-development-v1"
STRUCTURAL_GENERATOR_VERSION = "mr-rcrp-paired-structural-v1"
STRUCTURAL_SCENARIOS = ('BASE','HV-GEOM','SPATIAL','BOTTLENECK','TURN-HIGH','TRAVEL-HIGH','SWEEP-NARROW')
STRUCTURAL_FAMILY_MATRIX = tuple(FamilySpec(
    f'E10_{scenario}', 'development', 4, 40,
    'mixed-aspect' if scenario=='HV-GEOM' else 'square-ish',
    'dispersed' if scenario=='SPATIAL' else 'uniform','balanced',
    'high-HV-sensitivity' if scenario=='HV-GEOM' else 'mixed-HV',
    replicate_count=3,coordinate_scale=600.,structural_scenario=scenario
) for scenario in STRUCTURAL_SCENARIOS)


def stable_generation_seed(dataset_version: str, family_id: str, replicate_id: int) -> int:
    if type(replicate_id) is not int or replicate_id < 0:
        raise ValueError("replicate_id must be a non-negative integer")
    payload = f"{dataset_version}\0{family_id}\0{replicate_id}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def generate_instance(spec: FamilySpec, replicate_id: int, *, dataset_version: str = DATASET_VERSION) -> GeneratedInstance:
    spec.validate()
    if type(replicate_id) is not int or not 0 <= replicate_id < spec.replicate_count:
        raise ValueError("replicate_id is outside the family replicate range")
    if spec.structural_scenario is not None:
        return _generate_structural(spec,replicate_id,dataset_version)
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
    # Preserve R2 configuration hashes after adding the optional E10 extension.
    legacy_spec=asdict(spec);legacy_spec.pop('structural_scenario')
    config_hash = _hash_json({"dataset_version": dataset_version, "generator_version": GENERATOR_VERSION, "spec": legacy_spec})
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
    h_sweeps=[max(1,math.ceil(h/instance.sweep_width)) for h in heights]
    v_sweeps=[max(1,math.ceil(w/instance.sweep_width)) for w in widths]
    preferred_turns=[(nh-1 if ph<=pv else nv-1)*instance.turning_time
                     for nh,nv,ph,pv in zip(h_sweeps,v_sweeps,h_values,v_values)]
    unoriented_aspect=[max(w/h,h/w) for w,h in zip(widths,heights)]
    areas=[w*h for w,h in zip(widths,heights)]
    nearest=[min(manhattan_distance(c,other) for j,other in enumerate(centers) if j!=k)
             for k,c in enumerate(centers)] if len(centers)>1 else [0.]
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
        "processing_h_std":pstdev(h_values),"processing_h_min":min(h_values),"processing_h_max":max(h_values),
        "processing_v_std":pstdev(v_values),"processing_v_min":min(v_values),"processing_v_max":max(v_values),
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
        "sweep_width":instance.sweep_width,"area_sum":sum(areas),"area_mean":mean(areas),
        "area_cv":pstdev(areas)/mean(areas),
        "unoriented_aspect_mean":mean(unoriented_aspect),"unoriented_aspect_std":pstdev(unoriented_aspect),
        "unoriented_aspect_min":min(unoriented_aspect),"unoriented_aspect_max":max(unoriented_aspect),
        "sweeps_h_mean":mean(h_sweeps),"sweeps_h_min":min(h_sweeps),"sweeps_h_max":max(h_sweeps),
        "sweeps_v_mean":mean(v_sweeps),"sweeps_v_min":min(v_sweeps),"sweeps_v_max":max(v_sweeps),
        "sweeps_h_odd_fraction":mean(n%2 for n in h_sweeps),"sweeps_v_odd_fraction":mean(n%2 for n in v_sweeps),
        "turning_h_mean":mean((n-1)*instance.turning_time for n in h_sweeps),
        "turning_v_mean":mean((n-1)*instance.turning_time for n in v_sweeps),
        "preferred_turning_share_mean":mean(t/p for t,p in zip(preferred_turns,minimum_processing)),
        "workload_cv":pstdev(minimum_processing)/mean(minimum_processing),
        "workload_max_to_mean":max(minimum_processing)/mean(minimum_processing),
        "workload_top10_fraction":sum(sorted(minimum_processing,reverse=True)[:max(1,math.ceil(.1*instance.task_count))])/coverage_pressure,
        "nearest_neighbor_manhattan_mean":mean(nearest),
        "travel_processing_pressure_ratio":(mean(pairwise_distances)/instance.travel_speed/mean(minimum_processing)) if pairwise_distances else 0.,
        "depot_processing_pressure_ratio":2*mean(distances)/instance.travel_speed/mean(minimum_processing),
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
    for spec in SANITY_FAMILY_MATRIX+STRUCTURAL_FAMILY_MATRIX:
        if spec.family_id == generated.family_id:
            return spec
    raise ValueError(f"unknown generated family: {generated.family_id}")


def generate_structural_instance(scenario: str, replicate_id: int) -> GeneratedInstance:
    """Paired scenarios share the BASE seed; replicates use independent hash seeds."""
    for spec in STRUCTURAL_FAMILY_MATRIX:
        if spec.structural_scenario==scenario:
            return generate_instance(spec,replicate_id,dataset_version=STRUCTURAL_VERSION)
    raise ValueError(f'unknown structural scenario: {scenario}')


def _generate_structural(spec,replicate_id,dataset_version):
    if dataset_version!=STRUCTURAL_VERSION:
        raise ValueError('use the explicit E10 structural dataset version')
    scenario=spec.structural_scenario
    seed=stable_generation_seed(dataset_version,'E10_BASE',replicate_id)
    rng=random.Random(seed)
    sides=[rng.choice((12.,15.,18.)) for _ in range(40)]
    dimensions={s:[(side,side) for side in sides] for s in STRUCTURAL_SCENARIOS}
    dimensions['HV-GEOM']=[(side*3,side/3) if k%2==0 else (side/3,side*3) for k,side in enumerate(sides)]
    # Four heavy tasks; all others lighter. Normalize total min(H,V) processing,
    # not area. Ceil discontinuities mean exact equality is generally impossible.
    heavy=set(rng.sample(range(40),4))
    raw=[side*(2.4 if k in heavy else .6)*rng.uniform(.97,1.03) for k,side in enumerate(sides)]
    target=sum(math.ceil(side/3)*side+(math.ceil(side/3)-1)*5 for side in sides)
    def total(scale):
        return sum(math.ceil(side*scale/3)*side*scale+(math.ceil(side*scale/3)-1)*5 for side in raw)
    lo,hi=.1,3.
    for _ in range(80):
        middle=(lo+hi)/2
        if total(middle)<target:lo=middle
        else:hi=middle
    factor=min((lo,hi),key=lambda x:abs(total(x)-target))
    dimensions['BOTTLENECK']=[(side*factor,side*factor) for side in raw]
    # Shared exclusion envelopes protect every paired geometry. Coordinates are
    # conditioned on all variants fitting; no solver outcome enters placement.
    envelopes=[(max(dimensions[s][k][0] for s in STRUCTURAL_SCENARIOS),
                max(dimensions[s][k][1] for s in STRUCTURAL_SCENARIOS)) for k in range(40)]
    centers=[];placed=[]
    for k,(width,height) in enumerate(envelopes):
        for _ in range(5000):
            x,y=_candidate_center('uniform',spec.coordinate_scale,k+1,40,rng)
            x,y=float(round(x)),float(round(y))
            rectangle=TaskRegion(k+1,x-width/2,y-height/2,x+width/2,y+height/2)
            if min(rectangle.x_left,rectangle.y_bottom)<0 or max(rectangle.x_right,rectangle.y_top)>spec.coordinate_scale:
                continue
            if all(not _overlaps(rectangle,other) for other in placed):
                centers.append((x,y));placed.append(rectangle);break
        else:raise RuntimeError('unable to place paired E10 exclusion envelopes')
    tasks=[]
    for k,((x,y),(width,height)) in enumerate(zip(centers,dimensions[scenario])):
        # Spatial-only stretching increases pairwise separation and depot travel;
        # it does not claim to isolate clustering or hold depot distance fixed.
        if scenario=='SPATIAL':x*=2
        tasks.append(TaskRegion(k+1,x-width/2,y-height/2,x+width/2,y+height/2))
    parameters=dict(sweep_width=3.,sweep_speed=1.,travel_speed=1.,turning_time=5.)
    if scenario=='TURN-HIGH':parameters['turning_time']=10.
    if scenario=='TRAVEL-HIGH':parameters['travel_speed']=.5
    if scenario=='SWEEP-NARROW':parameters['sweep_width']=2.
    instance=Instance(f'R4_T40_{replicate_id}',(0.,0.),4,tasks=tasks,rep_id=replicate_id,**parameters)
    config_hash=_hash_json(dict(dataset_version=dataset_version,generator_version=STRUCTURAL_GENERATOR_VERSION,
                               spec=asdict(spec),paired_seed=seed))
    return GeneratedInstance(instance,f'E10_{scenario}_r{replicate_id}',spec.family_id,'development',replicate_id,
                             seed,config_hash,dataset_version)


def _csv_table(path,rows):
    with Path(path).open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def _structural_checks(features):
    checks=[]
    by_id={(r['scenario'],r['replicate_id']):r for r in features}
    for rep in range(3):
        b=by_id['BASE',rep]
        comparisons=[('HV-GEOM','relative_hv_gap_mean',lambda x:x>b['relative_hv_gap_mean']+.15,'BASE + 0.15'),
            ('TURN-HIGH','preferred_turning_share_mean',lambda x:x>b['preferred_turning_share_mean']+.05,'BASE + 0.05'),
            ('TRAVEL-HIGH','travel_processing_pressure_ratio',lambda x:math.isclose(x,2*b['travel_processing_pressure_ratio']),'2 * BASE'),
            ('SWEEP-NARROW','sweeps_h_mean',lambda x:x>b['sweeps_h_mean'],'greater than BASE'),
            ('SWEEP-NARROW','mean_p_min',lambda x:x>b['mean_p_min'],'greater than BASE'),
            ('BOTTLENECK','workload_cv',lambda x:x>b['workload_cv']+.5,'BASE + 0.5'),
            ('BOTTLENECK','sum_p_min',lambda x:abs(x/b['sum_p_min']-1)<.02,'within 2% of BASE'),
            ('SPATIAL','pairwise_distance_mean',lambda x:x>b['pairwise_distance_mean']*1.2,'greater than 1.2 * BASE')]
        for scenario,metric,predicate,rule in comparisons:
            value=by_id[scenario,rep][metric]
            checks.append(dict(scenario=scenario,replicate_id=rep,metric=metric,value=value,base_value=b[metric],rule=rule,passed=predicate(value)))
    return checks


def build_structural_dataset(output_dir: str | Path) -> dict[str,Any]:
    """Write only a fresh dedicated directory, keeping R2 manifests/data untouched."""
    output=Path(output_dir)
    if output.exists() and any(output.iterdir()):raise FileExistsError(f'refusing to overwrite structural dataset: {output}')
    output.mkdir(parents=True,exist_ok=True)
    entries=[];features=[]
    for scenario in STRUCTURAL_SCENARIOS:
        for rep in range(3):
            generated=generate_structural_instance(scenario,rep)
            path=write_generated_instance(generated,output/scenario)
            instance=load_instance(path)
            assert instance==generate_structural_instance(scenario,rep).instance
            assert all(not _overlaps(a,b) for a,b in combinations(instance.tasks,2))
            assert min(min(t.x_left,t.y_bottom) for t in instance.tasks)>=0
            base=generate_structural_instance('BASE',rep).instance
            if scenario in ('TURN-HIGH','TRAVEL-HIGH','SWEEP-NARROW'):assert instance.tasks==base.tasks
            entry=dict(instance_id=generated.instance_id,instance_name=instance.name,scenario=scenario,split='development',
                replicate_id=rep,generation_seed=generated.generation_seed,base_pair_id=f'E10_BASE_r{rep}',
                file_path=path.relative_to(output).as_posix(),file_hash=hashlib.sha256(path.read_bytes()).hexdigest(),
                generation_config_hash=generated.generation_config_hash,
                geometry_hash=_hash_json([asdict(t) for t in instance.tasks]),
                n_tasks=40,n_robots=4,depot=[0.,0.],homogeneous=True,
                sweep_width=instance.sweep_width,sweep_speed=instance.sweep_speed,
                travel_speed=instance.travel_speed,turning_time=instance.turning_time)
            entries.append(entry)
            features.append(dict(instance_id=generated.instance_id,scenario=scenario,replicate_id=rep,
                **extract_intrinsic_features(instance)))
    checks=_structural_checks(features)
    if not all(c['passed'] for c in checks):raise ValueError('structural distinction failed; inspect generation rules')
    manifest=dict(dataset_version=STRUCTURAL_VERSION,generator_version=STRUCTURAL_GENERATOR_VERSION,
        instance_schema_version=INSTANCE_SCHEMA_VERSION,manifest_schema_version='mr-rcrp-structural-development-manifest-v1',
        split='development',entries=entries,
        pairing='Each replicate shares BASE geometry/seed; physical contrasts change only their named parameter.',
        seed_rule='stable_generation_seed(dataset_version, E10_BASE, replicate_id); shared within pair, independent across replicates',
        notes='Development-only initial model settings, not engineering calibration. Not the r2-sanity manifest schema. No held-out/final inputs.',
        source_specs=[asdict(s) for s in STRUCTURAL_FAMILY_MATRIX])
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    _csv_table(output/'structure_features.csv',features)
    summary=[]
    keys=[k for k,v in features[0].items() if isinstance(v,(int,float)) and k!='replicate_id']
    for scenario in STRUCTURAL_SCENARIOS:
        group=[r for r in features if r['scenario']==scenario]
        summary.append(dict(scenario=scenario,replicates=3,**{f'{k}_{stat}':fn(r[k] for r in group)
            for k in keys for stat,fn in (('mean',mean),('min',min),('max',max))}))
    _csv_table(output/'structure_summary.csv',summary)
    (output/'structure_checks.json').write_text(json.dumps(checks,indent=2)+'\n',encoding='utf-8')
    _structural_report(output,features,summary)
    return manifest


def _structural_report(output,features,summary):
    lines=['# E10 structural development dataset','',
        '21 instances, seven paired scenarios x three independent replicate seeds. R=4, T=40, depot=(0,0); every robot shares the instance parameters. Six-line TXT files round-trip through the production loader. No optimization score enters generation or labels.','',
        '| Scenario | Aspect max/min mean | Relative H/V gap | Preferred turning share | Mean H/V sweeps | Mean min processing | Workload CV | Pairwise Manhattan | Travel/work proxy |',
        '|---|---:|---:|---:|---|---:|---:|---:|---:|']
    for r in summary:
        lines.append(f"| {r['scenario']} | {r['unoriented_aspect_mean_mean']:.3f} | {r['relative_hv_gap_mean_mean']:.3f} | {r['preferred_turning_share_mean_mean']:.3f} | {r['sweeps_h_mean_mean']:.2f}/{r['sweeps_v_mean_mean']:.2f} | {r['mean_p_min_mean']:.2f} | {r['workload_cv_mean']:.3f} | {r['pairwise_distance_mean_mean']:.2f} | {r['travel_processing_pressure_ratio_mean']:.3f} |")
    lines+=['','## Design and actual controls','',
        '- BASE: independent uniformly sampled integer centers conditioned on non-overlapping shared exclusion envelopes; square sides sampled from 12/15/18. Square geometry is the deliberately neutral H/V reference. Placement is not an unconstrained spatial Poisson process.','- HV-GEOM: alternating 3x and 1/3x dimensions (aspect 9), preserves each area and center exactly. Perimeter, corner locations and discrete processing workloads change; it is not an isolated H/V-state intervention.','- SPATIAL: doubles center x only, retaining every dimension and all physical parameters. The layout is stretched; coordinate spans, separation and depot distances co-vary. It does not isolate clustering or hold depot travel fixed.','- BOTTLENECK: four enlarged square tasks and 36 smaller ones; scalar normalization targets BASE sum min(H,V) processing within 2%. Centers stay fixed; total area/perimeter and task dimensions are not fixed. Intrinsic workload imbalance does not prove any solver bottleneck.','- TURN-HIGH/TRAVEL-HIGH/SWEEP-NARROW: exact BASE task list, only turning_time=10 / travel_speed=0.5 / sweep_width=2 changes respectively. Other parameters remain 3/1/1/5.','',
        'All variants use shared exclusion envelopes during BASE placement so changed geometry fits without relocating centers. Non-overlap is strict in rectangle interiors; coordinates stay nonnegative. SPATIAL extends the x domain, intentionally.','',
        '## Definitions','',
        'H sweeps=ceil(height/sweep_width), V sweeps=ceil(width/sweep_width). Processing=passes*scan_length/sweep_speed+(passes-1)*turning_time. Relative H/V gap=abs(pH-pV)/max(pH,pV), matching the existing extractor. Preferred turning share uses the mode of minimum isolated processing; H wins exact ties. Workload CV=population std(p_min)/mean(p_min). Travel/work proxy=mean centroid pair Manhattan / travel_speed / mean(p_min); depot proxy=2*mean depot Manhattan / travel_speed / mean(p_min). These are intrinsic pressure proxies, not Route-DP route costs. Sweep parity fractions record potential exit-state changes, not observed optimized state transitions.','',
        'Every numerical feature has mean/min/max across three replicates in structure_summary.csv. structure_checks.json records per-replicate structural tests. No algorithm outcomes are used for those tests.','',
        '## Seeds and pairing','',
        '| Replicate | Shared geometry seed | BASE paired instances |','|---|---:|---|']
    for rep in range(3):lines.append(f"| {rep} | {stable_generation_seed(STRUCTURAL_VERSION,'E10_BASE',rep)} | all seven scenarios, replicate {rep} |")
    by={(r['scenario'],r['replicate_id']):r for r in features}
    lines+=['','| Replicate | HV area vs BASE | HV min-work change | BOTTLENECK area change | BOTTLENECK min-work change |','|---|---:|---:|---:|---:|']
    for rep in range(3):
        b=by['BASE',rep];h=by['HV-GEOM',rep];q=by['BOTTLENECK',rep]
        lines.append(f"| {rep} | {100*(h['area_sum']/b['area_sum']-1):+.3f}% | {100*(h['sum_p_min']/b['sum_p_min']-1):+.3f}% | {100*(q['area_sum']/b['area_sum']-1):+.3f}% | {100*(q['sum_p_min']/b['sum_p_min']-1):+.3f}% |")
    lines+=['','## Use and reproduce','',
        'All entries are development. These do not replace the 60 original main instances or r2_sanity. Existing held-out/final/lockbox data were not inputs. For future confirmation freeze this design first and use a new dataset version and independent seeds. Do not treat the three paired scenarios within one replicate as independent draws.','',
        '```powershell',"$env:PYTHONPATH='src'",
        "& 'G:\\Anaconda\\envs\\mrta_env\\python.exe' -m mrta_rect_coverage.experiments.dataset_protocol --structural-output data/e10_structural_development",
        '```','',
        'Existing nonempty output is refused. To reproduce bytes use a fresh --structural-output directory, then compare TXT hashes with manifest.json. The per-scenario subdirectories permit legacy R4_T40_0/1/2 names without changing the loader. Instance IDs must include scenario or relative path to avoid basename collisions.','',
        'Validation and a few optional short B1 runs are separate from generation; no LLM calls or method comparison is part of this dataset. These physical settings are development controls without engineering calibration.']
    (output/'STRUCTURE_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def validate_structural_dataset(dataset_dir: str | Path, output_dir: str | Path, *, smoke: bool = False) -> dict[str,Any]:
    """Validate the saved E10 development manifest; optional three short manual B1 runs."""
    import tempfile
    from ..core.cost_matrix import CostMatrix
    from ..core.dp_evaluator import RouteDPEvaluator
    from ..core.models import MultiRobotSolution
    from ..core.solution_evaluator import MultiRobotSolutionEvaluator
    root=Path(dataset_dir).resolve();output=Path(output_dir)
    manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    if manifest['dataset_version']!=STRUCTURAL_VERSION or manifest['split']!='development':
        raise ValueError('expected E10 development manifest')
    expected={(s,r) for s in STRUCTURAL_SCENARIOS for r in range(3)}
    if {(e['scenario'],e['replicate_id']) for e in manifest['entries']}!=expected or len(manifest['entries'])!=21:
        raise ValueError('incomplete structural manifest')
    complete=[];loaded={};state_count=0
    with tempfile.TemporaryDirectory(prefix='mr_rcrp_e10_reproduce_') as temporary:
        for e in manifest['entries']:
            path=(root/e['file_path']).resolve();path.relative_to(root)
            if hashlib.sha256(path.read_bytes()).hexdigest()!=e['file_hash']:raise ValueError(f'file hash mismatch: {path}')
            instance=load_instance(path);generated=generate_structural_instance(e['scenario'],e['replicate_id'])
            recreated=write_generated_instance(generated,Path(temporary)/e['scenario'])
            if path.read_bytes()!=recreated.read_bytes():raise ValueError('seed reproduction mismatch')
            assert instance==generated.instance and instance.task_count==40 and instance.robot_count==4
            assert e['generation_seed']==generated.generation_seed and e['generation_config_hash']==generated.generation_config_hash
            assert e['geometry_hash']==_hash_json([asdict(t) for t in instance.tasks])
            assert e['split']=='development' and e['homogeneous'] is True and e['depot']==[0.,0.]
            assert all(math.isfinite(v) for t in instance.tasks for v in (t.x_left,t.x_right,t.y_bottom,t.y_top))
            assert all(t.width>0 and t.height>0 and min(t.x_left,t.y_bottom)>=0 for t in instance.tasks)
            assert all(not _overlaps(a,b) for a,b in combinations(instance.tasks,2))
            for key in ('sweep_width','sweep_speed','travel_speed','turning_time'):assert getattr(instance,key)==e[key]
            states=generate_all_states(instance)
            assert all(len(s)==8 for s in states.values());state_count+=sum(map(len,states.values()))
            costs=CostMatrix(instance.depot,states,travel_speed=instance.travel_speed)
            evaluator=MultiRobotSolutionEvaluator(RouteDPEvaluator(costs,states),instance=instance)
            routes=[[t.task_id for t in instance.tasks][r::4] for r in range(4)]
            solution=MultiRobotSolution(routes);evaluation=evaluator.evaluate(solution)
            assert math.isfinite(evaluation.makespan) and evaluation.makespan>0
            assert all(len(r.chosen_states)==len(r.route_task_ids) for r in evaluation.route_evaluations)
            complete.append(dict(instance_id=e['instance_id'],routes=routes,makespan=evaluation.makespan,
                per_robot_costs=evaluation.per_robot_costs,feasible=True,purpose='fixed round-robin evaluator compatibility, not an algorithm result'))
            loaded[e['scenario'],e['replicate_id']]=instance
    paired=[]
    for rep in range(3):
        base=loaded['BASE',rep]
        for scenario,param in (('TURN-HIGH','turning_time'),('TRAVEL-HIGH','travel_speed'),('SWEEP-NARROW','sweep_width')):
            other=loaded[scenario,rep]
            assert other.tasks==base.tasks
            assert [k for k in asdict(base) if asdict(base)[k]!=asdict(other)[k]]==[param]
            paired.append(dict(base=f'E10_BASE_r{rep}',contrast=f'E10_{scenario}_r{rep}',only_changed_parameter=param,exact_same_tasks=True))
    features=[dict(instance_id=f'E10_{s}_r{r}',scenario=s,replicate_id=r,**extract_intrinsic_features(i)) for (s,r),i in loaded.items()]
    checks=_structural_checks(features);assert all(c['passed'] for c in checks)
    smoke_runs=[]
    if smoke:
        from ..heuristics.alns_solver import ALNSSolver, ALNSConfig
        for scenario in ('BASE','HV-GEOM','SWEEP-NARROW'):
            instance=loaded[scenario,0]
            config=ALNSConfig.enhanced(max_runtime_seconds=2.,random_seed=0)
            solver=ALNSSolver(instance,constructor='spatial_sort',config=config)
            result=solver.solve();verified=solver.solution_evaluator.evaluate(result.best_solution)
            assert verified.makespan==result.best_evaluation.makespan and not result.fallback_events
            smoke_runs.append(dict(instance_id=f'E10_{scenario}_r0',config=asdict(config),constructor='spatial_sort',
                feasible=True,best_routes=result.best_solution.routes,makespan=verified.makespan,
                per_robot_costs=verified.per_robot_costs,runtime_seconds=result.runtime_seconds,
                iterations=result.iterations_completed,route_dp_calls=result.route_dp_calls,
                route_dp_cache_misses=result.route_dp_cache_misses,fallback_count=len(result.fallback_events),
                history=result.iteration_history,purpose='compatibility smoke only; not method comparison'))
    output.mkdir(parents=True,exist_ok=True)
    result=dict(dataset_version=STRUCTURAL_VERSION,split='development',loaded_instances=21,reproducible_txt_files=21,
        exact_dp_complete_evaluations=21,state_count=state_count,nonoverlapping_positive_rectangles=True,
        physical_pair_checks=paired,structural_checks=checks,homogeneous_robots=True,
        seed_rule=manifest['seed_rule'],b1_smoke_runs=smoke_runs,llm_calls=0,
        model_unchanged=True,final_or_heldout_inputs_used=False)
    (output/'validation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    (output/'fixed_dp_compatibility.json').write_text(json.dumps(complete,indent=2)+'\n',encoding='utf-8')
    return result


__all__ = [
    "DATASET_VERSION", "GENERATOR_VERSION", "INSTANCE_SCHEMA_VERSION", "MANIFEST_SCHEMA_VERSION", "NEAR_TIE_THRESHOLD",
    "FamilySpec", "GeneratedInstance", "SANITY_FAMILY_MATRIX", "stable_generation_seed", "generate_instance",
    "write_generated_instance", "extract_intrinsic_features", "write_manifest", "load_manifest", "load_manifest_instances",
    "build_sanity_dataset",
    "STRUCTURAL_SCENARIOS", "STRUCTURAL_FAMILY_MATRIX", "generate_structural_instance", "build_structural_dataset", "validate_structural_dataset",
]


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    action=parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--structural-output',type=Path)
    action.add_argument('--validate-structural',type=Path)
    parser.add_argument('--validation-output',type=Path,default=Path('outputs/e10_structural_development'))
    parser.add_argument('--smoke',action='store_true',help='Run three 2-second manual B1 feasibility smokes only')
    args=parser.parse_args()
    if args.structural_output:
        if args.smoke:parser.error('--smoke requires --validate-structural')
        result=build_structural_dataset(args.structural_output)
        print(f"Wrote {len(result['entries'])} development instances to {args.structural_output}")
    else:
        result=validate_structural_dataset(args.validate_structural,args.validation_output,smoke=args.smoke)
        print(f"Validated {result['loaded_instances']} instances, {result['state_count']} states and {len(result['b1_smoke_runs'])} B1 smokes")
