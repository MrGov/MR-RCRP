"""Small real-provider C1 evolution and full-ALNS pilot."""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean
from time import perf_counter

from ..core.instance_loader import load_instance
from ..heuristics.alns_solver import ALNSConfig, ALNSSolver
from ..llm.operator_evolution.candidate_loader import load_and_validate_candidate
from .e1_real_llm_pilot import E1PilotConfig, _evaluate_candidate, compute_exact_dp_behavior, run_e1_pilot
from ..llm.operator_evolution.evaluator import build_repair_benchmark_cases


def freeze_instances(root: Path, output: Path) -> dict:
    """Freeze a balanced, non-overlapping subset of existing top-level data."""
    paths = sorted((root / "data").glob("R*_T*_*.txt"))
    inventory = []
    for path in paths:
        instance = load_instance(path)
        widths = [t.x_right - t.x_left for t in instance.tasks]
        heights = [t.y_top - t.y_bottom for t in instance.tasks]
        centers = [((t.x_left + t.x_right) / 2, (t.y_bottom + t.y_top) / 2) for t in instance.tasks]
        inventory.append({
            "path": str(path.relative_to(root)), "robots": instance.robot_count,
            "tasks": instance.task_count, "mean_area": mean(w * h for w, h in zip(widths, heights)),
            "mean_depot_distance": mean(x + y for x, y in centers),
            "mean_aspect_imbalance": mean(abs(w - h) / max(w, h) for w, h in zip(widths, heights)),
        })
    # Three structural proxies: per-robot load, travel distance, and aspect imbalance.
    scores = {
        "high_load": lambda r: r["tasks"] / r["robots"] * r["mean_area"],
        "travel_dominated": lambda r: r["mean_depot_distance"] / max(1, r["mean_area"] ** 0.5),
        "hv_sensitive": lambda r: r["mean_aspect_imbalance"],
    }
    used = set()
    selected = []
    for family, score in scores.items():
        ranked = sorted(inventory, key=lambda r: (score(r), r["path"]), reverse=True)
        for row in ranked:
            if row["path"] in used:
                continue
            used.add(row["path"])
            selected.append({**row, "family": family})
            if sum(x["family"] == family for x in selected) == 8:
                break
    # Within every structural family, reserve four development, two validation,
    # and two heldout instances. The list and split are persisted before evolution.
    for family in scores:
        rows = [r for r in selected if r["family"] == family]
        for i, row in enumerate(rows):
            row["split"] = "evolution-development" if i < 4 else "selection-validation" if i < 6 else "confirmatory-heldout"
    output.mkdir(parents=True, exist_ok=True)
    (output / "inventory.json").write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    manifest = {"selection_rule": "fixed structural scores, descending with path tie-break; 8 per family", "instances": selected}
    (output / "instance_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def select_elite(root: Path, evolution_dir: Path, manifest: dict, seeds: tuple[int, ...], output: Path | None = None) -> dict:
    output = output or evolution_dir.parent
    output.mkdir(parents=True, exist_ok=True)
    (output / "selection_trials.jsonl").write_text("", encoding="utf-8")
    paths = [root / r["path"] for r in manifest["instances"] if r["split"] == "selection-validation"]
    cases = build_repair_benchmark_cases(paths)
    selected = {}
    for method, branch in (("L0", "L0"), ("L1", "F1"), ("L2", "F2")):
        elite = json.loads((evolution_dir / branch / "elite_archive.json").read_text(encoding="utf-8"))
        comparisons = []
        for row in elite:
            loaded = load_and_validate_candidate(
                path=Path(row["source_path"]), operator_type="repair", round_id=row["generation"],
                source="langchain_openai_compatible", description="E2 selected elite",
                allow_unsafe_candidate_execution=True,
            )
            if loaded.callable_obj is None or loaded.validation.code_hash != row["source_hash"]:
                continue
            result = _evaluate_candidate(loaded, cases, seeds, 2000.0)
            with (output / "selection_trials.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"method": method, "source_hash": row["source_hash"], "evaluation": result}) + "\n")
            if result["feasible_count"] == result["executed_count"] and result["executed_count"]:
                comparisons.append({"source_path": row["source_path"], "source_hash": row["source_hash"],
                                    "operator_id": row["operator_id"], "generation": row["generation"],
                                    "development_improvement": row["avg_relative_improvement"],
                                    "validation_improvement": result["avg_relative_improvement"]})
        selected[method] = max(comparisons, key=lambda r: r["validation_improvement"]) if comparisons else None
        selected[method + "_validation"] = comparisons
    (output / "selected_operators.json").write_text(json.dumps(selected, indent=2) + "\n", encoding="utf-8")
    return selected


def recover_historical_elites(root: Path, output: Path) -> None:
    """Enable an exploratory integration run from the already completed E1R run."""
    historical = root / "outputs" / "e1r_real_llm_pilot_20261019"
    target = output / "historical_e1r"
    for branch in ("L0", "F1", "F2"):
        source_branch = historical / ("F1" if branch == "L0" else branch)
        validations = [json.loads(line) for line in (source_branch / "validation_results.jsonl").read_text(encoding="utf-8").splitlines()]
        raw_trials = [json.loads(line) for line in (source_branch / "trial_metrics.jsonl").read_text(encoding="utf-8").splitlines()]
        trials = defaultdict(list)
        chunk = len(raw_trials) // len(validations)
        for index, row in enumerate(validations):
            trials[(row["round_id"], row["operator_id"])].extend(raw_trials[index * chunk:(index + 1) * chunk])
        elite = []
        for row in validations:
            if branch == "L0" and row["round_id"] != 0:
                continue
            observations = trials[(row["round_id"], row["operator_id"])]
            if row["validation_status"] != "valid" or not observations or not all(t["feasible"] for t in observations):
                continue
            elite.append({"operator_id": row["operator_id"], "generation": row["round_id"],
                          "source_path": row["file_path"], "source_hash": row["code_hash"],
                          "avg_relative_improvement": mean(t["relative_improvement"] for t in observations),
                          "executed_count": len(observations), "feasible_count": len(observations)})
        directory = target / branch
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "elite_archive.json").write_text(json.dumps(elite, indent=2) + "\n", encoding="utf-8")
    (output / "historical_e1r_provenance.json").write_text(json.dumps({
        "source": str(historical), "purpose": "exploratory ALNS integration after E2 provider failure",
        "limitation": "historical E1R development set and unequal L0 candidate request budget; not E2 confirmatory evolution",
    }, indent=2) + "\n", encoding="utf-8")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(5, 3.5))
    for branch in ("F1", "F2"):
        rows = json.loads((target / branch / "elite_archive.json").read_text(encoding="utf-8"))
        by_round = {row["generation"]: row["avg_relative_improvement"] for row in rows}
        ax.plot(sorted(by_round), [by_round[g] for g in sorted(by_round)], marker="o", label=branch)
    ax.set(xlabel="Generation", ylabel="Mean fixed-repair improvement", xticks=[0, 1],
           title="Historical E1R parent and child")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output / "historical_parent_child.png", dpi=180)
    plt.close(fig)


