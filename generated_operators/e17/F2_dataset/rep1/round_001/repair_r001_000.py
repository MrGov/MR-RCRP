from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import RepairResult

def repair(partial_solution, unassigned_tasks, context, rng):
    robot_count = context.instance.robot_count
    routes = [list(route) for route in partial_solution.routes[:robot_count]]
    while len(routes) < robot_count:
        routes.append([])

    if len(partial_solution.routes) > robot_count and robot_count > 0:
        for extra_route in partial_solution.routes[robot_count:]:
            for task_id in extra_route:
                target = min(range(robot_count), key=lambda r: len(routes[r]))
                routes[target].append(task_id)

    if robot_count == 0:
        return RepairResult(solution=MultiRobotSolution(routes=routes), note="slack geometry repair")

    task_by_id = {task.task_id: task for task in context.instance.tasks}
    costs = [context.per_robot_costs[r] if r < len(context.per_robot_costs) else 0.0 for r in range(robot_count)]
    makespan = context.route_costs_makespan
    bottleneck = context.bottleneck_route_id
    assigned_counts = [0] * robot_count

    def center(task_id):
        task = task_by_id[task_id]
        return ((task.x_left + task.x_right) * 0.5, (task.y_bottom + task.y_top) * 0.5)

    def distance(a, b):
        ax, ay = center(a)
        bx, by = center(b)
        dx = ax - bx
        dy = ay - by
        return (dx * dx + dy * dy) ** 0.5

    def shape_value(task_id):
        task = task_by_id[task_id]
        total = task.width + task.height
        if total <= 0.0:
            return 0.0
        return (task.width - task.height) / total

    def insertion_score(route, position, task_id):
        previous_id = route[position - 1] if position > 0 else None
        next_id = route[position] if position < len(route) else None
        travel = 0.0
        shape = 0.0
        neighbors = 0

        if previous_id in task_by_id:
            travel += distance(previous_id, task_id)
            shape += abs(shape_value(previous_id) - shape_value(task_id))
            neighbors += 1
        if next_id in task_by_id:
            travel += distance(task_id, next_id)
            shape += abs(shape_value(next_id) - shape_value(task_id))
            neighbors += 1
        if previous_id in task_by_id and next_id in task_by_id:
            travel -= distance(previous_id, next_id)
        if neighbors:
            shape /= neighbors

        task = task_by_id[task_id]
        scale = task.width + task.height
        if scale < 1.0:
            scale = 1.0
        return travel / scale + 0.8 * shape

    pending = list(unassigned_tasks)
    rng.shuffle(pending)
    pending.sort(key=lambda task_id: task_by_id[task_id].width * task_by_id[task_id].height, reverse=True)

    eligible = list(range(robot_count))
    if robot_count > 1 and 0 <= bottleneck < robot_count:
        eligible.remove(bottleneck)

    min_cost = min(costs) if costs else 0.0
    max_cost = max(costs) if costs else 0.0
    cost_span = max_cost - min_cost
    if cost_span <= 0.0:
        cost_span = 1.0

    for task_id in pending:
        candidates = []
        for robot_id in eligible:
            route = routes[robot_id]
            best_position = 0
            best_local = None
            for position in range(len(route) + 1):
                local = insertion_score(route, position, task_id)
                if best_local is None or local < best_local:
                    best_local = local
                    best_position = position

            cost_pressure = (costs[robot_id] - min_cost) / cost_span
            slack = makespan - costs[robot_id]
            slack_bonus = slack / (abs(makespan) + 1.0)
            score = best_local + 1.15 * cost_pressure + 0.4 * assigned_counts[robot_id] - 0.35 * slack_bonus
            candidates.append((score, rng.random(), robot_id, best_position))

        candidates.sort()
        _, _, chosen_robot, chosen_position = candidates[0]
        routes[chosen_robot].insert(chosen_position, task_id)
        assigned_counts[chosen_robot] += 1

    return RepairResult(solution=MultiRobotSolution(routes=routes), note="slack-first geometry-compatible insertion")