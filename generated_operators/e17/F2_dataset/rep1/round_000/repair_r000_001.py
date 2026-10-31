from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import RepairResult
import math


def repair(partial_solution, unassigned_tasks, context, rng):
    routes = [list(route) for route in partial_solution.routes]
    while len(routes) < context.instance.robot_count:
        routes.append([])

    task_by_id = {task.task_id: task for task in context.instance.tasks}

    def center(task_id):
        task = task_by_id[task_id]
        return ((task.x_left + task.x_right) * 0.5,
                (task.y_bottom + task.y_top) * 0.5)

    def orientation(task_id):
        task = task_by_id[task_id]
        return 0 if task.width >= task.height else 1

    def neighbor_cost(first_id, second_id):
        first = task_by_id[first_id]
        second = task_by_id[second_id]
        first_center = center(first_id)
        second_center = center(second_id)
        dx = abs(first_center[0] - second_center[0])
        dy = abs(first_center[1] - second_center[1])
        same_mode = orientation(first_id) == orientation(second_id)

        if orientation(second_id) == 0:
            alignment_gap = dy + 0.35 * dx
        else:
            alignment_gap = dx + 0.35 * dy

        aspect_first = first.width / max(first.height, 1.0e-9)
        aspect_second = second.width / max(second.height, 1.0e-9)
        aspect_gap = abs(math.log(max(aspect_first, 1.0e-9) /
                                  max(aspect_second, 1.0e-9)))
        switch_penalty = 0.0 if same_mode else max(first.width, first.height,
                                                   second.width, second.height) * 0.8
        return alignment_gap + aspect_gap * 2.0 + switch_penalty

    proxy_costs = []
    for robot_id in range(len(routes)):
        if robot_id < len(context.per_robot_costs):
            proxy_costs.append(float(context.per_robot_costs[robot_id]))
        else:
            proxy_costs.append(0.0)

    ordered_tasks = list(unassigned_tasks)
    ordered_tasks.sort(
        key=lambda task_id: (
            orientation(task_id),
            center(task_id)[1] if orientation(task_id) == 0 else center(task_id)[0],
            center(task_id)[0] if orientation(task_id) == 0 else center(task_id)[1],
            rng.random()
        )
    )

    scale = max(float(context.route_costs_makespan), 1.0)
    for task_id in ordered_tasks:
        best = None

        for robot_id, route in enumerate(routes):
            load_term = proxy_costs[robot_id] / scale
            bottleneck_penalty = 0.45 * scale if robot_id == context.bottleneck_route_id else 0.0

            for position in range(len(route) + 1):
                if not route:
                    point = center(task_id)
                    local_cost = math.hypot(point[0], point[1])
                else:
                    local_cost = 0.0
                    if position > 0:
                        local_cost += neighbor_cost(route[position - 1], task_id)
                    if position < len(route):
                        local_cost += neighbor_cost(task_id, route[position])
                    if 0 < position < len(route):
                        local_cost -= 0.6 * neighbor_cost(route[position - 1], route[position])

                score = (local_cost + load_term * scale * 0.18 +
                         bottleneck_penalty + rng.random() * 1.0e-7)
                candidate = (score, robot_id, position, local_cost)
                if best is None or candidate < best:
                    best = candidate

        _, robot_id, position, local_cost = best
        routes[robot_id].insert(position, task_id)
        task = task_by_id[task_id]
        proxy_costs[robot_id] += max(task.width, task.height) + max(0.0, local_cost)

    return RepairResult(
        solution=MultiRobotSolution(routes=routes),
        note="orientation and axis-alignment chain repair"
    )
