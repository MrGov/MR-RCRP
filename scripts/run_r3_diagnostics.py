from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from time import perf_counter


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mrta_rect_coverage.core.instance_loader import load_instance, parse_instance_filename
from mrta_rect_coverage.experiments.dataset_protocol import (
    extract_intrinsic_features,
    load_manifest,
    load_manifest_instances,
)
from mrta_rect_coverage.experiments.r3_diagnostics import run_diagnostic_alns
from mrta_rect_coverage.heuristics.alns_solver import ALNSConfig
from mrta_rect_coverage.heuristics.baseline_solver import baseline_solve


def main() -> None:
    parser = argparse.ArgumentParser(description="Run built-in-only R3 diagnostics")
    parser.add_argument(
        "--mode",
        required=True,
        choices=("track-a", "track-b-development", "held-out"),
    )
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    output_root = PROJECT_ROOT / "outputs" / "r3_diagnostics" / "raw"
    output_root.mkdir(parents=True, exist_ok=True)
    run_path = output_root / f"{args.mode}_runs.json"
    instance_path = output_root / f"{args.mode}_instances.json"
    if not args.overwrite and (run_path.exists() or instance_path.exists()):
        raise FileExistsError("R3 raw output exists; pass --overwrite to replace it")

    if args.mode == "track-a":
        records = _track_a_records()
        selected = [row for row in records if row["replicate_id"] == 0]
    else:
        split = "development" if args.mode == "track-b-development" else "held-out"
        records = _manifest_records(split)
        selected = records

    instance_rows = [_instance_row(row) for row in records]
    runs: list[dict] = []
    for record in selected:
        instance = record["instance"]
        baseline_started = perf_counter()
        _, baseline_evaluation = baseline_solve(
            instance,
            enable_local_search=True,
            max_iterations=20,
        )
        baseline_runtime = perf_counter() - baseline_started
        seeds = range(3 if instance.task_count >= 60 or args.mode == "held-out" else 5)
        for seed in seeds:
            print(
                f"START {args.mode} {record['instance_id']} seed={seed}",
                flush=True,
            )
            run = run_diagnostic_alns(
                instance,
                source_track=record["source_track"],
                family_id=record["family_id"],
                config=ALNSConfig(
                    iterations=args.iterations,
                    destroy_fraction=0.25,
                    acceptance="simulated_annealing",
                    random_seed=seed,
                    frozen_operator_registry_path=None,
                    use_frozen_repair=False,
                    use_frozen_destroy=False,
                ),
            )
            run["baseline_makespan"] = baseline_evaluation.makespan
            run["baseline_runtime_sec"] = baseline_runtime
            run["instance_path"] = record["file_path"]
            runs.append(run)
            print(
                f"DONE {run['run_id']} best={run['best_makespan']:.6f} "
                f"runtime={run['runtime_sec']:.3f}",
                flush=True,
            )

    run_path.write_text(
        json.dumps(runs, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    serializable_rows = [
        {key: value for key, value in row.items() if key != "instance"}
        for row in instance_rows
    ]
    instance_path.write_text(
        json.dumps(serializable_rows, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(f"COMPLETE mode={args.mode} runs={len(runs)} instances={len(records)}")


def _track_a_records() -> list[dict]:
    final_manifest = load_manifest(
        PROJECT_ROOT / "manifests" / "r2-sanity-v1_final.json",
        expected_split="final",
    )
    final_paths = {
        (PROJECT_ROOT / entry["file_path"]).resolve()
        for entry in final_manifest["entries"]
    }
    records = []
    for path in (PROJECT_ROOT / "data").glob("R*_T*_*.txt"):
        if path.resolve() in final_paths:
            continue
        robots, tasks, replicate = parse_instance_filename(path)
        instance = load_instance(path)
        records.append(
            {
                "instance": instance,
                "instance_id": instance.name,
                "source_track": "A",
                "family_id": None,
                "replicate_id": replicate,
                "n_robots": robots,
                "n_tasks": tasks,
                "file_path": path.relative_to(PROJECT_ROOT).as_posix(),
            }
        )
    return sorted(
        records,
        key=lambda row: (row["n_tasks"], row["n_robots"], row["replicate_id"]),
    )


def _manifest_records(split: str) -> list[dict]:
    manifest_path = (
        PROJECT_ROOT / "manifests" / f"r2-sanity-v1_{split}.json"
    )
    manifest = load_manifest(manifest_path, expected_split=split)
    instances = load_manifest_instances(manifest_path, expected_split=split)
    records = []
    for entry, instance in zip(manifest["entries"], instances):
        records.append(
            {
                "instance": instance,
                "instance_id": entry["instance_id"],
                "source_track": f"B-{split}",
                "family_id": entry["family_id"],
                "replicate_id": entry["replicate_id"],
                "n_robots": entry["n_robots"],
                "n_tasks": entry["n_tasks"],
                "file_path": entry["file_path"],
                "geometry_regime": entry["geometry_regime"],
                "spatial_regime": entry["spatial_regime"],
                "travel_coverage_regime": entry["travel_coverage_regime"],
                "hv_sensitivity_regime": entry["hv_sensitivity_regime"],
                "load_regime": entry["load_regime"],
            }
        )
    return records


def _instance_row(record: dict) -> dict:
    instance = record["instance"]
    return {
        key: value
        for key, value in {
            "diagnostic_schema_version": "r3-diagnostics-v1",
            "instance_id": record["instance_id"],
            "source_track": record["source_track"],
            "family_id": record["family_id"],
            "replicate_id": record["replicate_id"],
            "file_path": record["file_path"],
            "sweep_width": instance.sweep_width,
            "sweep_speed": instance.sweep_speed,
            "travel_speed": instance.travel_speed,
            "turning_time": instance.turning_time,
            "geometry_regime": record.get("geometry_regime"),
            "spatial_regime": record.get("spatial_regime"),
            "travel_coverage_regime": record.get("travel_coverage_regime"),
            "hv_sensitivity_regime": record.get("hv_sensitivity_regime"),
            "load_regime": record.get("load_regime"),
            **extract_intrinsic_features(instance),
        }.items()
    }


if __name__ == "__main__":
    main()
