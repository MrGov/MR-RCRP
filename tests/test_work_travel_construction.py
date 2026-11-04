from importlib import import_module, util
from copy import deepcopy
from time import perf_counter

import pytest

from mrta_rect_coverage.core.models import Instance, TaskRegion
from mrta_rect_coverage.heuristics.structural_search import PairPortfolioSolver
from mrta_rect_coverage.heuristics.alns_solver import ALNSConfig


def build_solver():
    tasks = [TaskRegion(i, (i % 4) * 25, (i // 4) * 30,
                       (i % 4) * 25 + 3 + i, (i // 4) * 30 + 5) for i in range(12)]
    solver = PairPortfolioSolver(Instance('construction-test', (0, 0), 3, 1, .7, 1.5, .4, tasks),
        config=ALNSConfig.enhanced(iterations=0, random_seed=17))
    solver.set_pairs([('random_destroy', 'greedy_insertion')])
    return solver


def constructor():
    name = 'mrta_rect_coverage.heuristics.work_travel_construction'
    assert util.find_spec(name) is not None, 'budgeted work/travel constructor is not implemented'
    return import_module(name).improve_initialization


def test_complete_construction_preserves_tasks_and_exact_costs():
    fn = constructor()
    solver = build_solver()
    old = solver.solution_evaluator.evaluate(solver.initial_solution).makespan
    state = solver.rng.getstate()
    row = fn(solver, deadline=perf_counter() + 10)
    value = solver.solution_evaluator.evaluate(solver.initial_solution)
    assert row['status'] == 'complete'
    assert row['assigned_tasks'] == 12
    assert value.makespan <= old + 1e-8
    assert value.per_robot_costs == pytest.approx(row['selected_costs'])
    assert sorted(t for r in solver.initial_solution.routes for t in r) == list(range(12))
    assert solver.rng.getstate() == state
    assert solver.solve().best_evaluation.makespan == pytest.approx(value.makespan)


def test_expired_budget_starts_no_pricing(monkeypatch):
    fn = constructor()
    solver = build_solver()
    old = deepcopy(solver.initial_solution.routes)
    monkeypatch.setattr(solver.insertion_pricer, 'tables', lambda *a: pytest.fail('priced after deadline'))
    row = fn(solver, deadline=perf_counter() - 1)
    assert row['status'] == 'budget_exhausted'
    assert row['price_requests'] == 0
    assert solver.initial_solution.routes == old
    solver.solution_evaluator.evaluate(solver.initial_solution)


def test_price_cap_discards_partial_construction():
    fn = constructor()
    solver = build_solver()
    old = deepcopy(solver.initial_solution.routes)
    row = fn(solver, deadline=perf_counter() + 10, price_cap=7)
    assert row['status'] == 'price_cap'
    assert row['price_requests'] == 7
    assert solver.initial_solution.routes == old
    assert row['assigned_tasks'] < 12


def test_route_matching_ignores_robot_permutation():
    from mrta_rect_coverage.experiments.constructor_followup import route_match
    result = route_match([[1, 2], [3], [4, 5]], [[5, 4], [2, 1], [3]])
    assert result['changed_assignment_tasks'] == 0
    assert tuple(result['right_robot_for_left']) == (1, 2, 0)
