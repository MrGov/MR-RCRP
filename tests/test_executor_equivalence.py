"""Executor modes must be behaviour-identical when the iteration count is fixed.

``original`` starts one process per generated-operator call; ``warm`` keeps one
validated worker per operator for the whole solve. Only process lifetime
changes, so with an iteration bound (no wall-clock deadline) both modes must
produce the same search path, the same best solution and the same objective.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from mrta_rect_coverage.core.instance_loader import load_instance  # noqa: E402
from mrta_rect_coverage.experiments.e6_pair_selection import (  # noqa: E402
    close_extra_executors,
    make_solver,
)
from mrta_rect_coverage.experiments.e11_structural_benchmark import identities  # noqa: E402

INSTANCE = ROOT / 'data/R2_T6_0.txt'
ITERATIONS = 6
SEED = 3


def _solve(executor):
    instance = load_instance(INSTANCE)
    selected = identities()
    solver = make_solver(
        instance,
        SEED,
        dict(destroy=selected['destroy'], repair=selected['main']),
        'V1',
        iterations=ITERATIONS,
        executor=executor,
    )
    try:
        proxies = list(getattr(solver, 'extra_executors', ()))
        result = solver.solve()
        starts = [getattr(proxy, 'process_starts', 0) for proxy in proxies]
        return result, starts, proxies
    finally:
        close_extra_executors(solver)


@pytest.fixture(scope='module')
def runs():
    original, _, _ = _solve('original')
    warm, starts, proxies = _solve('warm')
    return original, warm, starts, proxies


def test_same_number_of_iterations(runs):
    original, warm, _, _ = runs
    assert original.iterations_completed == warm.iterations_completed == ITERATIONS


def test_same_best_objective_and_routes(runs):
    original, warm, _, _ = runs
    assert warm.best_evaluation.makespan == pytest.approx(
        original.best_evaluation.makespan, abs=1e-9)
    assert [list(r) for r in warm.best_solution.routes] == [
        list(r) for r in original.best_solution.routes]


def test_same_decision_trace(runs):
    original, warm, _, _ = runs
    keys = ('destroy', 'repair', 'best_makespan', 'accepted', 'fallback_used')
    left = [tuple(h[k] for k in keys) for h in original.iteration_history]
    right = [tuple(h[k] for k in keys) for h in warm.iteration_history]
    assert left == right


def test_same_generated_operator_invocation_counts(runs):
    original, warm, _, _ = runs
    assert warm.generated_operator_execution.keys() == original.generated_operator_execution.keys()
    for kind, per_stem in original.generated_operator_execution.items():
        other_kind = warm.generated_operator_execution[kind]
        assert other_kind.keys() == per_stem.keys(), kind
        for stem, stats in per_stem.items():
            other = other_kind[stem]
            assert other['calls'] == stats['calls'], (kind, stem)
            assert other['failures'] == stats['failures'], (kind, stem)


def test_warm_mode_reuses_a_single_worker(runs):
    _, _, starts, proxies = runs
    assert proxies, 'warm mode must register resident workers'
    assert min(starts) >= 0 and max(starts) <= 1, starts
    assert any(count == 1 for count in starts), 'no resident worker was used'


def test_close_is_idempotent():
    instance = load_instance(INSTANCE)
    selected = identities()
    solver = make_solver(
        instance, SEED,
        dict(destroy=selected['destroy'], repair=selected['main']),
        'V1', iterations=1, executor='warm')
    close_extra_executors(solver)
    close_extra_executors(solver)
    assert solver.extra_executors == []


def test_unknown_executor_is_rejected():
    instance = load_instance(INSTANCE)
    selected = identities()
    with pytest.raises(ValueError):
        make_solver(
            instance, SEED,
            dict(destroy=selected['destroy'], repair=selected['main']),
            'V1', iterations=1, executor='turbo')
