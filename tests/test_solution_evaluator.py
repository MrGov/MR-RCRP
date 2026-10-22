from __future__ import annotations

from pathlib import Path

from mrta_rect_coverage.core.cost_matrix import CostMatrix
from mrta_rect_coverage.core.dp_evaluator import RouteDPEvaluator
from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.core.solution_evaluator import MultiRobotSolutionEvaluator
from mrta_rect_coverage.core.state_generator import generate_all_states


def _build_solution_evaluator():
    project_root = Path(__file__).resolve().parents[1]
    instance_path = project_root / "data" / "R2_T6_0.txt"
    instance = load_instance(instance_path)
    states_by_task = generate_all_states(instance)
    cost_matrix = CostMatrix(
        instance.depot, states_by_task, travel_speed=instance.travel_speed
    )
    route_dp = RouteDPEvaluator(cost_matrix, states_by_task)
    evaluator = MultiRobotSolutionEvaluator(route_dp, instance=instance)
    return evaluator


def test_makespan_is_max_cost() -> None:
    evaluator = _build_solution_evaluator()
    solution = MultiRobotSolution(routes=[[1, 3, 5], [2, 4, 6]])
    evaluation = evaluator.evaluate(solution)
    assert evaluation.makespan == max(evaluation.per_robot_costs)


def test_empty_routes_handled() -> None:
    evaluator = _build_solution_evaluator()
    solution = MultiRobotSolution(routes=[[], []])
    evaluation = evaluator.evaluate_partial(solution)
    assert evaluation.makespan == 0
    assert evaluation.per_robot_costs == [0, 0]


def test_multi_robot_solution_evaluates() -> None:
    evaluator = _build_solution_evaluator()
    solution = MultiRobotSolution(routes=[[1, 3, 5], [2, 4, 6]])
    evaluation = evaluator.evaluate(solution)
    assert len(evaluation.per_robot_costs) == 2
    assert evaluation.makespan >= 0
