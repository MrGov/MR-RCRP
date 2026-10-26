from __future__ import annotations

from pathlib import Path
import subprocess
import types

from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.heuristics.alns_solver import ALNSConfig, ALNSSolver


ROOT = Path(__file__).resolve().parents[1]


def _solver(*, iterations: int = 0) -> ALNSSolver:
    return ALNSSolver(
        load_instance(ROOT / "data" / "R2_T6_0.txt"),
        config=ALNSConfig.enhanced(
            iterations=iterations,
            pair_selection_mode="coupled",
            coupled_destroy_operator="llm_destroy",
            coupled_repair_operator="llm_repair",
        ),
    )


def test_coupled_and_independent_pair_selections_are_distinguished() -> None:
    solver = _solver()
    solver.destroy_weights["llm_destroy"] = 1.0
    solver.repair_weights["llm_repair"] = 1.0
    solver._weighted_pick = lambda weights: (
        "llm_destroy" if weights is solver.destroy_weights else "llm_repair"
    )

    class FixedRandom:
        def __init__(self, value: float) -> None:
            self.value = value

        def random(self) -> float:
            return self.value

    solver.rng = FixedRandom(0.0)
    active = solver._select_operators(None)
    assert active[:2] == ("llm_destroy", "llm_repair")
    assert solver._last_selection_action == "coupled"

    solver.rng = FixedRandom(1.0)
    coincidental = solver._select_operators(None)
    assert coincidental[:2] == ("llm_destroy", "llm_repair")
    assert solver._last_selection_action == "independent"
    assert solver.pair_action_stats["independent_coincidental_uses"] == 1


def test_segment_reward_changes_pair_odds_and_fallback_has_zero_reward() -> None:
    solver = _solver()
    solver.destroy_weights["llm_destroy"] = 1.0
    solver.repair_weights["llm_repair"] = 1.0
    initial = solver._coupled_selection_probability()
    pair = solver.pair_selection_segment["coupled"]
    independent = solver.pair_selection_segment["independent"]
    pair.uses, pair.score = 2, 16.0
    independent.uses, independent.score = 18, 18.0
    solver._update_coupled_selection_preference()
    assert solver._coupled_selection_probability() > initial
    assert pair.uses == independent.uses == 0
    boosted = solver._coupled_selection_probability()
    pair.uses, pair.score = 2, 0.0
    independent.uses, independent.score = 18, 18.0
    solver._update_coupled_selection_preference()
    assert solver._coupled_selection_probability() < boosted


def test_coupled_fallback_is_recorded_but_receives_no_pair_reward() -> None:
    solver = _solver(iterations=1)
    destroy_name = "llm_destroy"
    repair_name = "llm_repair"

    def fallback_destroy(solution, evaluation, remove_count):
        solver._record_fallback("destroy", destroy_name, "runtime", "synthetic test fallback")
        return solver._random_destroy(solution, evaluation, remove_count)

    solver.destroy_ops[destroy_name] = fallback_destroy
    solver.repair_ops[repair_name] = solver._greedy_insertion
    for group, name in (("destroy", destroy_name), ("repair", repair_name)):
        weights = solver.destroy_weights if group == "destroy" else solver.repair_weights
        weights[name] = 1.0
        solver.operator_stats[group][name] = type(next(iter(solver.operator_stats[group].values())))()
        solver.segment_stats[group][name] = type(next(iter(solver.segment_stats[group].values())))()
    solver.frozen_destroy_ops.add(destroy_name)
    solver.frozen_repair_ops.add(repair_name)

    def select(_context):
        solver._last_selection_action = "coupled"
        return destroy_name, repair_name, "test"

    solver._select_operators = select
    result = solver.solve()

    assert result.fallback_events
    assert result.pair_action_stats["uses"] == 1
    assert result.pair_action_stats["fallbacks"] == 1
    assert result.pair_action_stats["successful_uses"] == 0
    assert result.pair_action_stats["accepted"] == 0
    assert result.pair_action_stats["global_best"] == 0
    assert result.pair_action_stats["reward"] == 0.0
    assert result.iteration_history[0]["coupled_pair_fallback"]
    assert solver.pair_selection_segment["coupled"].uses == 1
    assert solver.pair_selection_segment["coupled"].score == 0.0


def test_solver_reports_search_phase_and_generated_execution_timings() -> None:
    solver = ALNSSolver(
        load_instance(ROOT / "data" / "R2_T6_0.txt"),
        config=ALNSConfig.enhanced(iterations=1),
    )
    result = solver.solve()

    assert result.iterations_completed == 1
    expected = {
        "destroy_execution_seconds",
        "partial_evaluation_seconds",
        "repair_execution_seconds",
        "local_search_seconds",
        "initial_full_evaluation_seconds",
        "full_evaluation_seconds",
        "other_seconds",
    }
    assert expected <= result.timing_breakdown_seconds.keys()
    assert all(result.timing_breakdown_seconds[key] >= 0.0 for key in expected)
    assert result.generated_operator_execution["destroy"] == {}
    assert result.generated_operator_execution["repair"] == {}


def test_v1_retains_e5_rng_selection_and_fixed_iteration_search_results() -> None:
    source = subprocess.check_output([
        "git", "show", "297a9495aa2dc04ebad21dc0314172b8df78ef00:src/mrta_rect_coverage/heuristics/alns_solver.py"
    ], cwd=ROOT, text=True)
    # Use the original module name for dataclass annotation resolution, without
    # installing or overwriting any project module or frozen candidate source.
    original = types.ModuleType("mrta_rect_coverage.heuristics.alns_solver")
    original.__package__ = "mrta_rect_coverage.heuristics"
    exec(compile(source, "<E5 frozen solver>", "exec"), original.__dict__)
    instance = load_instance(ROOT / "data/R2_T6_0.txt")
    old = original.ALNSSolver(instance, config=original.ALNSConfig.enhanced(iterations=20, random_seed=2))
    new = ALNSSolver(instance, config=ALNSConfig.enhanced(iterations=20, random_seed=2))
    # Progress cooling is iteration-based here, so timing instrumentation does
    # not change either the random stream or the search decisions.
    a, b = old.solve(), new.solve()
    assert a.best_solution == b.best_solution
    assert a.best_evaluation.makespan == b.best_evaluation.makespan
    for left, right in zip(a.iteration_history, b.iteration_history):
        for field in ("destroy", "repair", "accepted", "candidate_makespan", "best_makespan", "temperature"):
            assert left[field] == right[field]
    assert old.rng.getstate() == new.rng.getstate()
