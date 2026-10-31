from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import RepairResult
import math


def repair(partial_solution, unassigned_tasks, context, rng):
    routes = [list(route) for route in partial_solution.routes]
    while len(routes) < context.instance.robot_count:
        routes.append([])

    task_by_id = {task.task_id: task for task in context.instance.tasks}

    def center(task_id):
        task = task_by_id[task_id]
        return ((task.x_left + task.x_right) * 0.5,
                (task.y_bottom + task.y_top) * 0.5)

    def distance(a, b):
        return math.hypot(a[0] - b[0], a[1] - b[1])

    def insertion_delta(route, position, task_id):
        point = center(task_id)
        before = (0.0, 0.0) if position == 0 else center(route[position - 1])
        after = (0.0, 0.0) if position == len(route) else center(route[position])
        return distance(before, point) + distance(point, after) - distance(before, after)

    proxy_costs = []
    for robot_id in range(len(routes)):
        if robot_id < len(context.per_robot_costs):
            proxy_costs.append(float(context.per_robot_costs[robot_id]))
        else:
            proxy_costs.append(0.0)

    ordered_tasks = list(unassigned_tasks)
    ordered_tasks.sort(
        key=lambda task_id: (
            -math.hypot(center(task_id)[0], center(task_id)[1]),
            -task_by_id[task_id].width * task_by_id[task_id].height,
            rng.random()
        )
    )

    makespan_scale = max(float(context.route_costs_makespan), 1.0)
    for task_id in ordered_tasks:
        task = task_by_id[task_id]
        coverage_proxy = max(task.width, task.height)
        best = None

        for robot_id, route in enumerate(routes):
            slack = max(0.0, context.route_costs_makespan - proxy_costs[robot_id])
            pressure = proxy_costs[robot_id] / makespan_scale
            bottleneck_penalty = makespan_scale * 0.35 if robot_id == context.bottleneck_route_id else 0.0

            for position in range(len(route) + 1):
                delta = insertion_delta(route, position, task_id)
                slack_penalty = max(0.0, delta + coverage_proxy - slack) * 0.75
                score = (delta + coverage_proxy * 0.20 +
                         pressure * makespan_scale * 0.15 +
                         slack_penalty + bottleneck_penalty +
                         rng.random() * 1.0e-7)
                candidate = (score, robot_id, position, delta)
                if best is None or candidate < best:
                    best = candidate

        _, robot_id, position, delta = best
        routes[robot_id].insert(position, task_id)
        proxy_costs[robot_id] += delta + coverage_proxy

    return RepairResult(
        solution=MultiRobotSolution(routes=routes),
        note="slack-weighted geometric insertion with bottleneck protection"
    )
