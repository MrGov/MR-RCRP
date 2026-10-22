from __future__ import annotations

from pathlib import Path

from mrta_rect_coverage.llm.operator_evolution.file_provider import FileOperatorEvolutionProvider


def test_file_provider_roundtrip(tmp_path: Path) -> None:
    provider = FileOperatorEvolutionProvider(exchange_dir=tmp_path)
    round_dir = tmp_path / "round_000" / "repair"
    round_dir.mkdir(parents=True)
    op_file = round_dir / "candidate_a.py"
    op_file.write_text("def repair(partial_solution, unassigned_tasks, context, rng):\n    return None\n", encoding="utf-8")

    drafts = provider.generate_operator_candidates("hello", 1, "repair", 0)
    assert len(drafts) == 1
    assert drafts[0].operator_id == "candidate_a"
    assert (tmp_path / "generate_repair_round_000_prompt.txt").exists()
