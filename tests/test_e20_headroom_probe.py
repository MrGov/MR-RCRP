"""Tests for the E20 headroom probe (exact bottleneck descent on saved routes)."""

from __future__ import annotations

from itertools import permutations
from pathlib import Path

import pytest

from mrta_rect_coverage.core.cost_matrix import CostMatrix
from mrta_rect_coverage.core.dp_evaluator import RouteDPEvaluator
from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.core.state_generator import generate_all_states
from mrta_rect_coverage.experiments.e20_headroom_probe import (
    RoutePricer,
    _objective,
    _better,
    descend,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _setup(instance_name: str = "R2_T6_0.txt"):
    instance = load_instance(PROJECT_ROOT / "data" / instance_name)
    states = generate_all_states(instance)
    matrix = CostMatrix(instance.depot, states, travel_speed=instance.travel_speed)
    evaluator = RouteDPEvaluator(matrix, states)
    return instance, evaluator


def _pricer(instance_name: str = "R2_T6_0.txt") -> RoutePricer:
    _, evaluator = _setup(instance_name)
    return RoutePricer(evaluator)


def _independent_cost(instance, route) -> float:
    """Recompute a route cost through a fresh evaluator, no shared memo."""
    states = generate_all_states(instance)
    matrix = CostMatrix(instance.depot, states, travel_speed=instance.travel_speed)
    evaluator = RouteDPEvaluator(matrix, states)
    return 0.0 if not route else evaluator.evaluate_route(list(route)).total_cost


def _neighborhood_improves(instance, routes) -> bool:
    """Brute-force check that no relocate or swap move improves the objective."""
    costs = [_independent_cost(instance, route) for route in routes]
    incumbent = _objective(costs)
    for critical, crit_route in enumerate(routes):
        for position, task in enumerate(crit_route):
            reduced = crit_route[:position] + crit_route[position + 1 :]
            reduced_cost = _independent_cost(instance, reduced)
            for target, route in enumerate(routes):
                if target == critical:
                    continue
                for insertion in range(len(route) + 1):
                    grown = route[:insertion] + [task] + route[insertion:]
                    trial = list(costs)
                    trial[critical] = reduced_cost
                    trial[target] = _independent_cost(instance, grown)
                    if _better(_objective(trial), incumbent):
                        return True
        for position, task in enumerate(crit_route):
            crit_base = crit_route[:position] + crit_route[position + 1 :]
            for target, route in enumerate(routes):
                if target == critical:
                    continue
                for other_position, other_task in enumerate(route):
                    new_crit = crit_base + [other_task]
                    new_target = route[:other_position] + route[other_position + 1 :] + [task]
                    for crit_order in {tuple(new_crit), tuple(reversed(new_crit))}:
                        for target_order in {tuple(new_target), tuple(reversed(new_target))}:
                            trial = list(costs)
                            trial[critical] = _independent_cost(instance, list(crit_order))
                            trial[target] = _independent_cost(instance, list(target_order))
                            if _better(_objective(trial), incumbent):
                                return True
    return False


def test_e20_t1_start_cost_matches_independent_evaluator():
    instance, _ = _setup()
    pricer = _pricer()
    routes = [[1, 2, 3], [4, 5, 6]]
    result = descend(routes, pricer, max_passes=1)
    assert result["start_makespan"] == pytest.approx(
        max(_independent_cost(instance, route) for route in routes), abs=1e-9
    )
    assert result["start_sum"] == pytest.approx(
        sum(_independent_cost(instance, route) for route in routes), abs=1e-6
    )


def test_e20_t2_descent_never_worsens():
    instance, _ = _setup("R2_T10_0.txt")
    pricer = _pricer("R2_T10_0.txt")
    routes = [[1, 3, 5, 7, 9], [2, 4, 6, 8, 10]]
    result = descend(routes, pricer)
    assert result["final_makespan"] <= result["start_makespan"] + 1e-9
    assert result["final_sum"] <= result["start_sum"] + 1e-9
    assert result["passes"] >= 1


def test_e20_t3_final_routes_are_a_local_optimum_of_that_neighborhood():
    instance, _ = _setup("R2_T10_0.txt")
    pricer = _pricer("R2_T10_0.txt")
    routes = [[1, 3, 5, 7, 9], [2, 4, 6, 8, 10]]
    result = descend(routes, pricer)
    assert not _neighborhood_improves(instance, result["routes"])


def test_e20_t4_relocate_is_applied_when_it_pays():
    """A badly unbalanced assignment must be repaired by moving work off the loaded robot."""
    instance, _ = _setup("R2_T10_0.txt")
    pricer = _pricer("R2_T10_0.txt")
    routes = [[1, 2, 3, 4, 5, 6, 7, 8], [9, 10]]
    result = descend(routes, pricer)
    moved = result["applied"]["relocate"] + result["applied"]["swap"]
    assert moved >= 1
    assert result["final_makespan"] < result["start_makespan"]
    assert abs(_objective(result["costs"])[0] - result["final_makespan"]) <= 1e-9


def test_e20_t5_result_routes_keep_every_task_exactly_once():
    instance, _ = _setup("R2_T10_0.txt")
    pricer = _pricer("R2_T10_0.txt")
    routes = [[1, 3, 5, 7, 9], [2, 4, 6, 8, 10]]
    result = descend(routes, pricer)
    flat = [task for route in result["routes"] for task in route]
    assert sorted(flat) == list(range(1, instance.task_count + 1))


def test_e20_t6_memo_does_not_change_the_result_but_saves_pricings():
    instance, _ = _setup("R2_T10_0.txt")
    routes = [[1, 3, 5, 7, 9], [2, 4, 6, 8, 10]]
    fresh = RoutePricer(_setup("R2_T10_0.txt")[1])
    warm = RoutePricer(_setup("R2_T10_0.txt")[1])
    first = descend(routes, fresh)
    for route in routes:
        warm.cost(route)
    warm.calls = 0
    second = descend(routes, warm)
    assert first["final_makespan"] == pytest.approx(second["final_makespan"], abs=1e-9)
    assert warm.calls < fresh.calls


def test_e20_t7_time_cap_is_reported_and_solution_stays_feasible():
    instance, _ = _setup("R2_T10_0.txt")
    pricer = _pricer("R2_T10_0.txt")
    routes = [[1, 2, 3, 4, 5, 6, 7, 8], [9, 10]]
    result = descend(routes, pricer, max_passes=40, max_seconds=0.0)
    assert result["time_limited"] is True
    flat = [task for route in result["routes"] for task in route]
    assert sorted(flat) == list(range(1, instance.task_count + 1))
    assert result["route_dp_calls"] >= instance.robot_count


def test_e20_t8_empty_route_costs_zero_and_can_receive_work():
    pricer = _pricer()
    assert pricer.cost([]) == 0.0
    assert pricer.cost([1]) > 0.0
    _, _ = _setup("R2_T6_0.txt")


def test_e20_t9_persisted_probe_report_is_consistent():
    report = PROJECT_ROOT / "outputs/e20_headroom_probe/headroom.json"
    if not report.exists():
        pytest.skip("run e20 --stage probe first")
    import json

    data = json.loads(report.read_text(encoding="utf-8"))
    rows = data["rows"]
    assert rows
    for row in rows:
        assert row["final_makespan"] <= row["start_makespan"] + 1e-9
        expected = 100.0 * (1.0 - row["final_makespan"] / row["start_makespan"])
        assert row["drop_pct"] == pytest.approx(expected, abs=1e-9)
    summary = data["summary"]
    assert summary["records"] == len(rows)
    assert summary["overall"]["makespan_mismatch"] == 0
