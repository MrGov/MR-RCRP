from __future__ import annotations

import math
import statistics

from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import DestroyResult


def destroy(solution, context, rng) -> DestroyResult:
    """
    Target route-level geometric outliers whose removal may allow repair to
    form more spatially compact and shape-compatible robot assignments.
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
    candidates = []

    for robot_id, route in enumerate(routes):
        if not route:
            continue

        centers_x = []
        centers_y = []
        log_aspects = []
        areas = []
        for task_id in route:
            task = task_by_id[task_id]
            centers_x.append(0.5 * (task.x_left + task.x_right))
            centers_y.append(0.5 * (task.y_bottom + task.y_top))
            log_aspects.append(math.log(max(task.width, 1e-12) / max(task.height, 1e-12)))
            areas.append(max(task.width * task.height, 1e-12))

        median_x = statistics.median(centers_x)
        median_y = statistics.median(centers_y)
        median_aspect = statistics.median(log_aspects)
        median_area = statistics.median(areas)
        spatial_distances = [
            abs(x - median_x) + abs(y - median_y)
            for x, y in zip(centers_x, centers_y)
        ]
        spatial_scale = statistics.median(spatial_distances) if spatial_distances else 0.0
        spatial_scale = max(spatial_scale, 1.0)
        aspect_deviations = [abs(value - median_aspect) for value in log_aspects]
        aspect_scale = statistics.median(aspect_deviations) if aspect_deviations else 0.0
        aspect_scale = max(aspect_scale, 0.15)
        route_pressure = (costs[robot_id] if robot_id < len(costs) else 0.0) / makespan

        for index, task_id in enumerate(route):
            spatial_outlier = spatial_distances[index] / spatial_scale
            aspect_outlier = aspect_deviations[index] / aspect_scale
            area_outlier = abs(math.log(areas[index] / median_area))

            if len(route) > 1:
                nearest = min(
                    abs(centers_x[index] - centers_x[j]) + abs(centers_y[index] - centers_y[j])
                    for j in range(len(route))
                    if j != index
                )
                isolation = nearest / spatial_scale
            else:
                isolation = 1.0

            jitter = rng.random() * 0.12
            score = (
                1.75 * spatial_outlier
                + 1.25 * isolation
                + 1.10 * aspect_outlier
                + 0.35 * area_outlier
                + 0.40 * route_pressure
                + jitter
            )
            candidates.append((score, rng.random(), task_id))

    candidates.sort(reverse=True)
    removed = []
    removed_set = set()
    for _, _, task_id in candidates:
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
        note="Removed route-level spatial, isolation, area, and aspect-ratio outliers."
    )
