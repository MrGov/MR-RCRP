from __future__ import annotations

import math

from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import DestroyResult


def destroy(solution, context, rng) -> DestroyResult:
    """
    Transfer-dominant bottleneck destroy. Tasks are scored by their approximate
    Manhattan bridge cost, depot distance, and membership in a critical route.
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

    def point_xy(point):
        if isinstance(point, (tuple, list)):
            return float(point[0]), float(point[1])
        for x_name, y_name in (("x", "y"), ("x_coord", "y_coord")):
            if hasattr(point, x_name) and hasattr(point, y_name):
                return float(getattr(point, x_name)), float(getattr(point, y_name))
        return 0.0, 0.0

    depot_xy = point_xy(instance.depot)

    def center(task_id):
        task = task_by_id[task_id]
        return (
            0.5 * (float(task.x_left) + float(task.x_right)),
            0.5 * (float(task.y_bottom) + float(task.y_top))
        )

    def manhattan(a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    max_cost = max(context.per_robot_costs, default=0.0)
    if max_cost <= 0.0:
        max_cost = 1.0

    sweep_width = max(float(instance.sweep_width), 1e-9)
    sweep_speed = max(float(instance.sweep_speed), 1e-9)
    turning_time = max(float(instance.turning_time), 0.0)

    scored = []
    for robot_id, route in enumerate(routes):
        route_cost = (
            float(context.per_robot_costs[robot_id])
            if robot_id < len(context.per_robot_costs)
            else 0.0
        )
        criticality = max(0.0, route_cost / max_cost)
        critical_weight = 0.25 + criticality * criticality

        for position, task_id in enumerate(route):
            task = task_by_id[task_id]
            current = center(task_id)
            previous = depot_xy if position == 0 else center(route[position - 1])
            following = depot_xy if position + 1 == len(route) else center(route[position + 1])

            bridge_saving = (
                manhattan(previous, current)
                + manhattan(current, following)
                - manhattan(previous, following)
            ) / max(float(instance.travel_speed), 1e-9)

            depot_exposure = manhattan(depot_xy, current) / max(
                float(instance.travel_speed), 1e-9
            )

            horizontal_passes = max(1, int(math.ceil(float(task.height) / sweep_width)))
            vertical_passes = max(1, int(math.ceil(float(task.width) / sweep_width)))
            horizontal_work = (
                float(task.width) * horizontal_passes / sweep_speed
                + max(0, horizontal_passes - 1) * turning_time
            )
            vertical_work = (
                float(task.height) * vertical_passes / sweep_speed
                + max(0, vertical_passes - 1) * turning_time
            )
            processing_floor = min(horizontal_work, vertical_work)

            base_score = (
                0.68 * max(0.0, bridge_saving)
                + 0.22 * depot_exposure
                + 0.10 * processing_floor
            ) * critical_weight

            # Mild randomization preserves the heuristic while diversifying ties.
            score = base_score * (0.90 + 0.20 * rng.random())
            scored.append((score, criticality, task_id))

    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    removed_tasks = [item[2] for item in scored[:target]]
    removed_set = set(removed_tasks)
    partial_routes = [
        [task_id for task_id in route if task_id not in removed_set]
        for route in routes
    ]

    return DestroyResult(
        partial_solution=MultiRobotSolution(routes=partial_routes),
        removed_tasks=removed_tasks,
        note="Removed critical-route tasks with large approximate Manhattan bridge and depot-transfer costs."
    )
