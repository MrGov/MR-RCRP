"""E4-A/B small development experiments, reusing saved operators and frozen B1."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import difflib
from pathlib import Path
from statistics import mean
from time import perf_counter

from ..core.instance_loader import load_instance
from ..heuristics.alns_solver import ALNSConfig, ALNSSolver
from ..llm.operator_evolution.candidate_loader import load_and_validate_candidate
from .e3_alns import ROOT, INSTANCES, SEEDS, write_json
from .e2_c1_pilot import _write_csv
from .e1_real_llm_pilot import build_f1_feedback, build_f2_feedback, build_f2d_feedback, build_f2g_feedback, revision_prompt, _evaluate_candidate, _invalid_row
from ..llm.operator_evolution.candidate_loader import persist_operator_drafts
from ..llm.operator_evolution.evaluator import build_repair_benchmark_cases
from ..llm.operator_evolution import prompt_builder

EVOLUTION = ROOT / "outputs/e2_c1_pilot/evolution"
SHORT_INSTANCES = ("R2_T6_0", "R2_T10_0", "R2_T20_3", "R4_T60_8")
E4A = ROOT / "outputs/e4a_decision_feedback"


def paired_inputs(output):
    f1, f2 = load_rows("F1"), load_rows("F2")
    initial = [row for row in f1 if row["generation"] == 0]
    initial2 = [row for row in f2 if row["generation"] == 0]
    assert [r["source_hash"] for r in initial] == [r["source_hash"] for r in initial2]
    assert [r["trials"] for r in initial] == [r["trials"] for r in initial2]
    parent = max(initial, key=lambda r: r["avg_relative_improvement"])
    reference = [(t["instance_id"], t["solver_seed"], t["baseline_makespan"]) for t in parent["trials"]]
    for branch in (f1, f2):
        children = [r for r in branch if r["generation"] == 1]
        assert len(children) == 2
        for child in children:
            assert child["parent_source_hash"] == parent["source_hash"]
            assert [(t["instance_id"], t["solver_seed"], t["baseline_makespan"]) for t in child["trials"]] == reference
    write_json(output / "paired_reuse.json", dict(parent_hash=parent["source_hash"],
        reused_round1={b: [r["source_hash"] for r in rows if r["generation"] == 1] for b, rows in (("F1", f1), ("F2", f2))},
        trials=reference, candidate_cap_per_condition=2, evaluation_trials_per_candidate=24,
        historical_prompt_caveat="E2-R rich prompt said 3 candidates but provider parser n=2 retained/evaluated 2. E4 fixes prompt count forwarding; all three new conditions request/retain 2. Historical F1/F2 retained only as reference, not the primary E4 comparison."))
    return parent, initial


def evolve(output, mode="F2-D"):
    """Exactly one new successful revision request, resume persisted generated work."""
    from ..llm.operator_evolution.provider_factory import build_provider
    from ..llm.runtime.config import load_from_env
    parent, initial = paired_inputs(output)
    branch = output / mode
    if (branch / "generated_candidates.json").exists():
        print(f"Reuse saved {mode} response; no provider call", flush=True)
        return
    feedback = build_f2d_feedback(initial, parent=parent,
        source_reference=str(EVOLUTION / "F1/candidate_metrics.jsonl"))
    if mode == "F1":
        feedback = build_f1_feedback(initial)
    elif mode == "F2":
        feedback = build_f2_feedback(initial)
    elif mode == "F2-G":
        reference = json.loads((E4A / "candidate_metrics.json").read_text())
        choice = json.loads((E4A / "selected_operators.json").read_text())["F2-D"]
        diagnosed = next(r for r in reference["F2-D"] if r["source_hash"] == choice["source_hash"])
        feedback = build_f2g_feedback(initial, parent=parent, diagnosed_operator=diagnosed,
            source_reference=f"parent:{EVOLUTION / 'F1/candidate_metrics.jsonl'}; F2-D:{E4A / 'candidate_metrics.json'}")
    write_json(branch / "feedback.json", feedback)
    prompt_builder.use_rich_prompts = True
    prompt = revision_prompt(parent, feedback, n=2)
    (branch / "prompt.txt").write_text(prompt, encoding="utf-8")
    cfg = load_from_env()
    historical = json.loads((EVOLUTION / "provider_config_redacted.json").read_text())
    if cfg.model != historical["model"] or cfg.base_url != historical["base_url"]:
        raise ValueError("current provider/model differs from paired historical run")
    write_json(output / "experiment_config.json", dict(
        provider={k: v for k, v in asdict(cfg).items() if k != "api_key"},
        parent_hash=parent["source_hash"], conditions=["F1", "F2", "F2-D"],
        revision_rounds=1, candidates_per_condition=2, seeds=SEEDS,
        development_instances=json.loads((EVOLUTION / "metadata.json").read_text())["development_instances"],
        timeout_ms=2000, final_test_accessed=False,
        short_instances=SHORT_INSTANCES, short_alpha=0.25,
        reuse_note="Historical F1/F2 prompt requested 3 but parsed 2; retained as reference. New F1/F2 requests use cap=2 to match F2-D; one real revision call per condition.",
        selection="single-best fully feasible Round 1 child by mean fixed-repair development improvement; frozen before short B1 runs; same rule applied to all three conditions",
        commands=["python -m mrta_rect_coverage.experiments.e4_decision_feedback --stage compatibility",
                  *["python -m mrta_rect_coverage.experiments.e4_decision_feedback --stage evolve --condition " + m for m in ("F2-D", "F1", "F2")],
                  *["python -m mrta_rect_coverage.experiments.e4_decision_feedback --stage " + s for s in ("evaluate", "short", "analyze")]]))
    if mode == "F2-G":
        write_json(output / "experiment_config.json", dict(
            phase="E4-B", provider={k: v for k, v in asdict(cfg).items() if k != "api_key"},
            parent_hash=parent["source_hash"], conditions=["F1", "F2-D", "F2-G"],
            revision_rounds=1, new_provider_calls=1, candidates_per_condition=2,
            development_instances=json.loads((EVOLUTION / "metadata.json").read_text())["development_instances"],
            seeds=SEEDS, timeout_ms=2000, final_test_accessed=False,
            alns_instances=SHORT_INSTANCES, alpha=0.25, minimum_runtime_seconds=5.0,
            selection="fully feasible single-best child by 12 development instances x 2 seeds mean fixed-repair improvement, frozen before B1 comparison",
            pairing_limits="F1 and F2-D reused from E4-A, generated earlier. F2-G uses same parent/scalar/candidate and evaluation caps but additionally sees saved F2-D diagnosis and geometry formulas; one independent evolution, not a randomized confirmatory experiment.",
            commands=["python -m mrta_rect_coverage.experiments.e4_decision_feedback --output outputs/e4b_geometry_feedback --stage " + s
                      for s in ("geometry-evolve", "geometry-evaluate", "geometry-benchmark", "geometry-analyze")]))
    provider = build_provider("langchain_openai_compatible", raw_response_dir=branch / "raw_responses")
    started = perf_counter()
    try:
        drafts = provider.revise_operator_candidates(prompt, feedback, 2, "repair", 1)
    except Exception as exc:
        write_json(branch / "provider_failure.json", dict(error=f"{type(exc).__name__}: {exc}",
                                                         elapsed_seconds=perf_counter()-started))
        raise
    paths = persist_operator_drafts(branch / "generated", list(drafts)[:2])
    write_json(branch / "provider_call.json", dict(metadata=provider.last_call_metadata,
        wall_seconds=perf_counter()-started, requested_cap=2, parsed_count=len(drafts)))
    write_json(branch / "generated_candidates.json", [dict(source_path=str(path), description=draft.description,
        generation=1, operator_id=draft.operator_id, source_hash=hashlib.sha256(path.read_text(encoding="utf-8").encode()).hexdigest())
        for path, draft in zip(paths, drafts)])
    print(f"Saved {len(paths)} real {mode} candidates", flush=True)


def evaluate(output, modes=("F1", "F2", "F2-D"), *, reuse_e4a=False):
    parent, initial = paired_inputs(output)
    paths = [Path(p) for p in json.loads((EVOLUTION / "metadata.json").read_text())["development_instances"]]
    cases = build_repair_benchmark_cases(paths)
    rows = {}
    for mode in modes:
        if reuse_e4a and mode != "F2-G":
            rows[mode] = json.loads((E4A / "candidate_metrics.json").read_text())[mode]
            continue
        branch = output / mode
        drafts = json.loads((branch / "generated_candidates.json").read_text())
        new_rows = []
        for draft in drafts:
            target = branch / "evaluations" / f"{draft['operator_id']}.json"
            if target.exists():
                new_rows.append(json.loads(target.read_text()))
                continue
            loaded = load_and_validate_candidate(path=Path(draft["source_path"]), operator_type="repair", round_id=1,
                source="langchain_openai_compatible", description=draft["description"], allow_unsafe_candidate_execution=True)
            if loaded.validation.code_hash != draft["source_hash"]:
                raise ValueError("persisted candidate source hash changed")
            evaluation = (_evaluate_candidate(loaded, cases, SEEDS, 2000)
                          if loaded.callable_obj is not None else _invalid_row(loaded.validation))
            evaluation.update(draft, parent_source_hash=parent["source_hash"], feedback_mode=mode)
            expected = [(t["instance_id"], t["solver_seed"], t["baseline_makespan"]) for t in parent["trials"]]
            measured = [(t["instance_id"], t["solver_seed"], t.get("baseline_makespan")) for t in evaluation.get("trials", [])]
            if evaluation.get("feasible_count") == 24 and measured != expected:
                raise ValueError("new candidate evaluated on different cases/seeds/baselines")
            write_json(target, evaluation)
            write_json(target.with_name(target.stem + "_validation.json"), asdict(loaded.validation))
            new_rows.append(evaluation)
            print(f"{mode} {draft['operator_id']}: {evaluation['avg_relative_improvement']:+.5f}, feasible {evaluation['feasible_count']}/{evaluation['executed_count']}", flush=True)
        rows[mode] = new_rows
    write_json(output / "candidate_metrics.json", rows)
    choices = {}
    table = []
    for mode, group in rows.items():
        eligible = [r for r in group if r.get("executed_count", 0) == 24 and r.get("feasible_count") == 24]
        best = max(eligible, key=lambda r: r["avg_relative_improvement"]) if eligible else None
        choices[mode] = {k: best[k] for k in ("source_path", "source_hash", "operator_id", "generation")} if best else None
        for row in group:
            table.append(dict(condition=mode, source_hash=row["source_hash"], operator_id=row["operator_id"],
                contract_valid=row["validation_status"] == "valid", feasible_trials=row["feasible_count"], total_trials=row["executed_count"],
                mean_fixed_repair_improvement_pct=100 * row["avg_relative_improvement"],
                parent_improvement_pct=100 * parent["avg_relative_improvement"],
                parent_child_change_percentage_points=100 * (row["avg_relative_improvement"]-parent["avg_relative_improvement"])))
            source = Path(row["source_path"]).read_text(encoding="utf-8")
            diff = "".join(difflib.unified_diff(Path(parent["source_path"]).read_text(encoding="utf-8").splitlines(True), source.splitlines(True), fromfile="parent", tofile=mode+"/"+row["operator_id"]))
            dest = output / "source_diffs" / f"{mode}_{row['operator_id']}.diff"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(diff, encoding="utf-8")
    write_json(output / "selected_operators.json", choices)
    _write_csv(output / "fixed_repair_results.csv", table)
    print(json.dumps(table, indent=2), flush=True)


def geometry_snapshot(output):
    """Record immutable inputs and explicit E4-A controls before any new request."""
    output.mkdir(parents=True, exist_ok=True)
    paths = [ROOT / "src/mrta_rect_coverage/heuristics/alns_solver.py",
             ROOT / "src/mrta_rect_coverage/core/dp_evaluator.py",
             ROOT / "configs/e3_b0.yaml", ROOT / "configs/e3_b1.yaml", ROOT / "configs/default.yaml"]
    paths.extend(ROOT / "data" / f"{name}.txt" for name in SHORT_INSTANCES)
    selected = json.loads((E4A / "selected_operators.json").read_text())
    paths.extend(Path(selected[m]["source_path"]) for m in ("F1", "F2-D"))
    paths.extend(E4A / "F2-D" / f for f in ("prompt.txt", "feedback.json"))
    paths.append(E4A / "candidate_metrics.json")
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    target = output / "frozen_input_hashes.json"
    if target.exists():
        assert hashes == json.loads(target.read_text()), "frozen E4-B inputs changed"
    else:
        write_json(target, hashes)


def geometry_analyze(output):
    """Post-evaluation summaries; this stage never changes candidate selection."""
    geometry_snapshot(output)
    metrics = json.loads((output / "candidate_metrics.json").read_text())
    choices = json.loads((output / "selected_operators.json").read_text())
    selected = {m: next(r for r in group if r["source_hash"] == choices[m]["source_hash"])
                for m, group in metrics.items()}
    parent = max((r for r in load_rows("F1") if r["generation"] == 0),
                 key=lambda r: r["avg_relative_improvement"])
    parent_source = Path(parent["source_path"]).read_text(encoding="utf-8")
    assert hashlib.sha256(parent_source.encode()).hexdigest() == parent["source_hash"]
    (output / "common_parent.py").write_text(parent_source, encoding="utf-8")
    write_json(output / "common_parent_evaluation.json", parent)
    write_json(output / "lineage.json", dict(parent_hash=parent["source_hash"],
        parent_source=parent["source_path"], selected_children=choices,
        children={mode: [dict(source_hash=r["source_hash"], parent_source_hash=r["parent_source_hash"],
                              source_path=r["source_path"], generation=r["generation"]) for r in group]
                  for mode, group in metrics.items()},
        reuse="F1/F2-D children and fixed-repair evaluations from E4-A; only F2-G generated in E4-B",
        selection="Fully feasible child with best development fixed-repair mean; no B1-based reselection"))
    ref = [(t["instance_id"], t["solver_seed"], t["baseline_makespan"]) for t in selected["F1"]["trials"]]
    trials, fixed = [], []
    for mode, group in metrics.items():
        for row in group:
            if row.get("feasible_count") == 24:
                assert [(t["instance_id"], t["solver_seed"], t["baseline_makespan"]) for t in row["trials"]] == ref
        row = selected[mode]
        source = Path(row["source_path"]).read_text(encoding="utf-8")
        assert hashlib.sha256(source.encode()).hexdigest() == row["source_hash"]
        fixed.append(dict(condition=mode, candidates=len(group),
            contract_valid=sum(r["validation_status"] == "valid" for r in group),
            feasible_trials=sum(r["feasible_count"] for r in group),
            evaluated_trials=sum(r["executed_count"] for r in group),
            selected_hash=row["source_hash"], fixed_repair_improvement_pct=100*row["avg_relative_improvement"],
            source_attributes_used={name: name in source for name in ("sweep_width", "sweep_speed", "turning_time", "travel_speed")}))
        for t in row["trials"]:
            if not t["feasible"]:
                continue
            before, after = t["baseline_route_costs"], t["candidate_route_costs"]
            old = {i for i, x in enumerate(before) if abs(x-max(before))<1e-9}
            new = {i for i, x in enumerate(after) if abs(x-max(after))<1e-9}
            trials.append(dict(condition=mode, **{k:t[k] for k in (
                "instance_id", "solver_seed", "baseline_makespan", "candidate_makespan", "relative_improvement",
                "baseline_route_costs", "candidate_route_costs", "reassigned_task_count")},
                bottleneck_changed=old.isdisjoint(new), degraded=t["relative_improvement"] < -1e-9,
                **t["exact_dp_behavior"]))
    write_json(output / "revision_summary.json", fixed)
    _write_csv(output / "selected_trial_comparison.csv", trials)
    rows = json.loads((output / "b1_comparison/results.json").read_text())
    assert len(rows) == 24 and len({(r["instance"],r["seed"],r["method"]) for r in rows}) == 24
    pairwise = []
    for mode in metrics:
        for comparator in metrics:
            if mode == comparator:
                continue
            others = {(r["instance"],r["seed"]):r for r in rows if r["method"] == comparator and r["feasible"]}
            pairs = [(r, others[(r["instance"],r["seed"])]) for r in rows if r["method"] == mode and r["feasible"]]
            pairwise.append(dict(method=mode, comparator=comparator, pairs=len(pairs),
                wins=sum(a["makespan"] < b["makespan"]-1e-9 for a,b in pairs),
                ties=sum(abs(a["makespan"]-b["makespan"])<1e-9 for a,b in pairs),
                losses=sum(a["makespan"] > b["makespan"]+1e-9 for a,b in pairs),
                paired_improvement_pct=mean(100*(1-a["makespan"]/b["makespan"]) for a,b in pairs) if pairs else None))
    write_json(output / "pairwise_comparisons.json", pairwise)
    per_instance=[]
    for name in SHORT_INSTANCES:
        for mode in metrics:
            group=[r for r in rows if r["instance"]==name and r["method"]==mode and r["feasible"]]
            if group:
                per_instance.append(dict(instance=name,condition=mode,
                    **{f"mean_{k}":mean(r[k] for r in group) for k in ("makespan","iterations","runtime_seconds","llm_repair_uses","route_dp_calls")}))
        records=[json.loads((output / "b1_comparison/runs" / f"{name}_{mode}_s{seed}.json").read_text()) for mode in metrics for seed in SEEDS]
        assert all(r["initial_routes"] == records[0]["initial_routes"] for r in records)
    _write_csv(output / "per_instance_results.csv", per_instance)
    iteration_diagnostics = []
    for row in rows:
        record=json.loads((output / "b1_comparison/runs" / f"{row['instance']}_{row['method']}_s{row['seed']}.json").read_text())
        assert row["budget_seconds"] == max(5.0,0.25*row["tasks"])
        assert len(record["history"]) == row["iterations"]
        assert row["feasible"] and row["llm_repair_uses"] > 0
        previous = 0.0
        selected_iteration_seconds = 0.0
        selected_history = []
        for item in record["history"]:
            if item["repair"] == "e4_selected_repair":
                selected_iteration_seconds += item["elapsed_seconds"] - previous
                selected_history.append(item)
            previous = item["elapsed_seconds"]
        iteration_diagnostics.append(dict(method=row["method"], instance=row["instance"], seed=row["seed"],
            selected_repair_iteration_seconds=selected_iteration_seconds,
            selected_repair_iteration_time_fraction=selected_iteration_seconds / row["runtime_seconds"],
            llm_iterations_worsening_current=sum(h["candidate_delta"] > 1e-9 for h in selected_history),
            llm_iterations_accepted=sum(h["accepted"] for h in selected_history),
            interpretation="Selected-repair iteration time includes bounded subprocess startup, repair, evaluation and local search; not isolated operator CPU time"))
    _write_csv(output / "iteration_diagnostics.csv", iteration_diagnostics)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,2,figsize=(10,6.5),constrained_layout=True)
    for name,ax in zip(SHORT_INSTANCES,axes.flat):
        for mode,color in zip(metrics,("#264653","#2A9D8F","#E76F51")):
            for seed in SEEDS:
                rec=json.loads((output / "b1_comparison/runs" / f"{name}_{mode}_s{seed}.json").read_text())
                r,h=rec["result"],rec["history"]
                ax.step([0]+[v["elapsed_seconds"] for v in h]+[r["runtime_seconds"]],
                    [r["initial_makespan"]]+[v["best_makespan"] for v in h]+[r["makespan"]],
                    where="post",color=color,linestyle="-" if seed==0 else "--",label=f"{mode}, seed {seed}")
        ax.set(title=name,xlabel="Solve time (s)",ylabel="Best makespan")
        ax.grid(alpha=0.2)
    axes.flat[0].legend(fontsize=7)
    fig.savefig(output / "convergence.png",dpi=180)
    fig.savefig(output / "convergence.pdf")
    plt.close(fig)
    print("E4-B paired summaries, frozen inputs and 24 real B1 histories verified",flush=True)


def load_rows(branch):
    return [json.loads(line) for line in (EVOLUTION / branch / "candidate_metrics.jsonl").read_text(encoding="utf-8").splitlines()]


def load_repair(choice):
    loaded = load_and_validate_candidate(
        path=Path(choice["source_path"]), operator_type="repair", round_id=choice["generation"],
        source="langchain_openai_compatible", description="E4 development repair",
        allow_unsafe_candidate_execution=True)
    if loaded.callable_obj is None or loaded.validation.code_hash != choice["source_hash"]:
        raise ValueError(f"repair validation/hash failed: {loaded.validation}")
    return loaded


def benchmark(output, choices, instances, *, alpha=1.0, minimum_runtime_seconds=0.0):
    """Same B1/initial routes; add one external repair to the existing manual pool."""
    output.mkdir(parents=True, exist_ok=True)
    methods = list(choices)
    write_json(output / "config.json", dict(
        instances=[dict(name=name, sha256=hashlib.sha256((ROOT / "data" / f"{name}.txt").read_bytes()).hexdigest()) for name in instances],
        seeds=SEEDS, alpha=alpha, minimum_runtime_seconds=minimum_runtime_seconds, choices=choices, constructor="spatial_sort",
        B1=asdict(ALNSConfig.enhanced()), interpretation="development/exploratory; additive repair registry; no tuning",
        timing="solve() includes initial evaluator; setup/loading/verification excluded; deadline checked at iteration boundaries"))
    rows = []
    for name in instances:
        instance = load_instance(ROOT / "data" / f"{name}.txt")
        budget = max(minimum_runtime_seconds, alpha * instance.task_count)
        for seed in SEEDS:
            initial_routes = None
            order = methods if seed == 0 else list(reversed(methods))
            for method in order:
                target = output / "runs" / f"{name}_{method}_s{seed}.json"
                if target.exists():
                    saved = json.loads(target.read_text(encoding="utf-8"))
                    if saved["choice"] != choices[method] or saved["config"] != asdict(ALNSConfig.enhanced(iterations=None, max_runtime_seconds=budget, random_seed=seed)):
                        raise ValueError("cannot resume a run with a different operator/config")
                    rows.append(saved["result"])
                    continue
                record = dict(method=method, instance=name, seed=seed, tasks=instance.task_count,
                              robots=instance.robot_count, budget_seconds=budget,
                              feasible=False, status="error")
                cfg = ALNSConfig.enhanced(iterations=None, max_runtime_seconds=budget, random_seed=seed)
                setup_started = perf_counter()
                solver = ALNSSolver(instance, config=cfg)
                if initial_routes is None:
                    initial_routes = solver.initial_solution.routes
                assert initial_routes == solver.initial_solution.routes
                choice = choices[method]
                try:
                    if choice is not None:
                        loaded = load_repair(choice)
                        solver.register_development_repair(loaded.callable_obj, name="e4_selected_repair")
                    setup_seconds = perf_counter() - setup_started
                    result = solver.solve()
                    verified = solver.solution_evaluator.evaluate(result.best_solution)
                    assert abs(verified.makespan - result.best_evaluation.makespan) < 1e-9
                    uses = result.operator_usage_stats["repair"].get("e4_selected_repair")
                    record.update(makespan=verified.makespan, initial_makespan=result.initial_makespan,
                                  runtime_seconds=result.runtime_seconds, setup_seconds=setup_seconds,
                                  iterations=result.iterations_completed, route_dp_calls=result.route_dp_calls,
                                  route_dp_cache_misses=result.route_dp_cache_misses,
                                  llm_repair_uses=uses.uses if uses else 0,
                                  llm_repair_successes=sum(h["llm_operator_success"] for h in result.iteration_history),
                                  fallback_count=len(result.fallback_events),
                                  feasible=True, status="fallback" if result.fallback_events else "ok",
                                  overrun_seconds=max(0, result.runtime_seconds - cfg.max_runtime_seconds))
                    write_json(target, dict(result=record, choice=choice, config=asdict(cfg),
                                            initial_routes=solver.initial_solution.routes,
                                            best_routes=result.best_solution.routes, per_robot_costs=verified.per_robot_costs,
                                            fallback_events=result.fallback_events, history=result.iteration_history))
                except Exception as exc:
                    record.update(error=f"{type(exc).__name__}: {exc}")
                    write_json(target.with_suffix(".error.json"), record)
                rows.append(record)
                _write_csv(output / "results.csv", rows)
                write_json(output / "results.json", rows)
                print(json.dumps(record), flush=True)
    _write_csv(output / "results.csv", rows)
    write_json(output / "results.json", rows)
    summary = []
    ref = {(r["instance"], r["seed"]): r for r in rows if r["method"] == methods[0] and r["feasible"]}
    for method in methods:
        group = [r for r in rows if r["method"] == method and r["feasible"]]
        pairs = [(r, ref[(r["instance"], r["seed"])]) for r in group if (r["instance"], r["seed"]) in ref]
        summary.append(dict(method=method, feasible_runs=len(group),
            **{f"mean_{key}": mean(r[key] for r in group) if group else None for key in
               ("makespan", "runtime_seconds", "iterations", "route_dp_calls", "route_dp_cache_misses", "llm_repair_uses")},
            mean_llm_use_fraction=mean(r["llm_repair_uses"] / max(1, r["iterations"]) for r in group) if group else None,
            paired_improvement_vs_reference_pct=mean(100 * (1 - r["makespan"] / b["makespan"]) for r, b in pairs) if pairs else None,
            wins=sum(r["makespan"] < b["makespan"] - 1e-9 for r, b in pairs),
            ties=sum(abs(r["makespan"] - b["makespan"]) < 1e-9 for r, b in pairs),
            losses=sum(r["makespan"] > b["makespan"] + 1e-9 for r, b in pairs)))
    write_json(output / "summary.json", summary)
    print(json.dumps(summary, indent=2), flush=True)
    return rows


def analyze(output):
    """Summarize persisted observations only; never select using ALNS outcomes."""
    metrics = json.loads((output / "candidate_metrics.json").read_text())
    selected = json.loads((output / "selected_operators.json").read_text())
    selected_rows = {m: next(r for r in group if r["source_hash"] == selected[m]["source_hash"])
                     for m, group in metrics.items()}
    matched = {}
    reference = None
    for mode, group in metrics.items():
        for row in group:
            ids = [(t["instance_id"], t["solver_seed"], t.get("baseline_makespan")) for t in row.get("trials", [])]
            if reference is None:
                reference = ids
            assert ids == reference, "candidate evaluation cases are not paired"
        matched[mode] = dict(candidates=len(group), contract_valid=sum(r["validation_status"] == "valid" for r in group),
                             feasible_trials=sum(r["feasible_count"] for r in group),
                             evaluated_trials=sum(r["executed_count"] for r in group),
                             mean_fixed_improvement_pct=mean(100*r["avg_relative_improvement"] for r in group),
                             selected_hash=selected[mode]["source_hash"],
                             selected_fixed_improvement_pct=100*selected_rows[mode]["avg_relative_improvement"])
    write_json(output / "revision_summary.json", matched)
    provider = {}
    for mode in metrics:
        call = json.loads((output / mode / "provider_call.json").read_text())
        provider[mode] = call
        assert call["requested_cap"] == 2 and call["parsed_count"] == 2
        assert "Requested candidates: 2" in (output / mode / "prompt.txt").read_text(encoding="utf-8")
    write_json(output / "provider_summary.json", dict(conditions=provider, calls=3,
        total_tokens=sum(v["metadata"]["total_tokens"] for v in provider.values()),
        total_wall_seconds=sum(v["wall_seconds"] for v in provider.values()), estimated_cost_usd=None))
    case_table = []
    for mode, row in selected_rows.items():
        for trial in row["trials"]:
            if trial["feasible"]:
                case_table.append(dict(condition=mode, source_hash=row["source_hash"],
                    **{k:trial[k] for k in ("instance_id", "solver_seed", "baseline_makespan", "candidate_makespan", "relative_improvement", "baseline_route_costs", "candidate_route_costs", "reassigned_task_count")},
                    **trial["exact_dp_behavior"]))
    _write_csv(output / "selected_trial_comparison.csv", case_table)
    short = json.loads((output / "short_b1/results.json").read_text())
    compatibility = json.loads((output / "compatibility/results.json").read_text())
    per_instance = []
    for stage, rows in (("compatibility", compatibility), ("short_b1", short)):
        names = list(dict.fromkeys(r["instance"] for r in rows))
        methods = list(dict.fromkeys(r["method"] for r in rows))
        for name in names:
            for method in methods:
                group = [r for r in rows if r["instance"] == name and r["method"] == method and r["feasible"]]
                per_instance.append(dict(stage=stage, instance=name, method=method,
                    **{f"mean_{key}": mean(r[key] for r in group) for key in
                       ("makespan", "iterations", "runtime_seconds", "route_dp_calls", "llm_repair_uses")}))
        for row in rows:
            assert row["feasible"] and row["llm_repair_uses"] == row["llm_repair_successes"]
            if row["method"] != "B1":
                assert row["llm_repair_uses"] > 0
        baselines = {(r["instance"], r["seed"]): r for r in rows if r["method"] == methods[0]}
        comparisons = []
        for method in methods[1:]:
            for comparator in methods:
                if method == comparator:
                    continue
                other = {(r["instance"], r["seed"]):r for r in rows if r["method"] == comparator}
                pairs = [(r,other[(r["instance"],r["seed"])]) for r in rows if r["method"] == method]
                comparisons.append(dict(method=method, comparator=comparator,
                    wins=sum(a["makespan"] < b["makespan"] - 1e-9 for a,b in pairs),
                    ties=sum(abs(a["makespan"]-b["makespan"]) < 1e-9 for a,b in pairs),
                    losses=sum(a["makespan"] > b["makespan"] + 1e-9 for a,b in pairs),
                    paired_improvement_pct=mean(100*(1-a["makespan"]/b["makespan"]) for a,b in pairs)))
        write_json(output / stage / "pairwise_comparisons.json", comparisons)
    _write_csv(output / "per_instance_results.csv", per_instance)
    frozen = json.loads((output / "frozen_b1_hashes.json").read_text())
    assert all(hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest for path, digest in frozen.items())

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    colors = ("#264653", "#2A9D8F", "#E76F51")
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True)
    for i, (mode, group) in enumerate(metrics.items()):
        axes[0].scatter([i]*len(group), [100*r["avg_relative_improvement"] for r in group], color=colors[i], s=45)
        axes[0].scatter(i, matched[mode]["selected_fixed_improvement_pct"], facecolors="none", edgecolors=colors[i], s=140)
    parent, _ = paired_inputs(output)
    axes[0].axhline(100*parent["avg_relative_improvement"], color="gray", linestyle="--", label="Common parent")
    axes[0].axhline(0, color="black", linewidth=0.5)
    axes[0].set(xticks=range(3), xticklabels=list(metrics), ylabel="Fixed-repair improvement vs greedy (%)", title="Two children per condition; circle = selected")
    axes[0].legend(fontsize=8)
    baseline = {(r["instance"],r["seed"]):r for r in short if r["method"] == "F1"}
    for i, mode in enumerate(metrics):
        ys = []
        for name in SHORT_INSTANCES:
            group=[r for r in short if r["method"] == mode and r["instance"] == name]
            ys.append(mean(100*(1-r["makespan"]/baseline[(name,r["seed"])]["makespan"]) for r in group))
        axes[1].bar([j+(i-1)*0.25 for j in range(4)], ys, width=0.25, color=colors[i], label=mode)
    axes[1].axhline(0,color="black",linewidth=0.6)
    axes[1].set(xticks=range(4), xticklabels=[n.replace("_0", "") for n in SHORT_INSTANCES],
                ylabel="Paired B1 makespan improvement vs F1 (%)",title="Short B1 runs; two seeds")
    axes[1].tick_params(axis="x", labelrotation=20)
    axes[1].legend(fontsize=8)
    fig.savefig(output / "revision_comparison.png", dpi=180)
    fig.savefig(output / "revision_comparison.pdf")
    plt.close(fig)
    fig, axes = plt.subplots(2,2,figsize=(10,6.5),constrained_layout=True)
    for name, ax in zip(SHORT_INSTANCES,axes.flat):
        for i, mode in enumerate(metrics):
            for seed in SEEDS:
                record=json.loads((output / "short_b1/runs" / f"{name}_{mode}_s{seed}.json").read_text())
                row=record["result"]; history=record["history"]
                ax.step([0]+[h["elapsed_seconds"] for h in history]+[row["runtime_seconds"]],
                    [row["initial_makespan"]]+[h["best_makespan"] for h in history]+[row["makespan"]],
                    where="post", color=colors[i], linestyle="-" if seed==0 else "--",label=f"{mode}, seed {seed}")
        ax.set(title=name, xlabel="Solve time (s)", ylabel="Best makespan")
        ax.grid(alpha=0.2)
    axes.flat[0].legend(fontsize=7)
    fig.savefig(output / "short_convergence.png",dpi=180)
    fig.savefig(output / "short_convergence.pdf")
    plt.close(fig)
    print("Validated paired cases, real use, frozen B1 hashes, and generated summaries/plots",flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("compatibility", "evolve", "evaluate", "short", "analyze", "geometry-evolve", "geometry-evaluate", "geometry-benchmark", "geometry-analyze"), required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/e4a_decision_feedback")
    parser.add_argument("--condition", choices=("F1", "F2", "F2-D"), default="F2-D")
    args = parser.parse_args()
    if args.stage == "compatibility":
        selected = json.loads((ROOT / "outputs/e2r_c1_pilot/selected_operators.json").read_text(encoding="utf-8"))
        benchmark(args.output / "compatibility", {"B1": None, "B1_F1": selected["L1"], "B1_F2": selected["L2"]}, INSTANCES)
    elif args.stage == "evolve":
        evolve(args.output, args.condition)
    elif args.stage == "evaluate":
        evaluate(args.output)
    elif args.stage == "short":
        choices = json.loads((args.output / "selected_operators.json").read_text())
        if any(choice is None for choice in choices.values()):
            raise ValueError("a condition has no qualified child; report failure without substituting historical operators")
        benchmark(args.output / "short_b1", choices, SHORT_INSTANCES, alpha=0.25)
    elif args.stage == "analyze":
        analyze(args.output)
    elif args.stage == "geometry-evolve":
        geometry_snapshot(args.output)
        evolve(args.output, "F2-G")
    elif args.stage == "geometry-evaluate":
        geometry_snapshot(args.output)
        evaluate(args.output, modes=("F1", "F2-D", "F2-G"), reuse_e4a=True)
    elif args.stage == "geometry-benchmark":
        geometry_snapshot(args.output)
        choices = json.loads((args.output / "selected_operators.json").read_text())
        if any(choice is None for choice in choices.values()):
            raise ValueError("a condition has no fully feasible child; no substitution")
        benchmark(args.output / "b1_comparison", choices, SHORT_INSTANCES,
                  alpha=0.25, minimum_runtime_seconds=5.0)
    elif args.stage == "geometry-analyze":
        geometry_analyze(args.output)


if __name__ == "__main__":
    main()
