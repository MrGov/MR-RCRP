"""Tests for prompt builder (compact and rich modes)."""
from __future__ import annotations

from mrta_rect_coverage.llm.operator_evolution import prompt_builder
from mrta_rect_coverage.llm.prompts import common


class TestCompactPrompts:
    """Tests for the original compact prompt templates."""

    def setup_method(self) -> None:
        prompt_builder.use_rich_prompts = False

    def test_generation_repair_contains_key_sections(self) -> None:
        prompt = prompt_builder.build_initial_generation_prompt(operator_type="repair", round_id=0)
        assert "Round: 0" in prompt
        assert "repair" in prompt.lower()
        assert "Multi-robot" in prompt or "MRTA" in prompt

    def test_generation_destroy_contains_key_sections(self) -> None:
        prompt = prompt_builder.build_initial_generation_prompt(operator_type="destroy", round_id=1)
        assert "Round: 1" in prompt
        assert "destroy" in prompt.lower()

    def test_revision_includes_feedback(self) -> None:
        prompt = prompt_builder.build_revision_prompt(
            operator_type="repair",
            round_id=1,
            previous_summary={"avg_improvement": 0.05},
            top_operators=[{"name": "best_op"}],
            weak_operators=[{"name": "worst_op"}],
        )
        assert "Revision" in prompt
        assert "best_op" in prompt
        assert "worst_op" in prompt


class TestRichPrompts:
    """Tests for the structured LLM prompt templates."""

    def setup_method(self) -> None:
        prompt_builder.use_rich_prompts = True

    def teardown_method(self) -> None:
        prompt_builder.use_rich_prompts = False

    def test_rich_generation_repair_includes_problem_description(self) -> None:
        prompt = prompt_builder.build_initial_generation_prompt(operator_type="repair", round_id=0)
        assert common.PROBLEM_DESCRIPTION.strip()[:40] in prompt
        assert "repair" in prompt.lower()
        assert "JSON" in prompt
        assert "from mrta_rect_coverage.core.models import MultiRobotSolution" in prompt
        assert "from mrta_rect_coverage.llm.operator_evolution.protocols import RepairResult" in prompt
        assert "getattr" in prompt and "sys" in prompt
        assert "context does not provide" in prompt
        assert "instance.robot_count" in prompt

    def test_rich_generation_destroy_includes_destroy_signature(self) -> None:
        prompt = prompt_builder.build_initial_generation_prompt(operator_type="destroy", round_id=0)
        assert "def destroy(" in prompt
        assert "DestroyResult" in prompt

    def test_rich_revision_includes_constraints_and_feedback(self) -> None:
        prompt = prompt_builder.build_revision_prompt(
            operator_type="repair",
            round_id=2,
            previous_summary={"avg_improvement": 0.1},
            top_operators=[{"name": "top_op", "score": 0.9}],
            weak_operators=[{"name": "weak_op", "score": 0.01}],
        )
        assert "Constraints:" in prompt
        assert "top_op" in prompt
        assert "weak_op" in prompt
        assert "Revision" in prompt

    def test_rich_revision_destroy(self) -> None:
        prompt = prompt_builder.build_revision_prompt(
            operator_type="destroy",
            round_id=1,
            previous_summary={},
            top_operators=[],
            weak_operators=[],
        )
        assert "destroy" in prompt.lower()
        assert "def destroy(" in prompt


class TestRichPromptModules:
    """Direct tests for llm/prompts/ modules."""

    def test_generation_prompt_dispatch_repair(self) -> None:
        from mrta_rect_coverage.llm.prompts.operator_generation import build_generation_prompt
        prompt = build_generation_prompt(operator_type="repair", round_id=0)
        assert "repair" in prompt.lower()
        assert "Initial Generation" in prompt

    def test_generation_prompt_dispatch_destroy(self) -> None:
        from mrta_rect_coverage.llm.prompts.operator_generation import build_generation_prompt
        prompt = build_generation_prompt(operator_type="destroy", round_id=0)
        assert "destroy" in prompt.lower()

    def test_generation_prompt_unknown_type_raises(self) -> None:
        from mrta_rect_coverage.llm.prompts.operator_generation import build_generation_prompt
        import pytest
        with pytest.raises(ValueError, match="Unknown operator_type"):
            build_generation_prompt(operator_type="unknown", round_id=0)

    def test_revision_prompt_dispatch_repair(self) -> None:
        from mrta_rect_coverage.llm.prompts.operator_revision import build_revision_prompt
        prompt = build_revision_prompt(
            operator_type="repair", round_id=1,
            previous_summary={}, top_operators=[], weak_operators=[],
        )
        assert "Revision" in prompt

    def test_revision_prompt_unknown_type_raises(self) -> None:
        from mrta_rect_coverage.llm.prompts.operator_revision import build_revision_prompt
        import pytest
        with pytest.raises(ValueError, match="Unknown operator_type"):
            build_revision_prompt(
                operator_type="unknown", round_id=0,
                previous_summary={}, top_operators=[], weak_operators=[],
            )

    def test_common_constants_are_nonempty(self) -> None:
        assert len(common.PROBLEM_DESCRIPTION) > 50
        assert len(common.CONSTRAINTS) > 50
        assert len(common.REPAIR_SIGNATURE) > 50
        assert len(common.DESTROY_SIGNATURE) > 50
        assert len(common.REPAIR_HEURISTIC_DIRECTIONS) > 50
        assert len(common.DESTROY_HEURISTIC_DIRECTIONS) > 50
        assert len(common.OUTPUT_FORMAT_JSON) > 50
