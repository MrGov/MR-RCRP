from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Iterable, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mrta_rect_coverage.experiments.r3_diagnostics import (  # noqa: E402
    DIAGNOSTIC_SCHEMA_VERSION,
    write_diagnostic_outputs,
)


RAW_STEMS = ("track-a", "track-b-development", "held-out")
DEVELOPMENT_SOURCES = frozenset({"A", "B-development"})
FEATURE_FIELDS = (
    "n_tasks",
    "n_robots",
    "task_robot_ratio",
    "spatial_dispersion",
    "pairwise_distance_mean",
    "relative_hv_gap_mean",
    "fraction_near_tie",
    "heavy_task_ratio",
    "state_variability_mean",
    "estimated_travel_pressure",
    "estimated_coverage_pressure",
)
CORRELATION_TARGETS = (
    "baseline_makespan_mean",
    "relative_improvement_mean",
    "initial_route_cost_cv_mean",
    "assignment_gain_mean",
    "ordering_gain_mean",
    "local_search_gain_mean",
    "state_changed_fraction",
    "dp_cascade_ratio",
    "longest_stagnation_fraction",
    "dp_calls_mean",
)


def normalize_run_identity(run: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy with a source-aware, collision-resistant run identity."""

    normalized = dict(run)
    source = _identity_token(str(run["source_track"]))
    identity = _identity_token(str(run.get("family_id") or run["instance_id"]))
    config_hash = str(run["solver_config_hash"])
    normalized["run_id"] = (
        f"{source}-{identity}-seed-{int(run['solver_seed'])}-{config_hash[:12]}"
    )
    normalized["behavior_id"] = _behavior_id(run)
    normalized["instance_uid"] = _instance_uid(run)
    return normalized


def load_raw_artifacts(raw_dir: str | Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Load the three precomputed R3 tracks without mutating raw artifacts."""

    source = Path(raw_dir)
    runs: list[dict[str, Any]] = []
    instance_rows: list[dict[str, Any]] = []
    for stem in RAW_STEMS:
        track_runs = _read_json_list(source / f"{stem}_runs.json")
        track_instances = _read_json_list(source / f"{stem}_instances.json")
        runs.extend(normalize_run_identity(run) for run in track_runs)
        for row in track_instances:
            enriched = dict(row)
            enriched["behavior_id"] = _behavior_id(row)
            enriched["instance_uid"] = _instance_uid(row)
            instance_rows.append(enriched)

    run_ids = [str(run["run_id"]) for run in runs]
    if len(run_ids) != len(set(run_ids)):
        raise ValueError("normalized R3 run IDs are not unique")
    instance_uids = [str(row["instance_uid"]) for row in instance_rows]
    if len(instance_uids) != len(set(instance_uids)):
        raise ValueError("R3 inventory contains duplicate source-aware instance IDs")
    for run in runs:
        if run.get("diagnostic_schema_version") != DIAGNOSTIC_SCHEMA_VERSION:
            raise ValueError("unexpected R3 diagnostic schema version")
        if run.get("status") != "completed":
            raise ValueError("R3 raw run is not completed")
        if run.get("provider_used") is not False:
            raise ValueError("R3 raw run indicates provider use")
        if run.get("generated_operator_used") is not False:
            raise ValueError("R3 raw run indicates generated operator use")
    return runs, instance_rows


def summarize_behavior(
    runs: Sequence[Mapping[str, Any]],
    instance_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Aggregate seed-level runs into source-aware behavioral instances."""

    rows_by_behavior: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in instance_rows:
        rows_by_behavior[str(row.get("behavior_id") or _behavior_id(row))].append(row)
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for run in runs:
        grouped[str(run.get("behavior_id") or _behavior_id(run))].append(run)

    output: list[dict[str, Any]] = []
    for behavior_id, selected in sorted(grouped.items()):
        selected = sorted(selected, key=lambda row: int(row["solver_seed"]))
        matching_features = rows_by_behavior.get(behavior_id, [])
        if len(matching_features) != 1:
            raise ValueError(
                f"behavior group {behavior_id} requires exactly one inventory row"
            )
        feature_row = matching_features[0]
        accepted = [
            iteration
            for run in selected
            for iteration in run.get("iterations", [])
            if iteration.get("accepted")
        ]
        run_count = len(selected)
        iterations_per_run = int(selected[0].get("iterations") and len(selected[0]["iterations"]) or 0)
        assignment_gain = sum(
            max(0.0, float(row["repair_gain"]))
            for row in accepted
            if row["repair_change_class"] == "assignment"
        )
        ordering_gain = sum(
            max(0.0, float(row["repair_gain"]))
            for row in accepted
            if row["repair_change_class"] == "ordering"
        )
        local_search_gain = sum(
            max(0.0, float(row["local_search_gain"])) for row in accepted
        )
        summary: dict[str, Any] = {
            "diagnostic_schema_version": DIAGNOSTIC_SCHEMA_VERSION,
            "behavior_id": behavior_id,
            "instance_id": selected[0]["instance_id"],
            "source_track": selected[0]["source_track"],
            "family_id": selected[0].get("family_id"),
            "replicate_id": selected[0]["replicate_id"],
            "run_count": run_count,
            "iterations_per_run": iterations_per_run,
            "accepted_move_count": len(accepted),
            "accepted_moves_per_run": len(accepted) / run_count,
            "initial_makespan_mean": _mean_field(selected, "initial_makespan"),
            "baseline_makespan_mean": _mean_field(selected, "baseline_makespan"),
            "best_makespan_mean": _mean_field(selected, "best_makespan"),
            "relative_improvement_mean": _mean_field(selected, "relative_improvement"),
            "relative_improvement_std": _std_field(selected, "relative_improvement"),
            "runtime_sec_mean": _mean_field(selected, "runtime_sec"),
            "iteration_to_best_mean": _mean_field(selected, "iteration_to_best"),
            "longest_stagnation_mean": _mean_field(selected, "longest_stagnation"),
            "longest_stagnation_fraction": _mean_field(selected, "longest_stagnation") / max(1, iterations_per_run),
            "final_stagnation_mean": _mean_field(selected, "final_stagnation"),
            "initial_route_cost_cv_mean": _mean_nested(selected, "initial_route_balance", "route_cost_cv"),
            "best_route_cost_cv_mean": _mean_nested(selected, "best_route_balance", "route_cost_cv"),
            "initial_bottleneck_gap_rel_mean": _mean_nested(selected, "initial_route_balance", "bottleneck_gap_rel"),
            "best_bottleneck_gap_rel_mean": _mean_nested(selected, "best_route_balance", "bottleneck_gap_rel"),
            "assignment_gain_mean": assignment_gain / run_count,
            "ordering_gain_mean": ordering_gain / run_count,
            "local_search_gain_mean": local_search_gain / run_count,
            "positive_bottleneck_relief_mean": sum(max(0.0, float(row["bottleneck_relief"])) for row in accepted) / run_count,
            "state_changed_fraction": _mean_iterations(accepted, "state_changed_fraction"),
            "mode_switch_fraction": _mean_iterations(accepted, "mode_switch_fraction"),
            "dp_cascade_ratio": _mean_iterations(accepted, "dp_cascade_ratio"),
            "cascade_event_fraction": _mean_iterations(accepted, "cascade_count"),
            "dp_calls_mean": _mean_nested(selected, "dp_workload", "calls"),
            "dp_cache_hit_rate_mean": _mean_nested(selected, "dp_workload", "cache_hit_rate"),
            "dp_compute_time_sec_mean": _mean_nested(selected, "dp_workload", "compute_time_sec"),
            "dp_runtime_share_mean": mean(
                float(run["dp_workload"]["compute_time_sec"]) / float(run["runtime_sec"])
                for run in selected
            ),
            "travel_share_mean": _mean_nested(selected, "best_objective_decomposition", "travel_share"),
            "coverage_share_mean": _mean_nested(selected, "best_objective_decomposition", "coverage_share"),
            "turning_share_mean": _mean_nested(selected, "best_objective_decomposition", "turning_share"),
        }
        for key, value in feature_row.items():
            if key not in summary:
                summary[key] = value
        output.append(summary)
    return output


def summarize_operators(runs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate operator associations using pre-local-search repair gain."""

    grouped: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    run_counts: dict[str, set[str]] = defaultdict(set)
    for run in runs:
        behavior_id = str(run.get("behavior_id") or _behavior_id(run))
        run_counts[behavior_id].add(str(run["run_id"]))
        for iteration in run.get("iterations", []):
            grouped[(behavior_id, "destroy", str(iteration["destroy"]))].append(iteration)
            grouped[(behavior_id, "repair", str(iteration["repair"]))].append(iteration)

    rows: list[dict[str, Any]] = []
    for (behavior_id, operator_type, operator_name), selected in sorted(grouped.items()):
        accepted = [row for row in selected if row["accepted"]]
        positive_gain = sum(max(0.0, float(row["repair_gain"])) for row in accepted)
        positive_objective_gain = sum(
            max(0.0, float(row["objective_gain"])) for row in accepted
        )
        rows.append(
            {
                "behavior_id": behavior_id,
                "source_track": behavior_id.split(":", 1)[0],
                "operator_type": operator_type,
                "operator_name": operator_name,
                "run_count": len(run_counts[behavior_id]),
                "usage_count": len(selected),
                "accepted_count": len(accepted),
                "improvement_count": sum(float(row["repair_gain"]) > 1e-9 for row in accepted),
                "accepted_rate": len(accepted) / len(selected),
                "positive_pre_ls_gain": positive_gain,
                "positive_pre_ls_gain_per_use": positive_gain / len(selected),
                "positive_objective_gain": positive_objective_gain,
                "positive_objective_gain_per_use": positive_objective_gain
                / len(selected),
                "state_changed_fraction": _mean_iterations(accepted, "state_changed_fraction"),
                "dp_cascade_ratio": _mean_iterations(accepted, "dp_cascade_ratio"),
            }
        )
    return rows


def spearman_correlation(x_values: Sequence[float], y_values: Sequence[float]) -> float | None:
    """Compute Spearman rho with average ranks and no inferential p-value."""

    if len(x_values) != len(y_values) or len(x_values) < 2:
        return None
    x_ranks = _average_ranks(x_values)
    y_ranks = _average_ranks(y_values)
    x_mean = mean(x_ranks)
    y_mean = mean(y_ranks)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_ranks, y_ranks))
    x_scale = math.sqrt(sum((x - x_mean) ** 2 for x in x_ranks))
    y_scale = math.sqrt(sum((y - y_mean) ** 2 for y in y_ranks))
    if x_scale == 0.0 or y_scale == 0.0:
        return None
    return numerator / (x_scale * y_scale)


