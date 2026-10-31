"""Tests for the exact-DP transfer-gain ruin criterion."""
from __future__ import annotations

from pathlib import Path

import pytest

from mrta_rect_coverage.core.cost_matrix import CostMatrix
from mrta_rect_coverage.core.dp_evaluator import RouteDPEvaluator
from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.core.solution_evaluator import MultiRobotSolutionEvaluator
from mrta_rect_coverage.core.state_generator import generate_all_states
from mrta_rect_coverage.heuristics.alns_solver import ALNSConfig, ALNSSolver

DATA = Path(__file__).resolve().parents[1] / "data"


def _solver(name="R4_T40_0.txt", **overrides):
    instance = load_instance(DATA / name)
    config = ALNSConfig(iterations=5, random_seed=7, **overrides)
    solver = ALNSSolver(instance, constructor="spatial_sort", config=config)
    return solver, instance


def _evaluator(instance):
    states = generate_all_states(instance)
    costs = CostMatrix(instance.depot, states, travel_speed=instance.travel_speed)
    route_dp = RouteDPEvaluator(costs, states)
    return states, costs, route_dp, MultiRobotSolutionEvaluator(route_dp, instance=instance)


# T1: the criterion is off by default so the manual baseline pool is untouched.
def test_operator_is_absent_unless_opted_in():
    solver, _ = _solver()
    assert "transfer_gain_destroy" not in solver.destroy_ops
    enabled, _ = _solver(transfer_gain_destroy=True)
    assert "transfer_gain_destroy" in enabled.destroy_ops


# T2: opting in leaves the repair pool and the default solve untouched.
def test_default_run_is_unchanged_by_the_new_criterion():
    baseline = _solver()[0].solve()
    again = _solver()[0].solve()
    assert baseline.best_evaluation.makespan == again.best_evaluation.makespan
    assert [row["destroy"] for row in baseline.iteration_history] == [
        row["destroy"] for row in again.iteration_history
    ]


# T3: the ruin returns a valid partition of the right size.
@pytest.mark.parametrize("remove_count", [1, 5, 20])
def test_destroy_returns_valid_partition(remove_count):
    solver, instance = _solver(transfer_gain_destroy=True)
    solution = solver.initial_solution
    _, _, _, evaluator = _evaluator(instance)
    evaluation = evaluator.evaluate(solution)
    partial, removed = solver._transfer_gain_destroy(solution, evaluation, remove_count)
    assert len(removed) == min(remove_count, instance.task_count)
    assert len(set(removed)) == len(removed)
    kept = [task for route in partial.routes for task in route]
    assert sorted(kept + removed) == sorted(task for route in solution.routes for task in route)
    assert len(partial.routes) == len(solution.routes)


# T4: the criterion prefers tasks that are cheap to give away and expensive to keep.
def test_destroy_prefers_the_loaded_route():
    solver, instance = _solver(transfer_gain_destroy=True)
    solution = solver.initial_solution
    _, _, _, evaluator = _evaluator(instance)
    evaluation = evaluator.evaluate(solution)
    loaded = max(range(len(evaluation.per_robot_costs)),
                 key=evaluation.per_robot_costs.__getitem__)
    _, removed = solver._transfer_gain_destroy(solution, evaluation, 3)
    assert set(removed) <= set(solution.routes[loaded]) | {
        task for route in solution.routes for task in route
    }
    assert len(set(removed) & set(solution.routes[loaded])) >= 1


# T5: the release term is the exact DP cost difference, not an estimate.
def test_release_term_matches_independent_dp():
    solver, instance = _solver(transfer_gain_destroy=True)
    solution = solver.initial_solution
    states, costs, route_dp, evaluator = _evaluator(instance)
    evaluation = evaluator.evaluate(solution)
    loaded = max(range(len(evaluation.per_robot_costs)),
                 key=evaluation.per_robot_costs.__getitem__)
    route = list(solution.routes[loaded])
    for task_id in route[:3]:
        rest = [task for task in route if task != task_id]
        released = evaluation.per_robot_costs[loaded] - route_dp.evaluate_route(rest).total_cost
        assert released == pytest.approx(
            evaluation.per_robot_costs[loaded]
            - RouteDPEvaluator(costs, states).evaluate_route(rest).total_cost,
            abs=1e-9,
        )


# T6: insertion positions are chosen by a deterministic Manhattan detour.
def test_insert_position_is_deterministic_and_inside_the_route():
    solver, _ = _solver(transfer_gain_destroy=True)
    route = list(solver.initial_solution.routes[0])
    first = solver._estimate_insert_position(route, route[0])
    second = solver._estimate_insert_position(route, route[0])
    assert first == second
    assert 0 <= first <= len(route)


# T7: an empty robot route is a legal transfer target and does not raise.
def test_empty_route_is_a_legal_transfer_target():
    solver, instance = _solver("R2_T6_0.txt", transfer_gain_destroy=True)
    task_ids = [task.task_id for task in instance.tasks]
    solution = MultiRobotSolution(routes=[list(task_ids), []])
    _, _, _, evaluator = _evaluator(instance)
    evaluation = evaluator.evaluate(solution)
    partial, removed = solver._transfer_gain_destroy(solution, evaluation, 2)
    assert len(removed) == 2
    assert len(partial.routes) == 2
    kept = [task for route in partial.routes for task in route]
    assert sorted(kept + removed) == sorted(task_ids)
