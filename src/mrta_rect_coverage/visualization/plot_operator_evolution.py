"""Plots for operator evolution experiments."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import List

import matplotlib.pyplot as plt


def plot_round_best_trend(summary_json: Path, output_dir: Path, *, dpi: int = 120) -> Path:
    payload = json.loads(summary_json.read_text(encoding="utf-8"))
    rounds = payload.get("rounds", [])

    xs = [row["round_id"] for row in rounds]
    ys = []
    for row in rounds:
        leaderboard = row.get("leaderboard", [])
        best = leaderboard[0]["avg_relative_improvement"] if leaderboard else 0.0
        ys.append(best)

    output_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(6, 4), dpi=dpi)
    ax.plot(xs, ys, marker="o", color="#2a9d8f")
    ax.set_xlabel("Round")
    ax.set_ylabel("Best Avg Relative Improvement")
    ax.set_title("Operator Evolution Trend")
    ax.grid(alpha=0.3)
    fig.tight_layout()

    path = output_dir / "round_best_trend.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_candidate_leaderboard(round_metrics_csv: Path, output_dir: Path, *, top_k: int = 10, dpi: int = 120) -> Path:
    rows: List[dict] = []
    with round_metrics_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            row["avg_relative_improvement"] = float(row["avg_relative_improvement"])
            rows.append(row)

    rows.sort(key=lambda r: r["avg_relative_improvement"], reverse=True)
    top = rows[:top_k]

    names = [f"{row['operator_type']}:{row['operator_id']}" for row in top]
    values = [row["avg_relative_improvement"] for row in top]

    output_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 4), dpi=dpi)
    ax.bar(range(len(names)), values, color="#f4a261")
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels(names, rotation=35, ha="right")
    ax.set_ylabel("Avg Relative Improvement")
    ax.set_title("Candidate Leaderboard")
    fig.tight_layout()

    path = output_dir / "candidate_leaderboard.png"
    fig.savefig(path)
    plt.close(fig)
    return path
