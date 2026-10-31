from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import RepairResult


def repair(partial_solution, unassigned_tasks, context, rng):
    routes = [list(route) for route in partial_solution.routes]
    robot_count = context.instance.robot_count
    while len(routes) < robot_count:
        routes.append([])

    task_by_id = {task.task_id: task for task in context.instance.tasks}
    present = set()
    for route in routes:
        present.update(route)

    pending = []
    for task_id in unassigned_tasks:
        if task_id not in present and task_id not in pending:
            pending.append(task_id)

    small_instance = len(context.instance.tasks) <= 16
    bottleneck = context.bottleneck_route_id
    makespan = context.route_costs_makespan

    def interval_overlap(a1, a2, b1, b2):
        return max(0.0, min(a2, b2) - max(a1, b1))

    def preferred_axis(task):
        if task.width >= task.height:
            return 0
        return 1

    def compatibility(first_id, second_id):
        first = task_by_id[first_id]
        second = task_by_id[second_id]
        x_overlap = interval_overlap(
            first.x_left, first.x_right, second.x_left, second.x_right
        )
        y_overlap = interval_overlap(
            first.y_bottom, first.y_top, second.y_bottom, second.y_top
        )
        x_scale = max(first.width, second.width, 1.0)
        y_scale = max(first.height, second.height, 1.0)
        vertical_corridor = x_overlap / x_scale
        horizontal_corridor = y_overlap / y_scale
        corridor = max(vertical_corridor, horizontal_corridor)

        same_axis = preferred_axis(first) == preferred_axis(second)
        if small_instance:
            axis_bonus = 1.25 if same_axis else -0.75
        else:
            axis_bonus = 0.35 if same_axis else 0.0

        first_cx = (first.x_left + first.x_right) * 0.5
        first_cy = (first.y_bottom + first.y_top) * 0.5
        second_cx = (second.x_left + second.x_right) * 0.5
        second_cy = (second.y_bottom + second.y_top) * 0.5
        gap = abs(first_cx - second_cx) + abs(first_cy - second_cy)
        return corridor * 3.0 + axis_bonus - gap * 0.002

    random_ties = {task_id: rng.random() for task_id in pending}
    if small_instance:
        pending.sort(
            key=lambda task_id: (
                -abs(task_by_id[task_id].width - task_by_id[task_id].height),
                random_ties[task_id]
            )
        )
    else:
        pending.sort(
            key=lambda task_id: (
                (task_by_id[task_id].x_left + task_by_id[task_id].x_right) * 0.5,
                (task_by_id[task_id].y_bottom + task_by_id[task_id].y_top) * 0.5,
                random_ties[task_id]
            )
        )

    inserted = [0] * len(routes)

    for task_id in pending:
        candidate_robots = list(range(len(routes)))
        if len(candidate_robots) > 1 and 0 <= bottleneck < len(routes):
            candidate_robots.remove(bottleneck)

        best_choice = None
        best_key = None
        for robot_id in candidate_robots:
            route = routes[robot_id]
            if robot_id < len(context.per_robot_costs):
                slack = makespan - context.per_robot_costs[robot_id]
            else:
                slack = makespan

            for position in range(len(route) + 1):
                alignment = 0.0
                neighbor_count = 0
                if position > 0:
                    alignment += compatibility(task_id, route[position - 1])
                    neighbor_count += 1
                if position < len(route):
                    alignment += compatibility(task_id, route[position])
                    neighbor_count += 1
                if neighbor_count:
                    alignment /= neighbor_count

                key = (
                    alignment,
                    -inserted[robot_id],
                    slack,
                    -len(route),
                    rng.random()
                )
                if best_key is None or key > best_key:
                    best_key = key
                    best_choice = (robot_id, position)

        robot_id, position = best_choice
        routes[robot_id].insert(position, task_id)
        inserted[robot_id] += 1

    return RepairResult(
        solution=MultiRobotSolution(routes=routes),
        note="horizontal-vertical corridor alignment with critical-route avoidance"
    )