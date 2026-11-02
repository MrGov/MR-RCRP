"""Vector/scalar price-cache equivalence and separate logical/computation counts."""
from dataclasses import replace
from pathlib import Path

import pytest

from mrta_rect_coverage.core.cost_matrix import CostMatrix
from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.core.incremental_route import RouteIncrementalEvaluator
from mrta_rect_coverage.core.dp_evaluator import RouteDPEvaluator
from mrta_rect_coverage.core.state_generator import generate_all_states

ROOT = Path(__file__).resolve().parents[1]


def make(speed=1.):
    instance = replace(load_instance(ROOT/'data/structural_benchmark_v1/development/SPATIAL/R2_T20_0.txt'), travel_speed=speed)
    states = generate_all_states(instance)
    matrix = CostMatrix(instance.depot, states, travel_speed=speed)
    return RouteIncrementalEvaluator(matrix, states), RouteDPEvaluator(matrix, states)


def test_vector_prices_reuse_scalar_cache_and_preserve_order():
    p, dp = make()
    route, task = [1, 4, 8], 2
    scalar = p.insertion_cost_at(p.tables(route), 1, task)
    actual = p.insertion_costs(route, task)
    assert actual[1] == scalar
    assert actual == [dp.evaluate_route(route[:i]+[task]+route[i:]).total_cost for i in range(4)]
    assert p.insertion_costs(route, task) == actual
    stats = p.statistics()
    assert stats['insertion_requests'] == 9
    assert stats['insertion_cache_hits'] == 5
    assert stats['insertion_computations'] == 4
    assert stats['table_builds'] == 1
    assert stats['table_build_seconds'] >= 0
    assert stats['insertion_compute_seconds'] >= 0
    assert p.best_insertion(route, task) == (actual.index(min(actual)), min(actual))


def test_uncached_reference_capacity_clear_and_instance_identity():
    p, _ = make()
    q, dpq = make(speed=2.)
    route, task = [1, 4, 8], 2
    expected = p.insertion_costs_uncached(route, task)
    assert p.insertion_costs(route, task) == expected
    other = q.insertion_costs(route, task)
    assert other != expected
    assert other == [dpq.evaluate_route(route[:i]+[task]+route[i:]).total_cost for i in range(4)]
    p._price_cache_limit = 2  # exercise existing generational capacity, no new cache policy
    p.clear_cache()
    assert p.insertion_costs(route, task) == expected
    assert p.statistics()['cached_prices'] <= 2
    p.clear_cache()
    assert p.statistics()['cached_prices'] == p.statistics()['cached_routes'] == 0
    assert p.insertion_costs(route, task) == expected
    stats = p.statistics()
    assert stats['insertion_requests'] == stats['insertion_computations'] + stats['insertion_cache_hits']


def test_task_route_position_keys_do_not_alias():
    p, dp = make()
    for route in ([1,4,8], [8,4,1], [1,4], []):
        for task in (2,3):
            expected = [dp.evaluate_route(list(route[:i])+[task]+list(route[i:])).total_cost for i in range(len(route)+1)]
            assert p.insertion_costs(route, task) == expected
            assert p.insertion_costs(route, task) == expected
    before = p.statistics()
    with pytest.raises(ValueError):
        p.insertion_costs([], 9999)
    assert p.statistics()['insertion_requests'] == before['insertion_requests']
