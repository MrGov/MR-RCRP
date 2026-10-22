"""Lower bound estimators."""
from __future__ import annotations

from math import inf
from typing import Dict, Iterable

from .cost_matrix import CostMatrix
from .models import Instance, State


def simple_average_processing_lb(
    instance: Instance, states_by_task: Dict[int, Iterable[State]]
) -> float:
    """Compute a trivial lower bound based on minimal processing time per task."""

    if instance.robot_count <= 0:
        raise ValueError("Instance must have a positive number of robots")
    total_processing = 0.0
    for task_id, states in states_by_task.items():
        try:
            min_time = min(state.processing_time for state in states)
        except ValueError as exc:
            raise ValueError(f"No states provided for task {task_id}") from exc
        total_processing += min_time
    return total_processing / instance.robot_count


def processing_with_travel_lb(
    instance: Instance,
    states_by_task: Dict[int, Iterable[State]],
    cost_matrix: CostMatrix,
) -> float:
    """Stronger LB using minimal depot access/leave costs per task.

    This bound accounts for the minimum cost of serving each task as a single-route
    (depot -> task -> depot) using the best entry/exit state. It returns the maximum
    of the average per-robot load and the largest single-task service cost.
    """

    if instance.robot_count <= 0:
        raise ValueError("Instance must have a positive number of robots")

    min_service_costs = []
    for task_id, states in states_by_task.items():
        try:
            best = min(
                cost_matrix.depot_to_state(state.state_id)
                + state.processing_time
                + cost_matrix.state_to_depot(state.state_id)
                for state in states
            )
        except ValueError as exc:
            raise ValueError(f"No states provided for task {task_id}") from exc
        min_service_costs.append(best)

    total = sum(min_service_costs)
    avg_lb = total / instance.robot_count
    max_lb = max(min_service_costs) if min_service_costs else 0.0
    return max(avg_lb, max_lb)


def processing_with_connectivity_lb(
    instance: Instance,
    states_by_task: Dict[int, Iterable[State]],
    cost_matrix: CostMatrix,
) -> float:
    """Approximate connectivity-aware LB using per-task min in/out links.

    For each task, we estimate one incoming and one outgoing connection cost by
    minimizing over candidate states and predecessor/successor tasks (including depot).
    This is task-graph aware and is generally tighter than a pure processing average.
    """

    if instance.robot_count <= 0:
        raise ValueError("Instance must have a positive number of robots")

    states_lookup = {task_id: list(states) for task_id, states in states_by_task.items()}
    if any(not states for states in states_lookup.values()):
        raise ValueError("Each task must provide at least one state")

    task_ids = list(states_lookup.keys())
    node_lbs = []

    for task_id in task_ids:
        states = states_lookup[task_id]
        min_processing = min(state.processing_time for state in states)

        min_in = inf
        min_out = inf
        for state in states:
            in_candidate = cost_matrix.depot_to_state(state.state_id)
            out_candidate = cost_matrix.state_to_depot(state.state_id)
            for other_task in task_ids:
                if other_task == task_id:
                    continue
                for prev_state in states_lookup[other_task]:
                    in_candidate = min(
                        in_candidate,
                        cost_matrix.transition(prev_state.state_id, state.state_id),
                    )
                    out_candidate = min(
                        out_candidate,
                        cost_matrix.transition(state.state_id, prev_state.state_id),
                    )
            min_in = min(min_in, in_candidate)
            min_out = min(min_out, out_candidate)

        node_lbs.append(min_processing + 0.5 * (min_in + min_out))

    total_lb = sum(node_lbs) / instance.robot_count
    singleton_lb = max(node_lbs) if node_lbs else 0.0
    return max(total_lb, singleton_lb)
