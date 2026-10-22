"""Neighbourhood generation for simple local search."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Generator, List

from ..core.models import MultiRobotSolution


@dataclass
class RelocateMove:
    """Move definition for relocating a task between robots."""

    from_robot: int
    from_index: int
    to_robot: int
    to_index: int


@dataclass
class SwapMove:
    """Move definition for swapping tasks between routes."""

    robot_a: int
    index_a: int
    robot_b: int
    index_b: int


@dataclass
class TwoOptMove:
    """Move definition for a 2-opt reversal within a route."""

    robot: int
    start_index: int
    end_index: int


def iter_inter_route_relocates(solution: MultiRobotSolution) -> Generator[RelocateMove, None, None]:
    """Yield all feasible inter-route relocate moves."""

    routes = solution.routes
    for from_robot, route in enumerate(routes):
        for from_index, _ in enumerate(route):
            for to_robot, target_route in enumerate(routes):
                if to_robot == from_robot:
                    continue
                for to_index in range(len(target_route) + 1):
                    yield RelocateMove(
                        from_robot=from_robot,
                        from_index=from_index,
                        to_robot=to_robot,
                        to_index=to_index,
                    )


def iter_bottleneck_relocates(
    solution: MultiRobotSolution, bottleneck_robot: int
) -> Generator[RelocateMove, None, None]:
    """Yield relocate moves that remove tasks from the bottleneck route."""

    routes = solution.routes
    if bottleneck_robot < 0 or bottleneck_robot >= len(routes):
        return
    for from_index, _ in enumerate(routes[bottleneck_robot]):
        for to_robot, target_route in enumerate(routes):
            if to_robot == bottleneck_robot:
                continue
            for to_index in range(len(target_route) + 1):
                yield RelocateMove(
                    from_robot=bottleneck_robot,
                    from_index=from_index,
                    to_robot=to_robot,
                    to_index=to_index,
                )


def iter_intra_route_swaps(solution: MultiRobotSolution) -> Generator[SwapMove, None, None]:
    """Yield swap moves within each route."""

    for robot, route in enumerate(solution.routes):
        for i in range(len(route)):
            for j in range(i + 1, len(route)):
                yield SwapMove(robot_a=robot, index_a=i, robot_b=robot, index_b=j)


def iter_inter_route_swaps(solution: MultiRobotSolution) -> Generator[SwapMove, None, None]:
    """Yield swap moves between distinct routes."""

    routes = solution.routes
    for robot_a, route_a in enumerate(routes):
        for robot_b, route_b in enumerate(routes):
            if robot_b <= robot_a:
                continue
            for index_a in range(len(route_a)):
                for index_b in range(len(route_b)):
                    yield SwapMove(
                        robot_a=robot_a,
                        index_a=index_a,
                        robot_b=robot_b,
                        index_b=index_b,
                    )


def iter_intra_route_two_opt(solution: MultiRobotSolution) -> Generator[TwoOptMove, None, None]:
    """Yield 2-opt moves within routes (reverse a segment)."""

    for robot, route in enumerate(solution.routes):
        for i in range(len(route) - 1):
            for k in range(i + 1, len(route)):
                yield TwoOptMove(robot=robot, start_index=i, end_index=k)


def apply_relocate(solution: MultiRobotSolution, move: RelocateMove) -> MultiRobotSolution:
    """Return a new solution after applying the given relocate move."""

    new_routes: List[List[int]] = [list(route) for route in solution.routes]
    task_id = new_routes[move.from_robot].pop(move.from_index)
    new_routes[move.to_robot].insert(move.to_index, task_id)
    return MultiRobotSolution(routes=new_routes)


def apply_swap(solution: MultiRobotSolution, move: SwapMove) -> MultiRobotSolution:
    """Return a new solution after swapping two tasks."""

    new_routes: List[List[int]] = [list(route) for route in solution.routes]
    task_a = new_routes[move.robot_a][move.index_a]
    task_b = new_routes[move.robot_b][move.index_b]
    new_routes[move.robot_a][move.index_a] = task_b
    new_routes[move.robot_b][move.index_b] = task_a
    return MultiRobotSolution(routes=new_routes)


def apply_two_opt(solution: MultiRobotSolution, move: TwoOptMove) -> MultiRobotSolution:
    """Return a new solution after reversing a segment within a route."""

    new_routes: List[List[int]] = [list(route) for route in solution.routes]
    route = new_routes[move.robot]
    i = move.start_index
    k = move.end_index
    route[i : k + 1] = list(reversed(route[i : k + 1]))
    return MultiRobotSolution(routes=new_routes)
