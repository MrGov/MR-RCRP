"""Rule-based advisor for ALNS search guidance."""
from __future__ import annotations

from typing import Dict

from .advisor_interface import Advisor, SearchContext


class RuleBasedAdvisor(Advisor):
    """Suggest operators based on bottleneck and recent improvement trend."""

    def suggest_operator(self, context: SearchContext) -> Dict[str, object]:
        stagnating = _is_stagnating(context)
        if stagnating:
            return {
                "destroy_operator": "geometry_aware_destroy",
                "repair_operator": "greedy_insertion",
            }
        return {
            "destroy_operator": "bottleneck_route_destroy",
            "repair_operator": "bottleneck_balancing_insertion",
        }

    def suggest_destroy_repair(self, context: SearchContext) -> Dict[str, object]:
        base = self.suggest_operator(context)
        stagnating = _is_stagnating(context)
        return {
            "destroy_operator": base["destroy_operator"],
            "repair_operator": base["repair_operator"],
            "intensify": not stagnating,
        }

    def suggest_search_phase(self, context: SearchContext) -> Dict[str, object]:
        stagnating = _is_stagnating(context)
        return {
            "phase": "diversify" if stagnating else "intensify",
            "intensify": not stagnating,
        }


def _is_stagnating(context: SearchContext, window: int = 8) -> bool:
    history = context.recent_improvement_history[-window:]
    if len(history) < 3:
        return False
    return max(history) - min(history) < 1e-6
