from importlib import import_module
from pathlib import Path

import pytest

from mrta_rect_coverage.comparison_algorithms.common import SearchConfig, SearchEnvironment, SearchDeadline
from mrta_rect_coverage.core.dp_evaluator import RouteDPEvaluator
from mrta_rect_coverage.core.instance_loader import load_instance

ROOT = Path(__file__).resolve().parents[1]


def test_greedy_trace_is_legal_and_last_choice_includes_return():
    env = SearchEnvironment(load_instance(ROOT/'data/R2_T10_0.txt'), SearchConfig(max_time=10, evaluation_mode='greedy'))
    route = [1, 4, 7]
    result = env.route(route)
    previous = None
    cumulative = 0
    for pos, chosen in enumerate(result.chosen_states):
        def incremental(state):
            incoming = env.costs.depot_to_state(state.state_id) if previous is None else env.costs.transition(previous, state.state_id)
            return incoming + state.processing_time + (env.costs.state_to_depot(state.state_id) if pos == len(route)-1 else 0)
        assert chosen == min(env.states[route[pos]], key=incremental)
        cumulative += result.transition_costs[pos] + chosen.processing_time
        assert result.cumulative_costs[pos] == pytest.approx(cumulative)
        previous = chosen.state_id
    assert result.total_cost == pytest.approx(cumulative + result.transition_costs[-1])


@pytest.mark.parametrize('module', ['cdabc','rnsga','sga_ts','mrhdabc'])
def test_greedy_search_never_calls_exact_before_independent_recheck(module, monkeypatch):
    original = RouteDPEvaluator.evaluate_route
    calls = []
    def spy(dp, route):
        # Only the independent final evaluator may invoke exact optimization.
        assert getattr(dp, '_e13_final_recheck', False)
        calls.append(tuple(route))
        return original(dp, route)
    monkeypatch.setattr(RouteDPEvaluator, 'evaluate_route', spy)
    result = import_module('mrta_rect_coverage.comparison_algorithms.'+module).solve(
        load_instance(ROOT/'data/R2_T10_0.txt'),
        SearchConfig(max_time=10, max_generations=2, population_size=4, evaluation_mode='greedy'))
    assert len(calls) == 2
    assert result.route_dp_calls == 0
    assert result.best_evaluation.makespan <= result.search_makespan + 1e-8
    assert result.best_solution.routes == result.selected_search_routes
    assert result.total_runtime_seconds >= result.runtime_seconds + result.final_recheck_seconds - 1e-8


def test_expired_insertion_starts_no_route_evaluation(monkeypatch):
    env = SearchEnvironment(load_instance(ROOT/'data/R2_T10_0.txt'), SearchConfig(max_time=10))
    monkeypatch.setattr(env, 'elapsed', lambda: 11)
    before = env.dp.statistics()['calls']
    with pytest.raises(SearchDeadline):
        env.insert(env.initial.solution, 1)
    assert env.dp.statistics()['calls'] == before


@pytest.mark.parametrize('module', ['cdabc','rnsga','sga_ts','mrhdabc'])
def test_tiny_budget_still_returns_complete_bootstrap_incumbent(module):
    result = import_module('mrta_rect_coverage.comparison_algorithms.'+module).solve(
        load_instance(ROOT/'data/R2_T10_0.txt'), SearchConfig(max_time=1e-9))
    assert sorted(t for r in result.best_solution.routes for t in r) == list(range(1,11))
    assert result.evaluations == 1
    assert result.deadline_reached
