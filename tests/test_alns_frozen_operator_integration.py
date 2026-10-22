from __future__ import annotations

from pathlib import Path

from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.heuristics.alns_solver import ALNSConfig, ALNSSolver
from mrta_rect_coverage.llm.operator_evolution.evolution_loop import EvolutionLoopConfig, run_evolution_loop
from mrta_rect_coverage.llm.operator_evolution.freezing import freeze_best_operators
from mrta_rect_coverage.llm.operator_evolution.mock_provider import MockOperatorEvolutionProvider


def test_alns_loads_frozen_operator_registry(tmp_path: Path) -> None:
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

    instance = load_instance(project_root / "data" / "R2_T6_0.txt")
    solver = ALNSSolver(
        instance,
        config=ALNSConfig(
            iterations=2,
            frozen_operator_registry_path=str(freeze.registry_path),
            use_frozen_repair=True,
            use_frozen_destroy=True,
            use_dp_aware_insertion=False,
            allow_generated_frozen_deployment=True,
            explicit_runtime_deployment_ack=True,
            runtime_authorization_source="current_runtime_config",
        ),
    )

    assert any(name.startswith("repair_r") for name in solver.repair_ops)
    assert any(name.startswith("destroy_r") for name in solver.destroy_ops)
