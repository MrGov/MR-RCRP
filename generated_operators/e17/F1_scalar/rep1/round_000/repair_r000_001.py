from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import RepairResult


def repair(partial_solution, unassigned_tasks, context, rng) -> RepairResult:
    routes = [list(route) for route in partial_solution.routes]
    task_by_id = {task.task_id: task for task in context.instance.tasks}
    robot_count = context.instance.robot_count
    inserted_counts = [0] * robot_count

    def orientation(task_id):
        task = task_by_id[task_id]
        return 0 if task.width >= task.height else 1

    def aspect(task_id):
        task = task_by_id[task_id]
        short_side = min(task.width, task.height)
        if short_side <= 0:
            return 1.0
        return max(task.width, task.height) / short_side

    def center(task_id):
        task = task_by_id[task_id]
        return ((task.x_left + task.x_right) * 0.5,
                (task.y_bottom + task.y_top) * 0.5)

    def route_alignment_penalty(route, task_id):
        if not route:
            return 1
        wanted = orientation(task_id)
        matches = sum(1 for existing_id in route if orientation(existing_id) == wanted)
        return len(route) - matches

    def neighbor_score(existing_id, task_id):
        first = center(existing_id)
        second = center(task_id)
        dx = first[0] - second[0]
        dy = first[1] - second[1]
        spatial_gap = (dx * dx + dy * dy) ** 0.5
        orientation_gap = 0 if orientation(existing_id) == orientation(task_id) else 1
        aspect_gap = abs(aspect(existing_id) - aspect(task_id))
        return orientation_gap * 1000.0 + aspect_gap * 10.0 + spatial_gap

    ordered_tasks = sorted(
        unassigned_tasks,
        key=lambda task_id: (
            orientation(task_id),
            -aspect(task_id),
            task_by_id[task_id].task_id,
        ),
    )

    for task_id in ordered_tasks:
        best_robot = None
        best_robot_key = None
        for robot_id in range(robot_count):
            bottleneck_penalty = 1 if robot_id == context.bottleneck_route_id else 0
            alignment_penalty = route_alignment_penalty(routes[robot_id], task_id)
            cost_hint = context.per_robot_costs[robot_id]
            key = (
                bottleneck_penalty,
                alignment_penalty,
                inserted_counts[robot_id],
                cost_hint,
                len(routes[robot_id]),
                robot_id,
            )
            if best_robot_key is None or key < best_robot_key:
                best_robot_key = key
                best_robot = robot_id

        route = routes[best_robot]
        if not route:
            position = 0
        else:
            neighbor_index = min(
                range(len(route)),
                key=lambda index: neighbor_score(route[index], task_id),
            )
            if neighbor_index + 1 < len(route):
                left_score = neighbor_score(route[neighbor_index], task_id)
                right_score = neighbor_score(route[neighbor_index + 1], task_id)
                position = neighbor_index + 1 if left_score <= right_score else neighbor_index + 2
            else:
                position = len(route)

        route.insert(position, task_id)
        inserted_counts[best_robot] += 1

    return RepairResult(
        solution=MultiRobotSolution(routes=routes),
        note='aspect-ratio and sweep-alignment affinity repair',
    )
