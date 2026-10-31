from __future__ import annotations

import math

from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import DestroyResult


def destroy(solution, context, rng) -> DestroyResult:
    """Create a spatially coherent destroy neighborhood around a critical outlier."""
    instance = context.instance
    routes = [list(route) for route in solution.routes]
    target = min(max(0, context.remove_count), instance.task_count)
    if target == 0:
        return DestroyResult(
            partial_solution=MultiRobotSolution(routes=routes),
            removed_tasks=[],
            note="route outlier cluster destroy removed no tasks",
        )

    tasks = {task.task_id: task for task in instance.tasks}
    costs = list(context.per_robot_costs)
    makespan = max(context.route_costs_makespan, max(costs, default=0.0), 1e-12)
    sweep_width = max(float(instance.sweep_width), 1e-12)
    sweep_speed = max(float(instance.sweep_speed), 1e-12)
    turning_time = max(float(instance.turning_time), 0.0)

    def features(task):
        cx = (task.x_left + task.x_right) * 0.5
        cy = (task.y_bottom + task.y_top) * 0.5
        width = max(float(task.width), 1e-12)
        height = max(float(task.height), 1e-12)
        aspect = math.log(width / height)
        h_lanes = max(1, int(math.ceil(height / sweep_width)))
        v_lanes = max(1, int(math.ceil(width / sweep_width)))
        h_time = h_lanes * width / sweep_speed + max(0, h_lanes - 1) * turning_time
        v_time = v_lanes * height / sweep_speed + max(0, v_lanes - 1) * turning_time
        process = min(h_time, v_time)
        return cx, cy, aspect, process

    all_ids = [task_id for route in routes for task_id in route]
    feature_map = {task_id: features(tasks[task_id]) for task_id in all_ids}
    xs = [feature_map[task_id][0] for task_id in all_ids]
    ys = [feature_map[task_id][1] for task_id in all_ids]
    aspects = [feature_map[task_id][2] for task_id in all_ids]
    x_scale = max(max(xs) - min(xs), 1.0)
    y_scale = max(max(ys) - min(ys), 1.0)
    aspect_scale = max(max(aspects) - min(aspects), 1.0)

    seed_candidates = []
    membership = {}
    for route_id, route in enumerate(routes):
        route_cost = costs[route_id] if route_id < len(costs) else 0.0
        pressure = max(0.0, route_cost / makespan)
        if not route:
            continue
        mean_x = sum(feature_map[t][0] for t in route) / len(route)
        mean_y = sum(feature_map[t][1] for t in route) / len(route)
        mean_a = sum(feature_map[t][2] for t in route) / len(route)
        for position, task_id in enumerate(route):
            membership[task_id] = (route_id, position)
            cx, cy, aspect, process = feature_map[task_id]
            spatial_outlier = abs(cx - mean_x) / x_scale + abs(cy - mean_y) / y_scale
            shape_outlier = abs(aspect - mean_a) / aspect_scale
            score = (0.35 + pressure * pressure) * (spatial_outlier + 0.65 * shape_outlier)
            score += pressure * process / max(sweep_width / sweep_speed, 1e-12)
            score *= 0.95 + 0.1 * rng.random()
            seed_candidates.append((score, task_id))

    seed_candidates.sort(reverse=True)
    seed_id = seed_candidates[0][1]
    seed_x, seed_y, seed_aspect, seed_process = feature_map[seed_id]
    seed_route, seed_position = membership[seed_id]

    ranked = []
    for task_id in all_ids:
        route_id, position = membership[task_id]
        cx, cy, aspect, process = feature_map[task_id]
        spatial = abs(cx - seed_x) / x_scale + abs(cy - seed_y) / y_scale
        shape = abs(aspect - seed_aspect) / aspect_scale
        sequence = abs(position - seed_position) / max(1, len(routes[route_id])) if route_id == seed_route else 1.0
        route_pressure = (costs[route_id] if route_id < len(costs) else 0.0) / makespan
        same_route_bonus = 0.42 if route_id == seed_route else 0.0
        process_similarity = abs(process - seed_process) / max(seed_process, process, 1e-12)
        relatedness = same_route_bonus + 0.40 / (1.0 + spatial)
        relatedness += 0.18 / (1.0 + shape) + 0.12 / (1.0 + sequence)
        relatedness += 0.18 * route_pressure - 0.08 * process_similarity
        relatedness *= 0.97 + 0.06 * rng.random()
        ranked.append((relatedness, task_id))

    ranked.sort(reverse=True)
    removed = [task_id for _, task_id in ranked[:target]]
    removed_set = set(removed)
    new_routes = [[task_id for task_id in route if task_id not in removed_set] for route in routes]
    return DestroyResult(
        partial_solution=MultiRobotSolution(routes=new_routes),
        removed_tasks=removed,
        note="removed a coherent geometry cluster seeded by a critical-route outlier",
    )
