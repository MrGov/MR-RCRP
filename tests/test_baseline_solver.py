from __future__ import annotations

from pathlib import Path

from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.heuristics.baseline_solver import baseline_solve


def test_baseline_solver_respects_constructor() -> None:
    project_root = Path(__file__).resolve().parents[1]
    instance_path = project_root / "data" / "R2_T6_0.txt"
    instance = load_instance(instance_path)

    solution, evaluation = baseline_solve(
        instance,
        constructor="round_robin",
        enable_local_search=False,
    )

    assert solution.routes == [[1, 3, 5], [2, 4, 6]]
    assert evaluation.makespan >= 0
