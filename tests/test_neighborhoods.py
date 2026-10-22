from __future__ import annotations

from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.heuristics.neighborhood import (
    TwoOptMove,
    apply_relocate,
    apply_swap,
    apply_two_opt,
    iter_bottleneck_relocates,
    iter_inter_route_swaps,
    iter_intra_route_swaps,
    iter_intra_route_two_opt,
)


def test_intra_route_swaps_count() -> None:
    solution = MultiRobotSolution(routes=[[1, 2, 3], [4, 5]])
    moves = list(iter_intra_route_swaps(solution))
    assert len(moves) == 4


def test_inter_route_swaps_count() -> None:
    solution = MultiRobotSolution(routes=[[1, 2, 3], [4, 5]])
    moves = list(iter_inter_route_swaps(solution))
    assert len(moves) == 6


def test_intra_route_two_opt_count() -> None:
    solution = MultiRobotSolution(routes=[[1, 2, 3], [4, 5]])
    moves = list(iter_intra_route_two_opt(solution))
    assert len(moves) == 4


def test_bottleneck_relocates_count() -> None:
    solution = MultiRobotSolution(routes=[[1, 2, 3], [4, 5]])
    moves = list(iter_bottleneck_relocates(solution, bottleneck_robot=0))
    assert len(moves) == 9


def test_apply_swap_and_two_opt() -> None:
    solution = MultiRobotSolution(routes=[[1, 2, 3, 4], [5]])
    swap_move = list(iter_inter_route_swaps(solution))[0]
    swapped = apply_swap(solution, swap_move)
    assert swapped.routes != solution.routes

    two_opt = apply_two_opt(solution, TwoOptMove(robot=0, start_index=1, end_index=3))
    assert two_opt.routes[0] == [1, 4, 3, 2]


def test_apply_relocate() -> None:
    solution = MultiRobotSolution(routes=[[1, 2, 3], [4, 5]])
    move = list(iter_bottleneck_relocates(solution, bottleneck_robot=0))[0]
    relocated = apply_relocate(solution, move)
    assert relocated.routes != solution.routes
