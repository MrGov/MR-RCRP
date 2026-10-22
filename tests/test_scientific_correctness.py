from __future__ import annotations

from pathlib import Path

import pytest

from mrta_rect_coverage.config import load_config
from mrta_rect_coverage.core.cost_matrix import CostMatrix
from mrta_rect_coverage.core.dp_evaluator import RouteDPEvaluator
from mrta_rect_coverage.core.enums import Corner, SweepMode
from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.core.models import MultiRobotSolution, State
from mrta_rect_coverage.core.solution_evaluator import MultiRobotSolutionEvaluator
from mrta_rect_coverage.core.state_generator import generate_all_states
from mrta_rect_coverage.experiments import benchmark_runner
from mrta_rect_coverage.heuristics.alns_solver import ALNSConfig, ALNSSolver


def _state(
    state_id: int,
    task_id: int,
    *,
    entry_point: tuple[float, float],
    exit_point: tuple[float, float],
) -> State:
    return State(
        state_id=state_id,
        task_id=task_id,
        entry_corner=Corner.LB,
        sweep_mode=SweepMode.H,
        exit_corner=Corner.RT,
        processing_time=0.0,
        entry_point=entry_point,
        exit_point=exit_point,
        n_sweeps=1,
    )


def _write_instance(path: Path, speed_fields: str) -> None:
    path.write_text(
        f"1 1\n{speed_fields}\n10\n12\n0\n2\n",
        encoding="utf-8",
    )


def test_instance_requires_explicit_sweep_and_travel_speeds(tmp_path: Path) -> None:
    path = tmp_path / "R1_T1_0.txt"
    _write_instance(path, "1.0 2.0 4.0 0.5")

    instance = load_instance(path)

    assert instance.sweep_speed == pytest.approx(2.0)
    assert instance.speed == pytest.approx(2.0)  # Compatibility alias.
    assert instance.travel_speed == pytest.approx(4.0)


def test_legacy_implicit_travel_speed_schema_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "R1_T1_0.txt"
    _write_instance(path, "1.0 2.0 0.5")

    with pytest.raises(ValueError, match="travel_speed"):
        load_instance(path)


@pytest.mark.parametrize("travel_speed", ["0", "-1", "nan", "inf"])
def test_travel_speed_must_be_finite_and_positive(
    tmp_path: Path, travel_speed: str
) -> None:
    path = tmp_path / "R1_T1_0.txt"
    _write_instance(path, f"1.0 2.0 {travel_speed} 0.5")

    with pytest.raises(ValueError, match="travel_speed"):
        load_instance(path)


@pytest.mark.parametrize(
    ("travel_speed", "expected"),
    [(2.0, 5.0), (1.0, 10.0)],
)
def test_all_transition_types_are_travel_time(
    travel_speed: float, expected: float
) -> None:
    first = _state(1, 1, entry_point=(10.0, 0.0), exit_point=(20.0, 0.0))
    second = _state(2, 2, entry_point=(30.0, 0.0), exit_point=(10.0, 0.0))
    costs = CostMatrix(
        (0.0, 0.0),
        {1: [first], 2: [second]},
        travel_speed=travel_speed,
    )

    assert costs.depot_to_state(first.state_id) == pytest.approx(expected)
    assert costs.transition(first.state_id, second.state_id) == pytest.approx(expected)
    assert costs.state_to_depot(second.state_id) == pytest.approx(expected)


def _complete_solution_evaluator() -> MultiRobotSolutionEvaluator:
    root = Path(__file__).resolve().parents[1]
    instance = load_instance(root / "data" / "R2_T6_0.txt")
    states = generate_all_states(instance)
    costs = CostMatrix(
        instance.depot, states, travel_speed=instance.travel_speed
    )
    return MultiRobotSolutionEvaluator(
        RouteDPEvaluator(costs, states), instance=instance
    )


def test_complete_solution_contract_accepts_exact_task_universe() -> None:
    evaluator = _complete_solution_evaluator()

    evaluation = evaluator.evaluate(
        MultiRobotSolution(routes=[[1, 3, 5], [2, 4, 6]])
    )

    assert evaluation.makespan == max(evaluation.per_robot_costs)


