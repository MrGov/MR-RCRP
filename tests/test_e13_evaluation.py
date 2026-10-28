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
def test_greedy_never_constructs_or_calls_exact_even_at_finish(module, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Greedy must not construct or call Exact-DP')
    monkeypatch.setattr(RouteDPEvaluator, '__init__', forbidden)
    monkeypatch.setattr(RouteDPEvaluator, 'evaluate_route', forbidden)
    result = import_module('mrta_rect_coverage.comparison_algorithms.'+module).solve(
        load_instance(ROOT/'data/R2_T10_0.txt'),
        SearchConfig(max_time=10, max_generations=2, population_size=4, evaluation_mode='greedy'))
    assert result.route_dp_calls == result.final_route_dp_calls == result.cache_misses == 0
    assert result.final_recheck_seconds == 0
    assert result.final_validation_seconds >= 0
    assert result.best_evaluation.makespan == result.search_makespan
    assert result.best_solution.routes == result.selected_search_routes
    assert result.total_runtime_seconds >= result.runtime_seconds + result.final_recheck_seconds - 1e-8


def test_greedy_finish_retains_same_evaluation_and_checks_costs_without_reselection(monkeypatch):
    from copy import deepcopy
    from mrta_rect_coverage.comparison_algorithms.common import validate_selected_evaluation
    instance=load_instance(ROOT/'data/R2_T10_0.txt')
    env=SearchEnvironment(instance,SearchConfig(max_time=10,evaluation_mode='greedy'))
    before=deepcopy(env.best)
    def forbidden(*args):raise AssertionError('finish must not reselect even Greedy states')
    monkeypatch.setattr(env.greedy,'evaluate_route',forbidden)
    result=env.finish(0)
    assert env.dp is None
    assert result.best_evaluation is env.best.evaluation
    assert env.best==before
    evidence=validate_selected_evaluation(instance,result.best_solution,result.best_evaluation,env.states,env.costs)
    assert max(r['route_cost'] for r in evidence)==result.best_evaluation.makespan
    for route in evidence:
        assert route['route_cost']==pytest.approx(route['travel_cost']+route['coverage_cost']+route['turning_cost'])
        assert all('entry_corner' in s and 'exit_corner' in s and 'sweep_mode' in s for s in route['states'])
    changed=deepcopy(result.best_evaluation)
    changed.route_evaluations[0].total_cost+=1
    with pytest.raises(ValueError):
        validate_selected_evaluation(instance,result.best_solution,changed,env.states,env.costs)


@pytest.mark.parametrize('defect',['duplicate','missing','corner','return','makespan'])
def test_fixed_chain_validation_rejects_invalid_saved_results(defect):
    from copy import deepcopy
    from mrta_rect_coverage.comparison_algorithms.common import validate_selected_evaluation
    instance=load_instance(ROOT/'data/R2_T10_0.txt')
    env=SearchEnvironment(instance,SearchConfig(max_time=10,evaluation_mode='greedy'))
    solution=deepcopy(env.best.solution);evaluation=deepcopy(env.best.evaluation)
    if defect=='duplicate':solution.routes[0].append(solution.routes[0][0])
    elif defect=='missing':solution.routes[0].pop()
    elif defect=='corner':evaluation.route_evaluations[0].chosen_states[0].exit_point=(999,999)
    elif defect=='return':evaluation.route_evaluations[0].transition_costs[-1]+=10
    elif defect=='makespan':evaluation.makespan+=1
    with pytest.raises(ValueError):
        validate_selected_evaluation(instance,solution,evaluation,env.states,env.costs)


@pytest.mark.parametrize('base',['CDABC','RNSGA','SGA-TS','MRHDABC'])
def test_runner_and_saved_record_validation_are_fully_greedy(base,monkeypatch):
    import json
    from copy import deepcopy
    from mrta_rect_coverage.experiments import e13_evaluation_efficiency as runner
    def forbidden(*args,**kwargs):raise AssertionError('No DP allowed in Greedy solve or analysis')
    monkeypatch.setattr(RouteDPEvaluator,'__init__',forbidden)
    monkeypatch.setattr(RouteDPEvaluator,'evaluate_route',forbidden)
    entry=runner.entries()[0]
    record=runner.solve_one(entry,0,base+'-Greedy',budget_seconds=.05)
    record=json.loads(json.dumps(record))
    before=deepcopy(record)
    evidence=runner.validate_record(runner.load_entry(entry),record)
    assert record==before
    assert record['result']['makespan']==max(r['route_cost'] for r in evidence)
    assert record['final_evaluation_kind']=='greedy_selected_states'
    assert record['result']['final_route_dp_calls']==0


@pytest.mark.parametrize('mode',['exact','greedy'])
def test_expired_budget_returns_unchanged_complete_result_in_both_modes(mode):
    from mrta_rect_coverage.comparison_algorithms.common import validate_selected_evaluation
    instance=load_instance(ROOT/'data/R2_T10_0.txt')
    result=import_module('mrta_rect_coverage.comparison_algorithms.rnsga').solve(instance,SearchConfig(max_time=1e-9,evaluation_mode=mode))
    validate_selected_evaluation(instance,result.best_solution,result.best_evaluation)
    assert result.deadline_reached and result.evaluations==1


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