def compute_correlations(behavior_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    development = [row for row in behavior_rows if row["source_track"] in DEVELOPMENT_SOURCES]
    rows: list[dict[str, Any]] = []
    for feature in FEATURE_FIELDS:
        for target in CORRELATION_TARGETS:
            pairs = [
                (float(row[feature]), float(row[target]))
                for row in development
                if row.get(feature) is not None and row.get(target) is not None
            ]
            rho = spearman_correlation(
                [pair[0] for pair in pairs], [pair[1] for pair in pairs]
            )
            rows.append(
                {
                    "scope": "development-only",
                    "feature": feature,
                    "behavior": target,
                    "n": len(pairs),
                    "spearman_rho": rho,
                }
            )
    return rows


def write_analysis(
    output_dir: str | Path,
    *,
    raw_dir: str | Path,
    runs: Sequence[Mapping[str, Any]],
    instance_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Path]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    paths = write_diagnostic_outputs(destination, runs=runs, instance_rows=instance_rows)
    behavior_rows = summarize_behavior(runs, instance_rows)
    operator_rows = summarize_operators(runs)
    correlation_rows = compute_correlations(behavior_rows)
    extra_paths = {
        "behavior_summary": destination / "behavior_summary.csv",
        "operator_regime_summary": destination / "operator_regime_summary.csv",
        "feature_correlations": destination / "feature_correlations.csv",
        "analysis_summary": destination / "analysis_summary.json",
    }
    _write_csv(extra_paths["behavior_summary"], behavior_rows)
    _write_csv(extra_paths["operator_regime_summary"], operator_rows)
    _write_csv(extra_paths["feature_correlations"], correlation_rows)
    _write_summary_json(extra_paths["analysis_summary"], behavior_rows, operator_rows)
    plot_paths = generate_plots(destination / "plots", behavior_rows, operator_rows)

    metadata_path = paths["metadata"]
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata.update(
        {
            "analysis_scope": "R3 built-in-only diagnostics",
            "behavior_instance_count": len(behavior_rows),
            "development_behavior_instance_count": sum(row["source_track"] in DEVELOPMENT_SOURCES for row in behavior_rows),
            "held_out_behavior_instance_count": sum(row["source_track"] == "B-held-out" for row in behavior_rows),
            "diagnostic_budget": {
                "iterations": 100,
                "destroy_fraction": 0.25,
                "acceptance": "simulated_annealing",
                "local_search_steps_per_iteration": 1,
                "small_scale_seeds": [0, 1, 2, 3, 4],
                "large_scale_and_held_out_seeds": [0, 1, 2],
            },
            "raw_input_sha256": {
                path.name: _sha256(path)
                for stem in RAW_STEMS
                for path in (Path(raw_dir) / f"{stem}_runs.json", Path(raw_dir) / f"{stem}_instances.json")
            },
            "normalized_run_ids": True,
            "plot_count": len(plot_paths) // 2,
        }
    )
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {**paths, **extra_paths, **plot_paths}


def generate_plots(
    plot_dir: str | Path,
    behavior_rows: Sequence[Mapping[str, Any]],
    operator_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Path]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    destination = Path(plot_dir)
    destination.mkdir(parents=True, exist_ok=True)
    _configure_matplotlib(plt)
    rows = sorted(behavior_rows, key=lambda row: (int(row["n_tasks"]), str(row["behavior_id"])))
    labels = [_short_label(row) for row in rows]
    colors = [_source_color(str(row["source_track"])) for row in rows]
    paths: dict[str, Path] = {}

    fig, ax = plt.subplots(figsize=(5.5, 3.4))
    for row, color in zip(rows, colors):
        ax.errorbar(row["n_tasks"], row["relative_improvement_mean"], yerr=row["relative_improvement_std"], marker=_source_marker(str(row["source_track"])), color=color, capsize=2, linestyle="none")
    ax.set(xlabel="Number of tasks", ylabel="Relative improvement", title="ALNS improvement across scale")
    _source_legend(ax)
    paths.update(_save_figure(fig, destination, "01_relative_improvement_vs_task_count"))

    fig, ax = plt.subplots(figsize=(6.75, 3.4))
    x = np.arange(len(rows))
    for index, row in enumerate(rows):
        ax.plot([index, index], [row["initial_route_cost_cv_mean"], row["best_route_cost_cv_mean"]], color="#8C8C8C", linewidth=1.2)
    ax.scatter(x, [row["initial_route_cost_cv_mean"] for row in rows], color="#D55E00", marker="o", label="Initial", zorder=3)
    ax.scatter(x, [row["best_route_cost_cv_mean"] for row in rows], color="#0072B2", marker="s", label="Best", zorder=3)
    ax.set_xticks(x, labels, rotation=35, ha="right")
    ax.set(ylabel="Route-cost coefficient of variation", title="Route imbalance before and after ALNS")
    ax.legend()
    paths.update(_save_figure(fig, destination, "02_route_imbalance_before_after"))

    fig, ax = plt.subplots(figsize=(6.75, 3.6))
    width = 0.24
    for offset, field, label, color in (
        (-width, "assignment_gain_mean", "Assignment repair", "#0072B2"),
        (0.0, "ordering_gain_mean", "Ordering repair", "#E69F00"),
        (width, "local_search_gain_mean", "Local search", "#009E73"),
    ):
        ax.bar(x + offset, [row[field] for row in rows], width=width, label=label, color=color)
    ax.set_xticks(x, labels, rotation=35, ha="right")
    ax.set(ylabel="Mean cumulative positive gain per run", title="Accepted-move improvement attribution")
    ax.legend(ncol=3)
    paths.update(_save_figure(fig, destination, "03_assignment_ordering_local_search"))

    fig, ax = plt.subplots(figsize=(6.75, 3.6))
    left = np.zeros(len(rows))
    for field, label, color in (
        ("travel_share_mean", "Travel", "#0072B2"),
        ("coverage_share_mean", "Coverage traversal", "#E69F00"),
        ("turning_share_mean", "Turning", "#009E73"),
    ):
        values = np.array([row[field] for row in rows])
        ax.barh(x, values, left=left, label=label, color=color)
        left += values
    ax.set_yticks(x, labels)
    ax.invert_yaxis()
    ax.set(xlabel="Share of summed best-route cost", title="Objective decomposition")
    ax.legend(ncol=3, loc="lower center", bbox_to_anchor=(0.5, 1.0))
    paths.update(_save_figure(fig, destination, "04_objective_decomposition"))

    fig, ax = plt.subplots(figsize=(5.5, 3.5))
    _scatter_behavior(ax, rows, "relative_hv_gap_mean", "state_changed_fraction")
    ax.set(xlabel="Mean relative H/V processing gap", ylabel="Accepted-move state-switch fraction", title="H/V sensitivity and DP state switching")
    paths.update(_save_figure(fig, destination, "05_state_switch_vs_hv_sensitivity"))

    fig, axes = plt.subplots(1, 2, figsize=(6.75, 3.0), sharey=True)
    _scatter_behavior(axes[0], rows, "relative_hv_gap_mean", "dp_cascade_ratio", annotate=False)
    _scatter_behavior(axes[1], rows, "state_variability_mean", "dp_cascade_ratio", annotate=False)
    axes[0].set(xlabel="Mean relative H/V gap", ylabel="Mean DP cascade ratio")
    axes[1].set(xlabel="Mean isolated state variability")
    fig.suptitle("Inner-DP cascade versus intrinsic state structure", fontsize=11, fontweight="bold")
    paths.update(_save_figure(fig, destination, "06_cascade_vs_state_structure"))

    controlled = [row for row in operator_rows if row["operator_type"] == "destroy" and row["source_track"] != "A"]
    controlled_ids = sorted({str(row["behavior_id"]) for row in controlled})
    operators = ["random_destroy", "geometry_aware_destroy", "bottleneck_route_destroy"]
    fig, ax = plt.subplots(figsize=(6.75, 3.4))
    cx = np.arange(len(controlled_ids))
    width = 0.24
    operator_colors = ("#0072B2", "#E69F00", "#009E73")
    for index, (operator, color) in enumerate(zip(operators, operator_colors)):
        lookup = {(row["behavior_id"], row["operator_name"]): row for row in controlled}
        values = [lookup[(behavior_id, operator)]["positive_pre_ls_gain_per_use"] for behavior_id in controlled_ids]
        ax.bar(cx + (index - 1) * width, values, width=width, label=operator.replace("_", " "), color=color)
    controlled_labels = [behavior_id.split(":", 1)[1].replace("F_", "") for behavior_id in controlled_ids]
    ax.set_xticks(cx, controlled_labels, rotation=25, ha="right")
    ax.set(ylabel="Positive pre-LS repair gain per use", title="Destroy-operator association by controlled family")
    ax.legend(ncol=3)
    paths.update(_save_figure(fig, destination, "07_operator_contribution_by_regime"))

    fig, axes = plt.subplots(1, 2, figsize=(6.75, 3.0))
    for row, color in zip(rows, colors):
        marker = _source_marker(str(row["source_track"]))
        axes[0].scatter(row["n_tasks"], row["dp_calls_mean"], color=color, marker=marker)
        axes[1].scatter(row["n_tasks"], row["runtime_sec_mean"], color=color, marker=marker)
    axes[0].set(xlabel="Number of tasks", ylabel="Mean Route-DP calls", yscale="log")
    axes[1].set(xlabel="Number of tasks", ylabel="Mean runtime (s)", yscale="log")
    _source_legend(axes[0])
    fig.suptitle("Route-DP workload and runtime scaling", fontsize=11, fontweight="bold")
    paths.update(_save_figure(fig, destination, "08_dp_workload_runtime_vs_scale"))
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Consolidate and analyze completed R3 diagnostics")
    parser.add_argument("--raw-dir", type=Path, default=PROJECT_ROOT / "outputs" / "r3_diagnostics" / "raw")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "outputs" / "r3_diagnostics")
    args = parser.parse_args()
    runs, instance_rows = load_raw_artifacts(args.raw_dir)
    paths = write_analysis(args.output_dir, raw_dir=args.raw_dir, runs=runs, instance_rows=instance_rows)
    print(f"R3 analysis complete: runs={len(runs)} instances={len(instance_rows)} artifacts={len(paths)}")


