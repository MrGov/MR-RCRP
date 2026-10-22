from __future__ import annotations

from mrta_rect_coverage.llm.advisor_interface import SearchContext
from mrta_rect_coverage.llm.mock_advisor import MockAdvisor
from mrta_rect_coverage.llm.rule_based_advisor import RuleBasedAdvisor


def _context(history):
    return SearchContext(
        best_makespan=100.0,
        per_route_costs=[100.0, 80.0],
        bottleneck_route_id=0,
        recent_improvement_history=history,
        operator_performance={"destroy": {}, "repair": {}},
    )


def test_mock_advisor_interface_shape() -> None:
    advisor = MockAdvisor()
    ctx = _context([100.0, 99.0])

    op = advisor.suggest_operator(ctx)
    dr = advisor.suggest_destroy_repair(ctx)
    phase = advisor.suggest_search_phase(ctx)

    assert "destroy_operator" in op
    assert "repair_operator" in dr
    assert "intensify" in dr
    assert "phase" in phase


def test_rule_based_advisor_stagnation_switches_to_diversify() -> None:
    advisor = RuleBasedAdvisor()
    ctx = _context([100.0, 100.0, 100.0, 100.0])

    dr = advisor.suggest_destroy_repair(ctx)
    phase = advisor.suggest_search_phase(ctx)

    assert dr["intensify"] is False
    assert phase["phase"] == "diversify"
