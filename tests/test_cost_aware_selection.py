"""M2 spend-aware operator selection (cost_aware_selection).

The mechanism multiplies roulette probability by
``(median measured call seconds / this operator's measured call seconds) ** exponent``,
clipped into ``[1 / clip, clip]``.

Test intent: the knob must be *neutral* when it carries no information
(homogeneous costs, unmeasured operators, exponent 0) and must *bite* when the
pool is genuinely heterogeneous.
"""

from __future__ import annotations

import time
from dataclasses import replace
from pathlib import Path

import pytest

from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.heuristics.alns_solver import ALNSConfig, ALNSSolver, OperatorRecord

DATA = Path(__file__).resolve().parents[1] / "data" / "R2_T6_0.txt"


def _instance():
    return load_instance(DATA)


def _config(**overrides) -> ALNSConfig:
    options = dict(
        iterations=25,
        acceptance="simulated_annealing",
        initial_temperature=None,
        cooling_schedule="iteration",
        weight_update="segment",
        segment_length=5,
        random_seed=11,
    )
    options.update(overrides)
    return ALNSConfig(**options)


def _solver(config: ALNSConfig) -> ALNSSolver:
    return ALNSSolver(_instance(), constructor="spatial_sort", config=config)


def _add_destroy(solver: ALNSSolver, name: str, fn) -> None:
    solver.destroy_ops[name] = fn
    solver.destroy_weights[name] = 1.0
    solver.operator_stats["destroy"][name] = OperatorRecord()
    solver.segment_stats["destroy"][name] = OperatorRecord()
    solver.operator_time_stats["destroy"][name] = [0.0, 0.0]


def _slow_wrapper(solver: ALNSSolver, seconds: float):
    base = solver._random_destroy

    def slow(solution, evaluation, remove_count):
        time.sleep(seconds)
        return base(solution, evaluation, remove_count)

    return slow


def _destroy_counts(result) -> dict:
    counts = {}
    for row in result.iteration_history:
        counts[row["destroy"]] = counts.get(row["destroy"], 0) + 1
    return counts


# C1: exponent 0 is exactly the baseline knob (factor == 1 for every operator).
def test_zero_exponent_is_bitwise_identical_to_disabled_selection():
    solver_off = _solver(_config())
    result_off = solver_off.solve()
    solver_zero = _solver(_config(cost_aware_selection=True, cost_aware_exponent=0.0))
    result_zero = solver_zero.solve()

    assert result_zero.best_evaluation.makespan == result_off.best_evaluation.makespan
    assert [row["destroy"] for row in result_zero.iteration_history] == [
        row["destroy"] for row in result_off.iteration_history
    ]
    assert all(
        row["cost_factors"]["destroy"] == 1.0 and row["cost_factors"]["repair"] == 1.0
        for row in result_zero.iteration_history
    )


# C2: equal measured costs -> factor exactly 1.0 for everyone.
def test_homogeneous_costs_give_unit_factor():
    solver = _solver(_config(cost_aware_selection=True))
    solver.operator_time_stats["destroy"] = {
        "a": [0.02, 10.0],
        "b": [0.02, 10.0],
        "c": [0.02, 10.0],
    }
    assert all(
        solver._cost_factor("destroy", name) == pytest.approx(1.0)
        for name in ("a", "b", "c")
    )


# C3: factor follows the formula and is clipped at both ends.
def test_cost_factor_follows_median_ratio_and_clips():
    solver = _solver(_config(cost_aware_selection=True, cost_aware_clip=4.0))
    # Odd count so the median is unambiguous: 0.02 seconds per call.
    solver.operator_time_stats["destroy"] = {
        "cheap": [0.01, 10.0],
        "median": [0.02, 10.0],
        "median2": [0.02, 10.0],
        "pricey": [0.06, 10.0],
        "extreme": [200.0, 10.0],
    }
    median = 0.02
    assert solver._cost_factor("destroy", "median") == pytest.approx(1.0)
    assert solver._cost_factor("destroy", "cheap") == pytest.approx(2.0)
    assert solver._cost_factor("destroy", "pricey") == pytest.approx(median / 0.06)
    # 0.02 / 100 -> 0.0002, clipped to 1 / 4.
    assert solver._cost_factor("destroy", "extreme") == pytest.approx(0.25)


