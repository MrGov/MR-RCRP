from __future__ import annotations

from pathlib import Path

from mrta_rect_coverage.llm.operator_evolution.evolution_loop import EvolutionLoopConfig, run_evolution_loop
from mrta_rect_coverage.llm.operator_evolution.freezing import freeze_best_operators
from mrta_rect_coverage.llm.operator_evolution.mock_provider import MockOperatorEvolutionProvider


def test_freezing_creates_registry_and_files(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    provider = MockOperatorEvolutionProvider()
    artifacts = run_evolution_loop(
        provider,
        EvolutionLoopConfig(
            project_root=project_root,
            generated_dir=tmp_path / "generated_ops",
            output_dir=tmp_path / "outputs_ops",
            round_count=1,
            repair_candidates_per_round=1,
            destroy_candidates_per_round=1,
            benchmark_instance_glob="data/R2_T6_0.txt",
            seeds=(0,),
        ),
    )

    freeze = freeze_best_operators(
        project_root=project_root,
        best_operators_json=Path(artifacts.best_operators_path),
        generated_root=tmp_path / "generated_ops",
        target_dir=tmp_path / "frozen_ops",
        registry_path=tmp_path / "frozen_ops" / "registry.json",
    )

    assert Path(freeze.registry_path).exists()
    assert len(freeze.copied_files) >= 1
