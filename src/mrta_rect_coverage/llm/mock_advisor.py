"""Mock advisor with deterministic recommendations."""
from __future__ import annotations

from typing import Dict

from .advisor_interface import Advisor, SearchContext


class MockAdvisor(Advisor):
    """Fixed responses to validate advisor plumbing without external APIs."""

    def suggest_operator(self, context: SearchContext) -> Dict[str, object]:
        return {
            "destroy_operator": "random_destroy",
            "repair_operator": "greedy_insertion",
        }

    def suggest_destroy_repair(self, context: SearchContext) -> Dict[str, object]:
        return {
            "destroy_operator": "random_destroy",
            "repair_operator": "greedy_insertion",
            "intensify": False,
        }

    def suggest_search_phase(self, context: SearchContext) -> Dict[str, object]:
        return {"phase": "diversify", "intensify": False}
