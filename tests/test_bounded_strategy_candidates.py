"""Focused equivalence of THIS batch's real policy sources when artifacts exist."""
from copy import deepcopy
import json
from pathlib import Path
import random

import pytest

from mrta_rect_coverage.experiments.bounded_repair_strategy import make_solver
from mrta_rect_coverage.heuristics.bounded_repair_search import BoundedRepairSearch, StrategyExecutor

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/bounded_repair_search/run_001'


@pytest.mark.parametrize('generation',[1,2])
def test_actual_generated_strategies_equivalent_and_isolated(generation):
    path=OUT/f'request_{generation:02d}/candidate.py'
    if not path.exists():
        pytest.skip('local real-call batch not present')
    record=json.loads((OUT/'paired_reference.json').read_text(encoding='utf-8'))
    frames=[record['cases'][i]['kernel']['features'] for i in (6,9,6)]
    expected_hash=json.loads((path.parent/'lineage.json').read_text(encoding='utf-8'))['hash']
    outcomes=[]
    for mode in ('original','warm'):
        with StrategyExecutor(path,expected_hash=expected_hash,executor=mode) as policy:
            before=deepcopy(frames)
            rng=random.Random(23)
            state=rng.getstate()
            results=[policy(f,rng) for f in frames]
            assert frames==before
            assert rng.getstate()==state
            assert results[0]==results[2]
            outcomes.append(results)
        if mode=='warm':
            assert policy.backend._process is None
    assert outcomes[0]==outcomes[1]


@pytest.mark.parametrize('generation',[1,2])
def test_actual_policies_in_fixed_alns_match_across_executor(generation):
    path=OUT/f'request_{generation:02d}/candidate.py'
    if not path.exists():
        pytest.skip('local real-call batch not present')
    entry=next(e for e in json.loads((OUT/'entries.json').read_text()) if 'SPATIAL' in e['instance_id'])
    outputs=[]
    for mode in ('original','warm'):
        s=make_solver(entry,seed=23,iterations=16,max_runtime_seconds=None)
        with StrategyExecutor(path,executor=mode) as policy:
            kernel=BoundedRepairSearch(s,ranker=policy)
            s.register_bounded_repair(kernel,name='policy')
            r=s.solve()
        assert policy.samples and not any(x['strategy_error'] for x in kernel.records)
        keys=('destroy','repair','accepted','candidate_delta','best_makespan','repaired_routes','refined_routes')
        outputs.append((r.best_solution.routes,
                        [tuple(h.get(k) for k in keys) for h in r.iteration_history],
                        [x['selected_pairs'] for x in kernel.records],
                        {k:v for k,v in s.insertion_pricer.statistics().items() if not k.endswith('_seconds')},
                        {k:v for k,v in s.route_dp.statistics().items() if k!='compute_time_sec'}))
    assert outputs[0]==outputs[1]
