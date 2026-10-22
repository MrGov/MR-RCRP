from __future__ import annotations

from pathlib import Path

from mrta_rect_coverage.core.cost_matrix import CostMatrix
from mrta_rect_coverage.core.dp_evaluator import RouteDPEvaluator
from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.core.solution_evaluator import MultiRobotSolutionEvaluator
from mrta_rect_coverage.core.state_generator import generate_all_states
from mrta_rect_coverage.heuristics.local_search import run_stronger_local_search


def test_stronger_local_search_keeps_solution_feasible() -> None:
    project_root = Path(__file__).resolve().parents[1]
    instance = load_instance(project_root / "data" / "R2_T6_0.txt")
    states_by_task = generate_all_states(instance)
    cost_matrix = CostMatrix(
        instance.depot, states_by_task, travel_speed=instance.travel_speed
    )
    route_dp = RouteDPEvaluator(cost_matrix, states_by_task)
    evaluator = MultiRobotSolutionEvaluator(route_dp, instance=instance)

    solution = MultiRobotSolution(routes=[[1, 3, 5], [2, 4, 6]])
    improved, evaluation = run_stronger_local_search(solution, evaluator, max_iterations=10)

    assigned = sorted(task for route in improved.routes for task in route)
    assert assigned == [1, 2, 3, 4, 5, 6]
    assert evaluation.makespan >= 0
