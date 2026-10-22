"""Built-in-only optimization diagnostics for R3."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from copy import deepcopy
from pathlib import Path
from statistics import mean, median, pstdev
from time import perf_counter
from typing import Any, Iterable, Mapping, Sequence

from ..core.models import Instance, MultiRobotSolution, SolutionEvaluation
from ..heuristics.alns_solver import ALNSConfig, ALNSSolver
from ..heuristics.local_search import run_stronger_local_search

DIAGNOSTIC_SCHEMA_VERSION = "r3-diagnostics-v1"
BUILTIN_DESTROY_OPERATORS = frozenset(
    {"random_destroy", "bottleneck_route_destroy", "geometry_aware_destroy"}
)
BUILTIN_REPAIR_OPERATORS = frozenset(
    {"greedy_insertion", "regret_k_insertion", "bottleneck_balancing_insertion"}
)


def route_balance_metrics(
    route_costs: Sequence[float], route_task_counts: Sequence[int]
) -> dict[str, float]:
    """Compute makespan-oriented route balance metrics."""

    if not route_costs or len(route_costs) != len(route_task_counts):
        raise ValueError("route costs and task counts must be non-empty and aligned")
    ordered = sorted((float(value) for value in route_costs), reverse=True)
    maximum = ordered[0]
    second = ordered[1] if len(ordered) > 1 else maximum
    avg = mean(ordered)
    std = pstdev(ordered) if len(ordered) > 1 else 0.0
    return {
        "max_route_cost": maximum,
        "second_max_route_cost": second,
        "mean_route_cost": avg,
        "std_route_cost": std,
        "route_cost_cv": std / avg if avg else 0.0,
        "bottleneck_gap_abs": maximum - second,
        "bottleneck_gap_rel": (maximum - second) / maximum if maximum else 0.0,
        "route_task_count_std": pstdev(route_task_counts)
        if len(route_task_counts) > 1
        else 0.0,
    }


def objective_decomposition(
    instance: Instance, evaluation: SolutionEvaluation
) -> dict[str, float]:
    """Decompose all route costs into travel, traversal, and turning time."""

    travel = 0.0
    coverage = 0.0
    turning = 0.0
    task_lookup = {task.task_id: task for task in instance.tasks}
    for route in evaluation.route_evaluations:
        travel += sum(route.transition_costs)
        for state in route.chosen_states:
            task = task_lookup[state.task_id]
            sweep_length = task.width if state.sweep_mode.value == "H" else task.height
            coverage += state.n_sweeps * sweep_length / instance.sweep_speed
            turning += max(0, state.n_sweeps - 1) * instance.turning_time
    total = travel + coverage + turning
    return {
        "travel_time": travel,
        "coverage_traversal_time": coverage,
        "turning_time": turning,
        "travel_share": travel / total if total else 0.0,
        "coverage_share": coverage / total if total else 0.0,
        "turning_share": turning / total if total else 0.0,
    }


def classify_solution_change(
    before: MultiRobotSolution, after: MultiRobotSolution
) -> str:
    """Classify a complete-solution change by assignment before ordering."""

    if before.routes == after.routes:
        return "unchanged"
    before_assignment = _assignment(before)
    after_assignment = _assignment(after)
    if before_assignment != after_assignment:
        return "assignment"
    return "ordering"


def state_chain_signatures(
    evaluation: SolutionEvaluation,
) -> dict[int, tuple[str, str, str]]:
    """Map each task to its DP-optimal mode, entry corner, and exit corner."""

    signatures: dict[int, tuple[str, str, str]] = {}
    for route in evaluation.route_evaluations:
        for state in route.chosen_states:
            signatures[state.task_id] = (
                state.sweep_mode.value,
                state.entry_corner.value,
                state.exit_corner.value,
            )
    return signatures


def state_chain_diff(
    before: Mapping[int, tuple[str, str, str]],
    after: Mapping[int, tuple[str, str, str]],
    *,
    affected_task_ids: Iterable[int],
    directly_moved_task_ids: Iterable[int],
) -> dict[str, float | int]:
    """Measure accepted-move state switching and indirect DP cascade."""

    affected = set(affected_task_ids)
    direct = set(directly_moved_task_ids)
    comparable = sorted(affected & before.keys() & after.keys())
    changed = [task for task in comparable if before[task] != after[task]]
    mode_switches = sum(before[task][0] != after[task][0] for task in changed)
    entry_switches = sum(before[task][1] != after[task][1] for task in changed)
    exit_switches = sum(before[task][2] != after[task][2] for task in changed)
    indirect = [task for task in changed if task not in direct]
    cascade_denominator = max(1, len(comparable) - len(direct & set(comparable)))
    return {
        "state_changed_count": len(changed),
        "state_changed_fraction": len(changed) / len(comparable) if comparable else 0.0,
        "mode_switch_count": mode_switches,
        "mode_switch_fraction": mode_switches / len(comparable) if comparable else 0.0,
        "entry_corner_changed_count": entry_switches,
        "exit_corner_changed_count": exit_switches,
        "indirect_state_changed_tasks": len(indirect),
        "cascade_count": int(bool(indirect)),
        "dp_cascade_ratio": len(indirect) / cascade_denominator,
    }


def run_diagnostic_alns(
    instance: Instance,
    *,
    source_track: str,
    family_id: str | None,
    config: ALNSConfig,
) -> dict[str, Any]:
    """Run manual built-in ALNS while collecting R3-only diagnostics."""

    _validate_diagnostic_config(config)
    solver = ALNSSolver(instance, config=config, advisor=None)
    if set(solver.destroy_ops) != BUILTIN_DESTROY_OPERATORS:
        raise ValueError("diagnostics require the exact built-in destroy pool")
    if set(solver.repair_ops) != BUILTIN_REPAIR_OPERATORS:
        raise ValueError("diagnostics require the exact built-in repair pool")

    current_solution = _copy_solution(solver.initial_solution)
    current_eval = solver.solution_evaluator.evaluate(current_solution)
    initial_solution = _copy_solution(current_solution)
    initial_eval = current_eval
    best_solution = _copy_solution(current_solution)
    best_eval = current_eval
    history: list[dict[str, Any]] = []
    temperature = config.initial_temperature
    recent_best = [best_eval.makespan]
    started = perf_counter()

    for iteration in range(1, config.iterations + 1):
        previous_solution = _copy_solution(current_solution)
        previous_eval = current_eval
        dp_before = solver.route_dp.statistics()
        context = solver._build_context(best_eval, current_eval, recent_best)
        destroy_name, repair_name, phase = solver._select_operators(context)
        remove_count = max(1, int(config.destroy_fraction * instance.task_count))
        partial_solution, removed_tasks = solver.destroy_ops[destroy_name](
            current_solution, current_eval, remove_count
        )
        partial_eval = solver.solution_evaluator.evaluate_partial(partial_solution)
        repaired_solution = solver.repair_ops[repair_name](
            partial_solution, removed_tasks, partial_eval
        )
        repaired_eval = solver.solution_evaluator.evaluate(repaired_solution)
        refined_solution, refined_eval = run_stronger_local_search(
            repaired_solution, solver.solution_evaluator, max_iterations=1
        )

        accepted, accept_reason = solver._accept(
            current_eval, refined_eval, temperature
        )
        if accepted:
            current_solution = _copy_solution(refined_solution)
            current_eval = refined_eval

        best_update = refined_eval.makespan + 1e-9 < best_eval.makespan
        score = 0.0
        if best_update:
            best_solution = _copy_solution(refined_solution)
            best_eval = refined_eval
            score = 8.0
        elif accepted and refined_eval.makespan + 1e-9 < previous_eval.makespan:
            score = 3.0
        elif accepted:
            score = 1.0
        solver._update_operator_stats("destroy", destroy_name, score)
        solver._update_operator_stats("repair", repair_name, score)
        solver._update_weights()

        affected_tasks = _affected_tasks(previous_solution, refined_solution)
        if accepted:
            state_metrics = state_chain_diff(
                state_chain_signatures(previous_eval),
                state_chain_signatures(refined_eval),
                affected_task_ids=affected_tasks,
                directly_moved_task_ids=removed_tasks,
            )
            relief = previous_eval.makespan - refined_eval.makespan
            change_class = classify_solution_change(previous_solution, refined_solution)
        else:
            state_metrics = _zero_state_metrics()
            relief = 0.0
            change_class = "rejected"
        dp_after = solver.route_dp.statistics()
        history.append(
            {
                "iteration": iteration,
                "phase": phase,
                "destroy": destroy_name,
                "repair": repair_name,
                "accepted": accepted,
                "accept_reason": accept_reason,
                "best_update": best_update,
                "objective_before_move": previous_eval.makespan,
                "objective_after_repair": repaired_eval.makespan,
                "objective_after_local_search": refined_eval.makespan,
                "current_makespan": current_eval.makespan,
                "best_makespan": best_eval.makespan,
                "repair_change_class": classify_solution_change(
                    previous_solution, repaired_solution
                ),
                "local_search_change_class": classify_solution_change(
                    repaired_solution, refined_solution
                ),
                "accepted_change_class": change_class,
                "repair_gain": previous_eval.makespan - repaired_eval.makespan,
                "local_search_gain": repaired_eval.makespan - refined_eval.makespan,
                "objective_gain": previous_eval.makespan - refined_eval.makespan,
                "directly_moved_tasks": len(set(removed_tasks)),
                "affected_task_count": len(affected_tasks),
                "bottleneck_relief": relief,
                "bottleneck_relief_rel": relief / previous_eval.makespan
                if previous_eval.makespan
                else 0.0,
                **state_metrics,
                "dp_calls": int(dp_after["calls"] - dp_before["calls"]),
                "dp_cache_hits": int(
                    dp_after["cache_hits"] - dp_before["cache_hits"]
                ),
                "dp_cache_misses": int(
                    dp_after["cache_misses"] - dp_before["cache_misses"]
                ),
                "dp_compute_time_sec": float(
                    dp_after["compute_time_sec"] - dp_before["compute_time_sec"]
                ),
            }
        )
        recent_best.append(best_eval.makespan)
        recent_best = recent_best[-20:]
        temperature = max(1e-4, temperature * config.cooling_rate)

    elapsed = perf_counter() - started
    config_hash = _hash_json(_config_payload(config))
    source_token = source_track.replace("/", "-").replace(" ", "-")
    identity_token = (family_id or instance.name).replace("/", "-").replace(" ", "-")
    run_id = (
        f"{source_token}-{identity_token}-seed-{config.random_seed}-"
        f"{config_hash[:12]}"
    )
    best_iteration = next(
        (
            row["iteration"]
            for row in history
            if math.isclose(row["best_makespan"], best_eval.makespan, abs_tol=1e-9)
        ),
        0,
    )
    best_series = [initial_eval.makespan] + [row["best_makespan"] for row in history]
    improvement_iterations = [
        index
        for index, (before, after) in enumerate(
            zip(best_series, best_series[1:]), start=1
        )
        if after + 1e-9 < before
    ]
    stagnation_lengths = _stagnation_lengths(config.iterations, improvement_iterations)
    workload = solver.route_dp.statistics()
    return {
        "diagnostic_schema_version": DIAGNOSTIC_SCHEMA_VERSION,
        "run_id": run_id,
        "instance_id": instance.name,
        "source_track": source_track,
        "family_id": family_id,
        "replicate_id": instance.rep_id,
        "n_robots": instance.robot_count,
        "n_tasks": instance.task_count,
        "solver_seed": config.random_seed,
        "solver_config_hash": config_hash,
        "status": "completed",
        "initial_makespan": initial_eval.makespan,
        "best_makespan": best_eval.makespan,
        "final_makespan": current_eval.makespan,
        "absolute_improvement": initial_eval.makespan - best_eval.makespan,
        "relative_improvement": (
            (initial_eval.makespan - best_eval.makespan) / initial_eval.makespan
            if initial_eval.makespan
            else 0.0
        ),
        "runtime_sec": elapsed,
        "iteration_to_best": best_iteration,
        "time_to_best_proxy_fraction": best_iteration / config.iterations
        if config.iterations
        else 0.0,
        "improvement_event_count": len(improvement_iterations),
        "longest_stagnation": max(stagnation_lengths, default=config.iterations),
        "final_stagnation": config.iterations
        - (improvement_iterations[-1] if improvement_iterations else 0),
        "initial_route_balance": route_balance_metrics(
            initial_eval.per_robot_costs,
            [len(route) for route in initial_solution.routes],
        ),
        "best_route_balance": route_balance_metrics(
            best_eval.per_robot_costs, [len(route) for route in best_solution.routes]
        ),
        "initial_objective_decomposition": objective_decomposition(
            instance, initial_eval
        ),
        "best_objective_decomposition": objective_decomposition(instance, best_eval),
        "dp_workload": workload,
        "operator_summary": _operator_summary(history),
        "iterations": history,
        "provider_used": False,
        "generated_operator_used": False,
    }


def write_diagnostic_outputs(
    output_dir: str | Path,
    *,
    runs: Sequence[Mapping[str, Any]],
    instance_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Path]:
    """Write deterministic JSON/CSV diagnostic artifacts without a database."""

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    convergence_dir = destination / "convergence"
    convergence_dir.mkdir(exist_ok=True)
    paths = {
        "metadata": destination / "metadata.json",
        "run_metrics": destination / "run_metrics.csv",
        "instance_summary": destination / "instance_summary.csv",
        "operator_summary": destination / "operator_summary.csv",
        "dp_behavior": destination / "dp_behavior.csv",
    }
    metadata = {
        "diagnostic_schema_version": DIAGNOSTIC_SCHEMA_VERSION,
        "run_count": len(runs),
        "instance_count": len(instance_rows),
        "final_test_used": False,
        "provider_used": False,
        "generated_operator_used": False,
    }
    paths["metadata"].write_text(
        json.dumps(metadata, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    _write_csv(paths["instance_summary"], instance_rows)
    _write_csv(paths["run_metrics"], [_flatten_run(run) for run in runs])
    operator_rows: list[dict[str, Any]] = []
    dp_rows: list[dict[str, Any]] = []
    for run in runs:
        for operator_type, rows in run.get("operator_summary", {}).items():
            for name, metrics in rows.items():
                operator_rows.append(
                    {
                        "run_id": run["run_id"],
                        "instance_id": run["instance_id"],
                        "source_track": run["source_track"],
                        "operator_type": operator_type,
                        "operator_name": name,
                        **metrics,
                    }
                )
        for iteration in run.get("iterations", []):
            if iteration.get("accepted"):
                dp_rows.append(
                    {
                        "run_id": run["run_id"],
                        "instance_id": run["instance_id"],
                        "source_track": run["source_track"],
                        **{
                            key: iteration[key]
                            for key in (
                                "iteration",
                                "state_changed_count",
                                "state_changed_fraction",
                                "mode_switch_count",
                                "entry_corner_changed_count",
                                "exit_corner_changed_count",
                                "indirect_state_changed_tasks",
                                "cascade_count",
                                "dp_cascade_ratio",
                            )
                        },
                    }
                )
        convergence_path = convergence_dir / f"{run['run_id']}.csv"
        _write_csv(
            convergence_path,
            [
                {
                    "iteration": row["iteration"],
                    "current_makespan": row["current_makespan"],
                    "best_makespan": row["best_makespan"],
                }
                for row in run.get("iterations", [])
            ],
        )
    _write_csv(paths["operator_summary"], operator_rows)
    _write_csv(paths["dp_behavior"], dp_rows)
    return paths


def _assignment(solution: MultiRobotSolution) -> dict[int, int]:
    return {
        task_id: robot
        for robot, route in enumerate(solution.routes)
        for task_id in route
    }


def _copy_solution(solution: MultiRobotSolution) -> MultiRobotSolution:
    return MultiRobotSolution(routes=[list(route) for route in solution.routes])


def _affected_tasks(
    before: MultiRobotSolution, after: MultiRobotSolution
) -> set[int]:
    affected: set[int] = set()
    for before_route, after_route in zip(before.routes, after.routes):
        if before_route != after_route:
            affected.update(before_route)
            affected.update(after_route)
    return affected


def _zero_state_metrics() -> dict[str, float | int]:
    return {
        "state_changed_count": 0,
        "state_changed_fraction": 0.0,
        "mode_switch_count": 0,
        "mode_switch_fraction": 0.0,
        "entry_corner_changed_count": 0,
        "exit_corner_changed_count": 0,
        "indirect_state_changed_tasks": 0,
        "cascade_count": 0,
        "dp_cascade_ratio": 0.0,
    }


def _validate_diagnostic_config(config: ALNSConfig) -> None:
    if config.iterations <= 0:
        raise ValueError("diagnostic iterations must be positive")
    if (
        config.frozen_operator_registry_path
        or config.use_frozen_repair
        or config.use_frozen_destroy
        or config.allow_generated_frozen_deployment
        or config.allow_real_provider_frozen_deployment
    ):
        raise ValueError("R3 diagnostics permit built-in operators only")


def _config_payload(config: ALNSConfig) -> dict[str, Any]:
    return {
        "iterations": config.iterations,
        "destroy_fraction": config.destroy_fraction,
        "acceptance": config.acceptance,
        "initial_temperature": config.initial_temperature,
        "cooling_rate": config.cooling_rate,
        "random_seed": config.random_seed,
        "operator_pool": {
            "destroy": sorted(BUILTIN_DESTROY_OPERATORS),
            "repair": sorted(BUILTIN_REPAIR_OPERATORS),
        },
        "local_search_iterations": 1,
        "advisor": None,
    }


def _hash_json(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _stagnation_lengths(iterations: int, improvement_iterations: list[int]) -> list[int]:
    boundaries = [0, *improvement_iterations, iterations]
    return [right - left for left, right in zip(boundaries, boundaries[1:])]


def _operator_summary(history: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    output: dict[str, dict[str, Any]] = {"destroy": {}, "repair": {}}
    for operator_type in ("destroy", "repair"):
        names = sorted({str(row[operator_type]) for row in history})
        for name in names:
            selected = [row for row in history if row[operator_type] == name]
            deltas = [float(row["objective_gain"]) for row in selected]
            output[operator_type][name] = {
                "usage_count": len(selected),
                "accepted_count": sum(bool(row["accepted"]) for row in selected),
                "improvement_count": sum(
                    bool(row["accepted"]) and float(row["objective_gain"]) > 1e-9
                    for row in selected
                ),
                "best_update_count": sum(bool(row["best_update"]) for row in selected),
                "mean_delta": mean(deltas) if deltas else 0.0,
                "median_delta": median(deltas) if deltas else 0.0,
                "bottleneck_relief_count": sum(
                    float(row["bottleneck_relief"]) > 1e-9 for row in selected
                ),
            }
    return output


def _flatten_run(run: Mapping[str, Any]) -> dict[str, Any]:
    flat = {
        key: value
        for key, value in run.items()
        if key
        not in {
            "iterations",
            "operator_summary",
            "initial_route_balance",
            "best_route_balance",
            "initial_objective_decomposition",
            "best_objective_decomposition",
            "dp_workload",
        }
    }
    for prefix in (
        "initial_route_balance",
        "best_route_balance",
        "initial_objective_decomposition",
        "best_objective_decomposition",
        "dp_workload",
    ):
        for key, value in run.get(prefix, {}).items():
            flat[f"{prefix}_{key}"] = value
    return flat


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


__all__ = [
    "BUILTIN_DESTROY_OPERATORS",
    "BUILTIN_REPAIR_OPERATORS",
    "DIAGNOSTIC_SCHEMA_VERSION",
    "classify_solution_change",
    "objective_decomposition",
    "route_balance_metrics",
    "run_diagnostic_alns",
    "state_chain_diff",
    "state_chain_signatures",
    "write_diagnostic_outputs",
]
