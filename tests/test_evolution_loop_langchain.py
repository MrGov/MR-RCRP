"""Tests for evolution loop with a fake LangChain-like provider (no network)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from mrta_rect_coverage.llm.operator_evolution.evolution_loop import (
    EvolutionLoopConfig,
    run_evolution_loop,
)
from mrta_rect_coverage.llm.operator_evolution.langchain_provider import (
    LangChainOperatorEvolutionProvider,
)
from mrta_rect_coverage.llm.operator_evolution.provider_factory import (
    PROVIDER_LANGCHAIN,
    PROVIDER_MOCK,
    build_provider,
)


# ------------------------------------------------------------------
# Provider factory tests
# ------------------------------------------------------------------


def test_factory_builds_mock() -> None:
    provider = build_provider(PROVIDER_MOCK)
    from mrta_rect_coverage.llm.operator_evolution.mock_provider import MockOperatorEvolutionProvider
    assert isinstance(provider, MockOperatorEvolutionProvider)


def test_factory_builds_file(tmp_path: Path) -> None:
    provider = build_provider("file", exchange_dir=tmp_path)
    from mrta_rect_coverage.llm.operator_evolution.file_provider import FileOperatorEvolutionProvider
    assert isinstance(provider, FileOperatorEvolutionProvider)


def test_factory_file_requires_exchange_dir() -> None:
    import pytest
    with pytest.raises(ValueError, match="exchange_dir"):
        build_provider("file")


def test_factory_unknown_provider_raises() -> None:
    import pytest
    with pytest.raises(ValueError, match="Unknown provider"):
        build_provider("nonexistent")


# ------------------------------------------------------------------
# Evolution loop with fake LangChain provider
# ------------------------------------------------------------------


def _make_fake_langchain_provider() -> LangChainOperatorEvolutionProvider:
    """Build a provider whose chat model returns valid JSON candidates."""
    repair_response = json.dumps([{
        "name": "fake_dp_repair",
        "description": "Fake DP-aware insertion for testing",
        "code": (
            "from __future__ import annotations\n"
            "from mrta_rect_coverage.llm.operator_evolution.protocols import "
            "RepairContext, RepairResult\n"
            "from mrta_rect_coverage.core.models import MultiRobotSolution\n"
            "import random\n\n"
            "def repair(partial_solution, unassigned_tasks, context, rng):\n"
            "    routes = [list(r) for r in partial_solution.routes]\n"
            "    for task_id in unassigned_tasks:\n"
            "        shortest = min(range(len(routes)), key=lambda i: len(routes[i]))\n"
            "        routes[shortest].append(task_id)\n"
            "    return RepairResult(\n"
            "        solution=MultiRobotSolution(routes=routes),\n"
            "        note='fake dp repair',\n"
            "    )\n"
        ),
    }])

    destroy_response = json.dumps([{
        "name": "fake_bottleneck_destroy",
        "description": "Fake bottleneck destroy for testing",
        "code": (
            "from __future__ import annotations\n"
            "from mrta_rect_coverage.llm.operator_evolution.protocols import "
            "DestroyContext, DestroyResult\n"
            "from mrta_rect_coverage.core.models import MultiRobotSolution\n"
            "import random\n\n"
            "def destroy(solution, context, rng):\n"
            "    routes = [list(r) for r in solution.routes]\n"
            "    removed = []\n"
            "    for _ in range(min(context.remove_count, sum(len(r) for r in routes))):\n"
            "        non_empty = [i for i, r in enumerate(routes) if r]\n"
            "        if not non_empty:\n"
            "            break\n"
            "        ri = rng.choice(non_empty)\n"
            "        removed.append(routes[ri].pop())\n"
            "    return DestroyResult(\n"
            "        partial_solution=MultiRobotSolution(routes=routes),\n"
            "        removed_tasks=removed,\n"
            "        note='fake bottleneck destroy',\n"
            "    )\n"
        ),
    }])

    mock_chat = MagicMock()
    call_count = {"n": 0}

    def fake_invoke(messages):
        call_count["n"] += 1
        resp = MagicMock()
        # Alternate between repair and destroy responses based on prompt content
        prompt_text = messages[0].content if hasattr(messages[0], "content") else str(messages[0])
        if "destroy" in prompt_text.lower():
            resp.content = destroy_response
        else:
            resp.content = repair_response
        return resp

    mock_chat.invoke.side_effect = fake_invoke
    return LangChainOperatorEvolutionProvider(chat_model=mock_chat)


def test_evolution_loop_with_fake_langchain(tmp_path: Path) -> None:
    """Full evolution loop with a fake LangChain provider, no network."""
    project_root = Path(__file__).resolve().parents[1]
    provider = _make_fake_langchain_provider()

    config = EvolutionLoopConfig(
        project_root=project_root,
        generated_dir=tmp_path / "generated_ops",
        output_dir=tmp_path / "outputs_ops",
        round_count=1,
        repair_candidates_per_round=1,
        destroy_candidates_per_round=1,
        benchmark_instance_glob="data/R2_T6_0.txt",
        seeds=(0,),
        provider_name="langchain_openai_compatible",
        use_rich_prompts=True,
    )
    artifacts = run_evolution_loop(provider, config)

    assert len(artifacts.round_metrics_files) == 1
    assert (tmp_path / "outputs_ops" / "evolution_summary.json").exists()
    assert (tmp_path / "outputs_ops" / "best_operators.json").exists()
    assert (tmp_path / "outputs_ops" / "round_000_candidates.json").exists()
    assert (tmp_path / "outputs_ops" / "round_000_repair_prompt.txt").exists()
    assert (tmp_path / "outputs_ops" / "round_000_destroy_prompt.txt").exists()

    # Verify rich prompts were used
    repair_prompt = (tmp_path / "outputs_ops" / "round_000_repair_prompt.txt").read_text(encoding="utf-8")
    assert "Constraints:" in repair_prompt or "MR-RCRP" in repair_prompt


def test_evolution_loop_rich_prompts_auto_enabled(tmp_path: Path) -> None:
    """When provider_name is langchain and use_rich_prompts is None, rich prompts activate."""
    from mrta_rect_coverage.llm.operator_evolution import prompt_builder

    project_root = Path(__file__).resolve().parents[1]
    provider = _make_fake_langchain_provider()

    config = EvolutionLoopConfig(
        project_root=project_root,
        generated_dir=tmp_path / "generated_ops",
        output_dir=tmp_path / "outputs_ops",
        round_count=1,
        repair_candidates_per_round=1,
        destroy_candidates_per_round=0,
        benchmark_instance_glob="data/R2_T6_0.txt",
        seeds=(0,),
        operator_types_to_evolve=("repair",),
        provider_name="langchain_openai_compatible",
        use_rich_prompts=None,  # Should auto-enable
    )
    run_evolution_loop(provider, config)

    # After the loop, the flag should have been set to True
    assert prompt_builder.use_rich_prompts is True

    # Reset for other tests
    prompt_builder.use_rich_prompts = False


def test_evolution_loop_compact_prompts_for_mock(tmp_path: Path) -> None:
    """Mock provider should use compact prompts by default."""
    from mrta_rect_coverage.llm.operator_evolution import prompt_builder
    from mrta_rect_coverage.llm.operator_evolution.mock_provider import MockOperatorEvolutionProvider

    project_root = Path(__file__).resolve().parents[1]
    provider = MockOperatorEvolutionProvider()

    config = EvolutionLoopConfig(
        project_root=project_root,
        generated_dir=tmp_path / "generated_ops",
        output_dir=tmp_path / "outputs_ops",
        round_count=1,
        repair_candidates_per_round=1,
        destroy_candidates_per_round=0,
        benchmark_instance_glob="data/R2_T6_0.txt",
        seeds=(0,),
        operator_types_to_evolve=("repair",),
        provider_name="mock",
        use_rich_prompts=None,
    )
    run_evolution_loop(provider, config)

    assert prompt_builder.use_rich_prompts is False
