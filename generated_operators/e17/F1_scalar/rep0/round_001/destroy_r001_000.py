from __future__ import annotations

from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import DestroyResult


def destroy(solution, context, rng) -> DestroyResult:
    instance = context.instance
    routes = [list(route) for route in solution.routes]
    count = min(context.remove_count, instance.task_count)
    if count <= 0:
        return DestroyResult(partial_solution=MultiRobotSolution(routes=routes), removed_tasks=[], note="No tasks requested for removal.")

    tasks = {task.task_id: task for task in instance.tasks}
    costs = list(context.per_robot_costs)
    max_cost = max(costs, default=0.0)
    ranked = []
    for robot, route in enumerate(routes):
        route_cost = costs[robot] if robot < len(costs) else 0.0
        criticality = route_cost / max(max_cost, 1e-12)
        for position, task_id in enumerate(route):
            task = tasks[task_id]
            width = max(float(task.width), 1e-9)
            height = max(float(task.height), 1e-9)
            speed = max(float(instance.sweep_speed), 1e-9)
            swath = max(float(instance.sweep_width), 1e-9)
            service = width * height / (swath * speed)
            edge = min(position + 1, len(route) - position)
            score = criticality * (0.65 + 0.35 * service / max(service + route_cost, 1e-9))
            ranked.append((score, edge, rng.random(), robot, task_id))
    ranked.sort(reverse=True)
    chosen = {item[4] for item in ranked[:count]}
    kept = [[task_id for task_id in route if task_id not in chosen] for route in routes]
    return DestroyResult(partial_solution=MultiRobotSolution(routes=kept), removed_tasks=[task_id for route in routes for task_id in route if task_id in chosen], note="Removed tasks preferentially from high-cost routes to enable workload rebalancing.")