from copy import deepcopy

from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.experiments.e3_alns import ROOT
from mrta_rect_coverage.experiments.e5_destroy_repair import read


def test_pool_deduplicates_sources_and_checks_raw_generation_provenance():
    from mrta_rect_coverage.experiments.e8_repair_portfolio import discover_candidates
    pool = discover_candidates()
    assert len(pool) == len({c['source_hash'] for c in pool})
    assert all(c['raw_response_sources'] and c['aliases'] for c in pool)
    assert {'E2-R/F1','E2-R/F2','E4-A/F2-D','E4-B/F2-G','E7'} <= {a for c in pool for a in c['aliases']}
    parent = read(ROOT/'outputs/e5_llm_destroy_repair/selected_operators.json')['repair']
    assert sum(c['source_hash']==parent['source_hash'] for c in pool) == 1


def test_structural_labels_depend_on_geometry_not_performance():
    from mrta_rect_coverage.experiments.e8_repair_portfolio import structure_features
    instance = load_instance(ROOT/'data/R2_T20_3.txt')
    result = structure_features(instance)
    assert result['tasks_per_robot'] == 10
    assert result['scale'] == 'small'
    assert result['mean_H_sweeps'] > 0 and result['mean_V_sweeps'] > 0
    assert result['mean_pair_manhattan'] > 0
    assert result == structure_features(deepcopy(instance))


def test_fixed_slot_pools_share_v1_controls_and_execute_both_repairs():
    from mrta_rect_coverage.experiments.e8_repair_portfolio import portfolio_solver, AUX_NAME, REPLACE_SLOT
    from mrta_rect_coverage.experiments.e6_pair_selection import make_solver
    from mrta_rect_coverage.experiments.e5_destroy_repair import D_NAME, R_NAME
    selected = read(ROOT/'outputs/e5_llm_destroy_repair/selected_operators.json')
    aux = read(ROOT/'outputs/e7_cooperative_evolution/generated_candidates.json')[0]
    instance = load_instance(ROOT/'data/R2_T10_0.txt')
    original = make_solver(instance,0,selected,'V1',iterations=2)
    solvers = {m: portfolio_solver(instance,0,selected,aux,m,iterations=2) for m in ('V1','AUX','PORT')}
    assert solvers['V1'].config == original.config
    assert list(solvers['V1'].repair_ops) == list(original.repair_ops)
    for solver in solvers.values():
        assert solver.initial_solution == original.initial_solution
        assert len(solver.destroy_ops) == len(solver.repair_ops) == 4
        assert solver.config == original.config
        assert set(solver.repair_ops)==set(solver.repair_weights)==set(solver.operator_stats['repair'])==set(solver.segment_stats['repair'])
    assert REPLACE_SLOT not in solvers['PORT'].repair_ops
    assert R_NAME in solvers['PORT'].repair_ops and AUX_NAME in solvers['PORT'].repair_ops
    expected_order=[AUX_NAME if n==REPLACE_SLOT else n for n in original.repair_ops]
    assert list(solvers['PORT'].repair_ops)==expected_order
    assert R_NAME not in solvers['AUX'].repair_ops
    assert AUX_NAME in solvers['AUX'].repair_ops and REPLACE_SLOT in solvers['AUX'].repair_ops
    port=solvers['PORT']
    names=iter([R_NAME,AUX_NAME])
    port._select_operators=lambda context:(D_NAME,next(names),'test_portfolio')
    result=port.solve()
    assert not result.fallback_events
    assert port.solution_evaluator.evaluate(result.best_solution).makespan==result.best_evaluation.makespan
    assert all(h['llm_operator_success'] for h in result.iteration_history)


def test_complementarity_requires_reliable_crossovers_not_top_average():
    from mrta_rect_coverage.experiments.e8_repair_portfolio import complementarity
    base=[]
    child=[]
    for name,parent_makespan,cost in [('a',90,98),('b',110,95),('c',100,105)]:
        for seed in (0,1):
            base.append(dict(input_id=f'{name}/manual_B1_100_iterations/{seed}',instance_id=name,solver_seed=seed,
                feasible=True,parent_makespan=parent_makespan,candidate_makespan=100,repair_runtime_ms=2))
            child.append(dict(base[-1],candidate_makespan=cost,repair_runtime_ms=4))
    p=dict(trials=base,feasible_count=6,executed_count=6,avg_runtime_ms=2)
    c=dict(trials=child,feasible_count=6,executed_count=6,avg_runtime_ms=4)
    result=complementarity(p,c)
    assert result['eligible'] and result['weak_case_improvement_pct'] > 0
    bad=deepcopy(c);bad['trials'][0]['feasible']=False
    assert not complementarity(p,bad)['eligible']
    expensive=deepcopy(c);expensive['avg_runtime_ms']=101
    assert not complementarity(p,expensive)['eligible']
    one_case=deepcopy(c)
    for t in one_case['trials']:
        if t['instance_id']=='a':t['candidate_makespan']=100
    assert not complementarity(p,one_case)['eligible']


def test_usage_does_not_credit_fallback_or_call_local_search_causal_repair_gain():
    from mrta_rect_coverage.experiments.e8_repair_portfolio import repair_usage
    history=[dict(repair='aux',accepted=True,best_makespan=90,fallback_used=False),
             dict(repair='aux',accepted=True,best_makespan=80,fallback_used=True),
             dict(repair='main',accepted=False,best_makespan=80,fallback_used=False)]
    stats=repair_usage(history,100)
    assert stats['aux']==dict(uses=2,no_fallback_uses=1,accepted=1,global_best=1,fallback_affected_uses=1)
    assert stats['main']['accepted']==stats['main']['global_best']==0
