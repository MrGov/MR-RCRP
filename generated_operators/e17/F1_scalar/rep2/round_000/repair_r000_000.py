from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import RepairResult


def repair(partial_solution, unassigned_tasks, context, rng) -> RepairResult:
    routes = [list(route) for route in partial_solution.routes]
    if not routes:
        routes = [[] for _ in range(context.instance.robot_count)]

    task_by_id = {task.task_id: task for task in context.instance.tasks}
    added_counts = [0] * len(routes)
    tie_breakers = {task_id: rng.random() for task_id in unassigned_tasks}

    def centroid(task_id):
        task = task_by_id[task_id]
        return ((task.x_left + task.x_right) * 0.5,
                (task.y_bottom + task.y_top) * 0.5)

    def distance_sq(first_id, second_id):
        ax, ay = centroid(first_id)
        bx, by = centroid(second_id)
        return (ax - bx) ** 2 + (ay - by) ** 2

    def best_position(route, task_id):
        if not route:
            return 0, 0.0
        best_pos = 0
        best_score = None
        for pos in range(len(route) + 1):
            if pos == 0:
                score = distance_sq(task_id, route[0])
            elif pos == len(route):
                score = distance_sq(route[-1], task_id)
            else:
                before = route[pos - 1]
                after = route[pos]
                score = (distance_sq(before, task_id)
                         + distance_sq(task_id, after)
                         - distance_sq(before, after))
            if best_score is None or score < best_score:
                best_score = score
                best_pos = pos
        return best_pos, best_score

    ordered_tasks = sorted(
        unassigned_tasks,
        key=lambda task_id: (
            -(centroid(task_id)[0] ** 2 + centroid(task_id)[1] ** 2),
            tie_breakers[task_id]
        )
    )

    for task_id in ordered_tasks:
        robot_order = list(range(len(routes)))
        rng.shuffle(robot_order)
        robot_order.sort(key=lambda robot_id: (
            robot_id == context.bottleneck_route_id,
            added_counts[robot_id],
            context.per_robot_costs[robot_id],
            len(routes[robot_id])
        ))

        window = robot_order[:min(2, len(robot_order))]
        choices = []
        for robot_id in window:
            position, geometry_score = best_position(routes[robot_id], task_id)
            choices.append((geometry_score, rng.random(), robot_id, position))

        _, _, target_robot, target_position = min(choices)
        routes[target_robot].insert(target_position, task_id)
        added_counts[target_robot] += 1

    return RepairResult(
        solution=MultiRobotSolution(routes=routes),
        note="slack-window geometry repair"
    )
