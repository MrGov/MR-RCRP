"""Tests for the table-priced local search and its exact removal/replacement prices."""
from __future__ import annotations

import random
from pathlib import Path
from typing import List

import pytest

from mrta_rect_coverage.core.cost_matrix import CostMatrix
from mrta_rect_coverage.core.dp_evaluator import RouteDPEvaluator
from mrta_rect_coverage.core.incremental_route import RouteIncrementalEvaluator
from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.core.solution_evaluator import MultiRobotSolutionEvaluator
from mrta_rect_coverage.core.state_generator import generate_all_states
from mrta_rect_coverage.heuristics.alns_solver import ALNSConfig, ALNSSolver
from mrta_rect_coverage.heuristics.local_search import run_stronger_local_search
from mrta_rect_coverage.heuristics.priced_local_search import run_priced_local_search

TOL = 1e-9
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA = PROJECT_ROOT / "data"


def _setup(name: str):
    instance = load_instance(DATA / name)
    states = generate_all_states(instance)
    costs = CostMatrix(instance.depot, states, travel_speed=instance.travel_speed)
    route_dp = RouteDPEvaluator(costs, states)
    pricer = RouteIncrementalEvaluator(costs, states)
    evaluator = MultiRobotSolutionEvaluator(route_dp, instance=instance)
    return instance, states, costs, route_dp, pricer, evaluator


def _start_solutions(instance, *, count: int = 3) -> List[MultiRobotSolution]:
    task_ids = [task.task_id for task in instance.tasks]
    robots = instance.robot_count
    routes: List[List[int]] = [[] for _ in range(robots)]
    for position, task_id in enumerate(task_ids):
        routes[position % robots].append(task_id)
    solutions = [MultiRobotSolution(routes=[list(route) for route in routes])]

    rng = random.Random(20261107)
    for _ in range(count - 1):
        pool = list(task_ids)
        rng.shuffle(pool)
        shuffled: List[List[int]] = [[] for _ in range(robots)]
        for position, task_id in enumerate(pool):
            shuffled[position % robots].append(task_id)
        # keep one route empty sometimes so empty-route handling is exercised
        if rng.random() < 0.5 and robots > 1:
            donor = rng.randrange(robots)
            moved = shuffled[donor]
            shuffled[donor] = []
            for offset, task_id in enumerate(moved):
                shuffled[(donor + 1 + offset) % robots].append(task_id)
        solutions.append(MultiRobotSolution(routes=shuffled))
    return solutions


INSTANCES = ("R2_T6_0.txt", "R2_T10_0.txt", "R4_T40_0.txt")


@pytest.mark.parametrize("name", INSTANCES)
def test_removal_price_matches_route_dp_for_every_position(name: str) -> None:
    instance, _, _, route_dp, pricer, _ = _setup(name)
    task_ids = [task.task_id for task in instance.tasks]
    route = task_ids[: min(len(task_ids), 8)]
    for position in range(len(route)):
        expected = route_dp.evaluate_route(
            [task_id for index, task_id in enumerate(route) if index != position]
        ).total_cost
        assert pricer.route_cost_without(route, position) == pytest.approx(expected, abs=TOL)


@pytest.mark.parametrize("name", INSTANCES)
def test_replacement_price_matches_route_dp_for_every_position(name: str) -> None:
    instance, _, _, route_dp, pricer, _ = _setup(name)
    task_ids = [task.task_id for task in instance.tasks]
    route = task_ids[: min(len(task_ids) - 1, 6)]
    spare = task_ids[-1]
    assert spare not in route
    for position in range(len(route)):
        replaced = list(route)
        replaced[position] = spare
        expected = route_dp.evaluate_route(replaced).total_cost
        assert pricer.route_cost_replaced(route, position, spare) == pytest.approx(expected, abs=TOL)


def test_removal_and_replacement_reject_bad_arguments() -> None:
    _, _, _, _, pricer, _ = _setup("R2_T6_0.txt")
    with pytest.raises(ValueError):
        pricer.route_cost_without([], 0)
    with pytest.raises(ValueError):
        pricer.route_cost_without([1, 2], 5)
    with pytest.raises(ValueError):
        pricer.route_cost_replaced([1, 2], 0, 999)


@pytest.mark.parametrize("name", INSTANCES)
def test_priced_search_matches_reference_decisions(name: str) -> None:
    """The priced scan must return exactly the solution the reference scan returns."""

    instance, _, _, _, pricer, evaluator = _setup(name)
    for solution in _start_solutions(instance):
        reference, reference_evaluation = run_stronger_local_search(
            solution, evaluator, max_iterations=1
        )
        priced, priced_evaluation = run_priced_local_search(
            solution, evaluator, pricer, max_iterations=1
        )
        assert priced.routes == reference.routes
        assert priced_evaluation.makespan == pytest.approx(reference_evaluation.makespan, abs=TOL)


