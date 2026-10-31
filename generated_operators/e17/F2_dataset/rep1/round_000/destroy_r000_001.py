from __future__ import annotations

import math

from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import DestroyResult


def destroy(solution, context, rng) -> DestroyResult:
    """
    Seed removal with an isolated task from a costly route, then remove nearby
    rectangles across all robots so repair can reconstruct geographic ownership.
    """
    instance = context.instance
    routes = [list(route) for route in solution.routes]
    task_by_id = {task.task_id: task for task in instance.tasks}
    remove_count = min(context.remove_count, instance.task_count)

    if remove_count <= 0:
        return DestroyResult(
            partial_solution=MultiRobotSolution(routes=routes),
            removed_tasks=[],
            note="No tasks requested for removal."
        )

    depot_x, depot_y = instance.depot
    costs = list(context.per_robot_costs)
    makespan = max(float(context.route_costs_makespan), 1e-12)
    all_ids = [task_id for route in routes for task_id in route]

    def center(task_id):
        task = task_by_id[task_id]
        return ((task.x_left + task.x_right) * 0.5,
                (task.y_bottom + task.y_top) * 0.5)

    def distance(task_a, task_b):
        ax, ay = center(task_a)
        bx, by = center(task_b)
        return abs(ax - bx) + abs(ay - by)

    xs = [center(task_id)[0] for task_id in all_ids]
    ys = [center(task_id)[1] for task_id in all_ids]
    spatial_scale = max(
        (max(xs) - min(xs)) + (max(ys) - min(ys)) if all_ids else 0.0,
        1.0
    )

    locations = {}
    for route_id, route in enumerate(routes):
        for position, task_id in enumerate(route):
            locations[task_id] = (route_id, position)

    seed_candidates = []
    for route_id, route in enumerate(routes):
        route_cost = costs[route_id] if route_id < len(costs) else 0.0
        pressure = 0.25 + max(0.0, route_cost / makespan) ** 3

        for position, task_id in enumerate(route):
            task_center = center(task_id)
            neighbor_distances = []
            if position > 0:
                neighbor_distances.append(distance(task_id, route[position - 1]))
            else:
                neighbor_distances.append(
                    abs(task_center[0] - depot_x) + abs(task_center[1] - depot_y)
                )
            if position + 1 < len(route):
                neighbor_distances.append(distance(task_id, route[position + 1]))
            else:
                neighbor_distances.append(
                    abs(task_center[0] - depot_x) + abs(task_center[1] - depot_y)
                )

            local_isolation = sum(neighbor_distances) / max(1, len(neighbor_distances))
            depot_distance = abs(task_center[0] - depot_x) + abs(task_center[1] - depot_y)
            seed_score = pressure * (local_isolation + 0.20 * depot_distance + 1e-9)
            seed_score *= 0.90 + 0.20 * rng.random()
            seed_candidates.append((seed_score, task_id))

    seed_candidates.sort(reverse=True)
    seed_pool_size = min(len(seed_candidates), max(2, int(math.sqrt(len(seed_candidates))) + 1))
    seed_pool = seed_candidates[:seed_pool_size]
    seed = seed_pool[rng.randrange(len(seed_pool))][1]

    selected = [seed]
    selected_set = {seed}
    seed_task = task_by_id[seed]
    seed_aspect = math.log(max(seed_task.width, 1e-12) / max(seed_task.height, 1e-12))

    while len(selected) < remove_count:
        ranked = []
        selected_centers = [center(task_id) for task_id in selected]
        cluster_x = sum(point[0] for point in selected_centers) / len(selected_centers)
        cluster_y = sum(point[1] for point in selected_centers) / len(selected_centers)

        for task_id in all_ids:
            if task_id in selected_set:
                continue

            task = task_by_id[task_id]
            task_x, task_y = center(task_id)
            cluster_distance = (abs(task_x - cluster_x) + abs(task_y - cluster_y)) / spatial_scale
            seed_distance = distance(seed, task_id) / spatial_scale
            aspect = math.log(max(task.width, 1e-12) / max(task.height, 1e-12))
            aspect_gap = min(abs(aspect - seed_aspect), 4.0) / 4.0

            route_id, _ = locations[task_id]
            route_cost = costs[route_id] if route_id < len(costs) else 0.0
            route_pressure = max(0.0, route_cost / makespan)
            different_robot_bonus = 0.0
            seed_route = locations[seed][0]
            if route_id != seed_route:
                different_robot_bonus = 0.18

            relatedness = (
                1.60 / (0.08 + cluster_distance)
                + 0.70 / (0.08 + seed_distance)
                + 0.35 * (1.0 - aspect_gap)
                + 0.30 * route_pressure
                + different_robot_bonus
            )
            relatedness *= 0.92 + 0.16 * rng.random()
            ranked.append((relatedness, task_id))

        if not ranked:
            break

        ranked.sort(reverse=True)
        pool_size = min(len(ranked), max(2, int(math.sqrt(len(ranked))) + 1))
        chosen = ranked[rng.randrange(pool_size)][1]
        selected.append(chosen)
        selected_set.add(chosen)

    if len(selected_set) < remove_count:
        fallback = [task_id for task_id in all_ids if task_id not in selected_set]
        rng.shuffle(fallback)
        selected_set.update(fallback[:remove_count - len(selected_set)])

    removed_tasks = [
        task_id for route in routes for task_id in route if task_id in selected_set
    ]
    partial_routes = [
        [task_id for task_id in route if task_id not in selected_set]
        for route in routes
    ]

    return DestroyResult(
        partial_solution=MultiRobotSolution(routes=partial_routes),
        removed_tasks=removed_tasks,
        note="Removed a spatially related cluster spanning robot territories, seeded from an isolated task on a costly route."
    )
