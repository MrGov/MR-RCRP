"""Benchmark harness for generated repair/destroy operators."""
from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Dict, List, Sequence

from ...core.cost_matrix import CostMatrix
from ...core.dp_evaluator import RouteDPEvaluator
from ...core.instance_loader import load_instance
from ...core.models import Instance, MultiRobotSolution, SolutionEvaluation
from ...core.solution_evaluator import MultiRobotSolutionEvaluator
from ...core.state_generator import generate_all_states
from ...heuristics.baseline_solver import resolve_constructor
from .candidate_loader import LoadedOperator
from .candidate_execution import CandidateExecutionResult, CandidateProxy
from .eligibility_policy import build_generated_artifact_metadata
from .metrics import TrialMetric, summarize_trials
from .protocols import DestroyContext, RepairContext
from .utils import clone_solution, is_solution_complete


@dataclass
class RepairBenchmarkCase:
    instance: Instance
    evaluator: MultiRobotSolutionEvaluator
    full_solution: MultiRobotSolution
    full_evaluation: SolutionEvaluation
    partial_solution: MultiRobotSolution
    partial_evaluation: SolutionEvaluation
    removed_tasks: List[int]


@dataclass
class DestroyBenchmarkCase:
    instance: Instance
    evaluator: MultiRobotSolutionEvaluator
    full_solution: MultiRobotSolution
    full_evaluation: SolutionEvaluation


def build_repair_benchmark_cases(
    instance_paths: Sequence[Path],
    *,
    constructor: str = "round_robin",
    remove_fraction: float = 0.3,
) -> List[RepairBenchmarkCase]:
    cases: List[RepairBenchmarkCase] = []
    ctor = resolve_constructor(constructor)

    for path in instance_paths:
        instance = load_instance(path)
        states_by_task = generate_all_states(instance)
        cost_matrix = CostMatrix(
            instance.depot, states_by_task, travel_speed=instance.travel_speed
        )
        route_dp = RouteDPEvaluator(cost_matrix, states_by_task)
        evaluator = MultiRobotSolutionEvaluator(route_dp, instance=instance)

        full_solution = ctor(instance)
        full_eval = evaluator.evaluate(full_solution)

        partial_solution, removed_tasks = _deterministic_destroy(
            full_solution,
            full_eval,
            remove_count=max(1, int(instance.task_count * remove_fraction)),
        )
        partial_eval = evaluator.evaluate_partial(partial_solution)
        cases.append(
            RepairBenchmarkCase(
                instance=instance,
                evaluator=evaluator,
                full_solution=full_solution,
                full_evaluation=full_eval,
                partial_solution=partial_solution,
                partial_evaluation=partial_eval,
                removed_tasks=removed_tasks,
            )
        )

    return cases


def build_destroy_benchmark_cases(
    instance_paths: Sequence[Path],
    *,
    constructor: str = "round_robin",
) -> List[DestroyBenchmarkCase]:
    cases: List[DestroyBenchmarkCase] = []
    ctor = resolve_constructor(constructor)
    for path in instance_paths:
        instance = load_instance(path)
        states_by_task = generate_all_states(instance)
        cost_matrix = CostMatrix(
            instance.depot, states_by_task, travel_speed=instance.travel_speed
        )
        route_dp = RouteDPEvaluator(cost_matrix, states_by_task)
        evaluator = MultiRobotSolutionEvaluator(route_dp, instance=instance)

        full_solution = ctor(instance)
        full_eval = evaluator.evaluate(full_solution)
        cases.append(
            DestroyBenchmarkCase(
                instance=instance,
                evaluator=evaluator,
                full_solution=full_solution,
                full_evaluation=full_eval,
            )
        )
    return cases


