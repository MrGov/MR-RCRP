from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import RepairResult


def repair(partial_solution, unassigned_tasks, context, rng):
    routes = [list(route) for route in partial_solution.routes]
    while len(routes) < context.instance.robot_count:
        routes.append([])
    if not routes:
        return RepairResult(solution=MultiRobotSolution(routes=routes), note="spatial serpentine repair: no robots")

    task_by_id = {task.task_id: task for task in context.instance.tasks}
    existing = set()
    for route in routes:
        existing.update(route)

    pending = []
    known = set(existing)
    for task_id in unassigned_tasks:
        if task_id not in known:
            pending.append(task_id)
            known.add(task_id)

    costs = []
    for robot_id in range(len(routes)):
        if robot_id < len(context.per_robot_costs):
            costs.append(context.per_robot_costs[robot_id])
        else:
            costs.append(0.0)

    bottleneck = context.bottleneck_route_id
    robot_order = [r for r in range(len(routes)) if r != bottleneck]
    if not robot_order:
        robot_order = list(range(len(routes)))
    robot_order.sort(key=lambda r: (costs[r], len(routes[r]), r))

    if len(robot_order) > 1:
        shift = rng.randrange(len(robot_order))
        robot_order = robot_order[shift:] + robot_order[:shift]

    def center(task):
        return ((task.x_left + task.x_right) * 0.5,
                (task.y_bottom + task.y_top) * 0.5)

    located = [task_id for task_id in pending if task_id in task_by_id]
    missing_geometry = [task_id for task_id in pending if task_id not in task_by_id]

    if located:
        centers = [center(task_by_id[task_id]) for task_id in located]
        min_x = min(point[0] for point in centers)
        max_x = max(point[0] for point in centers)
        span = max_x - min_x
        strip_count = max(1, min(len(robot_order) * 2, int(len(located) ** 0.5) + 1))
        strip_width = span / strip_count if span > 0.0 else 1.0

        def serpentine_key(task_id):
            x, y = center(task_by_id[task_id])
            strip = int((x - min_x) / strip_width) if span > 0.0 else 0
            if strip >= strip_count:
                strip = strip_count - 1
            return (strip, y if strip % 2 == 0 else -y, x)

        located.sort(key=serpentine_key)

    ordered = located + missing_geometry

    def squared_distance(first, second):
        ax, ay = center(first)
        bx, by = center(second)
        dx = ax - bx
        dy = ay - by
        return dx * dx + dy * dy

    def insertion_position(route, task):
        if not route:
            return 0
        best_position = len(route)
        best_change = None
        for pos in range(len(route) + 1):
            previous = task_by_id.get(route[pos - 1]) if pos > 0 else None
            following = task_by_id.get(route[pos]) if pos < len(route) else None
            change = 0.0
            if previous is not None:
                change += squared_distance(previous, task)
            if following is not None:
                change += squared_distance(task, following)
            if previous is not None and following is not None:
                change -= squared_distance(previous, following)
            if best_change is None or change < best_change:
                best_change = change
                best_position = pos
        return best_position

    for index, task_id in enumerate(ordered):
        target = robot_order[index % len(robot_order)]
        task = task_by_id.get(task_id)
        if task is None:
            routes[target].append(task_id)
        else:
            position = insertion_position(routes[target], task)
            routes[target].insert(position, task_id)

    return RepairResult(
        solution=MultiRobotSolution(routes=routes),
        note="spatial serpentine distribution across non-bottleneck routes"
    )