def benchmark(root: Path, output: Path, manifest: dict, selected: dict, *, seeds: tuple[int, ...], iterations: int, smoke: bool) -> list[dict]:
    rows = []
    entries = sorted((r for r in manifest["instances"] if r["split"] == "evolution-development"),
                     key=lambda r: r["tasks"])[:2] if smoke else manifest["instances"]
    target = output / ("smoke_results.csv" if smoke else "alns_results.csv")
    curves = output / ("smoke_curves.jsonl" if smoke else "convergence.jsonl")
    curves.write_text("", encoding="utf-8")
    for entry in entries:
        instance = load_instance(root / entry["path"])
        for seed in seeds:
            baseline = None
            for method in ("B0", "L0", "L1", "L2"):
                record = {"method": method, "instance": entry["path"], "family": entry["family"],
                          "split": entry["split"], "solver_seed": seed, "status": "error", "feasible": False}
                started = perf_counter()
                try:
                    solver = ALNSSolver(instance, config=ALNSConfig(iterations=iterations, random_seed=seed))
                    initial_evaluation = solver.solution_evaluator.evaluate(solver.initial_solution)
                    if method != "B0":
                        choice = selected.get(method)
                        if choice is None:
                            raise ValueError("no eligible selected repair")
                        loaded = load_and_validate_candidate(
                            path=Path(choice["source_path"]), operator_type="repair", round_id=choice["generation"],
                            source="langchain_openai_compatible", description="E2 selected repair",
                            allow_unsafe_candidate_execution=True,
                        )
                        if loaded.callable_obj is None or loaded.validation.code_hash != choice["source_hash"]:
                            raise ValueError(f"selected repair failed validation or hash check: {loaded.validation.execution_status}; {loaded.validation.error_message}")
                        solver.register_development_repair(loaded.callable_obj, name="e2_selected_repair")
                    result = solver.solve()
                    verified = solver.solution_evaluator.evaluate(result.best_solution)
                    behavior = compute_exact_dp_behavior(solver.initial_solution, result.best_solution,
                                                         initial_evaluation, verified, instance=instance)
                    record.update(status="fallback" if result.fallback_events else "ok", feasible=True,
                                  final_makespan=verified.makespan, runtime_sec=perf_counter() - started,
                                  route_dp_evaluations=solver.route_dp.statistics()["calls"] + solver.generated_route_dp_calls,
                                  route_dp_cache_misses=solver.route_dp.statistics()["cache_misses"] + solver.generated_route_dp_cache_misses,
                                  fallback_count=len(result.fallback_events),
                                  selected_repair_uses=result.operator_usage_stats["repair"].get("e2_selected_repair").uses if method != "B0" else 0)
                    with curves.open("a", encoding="utf-8") as handle:
                        handle.write(json.dumps({"method": method, "instance": entry["path"], "seed": seed,
                                                 "initial_makespan": initial_evaluation.makespan,
                                                 "final_dp_behavior": behavior,
                                                 "per_robot_costs": verified.per_robot_costs,
                                                 "best_routes": result.best_solution.routes,
                                                 "fallback_events": result.fallback_events,
                                                 "history": result.iteration_history}) + "\n")
                    if method == "B0":
                        baseline = verified.makespan
                    record["relative_improvement_vs_b0"] = (baseline - verified.makespan) / baseline if baseline else None
                except Exception as exc:
                    record.update(error=f"{type(exc).__name__}: {exc}", runtime_sec=perf_counter() - started)
                rows.append(record)
                _write_csv(target, rows)
    return rows


