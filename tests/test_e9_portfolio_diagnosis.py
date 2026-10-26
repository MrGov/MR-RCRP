from dataclasses import asdict

from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.experiments.e3_alns import ROOT
from mrta_rect_coverage.experiments.e5_destroy_repair import read, D_NAME, R_NAME
from mrta_rect_coverage.experiments.e8_repair_portfolio import AUX_NAME, REPLACE_SLOT


def test_port_all_preserves_all_manual_slots_and_executes_frozen_repairs():
    from mrta_rect_coverage.experiments.e9_portfolio_diagnosis import version_solver
    from mrta_rect_coverage.experiments.e6_pair_selection import make_solver
    decision=read(ROOT/'outputs/e8_repair_portfolio/selection_decision.json')
    instance=load_instance(ROOT/'data/R2_T10_0.txt')
    selected=dict(destroy=decision['destroy'],repair=decision['main'])
    original=make_solver(instance,0,selected,'V1',iterations=2)
    all_solver=version_solver(instance,0,decision,'PORT-ALL',iterations=2)
    assert asdict(all_solver.config)==asdict(original.config)
    assert all_solver.initial_solution==original.initial_solution
    assert list(all_solver.destroy_ops)==list(original.destroy_ops)
    assert list(all_solver.repair_ops)==list(original.repair_ops)+[AUX_NAME]
    assert REPLACE_SLOT in all_solver.repair_ops
    for group in (all_solver.repair_weights,all_solver.operator_stats['repair'],all_solver.segment_stats['repair']):
        assert set(group)==set(all_solver.repair_ops)
    repairs=iter([R_NAME,AUX_NAME])
    all_solver._select_operators=lambda context:(D_NAME,next(repairs),'integration_test')
    result=all_solver.solve()
    assert not result.fallback_events
    assert all(h['llm_operator_success'] for h in result.iteration_history)
    assert all_solver.solution_evaluator.evaluate(result.best_solution).makespan==result.best_evaluation.makespan
    for version in ('V1','V2','AUX','PORT'):
        solver=version_solver(instance,0,decision,version,iterations=2)
        assert len(solver.destroy_ops)==len(solver.repair_ops)==4
        assert solver.config.pair_selection_mode==('coupled' if version=='V2' else 'independent')


def test_stage_diagnosis_carries_best_at_wall_time_without_future_leakage():
    from mrta_rect_coverage.experiments.e9_portfolio_diagnosis import stage_rows
    saved=dict(result=dict(method='V1',instance='test',seed=0,budget_seconds=10,initial_makespan=100),
        history=[dict(elapsed_seconds=3,best_makespan=80,repair='a',accepted=True,fallback_used=False),
                 dict(elapsed_seconds=11,best_makespan=70,repair='b',accepted=True,fallback_used=False)])
    rows=stage_rows(saved)
    assert [r['best_makespan'] for r in rows]==[100,80,80,80]
    assert [r['iterations_by_checkpoint'] for r in rows]==[0,1,1,1]
    assert rows[-1]['budget_fraction']==1


def test_execution_diagnosis_separates_bounded_wall_from_run_request():
    from mrta_rect_coverage.experiments.e9_portfolio_diagnosis import execution_rows
    saved=dict(result=dict(method='PORT',instance='x',seed=1),generated_operator_execution=dict(
        repair={'aux':dict(calls=2,successes=2,failures=0,wall_time_seconds=.5,run_request_seconds=.04)}))
    row=execution_rows(saved)[0]
    assert row['mean_bounded_wall_ms']==250
    assert row['mean_run_request_ms']==20
    assert row['outside_run_request_seconds']==.46
