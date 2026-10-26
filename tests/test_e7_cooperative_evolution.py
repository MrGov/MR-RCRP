from pathlib import Path
from types import SimpleNamespace
import hashlib

import pytest

from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import DestroyResult, RepairResult
from mrta_rect_coverage.llm.operator_evolution import evaluator, feedback_builder
from mrta_rect_coverage.llm.prompts import operator_revision
from mrta_rect_coverage.experiments.e1_real_llm_pilot import compute_exact_dp_behavior

ROOT = Path(__file__).resolve().parents[1]


def loaded(fn, kind, code_hash):
    return SimpleNamespace(callable_obj=fn, validation=SimpleNamespace(
        operator_id=kind, code_hash=code_hash, validation_status='valid'))


def test_fixed_destroy_inputs_are_reused_and_repair_mapping_is_measured():
    cases = evaluator.build_destroy_benchmark_cases([ROOT / 'data/R2_T6_0.txt'])
    destroyed, received = [], []
    def destroy(solution, context, rng):
        task = solution.routes[0][0]
        destroyed.append(task)
        return DestroyResult(MultiRobotSolution([[t for t in r if t != task] for r in solution.routes]), [task])
    def repair(partial, removed, context, rng):
        received.append((tuple(tuple(r) for r in partial.routes), tuple(removed)))
        routes = [list(r) for r in partial.routes]
        routes[1].extend(removed)
        return RepairResult(MultiRobotSolution(routes))
    inputs = evaluator.prepare_paired_repair_cases(cases, fixed_destroy=loaded(destroy, 'd', 'dh'),
                                                   seeds=[0, 1], timeout_ms=2000)
    rows = evaluator.evaluate_paired_repair_candidates(
        [loaded(repair, 'r1', 'r1h'), loaded(repair, 'r2', 'r2h')], inputs,
        timeout_ms=2000, behavior_callback=compute_exact_dp_behavior)
    assert len(destroyed) == 2
    assert received[:2] == received[2:]
    assert [r['feasible_count'] for r in rows] == [2, 2]
    trial = rows[0]['trials'][0]
    assert trial['removed_task_moves'][0]['origin_robot'] == 0
    assert trial['removed_task_moves'][0]['destination_robot'] == 1
    assert trial['removed_task_moves'][0]['destination_position'] == len(trial['candidate_routes'][1]) - 1
    assert trial['fixed_destroy_hash'] == 'dh'
    assert trial['parent_to_candidate_behavior']['bottleneck_relief'] == trial['parent_makespan'] - trial['candidate_makespan']
    # Same repair compared against its persisted result must have zero DP changes.
    again = evaluator.evaluate_paired_repair_candidates([loaded(repair, 'r', 'rh')], inputs,
        timeout_ms=2000, behavior_callback=compute_exact_dp_behavior, reference_trials=rows[0]['trials'])[0]
    assert all(t['relative_improvement'] == 0 and t['exact_dp_behavior']['travel_change'] == 0 for t in again['trials'])
    missing = evaluator.evaluate_paired_repair_candidates([loaded(repair, 'r', 'rh')], inputs, timeout_ms=2000)[0]
    assert missing['trials'][0]['exact_dp_behavior'] == 'unavailable'


def test_pair_feedback_and_prompt_keep_real_evidence_and_parent_identity(tmp_path):
    source = 'def repair(partial_solution, unassigned_tasks, context, rng):\n    pass\n'
    path = tmp_path / 'r.py'; path.write_text(source)
    parent = dict(operator_id='r', source_path=str(path), source_hash=hashlib.sha256(source.encode()).hexdigest())
    trials = [dict(input_id='real/optimized/0', instance_id='real', solver_seed=0, feasible=True,
        parent_makespan=100, candidate_makespan=110, relative_improvement=-.1,
        parent_route_costs=[100, 90], candidate_route_costs=[80, 110],
        bottleneck_before=[0], bottleneck_after=[1], removed_tasks=[7],
        removed_task_moves=[dict(task_id=7, origin_robot=0, destination_robot=1)],
        parent_routes=[[7], [8]], partial_routes=[[], [8]], candidate_routes=[[], [8, 7]],
        parent_to_candidate_behavior={'travel_change': 4, 'hv_mode_switch_fraction': .2})]
    row = dict(parent, feasible_count=1, executed_count=1, trials=trials)
    feedback = feedback_builder.build_pair_feedback(row, destroy_identity={'source_hash': 'dh'}, source_reference='actual.json')
    assert feedback['representative_cases'][0]['observation']['removed_task_moves'][0]['task_id'] == 7
    assert feedback['representative_cases'][0]['observation']['parent_to_candidate_behavior']['turning_change'] == 'unavailable'
    assert 'bottleneck' in feedback['revision_directions'].lower()
    prompt = operator_revision.build_paired_repair_revision_prompt(parent=parent, feedback=feedback, n=2)
    assert source in prompt and parent['source_hash'] in prompt and 'dh' in prompt
    assert 'removed_task_moves' in prompt and '110' in prompt
    assert 'No evaluator' in prompt and 'Requested candidates: 2' in prompt
    assert 'associations' in prompt and 'per_robot_costs' in prompt
    assert 'no separate mode-switch penalty' in prompt
    path.write_text(source + '# changed')
    with pytest.raises(ValueError, match='hash'):
        operator_revision.build_paired_repair_revision_prompt(parent=parent, feedback=feedback, n=2)


