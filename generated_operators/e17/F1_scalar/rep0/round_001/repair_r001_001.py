from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import RepairResult


def repair(partial_solution, unassigned_tasks, context, rng):
    routes = [list(route) for route in partial_solution.routes]
    task_by_id = {task.task_id: task for task in context.instance.tasks}
    robot_count = context.instance.robot_count

    while len(routes) < robot_count:
        routes.append([])

    costs = list(context.per_robot_costs)
    while len(costs) < robot_count:
        costs.append(0.0)

    bottleneck = context.bottleneck_route_id
    additions = [0] * robot_count

    def features(task_id):
        task = task_by_id[task_id]
        cx = (task.x_left + task.x_right) * 0.5
        cy = (task.y_bottom + task.y_top) * 0.5
        longest = max(task.width, task.height)
        shortest = min(task.width, task.height)
        aspect = longest / shortest if shortest > 0 else longest
        orientation = 0 if task.width >= task.height else 1
        return cx, cy, aspect, orientation

    def pair_score(first_id, second_id):
        ax, ay, aspect_a, orientation_a = features(first_id)
        bx, by, aspect_b, orientation_b = features(second_id)
        aspect_gap = abs(aspect_a - aspect_b)
        if orientation_a == 0:
            alignment_gap = abs(ay - by)
        else:
            alignment_gap = abs(ax - bx)
        orientation_penalty = 0.0 if orientation_a == orientation_b else 1.0
        return aspect_gap + alignment_gap + orientation_penalty

    def route_match(route, task_id):
        if not route:
            return 0.0
        best = None
        for existing_id in route:
            value = pair_score(existing_id, task_id)
            if best is None or value < best:
                best = value
        return best

    def insertion_position(route, task_id):
        if not route:
            return 0
        best_pos = 0
        best_value = None
        for pos in range(len(route) + 1):
            value = 0.0
            if pos > 0:
                value += pair_score(route[pos - 1], task_id)
            if pos < len(route):
                value += pair_score(task_id, route[pos])
            if best_value is None or value < best_value:
                best_value = value
                best_pos = pos
        return best_pos

    tasks = list(unassigned_tasks)
    tasks.sort(
        key=lambda task_id: max(task_by_id[task_id].width,
                                task_by_id[task_id].height),
        reverse=True
    )

    for task_id in tasks:
        route_scores = []
        for robot_id in range(robot_count):
            bottleneck_penalty = 1 if robot_id == bottleneck and robot_count > 1 else 0
            route_scores.append((
                bottleneck_penalty,
                additions[robot_id],
                route_match(routes[robot_id], task_id),
                costs[robot_id],
                len(routes[robot_id]),
                robot_id
            ))

        target = min(range(robot_count), key=lambda robot_id: route_scores[robot_id])
        position = insertion_position(routes[target], task_id)
        routes[target].insert(position, task_id)
        additions[target] += 1

    return RepairResult(
        solution=MultiRobotSolution(routes=routes),
        note="Aspect-ratio and sweep-alignment grouping with bottleneck avoidance"
    )