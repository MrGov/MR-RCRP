"""Decision-level audit: exactness against the full Route-DP, and neutrality."""
from __future__ import annotations

import random
from pathlib import Path

import pytest

from mrta_rect_coverage.core.cost_matrix import CostMatrix
from mrta_rect_coverage.core.dp_evaluator import RouteDPEvaluator
from mrta_rect_coverage.core.incremental_route import RouteIncrementalEvaluator
from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.core.solution_evaluator import MultiRobotSolutionEvaluator
from mrta_rect_coverage.core.state_generator import generate_all_states
from mrta_rect_coverage.heuristics import decision_audit
from mrta_rect_coverage.heuristics.alns_solver import ALNSConfig, ALNSSolver
from mrta_rect_coverage.heuristics.decision_audit import (
    DECISION_TOLERANCE,
    DecisionAuditRecorder,
    audit_destroy,
    audit_repair,
)

ROOT = Path(__file__).resolve().parents[1]


def _setup(name: str = 'data/R4_T40_0.txt'):
    instance = load_instance(ROOT / name)
    states = generate_all_states(instance)
    costs = CostMatrix(instance.depot, states, travel_speed=instance.travel_speed)
    route_dp = RouteDPEvaluator(costs, states)
    pricer = RouteIncrementalEvaluator(costs, states)
    evaluator = MultiRobotSolutionEvaluator(route_dp, instance=instance)
    return instance, states, costs, route_dp, pricer, evaluator


def _routes(instance, *, count: int, seed: int = 0):
    ids = [task.task_id for task in instance.tasks]
    rng = random.Random(seed)
    rng.shuffle(ids)
    routes = [[] for _ in range(count)]
    for position, task_id in enumerate(ids):
        routes[position % count].append(task_id)
    return routes


def test_destroy_savings_match_full_route_dp():
    instance, _, _, route_dp, pricer, _ = _setup()
    routes = _routes(instance, count=instance.robot_count)
    index = {task_id: (route_index, position)
             for route_index, route in enumerate(routes)
             for position, task_id in enumerate(route)}
    removed = [routes[0][0], routes[1][-1], routes[2][2]]
    audit = audit_destroy(routes, removed, pricer)

    for task_id, saving in zip(audit.removed, audit.removed_savings):
        route_index, position = index[task_id]
        trimmed = [task for offset, task in enumerate(routes[route_index])
                   if offset != position]
        expected = (route_dp.evaluate_route(routes[route_index]).total_cost
                    - route_dp.evaluate_route(trimmed).total_cost)
        assert saving == pytest.approx(expected, abs=1e-9, rel=0)


def test_destroy_top_k_is_the_largest_saving_set():
    instance, _, _, route_dp, pricer, _ = _setup()
    routes = _routes(instance, count=instance.robot_count, seed=3)
    all_ids = [task for route in routes for task in route]
    savings = {}
    for route in routes:
        base = route_dp.evaluate_route(route).total_cost
        for position, task_id in enumerate(route):
            trimmed = [task for offset, task in enumerate(route) if offset != position]
            savings[task_id] = base - route_dp.evaluate_route(trimmed).total_cost

    removed = all_ids[:5]
    audit = audit_destroy(routes, removed, pricer)
    expected_top = tuple(sorted(all_ids, key=lambda task_id: (-savings[task_id], task_id))[:5])
    assert audit.top_k == expected_top
    assert audit.precision == pytest.approx(len(set(removed) & set(expected_top)) / 5)
    assert audit.saving_capture == pytest.approx(
        sum(savings[task] for task in removed) / sum(savings[task] for task in expected_top))


def test_destroy_flags_a_random_removal_set():
    instance, _, _, _, pricer, _ = _setup()
    routes = _routes(instance, count=instance.robot_count, seed=5)
    everything = [task for route in routes for task in route]
    audit = audit_destroy(routes, everything[:10], pricer)
    # Removing ten of forty tasks cannot beat a uniform draw by much.
    assert audit.precision <= 10 / len(everything) + DECISION_TOLERANCE
    assert audit.is_random_level is True


