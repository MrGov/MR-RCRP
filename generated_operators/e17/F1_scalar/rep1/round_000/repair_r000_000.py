from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import RepairResult


def repair(partial_solution, unassigned_tasks, context, rng) -> RepairResult:
    routes = [list(route) for route in partial_solution.routes]
    task_by_id = {task.task_id: task for task in context.instance.tasks}
    depot_x, depot_y = context.instance.depot
    robot_count = context.instance.robot_count
    added_counts = [0] * robot_count

    def centroid(task_id):
        task = task_by_id[task_id]
        return ((task.x_left + task.x_right) * 0.5,
                (task.y_bottom + task.y_top) * 0.5)

    def distance(a, b):
        dx = a[0] - b[0]
        dy = a[1] - b[1]
        return (dx * dx + dy * dy) ** 0.5

    def insertion_delta(route, position, task_id):
        point = centroid(task_id)
        before = (depot_x, depot_y) if position == 0 else centroid(route[position - 1])
        after = (depot_x, depot_y) if position == len(route) else centroid(route[position])
        return distance(before, point) + distance(point, after) - distance(before, after)

    ordered_tasks = sorted(
        unassigned_tasks,
        key=lambda task_id: task_by_id[task_id].width * task_by_id[task_id].height,
        reverse=True,
    )

    for task_id in ordered_tasks:
        route_candidates = []
        for robot_id in range(robot_count):
            slack = context.route_costs_makespan - context.per_robot_costs[robot_id]
            bottleneck_penalty = 1 if robot_id == context.bottleneck_route_id else 0
            effective_slack = slack / (1 + added_counts[robot_id])
            route_candidates.append((bottleneck_penalty, -effective_slack, robot_id))

        route_candidates.sort()
        preferred_count = min(2, robot_count)
        preferred_robots = [item[2] for item in route_candidates[:preferred_count]]

        best_choice = None
        for robot_id in preferred_robots:
            route = routes[robot_id]
            for position in range(len(route) + 1):
                delta = insertion_delta(route, position, task_id)
                choice = (delta, added_counts[robot_id], robot_id, position)
                if best_choice is None or choice < best_choice:
                    best_choice = choice

        _, _, robot_id, position = best_choice
        routes[robot_id].insert(position, task_id)
        added_counts[robot_id] += 1

    return RepairResult(
        solution=MultiRobotSolution(routes=routes),
        note='slack-first geometric insertion with bottleneck avoidance',
    )
