from __future__ import annotations

from pathlib import Path

from mrta_rect_coverage.core.cost_matrix import CostMatrix
from mrta_rect_coverage.core.dp_evaluator import RouteDPEvaluator
from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.core.state_generator import generate_all_states


def _build_dp():
    project_root = Path(__file__).resolve().parents[1]
    instance_path = project_root / "data" / "R2_T6_0.txt"
    instance = load_instance(instance_path)
    states_by_task = generate_all_states(instance)
    cost_matrix = CostMatrix(
        instance.depot, states_by_task, travel_speed=instance.travel_speed
    )
    route_dp = RouteDPEvaluator(cost_matrix, states_by_task)
    return instance, states_by_task, route_dp


def test_empty_route_cost_zero() -> None:
    _, _, route_dp = _build_dp()
    evaluation = route_dp.evaluate_route([])
    assert evaluation.total_cost == 0
    assert evaluation.chosen_state_ids == []


def test_single_task_route() -> None:
    instance, states_by_task, route_dp = _build_dp()
    evaluation = route_dp.evaluate_route([1])
    assert len(evaluation.chosen_state_ids) == 1
    assert evaluation.total_cost > 0
    state_lookup = {state.state_id: state.task_id for state_list in states_by_task.values() for state in state_list}
    assert state_lookup[evaluation.chosen_state_ids[0]] == 1


def test_two_task_route() -> None:
    instance, states_by_task, route_dp = _build_dp()
    route = [1, 2]
    evaluation = route_dp.evaluate_route(route)
    assert len(evaluation.route_task_ids) == len(route)
    assert len(evaluation.chosen_state_ids) == len(route)
    state_lookup = {state.state_id: state.task_id for state_list in states_by_task.values() for state in state_list}
    for task_id, state_id in zip(route, evaluation.chosen_state_ids):
        assert state_lookup[state_id] == task_id
    assert evaluation.total_cost >= 0
