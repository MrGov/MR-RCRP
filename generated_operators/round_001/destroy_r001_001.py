from __future__ import annotations

import math

from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import DestroyResult


def destroy(solution, context, rng) -> DestroyResult:
    """
    Select a disruptive seed on a critical route, then remove related tasks using
    spatial proximity, sweep orientation, aspect ratio, and route criticality.
    """
    instance = context.instance
    target = min(context.remove_count, instance.task_count)
    original_routes = [list(route) for route in solution.routes]

    if target <= 0:
        return DestroyResult(
            partial_solution=MultiRobotSolution(routes=original_routes),
            removed_tasks=[],
            note="No tasks requested for removal."
        )

    tasks = list(instance.tasks)
    task_by_id = {task.task_id: task for task in tasks}
    locations = {}
    ordered_ids = []
    for route_id, route in enumerate(original_routes):
        for pos, task_id in enumerate(route):
            locations[task_id] = (route_id, pos)
            ordered_ids.append(task_id)

    costs = list(context.per_robot_costs)
    makespan = max(float(context.route_costs_makespan), 1e-12)
    sweep_width = max(float(instance.sweep_width), 1e-12)
    sweep_speed = max(float(instance.sweep_speed), 1e-12)
    travel_speed = max(float(instance.travel_speed), 1e-12)
    turning_time = max(float(instance.turning_time), 0.0)

    depot = instance.depot
    if hasattr(depot, "x") and hasattr(depot, "y"):
        depot_point = (float(depot.x), float(depot.y))
    else:
        depot_point = (float(depot[0]), float(depot[1]))

    def center(task):
        return (
            0.5 * (float(task.x_left) + float(task.x_right)),
            0.5 * (float(task.y_bottom) + float(task.y_top)),
        )

    def distance(a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def features(task):
        width = max(float(task.width), 1e-12)
        height = max(float(task.height), 1e-12)
        h_passes = max(1, int(math.ceil(height / sweep_width)))
        v_passes = max(1, int(math.ceil(width / sweep_width)))
        h_time = (width * h_passes + height) / sweep_speed + max(0, h_passes - 1) * turning_time
        v_time = (height * v_passes + width) / sweep_speed + max(0, v_passes - 1) * turning_time
        return {
            "center": center(task),
            "aspect": math.log(width / height),
            "preferred": 0 if h_time <= v_time else 1,
            "processing": min(h_time, v_time),
            "mode_gap": abs(h_time - v_time),
        }

    feature = {task.task_id: features(task) for task in tasks}
    valid_ids = [task_id for task_id in ordered_ids if task_id in feature]

    if not valid_ids:
        return DestroyResult(
            partial_solution=MultiRobotSolution(routes=original_routes),
            removed_tasks=[],
            note="No removable task identifiers were found."
        )

    xs = [feature[task_id]["center"][0] for task_id in valid_ids]
    ys = [feature[task_id]["center"][1] for task_id in valid_ids]
    spatial_scale = max(max(xs) - min(xs) + max(ys) - min(ys), 1.0)

    seed_scores = []
    for task_id in valid_ids:
        route_id, pos = locations[task_id]
        route = original_routes[route_id]
        point = feature[task_id]["center"]
        prev_point = depot_point if pos == 0 else feature.get(route[pos - 1], {"center": depot_point})["center"]
        next_point = depot_point if pos + 1 == len(route) else feature.get(route[pos + 1], {"center": depot_point})["center"]
        detour = max(0.0, distance(prev_point, point) + distance(point, next_point) - distance(prev_point, next_point)) / travel_speed
        route_cost = float(costs[route_id]) if route_id < len(costs) else 0.0
        criticality = max(0.0, route_cost / makespan)

        if len(route) > 1:
            mean_distance = sum(
                distance(point, feature[other]["center"])
                for other in route
                if other != task_id and other in feature
            ) / max(1, sum(1 for other in route if other != task_id and other in feature))
        else:
            mean_distance = distance(point, depot_point)

        outlier = mean_distance / spatial_scale
        f = feature[task_id]
        score = (
            1.25 * criticality * criticality
            + 0.75 * outlier
            + 0.60 * detour / max(1.0, makespan)
            + 0.18 * f["processing"] / max(1.0, makespan)
            + 0.14 * f["mode_gap"] / max(1.0, makespan)
        )
        score *= 0.99 + 0.02 * rng.random()
        seed_scores.append((score, task_id))

    seed_scores.sort(reverse=True)
    seed_pool = seed_scores[:max(1, min(3, len(seed_scores)))]
    seed = seed_pool[int(rng.random() * len(seed_pool))][1]
    selected = [seed]
    selected_set = {seed}
    seed_route, seed_pos = locations[seed]

    while len(selected) < target:
        candidates = []
        for task_id in valid_ids:
            if task_id in selected_set:
                continue
            route_id, pos = locations[task_id]
            f = feature[task_id]

            nearest_spatial = min(
                distance(f["center"], feature[chosen]["center"]) / spatial_scale
                for chosen in selected
            )
            nearest_aspect = min(
                abs(f["aspect"] - feature[chosen]["aspect"])
                for chosen in selected
            )
            orientation_difference = min(
                float(f["preferred"] != feature[chosen]["preferred"])
                for chosen in selected
            )
            adjacency = min(
                abs(pos - locations[chosen][1])
                for chosen in selected
                if locations[chosen][0] == route_id
            ) if any(locations[chosen][0] == route_id for chosen in selected) else len(original_routes[route_id]) + 2

            route_cost = float(costs[route_id]) if route_id < len(costs) else 0.0
            criticality = max(0.0, route_cost / makespan)
            same_seed_route = float(route_id == seed_route)
            seed_neighbour = float(route_id == seed_route and abs(pos - seed_pos) <= 2)

            relatedness = (
                1.30 * nearest_spatial
                + 0.28 * min(nearest_aspect, 4.0)
                + 0.22 * orientation_difference
                + 0.08 * min(adjacency, 6)
                - 0.55 * criticality
                - 0.20 * same_seed_route
                - 0.16 * seed_neighbour
            )
            relatedness *= 0.985 + 0.03 * rng.random()
            candidates.append((relatedness, task_id))

        if not candidates:
            break

        candidates.sort(key=lambda item: item[0])
        rank_limit = min(len(candidates), max(2, int(math.sqrt(len(candidates))) + 1))
        rank = int((rng.random() ** 2) * rank_limit)
        chosen = candidates[rank][1]
        selected.append(chosen)
        selected_set.add(chosen)

    if len(selected) < target:
        for task_id in ordered_ids:
            if task_id not in selected_set:
                selected.append(task_id)
                selected_set.add(task_id)
                if len(selected) == target:
                    break

    new_routes = [
        [task_id for task_id in route if task_id not in selected_set]
        for route in original_routes
    ]

    return DestroyResult(
        partial_solution=MultiRobotSolution(routes=new_routes),
        removed_tasks=selected,
        note="Critical-route spatial cluster destroy for coordinated route reassignment."
    )
