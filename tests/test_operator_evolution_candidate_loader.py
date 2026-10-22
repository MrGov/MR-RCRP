from __future__ import annotations

from pathlib import Path

from mrta_rect_coverage.llm.operator_evolution.candidate_loader import (
    load_and_validate_candidate,
    persist_operator_drafts,
)
from mrta_rect_coverage.llm.operator_evolution.mock_provider import MockOperatorEvolutionProvider


def test_candidate_loader_validation() -> None:
    provider = MockOperatorEvolutionProvider()
    drafts = provider.generate_operator_candidates("p", 1, "repair", 0)

    project_root = Path(__file__).resolve().parents[1]
    target_dir = project_root / "generated_operators"
    paths = persist_operator_drafts(target_dir, drafts)
    loaded = load_and_validate_candidate(
        path=paths[0],
        operator_type="repair",
        round_id=0,
        source="mock",
        description="test",
    )
    assert loaded.validation.validation_status == "valid"
    assert loaded.callable_obj is not None
