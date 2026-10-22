"""Provider interface for offline operator candidate generation."""
from __future__ import annotations

from typing import Dict, List, Protocol

from .schemas import GeneratedOperatorDraft


class OperatorEvolutionProvider(Protocol):
    def generate_operator_candidates(
        self,
        prompt: str,
        n: int,
        operator_type: str,
        round_id: int,
    ) -> List[GeneratedOperatorDraft]:
        ...

    def revise_operator_candidates(
        self,
        prompt: str,
        previous_results: Dict[str, object],
        n: int,
        operator_type: str,
        round_id: int,
    ) -> List[GeneratedOperatorDraft]:
        ...
