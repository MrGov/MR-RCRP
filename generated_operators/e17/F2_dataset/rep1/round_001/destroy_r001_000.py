import math

from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import DestroyResult


def destroy(solution, context, rng) -> DestroyResult:
    instance = context.instance
    routes = [list(route) for route in solution.routes]
    target = max(0, min(context.remove_count, instance.task_count))
    if target == 0:
        return DestroyResult(
            partial_solution=MultiRobotSolution(routes=routes),
            removed_tasks=[],
            note='No tasks requested for critical Shaw-cluster destroy.'
        )

    task_by_id = {task.task_id: task for task in instance.tasks}
    all_ids = []
    seen = set()
    location = {}
    for rid, route in enumerate(routes):
        for pos, task_id in enumerate(route):
            location[task_id] = (rid, pos)
            if task_id not in seen:
                seen.add(task_id)
                all_ids.append(task_id)

    def features(task_id):
        task = task_by_id[task_id]
        width = max(float(task.width), 1e-9)
        height = max(float(task.height), 1e-9)
        cx = 0.5 * (float(task.x_left) + float(task.x_right))
        cy = 0.5 * (float(task.y_bottom) + float(task.y_top))
        aspect = math.log(width / height)
        sweep_width = max(float(instance.sweep_width), 1e-9)
        sweep_speed = max(float(instance.sweep_speed), 1e-9)
        horizontal_lanes = max(1, int(math.ceil(height / sweep_width)))
        vertical_lanes = max(1, int(math.ceil(width / sweep_width)))
        horizontal = width * horizontal_lanes / sweep_speed
        vertical = height * vertical_lanes / sweep_speed
        horizontal += max(0, horizontal_lanes - 1) * float(instance.turning_time)
        vertical += max(0, vertical_lanes - 1) * float(instance.turning_time)
        preferred = 0 if horizontal <= vertical else 1
        mode_strength = abs(horizontal - vertical) / max(min(horizontal, vertical), 1e-9)
        processing = min(horizontal, vertical)
        return cx, cy, aspect, preferred, mode_strength, processing

    feat = {task_id: features(task_id) for task_id in all_ids}
    xs = [feat[task_id][0] for task_id in all_ids]
    ys = [feat[task_id][1] for task_id in all_ids]
    spatial_scale = max((max(xs) - min(xs)) + (max(ys) - min(ys)), 1.0)
    average_processing = max(
        sum(feat[task_id][5] for task_id in all_ids) / max(len(all_ids), 1),
        1e-9
    )
    costs = [
        float(context.per_robot_costs[rid]) if rid < len(context.per_robot_costs) else 0.0
        for rid in range(len(routes))
    ]
    maximum_cost = max(costs) if costs else 0.0
    minimum_cost = min(costs) if costs else 0.0
    cost_span = max(maximum_cost - minimum_cost, 1e-9)

    def route_pressure(rid):
        if maximum_cost <= 0.0:
            return 1.0
        relative = costs[rid] / maximum_cost
        excess = (costs[rid] - minimum_cost) / cost_span
        return 0.65 * relative + 0.35 * excess

    def manhattan(a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    seed_scores = []
    for task_id in all_ids:
        rid, pos = location[task_id]
        route = routes[rid]
        center = feat[task_id][:2]
        previous = (0.0, 0.0) if pos == 0 else feat[route[pos - 1]][:2]
        following = (0.0, 0.0) if pos + 1 == len(route) else feat[route[pos + 1]][:2]
        edge_excess = manhattan(previous, center) + manhattan(center, following) - manhattan(previous, following)
        other_centers = [feat[value][:2] for value in route if value != task_id]
        if other_centers:
            mean_x = sum(value[0] for value in other_centers) / len(other_centers)
            mean_y = sum(value[1] for value in other_centers) / len(other_centers)
            outlier = manhattan(center, (mean_x, mean_y)) / spatial_scale
        else:
            outlier = 0.0
        processing = feat[task_id][5] / average_processing
        mode_signal = min(feat[task_id][4], 3.0)
        score = (
            2.8 * route_pressure(rid)
            + 1.8 * edge_excess / spatial_scale
            + 0.9 * outlier
            + 0.35 * processing
            + (0.45 if len(all_ids) <= 16 else 0.15) * mode_signal
            + 1e-7 * rng.random()
        )
        seed_scores.append((score, task_id))

    seed_scores.sort(reverse=True)
    seed_limit = min(len(seed_scores), max(2, int(math.sqrt(len(seed_scores))) + 1))
    seed_index = min(seed_limit - 1, int((rng.random() ** 2) * seed_limit))
    removed = [seed_scores[seed_index][1]]
    removed_set = set(removed)

    while len(removed) < target:
        candidates = []
        for task_id in all_ids:
            if task_id in removed_set:
                continue
            rid, pos = location[task_id]
            cx, cy, aspect, preferred, mode_strength, processing = feat[task_id]
            best_relation = -1e30
            for removed_id in removed:
                rcx, rcy, raspect, rpreferred, _, _ = feat[removed_id]
                distance_relation = 1.0 - min(1.0, (abs(cx - rcx) + abs(cy - rcy)) / spatial_scale)
                aspect_relation = 1.0 / (1.0 + abs(aspect - raspect))
                mode_relation = 1.0 if preferred == rpreferred else 0.0
                relation = 1.6 * distance_relation + 0.55 * aspect_relation + 0.35 * mode_relation
                if relation > best_relation:
                    best_relation = relation
            adjacency = 0.0
            route = routes[rid]
            if pos > 0 and route[pos - 1] in removed_set:
                adjacency += 0.8
            if pos + 1 < len(route) and route[pos + 1] in removed_set:
                adjacency += 0.8
            score = (
                best_relation
                + 1.7 * route_pressure(rid)
                + adjacency
                + 0.18 * processing / average_processing
                + (0.25 if len(all_ids) <= 16 else 0.08) * min(mode_strength, 3.0)
                + 1e-7 * rng.random()
            )
            candidates.append((score, task_id))
        candidates.sort(reverse=True)
        shortlist = min(3, len(candidates))
        choice = min(shortlist - 1, int((rng.random() ** 2) * shortlist))
        selected = candidates[choice][1]
        removed.append(selected)
        removed_set.add(selected)

    partial_routes = [
        [task_id for task_id in route if task_id not in removed_set]
        for route in routes
    ]
    return DestroyResult(
        partial_solution=MultiRobotSolution(routes=partial_routes),
        removed_tasks=removed,
        note='Critical-route Shaw cluster using transfer, aspect, and sweep-mode relatedness.'
    )
