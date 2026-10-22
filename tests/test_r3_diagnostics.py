from __future__ import annotations

import json
from pathlib import Path

import pytest

from mrta_rect_coverage.core.cost_matrix import CostMatrix
from mrta_rect_coverage.core.dp_evaluator import RouteDPEvaluator
from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.core.solution_evaluator import MultiRobotSolutionEvaluator
from mrta_rect_coverage.core.state_generator import generate_all_states
from mrta_rect_coverage.experiments.dataset_protocol import extract_intrinsic_features
from mrta_rect_coverage.experiments.r3_diagnostics import (
    DIAGNOSTIC_SCHEMA_VERSION,
    classify_solution_change,
    objective_decomposition,
    route_balance_metrics,
    run_diagnostic_alns,
    state_chain_diff,
    state_chain_signatures,
    write_diagnostic_outputs,
)
from mrta_rect_coverage.heuristics.alns_solver import ALNSConfig


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _fixture():
    instance = load_instance(PROJECT_ROOT / "data" / "R2_T6_0.txt")
    states = generate_all_states(instance)
    route_dp = RouteDPEvaluator(
        CostMatrix(instance.depot, states, travel_speed=instance.travel_speed),
        states,
    )
    evaluator = MultiRobotSolutionEvaluator(route_dp, instance=instance)
    solution = MultiRobotSolution(routes=[[1, 3, 5], [2, 4, 6]])
    return instance, route_dp, evaluator, solution, evaluator.evaluate(solution)


def test_intrinsic_feature_contract_covers_r3_structure() -> None:
    instance, _, _, _, _ = _fixture()
    features = extract_intrinsic_features(instance)
    required = {
        "task_centroid_x", "task_centroid_y", "centroid_distance_mean",
        "centroid_distance_max", "pairwise_distance_mean", "pairwise_distance_std",
        "pairwise_distance_max", "width_min", "width_max", "height_min", "height_max",
        "aspect_ratio_min", "aspect_ratio_max", "relative_hv_gap_mean",
        "fraction_H_preferred", "fraction_V_preferred", "fraction_near_tie",
        "sum_p_min", "mean_p_min", "std_p_min", "max_p_min",
        "processing_load_lb", "heavy_task_ratio", "state_variability_mean",
        "state_variability_std", "state_variability_max",
    }
    assert required <= features.keys()
    assert features["near_tie_threshold"] == pytest.approx(0.05)
    assert features["processing_load_lb"] == pytest.approx(
        features["sum_p_min"] / instance.robot_count
    )


def test_route_balance_formulas() -> None:
    metrics = route_balance_metrics([10.0, 6.0, 4.0], [4, 2, 1])
    assert metrics["max_route_cost"] == 10.0
    assert metrics["second_max_route_cost"] == 6.0
    assert metrics["mean_route_cost"] == pytest.approx(20.0 / 3.0)
    assert metrics["bottleneck_gap_abs"] == 4.0
    assert metrics["bottleneck_gap_rel"] == pytest.approx(0.4)
    assert metrics["route_task_count_std"] > 0


def test_objective_decomposition_reconciles_route_costs() -> None:
    instance, _, _, _, evaluation = _fixture()
    components = objective_decomposition(instance, evaluation)
    expected = sum(evaluation.per_robot_costs)
    assert components["travel_time"] + components["coverage_traversal_time"] + components["turning_time"] == pytest.approx(expected)
    assert components["travel_share"] + components["coverage_share"] + components["turning_share"] == pytest.approx(1.0)


def test_assignment_and_ordering_classification() -> None:
    before = MultiRobotSolution(routes=[[1, 2], [3, 4]])
    assert classify_solution_change(before, MultiRobotSolution(routes=[[2, 1], [3, 4]])) == "ordering"
    assert classify_solution_change(before, MultiRobotSolution(routes=[[1], [3, 2, 4]])) == "assignment"
    assert classify_solution_change(before, MultiRobotSolution(routes=[[1, 2], [3, 4]])) == "unchanged"


def test_state_chain_diff_separates_direct_and_cascade_changes() -> None:
    before = {1: ("H", "LB", "RT"), 2: ("H", "LT", "RB"), 3: ("V", "LB", "RT")}
    after = {1: ("V", "LB", "RT"), 2: ("H", "RB", "LT"), 3: ("V", "LB", "RT")}
    diff = state_chain_diff(before, after, affected_task_ids={1, 2, 3}, directly_moved_task_ids={1})
    assert diff["state_changed_count"] == 2
    assert diff["mode_switch_count"] == 1
    assert diff["entry_corner_changed_count"] == 1
    assert diff["indirect_state_changed_tasks"] == 1
    assert diff["dp_cascade_ratio"] == pytest.approx(0.5)


def test_route_dp_reports_cache_workload() -> None:
    _, route_dp, _, _, _ = _fixture()
    before = route_dp.statistics()
    route_dp.evaluate_route([1, 2, 3])
    route_dp.evaluate_route([1, 2, 3])
    after = route_dp.statistics()
    assert after["calls"] - before["calls"] == 2
    assert after["cache_misses"] - before["cache_misses"] == 1
    assert after["cache_hits"] - before["cache_hits"] == 1
    assert 0.0 <= after["cache_hit_rate"] <= 1.0


def test_diagnostic_alns_records_attribution_and_dp_behavior() -> None:
    instance, _, _, _, _ = _fixture()
    run = run_diagnostic_alns(
        instance,
        source_track="A",
        family_id=None,
        config=ALNSConfig(iterations=3, acceptance="simulated_annealing", random_seed=0),
    )
    assert run["diagnostic_schema_version"] == DIAGNOSTIC_SCHEMA_VERSION
    assert run["solver_seed"] == 0
    assert run["run_id"].startswith("A-R2_T6_0-seed-0-")
    assert len(run["iterations"]) == 3
    required = {
        "objective_before_move", "objective_after_repair", "objective_after_local_search",
        "repair_change_class", "local_search_change_class", "local_search_gain",
        "accepted", "best_update", "bottleneck_relief", "state_changed_count",
        "indirect_state_changed_tasks", "dp_cascade_ratio", "dp_calls",
        "dp_cache_hits", "dp_cache_misses",
    }
    assert required <= run["iterations"][0].keys()
    assert run["provider_used"] is False
    assert run["generated_operator_used"] is False


def test_diagnostic_serialization_is_versioned_and_has_no_llm_fields(tmp_path: Path) -> None:
    instance, _, _, _, evaluation = _fixture()
    run = {
        "diagnostic_schema_version": DIAGNOSTIC_SCHEMA_VERSION,
        "run_id": "run-1", "instance_id": instance.name, "source_track": "A",
        "family_id": None, "replicate_id": 0, "n_robots": 2, "n_tasks": 6,
        "solver_seed": 0, "solver_config_hash": "0" * 64, "status": "completed",
        "initial_makespan": evaluation.makespan, "best_makespan": evaluation.makespan,
        "final_makespan": evaluation.makespan, "runtime_sec": 0.1, "iterations": [],
        "provider_used": False, "generated_operator_used": False,
    }
    paths = write_diagnostic_outputs(tmp_path, runs=[run], instance_rows=[])
    metadata = json.loads(paths["metadata"].read_text(encoding="utf-8"))
    assert metadata["diagnostic_schema_version"] == DIAGNOSTIC_SCHEMA_VERSION
    text = paths["run_metrics"].read_text(encoding="utf-8").lower()
    assert "llm" not in text
