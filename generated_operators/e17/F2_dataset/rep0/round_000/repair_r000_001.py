from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import RepairResult


def repair(partial_solution, unassigned_tasks, context, rng):
    routes = [list(route) for route in partial_solution.routes]
    task_by_id = {task.task_id: task for task in context.instance.tasks}
    robot_count = context.instance.robot_count
    bottleneck = context.bottleneck_route_id
    small_instance = len(context.instance.tasks) <= 16

    pending = list(unassigned_tasks)
    rng.shuffle(pending)
    pending.sort(
        key=lambda task_id: abs(
            task_by_id[task_id].width - task_by_id[task_id].height
        ),
        reverse=True,
    )

    additions = [0] * robot_count

    def center(task):
        return ((task.x_left + task.x_right) * 0.5,
                (task.y_bottom + task.y_top) * 0.5)

    def preferred_mode(task):
        if task.width >= task.height:
            return 0
        return 1

    def pair_score(first, second):
        first_x, first_y = center(first)
        second_x, second_y = center(second)
        mode_mismatch = 1 if preferred_mode(first) != preferred_mode(second) else 0
        horizontal_gap = abs(first_y - second_y)
        vertical_gap = abs(first_x - second_x)
        centroid_gap = abs(first_x - second_x) + abs(first_y - second_y)

        if preferred_mode(first) == 0 and preferred_mode(second) == 0:
            alignment_gap = horizontal_gap
        elif preferred_mode(first) == 1 and preferred_mode(second) == 1:
            alignment_gap = vertical_gap
        else:
            alignment_gap = centroid_gap

        mode_weight = 6.0 if small_instance else 2.0
        scale = first.width + first.height + second.width + second.height
        return mode_weight * mode_mismatch * scale + alignment_gap + 0.2 * centroid_gap

    for task_id in pending:
        task = task_by_id[task_id]
        robot_candidates = list(range(robot_count))
        if robot_count > 1 and 0 <= bottleneck < robot_count:
            robot_candidates.remove(bottleneck)

        choices = []
        for robot_id in robot_candidates:
            route = routes[robot_id]
            if route:
                anchor_position = min(
                    range(len(route)),
                    key=lambda position: pair_score(task, task_by_id[route[position]]),
                )
                geometry_score = pair_score(task, task_by_id[route[anchor_position]])
            else:
                anchor_position = -1
                geometry_score = 0.0

            choices.append((
                geometry_score,
                additions[robot_id],
                context.per_robot_costs[robot_id],
                len(route),
                robot_id,
                anchor_position,
            ))

        choice = min(choices)
        target_robot = choice[4]
        anchor_position = choice[5]
        route = routes[target_robot]

        if anchor_position < 0:
            route.append(task_id)
        else:
            before_position = anchor_position
            after_position = anchor_position + 1
            before_score = pair_score(task, task_by_id[route[anchor_position]])
            after_score = before_score

            if anchor_position > 0:
                before_score += pair_score(task, task_by_id[route[anchor_position - 1]])
            if anchor_position + 1 < len(route):
                after_score += pair_score(task, task_by_id[route[anchor_position + 1]])

            if before_score < after_score:
                route.insert(before_position, task_id)
            else:
                route.insert(after_position, task_id)

        additions[target_robot] += 1

    return RepairResult(
        solution=MultiRobotSolution(routes=routes),
        note='Mode- and axis-alignment clustering with stronger small-instance sensitivity.',
    )