# C4: an operator with no samples keeps full weight (exploration is preserved).
def test_unmeasured_operator_keeps_unit_factor():
    solver = _solver(_config(cost_aware_selection=True))
    solver.operator_time_stats["destroy"] = {
        "known_fast": [0.01, 10.0],
        "known_slow": [0.10, 10.0],
        "fresh": [0.0, 0.0],
    }
    assert solver._cost_factor("destroy", "fresh") == pytest.approx(1.0)


# C5: a genuinely expensive operator is selected less often (the mechanism bites).
def test_expensive_operator_is_selected_less_often():
    solver_off = _solver(_config(iterations=40))
    _add_destroy(solver_off, "slow_destroy", _slow_wrapper(solver_off, 0.02))
    counts_off = _destroy_counts(solver_off.solve())

    solver_on = _solver(_config(iterations=40, cost_aware_selection=True))
    _add_destroy(solver_on, "slow_destroy", _slow_wrapper(solver_on, 0.02))
    counts_on = _destroy_counts(solver_on.solve())

    assert counts_off.get("slow_destroy", 0) >= 4
    assert counts_on.get("slow_destroy", 0) < counts_off.get("slow_destroy", 0)


# C6: the disabled default stays deterministic; the spend-aware modes are a
# function of measured wall-clock time and are therefore only reproducible given
# the same measured spend (see the module docstring of e22 for the consequence).
def test_disabled_selection_is_deterministic():
    first = _solver(_config()).solve()
    second = _solver(_config()).solve()
    assert first.best_evaluation.makespan == second.best_evaluation.makespan
    assert [row["destroy"] for row in first.iteration_history] == [
        row["destroy"] for row in second.iteration_history
    ]


def test_spend_aware_run_reports_factors_and_stays_consistent():
    solver = _solver(_config(cost_aware_selection=True))
    result = solver.solve()
    assert all(0.25 <= row["cost_factors"]["destroy"] <= 4.0
               for row in result.iteration_history)
    assert all(0.25 <= row["cost_factors"]["repair"] <= 4.0
               for row in result.iteration_history)


# C6b: throughput mode keeps the draw uniform but reweights on reward per second.
def test_throughput_mode_is_accepted_and_leaves_units_neutral():
    solver = _solver(_config(cost_aware_selection=True, cost_aware_mode="throughput"))
    result = solver.solve()
    assert result.iterations_completed == 25
    # Uniform draw: cost factors must stay at 1.0 in this mode.
    assert all(row["cost_factors"] == {"destroy": 1.0, "repair": 1.0}
               for row in result.iteration_history)


# C7: the flag is validated where it is configured.
def test_invalid_configuration_is_rejected():
    with pytest.raises(ValueError, match="cost_aware_exponent"):
        _config(cost_aware_selection=True, cost_aware_exponent=-1.0)
    with pytest.raises(ValueError, match="cost_aware_clip"):
        _config(cost_aware_selection=True, cost_aware_clip=0.5)
    with pytest.raises(ValueError, match="cost_aware_min_samples"):
        _config(cost_aware_selection=True, cost_aware_min_samples=0)


# C8: the disabled default writes neutral factors and still reports spend.
def test_disabled_run_reports_unit_factors_and_spend():
    solver = _solver(_config())
    result = solver.solve()
    assert all(row["cost_factors"] == {"destroy": 1.0, "repair": 1.0} for row in result.iteration_history)
    spend = result.operator_time_stats["repair"]
    assert spend and all(record[1] > 0 for record in spend.values())


# C9: spend accounting adds exactly one call per iteration per pool.
def test_spend_accounting_counts_one_call_per_iteration():
    solver = _solver(_config(iterations=12))
    result = solver.solve()
    destroy_calls = sum(record[1] for record in result.operator_time_stats["destroy"].values())
    repair_calls = sum(record[1] for record in result.operator_time_stats["repair"].values())
    assert destroy_calls == 12
    assert repair_calls == 12
