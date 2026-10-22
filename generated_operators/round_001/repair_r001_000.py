from __future__ import annotations

from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import RepairResult


def repair(partial_solution, unassigned_tasks, context, rng):
    routes = [list(route) for route in partial_solution.routes]
    # Problem-specific bias: prefer inserting into non-bottleneck routes first.
    robot_order = list(range(len(routes)))
    if 0 <= context.bottleneck_route_id < len(routes):
        robot_order.remove(context.bottleneck_route_id)
        robot_order.append(context.bottleneck_route_id)

    for task_id in unassigned_tasks:
        target_robot = min(robot_order, key=lambda r: len(routes[r])) if routes else 0
        routes[target_robot].append(task_id)
    return RepairResult(solution=MultiRobotSolution(routes=routes), note="template candidate")
