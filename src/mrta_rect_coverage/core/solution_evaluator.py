"""Evaluation of complete multi-robot solutions."""
from __future__ import annotations

from typing import List

from .dp_evaluator import RouteDPEvaluator
from .models import Instance, MultiRobotSolution, SolutionEvaluation


class MultiRobotSolutionEvaluator:
    """Evaluate multi-robot solutions using per-route DP."""

    def __init__(self, route_evaluator: RouteDPEvaluator, *, instance: Instance):
        self._route_evaluator = route_evaluator
        self._robot_count = instance.robot_count
        self._task_ids = frozenset(task.task_id for task in instance.tasks)

    @property
    def route_evaluator(self) -> RouteDPEvaluator:
        """Expose the underlying route evaluator for advanced heuristics."""

        return self._route_evaluator

    def evaluate(self, solution: MultiRobotSolution) -> SolutionEvaluation:
        """Validate and evaluate a complete multi-robot solution."""

        self._validate_solution(solution, allow_missing=False)
        return self._evaluate_routes(solution)

    def evaluate_partial(self, solution: MultiRobotSolution) -> SolutionEvaluation:
        """Evaluate an ALNS partial state while preserving structural validity."""

        self._validate_solution(solution, allow_missing=True)
        return self._evaluate_routes(solution)

    def _validate_solution(
        self, solution: MultiRobotSolution, *, allow_missing: bool
    ) -> None:
        if len(solution.routes) != self._robot_count:
            raise ValueError(
                "solution route count must equal instance robot count: "
                f"expected {self._robot_count}, got {len(solution.routes)}"
            )

        assigned = [task_id for route in solution.routes for task_id in route]
        unknown = sorted(
            {
                task_id
                for task_id in assigned
                if type(task_id) is not int or task_id not in self._task_ids
            },
            key=repr,
        )
        if unknown:
            raise ValueError(f"solution contains unknown task ids: {unknown}")

        seen: set[int] = set()
        duplicates: set[int] = set()
        for task_id in assigned:
            if task_id in seen:
                duplicates.add(task_id)
            seen.add(task_id)
        if duplicates:
            raise ValueError(
                f"solution contains duplicate task ids: {sorted(duplicates)}"
            )

        if not allow_missing:
            missing = sorted(self._task_ids - seen)
            if missing:
                raise ValueError(f"solution is missing task ids: {missing}")

    def _evaluate_routes(
        self, solution: MultiRobotSolution
    ) -> SolutionEvaluation:
        """Evaluate routes after the appropriate feasibility contract passes."""

        route_evaluations = []
        per_robot_costs: List[float] = []
        for route in solution.routes:
            evaluation = self._route_evaluator.evaluate_route(route)
            route_evaluations.append(evaluation)
            per_robot_costs.append(evaluation.total_cost)

        makespan = max(per_robot_costs) if per_robot_costs else 0.0
        return SolutionEvaluation(
            per_robot_costs=per_robot_costs,
            route_evaluations=route_evaluations,
            makespan=makespan,
        )

