from __future__ import annotations

import math

from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import DestroyResult


def destroy(solution, context, rng) -> DestroyResult:
    """
    Remove expensive tasks primarily from bottleneck routes, creating strong
    opportunities for the repair operator to rebalance work across robots.
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
    all_ids = [task_id for route in routes for task_id in route]
    costs = list(context.per_robot_costs)
    makespan = max(context.route_costs_makespan, max(costs, default=0.0), 1e-12)
    depot_x = getattr(instance.depot, "x", 0.0)
    depot_y = getattr(instance.depot, "y", 0.0)
    sweep_width = max(instance.sweep_width, 1e-12)
    sweep_speed = max(instance.sweep_speed, 1e-12)
    travel_speed = max(instance.travel_speed, 1e-12)

    candidates = []
    for robot_id, route in enumerate(routes):
        route_cost = costs[robot_id] if robot_id < len(costs) else 0.0
        pressure = route_cost / makespan
        route_size = max(len(route), 1)

        for position, task_id in enumerate(route):
            task = task_by_id[task_id]
            cx = 0.5 * (task.x_left + task.x_right)
            cy = 0.5 * (task.y_bottom + task.y_top)
            depot_time = (abs(cx - depot_x) + abs(cy - depot_y)) / travel_speed

            horizontal_passes = max(1, int(math.ceil(task.height / sweep_width)))
            vertical_passes = max(1, int(math.ceil(task.width / sweep_width)))
            horizontal_length = horizontal_passes * task.width
            vertical_length = vertical_passes * task.height
            processing_time = min(horizontal_length, vertical_length) / sweep_speed
            processing_time += max(0, min(horizontal_passes, vertical_passes) - 1) * instance.turning_time

            edge_exposure = 1.0 if position == 0 or position == len(route) - 1 else 0.0
            scarcity = 1.0 / route_size
            jitter = rng.random() * 0.08
            score = (
                5.0 * pressure
                + 0.35 * math.log1p(processing_time)
                + 0.15 * math.log1p(depot_time)
                + 0.20 * edge_exposure
                + 0.10 * scarcity
                + jitter
            )
            candidates.append((score, pressure, rng.random(), task_id))

    candidates.sort(reverse=True)
    removed = []
    removed_set = set()
    for _, _, _, task_id in candidates:
        if task_id not in removed_set:
            removed.append(task_id)
            removed_set.add(task_id)
            if len(removed) == target:
                break

    if len(removed) < target:
        remaining = [task_id for task_id in all_ids if task_id not in removed_set]
        rng.shuffle(remaining)
        for task_id in remaining:
            removed.append(task_id)
            removed_set.add(task_id)
            if len(removed) == target:
                break

    partial_routes = [
        [task_id for task_id in route if task_id not in removed_set]
        for route in routes
    ]
    return DestroyResult(
        partial_solution=MultiRobotSolution(routes=partial_routes),
        removed_tasks=removed,
        note="Removed tasks under combined bottleneck pressure, processing burden, and depot exposure."
    )
