from __future__ import annotations

from pathlib import Path

from mrta_rect_coverage.llm.operator_evolution.file_provider import FileOperatorEvolutionProvider
from mrta_rect_coverage.llm.operator_evolution.mock_provider import MockOperatorEvolutionProvider


def test_provider_interface_methods_exist(tmp_path: Path) -> None:
    mock = MockOperatorEvolutionProvider()
    file_provider = FileOperatorEvolutionProvider(exchange_dir=tmp_path)

    for provider in (mock, file_provider):
        assert callable(getattr(provider, "generate_operator_candidates"))
        assert callable(getattr(provider, "revise_operator_candidates"))
