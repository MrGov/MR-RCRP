from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import random

import pytest

from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.heuristics.alns_solver import ALNSConfig, ALNSSolver
from mrta_rect_coverage.heuristics.bounded_repair_search import (
    BoundedRepairSearch, SearchBudget, StrategyExecutor, reference_rank_pairs, validate_pair_ids,
)

ROOT = Path(__file__).resolve().parents[1]


def solver():
    return ALNSSolver(load_instance(ROOT / 'data/structural_benchmark_v1/development/SPATIAL/R2_T20_0.txt'),
                      config=ALNSConfig.enhanced(iterations=8, random_seed=23,
                                                operator_minimum_uses=1, capture_operator_states=True))


def state(s):
    ids = [t.task_id for t in s.instance.tasks]
    return MultiRobotSolution([ids[4::2], ids[5::2]]), ids[:4]


def test_joint_routes_exact_and_inputs_unchanged():
    s = solver()
    partial, removed = state(s)
    before = deepcopy((partial, removed))
    kernel = BoundedRepairSearch(s)
    result = kernel(partial, removed, s.solution_evaluator.evaluate_partial(partial))
    assert (partial, removed) == before
    assert s._is_valid_full_solution(result)
    record = kernel.records[-1]
    assert record['price_requests'] <= kernel.budget.max_prices
    assert record['expansions'] <= kernel.budget.max_expansions
    assert len(record['selected_pairs']) == 2
    assert record['joint_branches']
    for branch in record['joint_branches']:
        costs = [s.route_dp.evaluate_route(r).total_cost for r in branch['routes']]
        assert branch['costs'] == pytest.approx(costs)
    assert any(len(set(b['robots'])) == 2 for b in record['joint_branches'])
    assert record['pricing_work']['insertion_requests'] == record['price_requests']


@pytest.mark.parametrize('prices,expansions', [(100,36),(400,36),(4096,18),(4096,0)])
def test_actual_caps_not_just_declared(prices, expansions):
    s = solver()
    partial, removed = state(s)
    kernel = BoundedRepairSearch(s,budget=SearchBudget(max_prices=prices,max_expansions=expansions))
    result = kernel(partial,removed,s.solution_evaluator.evaluate_partial(partial))
    r = kernel.records[-1]
    assert r['price_requests'] <= prices
    assert r['pricing_work']['insertion_requests'] == r['price_requests']
    assert r['expansions'] <= expansions
    assert s._is_valid_full_solution(result)


def test_invalid_coverage_and_insufficient_completion_budget():
    s = solver()
    partial, removed = state(s)
    with pytest.raises(ValueError,match='coverage'):
        BoundedRepairSearch(s)(partial,removed+removed[:1],None)
    with pytest.raises(ValueError,match='cannot fund'):
        BoundedRepairSearch(s,budget=SearchBudget(max_prices=1))(partial,removed,None)


@pytest.mark.parametrize('output', [['a','a'], ['a'], ['a','b','c'], [1,2], ('a','b')])
def test_exact_output_contract(output):
    with pytest.raises(ValueError,match='identifiers'):
        validate_pair_ids(output,{'pairs':[{'id':'a'},{'id':'b'}]})


def test_budget_exhaustion_preserves_feasible_incumbent():
    s = solver()
    partial, removed = state(s)
    # Greedy requires 18+19+20+21 = 78 price requests, leaving none for lookahead.
    kernel = BoundedRepairSearch(s, budget=SearchBudget(max_prices=78, max_expansions=0))
    result = kernel(partial, removed, s.solution_evaluator.evaluate_partial(partial))
    assert s._is_valid_full_solution(result)
    assert kernel.records[-1]['price_requests'] == 78
    assert kernel.records[-1]['expansions'] == 0
    assert kernel.records[-1]['budget_stop']


