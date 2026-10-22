from __future__ import annotations

from pathlib import Path

from mrta_rect_coverage.core.cost_matrix import CostMatrix
from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.core.lower_bounds import (
    processing_with_travel_lb,
    simple_average_processing_lb,
)
from mrta_rect_coverage.core.state_generator import generate_all_states


def test_processing_with_travel_lb_stronger() -> None:
    project_root = Path(__file__).resolve().parents[1]
    instance_path = project_root / "data" / "R2_T6_0.txt"
    instance = load_instance(instance_path)
    states_by_task = generate_all_states(instance)
    cost_matrix = CostMatrix(
        instance.depot, states_by_task, travel_speed=instance.travel_speed
    )

    simple_lb = simple_average_processing_lb(instance, states_by_task)
    travel_lb = processing_with_travel_lb(instance, states_by_task, cost_matrix)

    assert travel_lb >= simple_lb
    assert travel_lb >= 0
