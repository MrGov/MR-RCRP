import math

from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import DestroyResult


def destroy(solution, context, rng) -> DestroyResult:
    instance = context.instance
    original_routes = [list(route) for route in solution.routes]
    working_routes = [list(route) for route in solution.routes]
    target = max(0, min(context.remove_count, instance.task_count))
    if target == 0:
        return DestroyResult(
            partial_solution=MultiRobotSolution(routes=original_routes),
            removed_tasks=[],
            note='No tasks requested for adaptive marginal destroy.'
        )

    task_by_id = {task.task_id: task for task in instance.tasks}
    original_costs = [
        float(context.per_robot_costs[rid]) if rid < len(context.per_robot_costs) else 0.0
        for rid in range(len(working_routes))
    ]
    estimated_costs = list(original_costs)
    sweep_width = max(float(instance.sweep_width), 1e-9)
    sweep_speed = max(float(instance.sweep_speed), 1e-9)
    travel_speed = max(float(instance.travel_speed), 1e-9)
    turning_time = float(instance.turning_time)

    def interval_gap(a_low, a_high, b_low, b_high):
        if a_high < b_low:
            return b_low - a_high
        if b_high < a_low:
            return a_low - b_high
        return 0.0

    def rectangle_distance(first_id, second_id):
        if first_id is None and second_id is None:
            return 0.0
        if first_id is None:
            task = task_by_id[second_id]
            dx = interval_gap(0.0, 0.0, float(task.x_left), float(task.x_right))
            dy = interval_gap(0.0, 0.0, float(task.y_bottom), float(task.y_top))
            return (dx + dy) / travel_speed
        if second_id is None:
            return rectangle_distance(None, first_id)
        first = task_by_id[first_id]
        second = task_by_id[second_id]
        dx = interval_gap(
            float(first.x_left), float(first.x_right),
            float(second.x_left), float(second.x_right)
        )
        dy = interval_gap(
            float(first.y_bottom), float(first.y_top),
            float(second.y_bottom), float(second.y_top)
        )
        return (dx + dy) / travel_speed

    def processing_features(task_id):
        task = task_by_id[task_id]
        width = max(float(task.width), 1e-9)
        height = max(float(task.height), 1e-9)
        horizontal_lanes = max(1, int(math.ceil(height / sweep_width)))
        vertical_lanes = max(1, int(math.ceil(width / sweep_width)))
        horizontal = width * horizontal_lanes / sweep_speed
        vertical = height * vertical_lanes / sweep_speed
        horizontal += max(0, horizontal_lanes - 1) * turning_time
        vertical += max(0, vertical_lanes - 1) * turning_time
        best = min(horizontal, vertical)
        dominance = abs(horizontal - vertical) / max(best, 1e-9)
        cx = 0.5 * (float(task.x_left) + float(task.x_right))
        cy = 0.5 * (float(task.y_bottom) + float(task.y_top))
        return best, dominance, cx, cy

    all_ids = [task_id for route in working_routes for task_id in route]
    features = {task_id: processing_features(task_id) for task_id in all_ids}
    average_processing = max(
        sum(features[task_id][0] for task_id in all_ids) / max(len(all_ids), 1),
        1e-9
    )
    xs = [features[task_id][2] for task_id in all_ids]
    ys = [features[task_id][3] for task_id in all_ids]
    spatial_scale = max((max(xs) - min(xs)) + (max(ys) - min(ys)), 1.0)
    removed = []
    removed_set = set()

    while len(removed) < target:
        active_costs = [
            estimated_costs[rid] if working_routes[rid] else -1e30
            for rid in range(len(working_routes))
        ]
        maximum_cost = max(active_costs)
        valid_costs = [value for value in active_costs if value > -1e20]
        minimum_cost = min(valid_costs) if valid_costs else 0.0
        span = max(maximum_cost - minimum_cost, 1e-9)
        total_remaining = sum(len(route) for route in working_routes)
        candidates = []

        for rid, route in enumerate(working_routes):
            if not route:
                continue
            relative_load = estimated_costs[rid] / max(maximum_cost, 1e-9) if maximum_cost > 0.0 else 1.0
            excess_load = (estimated_costs[rid] - minimum_cost) / span
            pressure = 0.7 * relative_load + 0.3 * excess_load
            for pos, task_id in enumerate(route):
                previous_id = route[pos - 1] if pos > 0 else None
                next_id = route[pos + 1] if pos + 1 < len(route) else None
                transfer_saving = (
                    rectangle_distance(previous_id, task_id)
                    + rectangle_distance(task_id, next_id)
                    - rectangle_distance(previous_id, next_id)
                )
                processing, mode_dominance, cx, cy = features[task_id]
                other_ids = [value for value in route if value != task_id]
                if other_ids:
                    mean_x = sum(features[value][2] for value in other_ids) / len(other_ids)
                    mean_y = sum(features[value][3] for value in other_ids) / len(other_ids)
                    outlier = (abs(cx - mean_x) + abs(cy - mean_y)) / spatial_scale
                else:
                    outlier = 0.0
                small_instance_mode_weight = 0.45 if total_remaining <= 16 else 0.10
                estimated_relief = max(0.0, transfer_saving) + processing
                score = (
                    pressure * (2.4 * transfer_saving + 0.70 * processing)
                    + 0.35 * processing
                    + 0.55 * outlier * average_processing
                    + small_instance_mode_weight * min(mode_dominance, 3.0) * average_processing
                    + 1e-7 * rng.random()
                )
                candidates.append((score, pressure, estimated_relief, rid, pos, task_id))

        candidates.sort(reverse=True)
        if not candidates:
            break
        shortlist = min(3, len(candidates))
        selected_index = min(shortlist - 1, int((rng.random() ** 2) * shortlist))
        _, _, estimated_relief, rid, pos, task_id = candidates[selected_index]
        removed.append(task_id)
        removed_set.add(task_id)
        del working_routes[rid][pos]
        estimated_costs[rid] = max(0.0, estimated_costs[rid] - estimated_relief)

    if len(removed) < target:
        for route in original_routes:
            for task_id in route:
                if task_id not in removed_set:
                    removed.append(task_id)
                    removed_set.add(task_id)
                    if len(removed) == target:
                        break
            if len(removed) == target:
                break

    partial_routes = [
        [task_id for task_id in route if task_id not in removed_set]
        for route in original_routes
    ]
    return DestroyResult(
        partial_solution=MultiRobotSolution(routes=partial_routes),
        removed_tasks=removed,
        note='Adaptive bottleneck destroy with recalculated transfer and processing relief.'
    )