def _write_summary_json(path: Path, behavior_rows: Sequence[Mapping[str, Any]], operator_rows: Sequence[Mapping[str, Any]]) -> None:
    development = [row for row in behavior_rows if row["source_track"] in DEVELOPMENT_SOURCES]
    held_out = [row for row in behavior_rows if row["source_track"] == "B-held-out"]
    top_destroy: dict[str, str] = {}
    for behavior_id in {str(row["behavior_id"]) for row in operator_rows}:
        candidates = [row for row in operator_rows if row["behavior_id"] == behavior_id and row["operator_type"] == "destroy"]
        if candidates:
            top_destroy[behavior_id] = str(
                max(
                    candidates,
                    key=lambda row: float(row["positive_objective_gain_per_use"]),
                )["operator_name"]
            )
    payload = {
        "diagnostic_schema_version": DIAGNOSTIC_SCHEMA_VERSION,
        "development_instance_count": len(development),
        "held_out_instance_count": len(held_out),
        "development_correlations": {
            "relative_hv_gap_vs_state_switch": spearman_correlation([float(row["relative_hv_gap_mean"]) for row in development], [float(row["state_changed_fraction"]) for row in development]),
            "relative_hv_gap_vs_cascade": spearman_correlation([float(row["relative_hv_gap_mean"]) for row in development], [float(row["dp_cascade_ratio"]) for row in development]),
            "state_variability_vs_state_switch": spearman_correlation([float(row["state_variability_mean"]) for row in development], [float(row["state_changed_fraction"]) for row in development]),
            "heavy_task_ratio_vs_initial_route_cv": spearman_correlation([float(row["heavy_task_ratio"]) for row in development], [float(row["initial_route_cost_cv_mean"]) for row in development]),
        },
        "held_out": [
            {
                "behavior_id": row["behavior_id"],
                "relative_hv_gap_mean": row["relative_hv_gap_mean"],
                "state_changed_fraction": row["state_changed_fraction"],
                "dp_cascade_ratio": row["dp_cascade_ratio"],
                "assignment_gain_mean": row["assignment_gain_mean"],
                "ordering_gain_mean": row["ordering_gain_mean"],
                "top_destroy_operator": top_destroy[row["behavior_id"]],
            }
            for row in held_out
        ],
        "boundaries": {
            "real_llm_used": False,
            "provider_used": False,
            "generated_operator_used": False,
            "final_test_used": False,
            "gate_p2": "OPEN",
            "t6_authorized": False,
        },
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _configure_matplotlib(plt: Any) -> None:
    plt.rcParams.update({
        "font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"],
        "font.size": 9, "axes.titlesize": 11, "axes.titleweight": "bold",
        "axes.labelsize": 9, "xtick.labelsize": 7.5, "ytick.labelsize": 7.5,
        "legend.fontsize": 7.5, "legend.frameon": False, "figure.dpi": 150,
        "savefig.dpi": 300, "savefig.bbox": "tight", "savefig.pad_inches": 0.08,
        "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
        "grid.alpha": 0.15, "grid.linewidth": 0.6,
    })