def evaluate_repair_candidates(
    candidates: Sequence[LoadedOperator],
    cases: Sequence[RepairBenchmarkCase],
    *,
    seeds: Sequence[int],
    timeout_ms: float,
) -> List[dict]:
    rows: List[dict] = []

    for candidate in candidates:
        trials: List[TrialMetric] = []
        for case in cases:
            baseline_solution = _fixed_greedy_repair(
                case.partial_solution,
                case.removed_tasks,
                case.evaluator,
            )
            baseline_eval = case.evaluator.evaluate(baseline_solution)
            for seed in seeds:
                rng = random.Random(seed)
                timeout = False
                error = False
                invalid = False
                makespan_delta = 0.0
                rel = 0.0
                success = False
                bottleneck = _bottleneck_route(case.partial_evaluation)
                context = RepairContext(
                    instance=case.instance,
                    per_robot_costs=list(case.partial_evaluation.per_robot_costs),
                    route_costs_makespan=case.partial_evaluation.makespan,
                    bottleneck_route_id=bottleneck,
                )
                outcome = _invoke_candidate(
                    candidate,
                    (
                        clone_solution(case.partial_solution),
                        list(case.removed_tasks),
                        context,
                        rng,
                    ),
                    timeout_ms,
                )
                runtime_ms = outcome.runtime_ms
                if outcome.status == "timeout":
                    timeout = True
                elif outcome.status != "success":
                    error = True
                else:
                    try:
                        new_solution = outcome.result.solution
                    except (AttributeError, TypeError):
                        error = True
                        new_solution = None
                    if not error and not _is_valid_complete_solution(
                        new_solution, case.instance
                    ):
                        invalid = True
                    if not error and not invalid:
                        repaired_eval = case.evaluator.evaluate(new_solution)
                        makespan_delta = baseline_eval.makespan - repaired_eval.makespan
                        base = max(1e-6, baseline_eval.makespan)
                        rel = makespan_delta / base
                        success = makespan_delta > 1e-9

                trials.append(
                    TrialMetric(
                        makespan_delta=makespan_delta,
                        relative_improvement=rel,
                        runtime_ms=runtime_ms,
                        success=success,
                        timeout=timeout,
                        error=error,
                        invalid_solution=invalid,
                    )
                )

        summary = summarize_trials(trials)
        failure_type = _summary_execution_status(summary)
        rows.append(
            {
                "operator_id": candidate.validation.operator_id,
                "operator_type": "repair",
                "round_id": candidate.validation.round_id,
                "name": candidate.validation.name,
                "validation_status": candidate.validation.validation_status,
                "execution_status": failure_type,
                "failure_type": failure_type,
                "failure_type_breakdown": _trial_failure_breakdown(trials),
                "fallback_used": False,
                "fallback_reason": "",
                "runtime_ms": summary.avg_runtime_ms,
                "code_hash": candidate.validation.code_hash,
                **build_generated_artifact_metadata(
                    claimed_source_provider=candidate.validation.source,
                    round_id=candidate.validation.round_id,
                    code_hash=candidate.validation.code_hash,
                ),
                "sandbox_level": candidate.validation.sandbox_level,
                "claimed_sandbox_level": candidate.validation.claimed_sandbox_level,
                "effective_sandbox_level": candidate.validation.effective_sandbox_level,
                "executor_identity": candidate.validation.executor_identity,
                "safe_to_execute": candidate.validation.safe_to_execute,
                "requires_human_risk_ack": candidate.validation.requires_human_risk_ack,
                "timeout_ms": timeout_ms,
                "avg_makespan_delta": summary.avg_makespan_delta,
                "avg_relative_improvement": summary.avg_relative_improvement,
                "success_rate": summary.success_rate,
                "avg_runtime_ms": summary.avg_runtime_ms,
                "timeout_rate": summary.timeout_rate,
                "error_rate": summary.error_rate,
                "invalid_solution_rate": summary.invalid_solution_rate,
                "validation_failed_rate": 0.0,
                "execution_blocked_rate": 0.0,
            }
        )
    return rows


