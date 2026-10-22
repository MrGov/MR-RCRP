"""Tests for LangChain provider response parsing (no real LLM calls)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from mrta_rect_coverage.llm.operator_evolution.langchain_provider import (
    LangChainOperatorEvolutionProvider,
)


def _make_provider(
    response_text: str, *, raw_dir: Path | None = None
) -> LangChainOperatorEvolutionProvider:
    """Build a provider with a mock chat model returning *response_text*."""
    mock_chat = MagicMock()
    mock_response = MagicMock()
    mock_response.content = response_text
    mock_chat.invoke.return_value = mock_response

    return LangChainOperatorEvolutionProvider(
        chat_model=mock_chat, raw_response_dir=raw_dir
    )


# ------------------------------------------------------------------
# JSON parsing
# ------------------------------------------------------------------


def test_parse_json_array() -> None:
    payload = json.dumps([
        {
            "name": "dp_insert",
            "description": "DP-aware insertion",
            "code": "def repair(partial_solution, unassigned_tasks, context, rng):\n    pass",
        },
        {
            "name": "balance_insert",
            "description": "Bottleneck balancing",
            "code": "def repair(partial_solution, unassigned_tasks, context, rng):\n    pass",
        },
    ])
    provider = _make_provider(payload)
    drafts = provider.generate_operator_candidates("prompt", 3, "repair", 0)

    assert len(drafts) == 2
    assert drafts[0].name == "dp_insert"
    assert drafts[0].source == "langchain"
    assert drafts[0].operator_type == "repair"
    assert drafts[0].round_id == 0
    assert "def repair(" in drafts[0].code


def test_parse_json_single_object() -> None:
    payload = json.dumps({
        "name": "geo_destroy",
        "description": "Geometry-aware destroy",
        "code": "def destroy(solution, context, rng):\n    pass",
    })
    provider = _make_provider(payload)
    drafts = provider.generate_operator_candidates("prompt", 1, "destroy", 2)

    assert len(drafts) == 1
    assert drafts[0].name == "geo_destroy"
    assert drafts[0].operator_id == "destroy_r002_000"


def test_parse_json_in_markdown_fence() -> None:
    payload = (
        "Here are the candidates:\n"
        "```json\n"
        + json.dumps([{
            "name": "fence_repair",
            "description": "test",
            "code": "def repair(partial_solution, unassigned_tasks, context, rng):\n    pass",
        }])
        + "\n```\n"
    )
    provider = _make_provider(payload)
    drafts = provider.generate_operator_candidates("prompt", 1, "repair", 0)

    assert len(drafts) == 1
    assert drafts[0].name == "fence_repair"


def test_parse_json_truncates_to_n() -> None:
    items = [
        {"name": f"op_{i}", "description": "test", "code": f"def repair(p,u,c,r):\n    return {i}"}
        for i in range(5)
    ]
    provider = _make_provider(json.dumps(items))
    drafts = provider.generate_operator_candidates("prompt", 2, "repair", 0)

    assert len(drafts) == 2


# ------------------------------------------------------------------
# Code fence fallback
# ------------------------------------------------------------------


def test_parse_code_fences_repair() -> None:
    response = (
        "Here is a repair operator:\n"
        "```python\n"
        "def repair(partial_solution, unassigned_tasks, context, rng):\n"
        "    # DP-aware insertion\n"
        "    pass\n"
        "```\n"
    )
    provider = _make_provider(response)
    drafts = provider.generate_operator_candidates("prompt", 1, "repair", 1)

    assert len(drafts) == 1
    assert "def repair(" in drafts[0].code
    assert drafts[0].source == "langchain"
    assert drafts[0].description == "LLM-generated candidate (code fence)"


def test_parse_code_fences_filters_wrong_function() -> None:
    """Code fences without the expected function name are skipped."""
    response = (
        "```python\n"
        "def helper():\n"
        "    pass\n"
        "```\n"
        "```python\n"
        "def repair(partial_solution, unassigned_tasks, context, rng):\n"
        "    pass\n"
        "```\n"
    )
    provider = _make_provider(response)
    drafts = provider.generate_operator_candidates("prompt", 2, "repair", 0)

    assert len(drafts) == 1
    assert "def repair(" in drafts[0].code


def test_parse_code_fences_destroy() -> None:
    response = (
        "```python\n"
        "def destroy(solution, context, rng):\n"
        "    pass\n"
        "```\n"
    )
    provider = _make_provider(response)
    drafts = provider.generate_operator_candidates("prompt", 1, "destroy", 0)

    assert len(drafts) == 1
    assert "def destroy(" in drafts[0].code


# ------------------------------------------------------------------
# Failure / empty
# ------------------------------------------------------------------


def test_unparseable_response_returns_empty() -> None:
    provider = _make_provider("This is just plain text with no code.")
    drafts = provider.generate_operator_candidates("prompt", 1, "repair", 0)

    assert drafts == []


def test_invalid_json_falls_through_to_code_fence() -> None:
    """Invalid JSON but valid code fence should still produce drafts."""
    response = (
        "{invalid json here}\n"
        "```python\n"
        "def repair(partial_solution, unassigned_tasks, context, rng):\n"
        "    pass\n"
        "```\n"
    )
    provider = _make_provider(response)
    drafts = provider.generate_operator_candidates("prompt", 1, "repair", 0)

    assert len(drafts) == 1


# ------------------------------------------------------------------
# Raw response saving
# ------------------------------------------------------------------


def test_raw_response_saved_to_disk(tmp_path: Path) -> None:
    provider = _make_provider("some response", raw_dir=tmp_path)
    provider.generate_operator_candidates("prompt", 1, "repair", 0)

    raw_file = tmp_path / "generate_repair_round_000_raw.txt"
    assert raw_file.exists()
    assert raw_file.read_text(encoding="utf-8") == "some response"


def test_raw_response_not_saved_when_dir_is_none() -> None:
    provider = _make_provider("some response", raw_dir=None)
    # Should not raise
    provider.generate_operator_candidates("prompt", 1, "repair", 0)


# ------------------------------------------------------------------
# Revise delegates to same parsing
# ------------------------------------------------------------------


def test_revise_uses_same_parsing() -> None:
    payload = json.dumps([{
        "name": "revised_op",
        "description": "improved",
        "code": "def repair(partial_solution, unassigned_tasks, context, rng):\n    pass",
    }])
    provider = _make_provider(payload)
    drafts = provider.revise_operator_candidates(
        "revision prompt", {"summary": {}}, 1, "repair", 1
    )

    assert len(drafts) == 1
    assert drafts[0].name == "revised_op"
