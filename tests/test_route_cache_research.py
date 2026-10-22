from __future__ import annotations

from pathlib import Path

from mrta_rect_coverage.core.cost_matrix import CostMatrix
from mrta_rect_coverage.core.dp_evaluator import RouteDPEvaluator
from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.core.state_generator import generate_all_states


def test_route_cache_preserves_rich_dp_info() -> None:
    project_root = Path(__file__).resolve().parents[1]
    instance = load_instance(project_root / "data" / "R2_T6_0.txt")
    states = generate_all_states(instance)
    cm = CostMatrix(instance.depot, states, travel_speed=instance.travel_speed)
    evaluator = RouteDPEvaluator(cm, states, enable_cache=True)

    route = [1, 2, 3]
    first = evaluator.evaluate_route(route)
    second = evaluator.evaluate_route(route)

    assert first is second
    assert len(first.cumulative_costs) == len(route)
    assert len(first.predecessor_state_ids) == len(route)
    assert len(first.transition_costs) == len(route) + 1
    assert first.transition_costs[0] >= 0
