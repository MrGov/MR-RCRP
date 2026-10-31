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
    costs = list(context.per_robot_costs)
    bottleneck = context.bottleneck_route_id
    makespan = context.route_costs_makespan
    cost_scale = makespan if makespan > 0.0 else 1.0

    def center(task):
        return ((task.x_left + task.x_right) * 0.5,
                (task.y_bottom + task.y_top) * 0.5)

    def distance_xy(ax, ay, bx, by):
        dx = ax - bx
        dy = ay - by
        return (dx * dx + dy * dy) ** 0.5

    def orientation(task):
        return 0 if task.width >= task.height else 1

    def route_cost(route_id):
        if route_id < len(costs):
            return costs[route_id]
        return 0.0

    pending = []
    seen_pending = set()
    for task_id in unassigned_tasks:
        if task_id not in seen_pending:
            pending.append(task_id)
            seen_pending.add(task_id)

    def priority(task_id):
        task = task_by_id.get(task_id)
        if task is None:
            return (0.0, 0.0)
        cx, cy = center(task)
        radial = distance_xy(cx, cy, depot_x, depot_y)
        return (task.width * task.height, radial)

    pending.sort(key=priority, reverse=True)

    for task_id in pending:
        task = task_by_id.get(task_id)
        if task is None:
            candidates = [r for r in range(len(routes)) if r != bottleneck]
            if not candidates:
                candidates = list(range(len(routes)))
            target = min(candidates, key=lambda r: (route_cost(r), len(routes[r]), r))
            routes[target].append(task_id)
            continue

        tx, ty = center(task)
        task_scale = max(task.width, task.height, 1.0)
        best = None

        for route_id, route in enumerate(routes):
            load_term = route_cost(route_id) / cost_scale
            bottleneck_penalty = 1.25 if route_id == bottleneck and len(routes) > 1 else 0.0

            for position in range(len(route) + 1):
                if position == 0:
                    px, py = depot_x, depot_y
                else:
                    previous = task_by_id.get(route[position - 1])
                    if previous is None:
                        px, py = depot_x, depot_y
                    else:
                        px, py = center(previous)

                if position == len(route):
                    nx, ny = depot_x, depot_y
                else:
                    following = task_by_id.get(route[position])
                    if following is None:
                        nx, ny = depot_x, depot_y
                    else:
                        nx, ny = center(following)

                added_distance = (distance_xy(px, py, tx, ty) +
                                  distance_xy(tx, ty, nx, ny) -
                                  distance_xy(px, py, nx, ny))
                geometry_term = added_distance / task_scale

                mismatch = 0.0
                neighbor_count = 0
                if position > 0:
                    previous = task_by_id.get(route[position - 1])
                    if previous is not None:
                        mismatch += 1.0 if orientation(previous) != orientation(task) else 0.0
                        neighbor_count += 1
                if position < len(route):
                    following = task_by_id.get(route[position])
                    if following is not None:
                        mismatch += 1.0 if orientation(following) != orientation(task) else 0.0
                        neighbor_count += 1
                if neighbor_count:
                    mismatch /= neighbor_count

                score = 2.8 * load_term + geometry_term + 0.45 * mismatch + bottleneck_penalty
                key = (score, route_cost(route_id), len(route), route_id, position)
                if best is None or key < best[0]:
                    best = (key, route_id, position)

        routes[best[1]].insert(best[2], task_id)

    return RepairResult(
        solution=MultiRobotSolution(routes=routes),
        note="slack-aware geometric insertion with sweep alignment"
    )