def evaluate_destroy_candidates(
    candidates: Sequence[LoadedOperator],
    cases: Sequence[DestroyBenchmarkCase],
    *,
    seeds: Sequence[int],
    timeout_ms: float,
    fixed_repair: LoadedOperator | None = None,
    reference_destroy=None,
    behavior_callback=None,
) -> List[dict]:
    """Evaluate destroy; optionally pair against manual destroy with one fixed repair.

    The optional behavior callback consumes real complete evaluator results. It
    permits reuse of canonical experiment diagnostics without a second metric
    implementation or exposing the evaluator to generated operators.
    """
    if fixed_repair is not None:
        if reference_destroy is None:
            raise ValueError("paired fixed-repair evaluation requires reference_destroy")
        return [_evaluate_paired_destroy(c, cases, seeds, timeout_ms, fixed_repair,
                                        reference_destroy, behavior_callback) for c in candidates]

    rows: List[dict] = []

    for candidate in candidates:
        trials: List[TrialMetric] = []
        for case in cases:
            for seed in seeds:
                rng = random.Random(seed)
                timeout = False
                error = False
                invalid = False
                makespan_delta = 0.0
                rel = 0.0
                success = False
                context = DestroyContext(
                    instance=case.instance,
                    per_robot_costs=list(case.full_evaluation.per_robot_costs),
                    route_costs_makespan=case.full_evaluation.makespan,
                    remove_count=max(1, case.instance.task_count // 4),
                )
                outcome = _invoke_candidate(
                    candidate,
                    (
                        clone_solution(case.full_solution),
                        context,
                        rng,
                    ),
                    timeout_ms,
                )
                runtime_ms = outcome.runtime_ms
                if outcome.status == "timeout":
                    timeout = True
                elif outcome.status != "success":
                    error = True
                else:
                    try:
                        destroyed = outcome.result
                        partial_solution = destroyed.partial_solution
                        removed_tasks = destroyed.removed_tasks
                        if not _is_valid_partial_solution(
                            partial_solution, case.instance
                        ) or not isinstance(removed_tasks, list):
                            raise ValueError("invalid destroy result shape")
                        repaired_solution = _fixed_greedy_repair(
                            partial_solution,
                            removed_tasks,
                            case.evaluator,
                        )
                    except (AttributeError, TypeError, ValueError):
                        error = True
                        repaired_solution = None
                    if not error and not _is_valid_complete_solution(
                        repaired_solution, case.instance
                    ):
                        invalid = True
                    if not error and not invalid:
                        repaired_eval = case.evaluator.evaluate(repaired_solution)
                        makespan_delta = case.full_evaluation.makespan - repaired_eval.makespan
                        rel = makespan_delta / max(1e-6, case.full_evaluation.makespan)
                        success = makespan_delta > 1e-9

                trials.append(
                    TrialMetric(
                        makespan_delta=makespan_delta,
                        relative_improvement=rel,
                        runtime_ms=runtime_ms,
                        success=success,
                        timeout=timeout,
                        error=error,
                        invalid_solution=invalid,
                    )
                )

        summary = summarize_trials(trials)
        failure_type = _summary_execution_status(summary)
        rows.append(
            {
                "operator_id": candidate.validation.operator_id,
                "operator_type": "destroy",
                "round_id": candidate.validation.round_id,
                "name": candidate.validation.name,
                "validation_status": candidate.validation.validation_status,
                "execution_status": failure_type,
                "failure_type": failure_type,
                "failure_type_breakdown": _trial_failure_breakdown(trials),
                "fallback_used": False,
                "fallback_reason": "",
                "runtime_ms": summary.avg_runtime_ms,
                "code_hash": candidate.validation.code_hash,
                **build_generated_artifact_metadata(
                    claimed_source_provider=candidate.validation.source,
                    round_id=candidate.validation.round_id,
                    code_hash=candidate.validation.code_hash,
                ),
                "sandbox_level": candidate.validation.sandbox_level,
                "claimed_sandbox_level": candidate.validation.claimed_sandbox_level,
                "effective_sandbox_level": candidate.validation.effective_sandbox_level,
                "executor_identity": candidate.validation.executor_identity,
                "safe_to_execute": candidate.validation.safe_to_execute,
                "requires_human_risk_ack": candidate.validation.requires_human_risk_ack,
                "timeout_ms": timeout_ms,
                "avg_makespan_delta": summary.avg_makespan_delta,
                "avg_relative_improvement": summary.avg_relative_improvement,
                "success_rate": summary.success_rate,
                "avg_runtime_ms": summary.avg_runtime_ms,
                "timeout_rate": summary.timeout_rate,
                "error_rate": summary.error_rate,
                "invalid_solution_rate": summary.invalid_solution_rate,
                "validation_failed_rate": 0.0,
                "execution_blocked_rate": 0.0,
            }
        )
    return rows


def _evaluate_paired_destroy(candidate, cases, seeds, timeout_ms, fixed_repair,
                             reference_destroy, behavior_callback):
    metrics, records = [], []
    for case in cases:
        for seed in seeds:
            started = perf_counter()
            calls_start = case.evaluator.route_evaluator.statistics()["calls"]
            count = max(1, case.instance.task_count // 4)
            record = dict(instance_id=case.instance.name, solver_seed=seed, remove_count=count,
                          fixed_repair_hash=fixed_repair.validation.code_hash,
                          parent_makespan=case.full_evaluation.makespan,
                          parent_route_costs=case.full_evaluation.per_robot_costs,
                          parent_routes=case.full_solution.routes, feasible=False,
                          fallback_used=False, status="error")
            runtime_ms = 0.0
            status = "success"
            def complete(partial, removed):
                nonlocal runtime_ms, status
                if (not _is_valid_partial_solution(partial, case.instance)
                    or not isinstance(removed, list) or len(removed) != count
                    or any(type(t) is not int for t in removed)
                    or len(set(removed)) != count):
                    status = "invalid_solution"
                    raise ValueError("wrong removal count/type")
                remaining = [t for r in partial.routes for t in r]
                original = [t for r in case.full_solution.routes for t in r]
                if Counter(remaining) + Counter(removed) != Counter(original) or set(remaining) & set(removed):
                    status = "invalid_solution"
                    raise ValueError("inconsistent destroy partition")
                partial_eval = case.evaluator.evaluate_partial(partial)
                context = RepairContext(case.instance, list(partial_eval.per_robot_costs),
                                        partial_eval.makespan, _bottleneck_route(partial_eval))
                outcome = _invoke_candidate(fixed_repair, (clone_solution(partial), list(removed),
                                                          context, random.Random(seed)), timeout_ms)
                runtime_ms += outcome.runtime_ms
                if outcome.status != "success":
                    status = outcome.status
                    raise RuntimeError(f"fixed repair {outcome.status}: {outcome.error_message}")
                repaired = outcome.result.solution
                if not _is_valid_complete_solution(repaired, case.instance):
                    status = "invalid_solution"
                    raise ValueError("fixed repair returned incomplete solution")
                return repaired, case.evaluator.evaluate(repaired)
            try:
                partial, removed = reference_destroy(clone_solution(case.full_solution),
                    case.full_evaluation, count, random.Random(seed))
                baseline_solution, baseline_eval = complete(partial, removed)
                record.update(reference_removed_tasks=removed, baseline_makespan=baseline_eval.makespan,
                              baseline_route_costs=baseline_eval.per_robot_costs, baseline_routes=baseline_solution.routes)
                context = DestroyContext(case.instance, list(case.full_evaluation.per_robot_costs),
                                         case.full_evaluation.makespan, count)
                outcome = _invoke_candidate(candidate, (clone_solution(case.full_solution), context,
                                                        random.Random(seed)), timeout_ms)
                runtime_ms += outcome.runtime_ms
                if outcome.status != "success":
                    status = outcome.status
                    raise RuntimeError(f"destroy {outcome.status}: {outcome.error_message}")
                destroyed = outcome.result
                record["removed_tasks"] = destroyed.removed_tasks
                repaired, evaluated = complete(destroyed.partial_solution, destroyed.removed_tasks)
                delta = baseline_eval.makespan - evaluated.makespan
                relative = delta / max(1e-6, baseline_eval.makespan)
                reassigned = sum(next(i for i,r in enumerate(baseline_solution.routes) if t in r) !=
                                 next(i for i,r in enumerate(repaired.routes) if t in r)
                                 for t in (task.task_id for task in case.instance.tasks))
                record.update(feasible=True, status="success", candidate_makespan=evaluated.makespan,
                              candidate_route_costs=evaluated.per_robot_costs, candidate_routes=repaired.routes,
                              relative_improvement=relative, reassigned_task_count=reassigned)
                if behavior_callback is not None:
                    record["exact_dp_behavior"] = behavior_callback(baseline_solution, repaired,
                        baseline_eval, evaluated, instance=case.instance)
                    record["parent_to_candidate_behavior"] = behavior_callback(case.full_solution, repaired,
                        case.full_evaluation, evaluated, instance=case.instance)
            except (ValueError, TypeError, AttributeError, RuntimeError) as exc:
                record.update(status=status if status != "success" else "runtime_error",
                              error=f"{type(exc).__name__}: {exc}")
            record.update(runtime_ms=runtime_ms, wall_seconds=perf_counter()-started,
                          route_dp_calls=case.evaluator.route_evaluator.statistics()["calls"]-calls_start)
            records.append(record)
            metrics.append(TrialMetric(makespan_delta=record.get("baseline_makespan", 0)-record.get("candidate_makespan", record.get("baseline_makespan", 0)),
                relative_improvement=record.get("relative_improvement", 0), runtime_ms=runtime_ms,
                success=record.get("relative_improvement", 0)>1e-9,
                timeout=record["status"]=="timeout",
                error=not record["feasible"] and record["status"] not in ("timeout", "invalid_solution"),
                invalid_solution=record["status"]=="invalid_solution"))
    summary = summarize_trials(metrics)
    from dataclasses import asdict
    return dict(operator_id=candidate.validation.operator_id, operator_type="destroy",
                code_hash=candidate.validation.code_hash, validation_status=candidate.validation.validation_status,
                execution_status=_summary_execution_status(summary), trials=records,
                feasible_count=sum(r["feasible"] for r in records), executed_count=len(records),
                failure_type_breakdown=_trial_failure_breakdown(metrics), fallback_used=False, **asdict(summary))


def _invoke_candidate(
    candidate: LoadedOperator,
    args: tuple,
    timeout_ms: float,
) -> CandidateExecutionResult:
    callable_obj = candidate.callable_obj
    if isinstance(callable_obj, CandidateProxy):
        return callable_obj.execute(args, timeout_ms=timeout_ms)
    if callable_obj is None:
        return CandidateExecutionResult(
            status="runtime_error",
            runtime_ms=0.0,
            error_message="Candidate callable is unavailable",
        )

    started = perf_counter()
    try:
        result = callable_obj(*args)
    except Exception as exc:  # noqa: BLE001 - trusted in-memory test compatibility.
        return CandidateExecutionResult(
            status="runtime_error",
            runtime_ms=(perf_counter() - started) * 1000.0,
            error_message=f"{type(exc).__name__}: {exc}",
        )
    runtime_ms = (perf_counter() - started) * 1000.0
    if runtime_ms > timeout_ms:
        return CandidateExecutionResult(
            status="timeout",
            runtime_ms=runtime_ms,
            error_message=f"Candidate exceeded {timeout_ms:g} ms timeout",
        )
    return CandidateExecutionResult(
        status="success", runtime_ms=runtime_ms, result=result
    )


def _summary_execution_status(summary) -> str:
    if summary.timeout_rate > 0.0:
        return "timeout"
    if summary.error_rate > 0.0:
        return "runtime_error"
    if summary.invalid_solution_rate > 0.0:
        return "invalid_solution"
    return "success"


def _trial_failure_breakdown(trials: Sequence[TrialMetric]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for trial in trials:
        if trial.timeout:
            counts["timeout"] += 1
        elif trial.error:
            counts["runtime_error"] += 1
        elif trial.invalid_solution:
            counts["invalid_solution"] += 1
        else:
            counts["success"] += 1
    return dict(counts)


def _is_valid_partial_solution(solution, instance: Instance) -> bool:
    return (
        isinstance(solution, MultiRobotSolution)
        and isinstance(solution.routes, list)
        and len(solution.routes) == instance.robot_count
        and all(
            isinstance(route, list)
            and all(type(task_id) is int for task_id in route)
            for route in solution.routes
        )
    )


def _is_valid_complete_solution(solution, instance: Instance) -> bool:
    if not _is_valid_partial_solution(solution, instance):
        return False
    try:
        return is_solution_complete(solution, instance)
    except (TypeError, ValueError, AttributeError):
        return False


def _deterministic_destroy(
    solution: MultiRobotSolution,
    evaluation: SolutionEvaluation,
    *,
    remove_count: int,
) -> tuple[MultiRobotSolution, List[int]]:
    if not evaluation.per_robot_costs:
        return clone_solution(solution), []
    bottleneck = int(max(range(len(evaluation.per_robot_costs)), key=evaluation.per_robot_costs.__getitem__))
    routes = [list(route) for route in solution.routes]
    route = routes[bottleneck]
    removed = route[-remove_count:] if remove_count <= len(route) else list(route)
    keep = set(removed)
    route = [task for task in route if task not in keep]
    routes[bottleneck] = route
    return MultiRobotSolution(routes=routes), removed


def _bottleneck_route(evaluation: SolutionEvaluation) -> int:
    if not evaluation.per_robot_costs:
        return 0
    return int(max(range(len(evaluation.per_robot_costs)), key=evaluation.per_robot_costs.__getitem__))


def _fixed_greedy_repair(
    partial_solution: MultiRobotSolution,
    removed_tasks: Sequence[int],
    evaluator: MultiRobotSolutionEvaluator,
) -> MultiRobotSolution:
    routes = [list(route) for route in partial_solution.routes]
    current_eval = evaluator.evaluate_partial(MultiRobotSolution(routes=routes))
    costs = list(current_eval.per_robot_costs)

    for task_id in removed_tasks:
        best_robot = 0
        best_idx = 0
        best_score = float("inf")
        for robot, route in enumerate(routes):
            others = max((c for idx, c in enumerate(costs) if idx != robot), default=0.0)
            for idx in range(len(route) + 1):
                candidate = list(route)
                candidate.insert(idx, task_id)
                route_eval = evaluator.route_evaluator.evaluate_route(candidate)
                score = max(others, route_eval.total_cost)
                if score < best_score:
                    best_robot = robot
                    best_idx = idx
                    best_score = score
        routes[best_robot].insert(best_idx, task_id)
        costs[best_robot] = evaluator.route_evaluator.evaluate_route(routes[best_robot]).total_cost

    return MultiRobotSolution(routes=routes)
