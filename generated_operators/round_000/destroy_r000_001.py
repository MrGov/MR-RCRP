from __future__ import annotations

import math

from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import DestroyResult


def destroy(solution, context, rng) -> DestroyResult:
    """
    Args:
        solution: MultiRobotSolution with .routes (List[List[int]])
        context: DestroyContext
        rng: random.Random instance
    Returns:
        DestroyResult
    """
    instance = context.instance
    routes = [list(route) for route in solution.routes]
    target = min(context.remove_count, instance.task_count)

    if target <= 0:
        return DestroyResult(
            partial_solution=MultiRobotSolution(routes=routes),
            removed_tasks=[],
            note="No tasks requested for mode-gap removal."
        )

    task_by_id = {task.task_id: task for task in instance.tasks}
    sweep_width = max(instance.sweep_width, 1e-12)
    sweep_speed = max(instance.sweep_speed, 1e-12)
    turning_time = instance.turning_time
    costs = list(context.per_robot_costs)
    makespan = max(context.route_costs_makespan, 1e-12)
    small_instance_weight = 1.5 if instance.task_count <= 16 else 0.75

    def sweep_estimates(task):
        horizontal_lanes = max(1, int(math.ceil(task.height / sweep_width)))
        vertical_lanes = max(1, int(math.ceil(task.width / sweep_width)))

        horizontal_length = (horizontal_lanes * task.width
                             + max(0, horizontal_lanes - 1) * sweep_width)
        vertical_length = (vertical_lanes * task.height
                           + max(0, vertical_lanes - 1) * sweep_width)

        horizontal_time = (horizontal_length / sweep_speed
                           + max(0, horizontal_lanes - 1) * turning_time)
        vertical_time = (vertical_length / sweep_speed
                         + max(0, vertical_lanes - 1) * turning_time)
        return horizontal_time, vertical_time

    def preferred_mode(task):
        horizontal_time, vertical_time = sweep_estimates(task)
        return 0 if horizontal_time <= vertical_time else 1

    candidates = []
    for robot_id, route in enumerate(routes):
        route_cost = costs[robot_id] if robot_id < len(costs) else 0.0
        criticality = route_cost / makespan

        for position, task_id in enumerate(route):
            task = task_by_id[task_id]
            horizontal_time, vertical_time = sweep_estimates(task)
            mode_gap = abs(horizontal_time - vertical_time)
            own_mode = 0 if horizontal_time <= vertical_time else 1

            mismatch = 0.0
            neighbor_count = 0
            if position > 0:
                neighbor_count += 1
                mismatch += float(own_mode != preferred_mode(task_by_id[route[position - 1]]))
            if position + 1 < len(route):
                neighbor_count += 1
                mismatch += float(own_mode != preferred_mode(task_by_id[route[position + 1]]))
            if neighbor_count:
                mismatch /= neighbor_count

            aspect = max(task.width, task.height) / max(min(task.width, task.height), 1e-12)
            score = (small_instance_weight * mode_gap * (1.0 + 0.9 * mismatch)
                     * (0.65 + 0.35 * criticality)
                     + 0.08 * aspect
                     + rng.random() * 1e-6)
            candidates.append((score, task_id))

    candidates.sort(reverse=True)
    removed_tasks = [task_id for _, task_id in candidates[:target]]
    removed_set = set(removed_tasks)
    partial_routes = [
        [task_id for task_id in route if task_id not in removed_set]
        for route in routes
    ]

    return DestroyResult(
        partial_solution=MultiRobotSolution(routes=partial_routes),
        removed_tasks=removed_tasks,
        note="Removed mode-sensitive tasks with large H/V gaps or neighboring orientation mismatch."
    )
