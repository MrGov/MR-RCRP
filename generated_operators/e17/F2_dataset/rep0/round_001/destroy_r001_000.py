from __future__ import annotations

import math

from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import DestroyResult


def destroy(solution, context, rng) -> DestroyResult:
    """
    Remove tasks that create large travel bridges or processing load on critical
    routes. Scores are recomputed after each removal so adjacent removals reflect
    the evolving partial route rather than stale original positions.
    """
    instance = context.instance
    tasks = list(instance.tasks)
    task_by_id = {task.task_id: task for task in tasks}
    routes = [list(route) for route in solution.routes]
    original_routes = [list(route) for route in solution.routes]

    task_count = getattr(instance, "task_count", len(tasks))
    remove_target = min(max(0, int(context.remove_count)), int(task_count))
    if remove_target == 0:
        return DestroyResult(
            partial_solution=MultiRobotSolution(routes=routes),
            removed_tasks=[],
            note="adaptive bottleneck bridge destroy: no tasks requested",
        )

    costs = list(context.per_robot_costs)
    positive_costs = [float(c) for c in costs if c > 0.0]
    max_cost = max(positive_costs) if positive_costs else 1.0
    mean_cost = sum(positive_costs) / len(positive_costs) if positive_costs else 0.0

    depot = instance.depot
    if isinstance(depot, (tuple, list)):
        depot_xy = (float(depot[0]), float(depot[1]))
    else:
        depot_xy = (float(getattr(depot, "x", 0.0)), float(getattr(depot, "y", 0.0)))

    sweep_width = max(float(instance.sweep_width), 1e-12)
    sweep_speed = max(float(instance.sweep_speed), 1e-12)
    travel_speed = max(float(instance.travel_speed), 1e-12)
    turning_time = max(float(instance.turning_time), 0.0)

    def center(task):
        return (
            0.5 * (float(task.x_left) + float(task.x_right)),
            0.5 * (float(task.y_bottom) + float(task.y_top)),
        )

    def distance(a, b):
        return (abs(a[0] - b[0]) + abs(a[1] - b[1])) / travel_speed

    def processing(task):
        width = max(float(task.width), 0.0)
        height = max(float(task.height), 0.0)
        h_lanes = max(1, int(math.ceil(height / sweep_width)))
        v_lanes = max(1, int(math.ceil(width / sweep_width)))
        horizontal = h_lanes * width / sweep_speed + (h_lanes - 1) * turning_time
        vertical = v_lanes * height / sweep_speed + (v_lanes - 1) * turning_time
        return min(horizontal, vertical)

    proc_values = {task.task_id: processing(task) for task in tasks}
    proc_scale = max(proc_values.values()) if proc_values else 1.0
    all_centers = [center(task) for task in tasks]
    if all_centers:
        global_x = sum(p[0] for p in all_centers) / len(all_centers)
        global_y = sum(p[1] for p in all_centers) / len(all_centers)
        geo_scale = max(
            1.0,
            max(abs(p[0] - global_x) + abs(p[1] - global_y) for p in all_centers),
        )
    else:
        global_x = global_y = 0.0
        geo_scale = 1.0

    removed = []
    removed_set = set()

    while len(removed) < remove_target:
        candidates = []
        for route_id, route in enumerate(routes):
            if not route:
                continue
            route_cost = float(costs[route_id]) if route_id < len(costs) else 0.0
            criticality = route_cost / max_cost
            overload = max(0.0, route_cost - mean_cost) / max_cost

            for pos, task_id in enumerate(route):
                if task_id in removed_set or task_id not in task_by_id:
                    continue
                task = task_by_id[task_id]
                point = center(task)
                prev_point = depot_xy if pos == 0 else center(task_by_id[route[pos - 1]])
                next_point = depot_xy if pos + 1 == len(route) else center(task_by_id[route[pos + 1]])
                bridge = max(
                    0.0,
                    distance(prev_point, point)
                    + distance(point, next_point)
                    - distance(prev_point, next_point),
                )
                bridge_norm = bridge / max(1.0, max_cost)
                proc_norm = proc_values.get(task_id, 0.0) / max(1.0, proc_scale)
                outlier = (
                    abs(point[0] - global_x) + abs(point[1] - global_y)
                ) / geo_scale

                score = (
                    1.55 * criticality
                    + 1.20 * overload
                    + 1.80 * bridge_norm
                    + 0.45 * proc_norm
                    + 0.20 * outlier
                    + 0.035 * rng.random()
                )
                candidates.append((score, route_id, pos, task_id))

        if not candidates:
            break

        candidates.sort(reverse=True)
        restricted = candidates[: min(3, len(candidates))]
        if len(restricted) == 1 or rng.random() < 0.72:
            chosen = restricted[0]
        else:
            weights = [max(1e-9, item[0] - restricted[-1][0] + 0.05) for item in restricted]
            draw = rng.random() * sum(weights)
            chosen = restricted[-1]
            for item, weight in zip(restricted, weights):
                draw -= weight
                if draw <= 0.0:
                    chosen = item
                    break

        _, route_id, _, task_id = chosen
        routes[route_id].remove(task_id)
        removed.append(task_id)
        removed_set.add(task_id)

    if len(removed) < remove_target:
        for route_id, route in enumerate(routes):
            for task_id in list(route):
                if task_id not in removed_set:
                    route.remove(task_id)
                    removed.append(task_id)
                    removed_set.add(task_id)
                    if len(removed) == remove_target:
                        break
            if len(removed) == remove_target:
                break

    retained = {task_id for route in routes for task_id in route}
    expected = {task_id for route in original_routes for task_id in route}
    if retained | removed_set != expected or retained & removed_set:
        raise ValueError("destroy produced an inconsistent task partition")

    return DestroyResult(
        partial_solution=MultiRobotSolution(routes=routes),
        removed_tasks=removed,
        note="adaptive bottleneck bridge destroy targeting transfer-heavy critical routes",
    )
