from math import hypot, log

from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import RepairResult


def repair(partial_solution, unassigned_tasks, context, rng) -> RepairResult:
    routes = [list(route) for route in partial_solution.routes]
    while len(routes) < context.instance.robot_count:
        routes.append([])
    if not routes:
        return RepairResult(solution=MultiRobotSolution(routes=routes), note="aspect alignment repair: no robots")

    task_by_id = {task.task_id: task for task in context.instance.tasks}

    def features(task_id):
        task = task_by_id[task_id]
        cx = (task.x_left + task.x_right) * 0.5
        cy = (task.y_bottom + task.y_top) * 0.5
        aspect = log((task.width + 1.0e-9) / (task.height + 1.0e-9))
        axis = 1 if task.width >= task.height else -1
        return cx, cy, aspect, axis

    sizes = [hypot(task.width, task.height) for task in context.instance.tasks]
    geometry_scale = sum(sizes) / len(sizes) if sizes else 1.0
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
    insertion_counts = [0 for _ in routes]

    ordered = []
    for task_id in unassigned_tasks:
        task = task_by_id[task_id]
        _, _, aspect, _ = features(task_id)
        ordered.append((-abs(aspect), -(task.width * task.height),
                        rng.random(), task_id))
    ordered.sort()

    for _, _, _, task_id in ordered:
        tx, ty, task_aspect, task_axis = features(task_id)
        best_choice = None

        for route_id, route in enumerate(routes):
            route_pressure = route_cost_hint[route_id] / cost_scale
            bottleneck_penalty = 0.0
            if len(routes) > 1 and route_id == context.bottleneck_route_id:
                bottleneck_penalty = 1.15

            for position in range(len(route) + 1):
                if position == 0:
                    px, py = 0.0, 0.0
                    prev_aspect = task_aspect
                    prev_axis = task_axis
                else:
                    px, py, prev_aspect, prev_axis = features(route[position - 1])

                if position == len(route):
                    nx, ny = 0.0, 0.0
                    next_aspect = task_aspect
                    next_axis = task_axis
                else:
                    nx, ny, next_aspect, next_axis = features(route[position])

                transfer_delta = (hypot(tx - px, ty - py) +
                                  hypot(nx - tx, ny - ty) -
                                  hypot(nx - px, ny - py)) / geometry_scale
                aspect_gap = (abs(task_aspect - prev_aspect) +
                              abs(task_aspect - next_aspect)) * 0.5
                axis_switches = ((1 if task_axis != prev_axis else 0) +
                                 (1 if task_axis != next_axis else 0))

                if task_axis > 0:
                    alignment_gap = (abs(ty - py) + abs(ty - ny)) / (2.0 * geometry_scale)
                else:
                    alignment_gap = (abs(tx - px) + abs(tx - nx)) / (2.0 * geometry_scale)

                score = (transfer_delta +
                         0.24 * aspect_gap +
                         0.18 * axis_switches +
                         0.12 * alignment_gap +
                         0.72 * route_pressure +
                         0.10 * insertion_counts[route_id] +
                         bottleneck_penalty)
                choice = (score, route_id, position)
                if best_choice is None or choice < best_choice:
                    best_choice = choice

        _, route_id, position = best_choice
        routes[route_id].insert(position, task_id)
        insertion_counts[route_id] += 1

    return RepairResult(
        solution=MultiRobotSolution(routes=routes),
        note="aspect and sweep-axis clustering with critical-route avoidance"
    )
