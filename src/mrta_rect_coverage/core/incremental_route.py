"""Exact insertion pricing for a fixed route without re-running the route DP.

The exact evaluator (:class:`~mrta_rect_coverage.core.dp_evaluator.RouteDPEvaluator`)
prices a whole route in ``O(length * 64)``; a repair heuristic that tries every
insertion position of every task on every robot therefore pays that cost once per
candidate.  This module keeps the exactness and removes the repetition.

For a route ``t_0..t_{m-1}`` it builds, once, the two halves of the state DP:

``forward[k][s]``
    minimum cost of covering ``t_0..t_k`` and *finishing* ``t_k`` in state ``s``
    (processing times included, no return to the depot).
``backward[k][s]``
    minimum cost incurred *after* finishing ``t_k`` in state ``s``: transitions,
    processing times of the remaining tasks and the final return to the depot.

Inserting task ``i`` at position ``p`` then costs

``min_{s'} A(s') + min_{s_i} [ travel(s', s_i) + P_i(s_i) + K(s_i) ]``

with ``A = forward[p-1]`` (or the depot alone when ``p == 0``) and
``K(s_i) = min_{s''} [ travel(s_i, s'') + P(s'' next) + backward[p][s''] ]``
(or ``state_to_depot(s_i)`` when ``p == m``).  That is ``O(64)`` per position,
independent of the route length, and it is the same optimum the route DP returns.

Only the insertion side is provided: removal is a single route evaluation that the
caller already pays once per destroy.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import inf
from typing import Dict, Iterable, List, Optional, Tuple

from .cost_matrix import CostMatrix
from .models import State

# Routes revisited by the ALNS live in a short window; a small generational cache
# keeps the tables cheap while bounding memory (a 100-task route costs ~64 KB).
DEFAULT_CACHE_LIMIT = 256

# Neighbourhood scans revisit the same (route, task, slot) triples across iterations
# because simulated annealing accepts and rejects the same few routes repeatedly.
# The route DP gets an 89% hit rate from exactly this repetition, so the priced
# path needs its own memo or it recomputes what the DP would have served from cache.
DEFAULT_PRICE_CACHE_LIMIT = 50000


@dataclass(frozen=True)
class RouteTables:
    """Forward/backward state-DP tables for one fixed task sequence."""

    route: Tuple[int, ...]
    forward: Tuple[Dict[int, float], ...]
    backward: Tuple[Dict[int, float], ...]
    cost: float


class RouteIncrementalEvaluator:
    """Exact insertion pricing for fixed routes using forward/backward tables."""

    def __init__(
        self,
        cost_matrix: CostMatrix,
        states_by_task: Dict[int, Iterable[State]],
        *,
        cache_limit: int = DEFAULT_CACHE_LIMIT,
    ):
        self._cost_matrix = cost_matrix
        self._task_states: Dict[int, Tuple[Tuple[int, float], ...]] = {
            task_id: tuple((state.state_id, state.processing_time) for state in states)
            for task_id, states in states_by_task.items()
        }
        self._cache: Dict[Tuple[int, ...], RouteTables] = {}
        self._cache_limit = cache_limit
        self._price_cache: Dict[Tuple[str, Tuple[int, ...], int, int], float] = {}
        self._removal_cache: Dict[Tuple[Tuple[int, ...], int], float] = {}
        self._price_cache_limit = DEFAULT_PRICE_CACHE_LIMIT
        self._table_builds = 0
        self._insertion_calls = 0
        self._price_hits = 0

    # -- tables -----------------------------------------------------------
    def tables(self, route: List[int] | Tuple[int, ...]) -> RouteTables:
        """Return the cached forward/backward tables of ``route``."""

        key = tuple(route)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        tables = self._build(key)
        if len(self._cache) >= self._cache_limit:
            # Generational reset: routes are replaced constantly, so an eviction
            # policy would not buy hit rate and would cost bookkeeping.
            self._cache.clear()
        self._cache[key] = tables
        return tables

    def _build(self, route: Tuple[int, ...]) -> RouteTables:
        self._table_builds += 1
        if not route:
            return RouteTables(route=route, forward=(), backward=(), cost=0.0)
        for task_id in route:
            if task_id not in self._task_states:
                raise ValueError(f"Unknown task id {task_id} in route")

        transition = self._cost_matrix.transition
        depot_to_state = self._cost_matrix.depot_to_state
        state_to_depot = self._cost_matrix.state_to_depot

        forward: List[Dict[int, float]] = []
        layer: Dict[int, float] = {}
        for position, task_id in enumerate(route):
            current: Dict[int, float] = {}
            for state_id, processing in self._task_states[task_id]:
                if position == 0:
                    current[state_id] = depot_to_state(state_id) + processing
                    continue
                best = inf
                for prev_id, prev_cost in layer.items():
                    candidate = prev_cost + transition(prev_id, state_id) + processing
                    if candidate < best:
                        best = candidate
                current[state_id] = best
            forward.append(current)
            layer = current

        backward: List[Dict[int, float]] = [{} for _ in route]
        layer = {}
        for position in range(len(route) - 1, -1, -1):
            task_id = route[position]
            if position == len(route) - 1:
                current = {
                    state_id: state_to_depot(state_id)
                    for state_id, _ in self._task_states[task_id]
                }
            else:
                following = route[position + 1]
                following_states = self._task_states[following]
                current = {}
                for state_id, _ in self._task_states[task_id]:
                    best = inf
                    for next_id, next_processing in following_states:
                        candidate = (
                            transition(state_id, next_id)
                            + next_processing
                            + layer[next_id]
                        )
                        if candidate < best:
                            best = candidate
                    current[state_id] = best
            backward[position] = current
            layer = current

        cost = min(
            value + state_to_depot(state_id)
            for state_id, value in forward[-1].items()
        )
        return RouteTables(
            route=route,
            forward=tuple(forward),
            backward=tuple(backward),
            cost=cost,
        )

    # -- pricing ----------------------------------------------------------
    def route_cost(self, route: List[int] | Tuple[int, ...]) -> float:
        """Return the exact optimal cost of ``route`` (same optimum as the route DP)."""

        return self.tables(route).cost

    def insertion_costs(self, route: List[int] | Tuple[int, ...], task_id: int) -> List[float]:
        """Return the exact cost of ``route`` with ``task_id`` inserted at each slot.

        The result has ``len(route) + 1`` entries; entry ``p`` is the optimal cost of
        the sequence ``route[:p] + [task_id] + route[p:]``.
        """

        tables = self.tables(route)
        if task_id not in self._task_states:
            raise ValueError(f"Unknown task id {task_id}")
        return [self._insertion_at(tables, position, task_id)
                for position in range(len(tables.route) + 1)]

    def best_insertion(self, route: List[int] | Tuple[int, ...], task_id: int) -> Tuple[int, float]:
        """Return the cheapest ``(position, cost)`` for inserting ``task_id``."""

        costs = self.insertion_costs(route, task_id)
        best_position = 0
        best_cost = costs[0]
        for position in range(1, len(costs)):
            if costs[position] < best_cost:
                best_cost = costs[position]
                best_position = position
        return best_position, best_cost

    def insertion_cost_at(
        self, tables: RouteTables, position: int, task_id: int
    ) -> float:
        """Return the exact cost of inserting ``task_id`` at one slot only.

        A local search stops at the first improving neighbour, so pricing the whole
        slot vector up front would compute slots that are never looked at.  This
        entry point keeps the scan lazy without giving up exactness.
        """

        if task_id not in self._task_states:
            raise ValueError(f"Unknown task id {task_id}")
        if position < 0 or position > len(tables.route):
            raise ValueError(
                f"position {position} out of range for route of length {len(tables.route)}"
            )
        key = ("insert", tables.route, task_id, position)
        cached = self._price_cache.get(key)
        if cached is not None:
            self._price_hits += 1
            return cached
        value = self._insertion_at(tables, position, task_id)
        self._remember_price(key, value)
        return value

    def _insertion_at(self, tables: RouteTables, position: int, task_id: int) -> float:
        self._insertion_calls += 1
        transition = self._cost_matrix.transition
        depot_to_state = self._cost_matrix.depot_to_state
        state_to_depot = self._cost_matrix.state_to_depot
        states_i = self._task_states[task_id]
        length = len(tables.route)

        after: Dict[int, float] = {}
        if position < length:
            following_states = self._task_states[tables.route[position]]
            backward = tables.backward[position]
            for state_id, _ in states_i:
                best = inf
                for next_id, next_processing in following_states:
                    candidate = transition(state_id, next_id) + next_processing + backward[next_id]
                    if candidate < best:
                        best = candidate
                after[state_id] = best

        best_total = inf
        if position == 0:
            for state_id, processing in states_i:
                tail = state_to_depot(state_id) if position == length else after[state_id]
                candidate = depot_to_state(state_id) + processing + tail
                if candidate < best_total:
                    best_total = candidate
            return best_total

        for previous_id, previous_cost in tables.forward[position - 1].items():
            best_step = inf
            for state_id, processing in states_i:
                tail = state_to_depot(state_id) if position == length else after[state_id]
                candidate = transition(previous_id, state_id) + processing + tail
                if candidate < best_step:
                    best_step = candidate
            total = previous_cost + best_step
            if total < best_total:
                best_total = total
        return best_total

    def removal_at(self, tables: RouteTables, position: int) -> float:
        """Return the exact cost of ``tables.route`` with one task removed.

        The prefix table and the suffix table meet across a single transition, so
        deleting a task costs ``O(64)`` regardless of the route length.  This is
        what makes a relocate scan affordable: the source side of every candidate
        is priced once per removed task instead of once per target slot.
        """

        self._insertion_calls += 1
        route = tables.route
        length = len(route)
        if length == 0 or position < 0 or position >= length:
            raise ValueError(f"position {position} out of range for route of length {length}")
        if length == 1:
            return 0.0

        key = (route, position)
        cached = self._removal_cache.get(key)
        if cached is not None:
            self._price_hits += 1
            return cached
        value = self._removal_uncached(tables, position)
        if len(self._removal_cache) >= self._price_cache_limit:
            self._removal_cache.clear()
        self._removal_cache[key] = value
        return value

    def _removal_uncached(self, tables: RouteTables, position: int) -> float:
        route = tables.route
        length = len(route)
        transition = self._cost_matrix.transition
        depot_to_state = self._cost_matrix.depot_to_state
        state_to_depot = self._cost_matrix.state_to_depot

        if position == 0:
            # ``backward[k]`` starts after task k finishes, so the processing time
            # of the task that comes next has to be added here.
            following = self._task_states[route[1]]
            suffix = tables.backward[1]
            best = inf
            for next_id, next_processing in following:
                candidate = depot_to_state(next_id) + next_processing + suffix[next_id]
                if candidate < best:
                    best = candidate
            return best

        if position == length - 1:
            best = inf
            for state_id, cost in tables.forward[position - 1].items():
                candidate = cost + state_to_depot(state_id)
                if candidate < best:
                    best = candidate
            return best

        following = self._task_states[route[position + 1]]
        suffix = tables.backward[position + 1]
        best = inf
        for previous_id, previous_cost in tables.forward[position - 1].items():
            for next_id, next_processing in following:
                candidate = (
                    previous_cost
                    + transition(previous_id, next_id)
                    + next_processing
                    + suffix[next_id]
                )
                if candidate < best:
                    best = candidate
        return best

    def replacement_at(self, tables: RouteTables, position: int, task_id: int) -> float:
        """Return the exact cost of ``tables.route`` with one task replaced in place.

        Replacing is "remove plus insert at the same index", so the prefix and the
        suffix are the untouched tables and only the new task's states are
        re-optimised: ``O(192)``, i.e. a small constant rather than a route DP.
        """

        self._insertion_calls += 1
        route = tables.route
        length = len(route)
        if length == 0 or position < 0 or position >= length:
            raise ValueError(f"position {position} out of range for route of length {length}")
        if task_id not in self._task_states:
            raise ValueError(f"Unknown task id {task_id}")

        key = ("replace", route, task_id, position)
        cached = self._price_cache.get(key)
        if cached is not None:
            self._price_hits += 1
            return cached
        value = self._replacement_uncached(tables, position, task_id)
        self._remember_price(key, value)
        return value

    def _replacement_uncached(
        self, tables: RouteTables, position: int, task_id: int
    ) -> float:
        route = tables.route
        length = len(route)
        transition = self._cost_matrix.transition
        depot_to_state = self._cost_matrix.depot_to_state
        state_to_depot = self._cost_matrix.state_to_depot
        states = self._task_states[task_id]

        prefix: Dict[int, float] = {}
        if position == 0:
            for state_id, _ in states:
                prefix[state_id] = depot_to_state(state_id)
        else:
            previous_layer = tables.forward[position - 1]
            for state_id, _ in states:
                best = inf
                for previous_id, previous_cost in previous_layer.items():
                    candidate = previous_cost + transition(previous_id, state_id)
                    if candidate < best:
                        best = candidate
                prefix[state_id] = best

        suffix: Dict[int, float] = {}
        if position == length - 1:
            for state_id, _ in states:
                suffix[state_id] = state_to_depot(state_id)
        else:
            following = self._task_states[route[position + 1]]
            following_layer = tables.backward[position + 1]
            for state_id, _ in states:
                best = inf
                for next_id, next_processing in following:
                    candidate = (
                        transition(state_id, next_id)
                        + next_processing
                        + following_layer[next_id]
                    )
                    if candidate < best:
                        best = candidate
                suffix[state_id] = best

        best = inf
        for state_id, processing in states:
            candidate = prefix[state_id] + processing + suffix[state_id]
            if candidate < best:
                best = candidate
        return best

    def route_cost_without(self, route: List[int] | Tuple[int, ...], position: int) -> float:
        """Return the exact cost of ``route`` with ``position`` removed."""

        return self.removal_at(self.tables(route), position)

    def route_cost_replaced(
        self, route: List[int] | Tuple[int, ...], position: int, task_id: int
    ) -> float:
        """Return the exact cost of ``route`` with ``task_id`` put at ``position``."""

        return self.replacement_at(self.tables(route), position, task_id)

    def route_costs(self, routes: Iterable[List[int] | Tuple[int, ...]]) -> List[float]:
        """Return the exact cost of every route in ``routes``."""

        return [self.route_cost(route) for route in routes]

    def _remember_price(self, key: Tuple[str, Tuple[int, ...], int, int], value: float) -> None:
        if len(self._price_cache) >= self._price_cache_limit:
            # Generational reset for the same reason as the table cache: candidate
            # routes are replaced constantly, so an eviction policy buys nothing.
            self._price_cache.clear()
        self._price_cache[key] = value

    def _clear_prices(self) -> None:
        self._price_cache.clear()
        self._removal_cache.clear()

    # -- introspection ----------------------------------------------------
    def statistics(self) -> Dict[str, int]:
        """Return cheap counters; they never include floating point state."""

        return {
            "table_builds": self._table_builds,
            "insertion_prices": self._insertion_calls,
            "price_cache_hits": self._price_hits,
            "cached_routes": len(self._cache),
            "cached_prices": len(self._price_cache),
        }

    def clear_cache(self) -> None:
        """Drop cached tables and prices; correctness is unaffected."""

        self._cache.clear()
        self._clear_prices()
