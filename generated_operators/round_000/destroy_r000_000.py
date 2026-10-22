from __future__ import annotations

from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import DestroyResult


def destroy(solution, context, rng):
    routes = [list(route) for route in solution.routes]
    all_tasks = [task for route in routes for task in route]
    remove_count = min(max(1, context.remove_count), len(all_tasks)) if all_tasks else 0
    removed = all_tasks[:remove_count]
    removed_set = set(removed)
    new_routes = [[task for task in route if task not in removed_set] for route in routes]
    return DestroyResult(partial_solution=MultiRobotSolution(routes=new_routes), removed_tasks=removed, note="template candidate")
