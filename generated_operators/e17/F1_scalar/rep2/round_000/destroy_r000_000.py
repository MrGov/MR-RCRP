from __future__ import annotations

import math

from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import DestroyResult


def destroy(solution, context, rng) -> DestroyResult:
    """
    Remove processing-heavy tasks preferentially from routes near the current
    makespan, while preserving the order and membership of retained tasks.
    """
    instance = context.instance
    routes = [list(route) for route in solution.routes]
    target = min(context.remove_count, instance.task_count)

    if target <= 0:
        return DestroyResult(
            partial_solution=MultiRobotSolution(routes=routes),
            removed_tasks=[],
            note="No tasks requested for removal."
        )

    task_by_id = {task.task_id: task for task in instance.tasks}
    costs = list(context.per_robot_costs)
    makespan = context.route_costs_makespan
    max_cost = max(costs, default=0.0)
    scale = max(makespan, max_cost, 1e-12)
    sweep_width = max(instance.sweep_width, 1e-12)
    sweep_speed = max(instance.sweep_speed, 1e-12)

    ranked = []
    for robot_id, route in enumerate(routes):
        route_cost = costs[robot_id] if robot_id < len(costs) else 0.0
        criticality = route_cost / scale
        route_size = max(len(route), 1)

        for position, task_id in enumerate(route):
            task = task_by_id[task_id]
            horizontal_passes = max(1, int(math.ceil(task.height / sweep_width)))
            vertical_passes = max(1, int(math.ceil(task.width / sweep_width)))
            horizontal_work = horizontal_passes * task.width
            vertical_work = vertical_passes * task.height
            approximate_processing = min(horizontal_work, vertical_work) / sweep_speed
            approximate_turns = min(horizontal_passes, vertical_passes) - 1
            approximate_processing += approximate_turns * instance.turning_time

            center_bias = 1.0 - abs((position + 0.5) / route_size - 0.5)
            jitter = rng.random() * 1e-9
            score = (
                4.0 * criticality
                + approximate_processing / scale
                + 0.05 * center_bias
                + jitter
            )
            ranked.append((score, task_id))

    ranked.sort(key=lambda item: item[0], reverse=True)
    removed = [task_id for _, task_id in ranked[:target]]
    removed_set = set(removed)
    partial_routes = [
        [task_id for task_id in route if task_id not in removed_set]
        for route in routes
    ]

    return DestroyResult(
        partial_solution=MultiRobotSolution(routes=partial_routes),
        removed_tasks=removed,
        note="Removed processing-heavy tasks from routes closest to the makespan."
    )