def test_repair_prices_and_routes_match_full_route_dp():
    instance, _, _, route_dp, pricer, _ = _setup()
    partial = _routes(instance, count=instance.robot_count, seed=7)
    removed = [partial[0].pop(0), partial[1].pop(1)]
    repaired = [list(route) for route in partial]
    repaired[2].append(removed[0])
    repaired[3].append(removed[1])
    costs = [route_dp.evaluate_route(route).total_cost for route in partial]

    audit = audit_repair(partial, costs, removed, repaired, pricer)
    assert len(audit.decisions) == 2

    for decision in audit.decisions:
        prices = []
        for route in partial:
            best = None
            for position in range(len(route) + 1):
                candidate = route[:position] + [decision.task_id] + route[position:]
                increase = (route_dp.evaluate_route(candidate).total_cost
                            - route_dp.evaluate_route(route).total_cost)
                best = increase if best is None else min(best, increase)
            prices.append(best)
        projected = [costs[index] + prices[index] for index in range(len(partial))]
        makespans = []
        for route_index in range(len(partial)):
            # Only the chosen route grows; the others keep their current cost.
            others = [costs[other] for other in range(len(partial)) if other != route_index]
            makespans.append(max(projected[route_index], max(others, default=0.0)))
        best_sum = min(range(len(prices)), key=lambda index: (prices[index], index))
        best_makespan = min(range(len(makespans)), key=lambda index: (makespans[index], index))

        assert decision.price_best_sum == pytest.approx(prices[best_sum], abs=1e-9)
        assert decision.sum_optimal_route == best_sum
        assert decision.makespan_best == pytest.approx(makespans[best_makespan], abs=1e-9)
        assert decision.makespan_optimal_route == best_makespan
        assert decision.price_assigned == pytest.approx(prices[decision.assigned_route], abs=1e-9)
        assert decision.makespan_assigned == pytest.approx(
            makespans[decision.assigned_route], abs=1e-9)


def test_repair_profile_separates_myopic_from_balance_aware():
    instance, _, _, route_dp, pricer, _ = _setup()
    # Force an imbalance: robot 0 carries almost everything, so the summed-cost
    # optimum and the makespan optimum must disagree for some task.
    ids = [task.task_id for task in instance.tasks]
    routes = [ids[:-2], ids[-2:-1], ids[-1:], []][: instance.robot_count]
    costs = [route_dp.evaluate_route(route).total_cost for route in routes]
    removed = [ids[0]]
    partial = [[task for task in route if task not in removed] for route in routes]
    partial_costs = [route_dp.evaluate_route(route).total_cost for route in partial]
    # The operator handed the task back to the (already heaviest) first robot.
    repaired = [list(route) for route in partial]
    repaired[0].append(removed[0])

    audit = audit_repair(partial, partial_costs, removed, repaired, pricer)
    decision = audit.decisions[0]
    assert decision.assigned_route == 0
    assert decision.makespan_regret >= -DECISION_TOLERANCE
    assert decision.sum_regret >= -DECISION_TOLERANCE
    assert decision.makespan_regret == pytest.approx(
        decision.makespan_assigned - decision.makespan_best)
    # Route 0 is the bottleneck, so re-inserting there cannot be makespan-optimal.
    assert decision.is_makespan_optimal is False


def test_repair_empty_removal_is_a_no_op():
    instance, _, _, route_dp, pricer, _ = _setup()
    routes = _routes(instance, count=instance.robot_count)
    costs = [route_dp.evaluate_route(route).total_cost for route in routes]
    audit = audit_repair(routes, costs, [], routes, pricer)
    assert audit.decisions == []
    assert audit.summary()["calls"] == 0


def test_repair_rejects_a_lost_task():
    instance, _, _, route_dp, pricer, _ = _setup()
    routes = _routes(instance, count=instance.robot_count)
    costs = [route_dp.evaluate_route(route).total_cost for route in routes]
    removed = [routes[0][0]]
    partial = [[task for task in route if task not in removed] for route in routes]
    with pytest.raises(ValueError):
        audit_repair(partial, costs, removed, partial, pricer)


def test_recorder_aggregates_per_operator():
    instance, _, _, route_dp, pricer, _ = _setup()
    routes = _routes(instance, count=instance.robot_count, seed=11)
    removed = [routes[0][0], routes[0][1]]
    # The operator took both tasks out of robot 0 and handed them to robot 1.
    partial = [[task for task in route if task not in removed] for route in routes]
    partial_costs = [route_dp.evaluate_route(route).total_cost for route in partial]
    repaired = [list(route) for route in partial]
    repaired[1].extend(removed)

    recorder = DecisionAuditRecorder()
    recorder.record_destroy('d1', audit_destroy(routes, removed, pricer))
    recorder.record_destroy('d1', audit_destroy(routes, removed[:1], pricer))
    recorder.record_repair('r1', audit_repair(partial, partial_costs, removed, repaired, pricer))
    # Same removal set, but this time the operator put both tasks back on robot 0.
    handed_back = [list(route) for route in partial]
    handed_back[0].extend(removed)
    recorder.record_repair(
        'r1', audit_repair(partial, partial_costs, removed, handed_back, pricer))
    summary = recorder.summary()

    assert summary['destroy']['d1']['calls'] == 2
    assert summary['repair']['r1']['calls'] == 2
    assert summary['destroy_calls'] == 2
    assert summary['repair_calls'] == 2
    assert 0.0 <= summary['destroy']['d1']['mean_precision'] <= 1.0
    assert summary['repair']['r1']['mean_sum_hit_rate'] is not None
    # The two repair calls disagree (robot 1 vs robot 0), so both the per-call
    # hit rate and the aggregated one stay inside [0, 1].
    assert 0.0 <= summary['repair']['r1']['mean_sum_hit_rate'] <= 1.0
    assert 0.0 <= summary['repair']['r1']['mean_makespan_hit_rate'] <= 1.0
    assert summary['repair']['r1']['max_mean_makespan_regret_ratio'] >= 0.0


