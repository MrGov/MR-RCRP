from __future__ import annotations

from pathlib import Path

from mrta_rect_coverage.llm.operator_evolution.candidate_loader import load_and_validate_candidate, persist_operator_drafts
from mrta_rect_coverage.llm.operator_evolution.evaluator import (
    build_destroy_benchmark_cases,
    build_repair_benchmark_cases,
    evaluate_destroy_candidates,
    evaluate_repair_candidates,
)
from mrta_rect_coverage.llm.operator_evolution.mock_provider import MockOperatorEvolutionProvider


def _data_paths():
    project_root = Path(__file__).resolve().parents[1]
    return [project_root / "data" / "R2_T6_0.txt"]


def test_repair_evaluator_smoke() -> None:
    provider = MockOperatorEvolutionProvider()
    drafts = provider.generate_operator_candidates("p", 1, "repair", 1)
    project_root = Path(__file__).resolve().parents[1]
    paths = persist_operator_drafts(project_root / "generated_operators", drafts)
    candidate = load_and_validate_candidate(
        path=paths[0],
        operator_type="repair",
        round_id=1,
        source="mock",
        description="repair",
    )

    cases = build_repair_benchmark_cases(_data_paths())
    rows = evaluate_repair_candidates([candidate], cases, seeds=[0, 1], timeout_ms=1000)
    assert len(rows) == 1
    assert "avg_makespan_delta" in rows[0]


def test_destroy_evaluator_smoke() -> None:
    provider = MockOperatorEvolutionProvider()
    drafts = provider.generate_operator_candidates("p", 1, "destroy", 1)
    project_root = Path(__file__).resolve().parents[1]
    paths = persist_operator_drafts(project_root / "generated_operators", drafts)
    candidate = load_and_validate_candidate(
        path=paths[0],
        operator_type="destroy",
        round_id=1,
        source="mock",
        description="destroy",
    )

    cases = build_destroy_benchmark_cases(_data_paths())
    rows = evaluate_destroy_candidates([candidate], cases, seeds=[0], timeout_ms=1000)
    assert len(rows) == 1
    assert "success_rate" in rows[0]
