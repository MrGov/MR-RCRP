"""Focused E3 controls: limits, reaction, calibration, and best/current separation."""
from pathlib import Path
from types import SimpleNamespace
import math

import pytest

import mrta_rect_coverage.heuristics.alns_solver as module
from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.config import load_config


ROOT = Path(__file__).resolve().parents[1]


def solver(**options):
    return module.ALNSSolver(load_instance(ROOT / "data/R2_T6_0.txt"),
                             config=module.ALNSConfig.enhanced(**options))


def test_time_limit_stops_at_boundary_and_records_work(monkeypatch):
    s = solver(iterations=None, max_runtime_seconds=1.0)
    clock = [0.0]
    monkeypatch.setattr(module, "perf_counter", lambda: clock[0])
    # Both local-search entry points advance the fake clock: the priced one is the
    # default since E24, the reference one is used when the switch is turned off.
    original = module.run_priced_local_search
    def step(*args, **kwargs):
        result = original(*args, **kwargs)
        clock[0] += 0.6
        return result
    monkeypatch.setattr(module, "run_priced_local_search", step)
    monkeypatch.setattr(module, "run_stronger_local_search", step)
    result = s.solve()
    assert result.iterations_completed == 2
    assert result.runtime_seconds == pytest.approx(1.2)
    assert result.termination_reason == "time"
    assert result.route_dp_calls > 0
    assert result.iteration_history[-1]["route_dp_calls"] == result.route_dp_calls
    assert result.iteration_history[1]["temperature"] < result.initial_temperature


def test_segment_reaction_uses_only_recent_rewards():
    s = solver(reaction_factor=0.2)
    name = next(iter(s.destroy_ops))
    unused = list(s.destroy_ops)[1]
    s._update_operator_stats("destroy", name, 8)
    s._update_weights()
    assert s.destroy_weights[name] == pytest.approx(2.4)
    assert s.destroy_weights[unused] == 1
    s._update_operator_stats("destroy", name, 0)
    s._update_weights()
    assert s.destroy_weights[name] == pytest.approx(1.92)
    assert s.operator_stats["destroy"][name].uses == 2
    assert s.segment_stats["destroy"][name].uses == 0


def test_temperature_calibration_and_progress():
    s = solver(iterations=100)
    temp = s._initial_temperature(1000)
    assert math.exp(-10 / temp) == pytest.approx(0.5)
    assert s._progress_temperature(temp, 0, 100) == pytest.approx(temp * 0.01)
    assert s._accept(SimpleNamespace(makespan=1000), SimpleNamespace(makespan=999), temp)[0]


def test_global_best_survives_accepted_worsening(monkeypatch):
    s = solver(iterations=2)
    initial = s.solution_evaluator.evaluate(s.initial_solution).makespan
    s.destroy_ops = {"noop": lambda sol, ev, n: (sol, [])}
    s.repair_ops = {"noop": lambda sol, removed, ev: sol}
    monkeypatch.setattr(s, "_select_operators", lambda ctx: ("noop", "noop", "test"))
    monkeypatch.setattr(s, "_update_operator_stats", lambda *args: None)
    values = iter([initial - 10, initial + 10])
    fake_local_search = lambda sol, *args, **kw: (
        MultiRobotSolution(routes=[list(r) for r in sol.routes]),
        SimpleNamespace(makespan=next(values)))
    monkeypatch.setattr(module, "run_stronger_local_search", fake_local_search)
    monkeypatch.setattr(module, "run_priced_local_search", fake_local_search)
    monkeypatch.setattr(s, "_accept", lambda *args: (True, "sa"))
    monkeypatch.setattr(s, "_build_context", lambda *args: None)
    result = s.solve()
    assert result.best_evaluation.makespan == initial - 10
    assert result.iteration_history[-1]["current_makespan"] == initial + 10


def test_segment_updates_only_at_boundaries(monkeypatch):
    s = solver(iterations=5, segment_length=2)
    updates = []
    original = s._update_weights
    def update():
        updates.append(1)
        original()
    monkeypatch.setattr(s, "_update_weights", update)
    result = s.solve()
    assert len(updates) == 2
    assert result.iterations_completed == 5


def test_b1_yaml_and_original_defaults():
    cfg = load_config("configs/e3_b1.yaml")
    assert cfg.alns_profile == "B1" and cfg.alns_iterations is None
    assert cfg.alns_time_per_task == 1.0
    assert load_config().alns_profile == "B1"
    legacy = module.ALNSConfig()
    assert legacy.acceptance == "improvement_only" and legacy.weight_update == "cumulative"
    with pytest.raises(ValueError, match="termination"):
        module.ALNSConfig(iterations=None)
    with pytest.raises(ValueError, match="finite"):
        module.ALNSConfig(max_runtime_seconds=float("nan"))
