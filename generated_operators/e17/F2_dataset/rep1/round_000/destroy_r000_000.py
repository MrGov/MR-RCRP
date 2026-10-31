from __future__ import annotations

import math

from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import DestroyResult


def destroy(solution, context, rng) -> DestroyResult:
    """
    Remove tasks with large approximate marginal cost, emphasizing routes near
    the current makespan. Retained tasks keep their robot and relative order.
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
    max_cost = max(costs, default=makespan)
    sweep_width = max(float(instance.sweep_width), 1e-12)
    sweep_speed = max(float(instance.sweep_speed), 1e-12)
    travel_speed = max(float(instance.travel_speed), 1e-12)
    turning_time = max(float(instance.turning_time), 0.0)

    def center(task_id):
        task = task_by_id[task_id]
        return ((task.x_left + task.x_right) * 0.5,
                (task.y_bottom + task.y_top) * 0.5)

    def manhattan(a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def approximate_service(task):
        horizontal_passes = max(1, int(math.ceil(task.height / sweep_width)))
        vertical_passes = max(1, int(math.ceil(task.width / sweep_width)))
        horizontal = (
            horizontal_passes * task.width / sweep_speed
            + (horizontal_passes - 1) * turning_time
        )
        vertical = (
            vertical_passes * task.height / sweep_speed
            + (vertical_passes - 1) * turning_time
        )
        return min(horizontal, vertical)

    candidates = []
    for route_id, route in enumerate(routes):
        route_cost = costs[route_id] if route_id < len(costs) else 0.0
        criticality = max(0.0, route_cost / max(max_cost, 1e-12))
        makespan_proximity = max(0.0, route_cost / makespan)
        route_weight = 0.20 + 2.80 * criticality ** 3 + makespan_proximity ** 2

        for position, task_id in enumerate(route):
            task = task_by_id[task_id]
            current = center(task_id)
            previous = center(route[position - 1]) if position > 0 else (depot_x, depot_y)
            following = center(route[position + 1]) if position + 1 < len(route) else (depot_x, depot_y)

            detour = max(
                0.0,
                manhattan(previous, current)
                + manhattan(current, following)
                - manhattan(previous, following)
            ) / travel_speed
            depot_remoteness = manhattan((depot_x, depot_y), current) / travel_speed
            service = approximate_service(task)

            marginal = service + detour + 0.12 * depot_remoteness
            jitter = 0.90 + 0.20 * rng.random()
            score = max(1e-12, route_weight * marginal * jitter)
            candidates.append((score, route_id, position, task_id))

    selected = set()
    remaining = list(candidates)

    while len(selected) < remove_count and remaining:
        remaining.sort(key=lambda item: item[0], reverse=True)
        pool_size = min(len(remaining), max(2, int(math.sqrt(len(remaining))) + 1))
        pool = remaining[:pool_size]
        total_weight = sum(item[0] for item in pool)

        if total_weight <= 0.0:
            chosen = pool[rng.randrange(len(pool))]
        else:
            threshold = rng.random() * total_weight
            cumulative = 0.0
            chosen = pool[-1]
            for item in pool:
                cumulative += item[0]
                if cumulative >= threshold:
                    chosen = item
                    break

        selected.add(chosen[3])
        remaining = [item for item in remaining if item[3] != chosen[3]]

    if len(selected) < remove_count:
        fallback = [task_id for route in routes for task_id in route if task_id not in selected]
        rng.shuffle(fallback)
        selected.update(fallback[:remove_count - len(selected)])

    removed_tasks = [
        task_id for route in routes for task_id in route if task_id in selected
    ]
    partial_routes = [
        [task_id for task_id in route if task_id not in selected]
        for route in routes
    ]

    return DestroyResult(
        partial_solution=MultiRobotSolution(routes=partial_routes),
        removed_tasks=removed_tasks,
        note="Removed approximate high-marginal-cost tasks with strong emphasis on makespan-critical routes."
    )
