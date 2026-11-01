from mrta_rect_coverage.experiments.operator_portfolio_evolution import (
    _evaluate_candidate,
    request_bounded_revisions,
    select_behavioral_shortlist,
    select_complementary_repairs,
)
import pytest
from types import SimpleNamespace
from mrta_rect_coverage.core.models import MultiRobotSolution


def test_complementarity_selects_incremental_behavior_not_top_k():
    candidates = [
        {"id": "champion", "valid": True, "score": 0.9, "gains": [1.0, 0.0, 1.0]},
        {"id": "duplicate", "valid": True, "score": 0.8, "gains": [0.95, 0.0, 0.95]},
        {"id": "specialist", "valid": True, "score": 0.6, "gains": [0.0, 1.1, 0.0]},
    ]

    selected = select_complementary_repairs(candidates, capacity=2, min_gain=0.05)

    assert [item["id"] for item in selected] == ["champion", "specialist"]


def test_complementarity_never_fills_slots_with_invalid_or_noncontributing_candidates():
    candidates = [
        {"id": "invalid", "valid": False, "score": 10.0, "gains": [10.0]},
        {"id": "negative", "valid": True, "score": 1.0, "gains": [-0.1]},
        {"id": "no-gain", "valid": True, "score": 0.0, "gains": [0.0]},
    ]

    assert select_complementary_repairs(candidates, capacity=2, min_gain=0.01) == []


def test_behaviorally_distinct_candidate_reaches_short_alns_without_beating_anchor():
    anchor = {
        "id": "anchor", "hash": "a", "valid": True,
        "cases": [{"status": "success", "baseline_repair": 100,
                   "candidate_repair": 100, "candidate_after_local_search": 100,
                   "baseline_per_robot_costs": [100], "per_robot_costs": [100]}],
    }
    candidate = {
        "id": "distinct", "hash": "b", "valid": True,
        "cases": [{"status": "success", "baseline_repair": 100,
                   "candidate_repair": 96, "candidate_after_local_search": 100,
                   "baseline_per_robot_costs": [100], "per_robot_costs": [96]}],
    }

    selected = select_behavioral_shortlist(
        [anchor, candidate], anchor_hash="a", capacity=1, min_behavior_delta=2.0
    )

    assert [item["hash"] for item in selected] == ["b"]


def test_behavioral_shortlist_rejects_duplicates_invalid_and_dominated_candidates():
    anchor = {
        "id": "anchor", "hash": "a", "valid": True,
        "cases": [{"status": "success", "baseline_repair": 100,
                   "candidate_repair": 100, "candidate_after_local_search": 100,
                   "baseline_per_robot_costs": [100], "per_robot_costs": [100]}],
    }
    candidates = [
        anchor,
        {"id": "duplicate", "hash": "b", "valid": True,
         "cases": [{"status": "success", "baseline_repair": 100,
                    "candidate_repair": 100, "candidate_after_local_search": 100,
                    "baseline_per_robot_costs": [100], "per_robot_costs": [100]}]},
        {"id": "dominated", "hash": "c", "valid": True,
         "cases": [{"status": "success", "baseline_repair": 100,
                    "candidate_repair": 90, "candidate_after_local_search": 101,
                    "baseline_per_robot_costs": [100], "per_robot_costs": [90]}]},
        {"id": "invalid", "hash": "d", "valid": False,
         "cases": [{"status": "success", "baseline_repair": 100,
                    "candidate_repair": 90, "candidate_after_local_search": 100,
                    "baseline_per_robot_costs": [100], "per_robot_costs": [90]}]},
    ]

    assert select_behavioral_shortlist(
        candidates, anchor_hash="a", capacity=2, min_behavior_delta=2.0
    ) == []


def test_candidate_and_baseline_receive_the_same_local_search_pass():
    class Proxy:
        def execute(self, args, timeout_ms):
            return SimpleNamespace(
                status="success", result=SimpleNamespace(solution=MultiRobotSolution([[8]]))
            )

    class Solver:
        instance = object()

        class RouteDP:
            @staticmethod
            def statistics():
                return {"calls": 0, "cache_misses": 0}

        route_dp = RouteDP()

        class Evaluator:
            @staticmethod
            def evaluate(solution):
                value = float(solution.routes[0][0])
                return SimpleNamespace(
                    makespan=value, per_robot_costs=[value],
                    route_evaluations=[SimpleNamespace(
                        route_task_ids=solution.routes[0], total_cost=value,
                        chosen_state_ids=[], entry_points=[], exit_points=[], transition_costs=[],
                    )],
                )

        solution_evaluator = Evaluator()

        @staticmethod
        def _is_valid_full_solution(solution):
            return True

        @staticmethod
        def local_search(solution):
            improved = MultiRobotSolution([[solution.routes[0][0] - 1]])
            value = float(improved.routes[0][0])
            return improved, SimpleNamespace(
                makespan=value, per_robot_costs=[value],
                route_evaluations=[SimpleNamespace(
                    route_task_ids=improved.routes[0], total_cost=value,
                    chosen_state_ids=[], entry_points=[], exit_points=[], transition_costs=[],
                )],
            )

    metrics = _evaluate_candidate(Solver(), {"proxy": Proxy()}, [{
        "partial_routes": [[]], "removed_tasks": [0], "partial_costs": [0],
        "seed": 1, "baseline_repaired_routes": [[10]],
        "instance_id": "dev/A", "band": "early",
    }])

    assert metrics["raw_repair_gains"] == [2.0]
    assert metrics["gains"] == [2.0]
    assert metrics["cases"][0]["baseline_after_local_search"] == 9.0


def test_revision_interface_checks_budget_before_provider_call():
    class Provider:
        called = False

        def revise_operator_candidates(self, *args, **kwargs):
            self.called = True

    provider = Provider()
    with pytest.raises(RuntimeError, match="call budget"):
        request_bounded_revisions(
            provider, "short", round_id=1, n=1, parent_hashes=["abc"],
            call_budget=0, token_budget=1000,
        )
    assert not provider.called


def test_revision_interface_reserves_output_and_enforces_cumulative_token_budget():
    class Provider:
        calls = 0
        last_call_metadata = {"total_tokens": 40}

        def revise_operator_candidates(self, *args, **kwargs):
            self.calls += 1
            return ["draft"]

    provider = Provider()
    _, provenance = request_bounded_revisions(
        provider, "x" * 80, round_id=1, n=1, parent_hashes=["abc"],
        call_budget=2, token_budget=100, max_output_tokens=40,
    )
    assert provenance["reserved_total_tokens"] == 60
    assert provenance["budget_tokens_charged"] == 40
    assert provenance["calls_charged"] == 1

    with pytest.raises(RuntimeError, match="token budget"):
        request_bounded_revisions(
            provider, "x" * 80, round_id=2, n=1, parent_hashes=["abc"],
            call_budget=2, token_budget=100, calls_used=1,
            tokens_used=45, max_output_tokens=40,
        )
    assert provider.calls == 1
