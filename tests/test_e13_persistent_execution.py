import hashlib
from pathlib import Path
import random

from mrta_rect_coverage.llm.operator_evolution.candidate_execution import CandidateProxy
from mrta_rect_coverage.llm.operator_evolution.persistent_candidate_execution import PersistentCandidateProxy
from mrta_rect_coverage.llm.operator_evolution.protocols import RepairContext, DestroyContext
from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.core.models import MultiRobotSolution

ROOT = Path(__file__).resolve().parents[1]


def test_frozen_candidates_match_original_and_reuse_process():
    from mrta_rect_coverage.experiments.e11_structural_benchmark import identities
    instance=load_instance(ROOT/'data/R2_T10_0.txt')
    ids=identities()
    for kind,key in [('destroy','destroy'),('repair','aux')]:
        identity=ids[key]
        original=CandidateProxy(Path(identity['source_path']),kind,identity['source_hash'])
        warm=PersistentCandidateProxy.from_validated(original)
        def args():
            if kind=='destroy':
                return (MultiRobotSolution([list(range(1,6)),list(range(6,11))]),
                    DestroyContext(instance,[1000.,900.],1000.,3),random.Random(1))
            return (MultiRobotSolution([[1,2,3,4],[6,7,8]]),[5,9,10],
                RepairContext(instance,[500.,600.],600.,1),random.Random(1))
        try:
            a=original.execute(args(),timeout_ms=1000)
            b=warm.execute(args(),timeout_ms=1000)
            c=warm.execute(args(),timeout_ms=1000)
            assert a.status==b.status==c.status=='success'
            assert a.result==b.result==c.result
            assert warm.process_starts==1
        finally:warm.close()
        assert warm._process is None


def write_proxy(tmp_path,body):
    source='from mrta_rect_coverage.llm.operator_evolution.protocols import RepairResult\n'+body
    path=tmp_path/'candidate.py';path.write_text(source,encoding='utf-8')
    return PersistentCandidateProxy(path,'repair',hashlib.sha256(source.encode()).hexdigest())


def test_namespace_reset_hash_check_timeout_and_recovery(tmp_path):
    proxy=write_proxy(tmp_path,'counter = []\ndef repair(partial_solution, unassigned_tasks, context, rng):\n    counter.append(1)\n    if len(counter)>1:\n        raise ValueError("leaked namespace")\n    if unassigned_tasks:\n        while True:\n            pass\n    return RepairResult(solution=partial_solution)\n')
    args=(MultiRobotSolution([[],[]]),[],None,random.Random(0))
    try:
        assert proxy.execute(args,timeout_ms=1000).status=='success'
        assert proxy.execute(args,timeout_ms=1000).status=='success'
        assert proxy.execute((args[0],[1],None,args[3]),timeout_ms=30).status=='timeout'
        assert proxy._process is None
        assert proxy.execute(args,timeout_ms=1000).status=='success'
        assert proxy.process_starts==2
        proxy.path.write_text(proxy.path.read_text()+'\n# changed',encoding='utf-8')
        assert proxy.execute(args,timeout_ms=1000).status=='source_hash_mismatch'
        assert proxy._process is None
    finally:proxy.close()


def test_vnext_same_pools_config_and_fixed_iteration_joint_results():
    from dataclasses import asdict
    from mrta_rect_coverage.experiments.e11_structural_benchmark import make_solver
    from mrta_rect_coverage.experiments.e13_evaluation_efficiency import make_vnext
    from mrta_rect_coverage.experiments.e5_destroy_repair import D_NAME
    from mrta_rect_coverage.experiments.e8_repair_portfolio import AUX_NAME
    instance=load_instance(ROOT/'data/R2_T10_0.txt')
    original=make_solver(instance,0,'AUX')
    warm,proxies=make_vnext(instance,0)
    try:
        assert asdict(original.config)==asdict(warm.config)
        assert list(original.destroy_ops)==list(warm.destroy_ops)
        assert list(original.repair_ops)==list(warm.repair_ops)
        assert original.initial_solution==warm.initial_solution
        results=[]
        for solver in (original,warm):
            solver.config.iterations=4;solver.config.max_runtime_seconds=None
            solver._select_operators=lambda context:(D_NAME,AUX_NAME,'joint_test')
            results.append(solver.solve())
        a,b=results
        assert a.best_solution==b.best_solution
        assert a.best_evaluation==b.best_evaluation
        assert not a.fallback_events and not b.fallback_events
        assert all(p.process_starts==1 for p in proxies)
        assert sum(r['calls'] for group in b.generated_operator_execution.values() for r in group.values())==8
    finally:
        for p in proxies:p.close()


def test_timeout_retains_alns_feasibility_fallback(tmp_path):
    from mrta_rect_coverage.heuristics.alns_solver import ALNSSolver, ALNSConfig
    instance=load_instance(ROOT/'data/R2_T10_0.txt')
    proxy=write_proxy(tmp_path,'def repair(partial_solution, unassigned_tasks, context, rng):\n    while True:\n        pass\n')
    proxy.timeout_ms=20
    solver=ALNSSolver(instance,constructor='spatial_sort',config=ALNSConfig.enhanced(iterations=1,random_seed=0))
    solver.register_development_repair(proxy,name='timeout_repair')
    solver._select_operators=lambda context:('random_destroy','timeout_repair','timeout_test')
    try:
        result=solver.solve()
        assert len(result.fallback_events)==1
        assert sorted(t for r in result.best_solution.routes for t in r)==list(range(1,11))
        assert solver.solution_evaluator.evaluate(result.best_solution)==result.best_evaluation
    finally:proxy.close()
