import pytest


def test_manifest_identity_and_test_boundary():
    from mrta_rect_coverage.experiments.e11_structural_benchmark import catalog, load_entry
    rows=catalog()['entries']
    assert len(rows)==336 and len({r['instance_id'] for r in rows})==336
    assert len({r['path'] for r in rows})==336
    a=next(r for r in rows if r['instance_id']=='development/BASE/R2_T10_0')
    b=next(r for r in rows if r['instance_id']=='development/HV-GEOM/R2_T10_0')
    assert load_entry(a).name!=load_entry(b).name
    with pytest.raises(ValueError,match='test'):
        load_entry(next(r for r in rows if r['split']=='test'))


def test_fixed_sample_and_equal_budget_pools():
    from mrta_rect_coverage.experiments.e11_structural_benchmark import sample, make_solver, load_entry
    rows=sample('development')
    assert len(rows)==7 and len({r['scenario'] for r in rows})==7
    assert len({(r['n_robots'],r['n_tasks']) for r in rows})==6
    assert len(sample('validation'))==3
    with pytest.raises(ValueError):sample('test')
    e=rows[0];solvers=[make_solver(load_entry(e),0,m) for m in ('B1','V1','AUX')]
    assert all(s.config.max_runtime_seconds==e['n_tasks'] for s in solvers)
    assert all(s.initial_solution.routes==solvers[0].initial_solution.routes for s in solvers)
    assert [(len(s.destroy_ops),len(s.repair_ops)) for s in solvers]==[(3,3),(4,4),(4,4)]


def test_paired_gains_do_not_use_ratio_of_means():
    from mrta_rect_coverage.experiments.e11_structural_benchmark import comparison
    rows=[dict(instance_id=i,seed=0,method=m,makespan=c) for i,a,b in [('a',100,90),('b',200,220)]
          for m,c in [('V1',a),('AUX',b)]]
    assert comparison(rows,'AUX','V1')['paired_improvement_pct']==pytest.approx(0)
    with pytest.raises(ValueError):comparison(rows[:-1],'AUX','V1')
