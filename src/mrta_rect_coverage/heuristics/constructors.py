"""Initial solution constructors."""
from __future__ import annotations

from typing import List

from ..core.models import Instance, MultiRobotSolution


def round_robin_constructor(instance: Instance) -> MultiRobotSolution:
    """Distribute tasks over robots in task-id order."""

    if instance.robot_count <= 0:
        raise ValueError("Instance must define at least one robot")
    routes: List[List[int]] = [[] for _ in range(instance.robot_count)]
    for idx, task in enumerate(sorted(instance.tasks, key=lambda t: t.task_id)):
        robot_idx = idx % instance.robot_count
        routes[robot_idx].append(task.task_id)
    return MultiRobotSolution(routes=routes)


def spatial_sort_constructor(instance: Instance) -> MultiRobotSolution:
    """Sort tasks by centre (x+y) and assign round robin."""

    if instance.robot_count <= 0:
        raise ValueError("Instance must define at least one robot")
    routes: List[List[int]] = [[] for _ in range(instance.robot_count)]
    tasks_sorted = sorted(
        instance.tasks,
        key=lambda t: ((t.x_left + t.x_right) * 0.5) + ((t.y_bottom + t.y_top) * 0.5),
    )
    for idx, task in enumerate(tasks_sorted):
        robot_idx = idx % instance.robot_count
        routes[robot_idx].append(task.task_id)
    return MultiRobotSolution(routes=routes)
