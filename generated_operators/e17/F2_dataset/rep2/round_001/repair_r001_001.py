import math

from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import RepairResult


def repair(partial_solution, unassigned_tasks, context, rng):
    routes = [list(route) for route in partial_solution.routes]
    while len(routes) < context.instance.robot_count:
        routes.append([])

    if not routes:
        return RepairResult(
            solution=MultiRobotSolution(routes=routes),
            note="mode_aligned_slack_repair: no robot routes available",
        )

    task_by_id = {task.task_id: task for task in context.instance.tasks}
    costs = list(context.per_robot_costs)
    makespan = max(1.0, context.route_costs_makespan)
    bottleneck = context.bottleneck_route_id
    added = [0] * len(routes)

    def center(task_id):
        task = task_by_id[task_id]
        return ((task.x_left + task.x_right) * 0.5,
                (task.y_bottom + task.y_top) * 0.5)

    def distance(first, second):
        return math.hypot(first[0] - second[0], first[1] - second[1])

    def shape_mode(task_id):
        task = task_by_id[task_id]
        return 0 if task.width >= task.height else 1

    def anisotropy(task_id):
        task = task_by_id[task_id]
        large = max(task.width, task.height)
        small = max(1e-9, min(task.width, task.height))
        return large / small

    def insertion_score(route, position, task_id):
        task = task_by_id[task_id]
        point = center(task_id)
        depot = (0.0, 0.0)
        previous = depot if position == 0 else center(route[position - 1])
        following = depot if position == len(route) else center(route[position])
        transfer = (distance(previous, point) + distance(point, following)
                    - distance(previous, following))
        scale = max(1.0, task.width + task.height)

        mode = shape_mode(task_id)
        switches = 0.0
        comparisons = 0
        if position > 0:
            switches += 1.0 if shape_mode(route[position - 1]) != mode else 0.0
            comparisons += 1
        if position < len(route):
            switches += 1.0 if shape_mode(route[position]) != mode else 0.0
            comparisons += 1
        if comparisons:
            switches /= comparisons

        alignment = 0.0
        neighbors = 0
        for neighbor_position in (position - 1, position):
            if 0 <= neighbor_position < len(route):
                neighbor = task_by_id[route[neighbor_position]]
                neighbor_center = center(route[neighbor_position])
                if mode == 0:
                    alignment += abs(point[1] - neighbor_center[1]) / max(1.0, task.height + neighbor.height)
                else:
                    alignment += abs(point[0] - neighbor_center[0]) / max(1.0, task.width + neighbor.width)
                neighbors += 1
        if neighbors:
            alignment /= neighbors

        return transfer / scale + 0.55 * switches + 0.2 * alignment

    def task_priority(task_id):
        task = task_by_id[task_id]
        point = center(task_id)
        return (anisotropy(task_id),
                distance((0.0, 0.0), point),
                task.width * task.height,
                rng.random())

    ordered_tasks = sorted(unassigned_tasks, key=task_priority, reverse=True)

    for task_id in ordered_tasks:
        best = None
        for robot_id, route in enumerate(routes):
            route_cost = costs[robot_id] if robot_id < len(costs) else 0.0
            slack_ratio = max(0.0, makespan - route_cost) / makespan
            bottleneck_penalty = 3.0 if len(routes) > 1 and robot_id == bottleneck else 0.0
            balance_penalty = route_cost / makespan + 0.28 * added[robot_id]

            for position in range(len(route) + 1):
                score = (bottleneck_penalty
                         + balance_penalty
                         - 0.45 * slack_ratio
                         + insertion_score(route, position, task_id)
                         + rng.random() * 1e-10)
                if best is None or score < best[0]:
                    best = (score, robot_id, position)

        robot_id = best[1]
        routes[robot_id].insert(best[2], task_id)
        added[robot_id] += 1

    return RepairResult(
        solution=MultiRobotSolution(routes=routes),
        note="mode_aligned_slack_repair: grouped sweep-compatible rectangles on slack routes",
    )
