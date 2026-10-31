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


def test_build_evidence_ignores_aggregate_summary_files(tmp_path: Path) -> None:
    """A ``*_summary.json`` is an aggregate, not a report: it must not become an instance."""
    from mrta_rect_coverage.llm.operator_evolution.evolution_loop import _build_evidence
    import json

    reports = tmp_path / "reports"
    reports.mkdir()
    report = {
        "instance": {"name": "R2_T10_0", "robot_count": 2, "task_count": 10},
        "makespan": 1000.0,
        "per_robot_costs": [1000.0, 1000.0],
        "route_load_excess": 0.0,
        "routes": [],
        "state_degeneracy": {
            "position_count": 10,
            "tied_position_count": 5,
            "all_equal_position_count": 0,
            "informative_position_count": 5,
            "mode_gap_abs_median": 1.0,
            "mode_gap_abs_max": 2.0,
            "mode_preference_counts": {"H": 1, "V": 1, "equivalent": 8, "unknown": 0},
        },
    }
    (reports / "a.json").write_text(json.dumps(report), encoding="utf-8")
    (reports / "alns_summary.json").write_text(
        json.dumps({"instance": None, "reports": 1}), encoding="utf-8"
    )
    evidence = _build_evidence(tmp_path, "reports/*.json", 2500)
    assert evidence["instance_count"] == 1
    assert evidence["scale_note"]["n_tasks_range"] == [10, 10]
