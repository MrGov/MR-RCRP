"""E15: runtime calibration of the iteration-cost reference used by P1 penalties.

The reference time ``t_ref`` feeds ``ALNSConfig.iteration_cost_reference_seconds``:

    factor = min(1.0, sqrt(t_ref / measured_stage_seconds))

A machine-bound absolute constant is not reproducible, so ``t_ref`` is never
hard-coded: this script measures the cost of one pinned route evaluation and
scales it by the pre-registered ``kappa``.

Usage:
    python -m mrta_rect_coverage.experiments.e15_cost_penalty_calibration --stage calibrate
    python -m mrta_rect_coverage.experiments.e15_cost_penalty_calibration --stage verify
"""
from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path
import statistics
import subprocess
import sys
from time import perf_counter

from ..core.cost_matrix import CostMatrix
from ..core.dp_evaluator import RouteDPEvaluator
from ..core.instance_loader import load_instance
from ..core.state_generator import generate_all_states

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = ROOT / "outputs/e15_cost_penalty_calibration"
DEFAULT_INSTANCE = ROOT / "data/R2_T6_0.txt"
DEFAULT_REPEATS = 20
DEFAULT_KAPPA = 8.0
CALIBRATION_TOL = 1e-12


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
    """Cold-cache cost of evaluating one pinned route, measured ``repeats`` times."""
    route_dp._cache.clear()
    route_dp.evaluate_route(route)  # warm-up: caches, imports, first-call costs
    samples: list[float] = []
    for _ in range(repeats):
        route_dp._cache.clear()
        started = perf_counter()
        route_dp.evaluate_route(route)
        samples.append(perf_counter() - started)
    return samples


def stage_calibrate(
    output: Path, *, instance_path: Path, repeats: int, kappa: float
) -> dict:
    if repeats < 3:
        raise ValueError("repeats must be >= 3 for a meaningful median")
    if not (kappa > 0):
        raise ValueError("kappa must be positive")
    instance = load_instance(instance_path)
    _, _, route_dp = build_evaluator(instance)
    route = pinned_route(instance)
    samples = measure_probe_seconds(route_dp, route, repeats=repeats)
    t_probe = statistics.median(samples)
    record = {
        "git_head": _git_head(),
        "python": sys.version.split()[0],
        "instance": instance_path.stem,
        "route": route,
        "repeats": repeats,
        "t_probe_seconds": t_probe,
        "kappa": kappa,
        "t_ref_seconds": kappa * t_probe,
        "samples_seconds": samples,
        "machine_fingerprint": {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "created_at_utc": _utc_now(),
        "note": (
            "t_ref is calibrated on THIS machine; re-run --stage calibrate "
            "elsewhere before comparing wall-clock-budgeted runs."
        ),
    }
    _write_json(output / "calibration.json", record)
    print(json.dumps(
        {key: record[key] for key in
         ("instance", "repeats", "t_probe_seconds", "kappa", "t_ref_seconds", "created_at_utc")},
        indent=2, sort_keys=True,
    ))
    return record


def _utc_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def stage_verify(output: Path) -> dict:
    path = output / "calibration.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    problems: list[str] = []

    samples = record.get("samples_seconds") or []
    t_probe = record["t_probe_seconds"]
    kappa = record["kappa"]
    t_ref = record["t_ref_seconds"]

    if len(samples) != record["repeats"]:
        problems.append(
            f"sample count {len(samples)} != repeats {record['repeats']}"
        )
    if samples and abs(statistics.median(samples) - t_probe) > CALIBRATION_TOL:
        problems.append("t_probe_seconds is not the median of samples_seconds")
    if abs(kappa * t_probe - t_ref) > CALIBRATION_TOL:
        problems.append("t_ref_seconds != kappa * t_probe_seconds")
    if not (t_ref > 0):
        problems.append("t_ref_seconds must be positive")
    for key in ("git_head", "instance", "route", "machine_fingerprint", "created_at_utc"):
        if not record.get(key):
            problems.append(f"missing calibration field: {key}")

    summary = {
        "calibration_file": str(path),
        "instance": record.get("instance"),
        "t_probe_seconds": t_probe,
        "kappa": kappa,
        "t_ref_seconds": t_ref,
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
    parser.add_argument("--instance", type=Path, default=DEFAULT_INSTANCE)
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    parser.add_argument("--kappa", type=float, default=DEFAULT_KAPPA)
    args = parser.parse_args()
    output = args.output.resolve()
    if args.stage == "calibrate":
        stage_calibrate(
            output,
            instance_path=args.instance.resolve(),
            repeats=args.repeats,
            kappa=args.kappa,
        )
    else:
        stage_verify(output)


if __name__ == "__main__":
    main()
