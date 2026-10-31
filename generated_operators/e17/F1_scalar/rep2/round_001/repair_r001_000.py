from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import RepairResult


def repair(partial_solution, unassigned_tasks, context, rng):
    routes = [list(route) for route in partial_solution.routes]
    while len(routes) < context.instance.robot_count:
        routes.append([])
    if not routes:
        return RepairResult(solution=MultiRobotSolution(routes=routes), note="slack-band geometry repair: no robots")

    task_by_id = {task.task_id: task for task in context.instance.tasks}
    existing = set()
    for route in routes:
        existing.update(route)

    pending = []
    seen = set(existing)
    for task_id in unassigned_tasks:
        if task_id not in seen:
            pending.append(task_id)
            seen.add(task_id)

    costs = []
    for robot_id in range(len(routes)):
        if robot_id < len(context.per_robot_costs):
            costs.append(context.per_robot_costs[robot_id])
        else:
            costs.append(0.0)

    makespan = context.route_costs_makespan
    bottleneck = context.bottleneck_route_id
    added = [0] * len(routes)

    def centroid(task):
        return ((task.x_left + task.x_right) * 0.5,
                (task.y_bottom + task.y_top) * 0.5)

    def distance(first, second):
        ax, ay = centroid(first)
        bx, by = centroid(second)
        dx = ax - bx
        dy = ay - by
        return (dx * dx + dy * dy) ** 0.5

    def shape_gap(first, second):
        first_scale = first.width + first.height + 1.0
        second_scale = second.width + second.height + 1.0
        first_bias = (first.width - first.height) / first_scale
        second_bias = (second.width - second.height) / second_scale
        return abs(first_bias - second_bias)

    def best_position(route, task):
        if not route:
            return 0, 0.0
        best_pos = len(route)
        best_penalty = None
        for pos in range(len(route) + 1):
            penalty = 0.0
            previous = task_by_id.get(route[pos - 1]) if pos > 0 else None
            following = task_by_id.get(route[pos]) if pos < len(route) else None
            if previous is not None:
                penalty += distance(previous, task) + 0.35 * shape_gap(previous, task)
            if following is not None:
                penalty += distance(task, following) + 0.35 * shape_gap(task, following)
            if previous is not None and following is not None:
                penalty -= distance(previous, following)
            if best_penalty is None or penalty < best_penalty:
                best_penalty = penalty
                best_pos = pos
        return best_pos, best_penalty

    pending.sort(key=lambda task_id: -(task_by_id[task_id].width * task_by_id[task_id].height)
                 if task_id in task_by_id else 0.0)

    for task_id in pending:
        task = task_by_id.get(task_id)
        eligible = [r for r in range(len(routes)) if r != bottleneck]
        if not eligible:
            eligible = list(range(len(routes)))

        minimum_added = min(added[r] for r in eligible)
        balanced = [r for r in eligible if added[r] == minimum_added]
        slacks = {r: makespan - costs[r] for r in balanced}
        maximum_slack = max(slacks.values())
        tolerance = 0.20 * (abs(maximum_slack) + 1.0)
        slack_band = [r for r in balanced if slacks[r] >= maximum_slack - tolerance]

        if task is None:
            target = max(slack_band, key=lambda r: (slacks[r], -len(routes[r])))
            position = len(routes[target])
        else:
            choices = []
            for robot_id in slack_band:
                position, penalty = best_position(routes[robot_id], task)
                choices.append((penalty, -slacks[robot_id], len(routes[robot_id]), rng.random(), robot_id, position))
            choice = min(choices)
            target = choice[4]
            position = choice[5]

        routes[target].insert(position, task_id)
        added[target] += 1

    return RepairResult(
        solution=MultiRobotSolution(routes=routes),
        note="slack-band balancing with geometry-aware insertion"
    )