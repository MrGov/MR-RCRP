import json
from types import SimpleNamespace

import pytest

from mrta_rect_coverage.experiments.operator_gap_revision import eligible, request
from mrta_rect_coverage.experiments.operator_portfolio_evolution import _evaluate_candidate


def test_failed_request_is_charged_and_not_retried(tmp_path):
    class Provider:
        calls = 0

        def revise_operator_candidates(self, *args, **kwargs):
            self.calls += 1
            persisted = json.loads((tmp_path / "requests.json").read_text())
            assert persisted[0]["status"] == "started"
            raise RuntimeError("secret endpoint must not enter logs")

    provider = Provider()
    ledger = []
    assert request(provider, "prompt", tmp_path / "call1", ledger, 1, 1, "revision") == []
    assert provider.calls == 1
    assert ledger[0]["status"] == "provider_failure"
    assert "secret" not in (tmp_path / "requests.json").read_text()
    with pytest.raises(RuntimeError, match="budget exhausted"):
        request(provider, "prompt", tmp_path / "call2", ledger, 1, 1, "revision")
    assert provider.calls == 1


def test_deployment_requires_real_calls_no_fallback_and_feasibility():
    assert not eligible([])
    row = {"valid": True, "fallback_events": [], "generated_members": {"child": "hash"},
           "operator_stats": {"repair": {"child": {"calls": 0}}}}
    assert not eligible([row])
    row["operator_stats"]["repair"]["child"]["calls"] = 1
    assert eligible([row])
    row["fallback_events"] = [{"reason": "timeout"}]
    assert not eligible([row])
    row["fallback_events"] = []
    row["valid"] = False
    assert not eligible([row])


def test_failed_paired_execution_preserves_error_and_serializes_without_nan():
    solver = SimpleNamespace(instance=object(), route_dp=SimpleNamespace(
        statistics=lambda: {"calls": 0, "cache_misses": 0}))
    proxy = SimpleNamespace(execute=lambda *args, **kwargs: SimpleNamespace(
        status="runtime_error", error_message="missing task key"))
    result = _evaluate_candidate(solver, {"proxy": proxy}, [{
        "partial_routes": [[]], "partial_costs": [0.0], "removed_tasks": [1],
        "seed": 23, "instance_id": "development/example", "band": "early"}])
    assert not result["valid"]
    assert result["raw_repair_gains"] == [None]
    assert result["cases"][0]["error_message"] == "missing task key"
    json.dumps(result, allow_nan=False)
