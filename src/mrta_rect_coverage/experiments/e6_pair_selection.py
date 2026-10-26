"""Frozen E5 operators, optional pair selection, and small E6 development runs.

No provider requests. All methods run serially with the same B1 time budgets.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path
from statistics import mean
import subprocess
from time import perf_counter

from .e3_alns import ROOT, INSTANCES, SEEDS, write_json
from .e5_destroy_repair import D_NAME, R_NAME, digest, read, load_choice
from .e2_c1_pilot import _write_csv
from ..core.instance_loader import load_instance
from ..core.models import MultiRobotSolution
from ..heuristics.alns_solver import ALNSConfig, ALNSSolver

METHODS = ("B1+R", "V1", "V2")
E5 = ROOT / "outputs/e5_llm_destroy_repair"
BASE_HEAD = "297a9495aa2dc04ebad21dc0314172b8df78ef00"


def config_for(instance, seed, method, *, iterations=None):
    return ALNSConfig.enhanced(
        iterations=iterations,
        max_runtime_seconds=float(instance.task_count) if iterations is None else None,
        random_seed=seed,
        pair_selection_mode="coupled" if method == "V2" else "independent",
        coupled_destroy_operator=D_NAME if method != "B1+R" else None,
        coupled_repair_operator=R_NAME if method != "B1+R" else None,
    )


def make_solver(instance, seed, selected, method, *, iterations=None):
    solver = ALNSSolver(instance, constructor="spatial_sort",
                        config=config_for(instance, seed, method, iterations=iterations))
    if method != "B1+R":
        solver.register_development_destroy(load_choice(selected["destroy"], "destroy").callable_obj,
                                            name=D_NAME)
    solver.register_development_repair(load_choice(selected["repair"], "repair").callable_obj,
                                       name=R_NAME)
    return solver


def setup(output):
    output.mkdir(parents=True, exist_ok=True)
    selected = read(E5 / "selected_operators.json")
    old_config = read(E5 / "experiment_config.json")
    for kind, identity in selected.items():
        if digest(identity["source_path"]) != identity["source_hash"]:
            raise ValueError(f"frozen {kind} changed")
    frozen = [ROOT / "src/mrta_rect_coverage/core/dp_evaluator.py", ROOT / "configs/e3_b1.yaml"]
    frozen += [ROOT / "data" / f"{name}.txt" for name in INSTANCES]
    for path in frozen:
        assert digest(path) == old_config["frozen_hashes"][str(path)], path
    # Archive the exact E5 V1 implementation from the user's baseline commit.
    legacy = subprocess.check_output([
        "git", "show", f"{BASE_HEAD}:src/mrta_rect_coverage/heuristics/alns_solver.py"
    ], cwd=ROOT).decode("utf-8").replace("\r\n", "\n")
    reference = output / "v1_reference" / "alns_solver_e5.py"
    if reference.exists():
        assert reference.read_text(encoding="utf-8") == legacy
    else:
        reference.parent.mkdir(parents=True, exist_ok=True)
        reference.write_text(legacy, encoding="utf-8")
    assert digest(reference) == old_config["frozen_hashes"][str(ROOT / "src/mrta_rect_coverage/heuristics/alns_solver.py")]

    # Validate historical settings/identities for provenance, but do not use old
    # measurements in this newly timed comparison.
    historical = []
    new_fields = {"pair_selection_mode", "coupled_destroy_operator", "coupled_repair_operator"}
    for name in INSTANCES:
        instance = load_instance(ROOT / "data" / f"{name}.txt")
        for seed in SEEDS:
            for method, old_method in (("B1+R", "B1+R"), ("V1", "B1+D+R")):
                path = E5 / "runs" / f"{name}_{old_method}_s{seed}.json"
                saved = read(path)
                expected = asdict(config_for(instance, seed, method))
                assert saved["config"] == {k: v for k, v in expected.items() if k not in new_fields}
                assert saved["selected"] == selected
                assert saved["result"]["feasible"]
                historical.append(dict(path=str(path), hash=digest(path), method=method,
                                       makespan=saved["result"]["makespan"], reused=False))
    config = dict(
        phase="E6", base_git_head=BASE_HEAD, selected=selected, instances=list(INSTANCES), seeds=list(SEEDS),
        methods=list(METHODS), constructor="spatial_sort", alpha=1.0,
        B1=asdict(ALNSConfig.enhanced()),
        method_configs={m: asdict(config_for(load_instance(ROOT / "data/R2_T10_0.txt"), 0, m)) for m in METHODS},
        pool_sizes={"B1+R": [3, 4], "V1": [4, 4], "V2": [4, 4]},
        selection_rule="V2: active pair probability has current independent roulette pair odds as prior, multiplied by adaptive preference; otherwise unchanged independent roulette",
        preference_update="every 20 iterations: preference *= (max(0.1,pair_mean_reward)/max(0.1,independent_mean_reward))**0.2; bounds [0.05,20]; probability cap 0.5",
        initial_active_pair_probability=1 / 16,
        initial_total_pair_probability=1 / 16 + (15 / 16) * (1 / 16),
        reward_semantics="existing 8/3/1/0; single-operator records are marginal selection statistics; action records are joint selection statistics, not additive or causal contributions",
        fallback_rule="active pair fallback counts as use and zero action reward; excluded from successful use, accepted and global-best contribution",
        historical_runs=historical, historical_results_reused=False,
        frozen_hashes={str(p): digest(p) for p in frozen}, v1_reference_hash=digest(reference),
        implementation_hash=digest(ROOT / "src/mrta_rect_coverage/heuristics/alns_solver.py"),
        runner_hash=digest(Path(__file__)),
        interpretation="development/exploratory; no significance/SOTA claim; no frequency-matched ablation",
        llm_calls=0, final_test_accessed=False,
        timing="solve includes initial evaluation and bounded process startup/execution/exit; setup and independent final verification excluded; stop at iteration boundary",
        timing_overlap="full_evaluation_seconds is a nested diagnostic including initial evaluation and full evaluations within local_search_seconds; never add it to phase totals",
        commands=["python -m mrta_rect_coverage.experiments.e6_pair_selection --stage " + s for s in ("smoke", "benchmark", "analyze")],
    )
    target = output / "experiment_config.json"
    if target.exists():
        if read(target) != config:
            raise ValueError("E6 configuration/source changed; preserve previous directory and use a fresh output")
    else:
        write_json(target, config)
    write_json(output / "selected_operators.json", selected)
    return config, selected


def smoke(output):
    _, selected = setup(output)
    instance = load_instance(ROOT / "data/R2_T10_0.txt")
    solver = make_solver(instance, 0, selected, "V2", iterations=2)
    # Force only this integration smoke; benchmark uses adaptive selection.
    def select(_context):
        solver._last_selection_action = "coupled"
        return D_NAME, R_NAME, "integration_smoke"
    solver._select_operators = select
    result = solver.solve()
    verified = solver.solution_evaluator.evaluate(result.best_solution)
    assert verified.makespan == result.best_evaluation.makespan
    assert result.pair_action_stats["uses"] == result.pair_action_stats["successful_uses"] == 2
    assert not result.fallback_events
    write_json(output / "smoke.json", dict(feasible=True, makespan=verified.makespan,
        history=result.iteration_history, pair_action_stats=result.pair_action_stats,
        timing=result.timing_breakdown_seconds, generated_execution=result.generated_operator_execution))
    print("Real frozen coupled Destroy+Repair smoke passed (2/2, no fallback)", flush=True)


def benchmark(output):
    _, selected = setup(output)
    if not (output / "smoke.json").exists():
        raise RuntimeError("run smoke before benchmark")
    rows = []
    for name in INSTANCES:
        instance = load_instance(ROOT / "data" / f"{name}.txt")
        for seed in SEEDS:
            order = METHODS if seed == 0 else tuple(reversed(METHODS))
            for method in order:
                target = output / "runs" / f"{name}_{method}_s{seed}.json"
                if target.exists():
                    saved = read(target)
                    assert saved["config"] == asdict(config_for(instance, seed, method))
                    assert saved["selected"] == selected
                    rows.append(saved["result"])
                    continue
                record = dict(method=method, instance=name, seed=seed, tasks=instance.task_count,
                              robots=instance.robot_count, budget_seconds=float(instance.task_count), feasible=False)
                started = perf_counter()
                try:
                    solver = make_solver(instance, seed, selected, method)
                    setup_seconds = perf_counter() - started
                    result = solver.solve()
                    verified = solver.solution_evaluator.evaluate(result.best_solution)
                    assert verified.makespan == result.best_evaluation.makespan
                    history = result.iteration_history
                    execution = result.generated_operator_execution
                    bounded_seconds = sum(v["wall_time_seconds"] for g in execution.values() for v in g.values())
                    request_seconds = sum(v["run_request_seconds"] for g in execution.values() for v in g.values())
                    record.update(
                        feasible=True, status="fallback" if result.fallback_events else "ok",
                        makespan=verified.makespan, initial_makespan=result.initial_makespan,
                        runtime_seconds=result.runtime_seconds, setup_seconds=setup_seconds,
                        iterations=result.iterations_completed, route_dp_calls=result.route_dp_calls,
                        route_dp_cache_misses=result.route_dp_cache_misses,
                        llm_destroy_uses=sum(h["destroy"] == D_NAME for h in history),
                        llm_repair_uses=sum(h["repair"] == R_NAME for h in history),
                        joint_uses=sum(h["destroy"] == D_NAME and h["repair"] == R_NAME for h in history),
                        active_pair_uses=result.pair_action_stats["uses"],
                        independent_coincidental_pair_uses=result.pair_action_stats["independent_coincidental_uses"],
                        active_pair_accepted=result.pair_action_stats["accepted"],
                        active_pair_global_best=result.pair_action_stats["global_best"],
                        active_pair_reward=result.pair_action_stats["reward"],
                        active_pair_fallbacks=result.pair_action_stats["fallbacks"],
                        fallback_count=len(result.fallback_events), destroy_pool_size=len(solver.destroy_ops),
                        repair_pool_size=len(solver.repair_ops), bounded_execution_seconds=bounded_seconds,
                        bounded_run_request_seconds=request_seconds,
                        bounded_lifecycle_overhead_seconds=max(0.0, bounded_seconds - request_seconds),
                        overrun_seconds=max(0.0, result.runtime_seconds - instance.task_count),
                        **result.timing_breakdown_seconds,
                    )
                    write_json(target, dict(result=record, selected=selected, config=asdict(solver.config),
                        operator_pools=dict(destroy=list(solver.destroy_ops), repair=list(solver.repair_ops)),
                        initial_routes=solver.initial_solution.routes, best_routes=result.best_solution.routes,
                        per_robot_costs=verified.per_robot_costs, history=history,
                        fallback_events=result.fallback_events, pair_action_stats=result.pair_action_stats,
                        generated_operator_execution=execution,
                        final_weights=dict(destroy=solver.destroy_weights, repair=solver.repair_weights,
                                           coupled_preference=solver.coupled_selection_preference)))
                except Exception as exc:
                    record.update(status="error", error=f"{type(exc).__name__}: {exc}", wall_seconds=perf_counter() - started)
                    write_json(target.with_suffix(".error.json"), record)
                    raise
                rows.append(record)
                write_json(output / "results.json", rows)
                _write_csv(output / "results.csv", rows)
                print(f"{name} s{seed} {method}: M={record['makespan']:.1f}, {record['runtime_seconds']:.3f}s, "
                      f"{record['iterations']} iters, joint={record['joint_uses']} active={record['active_pair_uses']}, "
                      f"fallback={record['fallback_count']}", flush=True)
    write_json(output / "results.json", rows)
    _write_csv(output / "results.csv", rows)


def analyze(output):
    config, selected = setup(output)
    saved = [read(output / "runs" / f"{n}_{m}_s{s}.json") for n in INSTANCES for s in SEEDS for m in METHODS]
    rows = [d["result"] for d in saved]
    indexed = {(r["method"], r["instance"], r["seed"]): r for r in rows}
    for name in INSTANCES:
        group = [d for d in saved if d["result"]["instance"] == name]
        verifier = ALNSSolver(load_instance(ROOT / "data" / f"{name}.txt"))
        assert all(d["initial_routes"] == verifier.initial_solution.routes for d in group)
        for d in group:
            r = d["result"]
            assert r["feasible"] and verifier.solution_evaluator.evaluate(MultiRobotSolution(d["best_routes"])).makespan == r["makespan"]
            assert d["selected"] == selected
            assert len(d["history"]) == r["iterations"]
            assert sum(h["actively_selected_frozen_pair"] for h in d["history"]) == r["active_pair_uses"]
            assert r["joint_uses"] == r["active_pair_uses"] + r["independent_coincidental_pair_uses"]
            assert all(b["best_makespan"] <= a["best_makespan"] for a, b in zip(d["history"], d["history"][1:]))
    keys = ("makespan", "runtime_seconds", "iterations", "route_dp_calls", "route_dp_cache_misses",
            "llm_destroy_uses", "llm_repair_uses", "joint_uses", "active_pair_uses", "active_pair_accepted",
            "active_pair_global_best", "active_pair_reward", "bounded_execution_seconds",
            "bounded_lifecycle_overhead_seconds", "destroy_execution_seconds", "partial_evaluation_seconds",
            "repair_execution_seconds", "local_search_seconds", "other_seconds")
    summary = []
    for method in METHODS:
        group = [r for r in rows if r["method"] == method]
        row = dict(method=method, feasible_runs=len(group), **{f"mean_{k}": mean(r[k] for r in group) for k in keys})
        row.update(joint_selection_fraction=sum(r["joint_uses"] for r in group) / sum(r["iterations"] for r in group),
                   active_pair_selection_fraction=sum(r["active_pair_uses"] for r in group) / sum(r["iterations"] for r in group),
                   bounded_fraction=sum(r["bounded_execution_seconds"] for r in group) / sum(r["runtime_seconds"] for r in group),
                   lifecycle_fraction=sum(r["bounded_lifecycle_overhead_seconds"] for r in group) / sum(r["runtime_seconds"] for r in group))
        for baseline in ("B1+R", "V1"):
            pairs = [(r, indexed[(baseline, r["instance"], r["seed"])]) for r in group]
            row[f"paired_improvement_vs_{baseline}_pct"] = mean(100 * (1 - a["makespan"] / b["makespan"]) for a, b in pairs)
            row[f"wtl_vs_{baseline}"] = [sum(a["makespan"] < b["makespan"] for a, b in pairs),
                                         sum(a["makespan"] == b["makespan"] for a, b in pairs),
                                         sum(a["makespan"] > b["makespan"] for a, b in pairs)]
        summary.append(row)
    write_json(output / "summary.json", summary)
    _write_csv(output / "summary.csv", summary)
    per_instance = []
    for name in INSTANCES:
        per_instance.append(dict(instance=name, **{m: mean(r["makespan"] for r in rows if r["instance"] == name and r["method"] == m) for m in METHODS}))
    _write_csv(output / "per_instance_results.csv", per_instance)
    write_json(output / "verification_summary.json", dict(feasible_runs=len(rows), expected_runs=24,
        fallback_count=sum(r["fallback_count"] for r in rows), final_solutions_independently_reevaluated=True,
        matched_initial_solutions=True, global_best_monotonic=True, selection_usage_counts_checked=True,
        frozen_hashes_checked=True, llm_calls=0, post_result_tuning=False))
    plot(output, saved)
    print(__import__("json").dumps(summary, indent=2), flush=True)


def plot(output, saved):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "serif", "font.size": 9, "legend.frameon": False,
                         "axes.spines.top": False, "axes.spines.right": False, "pdf.fonttype": 42})
    colors = {"B1+R": "#0072B2", "V1": "#009E73", "V2": "#D55E00"}
    fig, axes = plt.subplots(2, 4, figsize=(13, 5.4))
    for column, name in enumerate(INSTANCES):
        for seed in SEEDS:
            ax = axes[seed, column]
            for method in METHODS:
                d = next(d for d in saved if d["result"]["instance"] == name and d["result"]["seed"] == seed and d["result"]["method"] == method)
                h = d["history"]
                ax.step([0] + [v["elapsed_seconds"] for v in h] + [d["result"]["runtime_seconds"]],
                        [d["result"]["initial_makespan"]] + [v["best_makespan"] for v in h] + [d["result"]["makespan"]],
                        where="post", label=method, color=colors[method], linewidth=1.4)
            ax.set_title(f"{name}, seed {seed}")
            ax.set_xlabel("Solve time (s)")
            ax.set_ylabel("Best makespan")
            ax.grid(alpha=.15)
    axes[0, 0].legend()
    fig.tight_layout()
    fig.savefig(output / "convergence.png", dpi=300)
    fig.savefig(output / "convergence.pdf")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("smoke", "benchmark", "analyze"), required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/e6_pair_selection")
    args = parser.parse_args()
    {"smoke": smoke, "benchmark": benchmark, "analyze": analyze}[args.stage](args.output.resolve())


if __name__ == "__main__":
    main()
