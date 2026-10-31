from __future__ import annotations

import math

from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import DestroyResult


def destroy(solution, context, rng) -> DestroyResult:
    instance = context.instance
    target = int(min(context.remove_count, instance.task_count))
    routes = [list(route) for route in solution.routes]

    if target <= 0:
        return DestroyResult(
            partial_solution=MultiRobotSolution(routes=routes),
            removed_tasks=[],
            note='No tasks requested for removal.'
        )

    task_by_id = {task.task_id: task for task in instance.tasks}
    sweep_width = max(float(instance.sweep_width), 1e-12)
    sweep_speed = max(float(instance.sweep_speed), 1e-12)
    travel_speed = max(float(instance.travel_speed), 1e-12)
    turning_time = float(instance.turning_time)
    makespan = max(float(context.route_costs_makespan), 1e-12)
    depot_x, depot_y = instance.depot

    candidates = []
    for robot_id, route in enumerate(routes):
        route_cost = float(context.per_robot_costs[robot_id])
        criticality = route_cost / makespan
        route_length = max(len(route), 1)

        for position, task_id in enumerate(route):
            task = task_by_id[task_id]
            width = max(float(task.width), 0.0)
            height = max(float(task.height), 0.0)

            horizontal_passes = max(1, int(math.ceil(height / sweep_width)))
            vertical_passes = max(1, int(math.ceil(width / sweep_width)))
            horizontal_cost = (
                horizontal_passes * width / sweep_speed
                + max(0, horizontal_passes - 1) * turning_time
            )
            vertical_cost = (
                vertical_passes * height / sweep_speed
                + max(0, vertical_passes - 1) * turning_time
            )
            processing_proxy = min(horizontal_cost, vertical_cost)

            center_x = 0.5 * (float(task.x_left) + float(task.x_right))
            center_y = 0.5 * (float(task.y_bottom) + float(task.y_top))
            depot_distance = abs(center_x - depot_x) + abs(center_y - depot_y)
            travel_proxy = 2.0 * depot_distance / travel_speed

            edge_factor = 1.0
            if position == 0 or position == len(route) - 1:
                edge_factor = 1.08

            score = (
                4.0 * criticality
                + criticality * (processing_proxy + 0.55 * travel_proxy) / makespan
                + 0.15 / route_length
            ) * edge_factor
            score += rng.random() * 1e-9
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
        note='Released costly and remote tasks from routes nearest the current makespan.'
    )
