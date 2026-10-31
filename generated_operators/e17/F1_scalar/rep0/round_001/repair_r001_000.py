from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import RepairResult


def repair(partial_solution, unassigned_tasks, context, rng):
    routes = [list(route) for route in partial_solution.routes]
    task_by_id = {task.task_id: task for task in context.instance.tasks}
    robot_count = context.instance.robot_count

    while len(routes) < robot_count:
        routes.append([])

    base_costs = list(context.per_robot_costs)
    while len(base_costs) < robot_count:
        base_costs.append(0.0)

    inserted_counts = [0] * robot_count
    bottleneck = context.bottleneck_route_id

    def centroid(task_id):
        task = task_by_id[task_id]
        return ((task.x_left + task.x_right) * 0.5,
                (task.y_bottom + task.y_top) * 0.5)

    def distance_sq(first_id, second_id):
        ax, ay = centroid(first_id)
        bx, by = centroid(second_id)
        dx = ax - bx
        dy = ay - by
        return dx * dx + dy * dy

    def best_position(route, task_id):
        if not route:
            return 0
        best_pos = 0
        best_score = None
        for pos in range(len(route) + 1):
            score = 0.0
            neighbors = 0
            if pos > 0:
                score += distance_sq(route[pos - 1], task_id)
                neighbors += 1
            if pos < len(route):
                score += distance_sq(task_id, route[pos])
                neighbors += 1
            score /= neighbors
            if best_score is None or score < best_score:
                best_score = score
                best_pos = pos
        return best_pos

    ordered_tasks = list(unassigned_tasks)
    ordered_tasks.sort(
        key=lambda task_id: task_by_id[task_id].width * task_by_id[task_id].height,
        reverse=True
    )

    for task_id in ordered_tasks:
        candidates = list(range(robot_count))
        if robot_count > 1 and 0 <= bottleneck < robot_count:
            candidates.remove(bottleneck)

        target = min(
            candidates,
            key=lambda robot_id: (
                inserted_counts[robot_id],
                base_costs[robot_id],
                len(routes[robot_id]),
                robot_id
            )
        )
        position = best_position(routes[target], task_id)
        routes[target].insert(position, task_id)
        inserted_counts[target] += 1

    return RepairResult(
        solution=MultiRobotSolution(routes=routes),
        note="High-slack non-bottleneck assignment with nearest-neighbor insertion"
    )