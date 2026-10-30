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
