from __future__ import annotations

from itertools import product
import json
from pathlib import Path

import pytest

from mrta_rect_coverage.core.cost_matrix import CostMatrix
from mrta_rect_coverage.core.dp_evaluator import RouteDPEvaluator
from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.core.models import MultiRobotSolution, RouteEvaluation
from mrta_rect_coverage.core.solution_evaluator import MultiRobotSolutionEvaluator
from mrta_rect_coverage.core.state_chain_report import (
    assert_report_consistent,
    route_cost_split,
    route_regret_report,
    solution_state_report,
)
from mrta_rect_coverage.core.state_generator import generate_all_states

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _build(instance_name: str = "R2_T6_0.txt"):
    instance = load_instance(PROJECT_ROOT / "data" / instance_name)
    states_by_task = generate_all_states(instance)
    cost_matrix = CostMatrix(
        instance.depot, states_by_task, travel_speed=instance.travel_speed
    )
    route_dp = RouteDPEvaluator(cost_matrix, states_by_task)
    return instance, states_by_task, cost_matrix, route_dp


def _brute_force_chain_cost(chain, cost_matrix):
    if not chain:
        return 0.0
    total = cost_matrix.depot_to_state(chain[0].state_id)
    total += sum(state.processing_time for state in chain)
    total += sum(
        cost_matrix.transition(a.state_id, b.state_id)
        for a, b in zip(chain, chain[1:])
    )
    return total + cost_matrix.state_to_depot(chain[-1].state_id)


def _report_bundle(instance, states_by_task, cost_matrix, route_dp, routes=None):
    routes = routes or [list(range(1, instance.task_count + 1, 2)),
                        list(range(2, instance.task_count + 1, 2))]
    solution = MultiRobotSolution(routes=routes)
    evaluator = MultiRobotSolutionEvaluator(route_dp, instance=instance)
    evaluation = evaluator.evaluate(solution)
    report = solution_state_report(
        instance, solution, evaluation, states_by_task=states_by_task,
        cost_matrix=cost_matrix
    )
    return solution, evaluation, report


def test_t1_empty_route():
    _, states, cm, dp = _build()
    route = dp.evaluate_route([])
    report = route_regret_report(route, states_by_task=states, cost_matrix=cm)
    assert report.positions == ()
    assert report.route_optimal_cost == 0.0


def test_t2_single_task_route():
    _, states, cm, dp = _build()
    route = dp.evaluate_route([1])
    report = route_regret_report(route, states_by_task=states, cost_matrix=cm)
    position = report.positions[0]
    assert len(position.options) == 8
    assert min(option.q_cost for option in position.options) == pytest.approx(route.total_cost)
    chosen = next(o for o in position.options if o.state_id == position.chosen_state_id)
    assert chosen.regret == pytest.approx(0.0)
    assert position.chosen_rank == 1 + sum(
        (o.q_cost, o.state_id) < (chosen.q_cost, chosen.state_id)
        for o in position.options
    )


def test_t3_two_task_route_identities():
    _, states, cm, dp = _build()
    route = dp.evaluate_route([1, 2])
    report = route_regret_report(route, states_by_task=states, cost_matrix=cm)
    for position in report.positions:
        assert min(o.q_cost for o in position.options) == pytest.approx(
            report.route_optimal_cost, abs=1e-9
        )
        chosen = next(o for o in position.options if o.state_id == position.chosen_state_id)
        assert chosen.q_cost == pytest.approx(report.route_optimal_cost, abs=1e-9)


def test_t4_three_task_brute_force_and_fixed_state_q():
    _, states, cm, dp = _build()
    route_ids = [1, 2, 3]
    route_eval = dp.evaluate_route(route_ids)
    report = route_regret_report(route_eval, states_by_task=states, cost_matrix=cm)
    layers = [states[task_id] for task_id in route_ids]
    all_chains = list(product(*layers))
    brute_optimum = min(_brute_force_chain_cost(chain, cm) for chain in all_chains)
    assert len(all_chains) == 8**3
    assert brute_optimum == pytest.approx(report.route_optimal_cost, abs=1e-9)
    for position, layer in enumerate(layers):
        for state in layer:
            fixed_cost = min(
                _brute_force_chain_cost(chain, cm)
                for chain in all_chains
                if chain[position].state_id == state.state_id
            )
            option = next(
                o for o in report.positions[position].options
                if o.state_id == state.state_id
            )
            assert fixed_cost == pytest.approx(option.q_cost, abs=1e-9)


