from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import RepairResult


def repair(partial_solution, unassigned_tasks, context, rng):
    routes = [list(route) for route in partial_solution.routes]
    task_by_id = {task.task_id: task for task in context.instance.tasks}
    robot_count = context.instance.robot_count
    bottleneck = context.bottleneck_route_id

    pending = list(unassigned_tasks)
    rng.shuffle(pending)
    pending.sort(
        key=lambda task_id: task_by_id[task_id].width * task_by_id[task_id].height,
        reverse=True,
    )

    inserted_counts = [0] * robot_count
    makespan = context.route_costs_makespan

    def centroid(task_id):
        task = task_by_id[task_id]
        return ((task.x_left + task.x_right) * 0.5,
                (task.y_bottom + task.y_top) * 0.5)

    def distance(first_id, second_id):
        ax, ay = centroid(first_id)
        bx, by = centroid(second_id)
        return abs(ax - bx) + abs(ay - by)

    def insertion_position(route, task_id):
        if not route:
            return 0
        task_x, task_y = centroid(task_id)
        depot_x, depot_y = context.instance.depot
        best_position = 0
        best_detour = None
        for position in range(len(route) + 1):
            if position == 0:
                left_distance = abs(task_x - depot_x) + abs(task_y - depot_y)
            else:
                left_distance = distance(route[position - 1], task_id)
            if position == len(route):
                right_distance = abs(task_x - depot_x) + abs(task_y - depot_y)
            else:
                right_distance = distance(task_id, route[position])

            if position == 0 and position == len(route):
                replaced_distance = 0.0
            elif position == 0:
                next_x, next_y = centroid(route[position])
                replaced_distance = abs(next_x - depot_x) + abs(next_y - depot_y)
            elif position == len(route):
                prev_x, prev_y = centroid(route[position - 1])
                replaced_distance = abs(prev_x - depot_x) + abs(prev_y - depot_y)
            else:
                replaced_distance = distance(route[position - 1], route[position])

            detour = left_distance + right_distance - replaced_distance
            if best_detour is None or detour < best_detour:
                best_detour = detour
                best_position = position
        return best_position

    for task_id in pending:
        candidates = list(range(robot_count))
        if robot_count > 1 and 0 <= bottleneck < robot_count:
            candidates.remove(bottleneck)

        target_robot = min(
            candidates,
            key=lambda robot_id: (
                inserted_counts[robot_id],
                -(makespan - context.per_robot_costs[robot_id]),
                len(routes[robot_id]),
                robot_id,
            ),
        )
        position = insertion_position(routes[target_robot], task_id)
        routes[target_robot].insert(position, task_id)
        inserted_counts[target_robot] += 1

    return RepairResult(
        solution=MultiRobotSolution(routes=routes),
        note='High-slack assignment with geometric detour insertion and bottleneck avoidance.',
    )
