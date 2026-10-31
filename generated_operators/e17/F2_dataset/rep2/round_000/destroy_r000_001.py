from __future__ import annotations

import math

from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import DestroyResult


def destroy(solution, context, rng) -> DestroyResult:
    """
    Mode-sensitive destroy. It estimates each rectangle's preferred sweep mode
    and removes tasks near H/V preference boundaries in expensive routes.
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
    sweep_width = max(float(instance.sweep_width), 1e-9)
    sweep_speed = max(float(instance.sweep_speed), 1e-9)
    turning_time = max(float(instance.turning_time), 0.0)
    travel_speed = max(float(instance.travel_speed), 1e-9)

    def center(task_id):
        task = task_by_id[task_id]
        return (
            0.5 * (float(task.x_left) + float(task.x_right)),
            0.5 * (float(task.y_bottom) + float(task.y_top))
        )

    def mode_data(task_id):
        task = task_by_id[task_id]
        horizontal_passes = max(1, int(math.ceil(float(task.height) / sweep_width)))
        vertical_passes = max(1, int(math.ceil(float(task.width) / sweep_width)))
        horizontal_cost = (
            horizontal_passes * float(task.width) / sweep_speed
            + max(0, horizontal_passes - 1) * turning_time
        )
        vertical_cost = (
            vertical_passes * float(task.height) / sweep_speed
            + max(0, vertical_passes - 1) * turning_time
        )
        preferred = "H" if horizontal_cost <= vertical_cost else "V"
        gap = abs(horizontal_cost - vertical_cost)
        scale = max(horizontal_cost, vertical_cost, 1e-9)
        return preferred, gap / scale, horizontal_cost, vertical_cost

    mode_cache = {task_id: mode_data(task_id) for task_id in task_by_id}
    max_route_cost = max(context.per_robot_costs, default=0.0)
    if max_route_cost <= 0.0:
        max_route_cost = 1.0

    # Exact state choice is most influential on smaller instances.
    state_emphasis = 1.0 if instance.task_count <= 16 else 0.35
    scored = []

    for robot_id, route in enumerate(routes):
        route_cost = (
            float(context.per_robot_costs[robot_id])
            if robot_id < len(context.per_robot_costs)
            else 0.0
        )
        criticality = max(0.0, route_cost / max_route_cost)

        for position, task_id in enumerate(route):
            preferred, relative_gap, horizontal_cost, vertical_cost = mode_cache[task_id]
            boundary_count = 0.0
            directional_conflict = 0.0
            current_center = center(task_id)

            for neighbour_position in (position - 1, position + 1):
                if neighbour_position < 0 or neighbour_position >= len(route):
                    continue
                neighbour_id = route[neighbour_position]
                neighbour_mode = mode_cache[neighbour_id][0]
                if neighbour_mode != preferred:
                    boundary_count += 1.0

                neighbour_center = center(neighbour_id)
                dx = abs(current_center[0] - neighbour_center[0])
                dy = abs(current_center[1] - neighbour_center[1])
                distance = (dx + dy) / travel_speed

                # Horizontal separation favors H-aligned access; vertical
                # separation favors V-aligned access. Penalize disagreement.
                geometry_mode = "H" if dx >= dy else "V"
                if geometry_mode != preferred:
                    directional_conflict += distance

            task_scale = max(min(horizontal_cost, vertical_cost), 1e-9)
            mode_signal = boundary_count * (0.5 + relative_gap)
            geometry_signal = directional_conflict / task_scale
            critical_weight = 0.35 + criticality * criticality

            score = critical_weight * (
                state_emphasis * (2.0 * mode_signal + geometry_signal)
                + (1.0 - state_emphasis) * 0.4 * geometry_signal
            )
            score *= 0.88 + 0.24 * rng.random()
            scored.append((score, boundary_count, relative_gap, task_id))

    scored.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    removed_tasks = [item[3] for item in scored[:target]]
    removed_set = set(removed_tasks)
    partial_routes = [
        [task_id for task_id in route if task_id not in removed_set]
        for route in routes
    ]

    return DestroyResult(
        partial_solution=MultiRobotSolution(routes=partial_routes),
        removed_tasks=removed_tasks,
        note="Removed tasks near estimated H/V preference boundaries, with stronger state emphasis on small instances."
    )
