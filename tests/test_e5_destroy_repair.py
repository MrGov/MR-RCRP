from pathlib import Path
from types import SimpleNamespace

import pytest

from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.heuristics.alns_solver import ALNSConfig, ALNSSolver
from mrta_rect_coverage.llm.operator_evolution.candidate_loader import load_and_validate_candidate
from mrta_rect_coverage.llm.operator_evolution.evaluator import build_destroy_benchmark_cases, evaluate_destroy_candidates
from mrta_rect_coverage.llm.operator_evolution.protocols import DestroyResult, RepairResult
from mrta_rect_coverage.experiments.e1_real_llm_pilot import compute_exact_dp_behavior

ROOT = Path(__file__).resolve().parents[1]


def test_experiment_reference_reuses_manual_random_destroy():
    import random
    from mrta_rect_coverage.experiments.e5_destroy_repair import reference_destroy
    solver=ALNSSolver(load_instance(ROOT/'data/R2_T6_0.txt'))
    solution=solver.initial_solution
    evaluation=solver.solution_evaluator.evaluate(solution)
    solver.rng=random.Random(1)
    expected=solver._random_destroy(solution,evaluation,2)
    actual=reference_destroy(solution,evaluation,2,random.Random(1))
    assert actual==expected


def test_paired_destroy_uses_same_fixed_repair_and_real_dp_evidence():
    case = build_destroy_benchmark_cases([ROOT / 'data/R2_T6_0.txt'])[0]
    solver = ALNSSolver(case.instance)
    seen = []
    def reference(solution, evaluation, count, rng):
        solver.rng = rng
        return solver._random_destroy(solution, evaluation, count)
    def destroy(solution, context, rng):
        partial, removed = reference(solution, case.full_evaluation, context.remove_count, rng)
        return DestroyResult(partial, removed)
    def repair(partial, removed, context, rng):
        seen.append(tuple(removed))
        solution = solver._greedy_insertion(partial, removed, solver.solution_evaluator.evaluate_partial(partial))
        return RepairResult(solution)
    candidate = SimpleNamespace(callable_obj=destroy, validation=SimpleNamespace(operator_id='d', code_hash='dh', validation_status='valid'))
    fixed = SimpleNamespace(callable_obj=repair, validation=SimpleNamespace(code_hash='rh'))
    row = evaluate_destroy_candidates([candidate], [case], seeds=[0], timeout_ms=2000,
        fixed_repair=fixed, reference_destroy=reference, behavior_callback=compute_exact_dp_behavior)[0]
    trial = row['trials'][0]
    assert len(seen) == 2 and seen[0] == seen[1]
    assert row['feasible_count'] == 1 and trial['relative_improvement'] == 0
    assert trial['baseline_makespan'] == trial['candidate_makespan']
    assert trial['reference_removed_tasks'] == trial['removed_tasks']
    assert len(trial['removed_tasks']) == trial['remove_count'] == 1
    assert trial['exact_dp_behavior']['travel_change'] == 0
    assert trial['exact_dp_behavior']['dp_state_switch_fraction'] == 0
    assert 'turning_change' in trial['parent_to_candidate_behavior']
    assert trial['fixed_repair_hash'] == 'rh'


def test_development_destroy_registration_executes_with_repair_and_checks_count(tmp_path):
    path = tmp_path / 'destroy.py'
    path.write_text('''from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import DestroyResult
def destroy(solution, context, rng):
    tasks = [t for r in solution.routes for t in r]
    removed = tasks[:context.remove_count]
    return DestroyResult(MultiRobotSolution([[t for t in r if t not in removed] for r in solution.routes]), removed)
''')
    loaded = load_and_validate_candidate(path=path, operator_type='destroy', round_id=0,
        source='test', description='test', allow_unsafe_candidate_execution=True)
    assert loaded.callable_obj is not None
    solver = ALNSSolver(load_instance(ROOT / 'data/R2_T6_0.txt'), config=ALNSConfig.enhanced(iterations=2))
    solver.register_development_destroy(loaded.callable_obj, name='test_d')
    with pytest.raises(ValueError, match='duplicate'):
        solver.register_development_destroy(loaded.callable_obj, name='test_d')
    with pytest.raises(ValueError, match='CandidateProxy'):
        solver.register_development_destroy(lambda *a: None, name='bad')
    solver._select_operators = lambda ctx: ('test_d', 'greedy_insertion', 'test')
    result = solver.solve()
    assert result.operator_usage_stats['destroy']['test_d'].uses == 2
    assert result.fallback_events == []
    assert result.iteration_history[0]['llm_operator_success']
    assert solver.solution_evaluator.evaluate(result.best_solution).makespan == result.best_evaluation.makespan
    # A valid partition with the wrong removal count must use the existing fallback.
    wrapped = solver._wrap_external_destroy(lambda sol, ctx, rng: DestroyResult(sol, []), 'wrong_count')
    _, removed = wrapped(solver.initial_solution, solver.solution_evaluator.evaluate(solver.initial_solution), 1)
    assert len(removed) == 1 and solver.fallback_events[-1]['operator_name'] == 'wrong_count'


def test_destroy_revision_has_real_parent_source_hash_and_removal_evidence(tmp_path):
    import hashlib
    from mrta_rect_coverage.experiments.e1_real_llm_pilot import destroy_revision_prompt, build_destroy_feedback
    source = 'def destroy(solution, context, rng):\n    pass\n'
    path = tmp_path / 'd.py'; path.write_text(source)
    row = dict(operator_id='d', source_path=str(path), source_hash=hashlib.sha256(source.encode()).hexdigest(),
               avg_relative_improvement=-.1, success_rate=0, trials=[dict(feasible=True, instance_id='real', solver_seed=0,
               baseline_makespan=100, candidate_makespan=110, relative_improvement=-.1,
               baseline_route_costs=[100,90], candidate_route_costs=[80,110], reassigned_task_count=1,
               removed_tasks=[2,3], reference_removed_tasks=[1,4], parent_route_costs=[101,95],
               exact_dp_behavior={'travel_change':-5,'coverage_change':0,'turning_change':1,'dp_cascade_ratio':.2})])
    feedback=build_destroy_feedback([row], parent=row)
    prompt=destroy_revision_prompt(row, feedback, n=2)
    assert source in prompt and row['source_hash'] in prompt
    assert 'removed_tasks' in prompt and '110' in prompt
    assert 'No evaluator' in prompt and 'remove_count' in prompt
    assert 'Requested candidates: 2' in prompt
    assert 'associations' in prompt and 'removal' in prompt
    path.write_text(source+'# changed')
    with pytest.raises(ValueError, match='hash'):
        destroy_revision_prompt(row, feedback, n=2)
