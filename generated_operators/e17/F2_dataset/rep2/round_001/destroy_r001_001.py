import math

from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import DestroyResult


def destroy(solution, context, rng) -> DestroyResult:
    """
    Approximate horizontal/vertical sweep costs and remove tasks whose preferred
    mode conflicts with adjacent travel geometry, especially on critical routes.
    """
    instance = context.instance
    routes = [list(route) for route in solution.routes]
    target = min(max(0, context.remove_count), instance.task_count)

    if target == 0:
        return DestroyResult(
            partial_solution=MultiRobotSolution(routes=routes),
            removed_tasks=[],
            note="No tasks requested for removal."
        )

    task_source = instance.tasks.values() if isinstance(instance.tasks, dict) else instance.tasks
    task_map = {task.task_id: task for task in task_source}
    costs = list(context.per_robot_costs)
    makespan = max(float(context.route_costs_makespan), max(costs, default=0.0), 1e-9)
    sweep_width = max(float(instance.sweep_width), 1e-9)
    sweep_speed = max(float(instance.sweep_speed), 1e-9)
    travel_speed = max(float(instance.travel_speed), 1e-9)
    turning_time = max(float(instance.turning_time), 0.0)
    depot = instance.depot
    depot_xy = (float(depot[0]), float(depot[1]))
    small_instance_weight = 1.35 if instance.task_count <= 16 else 1.0

    def center(task):
        return (
            0.5 * (float(task.x_left) + float(task.x_right)),
            0.5 * (float(task.y_bottom) + float(task.y_top))
        )

    def mode_data(task):
        width = max(float(task.width), 0.0)
        height = max(float(task.height), 0.0)
        h_passes = max(1, int(math.ceil(height / sweep_width)))
        v_passes = max(1, int(math.ceil(width / sweep_width)))
        h_cost = width * h_passes / sweep_speed + max(0, h_passes - 1) * turning_time
        v_cost = height * v_passes / sweep_speed + max(0, v_passes - 1) * turning_time
        preferred = "H" if h_cost <= v_cost else "V"
        return preferred, abs(h_cost - v_cost), min(h_cost, v_cost)

    candidates = []
    for robot_id, route in enumerate(routes):
        route_cost = costs[robot_id] if robot_id < len(costs) else 0.0
        criticality = 0.25 + 0.75 * max(0.0, float(route_cost)) / makespan
        for position, task_id in enumerate(route):
            task = task_map.get(task_id)
            if task is None:
                score = criticality + rng.random() * 1e-9
                candidates.append((score, task_id))
                continue

            current = center(task)
            preferred, mode_gap, base_service = mode_data(task)
            mismatch = 0.0
            neighbour_mode_conflict = 0.0
            detour = 0.0

            neighbours = []
            if position > 0 and route[position - 1] in task_map:
                neighbours.append(center(task_map[route[position - 1]]))
            else:
                neighbours.append(depot_xy)
            if position + 1 < len(route) and route[position + 1] in task_map:
                neighbours.append(center(task_map[route[position + 1]]))
            else:
                neighbours.append(depot_xy)

            for neighbour in neighbours:
                dx = abs(current[0] - neighbour[0])
                dy = abs(current[1] - neighbour[1])
                scale = dx + dy + 1e-9
                if preferred == "H":
                    mismatch += dy / scale
                else:
                    mismatch += dx / scale

            for neighbour_position in (position - 1, position + 1):
                if 0 <= neighbour_position < len(route):
                    neighbour_task = task_map.get(route[neighbour_position])
                    if neighbour_task is not None:
                        neighbour_preferred, neighbour_gap, _ = mode_data(neighbour_task)
                        if neighbour_preferred != preferred:
                            neighbour_mode_conflict += min(mode_gap, neighbour_gap)

            previous = neighbours[0]
            following = neighbours[-1]
            direct = abs(previous[0] - following[0]) + abs(previous[1] - following[1])
            via = (
                abs(previous[0] - current[0]) + abs(previous[1] - current[1])
                + abs(current[0] - following[0]) + abs(current[1] - following[1])
            )
            detour = max(0.0, via - direct) / travel_speed

            mode_signal = small_instance_weight * (
                mode_gap * (0.5 + mismatch) + 0.75 * neighbour_mode_conflict
            )
            score = criticality * (base_service + detour + mode_signal)
            score += rng.random() * 1e-9
            candidates.append((score, task_id))

    candidates.sort(key=lambda item: item[0], reverse=True)
    removed = []
    selected = set()
    for _, task_id in candidates:
        if task_id not in selected:
            selected.add(task_id)
            removed.append(task_id)
            if len(removed) == target:
                break

    new_routes = [[task_id for task_id in route if task_id not in selected] for route in routes]
    return DestroyResult(
        partial_solution=MultiRobotSolution(routes=new_routes),
        removed_tasks=removed,
        note="Removed critical tasks with strong sweep-mode gaps and neighbour-direction mismatches."
    )
