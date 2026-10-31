"""E15: runtime calibration of the iteration-cost reference used by P1 penalties.

The reference feeds ``ALNSConfig.iteration_cost_reference_seconds``:

    factor = min(1.0, sqrt(t_ref / measured_stage_seconds))

A machine-bound absolute constant is not reproducible, so ``t_ref`` is never
hard-coded: it is measured here on this machine, from a deterministic pilot.

Why the unit is "one typical iteration", not "one route DP evaluation"
---------------------------------------------------------------------
A cold-cache ``evaluate_route`` call is a poor unit: on the structural
development set one full ALNS iteration costs ~50x that on a 6-task instance and
~110x that on a 40-task instance, because an iteration is dominated by repair
(greedy insertion over many DP calls) and local search, not by a single DP
table. Calibrating ``t_ref`` from the probe therefore makes the factor a
near-constant shrink of every reward -- which, being common to all operators,
cannot change operator ranking at all. The pilot below measures the iteration
itself instead, so ``kappa = 1.0`` means "a median iteration is credited in
full and only visibly expensive iterations are discounted".

Usage:
    python -m mrta_rect_coverage.experiments.e15_cost_penalty_calibration --stage calibrate
    python -m mrta_rect_coverage.experiments.e15_cost_penalty_calibration --stage verify
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
from time import perf_counter

from ..core.cost_matrix import CostMatrix
from ..core.dp_evaluator import RouteDPEvaluator
from ..core.instance_loader import load_instance
from ..core.state_generator import generate_all_states
from ..heuristics.alns_solver import ALNSConfig, ALNSSolver

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = ROOT / "outputs/e15_cost_penalty_calibration"
STRUCTURAL_DATA = ROOT / "data/e10_structural_development"
DEFAULT_PROBE_INSTANCE = ROOT / "data/R2_T6_0.txt"
DEFAULT_PILOT_INSTANCES = (
    "BASE:0",
    "BOTTLENECK:0",
    "HV-GEOM:0",
    "SPATIAL:0",
    "SWEEP-NARROW:0",
    "TRAVEL-HIGH:0",
    "TURN-HIGH:0",
)
PILOT_ITERATIONS = 40
PILOT_SEED = 0
DEFAULT_KAPPA = 1.0
CALIBRATION_TOL = 1e-12


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git_head() -> str:
    for executable in ("git", r"C:\Program Files\Git\cmd\git.exe"):
        try:
            return subprocess.run(
                [executable, "rev-parse", "HEAD"], cwd=ROOT, check=True,
                capture_output=True, text=True
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            continue
    return "unavailable"


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _instance_path(instance_id: str) -> Path:
    family, _, repeat = instance_id.partition(":")
    if not repeat:
        raise SystemExit(f"instance id must look like 'FAMILY:repeat', got {instance_id!r}")
    return STRUCTURAL_DATA / family / f"R4_T40_{repeat}.txt"


def build_evaluator(instance):
    states = generate_all_states(instance)
    cost_matrix = CostMatrix(
        instance.depot, states, travel_speed=instance.travel_speed
    )
    route_dp = RouteDPEvaluator(cost_matrix, states)
    return states, cost_matrix, route_dp


def pinned_route(instance) -> list[int]:
    """A fixed, instance-independent route: tasks in loader order."""
    return [task.task_id for task in instance.tasks]


def measure_probe_seconds(
    route_dp: RouteDPEvaluator, route: list[int], *, repeats: int
) -> list[float]:
    """Cold-cache cost of one pinned route evaluation, measured ``repeats`` times."""
    route_dp._cache.clear()
    route_dp.evaluate_route(route)  # warm-up: caches, imports, first-call costs
    samples: list[float] = []
    for _ in range(repeats):
        route_dp._cache.clear()
        started = perf_counter()
        route_dp.evaluate_route(route)
        samples.append(perf_counter() - started)
    return samples


def measure_iteration_seconds(
    instance_path: Path, *, iterations: int = PILOT_ITERATIONS, seed: int = PILOT_SEED
) -> list[float]:
    """Deterministic pilot: the wall-clock cost of ``iterations`` real ALNS steps."""
    instance = load_instance(instance_path)
    config = ALNSConfig.enhanced(
        iterations=iterations, random_seed=seed, cooling_schedule="iteration"
    )
    result = ALNSSolver(instance, config=config).solve()
    return [row["measured_stage_seconds"] for row in result.iteration_history]


def stage_calibrate(
    output: Path, *, probe_instance: Path, pilot_instances: tuple[str, ...],
    repeats: int, kappa: float,
) -> dict:
    if repeats < 3:
        raise ValueError("repeats must be >= 3 for a meaningful median")
    if not (kappa > 0):
        raise ValueError("kappa must be positive")

    probe_instance_obj = load_instance(probe_instance)
    _, _, probe_dp = build_evaluator(probe_instance_obj)
    probe_route = pinned_route(probe_instance_obj)
    probe_samples = measure_probe_seconds(probe_dp, probe_route, repeats=repeats)
    t_probe = statistics.median(probe_samples)

    per_instance: dict[str, dict] = {}
    pooled: list[float] = []
    for instance_id in pilot_instances:
        path = _instance_path(instance_id)
        samples = measure_iteration_seconds(path)
        if not samples:
            raise SystemExit(f"pilot produced no iterations for {instance_id}")
        pooled.extend(samples)
        per_instance[instance_id] = {
            "iterations": len(samples),
            "median_seconds": statistics.median(samples),
            "mean_seconds": statistics.mean(samples),
            "min_seconds": min(samples),
            "max_seconds": max(samples),
        }

    t_iter = statistics.median(pooled)
    record = {
        "git_head": _git_head(),
        "python": sys.version.split()[0],
        "calibration_unit": "alns_iteration",
        "probe_instance": str(probe_instance.relative_to(ROOT)),
        "probe_route": probe_route,
        "probe_repeats": repeats,
        "t_probe_seconds": t_probe,
        "pilot_instances": list(pilot_instances),
        "pilot_iterations": PILOT_ITERATIONS,
        "pilot_seed": PILOT_SEED,
        "per_instance": per_instance,
        "pooled_sample_count": len(pooled),
        "t_iteration_median_seconds": t_iter,
        "t_iteration_mean_seconds": statistics.mean(pooled),
        "t_iteration_max_seconds": max(pooled),
        "probe_units_per_iteration": t_iter / t_probe,
        "kappa": kappa,
        "t_ref_seconds": kappa * t_iter,
        "machine_fingerprint": {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "created_at_utc": _utc_now(),
        "note": (
            "t_ref = kappa * median measured_stage_seconds of a deterministic "
            "pilot on THIS machine. A median iteration gets factor 1.0; only "
            "iterations slower than that are discounted. Re-run --stage "
            "calibrate on another machine before comparing wall-clock budgets."
        ),
    }
    _write_json(output / "calibration.json", record)
    print(json.dumps(
        {key: record[key] for key in
         ("t_iteration_median_seconds", "probe_units_per_iteration", "kappa",
          "t_ref_seconds", "created_at_utc")},
        indent=2, sort_keys=True,
    ))
    return record


def stage_verify(output: Path) -> dict:
    path = output / "calibration.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    problems: list[str] = []

    kappa = record["kappa"]
    t_iter = record["t_iteration_median_seconds"]
    t_ref = record["t_ref_seconds"]

    if abs(kappa * t_iter - t_ref) > CALIBRATION_TOL:
        problems.append("t_ref_seconds != kappa * t_iteration_median_seconds")
    if not (t_ref > 0):
        problems.append("t_ref_seconds must be positive")
    if record.get("pooled_sample_count", 0) < PILOT_ITERATIONS:
        problems.append("pilot produced fewer samples than one full iteration run")
    for instance_id in record.get("pilot_instances", []):
        entry = record.get("per_instance", {}).get(instance_id)
        if not entry or entry["iterations"] != PILOT_ITERATIONS:
            problems.append(f"missing or short pilot entry for {instance_id}")
    for key in ("git_head", "probe_instance", "machine_fingerprint",
                "created_at_utc", "calibration_unit"):
        if not record.get(key):
            problems.append(f"missing calibration field: {key}")

    summary = {
        "calibration_file": str(path),
        "calibration_unit": record.get("calibration_unit"),
        "t_iteration_median_seconds": t_iter,
        "kappa": kappa,
        "t_ref_seconds": t_ref,
        "pilot_instance_count": len(record.get("pilot_instances", [])),
        "problems": problems,
    }
    _write_json(output / "verify_summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    if problems:
        raise SystemExit(1)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("calibrate", "verify"), required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--probe-instance", type=Path, default=DEFAULT_PROBE_INSTANCE)
    parser.add_argument("--pilot-instances", nargs="+",
                        default=list(DEFAULT_PILOT_INSTANCES))
    parser.add_argument("--repeats", type=int, default=20)
    parser.add_argument("--kappa", type=float, default=DEFAULT_KAPPA)
    args = parser.parse_args()
    output = args.output.resolve()
    if args.stage == "calibrate":
        stage_calibrate(
            output,
            probe_instance=args.probe_instance.resolve(),
            pilot_instances=tuple(args.pilot_instances),
            repeats=args.repeats,
            kappa=args.kappa,
        )
    else:
        stage_verify(output)


if __name__ == "__main__":
    main()