def test_t5_tampering_is_detected():
    instance, states, cm, dp = _build()
    _, _, report = _report_bundle(instance, states, cm, dp)
    assert_report_consistent(report)
    report["routes"][0]["regret_table"][0]["options"][0]["regret"] = -1.0
    with pytest.raises(ValueError):
        assert_report_consistent(report)

    _, _, report = _report_bundle(instance, states, cm, dp)
    report["objective"]["makespan"] += 1.0
    with pytest.raises(ValueError):
        assert_report_consistent(report)


def test_t6_report_does_not_call_or_mutate_route_dp():
    instance, states, cm, dp = _build()
    solution = MultiRobotSolution(routes=[list(range(1, 7)), []])
    evaluation = MultiRobotSolutionEvaluator(dp, instance=instance).evaluate(solution)
    before = dp.statistics()
    solution_state_report(
        instance, solution, evaluation, states_by_task=states, cost_matrix=cm
    )
    after = dp.statistics()
    assert before["calls"] == after["calls"]
    assert before["cache_misses"] == after["cache_misses"]


def test_t7_report_is_deterministic():
    instance, states, cm, dp = _build()
    solution, evaluation, _ = _report_bundle(instance, states, cm, dp)
    first = solution_state_report(
        instance, solution, evaluation, states_by_task=states, cost_matrix=cm
    )
    second = solution_state_report(
        instance, solution, evaluation, states_by_task=states, cost_matrix=cm
    )
    assert first == second
    first_bytes = json.dumps(first, sort_keys=True, separators=(",", ":")).encode("utf-8")
    second_bytes = json.dumps(second, sort_keys=True, separators=(",", ":")).encode("utf-8")
    assert first_bytes == second_bytes


def test_t8_cost_split_identity():
    instance, states, cm, dp = _build()
    solution, evaluation, report = _report_bundle(instance, states, cm, dp)
    task_by_id = {task.task_id: task for task in instance.tasks}
    for route_eval, row in zip(evaluation.route_evaluations, report["routes"]):
        split = route_cost_split(route_eval, instance=instance, task_by_id=task_by_id)
        assert split["coverage"] + split["turning"] + split["transfer"] == pytest.approx(
            split["total"], abs=1e-6
        )
        assert split["transfer"] == pytest.approx(sum(route_eval.transition_costs))
        assert row["cost_split"] == split


def test_t9_option_sort_order_and_unique_ids():
    _, states, cm, dp = _build()
    report = route_regret_report(
        dp.evaluate_route([1, 2]), states_by_task=states, cost_matrix=cm
    )
    for position in report.positions:
        keys = [(option.q_cost, option.state_id) for option in position.options]
        assert keys == sorted(keys)
        ids = [option.state_id for option in position.options]
        assert len(ids) == len(set(ids))


def test_t10_invalid_routes_name_task_id():
    _, states, cm, dp = _build()
    for route_ids, state_map in (([1, 1], states), ([99], states), ([1], {2: states[2]})):
        with pytest.raises(ValueError, match="task_id"):
            route_regret_report(
                RouteEvaluation(route_ids, [], 0.0),
                states_by_task=state_map,
                cost_matrix=cm,
            )


def test_t11_near_tie_tolerance():
    _, states, cm, dp = _build()
    route = dp.evaluate_route([1])
    strict = route_regret_report(
        route, states_by_task=states, cost_matrix=cm, near_tie_tol=0.0
    )
    broad = route_regret_report(
        route, states_by_task=states, cost_matrix=cm, near_tie_tol=1e9
    )
    assert broad.positions[0].near_tie_count == 7
    assert strict.positions[0].near_tie_count <= 7


def test_state_generation_matches_sweep_and_corner_rules():
    from mrta_rect_coverage.core.state_generator import (
        _compute_n_sweeps,
        _determine_exit_corner,
    )

    instance, states, _, _ = _build()
    for task in instance.tasks:
        for state in states[task.task_id]:
            assert state.n_sweeps == _compute_n_sweeps(
                task, state.sweep_mode, instance.sweep_width
            )
            assert state.exit_corner == _determine_exit_corner(
                state.sweep_mode, state.entry_corner, state.n_sweeps
            )
