from __future__ import annotations

from mrta_rect_coverage.llm.operator_evolution.mock_provider import MockOperatorEvolutionProvider


def test_mock_provider_generates_repair_candidates() -> None:
    provider = MockOperatorEvolutionProvider()
    drafts = provider.generate_operator_candidates("prompt", 2, "repair", 0)
    assert len(drafts) == 2
    assert all("def repair(" in d.code for d in drafts)


def test_mock_provider_generates_destroy_candidates() -> None:
    provider = MockOperatorEvolutionProvider()
    drafts = provider.generate_operator_candidates("prompt", 1, "destroy", 0)
    assert len(drafts) == 1
    assert "def destroy(" in drafts[0].code
