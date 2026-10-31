from __future__ import annotations

import math

from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import DestroyResult


def destroy(solution, context, rng) -> DestroyResult:
    """
    Target route transitions where neighboring rectangles have conflicting
    preferred sweep modes or large centroid gaps, then expand locally.
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

    task_map = {task.task_id: task for task in instance.tasks}
    costs = list(context.per_robot_costs)
    makespan = max(float(context.route_costs_makespan), max(costs, default=0.0), 1e-12)
    sweep_width = max(float(instance.sweep_width), 1e-12)
    sweep_speed = max(float(instance.sweep_speed), 1e-12)
    travel_speed = max(float(instance.travel_speed), 1e-12)
    turning_time = max(float(instance.turning_time), 0.0)

    def center(task):
        return (
            0.5 * (float(task.x_left) + float(task.x_right)),
            0.5 * (float(task.y_bottom) + float(task.y_top))
        )

    def distance(first, second):
        a = center(first)
        b = center(second)
        return (abs(a[0] - b[0]) + abs(a[1] - b[1])) / travel_speed

    def sweep_profile(task):
        width = max(float(task.width), 0.0)
        height = max(float(task.height), 0.0)
        horizontal_passes = max(1, int(math.ceil(height / sweep_width)))
        vertical_passes = max(1, int(math.ceil(width / sweep_width)))
        horizontal = horizontal_passes * width / sweep_speed + (horizontal_passes - 1) * turning_time
        vertical = vertical_passes * height / sweep_speed + (vertical_passes - 1) * turning_time
        if horizontal <= vertical:
            return 0, horizontal, vertical
        return 1, vertical, horizontal

    records = {}
    base_scores = {}
    for route_id, route in enumerate(routes):
        route_cost = costs[route_id] if route_id < len(costs) else 0.0
        ratio = max(0.0, float(route_cost) / makespan)
        pressure = 1.0 + 4.5 * ratio * ratio
        if ratio >= 0.95:
            pressure += 2.5

        profiles = {}
        for task_id in route:
            task = task_map.get(task_id)
            if task is not None:
                profiles[task_id] = sweep_profile(task)

        for position, task_id in enumerate(route):
            task = task_map.get(task_id)
            records[task_id] = (route_id, position)
            if task is None:
                base_scores[task_id] = max(base_scores.get(task_id, 0.0), pressure)
                continue

            preferred, best_time, alternate_time = profiles[task_id]
            direction_sensitivity = max(0.0, alternate_time - best_time)
            transition_burden = 0.0

            for neighbor_position in (position - 1, position + 1):
                if 0 <= neighbor_position < len(route):
                    neighbor_id = route[neighbor_position]
                    neighbor = task_map.get(neighbor_id)
                    if neighbor is None:
                        continue
                    neighbor_preferred, neighbor_best, neighbor_alternate = profiles[neighbor_id]
                    gap = distance(task, neighbor)
                    if preferred != neighbor_preferred:
                        mismatch = 0.5 * (
                            direction_sensitivity
                            + max(0.0, neighbor_alternate - neighbor_best)
                        )
                        transition_burden += gap + mismatch
                    else:
                        transition_burden += 0.30 * gap

            aspect = max(
                max(float(task.width), 1e-12) / max(float(task.height), 1e-12),
                max(float(task.height), 1e-12) / max(float(task.width), 1e-12)
            )
            score = pressure * (
                best_time + 1.35 * transition_burden + 0.10 * best_time * math.log1p(aspect)
            )
            score *= 0.92 + 0.16 * rng.random()
            base_scores[task_id] = max(base_scores.get(task_id, 0.0), score)

    available = list(base_scores)
    selected = []
    selected_set = set()

    while len(selected) < target and available:
        best_id = None
        best_score = -1.0
        for task_id in available:
            score = base_scores[task_id]
            route_id, position = records.get(task_id, (-1, -1000000))
            for chosen_id in selected:
                chosen_route, chosen_position = records.get(chosen_id, (-2, 1000000))
                if route_id == chosen_route:
                    separation = abs(position - chosen_position)
                    if separation == 1:
                        score *= 1.55
                    elif separation == 2:
                        score *= 1.20
            score *= 0.97 + 0.06 * rng.random()
            if score > best_score:
                best_score = score
                best_id = task_id

        selected.append(best_id)
        selected_set.add(best_id)
        available.remove(best_id)

    new_routes = [[task_id for task_id in route if task_id not in selected_set] for route in routes]
    return DestroyResult(
        partial_solution=MultiRobotSolution(routes=new_routes),
        removed_tasks=selected,
        note="Removed critical local clusters around sweep-direction mismatches and large route gaps."
    )
