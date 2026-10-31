import math

from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import DestroyResult


def destroy(solution, context, rng) -> DestroyResult:
    """
    Remove tasks with large estimated marginal cost, emphasizing routes near the
    current makespan. Retained tasks preserve their robot and relative order.
    """
    instance = context.instance
    routes = [list(route) for route in solution.routes]
    target = min(max(0, context.remove_count), instance.task_count)

    if target == 0:
        return DestroyResult(
            partial_solution=MultiRobotSolution(routes=routes),
            removed_tasks=[],
            note="No tasks requested for removal."
        )

    task_source = instance.tasks.values() if isinstance(instance.tasks, dict) else instance.tasks
    task_map = {task.task_id: task for task in task_source}
    costs = list(context.per_robot_costs)
    makespan = max(float(context.route_costs_makespan), max(costs, default=0.0), 1e-9)
    travel_speed = max(float(instance.travel_speed), 1e-9)
    sweep_speed = max(float(instance.sweep_speed), 1e-9)
    sweep_width = max(float(instance.sweep_width), 1e-9)
    turning_time = max(float(instance.turning_time), 0.0)
    depot = instance.depot
    depot_xy = (float(depot[0]), float(depot[1]))

    def center(task):
        return (
            0.5 * (float(task.x_left) + float(task.x_right)),
            0.5 * (float(task.y_bottom) + float(task.y_top))
        )

    def distance(a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def service_time(task):
        width = max(float(task.width), 0.0)
        height = max(float(task.height), 0.0)
        horizontal_passes = max(1, int(math.ceil(height / sweep_width)))
        vertical_passes = max(1, int(math.ceil(width / sweep_width)))
        horizontal = width * horizontal_passes / sweep_speed
        horizontal += max(0, horizontal_passes - 1) * turning_time
        vertical = height * vertical_passes / sweep_speed
        vertical += max(0, vertical_passes - 1) * turning_time
        return min(horizontal, vertical)

    candidates = []
    for robot_id, route in enumerate(routes):
        route_cost = costs[robot_id] if robot_id < len(costs) else 0.0
        criticality = 0.20 + 0.80 * max(0.0, float(route_cost)) / makespan
        for position, task_id in enumerate(route):
            task = task_map.get(task_id)
            if task is None:
                score = criticality + rng.random() * 1e-9
            else:
                current = center(task)
                if position > 0 and route[position - 1] in task_map:
                    previous = center(task_map[route[position - 1]])
                else:
                    previous = depot_xy
                if position + 1 < len(route) and route[position + 1] in task_map:
                    following = center(task_map[route[position + 1]])
                else:
                    following = depot_xy
                detour = max(
                    0.0,
                    distance(previous, current)
                    + distance(current, following)
                    - distance(previous, following)
                ) / travel_speed
                marginal = service_time(task) + detour
                endpoint_bonus = 1.08 if position == 0 or position == len(route) - 1 else 1.0
                score = criticality * marginal * endpoint_bonus
                score += rng.random() * 1e-9
            candidates.append((score, robot_id, position, task_id))

    candidates.sort(key=lambda item: item[0], reverse=True)
    removed = []
    selected = set()
    for _, _, _, task_id in candidates:
        if task_id not in selected:
            selected.add(task_id)
            removed.append(task_id)
            if len(removed) == target:
                break

    new_routes = [[task_id for task_id in route if task_id not in selected] for route in routes]
    return DestroyResult(
        partial_solution=MultiRobotSolution(routes=new_routes),
        removed_tasks=removed,
        note="Removed bottleneck-weighted tasks with high estimated service and Manhattan detour cost."
    )
