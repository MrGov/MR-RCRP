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
            note="slack_geometry_insertion: no robot routes available",
        )

    task_by_id = {task.task_id: task for task in context.instance.tasks}
    costs = list(context.per_robot_costs)
    bottleneck = context.bottleneck_route_id
    assigned_counts = [0] * len(routes)
    max_cost = max([1.0] + costs)

    def center(task_id):
        task = task_by_id[task_id]
        return ((task.x_left + task.x_right) * 0.5,
                (task.y_bottom + task.y_top) * 0.5)

    def distance(a, b):
        return math.hypot(a[0] - b[0], a[1] - b[1])

    def aspect_difference(first_id, second_id):
        first = task_by_id[first_id]
        second = task_by_id[second_id]
        first_ratio = (first.width + 1e-9) / (first.height + 1e-9)
        second_ratio = (second.width + 1e-9) / (second.height + 1e-9)
        return abs(math.log(first_ratio) - math.log(second_ratio))

    def insertion_geometry(route, position, task_id):
        depot = (0.0, 0.0)
        point = center(task_id)
        previous = depot if position == 0 else center(route[position - 1])
        following = depot if position == len(route) else center(route[position])
        transfer_delta = (distance(previous, point) + distance(point, following)
                          - distance(previous, following))
        compatibility = 0.0
        neighbors = 0
        if position > 0:
            compatibility += aspect_difference(task_id, route[position - 1])
            neighbors += 1
        if position < len(route):
            compatibility += aspect_difference(task_id, route[position])
            neighbors += 1
        if neighbors:
            compatibility /= neighbors
        task = task_by_id[task_id]
        scale = max(1.0, task.width + task.height)
        return transfer_delta / scale + 0.18 * compatibility

    def difficulty(task_id):
        task = task_by_id[task_id]
        point = center(task_id)
        elongation = max(task.width, task.height) / max(1e-9, min(task.width, task.height))
        return (distance((0.0, 0.0), point)
                + 0.25 * (task.width + task.height)
                + 0.1 * elongation
                + rng.random() * 1e-9)

    ordered_tasks = sorted(unassigned_tasks, key=difficulty, reverse=True)

    for task_id in ordered_tasks:
        best_choice = None
        for robot_id, route in enumerate(routes):
            route_cost = costs[robot_id] if robot_id < len(costs) else 0.0
            load_pressure = route_cost / max_cost + 0.32 * assigned_counts[robot_id]
            bottleneck_penalty = 2.5 if len(routes) > 1 and robot_id == bottleneck else 0.0

            for position in range(len(route) + 1):
                score = (bottleneck_penalty
                         + load_pressure
                         + insertion_geometry(route, position, task_id)
                         + rng.random() * 1e-10)
                if best_choice is None or score < best_choice[0]:
                    best_choice = (score, robot_id, position)

        robot_id = best_choice[1]
        position = best_choice[2]
        routes[robot_id].insert(position, task_id)
        assigned_counts[robot_id] += 1

    return RepairResult(
        solution=MultiRobotSolution(routes=routes),
        note="slack_geometry_insertion: protected bottleneck and used geometry-aware best positions",
    )
