"""E14: read-only state-chain and state-regret instrumentation."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from ..core.cost_matrix import CostMatrix
from ..core.dp_evaluator import RouteDPEvaluator
from ..core.instance_loader import load_instance
from ..core.models import MultiRobotSolution
from ..core.solution_evaluator import MultiRobotSolutionEvaluator
from ..core.state_chain_report import assert_report_consistent, solution_state_report
from ..core.state_generator import generate_all_states

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = ROOT / "outputs/e14_state_regret_instrument"
E10B_OUTPUT = ROOT / "outputs/e10b_structural_dp_analysis"
STRUCTURAL_DATA = ROOT / "data/e10_structural_development"


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
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
            capture_output=True, text=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
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


def stage_verify(output: Path) -> dict:
    report_paths = sorted((output / "smoke").glob("*.json")) if (output / "smoke").is_dir() else []
    report_paths += sorted((output / "parents").glob("*.json")) if (output / "parents").is_dir() else []
    failures = []
    route_count = position_count = near_tie_positions = 0
    regret_values = []
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
            for route in report["routes"]:
                route_count += 1
                for position in route.get("regret_table", []):
                    position_count += 1
                    near_tie_positions += position["near_tie_count"] > 0
                    regret_values.extend(option["regret"] for option in position["options"])
        except Exception as exc:
            failures.append({"file": str(path), "error": str(exc)})
    summary = {
        "report_count": len(report_paths),
        "route_count": route_count,
        "position_count": position_count,
        "min_regret": min(regret_values, default=None),
        "max_regret": max(regret_values, default=None),
        "near_tie_position_fraction": (
            near_tie_positions / position_count if position_count else 0.0
        ),
        "failures": failures,
    }
    _write_json(output / "verify_summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("smoke", "parents", "verify"), required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--near-tie-tol", type=float, default=0.0)
    args = parser.parse_args()
    output = args.output.resolve()
    if args.stage == "smoke":
        stage_smoke(output, near_tie_tol=args.near_tie_tol)
    elif args.stage == "parents":
        stage_parents(output, near_tie_tol=args.near_tie_tol)
    else:
        stage_verify(output)


if __name__ == "__main__":
    main()