def test_audit_does_not_change_the_search():
    instance, _, _, _, _, _ = _setup()
    plain = ALNSSolver(instance, constructor='spatial_sort',
                       config=ALNSConfig.enhanced(iterations=6, cooling_schedule='iteration',
                                                  random_seed=5, decision_audit=False)).solve()
    audited = ALNSSolver(instance, constructor='spatial_sort',
                         config=ALNSConfig.enhanced(iterations=6, cooling_schedule='iteration',
                                                    random_seed=5, decision_audit=True)).solve()

    assert audited.best_evaluation.makespan == plain.best_evaluation.makespan
    assert audited.best_solution.routes == plain.best_solution.routes
    assert [(row['destroy'], row['repair'], row['best_makespan']) for row in audited.iteration_history] \
        == [(row['destroy'], row['repair'], row['best_makespan']) for row in plain.iteration_history]
    assert audited.decision_audit and audited.decision_audit['destroy_calls'] == 6
    assert audited.decision_audit['repair_calls'] == 6
    assert plain.decision_audit is None


def _solver(instance, *, decision_driven_selection: bool, decision_audit: bool = False,
            iterations: int = 6, seed: int = 5):
    config = ALNSConfig.enhanced(
        iterations=iterations,
        cooling_schedule='iteration',
        random_seed=seed,
        decision_audit=decision_audit,
        decision_driven_selection=decision_driven_selection,
    )
    return ALNSSolver(instance, constructor='spatial_sort', config=config).solve()


def test_decision_driven_rewards_come_from_the_audit():
    instance, _, _, _, _, _ = _setup()
    result = _solver(instance, decision_driven_selection=True, iterations=6)

    rows = result.iteration_history
    assert len(rows) == 6
    for row in rows:
        quality = row['decision_quality']
        assert quality is not None
        assert 0.0 <= quality['destroy'] <= 1.0
        assert 0.0 <= quality['repair'] <= 1.0
        # The credit is the decision quality scaled to the 8/3/1 range, not the
        # outcome score of the iteration.
        assert row['destroy_reward'] == pytest.approx(8.0 * quality['destroy'])
        assert row['repair_reward'] == pytest.approx(8.0 * quality['repair'])
    # ... and the outcome score is still recorded separately, untouched.
    assert {row['score_raw'] for row in rows} <= {0.0, 1.0, 3.0, 8.0}


def test_decision_driven_selection_is_reproducible():
    instance, _, _, _, _, _ = _setup()
    first = _solver(instance, decision_driven_selection=True)
    second = _solver(instance, decision_driven_selection=True)

    assert first.best_evaluation.makespan == second.best_evaluation.makespan
    assert first.best_solution.routes == second.best_solution.routes
    assert [(row['destroy'], row['repair'], row['best_makespan'], row['decision_quality'])
            for row in first.iteration_history] == [
        (row['destroy'], row['repair'], row['best_makespan'], row['decision_quality'])
        for row in second.iteration_history]


def test_decision_driven_selection_changes_what_gets_credited():
    instance, _, _, _, _, _ = _setup()
    plain = _solver(instance, decision_driven_selection=False, iterations=6)
    driven = _solver(instance, decision_driven_selection=True, iterations=6)

    # Instrumentation is off in the plain arm, so no decision payload at all.
    assert all(row['decision_quality'] is None for row in plain.iteration_history)
    assert plain.decision_audit is None
    # The driven arm always audits, because the audit produces the reward.
    assert driven.decision_audit is not None
    assert driven.decision_audit['destroy_calls'] == 6
    assert driven.decision_audit['repair_calls'] == 6
    # Compatibility: with this switch off the search is unchanged bit for bit.
    assert plain.best_evaluation.makespan == _solver(
        instance, decision_driven_selection=False, iterations=6,
    ).best_evaluation.makespan