def test_policy_decision_changes_expanded_pairs():
    s = solver()
    partial, removed = state(s)
    left = BoundedRepairSearch(s, ranker=reference_rank_pairs)
    right = BoundedRepairSearch(s, ranker=lambda f, rng: list(reversed(reference_rank_pairs(f, rng))))
    for kernel in (left, right):
        kernel(partial, removed, s.solution_evaluator.evaluate_partial(partial))
    assert left.records[-1]['selected_pairs'] != right.records[-1]['selected_pairs']


def test_invalid_strategy_ids_fail_closed_and_close_worker(tmp_path):
    source = tmp_path / 'bad.py'
    source.write_text('def rank_pairs(features, rng):\n    return ["unknown"]\n')
    with StrategyExecutor(source) as policy:
        with pytest.raises(ValueError, match='identifiers'):
            policy({'pairs': [{'id': 'a'}]}, random.Random(1))
        assert policy.backend._process is None


def test_strategy_isolation_hash_timeout_and_alns(tmp_path):
    source = tmp_path / 'policy.py'
    source.write_text('counter = 0\ndef rank_pairs(features, rng):\n    global counter\n    counter += 1\n    ids = [p["id"] for p in features["pairs"]]\n    features["pairs"].clear()\n    return ids if counter == 1 else []\n')
    f = {'pairs': [{'id': 'a'}, {'id': 'b'}]}
    with StrategyExecutor(source) as policy:
        assert policy(f, random.Random(1)) == ['a', 'b']
        assert policy(f, random.Random(1)) == ['a', 'b']
        assert len(f['pairs']) == 2
        s = solver()
        kernel = BoundedRepairSearch(s, ranker=policy)
        s.register_bounded_repair(kernel, name='bounded')
        result = s.solve()
        assert result.operator_usage_stats['repair']['bounded'].uses > 0
        assert len(kernel.records) > 0
        assert len(policy.samples) > 2
        source.write_text(source.read_text() + '\n# changed\n')
        with pytest.raises(RuntimeError, match='hash'):
            policy(f, random.Random(1))
    assert policy.backend._process is None
    source.write_text('def rank_pairs(features, rng):\n    while True: pass\n')
    with StrategyExecutor(source, timeout_ms=25) as policy:
        with pytest.raises(RuntimeError, match='timeout'):
            policy(f, random.Random(1))
        assert policy.backend._process is None


def test_runtime_exception_closes_worker(tmp_path):
    source=tmp_path/'raises.py'
    source.write_text('def rank_pairs(features, rng):\n    raise ValueError("test")\n')
    with StrategyExecutor(source) as policy:
        with pytest.raises(RuntimeError,match='runtime_error'):
            policy({'pairs':[]},random.Random(1))
        assert policy.backend._process is None


@pytest.mark.parametrize('prefix', [
    'from mrta_rect_coverage.core.dp_evaluator import RouteDPEvaluator\n',
    'import random\n', 'import math\nmath.pi = 1\n', 'import os\n'])
def test_strategy_cannot_acquire_solver_or_mutate_imported_modules(tmp_path,prefix):
    source=tmp_path/'unsafe.py'
    source.write_text(prefix+'def rank_pairs(features, rng):\n    return []\n')
    with pytest.raises(ValueError):
        StrategyExecutor(source)


def test_reference_and_policy_have_identical_kernel_capabilities(tmp_path):
    import inspect
    source=tmp_path/'reference.py'
    source.write_text(inspect.getsource(reference_rank_pairs).replace('reference_rank_pairs','rank_pairs'))
    outputs=[]
    for mode in ('native','original','warm'):
        s=solver()
        partial,removed=state(s)
        policy=StrategyExecutor(source,executor=mode) if mode!='native' else None
        try:
            kernel=BoundedRepairSearch(s,ranker=policy or reference_rank_pairs)
            result=kernel(partial,removed,s.solution_evaluator.evaluate_partial(partial))
            record=kernel.records[-1]
            outputs.append((result.routes,{k:record[k] for k in ('features','selected_pairs','joint_branches','price_requests','expansions','dp_work')},
                            {k:v for k,v in record['pricing_work'].items() if not k.endswith('_seconds')}))
        finally:
            if policy:
                policy.close()
    assert outputs[0]==outputs[1]==outputs[2]