def _write_csv(path: Path, rows: list[dict]) -> None:
    fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def retry_incomplete_instances(root: Path, output: Path, manifest: dict, selected: dict, *, seeds: tuple[int, ...], iterations: int) -> None:
    """Preserve the first attempt and rerun all methods/seeds on affected instances."""
    import shutil
    with (output / "alns_results.csv").open(newline="", encoding="utf-8") as handle:
        original = list(csv.DictReader(handle))
    affected = {row["instance"] for row in original if row["feasible"] != "True"}
    if not affected:
        return
    backup = output / "initial_attempt"
    backup.mkdir(exist_ok=True)
    for filename in ("alns_results.csv", "convergence.jsonl", "aggregate.csv", "l2_vs_l1_summary.json"):
        if not (backup / filename).exists():
            shutil.copy2(output / filename, backup / filename)
    retry_output = output / "retry_incomplete"
    retry_output.mkdir(exist_ok=True)
    subset = {**manifest, "instances": [r for r in manifest["instances"] if r["path"] in affected]}
    retried = benchmark(root, retry_output, subset, selected, seeds=seeds, iterations=iterations, smoke=False)
    merged = []
    for row in original:
        if row["instance"] in affected:
            replacement = next(r for r in retried if r["instance"] == row["instance"] and r["method"] == row["method"] and r["solver_seed"] == int(row["solver_seed"]))
            merged.append(replacement)
        else:
            for field in ("runtime_sec", "final_makespan", "relative_improvement_vs_b0"):
                if row.get(field):
                    row[field] = float(row[field])
            row["feasible"] = row["feasible"] == "True"
            merged.append(row)
    _write_csv(output / "alns_results.csv", merged)
    curves = [json.loads(line) for line in (backup / "convergence.jsonl").read_text(encoding="utf-8").splitlines()]
    curves = [r for r in curves if r["instance"] not in affected]
    curves.extend(json.loads(line) for line in (retry_output / "convergence.jsonl").read_text(encoding="utf-8").splitlines())
    (output / "convergence.jsonl").write_text("".join(json.dumps(row) + "\n" for row in curves), encoding="utf-8")
    (output / "retry_policy.json").write_text(json.dumps({
        "trigger": "three loader errors on R8_T100_1 following a 55005-second B0 wall-clock anomaly",
        "instances": sorted(affected), "methods": ["B0", "L0", "L1", "L2"], "seeds": seeds,
        "iterations": iterations, "original_records": "initial_attempt/", "rerun_records": "retry_incomplete/",
        "fallback_policy": "retain feasible fallback runs; no retry based on solution quality",
    }, indent=2), encoding="utf-8")
    summarize(output, merged)
    plot_results(output, merged)


