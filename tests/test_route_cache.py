from __future__ import annotations

from pathlib import Path

from mrta_rect_coverage.core.cost_matrix import CostMatrix
from mrta_rect_coverage.core.dp_evaluator import RouteDPEvaluator
from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.core.state_generator import generate_all_states


def test_route_cache_reuses_result() -> None:
    project_root = Path(__file__).resolve().parents[1]
    instance_path = project_root / "data" / "R2_T6_0.txt"
    instance = load_instance(instance_path)
    states_by_task = generate_all_states(instance)
    cost_matrix = CostMatrix(
        instance.depot, states_by_task, travel_speed=instance.travel_speed
    )
    evaluator = RouteDPEvaluator(cost_matrix, states_by_task, enable_cache=True)

    route = [1, 2, 3]
    first = evaluator.evaluate_route(route)
    second = evaluator.evaluate_route(route)

    assert first.total_cost == second.total_cost
    assert first.chosen_state_ids == second.chosen_state_ids
    assert len(first.entry_points) == len(route)
    assert len(first.exit_points) == len(route)