def test_selection_keeps_parent_if_child_only_wins_fixed_repair():
    from mrta_rect_coverage.experiments.e7_cooperative_evolution import choose_repair
    parent = dict(operator_id='parent', source_hash='p')
    child = dict(operator_id='child', source_hash='c')
    fixed = {'p': dict(feasible_count=2, executed_count=2, mean_makespan=100),
             'c': dict(feasible_count=2, executed_count=2, mean_makespan=90)}
    short = {'p': [dict(feasible=True, fallback_count=0, makespan=80)],
             'c': [dict(feasible=True, fallback_count=0, makespan=85)]}
    assert choose_repair(parent, [child], fixed, short)['source_hash'] == 'p'
    short['c'][0]['makespan'] = 79
    assert choose_repair(parent, [child], fixed, short)['source_hash'] == 'c'
    short['c'][0]['fallback_count'] = 1
    assert choose_repair(parent, [child], fixed, short)['source_hash'] == 'p'


def test_shrinking_tied_bottleneck_set_is_not_a_new_bottleneck_transfer():
    row = dict(source_hash='p',trials=[dict(feasible=True,parent_makespan=100,candidate_makespan=110,
        relative_improvement=-.1,bottleneck_before=[0,1],bottleneck_after=[0])])
    feedback = feedback_builder.build_pair_feedback(row,destroy_identity={'source_hash':'d'},source_reference='real.json')
    assert feedback['summary']['bottleneck_transfer_losses'] == 0
    assert 'bottleneck_transfer_loss' in feedback['unavailable_outcomes']


def test_selection_rejects_unpaired_instances_or_unequal_trial_budgets():
    from mrta_rect_coverage.experiments.e7_cooperative_evolution import choose_repair
    parent, child = dict(source_hash='p'), dict(source_hash='c')
    fixed = {'p': dict(feasible_count=2,executed_count=2,mean_makespan=100),
             'c': dict(feasible_count=1,executed_count=1,mean_makespan=90)}
    short = {'p': [dict(instance='a',seed=0,feasible=True,fallback_count=0,makespan=100)],
             'c': [dict(instance='b',seed=0,feasible=True,fallback_count=0,makespan=90)]}
    assert choose_repair(parent,[child],fixed,short)['source_hash'] == 'p'
    fixed['c'].update(feasible_count=2,executed_count=2)
    assert choose_repair(parent,[child],fixed,short)['source_hash'] == 'p'


def test_experiment_records_actual_best_progress_and_reuses_completed_run(tmp_path):
    from mrta_rect_coverage.experiments.e7_cooperative_evolution import run_one
    d = tmp_path / 'd.py'
    d.write_text('''from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import DestroyResult
def destroy(solution, context, rng):
    removed = [t for r in solution.routes for t in r][:context.remove_count]
    return DestroyResult(MultiRobotSolution([[t for t in r if t not in removed] for r in solution.routes]), removed)
''')
    r = tmp_path / 'r.py'
    r.write_text('''from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import RepairResult
def repair(partial_solution, unassigned_tasks, context, rng):
    routes = [list(r) for r in partial_solution.routes]
    routes[0].extend(unassigned_tasks)
    return RepairResult(MultiRobotSolution(routes))
''')
    selected = {kind: dict(source_path=str(p), source_hash=hashlib.sha256(p.read_text().encode()).hexdigest(),
        generation=0, operator_id=kind) for kind,p in [('destroy',d),('repair',r)]}
    saved = run_one(tmp_path,'R2_T6_0',0,'V3',selected,budget=.05)
    assert saved['result']['feasible']
    assert saved['result']['global_best_improvements'] >= 0
    assert run_one(tmp_path,'R2_T6_0',0,'V3',selected,budget=.05) == saved
