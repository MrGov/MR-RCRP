"""Pre-computed Manhattan travel-time matrices."""
from __future__ import annotations

import math
from typing import Dict, Iterable, Tuple

from ..utils.geometry import manhattan_distance
from .models import State


class CostMatrix:
    """Pre-compute travel times between the depot and task states."""

    def __init__(
        self,
        depot: Tuple[float, float],
        states_by_task: Dict[int, Iterable[State]],
        *,
        travel_speed: float,
    ):
        if not math.isfinite(travel_speed) or travel_speed <= 0:
            raise ValueError("travel_speed must be finite and positive")
        self._depot = depot
        self._travel_speed = travel_speed
        self._states_by_task: Dict[int, list[State]] = {
            task_id: list(states) for task_id, states in states_by_task.items()
        }
        self._state_lookup: Dict[int, State] = {}
        for state_list in self._states_by_task.values():
            for state in state_list:
                self._state_lookup[state.state_id] = state

        self._depot_to_state: Dict[int, float] = {}
        self._state_to_depot: Dict[int, float] = {}
        self._state_to_state: Dict[Tuple[int, int], float] = {}

        self._precompute_costs()

    def depot_to_state(self, state_id: int) -> float:
        """Return travel time from depot to state entry."""

        return self._depot_to_state[state_id]

    def state_to_depot(self, state_id: int) -> float:
        """Return travel time from state exit to depot."""

        return self._state_to_depot[state_id]

    def transition(self, from_state_id: int, to_state_id: int) -> float:
        """Return travel time between states belonging to different tasks."""

        return self._state_to_state[(from_state_id, to_state_id)]

    def state(self, state_id: int) -> State:
        """Return the state object for a given identifier."""

        return self._state_lookup[state_id]

    def _precompute_costs(self) -> None:
        for state in self._state_lookup.values():
            self._depot_to_state[state.state_id] = manhattan_distance(
                self._depot, state.entry_point
            ) / self._travel_speed
            self._state_to_depot[state.state_id] = manhattan_distance(
                state.exit_point, self._depot
            ) / self._travel_speed

        task_ids = list(self._states_by_task.keys())
        for task_id_a in task_ids:
            states_a = self._states_by_task[task_id_a]
            for task_id_b in task_ids:
                if task_id_a == task_id_b:
                    continue
                states_b = self._states_by_task[task_id_b]
                for state_a in states_a:
                    for state_b in states_b:
                        key = (state_a.state_id, state_b.state_id)
                        self._state_to_state[key] = manhattan_distance(
                            state_a.exit_point, state_b.entry_point
                        ) / self._travel_speed