def summarize(output: Path, rows: list[dict]) -> None:
    summary = []
    for method in ("B0", "L0", "L1", "L2"):
        valid = [r for r in rows if r["method"] == method and r["feasible"]]
        summary.append({"method": method, "completed": len(valid),
                        "mean_makespan": mean(r["final_makespan"] for r in valid) if valid else None,
                        "mean_improvement_vs_b0": mean(r["relative_improvement_vs_b0"] for r in valid) if valid else None,
                        "mean_runtime_sec": mean(r["runtime_sec"] for r in valid) if valid else None})
    _write_csv(output / "aggregate.csv", summary)
    paired = defaultdict(dict)
    for row in rows:
        if row["feasible"]:
            paired[(row["instance"], row["solver_seed"])][row["method"]] = row["final_makespan"]
    comparisons = []
    for key, values in paired.items():
        if "L1" in values and "L2" in values:
            comparisons.append({"instance": key[0], "seed": key[1], "l1": values["L1"], "l2": values["L2"],
                                "l2_improvement_vs_l1": (values["L1"] - values["L2"]) / values["L1"],
                                "outcome": "win" if values["L2"] < values["L1"] - 1e-9 else "loss" if values["L2"] > values["L1"] + 1e-9 else "tie"})
    _write_csv(output / "l2_vs_l1.csv", comparisons)
    (output / "l2_vs_l1_summary.json").write_text(json.dumps({
        "win": sum(r["outcome"] == "win" for r in comparisons),
        "tie": sum(r["outcome"] == "tie" for r in comparisons),
        "loss": sum(r["outcome"] == "loss" for r in comparisons),
        "mean_relative_improvement": mean(r["l2_improvement_vs_l1"] for r in comparisons) if comparisons else None,
    }, indent=2), encoding="utf-8")
    per_instance = []
    for method in ("B0", "L0", "L1", "L2"):
        for instance in sorted({r["instance"] for r in rows}):
            valid = [r for r in rows if r["method"] == method and r["instance"] == instance and r["feasible"]]
            if valid:
                per_instance.append({"method": method, "instance": instance,
                                     "mean_makespan": mean(r["final_makespan"] for r in valid),
                                     "mean_paired_improvement_vs_b0": mean(r["relative_improvement_vs_b0"] for r in valid)})
    _write_csv(output / "per_instance.csv", per_instance)


def plot_results(output: Path, rows: list[dict]) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    paired = defaultdict(dict)
    for row in rows:
        if row["feasible"]:
            paired[(row["instance"], row["solver_seed"])][row["method"]] = row["final_makespan"]
    complete = [r for r in paired.values() if len(r) == 4]
    if complete:
        fig, ax = plt.subplots(figsize=(6, 4))
        methods = ("B0", "L0", "L1", "L2")
        for values in complete:
            ax.plot(methods, [values[m] / values["B0"] for m in methods], color="0.8", lw=0.6)
        ax.plot(methods, [mean(v[m] / v["B0"] for v in complete) for m in methods],
                color="tab:blue", marker="o", lw=2, label="paired mean")
        ax.axhline(1, color="black", lw=0.7)
        ax.set(ylabel="Makespan / paired B0", title=f"Full ALNS ({len(complete)} paired runs)")
        ax.legend()
        fig.tight_layout()
        fig.savefig(output / "makespan_comparison.png", dpi=180)
        plt.close(fig)
    curves_path = output / "convergence.jsonl"
    if curves_path.exists():
        curves = [json.loads(line) for line in curves_path.read_text(encoding="utf-8").splitlines()]
        if curves:
            first = curves[0]["instance"]
            fig, ax = plt.subplots(figsize=(6, 4))
            for curve in curves:
                if curve["instance"] == first and curve["seed"] == 0:
                    ax.plot([h["iteration"] for h in curve["history"]],
                            [h["best_makespan"] for h in curve["history"]], label=curve["method"])
            ax.set(xlabel="ALNS iteration", ylabel="Best makespan", title=first)
            ax.legend()
            fig.tight_layout()
            fig.savefig(output / "convergence_example.png", dpi=180)
            plt.close(fig)


