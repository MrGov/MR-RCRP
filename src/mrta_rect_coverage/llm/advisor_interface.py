"""LLM-advisor abstraction for ALNS search guidance."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Protocol


@dataclass
class SearchContext:
    """Compact search context passed to advisor components."""

    best_makespan: float
    per_route_costs: List[float]
    bottleneck_route_id: int
    recent_improvement_history: List[float]
    operator_performance: Dict[str, Dict[str, Dict[str, float]]]


class Advisor(Protocol):
    """Unified advisor interface with future LLM-compatible methods."""

    def suggest_operator(self, context: SearchContext) -> Dict[str, object]:
        ...

    def suggest_destroy_repair(self, context: SearchContext) -> Dict[str, object]:
        ...

    def suggest_search_phase(self, context: SearchContext) -> Dict[str, object]:
        ...
