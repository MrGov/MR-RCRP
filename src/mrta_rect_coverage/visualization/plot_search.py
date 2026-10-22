"""Visualization helpers for search trajectories."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable

import matplotlib.pyplot as plt


def plot_convergence_curve(
    iteration_history: Iterable[dict],
    output_dir: Path,
    *,
    filename: str = "convergence_curve.png",
    dpi: int = 120,
) -> Path:
    """Plot best/current makespan over ALNS iterations."""

    output_dir.mkdir(parents=True, exist_ok=True)
    data = list(iteration_history)
    iters = [row["iteration"] for row in data]
    current = [row["current_makespan"] for row in data]
    best = [row["best_makespan"] for row in data]

    fig, ax = plt.subplots(figsize=(8, 4), dpi=dpi)
    ax.plot(iters, current, label="current", color="#d1495b", linewidth=1.2)
    ax.plot(iters, best, label="best", color="#00798c", linewidth=1.8)
    ax.set_xlabel("Iteration")
    ax.set_ylabel("Makespan")
    ax.set_title("ALNS Convergence")
    ax.legend()
    ax.grid(alpha=0.25)
    fig.tight_layout()

    path = output_dir / filename
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_operator_usage_histogram(
    operator_usage_stats: Dict[str, Dict[str, object]],
    output_dir: Path,
    *,
    filename: str = "operator_usage.png",
    dpi: int = 120,
) -> Path:
    """Plot per-operator usage counts for destroy and repair pools."""

    output_dir.mkdir(parents=True, exist_ok=True)

    names = []
    uses = []
    for group, stats in operator_usage_stats.items():
        for name, rec in stats.items():
            names.append(f"{group}:{name}")
            uses.append(getattr(rec, "uses", 0))

    fig, ax = plt.subplots(figsize=(10, 4), dpi=dpi)
    ax.bar(range(len(names)), uses, color="#edae49")
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels(names, rotation=35, ha="right")
    ax.set_ylabel("Uses")
    ax.set_title("Operator Usage")
    fig.tight_layout()

    path = output_dir / filename
    fig.savefig(path)
    plt.close(fig)
    return path
