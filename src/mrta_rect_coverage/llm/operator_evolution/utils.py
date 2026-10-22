"""Utility helpers for operator evolution pipelines."""
from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Iterable, List

from ...core.models import Instance, MultiRobotSolution


def clone_solution(solution: MultiRobotSolution) -> MultiRobotSolution:
    return MultiRobotSolution(routes=[list(route) for route in solution.routes])


def is_solution_complete(solution: MultiRobotSolution, instance: Instance) -> bool:
    all_tasks = [task.task_id for task in instance.tasks]
    flattened = [task_id for route in solution.routes for task_id in route]
    return sorted(flattened) == sorted(all_tasks)


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if is_dataclass(payload):
        payload = asdict(payload)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: List[dict], fieldnames: List[str]) -> None:
    import csv

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
