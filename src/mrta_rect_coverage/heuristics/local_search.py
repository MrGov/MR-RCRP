"""Simple and stronger local search procedures."""
from __future__ import annotations

from typing import Iterable, Tuple

from ..core.models import MultiRobotSolution, SolutionEvaluation
from ..core.solution_evaluator import MultiRobotSolutionEvaluator
from .neighborhood import (
    apply_relocate,
    apply_swap,
    apply_two_opt,
    iter_bottleneck_relocates,
    iter_inter_route_relocates,
    iter_inter_route_swaps,
    iter_intra_route_swaps,
    iter_intra_route_two_opt,
)


def _improving_first(
    current_solution: MultiRobotSolution,
    current_evaluation: SolutionEvaluation,
    evaluator: MultiRobotSolutionEvaluator,
    candidates: Iterable[MultiRobotSolution],
) -> Tuple[MultiRobotSolution, SolutionEvaluation, bool]:
    for candidate_solution in candidates:
        candidate_evaluation = evaluator.evaluate(candidate_solution)
        if candidate_evaluation.makespan + 1e-9 < current_evaluation.makespan:
            return candidate_solution, candidate_evaluation, True
    return current_solution, current_evaluation, False


def run_simple_inter_route_local_search(
    initial_solution: MultiRobotSolution,
    evaluator: MultiRobotSolutionEvaluator,
    max_iterations: int = 100,
) -> Tuple[MultiRobotSolution, SolutionEvaluation]:
    """Perform a greedy improving inter-route relocate search."""

    current_solution = initial_solution
    current_evaluation = evaluator.evaluate(current_solution)

    for _ in range(max_iterations):
        improved = False
        for move in iter_inter_route_relocates(current_solution):
            candidate_solution = apply_relocate(current_solution, move)
            candidate_evaluation = evaluator.evaluate(candidate_solution)
            if candidate_evaluation.makespan + 1e-9 < current_evaluation.makespan:
                current_solution = candidate_solution
                current_evaluation = candidate_evaluation
                improved = True
                break
        if not improved:
            break
    return current_solution, current_evaluation


def run_stronger_local_search(
    initial_solution: MultiRobotSolution,
    evaluator: MultiRobotSolutionEvaluator,
    max_iterations: int = 100,
) -> Tuple[MultiRobotSolution, SolutionEvaluation]:
    """Apply a richer neighborhood portfolio with bottleneck-focused refinement."""

    current_solution = initial_solution
    current_evaluation = evaluator.evaluate(current_solution)

    for _ in range(max_iterations):
        improved = False
        neighborhoods = [
            (iter_inter_route_relocates, apply_relocate),
            (iter_intra_route_swaps, apply_swap),
            (iter_intra_route_two_opt, apply_two_opt),
            (iter_inter_route_swaps, apply_swap),
        ]

        bottleneck_robot = int(
            max(range(len(current_evaluation.per_robot_costs)), key=current_evaluation.per_robot_costs.__getitem__)
        ) if current_evaluation.per_robot_costs else 0

        # Problem-specific intensification: aggressively remove from the critical route.
        for move in iter_bottleneck_relocates(current_solution, bottleneck_robot=bottleneck_robot):
            candidate_solution = apply_relocate(current_solution, move)
            candidate_evaluation = evaluator.evaluate(candidate_solution)
            if candidate_evaluation.makespan + 1e-9 < current_evaluation.makespan:
                current_solution = candidate_solution
                current_evaluation = candidate_evaluation
                improved = True
                break

        if improved:
            continue

        for iterator_fn, apply_fn in neighborhoods:
            for move in iterator_fn(current_solution):
                candidate_solution = apply_fn(current_solution, move)
                candidate_evaluation = evaluator.evaluate(candidate_solution)
                if candidate_evaluation.makespan + 1e-9 < current_evaluation.makespan:
                    current_solution = candidate_solution
                    current_evaluation = candidate_evaluation
                    improved = True
                    break
            if improved:
                break

        if not improved:
            break

    return current_solution, current_evaluation
