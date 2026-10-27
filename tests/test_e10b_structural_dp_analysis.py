import json

import pytest

from mrta_rect_coverage.core.models import MultiRobotSolution


def test_manifest_qualified_ids_and_common_parent_routes():
    from mrta_rect_coverage.experiments.e10b_structural_dp_analysis import entries, load, parent_routes
    rows=entries()
    assert len(rows)==21 and len({r['instance_id'] for r in rows})==21
    for rep in range(3):
        same=[e for e in rows if e['replicate_id']==rep]
        assert all(parent_routes(e)==parent_routes(same[0]) for e in same)
        for e in same:
            assert load(e).name==e['instance_id']
            assert sorted(t for r in parent_routes(e) for t in r)==list(range(1,41))


def test_snapshot_retains_real_state_chain_and_exact_cost_identity():
    from mrta_rect_coverage.experiments.e10b_structural_dp_analysis import entries, load, parent_routes, evaluator_for, snapshot
    e=entries()[3];instance=load(e);solution=MultiRobotSolution(parent_routes(e))
    evaluation=evaluator_for(instance).evaluate(solution)
    s=snapshot(instance,solution,evaluation)
    assert len(s['states'])==40
    assert sum(r['total_cost'] for r in s['routes'])==pytest.approx(sum(evaluation.per_robot_costs))
    assert s['objective']['travel_time']+s['objective']['coverage_traversal_time']+s['objective']['turning_time']==pytest.approx(sum(evaluation.per_robot_costs))
    assert s['critical_route']['total_cost']==evaluation.makespan
    assert all(set(('mode','entry','exit','sweeps'))<=set(x) for x in s['states'])
    assert json.loads(json.dumps(s))==s


def test_paired_summary_uses_matching_identity_and_rejects_missing_pair():
    from mrta_rect_coverage.experiments.e10b_structural_dp_analysis import paired_summary
    rows=[dict(method=m,instance_id=i,makespan=cost,seed=0) for i,a,b in [('a',100,90),('b',200,220)] for m,cost in [('V1',a),('AUX',b)]]
    s=paired_summary(rows)
    assert s['paired_improvement_pct']==pytest.approx(0.)
    assert s['wtl']==[1,0,1]
    with pytest.raises(ValueError):paired_summary(rows[:-1])
