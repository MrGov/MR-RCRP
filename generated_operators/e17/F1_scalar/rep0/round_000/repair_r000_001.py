from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import RepairResult


def repair(partial_solution, unassigned_tasks, context, rng):
    routes = [list(route) for route in partial_solution.routes]
    while len(routes) < context.instance.robot_count:
        routes.append([])

    task_by_id = {task.task_id: task for task in context.instance.tasks}
    bottleneck = context.bottleneck_route_id
    eligible = [r for r in range(len(routes)) if r != bottleneck]
    if not eligible:
        eligible = list(range(len(routes)))

    def center(task):
        return ((task.x_left + task.x_right) * 0.5,
                (task.y_bottom + task.y_top) * 0.5)

    def orientation(task):
        return 0 if task.width >= task.height else 1

    def pair_affinity(first_id, second_id):
        first = task_by_id[first_id]
        second = task_by_id[second_id]
        first_center = center(first)
        second_center = center(second)
        horizontal_gap = abs(first_center[1] - second_center[1])
        vertical_gap = abs(first_center[0] - second_center[0])
        scale = max(first.width, first.height, second.width, second.height, 1.0)
        alignment = 1.0 / (1.0 + min(horizontal_gap, vertical_gap) / scale)
        mode_bonus = 0.75 if orientation(first) == orientation(second) else 0.0
        return alignment + mode_bonus

    def position_affinity(route, task_id, position):
        score = 0.0
        neighbors = 0
        if position > 0:
            score += pair_affinity(route[position - 1], task_id)
            neighbors += 1
        if position < len(route):
            score += pair_affinity(task_id, route[position])
            neighbors += 1
        if neighbors == 0:
            return 0.0
        return score / neighbors

    makespan = context.route_costs_makespan
    added_count = [0] * len(routes)
    decorated = []
    for task_id in unassigned_tasks:
        task = task_by_id[task_id]
        decorated.append((-(task.width * task.height), rng.random(), task_id))
    decorated.sort()

    for _, _, task_id in decorated:
        choices = []
        for robot_id in eligible:
            route = routes[robot_id]
            best_position = 0
            best_affinity = -1.0
            for position in range(len(route) + 1):
                affinity = position_affinity(route, task_id, position)
                if affinity > best_affinity:
                    best_affinity = affinity
                    best_position = position
            cost = (context.per_robot_costs[robot_id]
                    if robot_id < len(context.per_robot_costs) else 0.0)
            slack = makespan - cost
            choices.append((best_affinity, slack, -added_count[robot_id],
                            rng.random(), robot_id, best_position))

        _, _, _, _, target, position = max(choices)
        routes[target].insert(position, task_id)
        added_count[target] += 1

    return RepairResult(
        solution=MultiRobotSolution(routes=routes),
        note="Sweep-orientation and axis-alignment affinity repair",
    )
