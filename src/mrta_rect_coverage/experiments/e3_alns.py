"""E3 development comparison, no provider calls. Run with python -m ...e3_alns."""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from statistics import mean
from time import perf_counter

from ..core.instance_loader import load_instance
from ..heuristics.alns_solver import ALNSConfig, ALNSSolver
from ..llm.operator_evolution.candidate_loader import load_and_validate_candidate

ROOT = Path(__file__).resolve().parents[3]
INSTANCES = ("R2_T10_0", "R2_T20_0", "R4_T40_0", "R8_T80_0")
SEEDS = (0, 1)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def generated_smoke(output):
    """Execute an existing hash-bound repair under B1, without changing its source."""
    selected = json.loads((ROOT / "outputs/e2r_c1_pilot/selected_operators.json").read_text(encoding="utf-8"))["L1"]
    loaded = load_and_validate_candidate(
        path=Path(selected["source_path"]), operator_type="repair",
        round_id=selected["generation"], source="real_provider", description="E3 compatibility smoke",
        allow_unsafe_candidate_execution=True,
    )
    if loaded.callable_obj is None:
        raise RuntimeError(f"selected repair failed loading: {loaded.validation}")
    if loaded.validation.code_hash != selected["source_hash"]:
        raise RuntimeError("selected repair hash differs")
    s = ALNSSolver(load_instance(ROOT / "data/R2_T10_0.txt"),
                   config=ALNSConfig.enhanced(iterations=2, segment_length=1))
    s.register_development_repair(loaded.callable_obj, name="e3_compatibility_repair")
    # Force actual use for this smoke only; comparative runs keep the manual registry.
    s.repair_ops = {"e3_compatibility_repair": s.repair_ops["e3_compatibility_repair"]}
    s.repair_weights = {"e3_compatibility_repair": 1.0}
    result = s.solve()
    verified = s.solution_evaluator.evaluate(result.best_solution)
    success = all(h["llm_operator_success"] for h in result.iteration_history)
    write_json(output / "generated_repair_smoke.json", dict(
        source_hash=selected["source_hash"], unchanged_source=True,
        feasible=True, successful_generated_execution=success,
        makespan=verified.makespan, fallback_events=result.fallback_events,
        history=result.iteration_history))
    if not success:
        raise RuntimeError("generated repair did not execute successfully; see smoke output")


