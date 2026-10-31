from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import RepairResult


def repair(partial_solution, unassigned_tasks, context, rng) -> RepairResult:
    routes = [list(route) for route in partial_solution.routes]
    while len(routes) < context.instance.robot_count:
        routes.append([])

    task_map = {task.task_id: task for task in context.instance.tasks}
    costs = list(context.per_robot_costs)
    while len(costs) < len(routes):
        costs.append(0.0)

    makespan = context.route_costs_makespan
    scale = makespan if makespan > 0.0 else 1.0
    bottleneck = context.bottleneck_route_id
    assigned = [0] * len(routes)

    def center(task_id):
        task = task_map[task_id]
        return ((task.x_left + task.x_right) * 0.5,
                (task.y_bottom + task.y_top) * 0.5)

    def orientation(task_id):
        task = task_map[task_id]
        if task.width > task.height:
            return 0
        if task.height > task.width:
            return 1
        return 2

    def task_priority(task_id):
        if task_id not in task_map:
            return (0.0, 0.0)
        task = task_map[task_id]
        cx, cy = center(task_id)
        distance = abs(cx) + abs(cy)
        short_side = min(task.width, task.height)
        long_side = max(task.width, task.height)
        elongation = long_side / short_side if short_side > 0.0 else long_side
        return (distance, elongation)

    pending = list(unassigned_tasks)
    pending.sort(key=task_priority, reverse=True)

    def placement_score(route, position, task_id):
        if task_id not in task_map:
            return float(position)

        tx, ty = center(task_id)
        task_orientation = orientation(task_id)
        neighbors = []
        if position > 0:
            neighbors.append(route[position - 1])
        if position < len(route):
            neighbors.append(route[position])

        if not neighbors:
            return 2.0 * (abs(tx) + abs(ty))

        score = 0.0
        for neighbor_id in neighbors:
            if neighbor_id not in task_map:
                continue
            nx, ny = center(neighbor_id)
            neighbor_orientation = orientation(neighbor_id)

            if task_orientation == 0:
                alignment_gap = abs(ty - ny) + 0.35 * abs(tx - nx)
            elif task_orientation == 1:
                alignment_gap = abs(tx - nx) + 0.35 * abs(ty - ny)
            else:
                alignment_gap = 0.65 * (abs(tx - nx) + abs(ty - ny))

            if (task_orientation != 2 and neighbor_orientation != 2
                    and task_orientation != neighbor_orientation):
                alignment_gap += scale * 0.07
            score += alignment_gap

        return score / len(neighbors)

    for task_id in pending:
        candidate_robots = list(range(len(routes)))
        if len(candidate_robots) > 1 and 0 <= bottleneck < len(routes):
            candidate_robots.remove(bottleneck)

        best_choice = None
        best_score = None

        for robot_id in candidate_robots:
            slack = makespan - costs[robot_id]
            slack_reward = slack * 0.30
            assignment_penalty = assigned[robot_id] * scale * 0.06

            for position in range(len(routes[robot_id]) + 1):
                score = placement_score(routes[robot_id], position, task_id)
                score += assignment_penalty - slack_reward
                score += rng.random() * 1.0e-9
                if best_score is None or score < best_score:
                    best_score = score
                    best_choice = (robot_id, position)

        if best_choice is None:
            robot_id = min(range(len(routes)), key=lambda r: (costs[r], len(routes[r])))
            position = len(routes[robot_id])
        else:
            robot_id, position = best_choice

        routes[robot_id].insert(position, task_id)
        assigned[robot_id] += 1

    return RepairResult(
        solution=MultiRobotSolution(routes=routes),
        note="distant-first sweep-alignment repair on non-bottleneck routes"
    )