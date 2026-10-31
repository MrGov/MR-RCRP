from __future__ import annotations

import math

from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import DestroyResult


def destroy(solution, context, rng) -> DestroyResult:
    """
    Select a costly seed from a critical route, then apply a Shaw-style related
    removal across routes. Related clusters give repair an opportunity to regroup
    nearby rectangles while route criticality keeps attention on makespan relief.
    """
    instance = context.instance
    tasks = list(instance.tasks)
    task_by_id = {task.task_id: task for task in tasks}
    routes = [list(route) for route in solution.routes]
    original_routes = [list(route) for route in solution.routes]

    task_count = getattr(instance, "task_count", len(tasks))
    remove_target = min(max(0, int(context.remove_count)), int(task_count))
    if remove_target == 0:
        return DestroyResult(
            partial_solution=MultiRobotSolution(routes=routes),
            removed_tasks=[],
            note="critical related cluster destroy: no tasks requested",
        )

    costs = list(context.per_robot_costs)
    max_cost = max([float(c) for c in costs] + [1.0])
    depot = instance.depot
    if isinstance(depot, (tuple, list)):
        depot_xy = (float(depot[0]), float(depot[1]))
    else:
        depot_xy = (float(getattr(depot, "x", 0.0)), float(getattr(depot, "y", 0.0)))

    sweep_width = max(float(instance.sweep_width), 1e-12)
    sweep_speed = max(float(instance.sweep_speed), 1e-12)
    travel_speed = max(float(instance.travel_speed), 1e-12)
    turning_time = max(float(instance.turning_time), 0.0)

    def center(task):
        return (
            0.5 * (float(task.x_left) + float(task.x_right)),
            0.5 * (float(task.y_bottom) + float(task.y_top)),
        )

    def manhattan(a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def mode_data(task):
        width = max(float(task.width), 0.0)
        height = max(float(task.height), 0.0)
        h_lanes = max(1, int(math.ceil(height / sweep_width)))
        v_lanes = max(1, int(math.ceil(width / sweep_width)))
        h_cost = h_lanes * width / sweep_speed + (h_lanes - 1) * turning_time
        v_cost = v_lanes * height / sweep_speed + (v_lanes - 1) * turning_time
        preferred = 0 if h_cost <= v_cost else 1
        minimum = min(h_cost, v_cost)
        gap = abs(h_cost - v_cost)
        return preferred, minimum, gap

    centers = {task.task_id: center(task) for task in tasks}
    mode_info = {task.task_id: mode_data(task) for task in tasks}
    if centers:
        xs = [p[0] for p in centers.values()]
        ys = [p[1] for p in centers.values()]
        spatial_scale = max(1.0, max(xs) - min(xs) + max(ys) - min(ys))
    else:
        spatial_scale = 1.0

    proc_scale = max([info[1] for info in mode_info.values()] + [1.0])
    gap_scale = max([info[2] for info in mode_info.values()] + [1.0])

    route_of = {}
    for route_id, route in enumerate(original_routes):
        for task_id in route:
            route_of[task_id] = route_id

    seed_candidates = []
    for route_id, route in enumerate(routes):
        route_cost = float(costs[route_id]) if route_id < len(costs) else 0.0
        criticality = route_cost / max_cost
        for pos, task_id in enumerate(route):
            task = task_by_id.get(task_id)
            if task is None:
                continue
            point = centers[task_id]
            prev_point = depot_xy if pos == 0 else centers[route[pos - 1]]
            next_point = depot_xy if pos + 1 == len(route) else centers[route[pos + 1]]
            bridge = max(
                0.0,
                (manhattan(prev_point, point)
                 + manhattan(point, next_point)
                 - manhattan(prev_point, next_point)) / travel_speed,
            )
            _, proc, gap = mode_info[task_id]
            score = (
                1.8 * criticality
                + 1.5 * bridge / max_cost
                + 0.55 * proc / proc_scale
                + 0.20 * gap / gap_scale
                + 0.03 * rng.random()
            )
            seed_candidates.append((score, task_id))

    seed_candidates.sort(reverse=True)
    seed_pool = seed_candidates[: min(3, len(seed_candidates))]
    seed_id = seed_pool[0][1]
    if len(seed_pool) > 1 and rng.random() < 0.25:
        seed_id = seed_pool[int(rng.random() * len(seed_pool))][1]

    removed = []
    removed_set = set()

    def remove_task(task_id):
        route_id = route_of[task_id]
        routes[route_id].remove(task_id)
        removed.append(task_id)
        removed_set.add(task_id)

    remove_task(seed_id)

    while len(removed) < remove_target:
        candidates = []
        for route_id, route in enumerate(routes):
            route_cost = float(costs[route_id]) if route_id < len(costs) else 0.0
            criticality = route_cost / max_cost
            for task_id in route:
                if task_id in removed_set or task_id not in task_by_id:
                    continue
                task = task_by_id[task_id]
                point = centers[task_id]
                preferred, proc, gap = mode_info[task_id]

                best_relatedness = 0.0
                for removed_id in removed:
                    removed_task = task_by_id[removed_id]
                    removed_point = centers[removed_id]
                    removed_mode, removed_proc, _ = mode_info[removed_id]
                    spatial = 1.0 - min(1.0, manhattan(point, removed_point) / spatial_scale)
                    mode_match = 1.0 if preferred == removed_mode else 0.0
                    proc_match = 1.0 - min(1.0, abs(proc - removed_proc) / proc_scale)
                    aspect_a = math.log(max(float(task.width), 1e-9) / max(float(task.height), 1e-9))
                    aspect_b = math.log(max(float(removed_task.width), 1e-9) / max(float(removed_task.height), 1e-9))
                    aspect_match = 1.0 / (1.0 + abs(aspect_a - aspect_b))
                    relatedness = (
                        0.52 * spatial
                        + 0.18 * mode_match
                        + 0.15 * proc_match
                        + 0.15 * aspect_match
                    )
                    best_relatedness = max(best_relatedness, relatedness)

                score = (
                    1.05 * criticality
                    + 1.35 * best_relatedness
                    + 0.25 * proc / proc_scale
                    + 0.10 * gap / gap_scale
                    + 0.025 * rng.random()
                )
                candidates.append((score, task_id))

        if not candidates:
            break
        candidates.sort(reverse=True)
        rank_limit = min(4, len(candidates))
        exponent = 2.2
        rank = min(rank_limit - 1, int((rng.random() ** exponent) * rank_limit))
        remove_task(candidates[rank][1])

    if len(removed) < remove_target:
        for route_id, route in enumerate(routes):
            for task_id in list(route):
                if task_id not in removed_set:
                    route.remove(task_id)
                    removed.append(task_id)
                    removed_set.add(task_id)
                    if len(removed) == remove_target:
                        break
            if len(removed) == remove_target:
                break

    retained = {task_id for route in routes for task_id in route}
    expected = {task_id for route in original_routes for task_id in route}
    if retained | removed_set != expected or retained & removed_set:
        raise ValueError("destroy produced an inconsistent task partition")

    return DestroyResult(
        partial_solution=MultiRobotSolution(routes=routes),
        removed_tasks=removed,
        note="critical-route seed with geometry, aspect and sweep-mode related removal",
    )
