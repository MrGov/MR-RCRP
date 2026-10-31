from __future__ import annotations

import math

from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import DestroyResult


def destroy(solution, context, rng) -> DestroyResult:
    """
    Args:
        solution: MultiRobotSolution with .routes (List[List[int]])
        context: DestroyContext
        rng: random.Random instance
    Returns:
        DestroyResult
    """
    instance = context.instance
    routes = [list(route) for route in solution.routes]
    target = min(max(0, context.remove_count), instance.task_count)
    if target == 0:
        return DestroyResult(
            partial_solution=MultiRobotSolution(routes=routes),
            removed_tasks=[],
            note="adaptive bottleneck burden destroy removed no tasks",
        )

    tasks = {task.task_id: task for task in instance.tasks}
    costs = list(context.per_robot_costs)
    makespan = max(context.route_costs_makespan, max(costs, default=0.0), 1e-12)
    sweep_width = max(float(instance.sweep_width), 1e-12)
    sweep_speed = max(float(instance.sweep_speed), 1e-12)
    travel_speed = max(float(instance.travel_speed), 1e-12)
    turning_time = max(float(instance.turning_time), 0.0)
    depot_x, depot_y = instance.depot

    def center(task):
        return ((task.x_left + task.x_right) * 0.5, (task.y_bottom + task.y_top) * 0.5)

    def distance(a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def processing(task):
        horizontal_lanes = max(1, int(math.ceil(max(task.height, 0.0) / sweep_width)))
        vertical_lanes = max(1, int(math.ceil(max(task.width, 0.0) / sweep_width)))
        horizontal = horizontal_lanes * max(task.width, 0.0) / sweep_speed
        horizontal += max(0, horizontal_lanes - 1) * turning_time
        vertical = vertical_lanes * max(task.height, 0.0) / sweep_speed
        vertical += max(0, vertical_lanes - 1) * turning_time
        return min(horizontal, vertical)

    candidates = []
    for route_id, route in enumerate(routes):
        route_cost = costs[route_id] if route_id < len(costs) else 0.0
        pressure = max(0.0, route_cost / makespan)
        if pressure >= 0.98:
            pressure_weight = 1.45
        elif pressure >= 0.85:
            pressure_weight = 1.0
        else:
            pressure_weight = 0.25 + 0.5 * pressure

        for position, task_id in enumerate(route):
            task = tasks[task_id]
            point = center(task)
            previous = center(tasks[route[position - 1]]) if position > 0 else (depot_x, depot_y)
            following = center(tasks[route[position + 1]]) if position + 1 < len(route) else (depot_x, depot_y)
            detour = max(0.0, distance(previous, point) + distance(point, following) - distance(previous, following))
            burden = processing(task) + detour / travel_speed
            isolation = min(distance(point, previous), distance(point, following)) / travel_speed
            score = pressure_weight * burden + 0.12 * pressure_weight * isolation
            score *= 0.97 + 0.06 * rng.random()
            candidates.append((score, pressure, route_id, position, task_id))

    candidates.sort(reverse=True)
    removed = []
    removed_set = set()
    selected_per_route = [0] * len(routes)

    critical_routes = [
        i for i, route in enumerate(routes)
        if route and (costs[i] if i < len(costs) else 0.0) >= 0.85 * makespan
    ]
    for route_id in sorted(
        critical_routes,
        key=lambda i: costs[i] if i < len(costs) else 0.0,
        reverse=True,
    ):
        if len(removed) >= target:
            break
        for candidate in candidates:
            if candidate[2] == route_id and candidate[4] not in removed_set:
                removed.append(candidate[4])
                removed_set.add(candidate[4])
                selected_per_route[route_id] += 1
                break

    for _, _, route_id, _, task_id in candidates:
        if len(removed) >= target:
            break
        if task_id in removed_set:
            continue
        route_size = len(routes[route_id])
        soft_cap = max(1, int(math.ceil(target * route_size / max(1, sum(map(len, routes))))) + 1)
        if selected_per_route[route_id] >= soft_cap and any(
            candidate[4] not in removed_set and selected_per_route[candidate[2]] < max(1, soft_cap)
            for candidate in candidates
        ):
            continue
        removed.append(task_id)
        removed_set.add(task_id)
        selected_per_route[route_id] += 1

    if len(removed) < target:
        for route in routes:
            for task_id in route:
                if task_id not in removed_set:
                    removed.append(task_id)
                    removed_set.add(task_id)
                    if len(removed) == target:
                        break
            if len(removed) == target:
                break

    new_routes = [[task_id for task_id in route if task_id not in removed_set] for route in routes]
    return DestroyResult(
        partial_solution=MultiRobotSolution(routes=new_routes),
        removed_tasks=removed,
        note="removed estimated processing and detour burdens from critical routes",
    )