@pytest.mark.parametrize(
    ("routes", "message"),
    [
        ([[1, 2, 3], [3, 4, 5, 6]], "duplicate"),
        ([[1, 2], [3, 4, 5]], "missing"),
        ([[1, 2, 3], [4, 5, 99]], "unknown"),
        ([[1, 2, 3, 4, 5, 6]], "route count"),
        ([[1, 2], [3, 4], [5, 6]], "route count"),
    ],
)
def test_complete_solution_contract_rejects_infeasible_routes(
    routes: list[list[int]], message: str
) -> None:
    evaluator = _complete_solution_evaluator()

    with pytest.raises(ValueError, match=message):
        evaluator.evaluate(MultiRobotSolution(routes=routes))


def test_complete_solution_contract_allows_empty_robot_route() -> None:
    evaluator = _complete_solution_evaluator()

    evaluation = evaluator.evaluate(
        MultiRobotSolution(routes=[[1, 2, 3, 4, 5, 6], []])
    )

    assert evaluation.per_robot_costs[1] == 0.0


def test_partial_solution_boundary_allows_missing_tasks_only() -> None:
    evaluator = _complete_solution_evaluator()
    partial = MultiRobotSolution(routes=[[1, 3], [2]])

    partial_evaluation = evaluator.evaluate_partial(partial)

    assert len(partial_evaluation.per_robot_costs) == 2
    with pytest.raises(ValueError, match="missing"):
        evaluator.evaluate(partial)


def _t6_instance():
    root = Path(__file__).resolve().parents[1]
    return load_instance(root / "data" / "R2_T6_0.txt")


def test_dp_aware_compatibility_alias_matches_greedy() -> None:
    solver = ALNSSolver(_t6_instance(), config=ALNSConfig(iterations=0))
    partial = MultiRobotSolution(routes=[[1, 3], [2, 4, 6]])
    partial_evaluation = solver.solution_evaluator.evaluate_partial(partial)

    greedy = solver._greedy_insertion(partial, [5], partial_evaluation)
    compatibility = solver._dp_aware_insertion(partial, [5], partial_evaluation)

    assert compatibility == greedy


def test_greedy_insertion_scores_candidates_with_route_dp(monkeypatch) -> None:
    solver = ALNSSolver(_t6_instance(), config=ALNSConfig(iterations=0))
    partial = MultiRobotSolution(routes=[[1, 3], [2, 4, 6]])
    partial_evaluation = solver.solution_evaluator.evaluate_partial(partial)
    original = solver.route_dp.evaluate_route
    evaluated_routes: list[tuple[int, ...]] = []

    def record_route(route: list[int]):
        evaluated_routes.append(tuple(route))
        return original(route)

    monkeypatch.setattr(solver.route_dp, "evaluate_route", record_route)

    repaired = solver._greedy_insertion(partial, [5], partial_evaluation)

    assert evaluated_routes
    assert sorted(task for route in repaired.routes for task in route) == [1, 2, 3, 4, 5, 6]


def test_dp_aware_alias_cannot_be_enabled_as_independent_operator() -> None:
    with pytest.raises(ValueError, match="not an independent"):
        ALNSSolver(
            _t6_instance(),
            config=ALNSConfig(iterations=0, use_dp_aware_insertion=True),
        )


def test_dp_aware_alias_is_not_a_selectable_repair_operator() -> None:
    solver = ALNSSolver(_t6_instance(), config=ALNSConfig(iterations=0))

    assert "dp_aware_insertion" not in solver.repair_ops
    assert "dp_aware_insertion" not in solver.repair_weights


def test_benchmark_modes_do_not_advertise_dp_aware_alias() -> None:
    assert "alns_dp_aware" not in benchmark_runner.ALLOWED_ABLATION_MODES


@pytest.mark.parametrize(
    "config_name", ["default.yaml", "small_demo.yaml"]
)
def test_shipped_configs_disable_dp_aware_compatibility_flag(
    config_name: str,
) -> None:
    root = Path(__file__).resolve().parents[1]

    config = load_config(root / "configs" / config_name)

    assert config.alns_use_dp_aware_insertion is False
