from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import RepairResult


def repair(partial_solution, unassigned_tasks, context, rng):
    routes = [list(route) for route in partial_solution.routes]
    robot_count = context.instance.robot_count
    while len(routes) < robot_count:
        routes.append([])

    task_by_id = {task.task_id: task for task in context.instance.tasks}
    existing = set()
    for route in routes:
        existing.update(route)

    pending = []
    for task_id in unassigned_tasks:
        if task_id not in existing and task_id not in pending:
            pending.append(task_id)

    def centroid(task_id):
        task = task_by_id[task_id]
        return ((task.x_left + task.x_right) * 0.5,
                (task.y_bottom + task.y_top) * 0.5)

    def aspect(task_id):
        task = task_by_id[task_id]
        long_side = max(task.width, task.height)
        if long_side == 0:
            return 1.0
        return min(task.width, task.height) / long_side

    def neighbor_score(task_id, neighbor_id):
        tx, ty = centroid(task_id)
        nx, ny = centroid(neighbor_id)
        distance = abs(tx - nx) + abs(ty - ny)
        shape_gap = abs(aspect(task_id) - aspect(neighbor_id))
        return distance + shape_gap * 20.0

    added = [0] * len(routes)
    makespan = context.route_costs_makespan
    bottleneck = context.bottleneck_route_id

    for task_id in pending:
        candidates = list(range(len(routes)))
        if len(candidates) > 1 and 0 <= bottleneck < len(routes):
            candidates.remove(bottleneck)

        slack = {}
        for robot_id in candidates:
            if robot_id < len(context.per_robot_costs):
                slack[robot_id] = makespan - context.per_robot_costs[robot_id]
            else:
                slack[robot_id] = makespan

        best_slack = max(slack.values()) if slack else 0.0
        tolerance = max(1.0, abs(best_slack) * 0.15)
        slack_group = [robot_id for robot_id in candidates
                       if best_slack - slack[robot_id] <= tolerance]
        target_robot = min(
            slack_group,
            key=lambda robot_id: (
                added[robot_id],
                len(routes[robot_id]),
                rng.random()
            )
        )

        route = routes[target_robot]
        if not route:
            route.append(task_id)
        else:
            best_position = 0
            best_score = None
            for position in range(len(route) + 1):
                score = 0.0
                if position > 0:
                    score += neighbor_score(task_id, route[position - 1])
                if position < len(route):
                    score += neighbor_score(task_id, route[position])
                if 0 < position < len(route):
                    score *= 0.5
                score += rng.random() * 1e-9
                if best_score is None or score < best_score:
                    best_score = score
                    best_position = position
            route.insert(best_position, task_id)
        added[target_robot] += 1

    return RepairResult(
        solution=MultiRobotSolution(routes=routes),
        note="slack-guided geometry and aspect-compatible insertion"
    )