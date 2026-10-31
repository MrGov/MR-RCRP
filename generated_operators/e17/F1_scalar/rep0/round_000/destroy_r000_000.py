from __future__ import annotations

import math

from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import DestroyResult


def destroy(solution, context, rng) -> DestroyResult:
    """
    Remove expensive, isolated tasks primarily from critical routes.
    """
    instance = context.instance
    routes = [list(route) for route in solution.routes]
    all_task_ids = [task_id for route in routes for task_id in route]
    target = min(context.remove_count, instance.task_count)

    if target <= 0:
        return DestroyResult(
            partial_solution=MultiRobotSolution(routes=routes),
            removed_tasks=[],
            note="No tasks requested for removal."
        )

    tasks = {task.task_id: task for task in instance.tasks}
    costs = list(context.per_robot_costs)
    max_cost = max(costs) if costs else 0.0
    mean_cost = sum(costs) / len(costs) if costs else 0.0
    sweep_width = max(float(instance.sweep_width), 1e-12)
    sweep_speed = max(float(instance.sweep_speed), 1e-12)
    travel_speed = max(float(instance.travel_speed), 1e-12)
    turning_time = float(instance.turning_time)

    def center(task):
        return (
            0.5 * (float(task.x_left) + float(task.x_right)),
            0.5 * (float(task.y_bottom) + float(task.y_top))
        )

    def processing_proxy(task):
        width = max(float(task.width), 0.0)
        height = max(float(task.height), 0.0)
        horizontal_passes = max(1, int(math.ceil(height / sweep_width)))
        vertical_passes = max(1, int(math.ceil(width / sweep_width)))
        horizontal = (
            horizontal_passes * width / sweep_speed
            + max(0, horizontal_passes - 1) * turning_time
        )
        vertical = (
            vertical_passes * height / sweep_speed
            + max(0, vertical_passes - 1) * turning_time
        )
        return min(horizontal, vertical)

    candidates = []
    for robot_id, route in enumerate(routes):
        route_cost = costs[robot_id] if robot_id < len(costs) else 0.0
        if max_cost > 0.0:
            criticality = route_cost / max_cost
        else:
            criticality = 1.0

        for position, task_id in enumerate(route):
            task = tasks.get(task_id)
            if task is None:
                continue

            cx, cy = center(task)
            depot_distance = (
                abs(cx - float(instance.depot[0]))
                + abs(cy - float(instance.depot[1]))
            ) / travel_speed

            neighbour_distances = []
            if position > 0 and route[position - 1] in tasks:
                px, py = center(tasks[route[position - 1]])
                neighbour_distances.append(abs(cx - px) + abs(cy - py))
            if position + 1 < len(route) and route[position + 1] in tasks:
                nx, ny = center(tasks[route[position + 1]])
                neighbour_distances.append(abs(cx - nx) + abs(cy - ny))

            isolation = (
                sum(neighbour_distances) / len(neighbour_distances)
                if neighbour_distances else depot_distance * travel_speed
            ) / travel_speed

            overload_bonus = max(0.0, route_cost - mean_cost)
            score = (
                4.0 * criticality
                + processing_proxy(task)
                + 0.35 * depot_distance
                + 0.45 * isolation
                + 0.25 * overload_bonus
                + rng.random() * 1e-9
            )
            candidates.append((score, criticality, task_id))

    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    removed = []
    removed_set = set()

    critical_candidates = [item for item in candidates if item[1] >= 1.0 - 1e-12]
    critical_quota = min(target, max(1, int(math.ceil(0.7 * target))))
    for _, _, task_id in critical_candidates:
        if len(removed) >= critical_quota:
            break
        if task_id not in removed_set:
            removed.append(task_id)
            removed_set.add(task_id)

    for _, _, task_id in candidates:
        if len(removed) >= target:
            break
        if task_id not in removed_set:
            removed.append(task_id)
            removed_set.add(task_id)

    if len(removed) < target:
        fallback = list(all_task_ids)
        rng.shuffle(fallback)
        for task_id in fallback:
            if len(removed) >= target:
                break
            if task_id not in removed_set:
                removed.append(task_id)
                removed_set.add(task_id)

    new_routes = [
        [task_id for task_id in route if task_id not in removed_set]
        for route in routes
    ]
    return DestroyResult(
        partial_solution=MultiRobotSolution(routes=new_routes),
        removed_tasks=removed,
        note="Removed costly and isolated tasks with a strong bias toward the current bottleneck routes."
    )
