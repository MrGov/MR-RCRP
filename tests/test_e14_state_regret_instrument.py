from __future__ import annotations

import json
from pathlib import Path

import pytest

from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.core.solution_evaluator import MultiRobotSolutionEvaluator
from mrta_rect_coverage.experiments import e14_state_regret_instrument as e14
from mrta_rect_coverage.core.state_chain_report import assert_report_consistent

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_smoke_stage_creates_report_and_preserves_dp_statistics(tmp_path):
    e14.stage_smoke(tmp_path)
    path = tmp_path / "smoke" / "R2_T6_0.json"
    assert path.exists()
    report = json.loads(path.read_text(encoding="utf-8"))
    assert_report_consistent(report)
    assert report["dp_statistics_before"]["calls"] == report["dp_statistics_after"]["calls"]
    assert report["dp_statistics_before"]["cache_misses"] == report["dp_statistics_after"]["cache_misses"]
    meta = json.loads((tmp_path / "meta.json").read_text(encoding="utf-8"))
    assert meta["dp_statistics_before"]["calls"] == meta["dp_statistics_after"]["calls"]


def test_round_robin_solution_is_a_complete_partition():
    instance = load_instance(PROJECT_ROOT / "data" / "R2_T6_0.txt")
    states, _, evaluator = e14.evaluator_for(instance)
    solution = e14.round_robin_solution(instance)
    assigned = [task_id for route in solution.routes for task_id in route]
    assert sorted(assigned) == sorted(task.task_id for task in instance.tasks)
    assert len(solution.routes) == instance.robot_count
    evaluation = evaluator.evaluate(solution)
    assert len(evaluation.per_robot_costs) == instance.robot_count


def test_parents_stage_requires_existing_e10b_inputs(tmp_path, monkeypatch):
    monkeypatch.setattr(e14, "E10B_OUTPUT", tmp_path / "missing")
    with pytest.raises(SystemExit, match="run e10b --stage prepare first"):
        e14.stage_parents(tmp_path / "out")


# ---------------------------------------------------------------------------
# P2: stage solutions (child evidence for paired contrast)
# ---------------------------------------------------------------------------

def _index_dir(tmp_path, instance_id="TEST_1", file_path="R2_T6_0.txt"):
    index_dir = tmp_path / "e10b_inputs"
    (index_dir / "inputs").mkdir(parents=True)
    (index_dir / "inputs" / f"{instance_id}.json").write_text(
        json.dumps(
            {"instance_id": instance_id, "entry": {"file_path": file_path}},
            indent=2,
        ),
        encoding="utf-8",
    )
    return index_dir


def _solutions_json(tmp_path, records):
    path = tmp_path / "solutions.json"
    path.write_text(json.dumps(records, indent=2), encoding="utf-8")
    return path


def _routes():
    instance = load_instance(PROJECT_ROOT / "data" / "R2_T6_0.txt")
    routes = [[] for _ in range(instance.robot_count)]
    for index, task in enumerate(instance.tasks):
        routes[index % instance.robot_count].append(task.task_id)
    return routes


def test_e14_s1_solutions_stage_writes_consistent_reports(tmp_path, monkeypatch):
    monkeypatch.setattr(e14, "E10B_OUTPUT", _index_dir(tmp_path))
    routes = _routes()
    reversed_routes = [list(reversed(route)) for route in routes]
    path = _solutions_json(
        tmp_path,
        [
            {"label": "R_round_robin", "instance_id": "TEST_1", "routes": routes,
             "input_id": "I1", "fixed_destroy_hash": "h1", "solver_seed": 0},
            {"label": "R_reversed", "instance_id": "TEST_1", "routes": reversed_routes,
             "input_id": "I1", "fixed_destroy_hash": "h1", "solver_seed": 0},
        ],
    )
    output = tmp_path / "out"
    e14.stage_solutions(
        output, solutions_path=path, instance_root=PROJECT_ROOT / "data"
    )
    written = sorted(p.name for p in (output / "solutions").glob("*.json"))
    assert written == ["TEST_1__R_reversed.json", "TEST_1__R_round_robin.json"]
    for name in written:
        report = json.loads((output / "solutions" / name).read_text(encoding="utf-8"))
        assert_report_consistent(report)
        assert report["input_id"] == "I1"
        assert report["fixed_destroy_hash"] == "h1"
        assert report["solver_seed"] == 0
        assert report["label"] in {"R_round_robin", "R_reversed"}
        assert report["dp_statistics_before"]["calls"] == report["dp_statistics_after"]["calls"]


def test_e14_s2_solutions_stage_detects_report_reentering_route_dp(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(e14, "E10B_OUTPUT", _index_dir(tmp_path))
    path = _solutions_json(
        tmp_path,
        [{"label": "R1", "instance_id": "TEST_1", "routes": _routes()}],
    )
    real_report = e14.solution_state_report
    holder = {}

    def _leaky_report(instance, solution, evaluation, **kwargs):
        route_dp = holder["dp"]
        route_dp.evaluate_route(tuple(solution.routes[0]))
        return real_report(instance, solution, evaluation, **kwargs)

    real_evaluator_for = e14.evaluator_for

    def _capturing_evaluator_for(instance):
        states, cost_matrix, evaluator = real_evaluator_for(instance)
        holder["dp"] = evaluator.route_evaluator
        return states, cost_matrix, evaluator

    monkeypatch.setattr(e14, "evaluator_for", _capturing_evaluator_for)
    monkeypatch.setattr(e14, "solution_state_report", _leaky_report)
    with pytest.raises(AssertionError, match="re-entered Route-DP"):
        e14.stage_solutions(
            tmp_path / "out", solutions_path=path, instance_root=PROJECT_ROOT / "data"
        )


def test_e14_s3_verify_scans_solutions_and_unknown_instance_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(e14, "E10B_OUTPUT", _index_dir(tmp_path))
    path = _solutions_json(
        tmp_path,
        [{"label": "R1", "instance_id": "TEST_1", "routes": _routes()}],
    )
    output = tmp_path / "out"
    e14.stage_solutions(
        output, solutions_path=path, instance_root=PROJECT_ROOT / "data"
    )
    summary = e14.stage_verify(output)
    assert summary["report_count"] == 1
    assert summary["failures"] == []

    bad = _solutions_json(
        tmp_path, [{"label": "R1", "instance_id": "UNKNOWN_9", "routes": _routes()}]
    )
    with pytest.raises(SystemExit, match="unknown instance_id"):
        e14.stage_solutions(
            tmp_path / "out2", solutions_path=bad, instance_root=PROJECT_ROOT / "data"
        )