def _scatter_behavior(ax: Any, rows: Sequence[Mapping[str, Any]], x_field: str, y_field: str, *, annotate: bool = True) -> None:
    for row in rows:
        ax.scatter(row[x_field], row[y_field], color=_source_color(str(row["source_track"])), marker=_source_marker(str(row["source_track"])), s=34, edgecolors="white", linewidth=0.5)
        if annotate:
            ax.annotate(_short_label(row), (row[x_field], row[y_field]), xytext=(3, 3), textcoords="offset points", fontsize=6)


def _save_figure(fig: Any, destination: Path, stem: str) -> dict[str, Path]:
    import matplotlib.pyplot as plt

    pdf = destination / f"{stem}.pdf"
    png = destination / f"{stem}.png"
    fig.tight_layout()
    fig.savefig(pdf)
    fig.savefig(png, dpi=300)
    plt.close(fig)
    return {f"plot_{stem}_pdf": pdf, f"plot_{stem}_png": png}


def _source_legend(ax: Any) -> None:
    from matplotlib.lines import Line2D

    labels = {
        "A": "Track A",
        "B-development": "Controlled development",
        "B-held-out": "Held-out",
    }
    handles = [
        Line2D(
            [0], [0], linestyle="none", marker=_source_marker(source),
            color=_source_color(source), label=label, markersize=5,
        )
        for source, label in labels.items()
    ]
    ax.legend(handles=handles)


