from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import RepairResult


def repair(partial_solution, unassigned_tasks, context, rng):
    routes = [list(route) for route in partial_solution.routes]
    while len(routes) < context.instance.robot_count:
        routes.append([])

    if not routes:
        return RepairResult(solution=MultiRobotSolution(routes=routes), note="no robots")

    task_by_id = {task.task_id: task for task in context.instance.tasks}
    depot_x, depot_y = context.instance.depot
    bottleneck = context.bottleneck_route_id
    costs = list(context.per_robot_costs)
    makespan = context.route_costs_makespan

    def center(task):
        return ((task.x_left + task.x_right) * 0.5,
                (task.y_bottom + task.y_top) * 0.5)

    def squared_distance(ax, ay, bx, by):
        dx = ax - bx
        dy = ay - by
        return dx * dx + dy * dy

    def route_cost(route_id):
        if route_id < len(costs):
            return costs[route_id]
        return 0.0

    def route_anchor(route):
        sx = 0.0
        sy = 0.0
        count = 0
        for task_id in route:
            task = task_by_id.get(task_id)
            if task is not None:
                cx, cy = center(task)
                sx += cx
                sy += cy
                count += 1
        if count == 0:
            return depot_x, depot_y
        return sx / count, sy / count

    pending = []
    used = set()
    for task_id in unassigned_tasks:
        if task_id not in used:
            pending.append(task_id)
            used.add(task_id)

    def farthest_key(task_id):
        task = task_by_id.get(task_id)
        if task is None:
            return (0.0, 0.0)
        cx, cy = center(task)
        radial = squared_distance(cx, cy, depot_x, depot_y)
        elongated = max(task.width, task.height)
        return (radial, elongated)

    pending.sort(key=farthest_key, reverse=True)

    for task_id in pending:
        task = task_by_id.get(task_id)
        candidate_routes = [r for r in range(len(routes)) if r != bottleneck]
        if not candidate_routes:
            candidate_routes = list(range(len(routes)))

        if task is None:
            target = min(candidate_routes, key=lambda r: (route_cost(r), len(routes[r]), r))
            routes[target].append(task_id)
            continue

        tx, ty = center(task)
        route_scores = []
        for route_id in candidate_routes:
            ax, ay = route_anchor(routes[route_id])
            cluster_distance = squared_distance(tx, ty, ax, ay) ** 0.5
            slack = makespan - route_cost(route_id)
            route_scores.append((-slack, cluster_distance, len(routes[route_id]), route_id))

        route_scores.sort()
        shortlist_size = 2 if len(route_scores) > 1 else 1
        shortlist = route_scores[:shortlist_size]
        target = min(shortlist, key=lambda item: (item[1], item[0], item[2], item[3]))[3]
        route = routes[target]

        best_position = 0
        best_score = None
        for position in range(len(route) + 1):
            neighbor_score = 0.0
            comparisons = 0

            if position > 0:
                previous = task_by_id.get(route[position - 1])
                if previous is not None:
                    px, py = center(previous)
                    neighbor_score += squared_distance(tx, ty, px, py) ** 0.5
                    comparisons += 1

            if position < len(route):
                following = task_by_id.get(route[position])
                if following is not None:
                    fx, fy = center(following)
                    neighbor_score += squared_distance(tx, ty, fx, fy) ** 0.5
                    comparisons += 1

            if comparisons == 0:
                neighbor_score = squared_distance(tx, ty, depot_x, depot_y) ** 0.5
            else:
                neighbor_score /= comparisons

            edge_penalty = 0.05 if position == 0 or position == len(route) else 0.0
            key = (neighbor_score + edge_penalty, position)
            if best_score is None or key < best_score:
                best_score = key
                best_position = position

        route.insert(best_position, task_id)

    return RepairResult(
        solution=MultiRobotSolution(routes=routes),
        note="farthest-first slack clustering away from bottleneck"
    )