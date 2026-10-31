"""E14: read-only state-chain and state-regret instrumentation."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import time
import sys

from ..core.cost_matrix import CostMatrix
from ..core.dp_evaluator import RouteDPEvaluator
from ..core.instance_loader import load_instance
from ..core.models import MultiRobotSolution
from ..core.solution_evaluator import MultiRobotSolutionEvaluator
from ..core.state_chain_report import assert_report_consistent, solution_state_report
from ..core.state_generator import generate_all_states
from ..llm.operator_evolution.regime_labeler import (
    label_regime,
    large_gap_share,
    route_cost_shares,
)

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = ROOT / "outputs/e14_state_regret_instrument"
E10B_OUTPUT = ROOT / "outputs/e10b_structural_dp_analysis"
STRUCTURAL_DATA = ROOT / "data/e10_structural_development"
V1_DATA = ROOT / "data/structural_benchmark_v1"
V1_MANIFEST = V1_DATA / "manifest.json"


def evaluator_for(instance):
    states = generate_all_states(instance)
    cost_matrix = CostMatrix(
        instance.depot, states, travel_speed=instance.travel_speed
    )
    route_dp = RouteDPEvaluator(cost_matrix, states)
    return states, cost_matrix, MultiRobotSolutionEvaluator(route_dp, instance=instance)


def round_robin_solution(instance) -> MultiRobotSolution:
    routes = [[] for _ in range(instance.robot_count)]
    for index, task in enumerate(instance.tasks):
        routes[index % instance.robot_count].append(task.task_id)
    return MultiRobotSolution(routes=routes)


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _solution_hash(solution: MultiRobotSolution) -> str:
    payload = json.dumps(solution.routes, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


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


def stage_smoke(output: Path, *, near_tie_tol: float = 0.0) -> None:
    instance = load_instance(ROOT / "data/R2_T6_0.txt")
    states, cost_matrix, evaluator = evaluator_for(instance)
    solution = round_robin_solution(instance)
    evaluation = evaluator.evaluate(solution)
    route_dp = evaluator.route_evaluator
    before = route_dp.statistics()
    report = solution_state_report(
        instance,
        solution,
        evaluation,
        states_by_task=states,
        cost_matrix=cost_matrix,
        solution_hash=_solution_hash(solution),
        near_tie_tol=near_tie_tol,
    )
    after = route_dp.statistics()
    if before["calls"] != after["calls"] or before["cache_misses"] != after["cache_misses"]:
        raise AssertionError("report generation changed Route-DP statistics")
    assert_report_consistent(report)
    report["dp_statistics_before"] = before
    report["dp_statistics_after"] = after
    report["near_tie_tol"] = near_tie_tol
    _write_json(output / "smoke" / f"{instance.name}.json", report)
    _write_json(
        output / "meta.json",
        {
            "git_head": _git_head(),
            "python": sys.version,
            "near_tie_tol": near_tie_tol,
            "dp_statistics_before": before,
            "dp_statistics_after": after,
        },
    )


def stage_parents(output: Path, *, near_tie_tol: float = 0.0) -> None:
    input_dir = E10B_OUTPUT / "inputs"
    inputs = sorted(input_dir.glob("*.json")) if input_dir.is_dir() else []
    if not inputs:
        raise SystemExit("run e10b --stage prepare first")
    for input_path in inputs:
        record = json.loads(input_path.read_text(encoding="utf-8"))
        instance_id = record.get("instance_id")
        entry = record.get("entry", {})
        relative_path = entry.get("file_path")
        if not instance_id or not relative_path or not record.get("parent_routes"):
            raise ValueError(f"incomplete parent input: {input_path}")
        instance_path = STRUCTURAL_DATA / relative_path
        instance = load_instance(instance_path)
        instance.name = instance_id
        states, cost_matrix, evaluator = evaluator_for(instance)
        solution = MultiRobotSolution(
            routes=[list(route) for route in record["parent_routes"]]
        )
        route_dp = evaluator.route_evaluator
        before = route_dp.statistics()
        evaluation = evaluator.evaluate(solution)
        after_evaluation = route_dp.statistics()
        report = solution_state_report(
            instance,
            solution,
            evaluation,
            states_by_task=states,
            cost_matrix=cost_matrix,
            solution_hash=record.get("parent_hash") or _solution_hash(solution),
            near_tie_tol=near_tie_tol,
        )
        after_report = route_dp.statistics()
        if before["calls"] >= after_evaluation["calls"]:
            raise AssertionError(f"parent evaluation did not call Route-DP for {instance_id}")
        if after_evaluation["calls"] != after_report["calls"]:
            raise AssertionError(f"report re-entered Route-DP for {instance_id}")
        if after_evaluation["cache_misses"] != after_report["cache_misses"]:
            raise AssertionError(f"report changed DP cache misses for {instance_id}")
        assert_report_consistent(report)
        report.update(
            {
                "input_id": record.get("input_id"),
                "fixed_destroy_hash": record.get("fixed_destroy_hash"),
                "parent_routes": solution.routes,
                "parent_label": record.get("parent_label") or "E10-B fixed parent",
                "near_tie_tol": near_tie_tol,
                "dp_statistics_before": after_evaluation,
                "dp_statistics_after": after_report,
            }
        )
        _write_json(output / "parents" / f"{instance_id}.json", report)


def _instance_index() -> dict:
    """Map ``instance_id -> relative instance path`` from the e10b prepare stage."""
    input_dir = E10B_OUTPUT / "inputs"
    inputs = sorted(input_dir.glob("*.json")) if input_dir.is_dir() else []
    if not inputs:
        raise SystemExit("run e10b --stage prepare first")
    index = {}
    for input_path in inputs:
        record = json.loads(input_path.read_text(encoding="utf-8"))
        instance_id = record.get("instance_id")
        entry = record.get("entry") or {}
        relative_path = entry.get("file_path")
        if instance_id and relative_path:
            index[instance_id] = relative_path
    return index


def _record_to_solution(record: dict) -> MultiRobotSolution:
    """Adapt one solutions-JSON record to a solution; the only schema adapter."""
    routes = record.get("routes")
    if routes is None:
        routes = record.get("solution_routes")
    if routes is None:
        raise ValueError(
            f"solutions record {record.get('label')!r} has no 'routes' field"
        )
    return MultiRobotSolution(routes=[list(route) for route in routes])


def stage_solutions(
    output: Path,
    *,
    solutions_path: Path,
    instance_root: Path = STRUCTURAL_DATA,
    near_tie_tol: float = 0.0,
) -> None:
    """Build state reports for externally produced solutions (P2 child evidence).

    Read-only with respect to Route-DP: the report must not re-enter the
    evaluator or change its cache statistics.
    """
    records = json.loads(solutions_path.read_text(encoding="utf-8"))
    if isinstance(records, dict):
        records = records.get("solutions", [])
    if not records:
        raise SystemExit(f"no solution records in {solutions_path}")
    index = _instance_index()
    missing = sorted(
        {
            str(record.get("instance_id"))
            for record in records
            if str(record.get("instance_id")) not in index
        }
    )
    if missing:
        raise SystemExit(f"unknown instance_id(s): {', '.join(missing)}")
    for record in records:
        instance_id = str(record["instance_id"])
        label = str(record.get("label") or "solution")
        instance = load_instance(instance_root / index[instance_id])
        instance.name = instance_id
        states, cost_matrix, evaluator = evaluator_for(instance)
        solution = _record_to_solution(record)
        route_dp = evaluator.route_evaluator
        before = route_dp.statistics()
        evaluation = evaluator.evaluate(solution)
        after_evaluation = route_dp.statistics()
        report = solution_state_report(
            instance,
            solution,
            evaluation,
            states_by_task=states,
            cost_matrix=cost_matrix,
            solution_hash=record.get("solution_hash") or _solution_hash(solution),
            near_tie_tol=near_tie_tol,
        )
        after_report = route_dp.statistics()
        if before["calls"] >= after_evaluation["calls"]:
            raise AssertionError(
                f"solution evaluation did not call Route-DP for {instance_id}__{label}"
            )
        if after_evaluation["calls"] != after_report["calls"]:
            raise AssertionError(
                f"report re-entered Route-DP for {instance_id}__{label}"
            )
        if after_evaluation["cache_misses"] != after_report["cache_misses"]:
            raise AssertionError(
                f"report changed DP cache misses for {instance_id}__{label}"
            )
        assert_report_consistent(report)
        report.update(
            {
                "input_id": record.get("input_id"),
                "fixed_destroy_hash": record.get("fixed_destroy_hash"),
                "solver_seed": record.get("solver_seed"),
                "label": label,
                "solution_routes": solution.routes,
                "near_tie_tol": near_tie_tol,
                "dp_statistics_before": after_evaluation,
                "dp_statistics_after": after_report,
            }
        )
        _write_json(output / "solutions" / f"{instance_id}__{label}.json", report)


def dataset_entries(dataset: str, split: str) -> list[dict]:
    """Return manifest entries for ``dataset``/``split`` (round-robin parents)."""
    if dataset != "v1":
        raise ValueError(f"unsupported dataset: {dataset!r} (expected 'v1')")
    if not V1_MANIFEST.is_file():
        raise SystemExit(f"missing manifest: {V1_MANIFEST}")
    manifest = json.loads(V1_MANIFEST.read_text(encoding="utf-8"))
    entries = [entry for entry in manifest.get("entries", []) if entry.get("split") == split]
    if not entries:
        raise ValueError(f"no entries for split {split!r} in {V1_MANIFEST}")
    return sorted(entries, key=lambda entry: entry["instance_id"])


def _sanitize(instance_id: str) -> str:
    return instance_id.replace("/", "__")


def _instance_summary(report: dict) -> dict:
    """Per-instance summary built only from frozen helpers (no new metrics)."""
    makespan = report["makespan"]
    positions = [
        position for route in report["routes"] for position in route.get("regret_table", [])
    ]
    gaps = [abs(position["mode_gap"]) for position in positions if position.get("mode_gap") is not None]
    regimes = label_regime(report)
    return {
        "makespan": makespan,
        "position_count": len(positions),
        "informative_position_fraction": (
            sum(1 for position in positions if position.get("informative")) / len(positions)
            if positions
            else 0.0
        ),
        "tied_position_fraction": (
            sum(1 for position in positions if position.get("tied_state_count", 1) > 1) / len(positions)
            if positions
            else 0.0
        ),
        "mode_gap_abs_median": statistics.median(gaps) if gaps else None,
        "mode_gap_abs_max": max(gaps) if gaps else None,
        "load_excess_ratio": (
            report["route_load_excess"] / makespan if makespan > 0 else None
        ),
        "cost_shares": route_cost_shares(report),
        "large_gap": large_gap_share(report),
        "regime": regimes,
    }


def stage_dataset(
    output: Path,
    *,
    dataset: str = "v1",
    split: str = "development",
    near_tie_tol: float = 0.0,
) -> dict:
    """Run the state-regret instrument on every instance of a manifest split."""
    entries = dataset_entries(dataset, split)
    target = output / dataset / split
    summaries = []
    for entry in entries:
        instance_id = entry["instance_id"]
        instance = load_instance(V1_DATA / entry["path"])
        instance.name = instance_id
        states, cost_matrix, evaluator = evaluator_for(instance)
        solution = round_robin_solution(instance)
        route_dp = evaluator.route_evaluator
        before = route_dp.statistics()
        evaluation = evaluator.evaluate(solution)
        after_evaluation = route_dp.statistics()
        report = solution_state_report(
            instance,
            solution,
            evaluation,
            states_by_task=states,
            cost_matrix=cost_matrix,
            solution_hash=_solution_hash(solution),
            near_tie_tol=near_tie_tol,
        )
        after_report = route_dp.statistics()
        if before["calls"] >= after_evaluation["calls"]:
            raise AssertionError(f"dataset evaluation did not call Route-DP for {instance_id}")
        if after_evaluation["calls"] != after_report["calls"]:
            raise AssertionError(f"report re-entered Route-DP for {instance_id}")
        if after_evaluation["cache_misses"] != after_report["cache_misses"]:
            raise AssertionError(f"report changed DP cache misses for {instance_id}")
        assert_report_consistent(report)
        report.update(
            {
                "instance_id": instance_id,
                "dataset": dataset,
                "split": split,
                "scenario": entry["scenario"],
                "n_robots": entry["n_robots"],
                "n_tasks": entry["n_tasks"],
                "replicate": entry["replicate"],
                "solver": "round_robin",
                "near_tie_tol": near_tie_tol,
                "dp_statistics_before": after_evaluation,
                "dp_statistics_after": after_report,
            }
        )
        _write_json(target / f"{_sanitize(instance_id)}.json", report)
        summary = {"instance_id": instance_id, "scenario": entry["scenario"],
                   "n_robots": entry["n_robots"], "n_tasks": entry["n_tasks"],
                   "replicate": entry["replicate"]}
        summary.update(_instance_summary(report))
        summaries.append(summary)

    def _mean(values: list) -> float | None:
        clean = [value for value in values if value is not None]
        return statistics.mean(clean) if clean else None

    regime_counts: dict[str, int] = {}
    by_scenario: dict[str, dict] = {}
    by_tasks: dict[str, dict] = {}
    for summary in summaries:
        regime = summary["regime"]["regime"]
        regime_counts[regime] = regime_counts.get(regime, 0) + 1
        for bucket, key in ((by_scenario, summary["scenario"]), (by_tasks, str(summary["n_tasks"]))):
            slot = bucket.setdefault(key, {"count": 0, "informative": [], "large_gap": [], "regime": {}})
            slot["count"] += 1
            slot["informative"].append(summary["informative_position_fraction"])
            slot["large_gap"].append(summary["large_gap"]["large_gap_position_count"])
            slot["regime"][regime] = slot["regime"].get(regime, 0) + 1

    def _finalize(bucket: dict) -> dict:
        return {
            key: {
                "count": slot["count"],
                "mean_informative_position_fraction": _mean(slot["informative"]),
                "total_large_gap_positions": sum(slot["large_gap"]),
                "regime_counts": slot["regime"],
            }
            for key, slot in sorted(bucket.items())
        }

    result = {
        "dataset": dataset,
        "split": split,
        "git_head": _git_head(),
        "instance_count": len(summaries),
        "position_count": sum(summary["position_count"] for summary in summaries),
        "regime_counts": dict(sorted(regime_counts.items())),
        "mean_informative_position_fraction": _mean(
            [summary["informative_position_fraction"] for summary in summaries]
        ),
        "mean_tied_position_fraction": _mean(
            [summary["tied_position_fraction"] for summary in summaries]
        ),
        "mean_mode_gap_abs_median": _mean(
            [summary["mode_gap_abs_median"] for summary in summaries]
        ),
        "mean_load_excess_ratio": _mean(
            [summary["load_excess_ratio"] for summary in summaries]
        ),
        "mean_transfer_share": _mean(
            [summary["cost_shares"]["mean_transfer_share"] for summary in summaries
             if summary["cost_shares"]["mean_transfer_share"] is not None]
        ),
        "mean_coverage_share": _mean(
            [summary["cost_shares"]["mean_coverage_share"] for summary in summaries
             if summary["cost_shares"]["mean_coverage_share"] is not None]
        ),
        "mean_turning_share": _mean(
            [summary["cost_shares"]["mean_turning_share"] for summary in summaries
             if summary["cost_shares"]["mean_turning_share"] is not None]
        ),
        "total_large_gap_positions": sum(
            summary["large_gap"]["large_gap_position_count"] for summary in summaries
        ),
        "by_scenario": _finalize(by_scenario),
        "by_n_tasks": _finalize(by_tasks),
        "instances": summaries,
    }
    _write_json(target / "dataset_summary.json", result)
    print(json.dumps(
        {key: result[key] for key in ("dataset", "split", "instance_count", "position_count",
                                      "regime_counts", "mean_informative_position_fraction",
                                      "total_large_gap_positions")},
        indent=2, sort_keys=True,
    ))
    return result


def stage_alns(
    output: Path,
    *,
    instances_path: Path,
    budget_seconds: float = 30.0,
    seeds: tuple[int, ...] = (0,),
    near_tie_tol: float = 0.0,
) -> list[dict]:
    """Produce state-regret reports for real ALNS solutions on a pinned instance list."""
    from ..heuristics.alns_solver import ALNSConfig, ALNSSolver

    if not Path(instances_path).is_file():
        raise SystemExit(f"missing instance list: {instances_path}")
    relatives = json.loads(Path(instances_path).read_text(encoding="utf-8"))
    if not isinstance(relatives, list) or not relatives:
        raise ValueError(f"instance list must be a non-empty JSON array: {instances_path}")
    if budget_seconds <= 0:
        raise ValueError("budget_seconds must be positive")

    summaries = []
    for relative in relatives:
        instance = load_instance(ROOT / relative)
        states, cost_matrix, evaluator = evaluator_for(instance)
        for seed in seeds:
            config = ALNSConfig.enhanced(
                iterations=None,
                max_runtime_seconds=budget_seconds,
                random_seed=seed,
            )
            started = time.perf_counter()
            result = ALNSSolver(instance, config=config).solve()
            wall = time.perf_counter() - started
            solution = result.best_solution
            evaluation = evaluator.evaluate(solution)
            report = solution_state_report(
                instance,
                solution,
                evaluation,
                states_by_task=states,
                cost_matrix=cost_matrix,
                solution_hash=_solution_hash(solution),
                near_tie_tol=near_tie_tol,
            )
            assert_report_consistent(report)
            instance_id = str(relative).split("structural_benchmark_v1/")[-1].replace(".txt", "")
            report.update(
                {
                    "instance_id": instance_id,
                    "instance_path": str(relative),
                    "solver": "alns",
                    "solver_seed": seed,
                    "budget_seconds": budget_seconds,
                    "runtime_seconds": wall,
                    "near_tie_tol": near_tie_tol,
                    "alns_iterations": len(result.iteration_history),
                    "fallback_events": len(result.fallback_events),
                }
            )
            _write_json(output / "alns" / f"{_sanitize(instance_id)}__s{seed}.json", report)
            summary = {"instance_id": instance_id, "solver_seed": seed,
                       "budget_seconds": budget_seconds, "runtime_seconds": wall}
            summary.update(_instance_summary(report))
            summaries.append(summary)
            print(json.dumps(summary, sort_keys=True))
    _write_json(output / "alns" / "alns_summary.json", {"summaries": summaries})
    return summaries


def stage_verify(output: Path) -> dict:
    report_paths = sorted((output / "smoke").glob("*.json")) if (output / "smoke").is_dir() else []
    report_paths += sorted((output / "parents").glob("*.json")) if (output / "parents").is_dir() else []
    report_paths += sorted((output / "solutions").glob("*.json")) if (output / "solutions").is_dir() else []
    report_paths += [
        path for path in sorted((output / "v1").rglob("*.json")) if path.name != "dataset_summary.json"
    ] if (output / "v1").is_dir() else []
    report_paths += [
        path for path in sorted((output / "alns").glob("*.json")) if path.name != "alns_summary.json"
    ] if (output / "alns").is_dir() else []
    failures = []
    route_count = position_count = near_tie_positions = 0
    regret_values = []
    tied_positions = all_equal_positions = informative_positions = 0
    mode_gaps = []
    mode_preference_counts = {"H": 0, "V": 0, "equivalent": 0, "unknown": 0}
    for path in report_paths:
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
            assert_report_consistent(report)
            before = report.get("dp_statistics_before", {})
            after = report.get("dp_statistics_after", {})
            if before.get("calls") != after.get("calls"):
                raise ValueError("DP calls changed across report generation")
            if before.get("cache_misses") != after.get("cache_misses"):
                raise ValueError("DP cache misses changed across report generation")
            degeneracy = report.get("state_degeneracy") or {}
            tied_positions += degeneracy.get("tied_position_count", 0)
            all_equal_positions += degeneracy.get("all_equal_position_count", 0)
            informative_positions += degeneracy.get("informative_position_count", 0)
            for key, value in degeneracy.get("mode_preference_counts", {}).items():
                mode_preference_counts[key] = mode_preference_counts.get(key, 0) + value
            for route in report["routes"]:
                route_count += 1
                for position in route.get("regret_table", []):
                    position_count += 1
                    near_tie_positions += position["near_tie_count"] > 0
                    regret_values.extend(option["regret"] for option in position["options"])
                    if position.get("mode_gap") is not None:
                        mode_gaps.append(abs(position["mode_gap"]))
        except Exception as exc:
            failures.append({"file": str(path), "error": str(exc)})

    def _share(count: int) -> float:
        return count / position_count if position_count else 0.0

    summary = {
        "report_count": len(report_paths),
        "route_count": route_count,
        "position_count": position_count,
        "min_regret": min(regret_values, default=None),
        "max_regret": max(regret_values, default=None),
        "near_tie_position_fraction": _share(near_tie_positions),
        "tied_position_fraction": _share(tied_positions),
        "all_equal_position_fraction": _share(all_equal_positions),
        "informative_position_fraction": _share(informative_positions),
        "mode_gap_abs_median": statistics.median(mode_gaps) if mode_gaps else None,
        "mode_gap_abs_max": max(mode_gaps) if mode_gaps else None,
        "mode_preference_counts": mode_preference_counts,
        "failures": failures,
    }
    _write_json(output / "verify_summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage",
        choices=("smoke", "parents", "solutions", "dataset", "alns", "verify"),
        required=True,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--near-tie-tol", type=float, default=0.0)
    parser.add_argument(
        "--instances", type=Path, default=None,
        help="JSON array of instance paths relative to the project root (stage=alns)",
    )
    parser.add_argument(
        "--budget", type=float, default=30.0, help="ALNS wall-clock budget per instance/seed"
    )
    parser.add_argument(
        "--seeds", type=int, nargs="+", default=[0], help="solver seeds for stage=alns"
    )
    parser.add_argument(
        "--dataset", choices=("v1",), default="v1", help="manifest dataset for stage=dataset"
    )
    parser.add_argument(
        "--split", choices=("development", "validation"), default="development",
        help="manifest split for stage=dataset",
    )
    parser.add_argument(
        "--solutions", type=Path, default=None, help="solutions JSON for stage=solutions"
    )
    parser.add_argument(
        "--instance-root", type=Path, default=STRUCTURAL_DATA,
        help="root for e10b relative instance paths",
    )
    args = parser.parse_args()
    output = args.output.resolve()
    if args.stage == "smoke":
        stage_smoke(output, near_tie_tol=args.near_tie_tol)
    elif args.stage == "parents":
        stage_parents(output, near_tie_tol=args.near_tie_tol)
    elif args.stage == "solutions":
        if args.solutions is None:
            parser.error("--solutions is required for stage=solutions")
        stage_solutions(
            output,
            solutions_path=args.solutions,
            instance_root=args.instance_root,
            near_tie_tol=args.near_tie_tol,
        )
    elif args.stage == "dataset":
        stage_dataset(
            output,
            dataset=args.dataset,
            split=args.split,
            near_tie_tol=args.near_tie_tol,
        )
    elif args.stage == "alns":
        if args.instances is None:
            parser.error("--instances is required for stage=alns")
        stage_alns(
            output,
            instances_path=args.instances,
            budget_seconds=args.budget,
            seeds=tuple(args.seeds),
            near_tie_tol=args.near_tie_tol,
        )
    else:
        stage_verify(output)


if __name__ == "__main__":
    main()
