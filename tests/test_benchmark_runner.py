from __future__ import annotations

from pathlib import Path

from mrta_rect_coverage.experiments.benchmark_runner import list_instance_files, run_ablation_mode


def test_list_instance_files() -> None:
    project_root = Path(__file__).resolve().parents[1]
    files = list_instance_files(project_root / "data")
    assert any(path.name == "R2_T6_0.txt" for path in files)


def test_run_ablation_mode_baseline() -> None:
    project_root = Path(__file__).resolve().parents[1]
    result = run_ablation_mode(project_root / "data" / "R2_T6_0.txt", "baseline")
    assert result.mode == "baseline"
    assert result.makespan >= 0
