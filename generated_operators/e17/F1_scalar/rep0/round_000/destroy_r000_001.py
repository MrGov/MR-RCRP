from __future__ import annotations

import math

from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import DestroyResult


def destroy(solution, context, rng) -> DestroyResult:
    """
    Shaw-style related removal using rectangular geometry and route load.
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
    owner = {}
    for robot_id, route in enumerate(routes):
        for task_id in route:
            owner[task_id] = robot_id

    valid_ids = [task_id for task_id in all_task_ids if task_id in tasks]
    if not valid_ids:
        return DestroyResult(
            partial_solution=MultiRobotSolution(routes=routes),
            removed_tasks=[],
            note="No removable task identifiers matched the instance."
        )

    min_x = min(float(tasks[task_id].x_left) for task_id in valid_ids)
    max_x = max(float(tasks[task_id].x_right) for task_id in valid_ids)
    min_y = min(float(tasks[task_id].y_bottom) for task_id in valid_ids)
    max_y = max(float(tasks[task_id].y_top) for task_id in valid_ids)
    spatial_scale = max((max_x - min_x) + (max_y - min_y), 1e-12)

    areas = [
        max(float(tasks[task_id].width) * float(tasks[task_id].height), 1e-12)
        for task_id in valid_ids
    ]
    area_scale = max(max(math.log1p(area) for area in areas), 1e-12)
    costs = list(context.per_robot_costs)
    max_cost = max(costs) if costs else 0.0

    def features(task_id):
        task = tasks[task_id]
        width = max(float(task.width), 1e-12)
        height = max(float(task.height), 1e-12)
        return (
            0.5 * (float(task.x_left) + float(task.x_right)),
            0.5 * (float(task.y_bottom) + float(task.y_top)),
            math.log(width / height),
            math.log1p(width * height)
        )

    feature_map = {task_id: features(task_id) for task_id in valid_ids}

    seed_weights = []
    for task_id in valid_ids:
        robot_id = owner.get(task_id, 0)
        route_cost = costs[robot_id] if robot_id < len(costs) else 0.0
        load_weight = 1.0 + (route_cost / max_cost if max_cost > 0.0 else 0.0)
        task = tasks[task_id]
        aspect = abs(feature_map[task_id][2])
        size = math.log1p(max(float(task.width) * float(task.height), 0.0))
        seed_weights.append(load_weight * (1.0 + 0.25 * aspect + 0.1 * size))

    total_weight = sum(seed_weights)
    draw = rng.random() * total_weight
    seed_id = valid_ids[-1]
    cumulative = 0.0
    for task_id, weight in zip(valid_ids, seed_weights):
        cumulative += weight
        if draw <= cumulative:
            seed_id = task_id
            break

    removed = [seed_id]
    removed_set = {seed_id}

    while len(removed) < target:
        reference_id = removed[rng.randrange(len(removed))]
        rx, ry, raspect, rarea = feature_map[reference_id]
        reference_owner = owner.get(reference_id, -1)
        ranked = []

        for task_id in valid_ids:
            if task_id in removed_set:
                continue
            cx, cy, aspect, area = feature_map[task_id]
            spatial = (abs(cx - rx) + abs(cy - ry)) / spatial_scale
            aspect_gap = abs(aspect - raspect)
            area_gap = abs(area - rarea) / area_scale
            same_route_discount = 0.0 if owner.get(task_id, -2) == reference_owner else 0.2
            relation = (
                1.0 * spatial
                + 0.35 * aspect_gap
                + 0.25 * area_gap
                + same_route_discount
                + rng.random() * 1e-9
            )
            ranked.append((relation, task_id))

        if not ranked:
            break
        ranked.sort(key=lambda item: item[0])
        restricted_size = max(1, int(math.ceil(math.sqrt(len(ranked)))))
        chosen_rank = int((rng.random() ** 2) * restricted_size)
        chosen_rank = min(chosen_rank, len(ranked) - 1)
        chosen_id = ranked[chosen_rank][1]
        removed.append(chosen_id)
        removed_set.add(chosen_id)

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
        note="Removed a geometry-related cluster using center, area, aspect ratio, route ownership, and load-biased seeding."
    )
