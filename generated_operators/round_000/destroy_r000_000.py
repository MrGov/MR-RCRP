from __future__ import annotations

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
    target = min(context.remove_count, instance.task_count)

    if target <= 0:
        return DestroyResult(
            partial_solution=MultiRobotSolution(routes=routes),
            removed_tasks=[],
            note="No tasks requested for bottleneck-detour removal."
        )

    task_by_id = {task.task_id: task for task in instance.tasks}
    depot_x, depot_y = instance.depot
    costs = list(context.per_robot_costs)
    makespan = max(context.route_costs_makespan, 1e-12)

    def center(task_id):
        task = task_by_id[task_id]
        return ((task.x_left + task.x_right) * 0.5,
                (task.y_bottom + task.y_top) * 0.5)

    def distance(a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    candidates = []
    for robot_id, route in enumerate(routes):
        route_cost = costs[robot_id] if robot_id < len(costs) else 0.0
        criticality = route_cost / makespan

        for position, task_id in enumerate(route):
            current = center(task_id)
            previous = ((depot_x, depot_y) if position == 0
                        else center(route[position - 1]))
            following = ((depot_x, depot_y) if position + 1 == len(route)
                         else center(route[position + 1]))

            detour = (distance(previous, current)
                      + distance(current, following)
                      - distance(previous, following))
            radial = distance((depot_x, depot_y), current)
            task = task_by_id[task_id]
            long_side = max(task.width, task.height)

            score = (2.5 * criticality * detour
                     + 0.35 * criticality * radial
                     + 0.10 * long_side
                     + rng.random() * 1e-6)
            candidates.append((score, task_id))

    candidates.sort(reverse=True)
    removed_tasks = [task_id for _, task_id in candidates[:target]]
    removed_set = set(removed_tasks)
    partial_routes = [
        [task_id for task_id in route if task_id not in removed_set]
        for route in routes
    ]

    return DestroyResult(
        partial_solution=MultiRobotSolution(routes=partial_routes),
        removed_tasks=removed_tasks,
        note="Removed transfer-detour tasks weighted toward current bottleneck routes."
    )
