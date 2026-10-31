from __future__ import annotations

import math

from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import DestroyResult


def destroy(solution, context, rng) -> DestroyResult:
    """
    Remove tasks offering the greatest approximate marginal relief, emphasizing
    routes at or near the current makespan while retaining limited randomness.
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

    task_map = {task.task_id: task for task in instance.tasks}
    costs = list(context.per_robot_costs)
    makespan = max(float(context.route_costs_makespan), max(costs, default=0.0), 1e-12)
    sweep_width = max(float(instance.sweep_width), 1e-12)
    sweep_speed = max(float(instance.sweep_speed), 1e-12)
    travel_speed = max(float(instance.travel_speed), 1e-12)
    turning_time = max(float(instance.turning_time), 0.0)

    depot = instance.depot
    if isinstance(depot, (tuple, list)) and len(depot) >= 2:
        depot_point = (float(depot[0]), float(depot[1]))
    else:
        depot_point = (
            float(getattr(depot, "x", getattr(depot, "x_coord", 0.0))),
            float(getattr(depot, "y", getattr(depot, "y_coord", 0.0)))
        )

    def center(task):
        return (
            0.5 * (float(task.x_left) + float(task.x_right)),
            0.5 * (float(task.y_bottom) + float(task.y_top))
        )

    def manhattan(a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def processing(task):
        width = max(float(task.width), 0.0)
        height = max(float(task.height), 0.0)
        horizontal_passes = max(1, int(math.ceil(height / sweep_width)))
        vertical_passes = max(1, int(math.ceil(width / sweep_width)))
        horizontal = (horizontal_passes * width) / sweep_speed + (horizontal_passes - 1) * turning_time
        vertical = (vertical_passes * height) / sweep_speed + (vertical_passes - 1) * turning_time
        return min(horizontal, vertical)

    candidates = {}
    for route_id, route in enumerate(routes):
        route_cost = costs[route_id] if route_id < len(costs) else 0.0
        ratio = max(0.0, float(route_cost) / makespan)
        pressure = 1.0 + 4.0 * ratio * ratio
        if ratio >= 0.95:
            pressure += 2.0

        for position, task_id in enumerate(route):
            task = task_map.get(task_id)
            if task is None:
                base = pressure
            else:
                current = center(task)
                previous = depot_point
                following = depot_point
                if position > 0 and route[position - 1] in task_map:
                    previous = center(task_map[route[position - 1]])
                if position + 1 < len(route) and route[position + 1] in task_map:
                    following = center(task_map[route[position + 1]])

                detour = max(
                    0.0,
                    manhattan(previous, current)
                    + manhattan(current, following)
                    - manhattan(previous, following)
                ) / travel_speed
                workload = processing(task)
                width = max(float(task.width), 1e-12)
                height = max(float(task.height), 1e-12)
                aspect = max(width / height, height / width)
                long_bonus = workload * min(math.log1p(aspect), 3.0) * 0.12
                base = pressure * (workload + detour + long_bonus)

            score = base * (0.90 + 0.20 * rng.random())
            old = candidates.get(task_id)
            if old is None or score > old:
                candidates[task_id] = score

    ranked = sorted(candidates, key=lambda task_id: (-candidates[task_id], str(task_id)))
    removed = ranked[:target]
    removed_set = set(removed)
    new_routes = [[task_id for task_id in route if task_id not in removed_set] for route in routes]

    return DestroyResult(
        partial_solution=MultiRobotSolution(routes=new_routes),
        removed_tasks=removed,
        note="Removed bottleneck-weighted tasks with high estimated processing and marginal travel relief."
    )
