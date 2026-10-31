from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import RepairResult


def repair(partial_solution, unassigned_tasks, context, rng):
    routes = [list(route) for route in partial_solution.routes]
    while len(routes) < context.instance.robot_count:
        routes.append([])

    task_by_id = {task.task_id: task for task in context.instance.tasks}
    added_count = [0] * len(routes)
    bottleneck = context.bottleneck_route_id

    candidates = [r for r in range(len(routes)) if r != bottleneck]
    if not candidates:
        candidates = list(range(len(routes)))

    def centroid(task_id):
        task = task_by_id[task_id]
        return ((task.x_left + task.x_right) * 0.5,
                (task.y_bottom + task.y_top) * 0.5)

    def distance(a, b):
        dx = a[0] - b[0]
        dy = a[1] - b[1]
        return (dx * dx + dy * dy) ** 0.5

    def insertion_proxy(route, task_id, position):
        point = centroid(task_id)
        if not route:
            return 0.0
        if position == 0:
            return distance(point, centroid(route[0]))
        if position == len(route):
            return distance(centroid(route[-1]), point)
        previous = centroid(route[position - 1])
        following = centroid(route[position])
        return (distance(previous, point) + distance(point, following)
                - distance(previous, following))

    pending = list(unassigned_tasks)
    rng.shuffle(pending)

    for task_id in pending:
        target = min(
            candidates,
            key=lambda r: (
                added_count[r],
                context.per_robot_costs[r] if r < len(context.per_robot_costs) else 0.0,
                len(routes[r]),
                rng.random(),
            ),
        )
        positions = list(range(len(routes[target]) + 1))
        position = min(
            positions,
            key=lambda p: (insertion_proxy(routes[target], task_id, p), rng.random()),
        )
        routes[target].insert(position, task_id)
        added_count[target] += 1

    return RepairResult(
        solution=MultiRobotSolution(routes=routes),
        note="Balanced non-bottleneck insertion with centroid-based placement",
    )