def analyze_results(output: Path, evolution_dir: Path) -> None:
    """Summarize measured evolution and paired final DP behavior without causal claims."""
    evolution = []
    for branch in ("L0", "F1", "F2"):
        candidates = [json.loads(line) for line in (evolution_dir / branch / "candidate_metrics.jsonl").read_text(encoding="utf-8").splitlines()]
        parent = max((r for r in candidates if r["generation"] == 0), key=lambda r: r["avg_relative_improvement"])
        for row in candidates:
            evolution.append({"branch": branch, "generation": row["generation"], "candidate": row["operator_id"],
                              "source_hash": row["source_hash"], "contract_valid": row["validation_status"] == "valid",
                              "feasible_trials": row["feasible_count"], "executed_trials": row["executed_count"],
                              "mean_repair_makespan": mean(t["candidate_makespan"] for t in row["trials"] if t["feasible"]),
                              "mean_repair_improvement": row["avg_relative_improvement"],
                              "change_vs_parent_in_improvement": row["avg_relative_improvement"] - parent["avg_relative_improvement"] if row["generation"] == 1 and branch != "L0" else None})
    _write_csv(output / "evolution_summary.csv", evolution)
    curves = [json.loads(line) for line in (output / "convergence.jsonl").read_text(encoding="utf-8").splitlines()]
    paired = defaultdict(dict)
    for curve in curves:
        paired[(curve["instance"], curve["seed"])][curve["method"]] = curve
    differences = []
    for (instance, seed), values in paired.items():
        if "L1" not in values or "L2" not in values:
            continue
        a, b = values["L1"], values["L2"]
        ma, mb = max(a["per_robot_costs"]), max(b["per_robot_costs"])
        row = {"instance": instance, "seed": seed, "l1_makespan": ma, "l2_makespan": mb,
               "l2_relative_improvement_vs_l1": (ma - mb) / ma}
        for key in a["final_dp_behavior"]:
            row[key + "_l1"] = a["final_dp_behavior"][key]
            row[key + "_l2"] = b["final_dp_behavior"][key]
        row["l1_route_spread"] = max(a["per_robot_costs"]) - min(a["per_robot_costs"])
        row["l2_route_spread"] = max(b["per_robot_costs"]) - min(b["per_robot_costs"])
        differences.append(row)
    _write_csv(output / "paired_dp_behavior.csv", differences)
    grouped = defaultdict(list)
    for row in differences:
        grouped[row["instance"]].append(row)
    per_instance = [{"instance": k, "l1_makespan": mean(r["l1_makespan"] for r in v),
                     "l2_makespan": mean(r["l2_makespan"] for r in v),
                     "improvement": mean(r["l2_relative_improvement_vs_l1"] for r in v)} for k, v in grouped.items()]
    stats = {"scope": "development/exploratory; no independent confirmatory evidence",
             "per_instance_l2_vs_l1": {"win": sum(r["l2_makespan"] < r["l1_makespan"] - 1e-9 for r in per_instance),
                                      "tie": sum(abs(r["l2_makespan"] - r["l1_makespan"]) <= 1e-9 for r in per_instance),
                                      "loss": sum(r["l2_makespan"] > r["l1_makespan"] + 1e-9 for r in per_instance)},
             "worst_l2_pairs": sorted(differences, key=lambda r: r["l2_relative_improvement_vs_l1"])[:3],
             "best_l2_pairs": sorted(differences, key=lambda r: r["l2_relative_improvement_vs_l1"], reverse=True)[:3]}
    (output / "analysis.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(5.5, 3.8))
    for branch, color in (("F1", "tab:blue"), ("F2", "tab:orange")):
        rows = [r for r in evolution if r["branch"] == branch]
        for generation in (0, 1):
            values = [100 * r["mean_repair_improvement"] for r in rows if r["generation"] == generation]
            ax.scatter([generation] * len(values), values, color=color, alpha=0.5)
        ax.plot([0, 1], [100 * max(r["mean_repair_improvement"] for r in rows if r["generation"] == g) for g in (0, 1)], color=color, marker="o", label=branch + " best")
    ax.set(xlabel="Generation", ylabel="Fixed-repair improvement vs greedy (%)", xticks=[0, 1])
    ax.legend()
    fig.tight_layout()
    fig.savefig(output / "parent_child_evolution.png", dpi=180)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("freeze", "evolve", "recover-e1r", "select", "smoke", "pilot", "analyze", "retry-incomplete"), required=True)
    parser.add_argument("--iterations", type=int, default=200)
    parser.add_argument("--historical-e1r", action="store_true", help="explicitly use historical E1R candidates")
    parser.add_argument("--seeds", type=int, nargs="+", default=[0, 1])
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/e2_c1_pilot"))
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--evolution-dir", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    output = root / args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = root / args.manifest if args.manifest else output / "instance_manifest.json"
    manifest = freeze_instances(root, output) if args.stage == "freeze" or not manifest_path.exists() else json.loads(manifest_path.read_text(encoding="utf-8"))
    evolution_dir = root / args.evolution_dir if args.evolution_dir else output / "evolution"
    if args.stage == "analyze":
        analyze_results(output, evolution_dir)
        return
    if args.stage == "freeze":
        return
    if args.stage == "recover-e1r":
        recover_historical_elites(root, output)
        return
    seeds = tuple(args.seeds)
    if args.stage == "evolve":
        paths = tuple(root / r["path"] for r in manifest["instances"] if r["split"] == "evolution-development")
        try:
            result = run_e1_pilot(E1PilotConfig(project_root=root, manifest_path=None, output_dir=output / "evolution",
                                                 development_instance_paths=paths, solver_seeds=seeds,
                                                 modes=("L0", "F1", "F2"), max_provider_calls=6, resume=True,
                                                 shared_f1_initial_pool=True, continue_on_provider_error=True))
        except Exception as exc:
            (output / "evolution_failure.json").write_text(json.dumps({
                "status": "incomplete", "error_type": type(exc).__name__, "error": str(exc),
            }, indent=2) + "\n", encoding="utf-8")
            raise
        (output / "evolution" / "pilot_summary.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        if not result.get("complete", True):
            (output / "evolution_failure.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            raise SystemExit(1)
        (output / "evolution_status.json").write_text(json.dumps({"status": "complete", "historical_failure_file_retained": True}), encoding="utf-8")
        return
    selected_path = output / "selected_operators.json"
    selected = select_elite(root, output / "historical_e1r" if args.historical_e1r else evolution_dir, manifest, seeds, output) if args.stage == "select" else json.loads(selected_path.read_text(encoding="utf-8"))
    if args.stage == "select":
        return
    if args.stage == "retry-incomplete":
        retry_incomplete_instances(root, output, manifest, selected, seeds=seeds, iterations=args.iterations)
        return
    (output / "run_config.json").write_text(json.dumps({
        "phase": "E2-R", "scope": "development/exploratory only; all 24 instances previously used",
        "manifest": str(manifest_path), "seeds": seeds, "iterations": args.iterations,
        "constructor": "spatial_sort", "destroy_fraction": 0.25, "acceptance": "improvement_only",
        "evaluator": "existing Exact Route-DP", "b0_reused": False,
        "selected_operators": selected, "original_split_labels_are_historical": True,
    }, indent=2) + "\n", encoding="utf-8")
    rows = benchmark(root, output, manifest, selected, seeds=seeds, iterations=args.iterations, smoke=args.stage == "smoke")
    if args.stage == "pilot":
        summarize(output, rows)
        plot_results(output, rows)


if __name__ == "__main__":
    main()
