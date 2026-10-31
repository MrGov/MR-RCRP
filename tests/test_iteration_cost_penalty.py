"""P1 acceptance tests: iteration_cost_penalty under a fixed wall-clock budget."""
from __future__ import annotations

from pathlib import Path

import pytest

from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.experiments.e15_cost_penalty_calibration import (
    build_evaluator,
    measure_probe_seconds,
    pinned_route,
    stage_calibrate,
    stage_verify,
)
from mrta_rect_coverage.heuristics.alns_solver import (
    ALNSConfig,
    ALNSSolver,
    OperatorRecord,
)
from mrta_rect_coverage.llm.operator_evolution.protocols import DestroyResult

ROOT = Path(__file__).resolve().parents[1]

# Wall-clock fields differ between any two runs; everything else must be stable.
TIMING_KEYS = {
    "elapsed_seconds",
    "stage_timings_seconds",
    "measured_stage_seconds",
}
PENALTY_KEYS = {"cost_penalty_factor", "score_raw", "score_effective"}
NEW_KEYS = TIMING_KEYS | PENALTY_KEYS


def _instance():
    return load_instance(ROOT / "data/R2_T6_0.txt")


def _solver(*, penalty: bool = False, reference: float | None = None,
            iterations: int | None = 5, max_runtime_seconds: float | None = None,
            seed: int = 2) -> ALNSSolver:
    if penalty and max_runtime_seconds is None:
        # The mechanism is only defined under a wall-clock budget. These unit
        # tests keep a budget that is never reached so that termination stays
        # iteration-based and two runs are comparable.
        max_runtime_seconds = 3600.0
    config = ALNSConfig.enhanced(
        cooling_schedule="iteration",
        iterations=iterations,
        max_runtime_seconds=max_runtime_seconds,
        random_seed=seed,
        iteration_cost_penalty=penalty,
        iteration_cost_reference_seconds=reference,
    )
    return ALNSSolver(_instance(), config=config)


def _comparable_history(history: list[dict]) -> list[dict]:
    return [{key: value for key, value in row.items() if key not in NEW_KEYS}
            for row in history]


# --- P1-T1 -----------------------------------------------------------------
def test_penalty_off_is_bitwise_equivalent_to_factor_one_run() -> None:
    """Flag off, or flag on with a huge t_ref (factor == 1), must agree exactly."""
    off = _solver(penalty=False).solve()
    neutral = _solver(penalty=True, reference=1e9).solve()

    assert off.iteration_cost_reference_seconds is None
    assert neutral.iteration_cost_reference_seconds == 1e9
    assert off.best_evaluation.makespan == neutral.best_evaluation.makespan
    assert off.best_solution.routes == neutral.best_solution.routes

    for row in off.iteration_history:
        assert row["score_effective"] == row["score_raw"]
        assert row["cost_penalty_factor"] == 1.0

    for row in neutral.iteration_history:
        assert row["cost_penalty_factor"] == 1.0
        assert row["score_effective"] == row["score_raw"]

    assert _comparable_history(off.iteration_history) == _comparable_history(
        neutral.iteration_history
    )
    for group in ("destroy", "repair"):
        assert {
            name: (record.uses, record.score)
            for name, record in off.operator_usage_stats[group].items()
        } == {
            name: (record.uses, record.score)
            for name, record in neutral.operator_usage_stats[group].items()
        }


# --- P1-T2 -----------------------------------------------------------------
def test_penalty_requires_wall_clock_budget() -> None:
    with pytest.raises(ValueError, match="max_runtime_seconds"):
        ALNSConfig(
            iterations=5,
            max_runtime_seconds=None,
            iteration_cost_penalty=True,
            iteration_cost_reference_seconds=1e-3,
        )


# --- P1-T3 -----------------------------------------------------------------
def test_penalty_requires_calibrated_reference() -> None:
    with pytest.raises(ValueError, match="reference_seconds"):
        ALNSConfig(
            iterations=None,
            max_runtime_seconds=5.0,
            iteration_cost_penalty=True,
            iteration_cost_reference_seconds=None,
        )
    for bad in (0.0, -1.0, float("inf"), float("nan")):
        with pytest.raises(ValueError, match="reference_seconds"):
            ALNSConfig(
                iterations=None,
                max_runtime_seconds=5.0,
                iteration_cost_penalty=True,
                iteration_cost_reference_seconds=bad,
            )


# --- P1-T4 -----------------------------------------------------------------
def test_penalty_factor_bounds_follow_reference_magnitude() -> None:
    tiny = _solver(penalty=True, reference=1e-12).solve()
    huge = _solver(penalty=True, reference=1e9).solve()

    assert tiny.iteration_history, "need at least one iteration"
    for row in tiny.iteration_history:
        assert 0.0 < row["cost_penalty_factor"] < 1.0
        assert row["score_effective"] < row["score_raw"] or row["score_raw"] == 0.0
        if row["measured_stage_seconds"] > 0:
            expected = min(1.0, (1e-12 / row["measured_stage_seconds"]) ** 0.5)
            assert row["cost_penalty_factor"] == pytest.approx(expected, rel=1e-9)
    for row in huge.iteration_history:
        assert row["cost_penalty_factor"] == 1.0
        assert row["score_effective"] == row["score_raw"]


