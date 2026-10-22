from __future__ import annotations

from pathlib import Path

from mrta_rect_coverage.llm.operator_evolution.evolution_loop import EvolutionLoopConfig, run_evolution_loop
from mrta_rect_coverage.llm.operator_evolution.mock_provider import MockOperatorEvolutionProvider


def test_evolution_loop_smoke(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    provider = MockOperatorEvolutionProvider()
    config = EvolutionLoopConfig(
        project_root=project_root,
        generated_dir=tmp_path / "generated_ops",
        output_dir=tmp_path / "outputs_ops",
        round_count=1,
        repair_candidates_per_round=1,
        destroy_candidates_per_round=1,
        benchmark_instance_glob="data/R2_T6_0.txt",
        seeds=(0,),
    )
    artifacts = run_evolution_loop(provider, config)

    assert len(artifacts.round_metrics_files) == 1
    assert (tmp_path / "outputs_ops" / "evolution_summary.json").exists()
    assert (tmp_path / "outputs_ops" / "best_operators.json").exists()
