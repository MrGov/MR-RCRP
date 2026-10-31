"""Local search whose candidate moves are priced by exact route tables.

``run_stronger_local_search`` evaluates every candidate with a full-solution
evaluation, i.e. one complete Route-DP pass per robot for every single move.
That is the right thing to compare against but the wrong thing to run inside an
iteration: on an 8-robot/80-task instance one failing scan of the five
neighbourhoods costs roughly 9400 full evaluations (~2 s), and most scans fail.

This module walks the same neighbours in the same order and accepts moves under
the same rule (``candidate + 1e-9 < current``), but prices each candidate from
the exact forward/backward route tables:

* relocate costs ``O(64)`` to remove the task and ``O(64)`` per target slot, so
  one removal price and one insertion-cost vector replace every slot DP;
* an inter-route swap costs two ``O(192)`` in-place replacements instead of two
  route-DP passes;
* intra-route swap and 2-opt still need a rebuild, but only for routes that can
  actually improve, which the dominance filter below guarantees.

The comparison is exact: table costs equal Route-DP costs up to floating point
noise far below the ``1e-9`` acceptance tolerance, so the first accepted move is
the one the reference scan would accept, and the returned solution is
re-evaluated through the reference evaluator before it is handed back.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from ..core.incremental_route import RouteIncrementalEvaluator
from ..core.models import MultiRobotSolution, SolutionEvaluation
from ..core.solution_evaluator import MultiRobotSolutionEvaluator
from .neighborhood import RelocateMove, SwapMove, TwoOptMove

ACCEPTANCE_TOLERANCE = 1e-9


class _RouteCostView:
    """Holds the current routes plus their exact per-route costs."""

    def __init__(
        self,
        routes: Sequence[Sequence[int]],
        pricer: RouteIncrementalEvaluator,
        costs: Optional[Sequence[float]] = None,
    ):
        self.pricer = pricer
        self.routes: List[List[int]] = [list(route) for route in routes]
        if costs is None:
            self.costs: List[float] = [pricer.route_cost(route) for route in self.routes]
        else:
            self.costs = [float(cost) for cost in costs]
            if len(self.costs) != len(self.routes):
                raise ValueError("costs must have one entry per route")
        self._removal_cache: Dict[Tuple[int, int], float] = {}
        self._insertion_cache: Dict[Tuple[int, int], List[float]] = {}

    # -- state -------------------------------------------------------------
    @property
    def makespan(self) -> float:
        return max(self.costs) if self.costs else 0.0

    def bottleneck_robot(self) -> int:
        if not self.costs:
            return 0
        return max(range(len(self.costs)), key=self.costs.__getitem__)

    def others_max(self, touched: Iterable[int]) -> float:
        """Largest cost among the routes a move does not touch."""

        skip = touched if isinstance(touched, (set, frozenset)) else set(touched)
        best = 0.0
        for index, cost in enumerate(self.costs):
            if index in skip:
                continue
            if cost > best:
                best = cost
        return best

    def _set_route(self, robot: int, route: List[int]) -> None:
        self.routes[robot] = route
        self.costs[robot] = self.pricer.route_cost(route)
        self._removal_cache.clear()
        self._insertion_cache.clear()

    # -- pricing -----------------------------------------------------------
    def removal(self, robot: int, index: int) -> float:
        key = (robot, index)
        cached = self._removal_cache.get(key)
        if cached is None:
            cached = self.pricer.route_cost_without(self.routes[robot], index)
            self._removal_cache[key] = cached
        return cached

    def insertions(self, robot: int, task_id: int) -> List[float]:
        key = (robot, task_id)
        cached = self._insertion_cache.get(key)
        if cached is None:
            cached = self.pricer.insertion_costs(self.routes[robot], task_id)
            self._insertion_cache[key] = cached
        return cached

    def insertion_at(self, robot: int, position: int, task_id: int) -> float:
        """Price one slot, so slots after the accepted move are never computed."""

        return self.pricer.insertion_cost_at(
            self.pricer.tables(self.routes[robot]), position, task_id
        )

    def replacement(self, robot: int, index: int, task_id: int) -> float:
        return self.pricer.route_cost_replaced(self.routes[robot], index, task_id)

    def route_cost(self, route: Sequence[int]) -> float:
        return self.pricer.route_cost(route)

    # -- applying ----------------------------------------------------------
    def apply_relocate(self, move: RelocateMove) -> None:
        source = list(self.routes[move.from_robot])
        task_id = source.pop(move.from_index)
        target = list(self.routes[move.to_robot])
        target.insert(move.to_index, task_id)
        self._set_route(move.from_robot, source)
        self._set_route(move.to_robot, target)

    def apply_swap(self, move: SwapMove) -> None:
        if move.robot_a == move.robot_b:
            route = list(self.routes[move.robot_a])
            route[move.index_a], route[move.index_b] = route[move.index_b], route[move.index_a]
            self._set_route(move.robot_a, route)
            return
        route_a = list(self.routes[move.robot_a])
        route_b = list(self.routes[move.robot_b])
        route_a[move.index_a], route_b[move.index_b] = route_b[move.index_b], route_a[move.index_a]
        self._set_route(move.robot_a, route_a)
        self._set_route(move.robot_b, route_b)

    def apply_two_opt(self, move: TwoOptMove) -> None:
        route = list(self.routes[move.robot])
        start = move.start_index
        end = move.end_index
        route[start : end + 1] = list(reversed(route[start : end + 1]))
        self._set_route(move.robot, route)


def _scan_relocates(view: _RouteCostView, *, from_robot: Optional[int] = None) -> Optional[RelocateMove]:
    """First improving relocate in neighbourhood order, priced from tables."""

    makespan = view.makespan
    robots = range(len(view.routes)) if from_robot is None else (from_robot,)
    for source_robot in robots:
        source_route = view.routes[source_robot]
        for source_index in range(len(source_route)):
            task_id = source_route[source_index]
            removed = view.removal(source_robot, source_index)
            for target_robot in range(len(view.routes)):
                if target_robot == source_robot:
                    continue
                # A move can only help if every untouched route stays below the
                # current makespan; this is an exact pruning rule, not a
                # heuristic relaxation of the acceptance test.
                others = view.others_max((source_robot, target_robot))
                if others + ACCEPTANCE_TOLERANCE >= makespan:
                    continue
                for target_index in range(len(view.routes[target_robot]) + 1):
                    inserted = view.insertion_at(target_robot, target_index, task_id)
                    candidate = max(others, removed, inserted)
                    if candidate + ACCEPTANCE_TOLERANCE < makespan:
                        return RelocateMove(
                            from_robot=source_robot,
                            from_index=source_index,
                            to_robot=target_robot,
                            to_index=target_index,
                        )
    return None


def _scan_intra_route_swaps(view: _RouteCostView) -> Optional[SwapMove]:
    makespan = view.makespan
    for robot, route in enumerate(view.routes):
        others = view.others_max((robot,))
        if others + ACCEPTANCE_TOLERANCE >= makespan:
            continue
        for i in range(len(route)):
            for j in range(i + 1, len(route)):
                swapped = list(route)
                swapped[i], swapped[j] = swapped[j], swapped[i]
                candidate = max(others, view.route_cost(swapped))
                if candidate + ACCEPTANCE_TOLERANCE < makespan:
                    return SwapMove(robot_a=robot, index_a=i, robot_b=robot, index_b=j)
    return None


def _scan_intra_route_two_opt(view: _RouteCostView) -> Optional[TwoOptMove]:
    makespan = view.makespan
    for robot, route in enumerate(view.routes):
        others = view.others_max((robot,))
        if others + ACCEPTANCE_TOLERANCE >= makespan:
            continue
        for start in range(len(route) - 1):
            for end in range(start + 1, len(route)):
                reversed_route = list(route)
                reversed_route[start : end + 1] = list(reversed(reversed_route[start : end + 1]))
                candidate = max(others, view.route_cost(reversed_route))
                if candidate + ACCEPTANCE_TOLERANCE < makespan:
                    return TwoOptMove(robot=robot, start_index=start, end_index=end)
    return None


def _scan_inter_route_swaps(view: _RouteCostView) -> Optional[SwapMove]:
    makespan = view.makespan
    for robot_a, route_a in enumerate(view.routes):
        for robot_b, route_b in enumerate(view.routes):
            if robot_b <= robot_a:
                continue
            others = view.others_max((robot_a, robot_b))
            if others + ACCEPTANCE_TOLERANCE >= makespan:
                continue
            for index_a, task_a in enumerate(route_a):
                for index_b, task_b in enumerate(route_b):
                    candidate = max(
                        others,
                        view.replacement(robot_a, index_a, task_b),
                        view.replacement(robot_b, index_b, task_a),
                    )
                    if candidate + ACCEPTANCE_TOLERANCE < makespan:
                        return SwapMove(
                            robot_a=robot_a,
                            index_a=index_a,
                            robot_b=robot_b,
                            index_b=index_b,
                        )
    return None


def run_priced_local_search(
    initial_solution: MultiRobotSolution,
    evaluator: MultiRobotSolutionEvaluator,
    pricer: RouteIncrementalEvaluator,
    max_iterations: int = 1,
    initial_evaluation: Optional[SolutionEvaluation] = None,
) -> Tuple[MultiRobotSolution, SolutionEvaluation]:
    """Same decisions as ``run_stronger_local_search``, priced from route tables."""

    if initial_evaluation is None:
        initial_evaluation = evaluator.evaluate(initial_solution)
    view = _RouteCostView(
        initial_solution.routes,
        pricer,
        costs=initial_evaluation.per_robot_costs,
    )

    for _ in range(max_iterations):
        improved = False

        relocate = _scan_relocates(view, from_robot=view.bottleneck_robot())
        if relocate is not None:
            view.apply_relocate(relocate)
            continue

        relocate = _scan_relocates(view)
        if relocate is not None:
            view.apply_relocate(relocate)
            improved = True
        else:
            intra_swap = _scan_intra_route_swaps(view)
            if intra_swap is not None:
                view.apply_swap(intra_swap)
                improved = True
            else:
                two_opt = _scan_intra_route_two_opt(view)
                if two_opt is not None:
                    view.apply_two_opt(two_opt)
                    improved = True
                else:
                    inter_swap = _scan_inter_route_swaps(view)
                    if inter_swap is not None:
                        view.apply_swap(inter_swap)
                        improved = True

        if not improved:
            break

    solution = MultiRobotSolution(routes=[list(route) for route in view.routes])
    return solution, evaluator.evaluate(solution)