@pytest.mark.parametrize("name", INSTANCES)
def test_priced_search_matches_reference_over_multiple_iterations(name: str) -> None:
    instance, _, _, _, pricer, evaluator = _setup(name)
    for solution in _start_solutions(instance):
        reference, _ = run_stronger_local_search(solution, evaluator, max_iterations=4)
        priced, _ = run_priced_local_search(solution, evaluator, pricer, max_iterations=4)
        assert priced.routes == reference.routes


def test_priced_search_is_deterministic() -> None:
    instance, _, _, _, pricer, evaluator = _setup("R4_T40_0.txt")
    solution = _start_solutions(instance)[1]
    first, first_evaluation = run_priced_local_search(solution, evaluator, pricer, max_iterations=2)
    second, second_evaluation = run_priced_local_search(solution, evaluator, pricer, max_iterations=2)
    assert first.routes == second.routes
    assert first_evaluation.makespan == second_evaluation.makespan


@pytest.mark.parametrize("name", INSTANCES)
def test_priced_search_never_worsens_the_solution(name: str) -> None:
    instance, _, _, _, pricer, evaluator = _setup(name)
    for solution in _start_solutions(instance):
        before = evaluator.evaluate(solution).makespan
        _, after = run_priced_local_search(solution, evaluator, pricer, max_iterations=3)
        assert after.makespan <= before + TOL


def test_priced_search_handles_empty_and_single_task_routes() -> None:
    instance, _, _, _, pricer, evaluator = _setup("R2_T6_0.txt")
    task_ids = [task.task_id for task in instance.tasks]
    solution = MultiRobotSolution(routes=[task_ids[:1], task_ids[1:]])
    reference, reference_evaluation = run_stronger_local_search(solution, evaluator, max_iterations=2)
    priced, priced_evaluation = run_priced_local_search(solution, evaluator, pricer, max_iterations=2)
    assert priced.routes == reference.routes
    assert priced_evaluation.makespan == pytest.approx(reference_evaluation.makespan, abs=TOL)


def test_priced_search_leaves_each_task_exactly_once() -> None:
    instance, _, _, _, pricer, evaluator = _setup("R4_T40_0.txt")
    expected = sorted(task.task_id for task in instance.tasks)
    for solution in _start_solutions(instance):
        priced, _ = run_priced_local_search(solution, evaluator, pricer, max_iterations=2)
        found = sorted(task_id for route in priced.routes for task_id in route)
        assert found == expected


def test_initial_evaluation_argument_is_respected() -> None:
    instance, _, _, _, pricer, evaluator = _setup("R2_T10_0.txt")
    solution = _start_solutions(instance)[0]
    evaluation = evaluator.evaluate(solution)
    priced, priced_evaluation = run_priced_local_search(
        solution, evaluator, pricer, max_iterations=1, initial_evaluation=evaluation
    )
    reference, reference_evaluation = run_stronger_local_search(solution, evaluator, max_iterations=1)
    assert priced.routes == reference.routes
    assert priced_evaluation.makespan == pytest.approx(reference_evaluation.makespan, abs=TOL)


def _solver(name: str, *, priced: bool):
    instance = load_instance(DATA / name)
    config = ALNSConfig.enhanced(
        iterations=8,
        cooling_schedule="iteration",
        random_seed=3,
        priced_local_search=priced,
    )
    return ALNSSolver(instance, constructor="spatial_sort", config=config)


@pytest.mark.parametrize("name", ("R2_T6_0.txt", "R2_T20_0.txt"))
def test_alns_decisions_are_identical_with_priced_local_search(name: str) -> None:
    """Turning the switch on must reproduce the reference run decision for decision."""

    reference = _solver(name, priced=False).solve()
    priced = _solver(name, priced=True).solve()
    assert priced.best_evaluation.makespan == pytest.approx(
        reference.best_evaluation.makespan, abs=TOL
    )
    assert priced.best_solution.routes == reference.best_solution.routes
    reference_trace = [
        (row["destroy"], row["repair"], round(row["best_makespan"], 9), row["accepted"])
        for row in reference.iteration_history
    ]
    priced_trace = [
        (row["destroy"], row["repair"], round(row["best_makespan"], 9), row["accepted"])
        for row in priced.iteration_history
    ]
    assert priced_trace == reference_trace