def _source_color(source: str) -> str:
    return {"A": "#0072B2", "B-development": "#E69F00", "B-held-out": "#009E73"}[source]


def _source_marker(source: str) -> str:
    return {"A": "o", "B-development": "s", "B-held-out": "^"}[source]


def _short_label(row: Mapping[str, Any]) -> str:
    return str(row.get("family_id") or row["instance_id"]).replace("F_", "")


def _mean_field(rows: Sequence[Mapping[str, Any]], key: str) -> float:
    return mean(float(row[key]) for row in rows)


def _std_field(rows: Sequence[Mapping[str, Any]], key: str) -> float:
    values = [float(row[key]) for row in rows]
    return pstdev(values) if len(values) > 1 else 0.0


def _mean_nested(rows: Sequence[Mapping[str, Any]], parent: str, key: str) -> float:
    return mean(float(row[parent][key]) for row in rows)


def _mean_iterations(rows: Sequence[Mapping[str, Any]], key: str) -> float:
    return mean(float(row[key]) for row in rows) if rows else 0.0


def _average_ranks(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(order):
        end = cursor + 1
        while end < len(order) and values[order[end]] == values[order[cursor]]:
            end += 1
        average_rank = (cursor + 1 + end) / 2.0
        for index in order[cursor:end]:
            ranks[index] = average_rank
        cursor = end
    return ranks


def _behavior_id(row: Mapping[str, Any]) -> str:
    return f"{row['source_track']}:{row.get('family_id') or row['instance_id']}"


def _instance_uid(row: Mapping[str, Any]) -> str:
    return f"{row['source_track']}:{row['instance_id']}"


def _identity_token(value: str) -> str:
    return value.replace("/", "-").replace(" ", "-")


def _read_json_list(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
        raise ValueError(f"expected a JSON list of objects: {path}")
    return payload


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    main()
