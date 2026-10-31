from __future__ import annotations

import math
from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import DestroyResult


def destroy(solution, context, rng) -> DestroyResult:
    instance = context.instance
    routes = [list(route) for route in solution.routes]
    count = min(context.remove_count, instance.task_count)
    if count <= 0:
        return DestroyResult(partial_solution=MultiRobotSolution(routes=routes), removed_tasks=[], note="No tasks requested for removal.")

    tasks = {task.task_id: task for task in instance.tasks}
    ranked = []
    for robot, route in enumerate(routes):
        if not route:
            continue
        centers = {}
        logs = {}
        for task_id in route:
            task = tasks[task_id]
            centers[task_id] = ((float(task.x_left) + float(task.x_right)) * 0.5, (float(task.y_bottom) + float(task.y_top)) * 0.5)
            w = max(float(task.width), 1e-9)
            h = max(float(task.height), 1e-9)
            logs[task_id] = abs(math.log(w / h))
        cx = sum(point[0] for point in centers.values()) / len(route)
        cy = sum(point[1] for point in centers.values()) / len(route)
        mean_shape = sum(logs.values()) / len(route)
        mean_dist = sum(math.hypot(point[0] - cx, point[1] - cy) for point in centers.values()) / len(route)
        route_cost = context.per_robot_costs[robot] if robot < len(context.per_robot_costs) else 0.0
        for position, task_id in enumerate(route):
            point = centers[task_id]
            spatial = math.hypot(point[0] - cx, point[1] - cy) / max(mean_dist, 1e-9)
            shape = abs(logs[task_id] - mean_shape) / max(mean_shape + 1.0, 1e-9)
            score = spatial + 0.45 * shape + 0.1 * route_cost / max(context.route_costs_makespan, 1e-9)
            ranked.append((score, rng.random(), robot, position, task_id))
    ranked.sort(reverse=True)
    chosen = {item[4] for item in ranked[:count]}
    kept = [[task_id for task_id in route if task_id not in chosen] for route in routes]
    removed = [task_id for route in routes for task_id in route if task_id in chosen]
    return DestroyResult(partial_solution=MultiRobotSolution(routes=kept), removed_tasks=removed, note="Removed route-relative geometric and shape outliers.")