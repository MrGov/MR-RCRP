from math import hypot

from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import RepairResult


def repair(partial_solution, unassigned_tasks, context, rng) -> RepairResult:
    routes = [list(route) for route in partial_solution.routes]
    while len(routes) < context.instance.robot_count:
        routes.append([])
    if not routes:
        return RepairResult(solution=MultiRobotSolution(routes=routes), note="slack geometric repair: no robots")

    task_by_id = {task.task_id: task for task in context.instance.tasks}

    def center(task_id):
        task = task_by_id[task_id]
        return ((task.x_left + task.x_right) * 0.5,
                (task.y_bottom + task.y_top) * 0.5)

    diagonals = [hypot(task.width, task.height) for task in context.instance.tasks]
    geometry_scale = sum(diagonals) / len(diagonals) if diagonals else 1.0
    if geometry_scale <= 0.0:
        geometry_scale = 1.0

    route_cost_hint = []
    for route_id in range(len(routes)):
        if route_id < len(context.per_robot_costs):
            route_cost_hint.append(context.per_robot_costs[route_id])
        else:
            route_cost_hint.append(0.0)
    cost_scale = max([1.0, abs(context.route_costs_makespan)] +
                     [abs(value) for value in route_cost_hint])
    added_pressure = [0.0 for _ in routes]

    ordered = []
    for task_id in unassigned_tasks:
        task = task_by_id[task_id]
        cx, cy = center(task_id)
        ordered.append((-(hypot(cx, cy)), -(task.width * task.height),
                        rng.random(), task_id))
    ordered.sort()

    for _, _, _, task_id in ordered:
        task = task_by_id[task_id]
        tx, ty = center(task_id)
        best_choice = None

        for route_id, route in enumerate(routes):
            load_term = route_cost_hint[route_id] / cost_scale
            bottleneck_term = 0.0
            if len(routes) > 1 and route_id == context.bottleneck_route_id:
                bottleneck_term = 1.35

            for position in range(len(route) + 1):
                if position == 0:
                    px, py = 0.0, 0.0
                else:
                    px, py = center(route[position - 1])
                if position == len(route):
                    nx, ny = 0.0, 0.0
                else:
                    nx, ny = center(route[position])

                local_delta = (hypot(tx - px, ty - py) +
                               hypot(nx - tx, ny - ty) -
                               hypot(nx - px, ny - py))
                score = (local_delta / geometry_scale +
                         0.85 * load_term +
                         0.16 * added_pressure[route_id] +
                         bottleneck_term)
                choice = (score, route_id, position)
                if best_choice is None or choice < best_choice:
                    best_choice = choice

        _, route_id, position = best_choice
        routes[route_id].insert(position, task_id)
        added_pressure[route_id] += (task.width + task.height) / geometry_scale

    return RepairResult(
        solution=MultiRobotSolution(routes=routes),
        note="slack-weighted geometric insertion with bottleneck avoidance"
    )
