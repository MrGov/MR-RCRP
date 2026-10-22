"""Baseline solver pipeline."""
from __future__ import annotations

from typing import Callable, Tuple

from ..core.cost_matrix import CostMatrix
from ..core.dp_evaluator import RouteDPEvaluator
from ..core.models import Instance, MultiRobotSolution, SolutionEvaluation
from ..core.solution_evaluator import MultiRobotSolutionEvaluator
from ..core.state_generator import generate_all_states
from .constructors import round_robin_constructor, spatial_sort_constructor
from .local_search import run_simple_inter_route_local_search, run_stronger_local_search

ConstructorFn = Callable[[Instance], MultiRobotSolution]


def resolve_constructor(constructor: str | ConstructorFn) -> ConstructorFn:
    """Resolve a constructor name or callable into a constructor function."""

    if callable(constructor):
        return constructor
    key = constructor.strip().lower()
    mapping: dict[str, ConstructorFn] = {
        "spatial_sort": spatial_sort_constructor,
        "round_robin": round_robin_constructor,
    }
    if key not in mapping:
        raise ValueError(
            f"Unknown constructor '{constructor}'. Available: {', '.join(sorted(mapping))}"
        )
    return mapping[key]


def baseline_solve(
    instance: Instance,
    *,
    constructor: str | ConstructorFn = "spatial_sort",
    enable_local_search: bool = True,
    max_iterations: int = 100,
    use_stronger_local_search: bool = False,
) -> Tuple[MultiRobotSolution, SolutionEvaluation]:
    """Build, evaluate, and optionally improve a baseline solution."""

    states_by_task = generate_all_states(instance)
    cost_matrix = CostMatrix(
        instance.depot, states_by_task, travel_speed=instance.travel_speed
    )
    route_dp = RouteDPEvaluator(cost_matrix, states_by_task)
    evaluator = MultiRobotSolutionEvaluator(route_dp, instance=instance)

    initial_solution = resolve_constructor(constructor)(instance)
    initial_evaluation = evaluator.evaluate(initial_solution)

    if not enable_local_search:
        return initial_solution, initial_evaluation

    if use_stronger_local_search:
        improved_solution, improved_evaluation = run_stronger_local_search(
            initial_solution,
            evaluator,
            max_iterations=max_iterations,
        )
    else:
        improved_solution, improved_evaluation = run_simple_inter_route_local_search(
            initial_solution,
            evaluator,
            max_iterations=max_iterations,
        )

    if improved_evaluation.makespan + 1e-9 < initial_evaluation.makespan:
        return improved_solution, improved_evaluation
    return initial_solution, initial_evaluation
