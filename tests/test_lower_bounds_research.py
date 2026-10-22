from __future__ import annotations

from pathlib import Path

from mrta_rect_coverage.core.cost_matrix import CostMatrix
from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.core.lower_bounds import (
    processing_with_connectivity_lb,
    simple_average_processing_lb,
)
from mrta_rect_coverage.core.state_generator import generate_all_states


def test_connectivity_lb_not_weaker_than_simple_lb() -> None:
    project_root = Path(__file__).resolve().parents[1]
    instance = load_instance(project_root / "data" / "R2_T6_0.txt")
    states = generate_all_states(instance)
    cost_matrix = CostMatrix(
        instance.depot, states, travel_speed=instance.travel_speed
    )

    simple_lb = simple_average_processing_lb(instance, states)
    connect_lb = processing_with_connectivity_lb(instance, states, cost_matrix)

    assert connect_lb >= simple_lb
    assert connect_lb >= 0


