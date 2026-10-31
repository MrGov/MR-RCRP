"""Tests for exact incremental insertion pricing.

The contract is: every number produced here equals the number the exact route DP
produces for the same task sequence, up to floating point tolerance.  The tests
therefore compare against :class:`RouteDPEvaluator` directly instead of asserting
hand-computed values.
"""
from __future__ import annotations

import random
from pathlib import Path

import pytest

from mrta_rect_coverage.core.cost_matrix import CostMatrix
from mrta_rect_coverage.core.dp_evaluator import RouteDPEvaluator
from mrta_rect_coverage.core.incremental_route import (
    DEFAULT_CACHE_LIMIT,
    RouteIncrementalEvaluator,
)
from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.core.state_generator import generate_all_states

DATA = Path(__file__).resolve().parents[1] / "data"
TOL = 1e-9


def _setup(name="R4_T40_0.txt"):
    instance = load_instance(DATA / name)
    states = generate_all_states(instance)
    costs = CostMatrix(instance.depot, states, travel_speed=instance.travel_speed)
    route_dp = RouteDPEvaluator(costs, states)
    incremental = RouteIncrementalEvaluator(costs, states)
    return instance, states, costs, route_dp, incremental


def _random_routes(instance, count, *, seed=0, max_length=None):
    rng = random.Random(seed)
    task_ids = [task.task_id for task in instance.tasks]
    routes = []
    for _ in range(count):
        length = rng.randint(1, min(max_length or len(task_ids), len(task_ids)))
        routes.append(rng.sample(task_ids, length))
    return routes


def _dp_cost(route_dp, route):
    if not route:
        return 0.0
    return route_dp.evaluate_route(list(route)).total_cost


# I1: the cost of a fixed route equals the route DP optimum.
def test_route_cost_matches_route_dp():
    instance, _, _, route_dp, incremental = _setup()
    routes = [[], *([task.task_id] for task in instance.tasks[:3]), *_random_routes(instance, 6)]
    for route in routes:
        assert incremental.route_cost(route) == pytest.approx(
            _dp_cost(route_dp, route), abs=TOL
        ), route


# I2: every insertion slot is priced exactly as the full route DP would price it.
def test_insertion_costs_match_full_route_dp_for_every_slot():
    instance, _, _, route_dp, incremental = _setup()
    routes = _random_routes(instance, 4, seed=11, max_length=6)
    for route in routes:
        for task_id in instance.tasks:
            if task_id.task_id in route:
                continue
            priced = incremental.insertion_costs(route, task_id.task_id)
            assert len(priced) == len(route) + 1
            for position, value in enumerate(priced):
                candidate = list(route[:position]) + [task_id.task_id] + list(route[position:])
                expected = _dp_cost(route_dp, candidate)
                assert value == pytest.approx(expected, abs=TOL), (route, position, value, expected)


# I3: best_insertion returns the argmin slot, first slot on ties.
def test_best_insertion_returns_cheapest_slot_and_cost():
    instance, _, _, route_dp, incremental = _setup()
    route = _random_routes(instance, 1, seed=5, max_length=4)[0]
    task_id = next(task.task_id for task in instance.tasks if task.task_id not in route)
    position, cost = incremental.best_insertion(route, task_id)
    priced = incremental.insertion_costs(route, task_id)
    assert cost == min(priced)
    assert position == min(index for index, value in enumerate(priced) if value == cost)
    candidate = list(route[:position]) + [task_id] + list(route[position:])
    assert cost == pytest.approx(_dp_cost(route_dp, candidate), abs=TOL)


# I4: inserting into an empty route reproduces the single-task route cost.
def test_insertion_into_empty_route():
    instance, _, _, route_dp, incremental = _setup()
    task_id = instance.tasks[0].task_id
    priced = incremental.insertion_costs([], task_id)
    assert len(priced) == 1
    assert priced[0] == pytest.approx(_dp_cost(route_dp, [task_id]), abs=TOL)
    assert incremental.route_cost([]) == 0.0


# I5: repeated pricing of one route rebuilds its tables once and stays stable.
def test_tables_are_built_once_and_results_are_stable():
    instance, _, _, _, incremental = _setup()
    route = _random_routes(instance, 1, seed=3, max_length=5)[0]
    task_id = next(task.task_id for task in instance.tasks if task.task_id not in route)
    first = incremental.insertion_costs(route, task_id)
    second = incremental.insertion_costs(route, task_id)
    assert first == second
    assert incremental.statistics()["table_builds"] == 1
    assert incremental.statistics()["cached_routes"] == 1
    incremental.clear_cache()
    assert incremental.insertion_costs(route, task_id) == first
    assert incremental.statistics()["table_builds"] == 2


# I6: unknown identifiers fail loudly instead of silently pricing something else.
def test_unknown_task_raises():
    _, _, _, _, incremental = _setup()
    with pytest.raises(ValueError):
        incremental.insertion_costs([], 10_000)
    with pytest.raises(ValueError):
        incremental.insertion_costs([10_000], 1)


# I7: pricing is deterministic across instances of the evaluator.
def test_pricing_is_deterministic():
    instance, states, costs, _, _ = _setup()
    route = _random_routes(instance, 1, seed=9, max_length=5)[0]
    task_id = next(task.task_id for task in instance.tasks if task.task_id not in route)
    left = RouteIncrementalEvaluator(costs, states).insertion_costs(route, task_id)
    right = RouteIncrementalEvaluator(costs, states).insertion_costs(route, task_id)
    assert left == right


# I8: pricing never touches the route DP, so the DP statistics stay untouched.
def test_pricing_does_not_call_the_route_dp():
    instance, _, _, route_dp, incremental = _setup()
    route = _random_routes(instance, 1, seed=2, max_length=5)[0]
    task_id = next(task.task_id for task in instance.tasks if task.task_id not in route)
    before = dict(route_dp.statistics())
    incremental.insertion_costs(route, task_id)
    after = dict(route_dp.statistics())
    assert before["calls"] == after["calls"] == 0
    assert after["cache_misses"] == 0


# I9: the cache is bounded, and a full cache does not change any value.
def test_cache_limit_does_not_change_values():
    instance, states, costs, route_dp, _ = _setup()
    bounded = RouteIncrementalEvaluator(costs, states, cache_limit=1)
    routes = _random_routes(instance, 3, seed=4, max_length=4)
    task_id = next(task.task_id for task in instance.tasks if task.task_id not in routes[0])
    for route in routes:
        for position, value in enumerate(bounded.insertion_costs(route, task_id)):
            candidate = list(route[:position]) + [task_id] + list(route[position:])
            assert value == pytest.approx(_dp_cost(route_dp, candidate), abs=TOL)
    assert bounded.statistics()["cached_routes"] <= 1
    assert DEFAULT_CACHE_LIMIT > 0


# I10: a longer route keeps every slot exact (length-independence of the formula).
def test_long_route_slots_are_exact():
    instance, _, _, route_dp, incremental = _setup("R2_T10_0.txt")
    task_ids = [task.task_id for task in instance.tasks]
    route = task_ids[: len(task_ids) - 2]
    task_id = task_ids[-1]
    priced = incremental.insertion_costs(route, task_id)
    for position, value in enumerate(priced):
        candidate = list(route[:position]) + [task_id] + list(route[position:])
        assert value == pytest.approx(_dp_cost(route_dp, candidate), abs=TOL)
