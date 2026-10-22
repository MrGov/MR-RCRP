"""Dynamic programming evaluator for fixed task sequences."""
from __future__ import annotations

from math import inf
from time import perf_counter
from typing import Dict, Iterable, List, Tuple

from .cost_matrix import CostMatrix
from .models import RouteEvaluation, State


class RouteDPEvaluator:
    """Evaluate the optimal state chain for a given ordered task route."""

    def __init__(
        self,
        cost_matrix: CostMatrix,
        states_by_task: Dict[int, Iterable[State]],
        *,
        enable_cache: bool = True,
    ):
        self._cost_matrix = cost_matrix
        self._states_by_task: Dict[int, List[State]] = {
            task_id: list(states) for task_id, states in states_by_task.items()
        }
        self._enable_cache = enable_cache
        self._cache: Dict[Tuple[int, ...], RouteEvaluation] = {}
        self._calls = 0
        self._cache_hits = 0
        self._cache_misses = 0
        self._compute_time_sec = 0.0

    def clear_cache(self) -> None:
        """Clear cached route evaluations."""

        self._cache.clear()

    def evaluate_route(self, route_task_ids: List[int]) -> RouteEvaluation:
        """Return optimal state chain and cost for the provided route."""

        self._calls += 1
        key = tuple(route_task_ids)
        if self._enable_cache and key in self._cache:
            self._cache_hits += 1
            return self._cache[key]
        self._cache_misses += 1
        compute_started = perf_counter()

        if not route_task_ids:
            evaluation = RouteEvaluation(
                route_task_ids=[],
                chosen_state_ids=[],
                total_cost=0.0,
                cumulative_costs=[],
                transition_costs=[],
                predecessor_state_ids=[],
            )
            if self._enable_cache:
                self._cache[key] = evaluation
            self._compute_time_sec += perf_counter() - compute_started
            return evaluation

        layer_history: List[Dict[int, tuple[float, int | None]]] = []
        previous_layer: Dict[int, tuple[float, int | None]] = {}

        for position, task_id in enumerate(route_task_ids):
            if task_id not in self._states_by_task:
                raise ValueError(f"Unknown task id {task_id} in route")
            current_layer: Dict[int, tuple[float, int | None]] = {}
            for state in self._states_by_task[task_id]:
                base_cost = state.processing_time
                if position == 0:
                    cost = self._cost_matrix.depot_to_state(state.state_id) + base_cost
                    current_layer[state.state_id] = (cost, None)
                else:
                    best_cost = inf
                    best_prev: int | None = None
                    for prev_state_id, (prev_cost, _) in previous_layer.items():
                        transition_cost = self._cost_matrix.transition(
                            prev_state_id, state.state_id
                        )
                        candidate = prev_cost + transition_cost + base_cost
                        if candidate < best_cost:
                            best_cost = candidate
                            best_prev = prev_state_id
                    current_layer[state.state_id] = (best_cost, best_prev)
            layer_history.append(current_layer)
            previous_layer = current_layer

        best_total = inf
        best_final_state: int | None = None
        final_layer = layer_history[-1]
        for state_id, (cost, _) in final_layer.items():
            total = cost + self._cost_matrix.state_to_depot(state_id)
            if total < best_total:
                best_total = total
                best_final_state = state_id

        if best_final_state is None:
            raise RuntimeError("Failed to identify final state in DP evaluation")

        chosen_state_ids_rev: List[int] = []
        predecessor_ids_rev: List[int | None] = []
        cumulative_costs_rev: List[float] = []

        current_state = best_final_state
        for layer in reversed(layer_history):
            chosen_state_ids_rev.append(current_state)
            cumulative_cost, prev_state = layer[current_state]
            predecessor_ids_rev.append(prev_state)
            cumulative_costs_rev.append(cumulative_cost)
            if prev_state is None:
                break
            current_state = prev_state

        chosen_state_ids = list(reversed(chosen_state_ids_rev))
        predecessor_state_ids = list(reversed(predecessor_ids_rev))
        cumulative_costs = list(reversed(cumulative_costs_rev))

        chosen_states = [self._cost_matrix.state(state_id) for state_id in chosen_state_ids]
        entry_points = [state.entry_point for state in chosen_states]
        exit_points = [state.exit_point for state in chosen_states]

        transition_costs: List[float] = []
        if chosen_state_ids:
            first_state = chosen_state_ids[0]
            transition_costs.append(self._cost_matrix.depot_to_state(first_state))
            for from_state, to_state in zip(chosen_state_ids, chosen_state_ids[1:]):
                transition_costs.append(self._cost_matrix.transition(from_state, to_state))
            transition_costs.append(self._cost_matrix.state_to_depot(chosen_state_ids[-1]))

        evaluation = RouteEvaluation(
            route_task_ids=list(route_task_ids),
            chosen_state_ids=chosen_state_ids,
            total_cost=best_total,
            chosen_states=chosen_states,
            entry_points=entry_points,
            exit_points=exit_points,
            cumulative_costs=cumulative_costs,
            transition_costs=transition_costs,
            predecessor_state_ids=predecessor_state_ids,
        )
        if self._enable_cache:
            self._cache[key] = evaluation
        self._compute_time_sec += perf_counter() - compute_started
        return evaluation

    def statistics(self) -> dict[str, float | int]:
        """Return cumulative workload counters without mutating the cache."""

        return {
            "calls": self._calls,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_hit_rate": self._cache_hits / self._calls if self._calls else 0.0,
            "compute_time_sec": self._compute_time_sec,
        }
