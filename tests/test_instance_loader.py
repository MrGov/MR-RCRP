from __future__ import annotations

from pathlib import Path

import pytest

from mrta_rect_coverage.core.instance_loader import (
    load_instance,
    parse_instance_filename,
)


def test_parse_instance_filename() -> None:
    robots, tasks, rep = parse_instance_filename("R2_T6_0.txt")
    assert robots == 2
    assert tasks == 6
    assert rep == 0


def test_load_instance_values() -> None:
    project_root = Path(__file__).resolve().parents[1]
    instance_path = project_root / "data" / "R2_T6_0.txt"
    instance = load_instance(instance_path)

    assert instance.robot_count == 2
    assert instance.task_count == 6
    assert instance.sweep_width == pytest.approx(2.0)
    assert instance.speed == pytest.approx(1.0)
    assert instance.turning_time == pytest.approx(0.5)

    first = instance.tasks[0]
    last = instance.tasks[-1]
    assert (first.x_left, first.y_bottom, first.x_right, first.y_top) == (8.0, 6.0, 16.0, 9.0)
    assert (last.x_left, last.y_bottom, last.x_right, last.y_top) == (40.0, 22.0, 46.0, 38.0)


def test_filename_mismatch_raises(tmp_path: Path) -> None:
    file_path = tmp_path / "R2_T6_1.txt"
    file_path.write_text(
        "6 3\n2.0 1.0 0.5\n0 1 2 3 4 5\n1 2 3 4 5 6\n0 1 2 3 4 5\n1 2 3 4 5 6\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_instance(file_path)
