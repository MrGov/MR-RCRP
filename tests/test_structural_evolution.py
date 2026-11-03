from pathlib import Path
import random
import pytest

from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.heuristics.alns_solver import ALNSConfig
from mrta_rect_coverage.heuristics.structural_search import (
    PairPortfolioSolver, StructuralKernel, StructuralExecutor, reference_step,
    validate_actions, MANUAL_PAIRS,
)
from mrta_rect_coverage.llm.operator_evolution.candidate_security import validate_candidate_source

ROOT = Path(__file__).resolve().parents[1]

def solver(iterations=5):
    return PairPortfolioSolver(load_instance(ROOT/'data/R2_T10_0.txt'),
        config=ALNSConfig.enhanced(iterations=iterations, random_seed=23))

def test_contract_rejects_illegal_and_overwide_actions():
    f = {'phase':'destroy', 'routes':[[1,2],[3]], 'remove_limit':2}
    for bad in ([1,1], [8], [], [1,2,3], [True]):
        with pytest.raises(ValueError):
            validate_actions(bad,f)
    assert validate_actions([1,3],f)==[1,3]
    f = {'phase':'repair','width':1,'branches':[{'options':[{'task':1,'robot':0,'position':0}]}]}
    with pytest.raises(ValueError):
        validate_actions([{'branch':0,'task':1,'robot':1,'position':0}],f)
    f['branches'][0]['options'].append({'task':2,'robot':0,'position':1})
    with pytest.raises(ValueError):
        validate_actions([{'branch':0,'task':1,'robot':0,'position':0},
                          {'branch':0,'task':1,'robot':0,'position':0}],f)

def test_structural_source_retains_security_checks():
    validate_candidate_source('def search_step(features, rng):\n    return []\n','structural')
    with pytest.raises(ValueError):
        validate_candidate_source('import os\ndef search_step(features, rng):\n    return []\n','structural')

def test_joint_kernel_exact_and_feasible():
    s=solver()
    k=StructuralKernel(s,reference_step)
    e=s.solution_evaluator.evaluate(s.initial_solution)
    p,removed=k.destroy(s.initial_solution,e,4)
    result=k.repair(p,removed,s.solution_evaluator.evaluate_partial(p))
    assert s._is_valid_full_solution(result)
    assert k.records[-1]['prices']<=k.price_cap
    assert k.records[-1]['max_live_branches']<=k.width
    assert all(abs(s.route_dp.evaluate_route(r).total_cost-c)<1e-8
               for r,c in zip(result.routes,k.records[-1]['costs']))

def test_only_allowed_pairs_selected_and_credited():
    s=solver(12)
    s.set_pairs(MANUAL_PAIRS[:2])
    r=s.solve()
    assert {(h['destroy'],h['repair']) for h in r.iteration_history}==set(MANUAL_PAIRS[:2])
    assert sum(v['calls'] for v in s.deployment_stats.values())==12
    assert sum(v['reward'] for v in s.deployment_stats.values())==sum(h['score_raw'] for h in r.iteration_history)
    assert all(v.score==0 for records in s.operator_stats.values() for v in records.values())

def test_executor_isolated_timeout_and_cleanup(tmp_path):
    p=tmp_path/'policy.py'
    p.write_text('def search_step(features, rng):\n    return features["routes"][0][:1]\n')
    with StructuralExecutor(p) as ex:
        f={'phase':'destroy','routes':[[1,2]],'remove_limit':1}
        assert ex(f,random.Random(1))==[1]
    assert ex.backend._process is None
    p.write_text('def search_step(features, rng):\n    while True:\n        pass\n')
    with StructuralExecutor(p,timeout_ms=30) as ex:
        with pytest.raises(RuntimeError):
            ex(f,random.Random(1))
    assert ex.backend._process is None

def test_survival_retains_instance_specialist_and_discards_weak(tmp_path):
    from mrta_rect_coverage.experiments.structural_population import Study
    study=object.__new__(Study)
    study.cfg={'population_quality_floor':.05,'population_capacity':10}
    study.entries={'development':[{},{}]}
    study.archive={n:{'id':n,'origin':'llm','valid':True,'group':n} for n in ['elite','specialist','weak']}
    study.groups={'elite':{'score':-.03,'mean_relative':-.03,'relative_by_instance':[-.05,-.01]},
                  'specialist':{'score':0.,'mean_relative':0.,'relative_by_instance':[.04,-.04]},
                  'weak':{'score':.1,'mean_relative':.1,'relative_by_instance':[-.01,.21]}}
    members=study.survivors()
    assert 'elite' in members and 'specialist' in members and 'weak' not in members

def test_crlf_artifact_hash_and_normalized_worker_hash(tmp_path):
    import hashlib
    p=tmp_path/'crlf.py'
    p.write_bytes(b'def search_step(features, rng):\r\n    return [1]\r\n')
    digest=hashlib.sha256(p.read_bytes()).hexdigest()
    with StructuralExecutor(p,expected_hash=digest) as ex:
        assert ex({'phase':'destroy','routes':[[1]],'remove_limit':1},random.Random(2))==[1]
    p.write_bytes(b'def search_step(features, rng):\r\n    return [2]\r\n')
    with pytest.raises(ValueError): StructuralExecutor(p,expected_hash=digest)
