"""Batch benchmarking and ablation utilities."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Iterable, List

from ..core.instance_loader import load_instance, parse_instance_filename
from ..heuristics.alns_solver import ALNSConfig, solve_with_alns
from ..heuristics.baseline_solver import baseline_solve
from ..llm.mock_advisor import MockAdvisor
from ..llm.rule_based_advisor import RuleBasedAdvisor


ALLOWED_ABLATION_MODES = frozenset(
    {"baseline", "baseline_stronger_ls", "alns", "alns_advisor"}
)


@dataclass
class BenchmarkResult:
    instance: str
    robots: int
    tasks: int
    rep: int
    mode: str
    makespan: float
    runtime_sec: float


def list_instance_files(data_dir: Path) -> List[Path]:
    return sorted(path for path in data_dir.glob("R*_T*_*.txt") if path.is_file())


def run_ablation_mode(instance_path: Path, mode: str) -> BenchmarkResult:
    if mode not in ALLOWED_ABLATION_MODES:
        raise ValueError(f"Unknown ablation mode: {mode}")
    instance = load_instance(instance_path)
    robots, tasks, rep = parse_instance_filename(instance_path)

    t0 = perf_counter()
    if mode == "baseline":
        _, evaluation = baseline_solve(instance, enable_local_search=False)
    elif mode == "baseline_stronger_ls":
        _, evaluation = baseline_solve(
            instance,
            enable_local_search=True,
            use_stronger_local_search=True,
            max_iterations=120,
        )
    elif mode == "alns":
        result = solve_with_alns(
            instance,
            config=ALNSConfig(iterations=180, acceptance="simulated_annealing"),
        )
        evaluation = result.best_evaluation
    elif mode == "alns_advisor":
        result = solve_with_alns(
            instance,
            config=ALNSConfig(
                iterations=180,
                acceptance="simulated_annealing",
            ),
            advisor=RuleBasedAdvisor(),
        )
        evaluation = result.best_evaluation
    elapsed = perf_counter() - t0

    return BenchmarkResult(
        instance=instance.name,
        robots=robots,
        tasks=tasks,
        rep=rep,
        mode=mode,
        makespan=evaluation.makespan,
        runtime_sec=elapsed,
    )


def run_batch_benchmark(
    data_dir: Path,
    output_csv: Path,
    modes: Iterable[str],
) -> List[BenchmarkResult]:
    results: List[BenchmarkResult] = []
    files = list_instance_files(data_dir)

    for file_path in files:
        for mode in modes:
            results.append(run_ablation_mode(file_path, mode))

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["instance", "robots", "tasks", "rep", "mode", "makespan", "runtime_sec"],
        )
        writer.writeheader()
        for row in results:
            writer.writerow(
                {
                    "instance": row.instance,
                    "robots": row.robots,
                    "tasks": row.tasks,
                    "rep": row.rep,
                    "mode": row.mode,
                    "makespan": f"{row.makespan:.6f}",
                    "runtime_sec": f"{row.runtime_sec:.6f}",
                }
            )

    return results
