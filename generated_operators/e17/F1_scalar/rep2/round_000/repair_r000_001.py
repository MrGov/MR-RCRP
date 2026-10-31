from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import RepairResult


def repair(partial_solution, unassigned_tasks, context, rng) -> RepairResult:
    routes = [list(route) for route in partial_solution.routes]
    if not routes:
        routes = [[] for _ in range(context.instance.robot_count)]

    task_by_id = {task.task_id: task for task in context.instance.tasks}
    added_counts = [0] * len(routes)

    def is_horizontal(task_id):
        task = task_by_id[task_id]
        return task.width >= task.height

    def centroid(task_id):
        task = task_by_id[task_id]
        return ((task.x_left + task.x_right) * 0.5,
                (task.y_bottom + task.y_top) * 0.5)

    def aspect(task_id):
        task = task_by_id[task_id]
        short_side = min(task.width, task.height)
        long_side = max(task.width, task.height)
        if short_side <= 0.0:
            return long_side
        return long_side / short_side

    def affinity(first_id, second_id, horizontal):
        ax, ay = centroid(first_id)
        bx, by = centroid(second_id)
        if horizontal:
            alignment_gap = abs(ay - by) + 0.25 * abs(ax - bx)
        else:
            alignment_gap = abs(ax - bx) + 0.25 * abs(ay - by)
        return alignment_gap + abs(aspect(first_id) - aspect(second_id))

    horizontal_tasks = []
    vertical_tasks = []
    for task_id in unassigned_tasks:
        if is_horizontal(task_id):
            horizontal_tasks.append(task_id)
        else:
            vertical_tasks.append(task_id)

    horizontal_tasks.sort(key=lambda task_id: (
        centroid(task_id)[1], centroid(task_id)[0], rng.random()
    ))
    vertical_tasks.sort(key=lambda task_id: (
        centroid(task_id)[0], centroid(task_id)[1], rng.random()
    ))

    if rng.random() < 0.5:
        ordered_tasks = horizontal_tasks + vertical_tasks
    else:
        ordered_tasks = vertical_tasks + horizontal_tasks

    for task_id in ordered_tasks:
        horizontal = is_horizontal(task_id)
        route_choices = []

        for robot_id, route in enumerate(routes):
            same_mode = 0
            best_affinity = None
            best_neighbor = None
            for existing_id in route:
                if is_horizontal(existing_id) == horizontal:
                    same_mode += 1
                    score = affinity(existing_id, task_id, horizontal)
                    if best_affinity is None or score < best_affinity:
                        best_affinity = score
                        best_neighbor = existing_id

            if best_affinity is None:
                best_affinity = float("inf")

            route_choices.append((
                robot_id == context.bottleneck_route_id,
                -same_mode,
                added_counts[robot_id],
                best_affinity,
                context.per_robot_costs[robot_id],
                rng.random(),
                robot_id,
                best_neighbor
            ))

        choice = min(route_choices)
        target_robot = choice[-2]
        neighbor = choice[-1]

        if neighbor is None:
            routes[target_robot].append(task_id)
        else:
            neighbor_index = routes[target_robot].index(neighbor)
            routes[target_robot].insert(neighbor_index + 1, task_id)
        added_counts[target_robot] += 1

    return RepairResult(
        solution=MultiRobotSolution(routes=routes),
        note="sweep-alignment affinity repair"
    )
