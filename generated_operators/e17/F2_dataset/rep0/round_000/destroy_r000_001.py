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
    depot_x, depot_y = instance.depot
    makespan = max(float(context.route_costs_makespan), 1e-12)

    def center(task):
        return (
            0.5 * (float(task.x_left) + float(task.x_right)),
            0.5 * (float(task.y_bottom) + float(task.y_top)),
        )

    def manhattan(a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def log_aspect(task):
        width = max(float(task.width), 1e-12)
        height = max(float(task.height), 1e-12)
        return math.log(width / height)

    ownership = {}
    seed_candidates = []
    for robot_id, route in enumerate(routes):
        route_criticality = float(context.per_robot_costs[robot_id]) / makespan
        points = [(depot_x, depot_y)]
        points.extend(center(task_by_id[task_id]) for task_id in route)
        points.append((depot_x, depot_y))

        for position, task_id in enumerate(route):
            ownership[task_id] = robot_id
            previous_point = points[position]
            current_point = points[position + 1]
            next_point = points[position + 2]
            detour = max(
                0.0,
                manhattan(previous_point, current_point)
                + manhattan(current_point, next_point)
                - manhattan(previous_point, next_point),
            )
            task = task_by_id[task_id]
            elongation = abs(log_aspect(task))
            score = (0.25 + route_criticality) * (1.0 + detour) * (1.0 + 0.12 * elongation)
            seed_candidates.append((task_id, score))

    total_weight = sum(score for _, score in seed_candidates)
    if total_weight > 0.0:
        draw = rng.random() * total_weight
        cumulative = 0.0
        seed_id = seed_candidates[-1][0]
        for task_id, score in seed_candidates:
            cumulative += score
            if cumulative >= draw:
                seed_id = task_id
                break
    else:
        seed_id = rng.choice([task_id for route in routes for task_id in route])

    removed_tasks = [seed_id]
    removed_set = {seed_id}
    seed_task = task_by_id[seed_id]
    seed_center = center(seed_task)
    seed_aspect = log_aspect(seed_task)
    seed_robot = ownership[seed_id]

    all_ids = [task_id for route in routes for task_id in route]
    while len(removed_tasks) < target:
        ranked = []
        cluster_centers = [center(task_by_id[task_id]) for task_id in removed_tasks]
        cluster_aspects = [log_aspect(task_by_id[task_id]) for task_id in removed_tasks]

        for task_id in all_ids:
            if task_id in removed_set:
                continue
            task = task_by_id[task_id]
            point = center(task)
            aspect = log_aspect(task)
            spatial_distance = min(manhattan(point, item) for item in cluster_centers)
            aspect_distance = min(abs(aspect - item) for item in cluster_aspects)
            seed_distance = manhattan(point, seed_center)
            route_bonus = 0.82 if ownership[task_id] == seed_robot else 1.0
            relation_score = route_bonus * (
                spatial_distance + 0.35 * seed_distance + 2.0 * aspect_distance
            )
            relation_score *= 1.0 + rng.random() * 0.04
            ranked.append((relation_score, task_id))

        ranked.sort()
        chosen_id = ranked[0][1]
        removed_tasks.append(chosen_id)
        removed_set.add(chosen_id)

    partial_routes = [
        [task_id for task_id in route if task_id not in removed_set]
        for route in routes
    ]

    return DestroyResult(
        partial_solution=MultiRobotSolution(routes=partial_routes),
        removed_tasks=removed_tasks,
        note='Removed a geometry-related cluster around a route-detour seed for joint reassignment.'
    )
