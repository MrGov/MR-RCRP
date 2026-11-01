from mrta_rect_coverage.experiments.operator_portfolio_evolution import (
    request_bounded_revisions,
    select_complementary_repairs,
)
import pytest


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