# --- P1-T5 -----------------------------------------------------------------
def test_fallback_reward_is_never_positive_under_penalty() -> None:
    solver = _solver(penalty=True, reference=1e-9, iterations=2)
    bad = solver._wrap_external_destroy(
        lambda solution, context, rng: DestroyResult(solution, []), "bad_destroy"
    )
    solver.destroy_ops["bad_destroy"] = bad
    solver.destroy_weights["bad_destroy"] = 1.0
    # Frozen = the execution boundary that owns the fallback accounting.
    solver.frozen_destroy_ops.add("bad_destroy")
    solver.operator_stats["destroy"]["bad_destroy"] = OperatorRecord()
    solver.segment_stats["destroy"]["bad_destroy"] = OperatorRecord()
    solver._select_operators = lambda ctx: ("bad_destroy", "greedy_insertion", "forced")

    result = solver.solve()

    assert result.fallback_events, "the wrong-count destroy must fall back"
    assert result.operator_usage_stats["destroy"]["bad_destroy"].score == 0.0
    for row in result.iteration_history:
        assert row["reward_attribution"]["destroy"] == "fallback_excluded"
        assert row["cost_penalty_factor"] < 1.0


# --- P1-T6 -----------------------------------------------------------------
def test_raw_score_still_decides_global_best_under_penalty() -> None:
    plain = _solver(penalty=False, iterations=15).solve()
    penalised = _solver(penalty=True, reference=1e-9, iterations=15).solve()

    improved_plain = [row for row in plain.iteration_history if row["score_raw"] >= 8.0]
    improved_penalised = [row for row in penalised.iteration_history if row["score_raw"] >= 8.0]
    assert improved_plain, "need at least one improving iteration"
    assert len(improved_plain) == len(improved_penalised)
    for row in improved_penalised:
        assert row["cost_penalty_factor"] < 1.0
        assert row["score_effective"] < 8.0
    # The search decisions are unchanged even though rewards are damped.
    assert penalised.best_evaluation.makespan == plain.best_evaluation.makespan


# --- P1-T7 -----------------------------------------------------------------
def test_penalised_run_is_deterministic() -> None:
    """Everything except the wall-clock-derived factor must be reproducible.

    ``score_effective = score_raw * min(1, sqrt(t_ref / measured_stage_seconds))``
    is wall-clock dependent by construction, so it can never be bitwise stable.
    What must be stable is the decision trace and the exact algebraic relation.
    """
    first = _solver(penalty=True, reference=1e-9).solve()
    second = _solver(penalty=True, reference=1e-9).solve()

    def trace(result) -> list[tuple]:
        return [
            (row["destroy"], row["repair"], row["score_raw"],
             row["current_makespan"], row["best_makespan"])
            for row in result.iteration_history
        ]

    assert trace(first) == trace(second)
    assert [row["score_raw"] for row in first.iteration_history] == [
        row["score_raw"] for row in second.iteration_history
    ]
    assert first.best_evaluation.makespan == second.best_evaluation.makespan

    for result in (first, second):
        for row in result.iteration_history:
            factor = row["cost_penalty_factor"]
            assert 0.0 < factor < 1.0
            assert row["score_effective"] == pytest.approx(
                row["score_raw"] * factor, rel=1e-12, abs=1e-15
            )


# --- P1-T8 -----------------------------------------------------------------
def test_penalty_actually_reaches_operator_weights() -> None:
    """A damped reward must reduce the score mass that feeds segment weights."""
    neutral = _solver(penalty=True, reference=1e9, iterations=15).solve()
    damped = _solver(penalty=True, reference=1e-9, iterations=15).solve()

    def total_score(result) -> float:
        return sum(
            record.score
            for group in ("destroy", "repair")
            for record in result.operator_usage_stats[group].values()
        )

    assert total_score(damped) < total_score(neutral)
    reward_rows = [row for row in damped.iteration_history if row["score_raw"] > 0]
    assert reward_rows, "need credited iterations"
    assert all(row["score_effective"] < row["score_raw"] for row in reward_rows)
    # Ranking between operators only changes through the reward mass, which we
    # have just shown moves; the search trace itself stays identical.
    assert damped.best_evaluation.makespan == neutral.best_evaluation.makespan


# --- E15 calibration round trip -------------------------------------------
def test_calibration_round_trip_is_self_consistent(tmp_path) -> None:
    record = stage_calibrate(
        tmp_path,
        probe_instance=ROOT / "data/R2_T6_0.txt",
        pilot_instances=("BASE:0",),
        repeats=5,
        kappa=1.0,
    )
    assert record["probe_repeats"] == 5
    entry = record["per_instance"]["BASE:0"]
    assert entry["iterations"] == record["pilot_iterations"]
    assert abs(record["t_ref_seconds"] - record["kappa"]
               * record["t_iteration_median_seconds"]) < 1e-12
    assert record["calibration_unit"] == "alns_iteration"
    summary = stage_verify(tmp_path)
    assert summary["problems"] == []

    # A tampered record must be rejected.
    import json
    path = tmp_path / "calibration.json"
    tampered = json.loads(path.read_text(encoding="utf-8"))
    tampered["t_ref_seconds"] = tampered["t_ref_seconds"] * 2
    path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(SystemExit):
        stage_verify(tmp_path)


def test_probe_route_is_pinned_and_measurable() -> None:
    instance = _instance()
    _, _, route_dp = build_evaluator(instance)
    route = pinned_route(instance)
    samples = measure_probe_seconds(route_dp, route, repeats=3)
    assert route == [task.task_id for task in instance.tasks]
    assert len(samples) == 3
    assert all(seconds > 0 for seconds in samples)
    assert route_dp.evaluate_route(route).total_cost > 0
