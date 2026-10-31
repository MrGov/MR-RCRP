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
        return RepairResult(solution=MultiRobotSolution(routes=routes), note="orientation cluster repair")

    task_by_id = {task.task_id: task for task in context.instance.tasks}
    costs = [context.per_robot_costs[r] if r < len(context.per_robot_costs) else 0.0 for r in range(robot_count)]
    bottleneck = context.bottleneck_route_id
    added = [0] * robot_count

    def center(task_id):
        task = task_by_id[task_id]
        return ((task.x_left + task.x_right) * 0.5, (task.y_bottom + task.y_top) * 0.5)

    def orientation(task_id):
        task = task_by_id[task_id]
        return 0 if task.width >= task.height else 1

    def distance(task_a, task_b):
        ax, ay = center(task_a)
        bx, by = center(task_b)
        dx = ax - bx
        dy = ay - by
        return (dx * dx + dy * dy) ** 0.5

    def route_orientation_penalty(route, task_id):
        known = [existing for existing in route if existing in task_by_id]
        if not known:
            return 0.0
        matching = sum(1 for existing in known if orientation(existing) == orientation(task_id))
        return 1.0 - matching / len(known)

    def best_position(route, task_id):
        best = None
        choices = []
        task = task_by_id[task_id]
        scale = task.width + task.height
        if scale < 1.0:
            scale = 1.0

        for position in range(len(route) + 1):
            previous_id = route[position - 1] if position > 0 else None
            next_id = route[position] if position < len(route) else None
            delta = 0.0
            switches = 0.0

            if previous_id in task_by_id:
                delta += distance(previous_id, task_id)
                if orientation(previous_id) != orientation(task_id):
                    switches += 1.0
            if next_id in task_by_id:
                delta += distance(task_id, next_id)
                if orientation(next_id) != orientation(task_id):
                    switches += 1.0
            if previous_id in task_by_id and next_id in task_by_id:
                delta -= distance(previous_id, next_id)

            score = delta / scale + 0.65 * switches
            if best is None or score < best - 1e-12:
                best = score
                choices = [position]
            elif abs(score - best) <= 1e-12:
                choices.append(position)

        return best, choices[rng.randrange(len(choices))]

    horizontal = []
    vertical = []
    for task_id in unassigned_tasks:
        if orientation(task_id) == 0:
            horizontal.append(task_id)
        else:
            vertical.append(task_id)

    rng.shuffle(horizontal)
    rng.shuffle(vertical)
    horizontal.sort(key=lambda task_id: (center(task_id)[1], center(task_id)[0]))
    vertical.sort(key=lambda task_id: (center(task_id)[0], center(task_id)[1]))

    if rng.random() < 0.5:
        batches = [horizontal, vertical]
    else:
        batches = [vertical, horizontal]

    eligible = list(range(robot_count))
    if robot_count > 1 and 0 <= bottleneck < robot_count:
        eligible.remove(bottleneck)

    minimum_cost = min(costs) if costs else 0.0
    cost_span = (max(costs) - minimum_cost) if costs else 0.0
    if cost_span <= 0.0:
        cost_span = 1.0

    for batch in batches:
        for task_id in batch:
            ranked = []
            for robot_id in eligible:
                local_score, position = best_position(routes[robot_id], task_id)
                cost_pressure = (costs[robot_id] - minimum_cost) / cost_span
                mode_penalty = route_orientation_penalty(routes[robot_id], task_id)
                score = local_score + 0.9 * mode_penalty + 0.85 * cost_pressure + 0.35 * added[robot_id]
                ranked.append((score, rng.random(), robot_id, position))

            ranked.sort()
            _, _, chosen_robot, chosen_position = ranked[0]
            routes[chosen_robot].insert(chosen_position, task_id)
            added[chosen_robot] += 1

    return RepairResult(solution=MultiRobotSolution(routes=routes), note="axis-aligned spatial clustering with bottleneck avoidance")