def summarize(output, rows):
    baseline = {(r["instance"], r["seed"]): r for r in rows if r["method"] == "B0"}
    for row in rows:
        base = baseline.get((row["instance"], row["seed"]))
        row["improvement_vs_b0_pct"] = (100 * (1 - row["makespan"] / base["makespan"]) if base else None)
    with (output / "results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = []
    for method in ("B0", "B1"):
        group = [r for r in rows if r["method"] == method]
        if not group:
            continue
        summary.append(dict(method=method, runs=len(group), mean_makespan=mean(r["makespan"] for r in group),
                            mean_runtime_seconds=mean(r["runtime_seconds"] for r in group),
                            mean_iterations=mean(r["iterations"] for r in group),
                            mean_route_dp_calls=mean(r["route_dp_calls"] for r in group),
                            mean_paired_improvement_pct=mean(r["improvement_vs_b0_pct"] for r in group if r["improvement_vs_b0_pct"] is not None)))
    write_json(output / "summary.json", summary)
    paired = [(r, baseline[(r["instance"], r["seed"])]) for r in rows if r["method"] == "B1"]
    write_json(output / "paired_summary.json", dict(
        wins=sum(r["makespan"] < b["makespan"] - 1e-9 for r, b in paired),
        ties=sum(abs(r["makespan"] - b["makespan"]) <= 1e-9 for r, b in paired),
        losses=sum(r["makespan"] > b["makespan"] + 1e-9 for r, b in paired),
        max_overrun_seconds=max(r["overrun_seconds"] for r in rows)))
    instance_summary = []
    diagnostics = []
    for name in INSTANCES:
        per_instance = dict(instance=name)
        for method in ("B0", "B1"):
            group = [r for r in rows if r["instance"] == name and r["method"] == method]
            for key in ("makespan", "runtime_seconds", "iterations", "route_dp_calls"):
                per_instance[f"{method}_{key}"] = mean(r[key] for r in group)
        per_instance["paired_improvement_pct"] = mean(r["improvement_vs_b0_pct"] for r in rows if r["instance"] == name and r["method"] == "B1")
        instance_summary.append(per_instance)
        for seed in SEEDS:
            for method in ("B0", "B1"):
                history = json.loads((output / "runs" / f"{name}_{method}_s{seed}.json").read_text())["history"]
                row = next(r for r in rows if (r["instance"], r["method"], r["seed"]) == (name, method, seed))
                improvements = []
                best = row["initial_makespan"]
                for h in history:
                    if h["best_makespan"] < best - 1e-9:
                        improvements.append(h["elapsed_seconds"])
                        best = h["best_makespan"]
                diagnostics.append(dict(instance=name, seed=seed, method=method,
                    best_improvements=len(improvements), last_best_improvement_seconds=improvements[-1] if improvements else 0,
                    worsening_candidates=sum(h["candidate_delta"] > 1e-9 for h in history),
                    sa_acceptances=row["sa_acceptances"],
                    current_worse_than_best_fraction=mean(h["current_makespan"] > h["best_makespan"] + 1e-9 for h in history)))
    write_json(output / "instance_summary.json", instance_summary)
    write_json(output / "search_diagnostics.json", diagnostics)
    return summary


def plots(output, rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(2, 2, figsize=(10, 6.5), constrained_layout=True)
    for name, ax in zip(INSTANCES, axes.flat):
        for method, color in (("B0", "#264653"), ("B1", "#E76F51")):
            for seed in SEEDS:
                history = json.loads((output / "runs" / f"{name}_{method}_s{seed}.json").read_text())["history"]
                row = next(r for r in rows if (r["instance"], r["method"], r["seed"]) == (name, method, seed))
                x = [0] + [h["elapsed_seconds"] for h in history] + [row["runtime_seconds"]]
                y = [row["initial_makespan"]] + [h["best_makespan"] for h in history] + [row["makespan"]]
                ax.step(x, y, where="post", color=color, linestyle="-" if seed == 0 else "--", label=f"{method}, seed {seed}")
        ax.set(title=name, xlabel="Solve time (s)", ylabel="Best makespan")
        ax.grid(alpha=0.2)
    axes.flat[0].legend(fontsize=8)
    fig.savefig(output / "convergence.png", dpi=180)
    fig.savefig(output / "convergence.pdf")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/e3_alns")
    parser.add_argument("--smoke-only", action="store_true")
    args = parser.parse_args()
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    if args.smoke_only:
        generated_smoke(output)
        print("B1 generated repair smoke passed", flush=True)
        return
    configurations = {m: (ALNSConfig if m == "B0" else ALNSConfig.enhanced)(iterations=None, max_runtime_seconds=10)
                      for m in ("B0", "B1")}
    write_json(output / "config.json", dict(
        purpose="E3 development search-control comparison", instances=[dict(
            path=f"data/{name}.txt", sha256=hashlib.sha256((ROOT / "data" / f"{name}.txt").read_bytes()).hexdigest()) for name in INSTANCES],
        seeds=SEEDS, alpha_seconds_per_task=1.0, constructor="spatial_sort",
        profiles={m: asdict(cfg) for m, cfg in configurations.items()},
        budget_note="max_runtime_seconds is replaced by task_count for each instance; solve includes initial evaluation but excludes solver setup; limits checked between full iterations",
        run_order="instance, seed; B0/B1 order reversed for seed 1",
        command="python -m mrta_rect_coverage.experiments.e3_alns"))
    rows = []
    for name in INSTANCES:
        instance = load_instance(ROOT / "data" / f"{name}.txt")
        for seed in SEEDS:
            initial_routes = None
            for method in (("B0", "B1") if seed == 0 else ("B1", "B0")):
                started = perf_counter()
                factory = ALNSConfig if method == "B0" else ALNSConfig.enhanced
                cfg = factory(iterations=None, max_runtime_seconds=float(instance.task_count), random_seed=seed)
                s = ALNSSolver(instance, constructor="spatial_sort", config=cfg)
                setup_seconds = perf_counter() - started
                if initial_routes is None:
                    initial_routes = s.initial_solution.routes
                assert s.initial_solution.routes == initial_routes
                result = s.solve()
                # Existing full evaluator checks complete coverage and robot count.
                verified = s.solution_evaluator.evaluate(result.best_solution)
                assert abs(verified.makespan - result.best_evaluation.makespan) < 1e-8
                row = dict(method=method, instance=name, tasks=instance.task_count, robots=instance.robot_count,
                           seed=seed, budget_seconds=cfg.max_runtime_seconds, makespan=verified.makespan,
                           initial_makespan=result.initial_makespan, runtime_seconds=result.runtime_seconds,
                           setup_seconds=setup_seconds, overrun_seconds=max(0, result.runtime_seconds-cfg.max_runtime_seconds),
                           iterations=result.iterations_completed, route_dp_calls=result.route_dp_calls,
                           route_dp_cache_misses=result.route_dp_cache_misses, feasible=True,
                           status="ok", termination=result.termination_reason,
                           sa_acceptances=sum(h["accept_reason"] == "sa" for h in result.iteration_history),
                           fallback_count=len(result.fallback_events))
                write_json(output / "runs" / f"{name}_{method}_s{seed}.json",
                           dict(result=row, config=asdict(cfg), initial_routes=initial_routes,
                                best_routes=result.best_solution.routes, history=result.iteration_history))
                rows.append(row)
                write_json(output / "results.json", rows)
                print(f"{name} seed={seed} {method}: {verified.makespan:.2f}, {result.runtime_seconds:.2f}s, {result.iterations_completed} iterations", flush=True)
    summary = summarize(output, rows)
    plots(output, rows)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
