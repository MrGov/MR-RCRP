from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path
import random

from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.heuristics.alns_solver import ALNSConfig
from mrta_rect_coverage.heuristics.structural_search import (
    PairPortfolioSolver, StructuralExecutor, StructuralKernel,
)
from mrta_rect_coverage.llm.operator_evolution.candidate_execution import CandidateProxy

ROOT = Path(__file__).resolve().parents[1]
R4_C2 = ROOT / 'outputs/structural_population/run_001/requests/16_r4_c2/candidate.py'
R4_C2_HASH = 'e76969c85dcef648d0c66a4da51ddba20e24195f9db54cfced801c9501b90b85'
R4_C2_ARTIFACT_HASH = 'd820906db3b238a1236522be637277e9a4cebb232fdec2e74a8940fdce356229'
SMALL_INSTANCE = ROOT / 'data/R2_T10_0.txt'


def _features():
    solver = PairPortfolioSolver(
        load_instance(SMALL_INSTANCE),
        config=ALNSConfig.enhanced(iterations=1, random_seed=23),
    )
    solution = solver.initial_solution
    evaluation = solver.solution_evaluator.evaluate(solution)
    kernel = StructuralKernel(solver, lambda features, rng: [])
    return solver, kernel.destroy_features(solution, evaluation, 3)


def _baseline_policy(path, digest):
    proxy = CandidateProxy(path, 'structural', digest, timeout_ms=150)

    def call(features, rng):
        from mrta_rect_coverage.heuristics.structural_search import validate_actions
        from copy import deepcopy
        outcome = proxy.execute((deepcopy(features), deepcopy(rng)), timeout_ms=150)
        if outcome.status != 'success':
            raise RuntimeError(outcome.error_message)
        return validate_actions(outcome.result, features)

    return call


def _solve(policy_factory):
    solver = PairPortfolioSolver(
        load_instance(SMALL_INSTANCE),
        config=ALNSConfig.enhanced(iterations=4, random_seed=731),
    )
    policy, cleanup = policy_factory()
    kernel = StructuralKernel(solver, policy)
    solver.add_kernel('r4_c2', kernel)
    solver.set_pairs([('r4_c2:destroy', 'r4_c2:repair')])
    try:
        result = solver.solve()
        trace = [(row['destroy'], row['repair'], row['best_makespan'],
                  row['accepted'], row['fallback_used']) for row in result.iteration_history]
        return result, trace
    finally:
        cleanup()


def test_frozen_r4_c2_call_reports_separate_execution_stages():
    source = R4_C2.read_text(encoding='utf-8')
    assert hashlib.sha256(source.encode('utf-8')).hexdigest() == R4_C2_HASH
    assert hashlib.sha256(R4_C2.read_bytes()).hexdigest() == R4_C2_ARTIFACT_HASH
    _, features = _features()
    with StructuralExecutor(R4_C2, expected_hash=R4_C2_ARTIFACT_HASH) as executor:
        executor(features, random.Random(13))
        stages = executor.samples[-1]['execution_stages']
    assert {'input_copy', 'input_send', 'source_hash_check', 'source_validation',
            'compile', 'namespace_setup', 'policy', 'return_wait', 'return_validation'} <= stages.keys()
    assert all(value >= 0 for value in stages.values())
    assert stages['source_hash_check'] > 0
    assert stages['source_validation'] > 0
    assert stages['compile'] > 0


def test_compiled_worker_is_fresh_and_does_not_mutate_features(tmp_path):
    source = (
        'calls = 0\n'
        'def search_step(features, rng):\n'
        '    global calls\n'
        '    calls += 1\n'
        '    action = features["routes"][0][0]\n'
        '    features["routes"][0].clear()\n'
        '    return [action]\n'
    )
    path = tmp_path / 'policy.py'
    path.write_text(source, encoding='utf-8')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    features = {'phase': 'destroy', 'routes': [[4, 5]], 'remove_limit': 1}
    with StructuralExecutor(path, expected_hash=digest) as executor:
        first = executor(deepcopy(features), random.Random(1))
        second = executor(deepcopy(features), random.Random(1))
        assert first == second == [4]
        assert executor.backend.process_starts == 1
    assert features['routes'] == [[4, 5]]


def test_changed_features_are_used_after_a_previous_call():
    source = R4_C2.read_text(encoding='utf-8')
    digest = hashlib.sha256(source.encode('utf-8')).hexdigest()
    _, first = _features()
    second = deepcopy(first)
    second['routes'] = [list(reversed(route)) for route in first['routes']]
    with StructuralExecutor(R4_C2, expected_hash=R4_C2_ARTIFACT_HASH) as executor:
        actual = executor(second, random.Random(31))
    expected = _baseline_policy(R4_C2, digest)(second, random.Random(31))
    assert actual == expected
    assert set(actual) <= {task for route in second['routes'] for task in route}


def test_frozen_r4_c2_fixed_iteration_trace_matches_per_call_executor():
    digest = hashlib.sha256(R4_C2.read_text(encoding='utf-8').encode('utf-8')).hexdigest()

    def original_factory():
        return _baseline_policy(R4_C2, digest), lambda: None

    def warm_factory():
        executor = StructuralExecutor(R4_C2, expected_hash=R4_C2_ARTIFACT_HASH)
        return executor, executor.close

    original, original_trace = _solve(original_factory)
    warm, warm_trace = _solve(warm_factory)
    assert original.iterations_completed == warm.iterations_completed == 4
    assert original_trace == warm_trace
    assert original.best_solution.routes == warm.best_solution.routes
    assert original.best_evaluation.makespan == warm.best_evaluation.makespan


def test_timeout_discards_worker_and_keeps_parent_features_isolated(tmp_path):
    path = tmp_path / 'timeout_policy.py'
    path.write_text(
        'def search_step(features, rng):\n'
        '    while True:\n'
        '        pass\n', encoding='utf-8')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    executor = StructuralExecutor(path, expected_hash=digest, timeout_ms=30)
    features = {'phase': 'destroy', 'routes': [[3, 8]], 'remove_limit': 1}
    try:
        try:
            executor(features, random.Random(2))
        except RuntimeError as exc:
            assert 'timeout' in str(exc)
        else:
            raise AssertionError('timed-out candidate must fail')
        assert executor.backend._process is None
        assert features['routes'] == [[3, 8]]
    finally:
        executor.close()
