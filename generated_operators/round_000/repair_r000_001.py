from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import RepairResult


def repair(partial_solution, unassigned_tasks, context, rng):
    routes = [list(route) for route in partial_solution.routes]
    task_by_id = {task.task_id: task for task in context.instance.tasks}
    robot_count = context.instance.robot_count

    def features(task_id):
        task = task_by_id[task_id]
        cx = (task.x_left + task.x_right) * 0.5
        cy = (task.y_bottom + task.y_top) * 0.5
        preferred_mode = 0 if task.width >= task.height else 1
        major = max(task.width, task.height)
        minor = min(task.width, task.height)
        aspect = major / minor if minor > 0 else major + 1.0
        return cx, cy, preferred_mode, aspect

    def compatibility(first_id, second_id):
        ax, ay, amode, aaspect = features(first_id)
        bx, by, bmode, baspect = features(second_id)
        mode_penalty = 0.0 if amode == bmode else 2.0
        if amode == 0:
            alignment_gap = abs(ay - by)
            travel_gap = abs(ax - bx)
        else:
            alignment_gap = abs(ax - bx)
            travel_gap = abs(ay - by)
        aspect_gap = abs(aaspect - baspect)
        return mode_penalty + alignment_gap + 0.35 * travel_gap + 0.5 * aspect_gap

    ordered_tasks = list(unassigned_tasks)
    ordered_tasks.sort(
        key=lambda task_id: (
            features(task_id)[2],
            -features(task_id)[3],
            features(task_id)[1],
            features(task_id)[0],
        )
    )
    inserted_counts = [0] * robot_count

    for task_id in ordered_tasks:
        best_choice = None
        best_key = None
        for robot_id in range(robot_count):
            route = routes[robot_id]
            bottleneck_penalty = 1 if robot_id == context.bottleneck_route_id and robot_count > 1 else 0
            slack = context.route_costs_makespan - context.per_robot_costs[robot_id]
            if not route:
                key = (bottleneck_penalty, inserted_counts[robot_id], -slack, 0.0, rng.random())
                choice = (robot_id, 0)
                if best_key is None or key < best_key:
                    best_key = key
                    best_choice = choice
                continue

            for position in range(len(route) + 1):
                neighbor_scores = []
                if position > 0:
                    neighbor_scores.append(compatibility(route[position - 1], task_id))
                if position < len(route):
                    neighbor_scores.append(compatibility(task_id, route[position]))
                local_score = sum(neighbor_scores) / len(neighbor_scores)
                key = (
                    bottleneck_penalty,
                    inserted_counts[robot_id],
                    -slack,
                    local_score,
                    rng.random(),
                )
                if best_key is None or key < best_key:
                    best_key = key
                    best_choice = (robot_id, position)

        robot_id, position = best_choice
        routes[robot_id].insert(position, task_id)
        inserted_counts[robot_id] += 1

    return RepairResult(
        solution=MultiRobotSolution(routes=routes),
        note="shape and sweep-axis alignment repair with critical-route avoidance",
    )