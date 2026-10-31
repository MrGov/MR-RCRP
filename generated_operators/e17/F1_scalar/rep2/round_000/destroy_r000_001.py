from __future__ import annotations

import math

from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import DestroyResult


def destroy(solution, context, rng) -> DestroyResult:
    """
    Identify route-local geometric outliers using rectangle centers, distance
    from the route centroid, and logarithmic aspect-ratio deviation.
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
    costs = list(context.per_robot_costs)
    scale = max(context.route_costs_makespan, max(costs, default=0.0), 1e-12)
    ranked = []

    for robot_id, route in enumerate(routes):
        if not route:
            continue

        features = []
        for task_id in route:
            task = task_by_id[task_id]
            center_x = 0.5 * (task.x_left + task.x_right)
            center_y = 0.5 * (task.y_bottom + task.y_top)
            aspect = math.log(max(task.width, 1e-12) / max(task.height, 1e-12))
            features.append((task_id, center_x, center_y, aspect))

        count = len(features)
        mean_x = sum(item[1] for item in features) / count
        mean_y = sum(item[2] for item in features) / count
        mean_aspect = sum(item[3] for item in features) / count

        spatial_distances = [
            abs(item[1] - mean_x) + abs(item[2] - mean_y)
            for item in features
        ]
        aspect_distances = [abs(item[3] - mean_aspect) for item in features]
        spatial_scale = max(sum(spatial_distances) / count, 1e-12)
        aspect_scale = max(sum(aspect_distances) / count, 1e-12)

        route_cost = costs[robot_id] if robot_id < len(costs) else 0.0
        critical_bonus = route_cost / scale

        for index, item in enumerate(features):
            task_id = item[0]
            spatial_outlier = spatial_distances[index] / spatial_scale
            aspect_outlier = aspect_distances[index] / aspect_scale
            isolation_bonus = 0.0

            if count > 1:
                nearest = min(
                    abs(item[1] - other[1]) + abs(item[2] - other[2])
                    for other in features
                    if other[0] != task_id
                )
                isolation_bonus = nearest / spatial_scale

            score = (
                1.8 * spatial_outlier
                + 1.2 * aspect_outlier
                + 0.5 * isolation_bonus
                + 0.25 * critical_bonus
                + rng.random() * 1e-9
            )
            ranked.append((score, task_id))

    ranked.sort(key=lambda item: item[0], reverse=True)
    removed = [task_id for _, task_id in ranked[:target]]
    removed_set = set(removed)
    partial_routes = [
        [task_id for task_id in route if task_id not in removed_set]
        for route in routes
    ]

    return DestroyResult(
        partial_solution=MultiRobotSolution(routes=partial_routes),
        removed_tasks=removed,
        note="Removed route-local position and aspect-ratio outliers."
    )
