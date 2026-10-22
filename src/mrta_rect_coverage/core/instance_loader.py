"""Instance loading utilities."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Tuple

from .models import Instance, TaskRegion


def parse_instance_filename(path: str | Path) -> Tuple[int, int, int]:
    """Parse instance filename of the form R{robots}_T{tasks}_{rep}.txt."""

    filename = Path(path).name
    if not filename.endswith(".txt"):
        raise ValueError(f"Instance filename must end with .txt: {filename}")
    stem = filename[:-4]
    parts = stem.split("_")
    if len(parts) != 3 or not parts[0].startswith("R") or not parts[1].startswith("T"):
        raise ValueError(
            "Filename must follow pattern R{robots}_T{tasks}_{rep}.txt"
        )
    try:
        robot_count = int(parts[0][1:])
        task_count = int(parts[1][1:])
        rep_id = int(parts[2])
    except ValueError as exc:
        raise ValueError(
            "Filename components must be integers in pattern R{robots}_T{tasks}_{rep}.txt"
        ) from exc
    if robot_count <= 0 or task_count <= 0:
        raise ValueError("Robot and task counts from filename must be positive")
    return robot_count, task_count, rep_id


def load_instance(path: str | Path) -> Instance:
    """Load an instance file, validating structure and filename consistency."""

    file_path = Path(path)
    robots_from_name, tasks_from_name, rep_id = parse_instance_filename(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Instance file not found: {file_path}")

    with file_path.open("r", encoding="utf-8") as handle:
        raw_lines = [line.strip() for line in handle if line.strip()]

    if len(raw_lines) != 6:
        raise ValueError(
            f"Instance file must contain exactly 6 non-empty lines, got {len(raw_lines)}"
        )

    line1 = raw_lines[0].split()
    if len(line1) != 2:
        raise ValueError("First line must contain exactly two integers: n_tasks n_robots")
    n_tasks, n_robots = map(int, line1)

    if n_tasks <= 0 or n_robots <= 0:
        raise ValueError("Number of tasks and robots must be positive integers")

    if n_tasks != tasks_from_name or n_robots != robots_from_name:
        raise ValueError(
            "Filename counts (robots/tasks) do not match values inside the file"
        )

    line2 = raw_lines[1].split()
    if len(line2) != 4:
        raise ValueError(
            "Second line must contain exactly four floats: "
            "sweep_width sweep_speed travel_speed turning_time"
        )
    sweep_width, sweep_speed, travel_speed, turning_time = map(float, line2)

    if not math.isfinite(sweep_width) or sweep_width <= 0:
        raise ValueError("sweep_width must be finite and positive")
    if not math.isfinite(sweep_speed) or sweep_speed <= 0:
        raise ValueError("sweep_speed must be finite and positive")
    if not math.isfinite(travel_speed) or travel_speed <= 0:
        raise ValueError("travel_speed must be finite and positive")
    if not math.isfinite(turning_time) or turning_time < 0:
        raise ValueError("turning_time must be finite and non-negative")

    x_left = _parse_float_line(raw_lines[2], n_tasks, "x_left")
    x_right = _parse_float_line(raw_lines[3], n_tasks, "x_right")
    y_bottom = _parse_float_line(raw_lines[4], n_tasks, "y_bottom")
    y_top = _parse_float_line(raw_lines[5], n_tasks, "y_top")

    tasks: list[TaskRegion] = []
    for idx in range(n_tasks):
        xl = x_left[idx]
        xr = x_right[idx]
        yb = y_bottom[idx]
        yt = y_top[idx]
        if xl >= xr:
            raise ValueError(f"Task {idx + 1} has non-positive width: {xl} >= {xr}")
        if yb >= yt:
            raise ValueError(f"Task {idx + 1} has non-positive height: {yb} >= {yt}")
        tasks.append(
            TaskRegion(
                task_id=idx + 1,
                x_left=xl,
                y_bottom=yb,
                x_right=xr,
                y_top=yt,
            )
        )

    instance = Instance(
        name=file_path.stem,
        depot=(0.0, 0.0),
        robot_count=n_robots,
        sweep_speed=sweep_speed,
        travel_speed=travel_speed,
        sweep_width=sweep_width,
        turning_time=turning_time,
        tasks=tasks,
        rep_id=rep_id,
    )
    return instance


def _parse_float_line(line: str, expected_count: int, label: str) -> list[float]:
    values = line.split()
    if len(values) != expected_count:
        raise ValueError(f"Line for {label} must contain {expected_count} values")
    try:
        return [float(val) for val in values]
    except ValueError as exc:
        raise ValueError(f"Failed to parse {label} line as floats") from exc
