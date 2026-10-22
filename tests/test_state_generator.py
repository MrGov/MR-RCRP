from __future__ import annotations

from pathlib import Path

import pytest

from mrta_rect_coverage.core.enums import Corner, SweepMode
from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.core.state_generator import generate_all_states


@pytest.fixture(scope="module")
def states_by_task():
    project_root = Path(__file__).resolve().parents[1]
    instance_path = project_root / "data" / "R2_T6_0.txt"
    instance = load_instance(instance_path)
    return generate_all_states(instance)


def test_each_task_has_eight_states(states_by_task) -> None:
    for task_id, states in states_by_task.items():
        assert len(states) == 8, f"Task {task_id} does not have 8 states"


def test_processing_times(states_by_task) -> None:
    first_task_states = states_by_task[1]
    lb_h = _find_state(first_task_states, Corner.LB, SweepMode.H)
    lb_v = _find_state(first_task_states, Corner.LB, SweepMode.V)

    assert lb_h.n_sweeps == 2
    assert lb_h.processing_time == pytest.approx(16.5)

    assert lb_v.n_sweeps == 4
    assert lb_v.processing_time == pytest.approx(13.5)


def test_parity_mapping(states_by_task) -> None:
    first_task_states = states_by_task[1]
    lb_h_even = _find_state(first_task_states, Corner.LB, SweepMode.H)
    assert lb_h_even.exit_corner == Corner.LT  # even sweeps

    lb_v_even = _find_state(first_task_states, Corner.LB, SweepMode.V)
    assert lb_v_even.exit_corner == Corner.RB  # even sweeps

    fourth_task_states = states_by_task[4]
    lb_h_odd = _find_state(fourth_task_states, Corner.LB, SweepMode.H)
    assert lb_h_odd.n_sweeps % 2 == 1
    assert lb_h_odd.exit_corner == Corner.RT

    lb_v_odd = _find_state(fourth_task_states, Corner.LB, SweepMode.V)
    assert lb_v_odd.n_sweeps % 2 == 1
    assert lb_v_odd.exit_corner == Corner.RT


def _find_state(states, corner: Corner, mode: SweepMode):
    for state in states:
        if state.entry_corner == corner and state.sweep_mode == mode:
            return state
    raise AssertionError(f"State not found for corner {corner} and mode {mode}")
