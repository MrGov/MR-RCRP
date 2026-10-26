"""One real pair-aware repair revision; frozen E6 ALNS and disjoint dev evaluation."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import difflib
from pathlib import Path
from statistics import mean
import subprocess
from time import perf_counter

from .e3_alns import ROOT, INSTANCES, SEEDS, write_json
from .e5_destroy_repair import D_NAME, R_NAME, digest, read, load_choice
from .e6_pair_selection import config_for, make_solver
from .e2_c1_pilot import _write_csv
from .e1_real_llm_pilot import compute_exact_dp_behavior
from ..core.instance_loader import load_instance
from ..core.models import MultiRobotSolution
from ..heuristics.alns_solver import ALNSConfig, ALNSSolver
from ..llm.operator_evolution.evaluator import (
    DestroyBenchmarkCase, PairedRepairBenchmarkCase, build_destroy_benchmark_cases,
    prepare_paired_repair_cases, evaluate_paired_repair_candidates)
from ..llm.operator_evolution.feedback_builder import build_pair_feedback
from ..llm.prompts.operator_revision import build_paired_repair_revision_prompt
from ..llm.operator_evolution.candidate_loader import load_and_validate_candidate, persist_operator_drafts

SELECTION = ("R2_T20_3", "R4_T60_8", "R8_T100_5")
METHODS = ("V1", "V2", "V3")
E5 = ROOT / "outputs/e5_llm_destroy_repair"
E6 = ROOT / "outputs/e6_pair_selection"


def choose_repair(parent, children, fixed_rows, short_rows):
    """Predeclared conservative gate, short full ALNS is the selection objective.

    Keep parent on ties, missing trials/fallbacks, or >2% fixed-pair degradation.
    Among eligible children choose lowest mean paired ALNS makespan ratio.
    """
    p = parent["source_hash"]
    baseline = short_rows[p]
    best, best_ratio = parent, 1.0
    for child in children:
        h = child["source_hash"]
        row, runs = fixed_rows.get(h), short_rows.get(h, [])
        if (not row or row["feasible_count"] != row["executed_count"] or not row["executed_count"]
            or row["executed_count"] != fixed_rows[p]["executed_count"]
            or len(runs) != len(baseline) or not runs
            or any((a.get("instance"),a.get("seed")) != (b.get("instance"),b.get("seed")) for a,b in zip(runs,baseline))
            or any(not r["feasible"] or r["fallback_count"] for r in runs)
            or row["mean_makespan"] > 1.02 * fixed_rows[p]["mean_makespan"]):
            continue
        ratio = mean(a["makespan"]/b["makespan"] for a,b in zip(runs,baseline))
        if ratio < best_ratio - 1e-9:
            best, best_ratio = child, ratio
    return best


def setup(output):
    output.mkdir(parents=True, exist_ok=True)
    target = output / "experiment_config.json"
    if not target.exists():
        selected = read(E5 / "selected_operators.json")
        e6 = read(E6 / "experiment_config.json")
        assert selected == e6["selected"]
        assert digest(ROOT / "src/mrta_rect_coverage/heuristics/alns_solver.py") == e6["implementation_hash"]
        assert not set(SELECTION) & set(INSTANCES)
        # These three were already evolution-development in the E2 pilot.
        manifest = read(ROOT / "outputs/e2_c1_pilot/instance_manifest.json")
        dev = {Path(r["path"]).stem for r in manifest["instances"] if r["split"] == "evolution-development"}
        assert set(SELECTION) <= dev
        for kind, identity in selected.items():
            assert digest(identity["source_path"]) == identity["source_hash"]
            (output / f"parent_{kind}.py").write_text(Path(identity["source_path"]).read_text(encoding="utf-8"), encoding="utf-8")
        frozen = [ROOT / "src/mrta_rect_coverage/heuristics/alns_solver.py",
                  ROOT / "src/mrta_rect_coverage/core/dp_evaluator.py", ROOT / "configs/e3_b1.yaml"]
        frozen += [ROOT / "data" / f"{n}.txt" for n in SELECTION + INSTANCES]
        frozen += [Path(i["source_path"]) for i in selected.values()]
        write_json(target, dict(phase="E7", git_head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
            selected=selected, selection_instances=SELECTION, comparison_instances=INSTANCES, seeds=SEEDS,
            constructor="spatial_sort", full_parent_states=["initial", "manual_B1_100_iterations"],
            remove_count="max(1,task_count//4)", fixed_inputs="one bounded D* execution per instance/parent-state/seed; persisted and reused for every repair",
            revision_requests=1, max_children=2, timeout_ms=2000, destroy_generation_requests=0,
            short_budget="max(5,0.1*task_count) seconds", comparison_budget="task_count seconds",
            selection_rule="all fixed and short trials feasible, no fallback; fixed mean <=1.02*parent; lowest mean paired short-ALNS makespan ratio <1; parent retained on ties",
            B1=asdict(ALNSConfig.enhanced()), pool_sizes={m:[4,4] for m in METHODS},
            method_configs={m:asdict(config_for(load_instance(ROOT/'data/R2_T10_0.txt'),0,'V2' if m=='V3' else m)) for m in METHODS},
            original_V1_config=str(E6/'V1_config.json'), original_V2_config=str(E6/'V2_config.json'),
            frozen_hashes={str(p):digest(p) for p in frozen},
            interpretation="development/exploratory, disjoint candidate-selection/comparison instances; comparison instances previously used in E5/E6, not confirmatory",
            final_test_accessed=False, post_comparison_tuning=False,
            commands=[f"python -m mrta_rect_coverage.experiments.e7_cooperative_evolution --stage {s}" for s in
                      ("prepare","evolve","evaluate","short","select","smoke","benchmark","analyze")]))
        for name in ("V1_config.json","V2_config.json","selected_operators.json"):
            write_json(output / "v1_v2_reference" / name, read(E6/name))
    config = read(target)
    for path,h in config["frozen_hashes"].items():
        if digest(path) != h:
            raise ValueError(f"frozen E7 input changed: {path}")
    return config


def prepare(output):
    config = setup(output)
    if (output / "pair_inputs.json").exists():
        print("Reuse frozen D* outputs and parent evidence; no destroy re-execution",flush=True)
        return
    selected = config["selected"]
    destroy, repair = load_choice(selected["destroy"],"destroy"), load_choice(selected["repair"],"repair")
    cases = build_destroy_benchmark_cases([ROOT/'data'/f'{n}.txt' for n in SELECTION],constructor="spatial_sort")
    paired = prepare_paired_repair_cases(cases,fixed_destroy=destroy,seeds=SEEDS,timeout_ms=2000)
    # Fixed-iteration manual incumbent supplies genuine harder restoration cases.
    for case in cases:
        for seed in SEEDS:
            solver = ALNSSolver(case.instance,constructor="spatial_sort",config=ALNSConfig.enhanced(iterations=100,random_seed=seed))
            result = solver.solve()
            incumbent = DestroyBenchmarkCase(case.instance,case.evaluator,result.best_solution,
                                              case.evaluator.evaluate(result.best_solution))
            paired.extend(prepare_paired_repair_cases([incumbent],fixed_destroy=destroy,seeds=[seed],timeout_ms=2000,
                                                     parent_label="manual_B1_100_iterations"))
    row = evaluate_paired_repair_candidates([repair],paired,timeout_ms=2000,behavior_callback=compute_exact_dp_behavior)[0]
    row.update(selected["repair"])
    write_json(output/"parent_pair_evaluation.json",row)
    if row["feasible_count"] != len(paired):
        raise RuntimeError("frozen parent pair failed; inspect real evidence")
    records = [dict(input_id=c.input_id,instance_id=c.instance.name,solver_seed=c.solver_seed,
        fixed_destroy_hash=c.fixed_destroy_hash,destroy_runtime_ms=c.destroy_runtime_ms,
        parent_routes=c.full_solution.routes,partial_routes=c.partial_solution.routes,removed_tasks=c.removed_tasks,
        parent_makespan=c.full_evaluation.makespan,parent_route_costs=c.full_evaluation.per_robot_costs) for c in paired]
    write_json(output/"pair_inputs.json",records)
    feedback = build_pair_feedback(row,destroy_identity=selected["destroy"],source_reference=str(output/"parent_pair_evaluation.json"))
    write_json(output/"feedback.json",feedback)
    prompt = build_paired_repair_revision_prompt(parent=selected["repair"],feedback=feedback,n=2)
    prompt += "\nFrozen D* actual source, for understanding released neighborhoods only (do not change):\n```python\n" + Path(selected["destroy"]["source_path"]).read_text(encoding="utf-8") + "\n```\n"
    (output/"revision_prompt.txt").write_text(prompt,encoding="utf-8")
    print(f"Frozen {len(paired)} real D* inputs; parent pair {row['feasible_count']} feasible. Outcomes: {feedback['summary']}",flush=True)


def load_inputs(output):
    result=[]
    bases = {c.instance.name:c for c in build_destroy_benchmark_cases([ROOT/'data'/f'{n}.txt' for n in SELECTION],constructor="spatial_sort")}
    for r in read(output/"pair_inputs.json"):
        base=bases[r["instance_id"]]
        full,partial=MultiRobotSolution(r["parent_routes"]),MultiRobotSolution(r["partial_routes"])
        evaluation=base.evaluator.evaluate(full)
        assert evaluation.makespan==r["parent_makespan"] and evaluation.per_robot_costs==r["parent_route_costs"]
        result.append(PairedRepairBenchmarkCase(base.instance,base.evaluator,full,evaluation,partial,
            base.evaluator.evaluate_partial(partial),r["removed_tasks"],r["solver_seed"],r["fixed_destroy_hash"],
            r["destroy_runtime_ms"],r["input_id"]))
    return result


def evolve(output):
    setup(output)
    if (output/"generated_candidates.json").exists():
        print("Reuse saved real revision; no new provider request",flush=True)
        return
    from ..llm.operator_evolution.provider_factory import build_provider
    from ..llm.runtime.config import load_from_env
    cfg=load_from_env()
    historical=read(E5/"provider_config.json")
    assert cfg.model==historical["model"] and cfg.base_url==historical["base_url"]
    write_json(output/"provider_config.json",{k:v for k,v in asdict(cfg).items() if k!="api_key"})
    provider=build_provider("langchain_openai_compatible",raw_response_dir=output/"raw_responses")
    started=perf_counter()
    try:
        drafts=provider.revise_operator_candidates((output/"revision_prompt.txt").read_text(encoding="utf-8"),read(output/"feedback.json"),2,"repair",2)
    except Exception as exc:
        write_json(output/"provider_failure.json",dict(error=f"{type(exc).__name__}: {exc}",wall_seconds=perf_counter()-started))
        raise
    paths=persist_operator_drafts(output/"generated",list(drafts)[:2])
    write_json(output/"provider_call.json",dict(metadata=provider.last_call_metadata,wall_seconds=perf_counter()-started,requested_cap=2,parsed_count=len(drafts)))
    config=setup(output)
    write_json(output/"generated_candidates.json",[dict(operator_id=d.operator_id,generation=2,source_path=str(p.resolve()),
        source_hash=digest(p),description=d.description,parent_source_hash=config["selected"]["repair"]["source_hash"],
        paired_destroy_hash=config["selected"]["destroy"]["source_hash"]) for p,d in zip(paths,drafts)])
    print(f"Saved {len(paths)} real pair-aware repair children",flush=True)


def evaluate(output):
    setup(output)
    inputs=load_inputs(output)
    parent=read(output/"parent_pair_evaluation.json")
    rows={parent["source_hash"]:parent}
    for child in read(output/"generated_candidates.json"):
        target=output/"fixed_evaluations"/f"{child['operator_id']}.json"
        if target.exists():
            rows[child["source_hash"]]=read(target)
            continue
        loaded=load_and_validate_candidate(path=Path(child["source_path"]),operator_type="repair",round_id=2,
            source="langchain_openai_compatible",description=child["description"],allow_unsafe_candidate_execution=True)
        write_json(target.with_name(target.stem+"_validation.json"),asdict(loaded.validation))
        assert loaded.validation.code_hash==child["source_hash"]
        row=(evaluate_paired_repair_candidates([loaded],inputs,timeout_ms=2000,behavior_callback=compute_exact_dp_behavior,
            reference_trials=parent["trials"])[0] if loaded.callable_obj is not None else
            dict(feasible_count=0,executed_count=len(inputs),mean_makespan=None,trials=[],validation_status=loaded.validation.validation_status))
        row.update(child)
        write_json(target,row); rows[child["source_hash"]]=row
        before=Path(parent["source_path"]).read_text(encoding="utf-8").splitlines(True)
        after=Path(child["source_path"]).read_text(encoding="utf-8").splitlines(True)
        target.with_suffix(".diff").write_text(''.join(difflib.unified_diff(before,after,fromfile="R_star",tofile=child["operator_id"])),encoding="utf-8")
        print(f"{child['operator_id']}: fixed pair feasible {row['feasible_count']}/{row['executed_count']}, mean={row['mean_makespan']}",flush=True)
    write_json(output/"fixed_evaluations.json",rows)


def run_one(output, name, seed, method, selected, *, budget=None):
    target=output/"runs"/f"{name}_{method}_s{seed}.json"
    instance=load_instance(ROOT/'data'/f'{name}.txt')
    expected=config_for(instance,seed,"V1" if method=="V1" else "V2")
    if budget is not None:
        expected.max_runtime_seconds=budget
    if target.exists():
        saved=read(target)
        assert saved["config"]==asdict(expected) and saved["selected"]==selected
        return saved
    started=perf_counter()
    solver=make_solver(instance,seed,selected,"V1" if method=="V1" else "V2")
    solver.config=expected
    setup_seconds=perf_counter()-started
    result=solver.solve()
    verified=solver.solution_evaluator.evaluate(result.best_solution)
    assert verified.makespan==result.best_evaluation.makespan
    h=result.iteration_history
    r=dict(instance=name,seed=seed,method=method,feasible=True,status="fallback" if result.fallback_events else "ok",
        makespan=verified.makespan,initial_makespan=result.initial_makespan,runtime_seconds=result.runtime_seconds,
        setup_seconds=setup_seconds,iterations=result.iterations_completed,route_dp_calls=result.route_dp_calls,
        route_dp_cache_misses=result.route_dp_cache_misses,budget_seconds=expected.max_runtime_seconds,
        llm_destroy_uses=sum(x["destroy"]==D_NAME for x in h),llm_repair_uses=sum(x["repair"]==R_NAME for x in h),
        joint_uses=sum(x["destroy"]==D_NAME and x["repair"]==R_NAME for x in h),
        global_best_improvements=sum(b < a for a,b in zip(
            [result.initial_makespan]+[x["best_makespan"] for x in h], [x["best_makespan"] for x in h])),
        active_pair_uses=result.pair_action_stats["uses"],active_pair_accepted=result.pair_action_stats["accepted"],
        active_pair_global_best=result.pair_action_stats["global_best"],active_pair_reward=result.pair_action_stats["reward"],
        fallback_count=len(result.fallback_events),**result.timing_breakdown_seconds)
    saved=dict(result=r,config=asdict(expected),selected=selected,initial_routes=solver.initial_solution.routes,
        best_routes=result.best_solution.routes,per_robot_costs=verified.per_robot_costs,history=h,
        pair_action_stats=result.pair_action_stats,generated_operator_execution=result.generated_operator_execution,
        fallback_events=result.fallback_events,operator_pools=dict(destroy=list(solver.destroy_ops),repair=list(solver.repair_ops)))
    write_json(target,saved)
    print(f"{name} s{seed} {method}: M={r['makespan']:.1f}, {r['iterations']} iterations, pair={r['active_pair_uses']}, fallback={r['fallback_count']}",flush=True)
    return saved


def short(output):
    config=setup(output)
    fixed=read(output/"fixed_evaluations.json")
    choices=[config["selected"]["repair"]]+read(output/"generated_candidates.json")
    eligible=[c for c in choices if fixed[c["source_hash"]]["feasible_count"]==fixed[c["source_hash"]]["executed_count"]]
    rows={c["source_hash"]:[] for c in eligible}
    for name in SELECTION:
        instance=load_instance(ROOT/'data'/f'{name}.txt')
        budget=max(5.,.1*instance.task_count)
        for seed in SEEDS:
            for c in (eligible if seed==0 else list(reversed(eligible))):
                selected=dict(config["selected"],repair=c)
                saved=run_one(output/"selection",name,seed,c["operator_id"],selected,budget=budget)
                rows[c["source_hash"]].append(saved["result"])
    write_json(output/"short_evaluations.json",rows)


def select(output):
    config=setup(output)
    parent=config["selected"]["repair"]
    children=read(output/"generated_candidates.json")
    fixed,short_rows=read(output/"fixed_evaluations.json"),read(output/"short_evaluations.json")
    chosen=choose_repair(parent,children,fixed,short_rows)
    selected=dict(config["selected"],repair=chosen)
    write_json(output/"selected_operators.json",selected)
    write_json(output/"selection_decision.json",dict(adopted_child=chosen["source_hash"]!=parent["source_hash"],selected=chosen,
        parent_retained=True,rule=config["selection_rule"],
        candidates=[dict(identity=c,fixed_mean=fixed[c["source_hash"]]["mean_makespan"],
            short_mean=mean(r["makespan"] for r in short_rows[c["source_hash"]]) if c["source_hash"] in short_rows else None)
            for c in [parent]+children]))
    (output/"selected_repair.py").write_text(Path(chosen["source_path"]).read_text(encoding="utf-8"),encoding="utf-8")
    write_json(output/"V3_config.json",dict(method="V3",selected=selected,
        adopted_child=chosen["source_hash"]!=parent["source_hash"],
        pair_selection="unchanged E6 coupled selection",constructor="spatial_sort",pool_size=[4,4],
        budget="task_count seconds",seeds=SEEDS,instances=INSTANCES,
        profile=asdict(config_for(load_instance(ROOT/'data/R2_T10_0.txt'),0,"V2")),
        status="new repair adopted" if chosen["source_hash"]!=parent["source_hash"] else "retains R*; V3 is an independent timed repeat of V2"))
    print(f"Selected {chosen['operator_id']} ({chosen['source_hash']}); child adopted={chosen['source_hash']!=parent['source_hash']}",flush=True)


def smoke(output):
    setup(output)
    selected=read(output/"selected_operators.json")
    solver=make_solver(load_instance(ROOT/'data/R2_T10_0.txt'),0,selected,"V2",iterations=2)
    def force(_context):
        solver._last_selection_action="coupled"
        return D_NAME,R_NAME,"E7_integration_smoke"
    solver._select_operators=force
    result=solver.solve()
    assert result.pair_action_stats["successful_uses"]==2 and not result.fallback_events
    assert solver.solution_evaluator.evaluate(result.best_solution).makespan==result.best_evaluation.makespan
    write_json(output/"smoke.json",dict(feasible=True,selected=selected,pair_action_stats=result.pair_action_stats,history=result.iteration_history))
    print("V3 frozen pair smoke: 2/2 successful, no fallback",flush=True)


def benchmark(output):
    config=setup(output)
    assert (output/"smoke.json").exists()
    selected=read(output/"selected_operators.json")
    rows=[]
    for name in INSTANCES:
        for seed in SEEDS:
            for method in (METHODS if seed==0 else tuple(reversed(METHODS))):
                identity=selected if method=="V3" else config["selected"]
                rows.append(run_one(output,name,seed,method,identity)["result"])
                _write_csv(output/"results.csv",rows)
                write_json(output/"results.json",rows)


def analyze(output):
    config=setup(output)
    saved=[read(output/"runs"/f"{n}_{m}_s{s}.json") for n in INSTANCES for s in SEEDS for m in METHODS]
    rows=[d["result"] for d in saved]
    index={(r["method"],r["instance"],r["seed"]):r for r in rows}
    for name in INSTANCES:
        verifier=ALNSSolver(load_instance(ROOT/'data'/f'{name}.txt'),constructor="spatial_sort")
        for d in (d for d in saved if d["result"]["instance"]==name):
            r=d["result"]
            assert d["initial_routes"]==verifier.initial_solution.routes
            assert verifier.solution_evaluator.evaluate(MultiRobotSolution(d["best_routes"])).makespan==r["makespan"]
            assert len(d["operator_pools"]["destroy"])==len(d["operator_pools"]["repair"])==4
            assert d["config"]==asdict(config_for(verifier.instance,r["seed"],"V1" if r["method"]=="V1" else "V2"))
            assert d["selected"]==(read(output/"selected_operators.json") if r["method"]=="V3" else config["selected"])
            assert sum(x["actively_selected_frozen_pair"] for x in d["history"])==r["active_pair_uses"]
            assert r["joint_uses"]==r["active_pair_uses"]+d["pair_action_stats"]["independent_coincidental_uses"]
            assert len(d["history"])==r["iterations"]
            assert all(b["best_makespan"]<=a["best_makespan"] for a,b in zip(d["history"],d["history"][1:]))
    fields=("makespan","runtime_seconds","iterations","route_dp_calls","route_dp_cache_misses","global_best_improvements",
        "llm_destroy_uses","llm_repair_uses","joint_uses","active_pair_uses","active_pair_accepted","active_pair_global_best","active_pair_reward")
    summary=[]
    for m in METHODS:
        group=[r for r in rows if r["method"]==m]
        row=dict(method=m,**{f"mean_{k}":mean(r[k] for r in group) for k in fields})
        row["joint_fraction"]=sum(r["joint_uses"] for r in group)/sum(r["iterations"] for r in group)
        for base in ("V1","V2"):
            pairs=[(r,index[base,r["instance"],r["seed"]]) for r in group]
            row[f"paired_improvement_vs_{base}_pct"]=mean(100*(1-a["makespan"]/b["makespan"]) for a,b in pairs)
            row[f"wtl_vs_{base}"]=[sum(a["makespan"]<b["makespan"] for a,b in pairs),sum(a["makespan"]==b["makespan"] for a,b in pairs),sum(a["makespan"]>b["makespan"] for a,b in pairs)]
        summary.append(row)
    write_json(output/"summary.json",summary); _write_csv(output/"summary.csv",summary)
    _write_csv(output/"per_instance_results.csv",[dict(instance=n,**{m:mean(r["makespan"] for r in rows if r["method"]==m and r["instance"]==n) for m in METHODS}) for n in INSTANCES])
    write_json(output/"verification_summary.json",dict(feasible_runs=len(rows),expected_runs=24,
        fallback_count=sum(r["fallback_count"] for r in rows),full_solutions_reevaluated=True,
        same_initial_solutions=True,pool_sizes_equal=True,global_best_monotonic=True,
        disjoint_selection_comparison=not bool(set(SELECTION)&set(INSTANCES)),frozen_hashes_verified=True,
        config_identity_and_pair_counts_verified=True,
        generated_execution_calls=sum(x["calls"] for d in saved for group in d["generated_operator_execution"].values() for x in group.values()),
        generated_execution_failures=sum(x["failures"] for d in saved for group in d["generated_operator_execution"].values() for x in group.values()),
        archived_runtime_anomalies=read(output/"runtime_anomaly.json") if (output/"runtime_anomaly.json").exists() else [],
        real_revision_requests=1,post_comparison_tuning=False))
    evolution_report(output, summary)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size":9,"axes.spines.top":False,"axes.spines.right":False,"pdf.fonttype":42})
    fig,axes=plt.subplots(2,4,figsize=(13,5.4))
    child_adopted=read(output/"selection_decision.json")["adopted_child"]
    for j,n in enumerate(INSTANCES):
        for s in SEEDS:
            ax=axes[s,j]
            for m,color,style in zip(METHODS,("#0072B2","#009E73","#D55E00"),("-","--",":")):
                d=next(d for d in saved if d["result"]["instance"]==n and d["result"]["method"]==m and d["result"]["seed"]==s)
                h=d["history"];r=d["result"]
                label=m+ (" (R* retained)" if m=="V3" and not child_adopted else "")
                ax.step([0]+[x["elapsed_seconds"] for x in h]+[r["runtime_seconds"]],
                    [r["initial_makespan"]]+[x["best_makespan"] for x in h]+[r["makespan"]],where="post",label=label,color=color,linestyle=style)
            ax.set(title=f"{n}, seed {s}",xlabel="Solve time (s)",ylabel="Best makespan"); ax.grid(alpha=.15)
    axes[0,0].legend(frameon=False);fig.tight_layout()
    fig.savefig(output/"convergence.png",dpi=300);fig.savefig(output/"convergence.pdf");plt.close(fig)
    print(summary,flush=True)


def evolution_report(output, summary):
    """Summarize measured outcomes and the code actually returned by the provider."""
    config=read(output/"experiment_config.json")
    parent=config["selected"]["repair"]
    p=parent["source_hash"]
    fixed,short_rows=read(output/"fixed_evaluations.json"),read(output/"short_evaluations.json")
    children=read(output/"generated_candidates.json")
    selected=read(output/"selection_decision.json")
    comparisons=[]
    cases=[]
    mapping=[]
    for identity in [parent]+children:
        h=identity["source_hash"]
        r=fixed[h]
        pairs=list(zip(r["trials"],fixed[p]["trials"]))
        short_pairs=list(zip(short_rows.get(h,[]),short_rows[p]))
        comparisons.append(dict(operator_id=identity["operator_id"],source_hash=h,
            fixed_feasible=r["feasible_count"],fixed_trials=r["executed_count"],fixed_mean_makespan=r["mean_makespan"],
            fixed_paired_improvement_pct=mean(100*(1-a["candidate_makespan"]/b["candidate_makespan"]) for a,b in pairs) if pairs else None,
            fixed_wtl=[sum(a["candidate_makespan"]<b["candidate_makespan"] for a,b in pairs),sum(a["candidate_makespan"]==b["candidate_makespan"] for a,b in pairs),sum(a["candidate_makespan"]>b["candidate_makespan"] for a,b in pairs)],
            fixed_mean_runtime_ms=r.get("avg_runtime_ms"),
            short_mean_makespan=mean(a["makespan"] for a,b in short_pairs) if short_pairs else None,
            short_paired_improvement_pct=mean(100*(1-a["makespan"]/b["makespan"]) for a,b in short_pairs) if short_pairs else None,
            short_mean_iterations=mean(a["iterations"] for a,b in short_pairs) if short_pairs else None,
            short_active_pair_uses=sum(a["active_pair_uses"] for a,b in short_pairs),
            short_llm_repair_uses=sum(a["llm_repair_uses"] for a,b in short_pairs)))
        if identity in children:
            tokens=("horizontal_passes", "vertical_passes", "turning_time", "travel_speed", "projected_loads",
                "other_peak", "regret", "calibration", "fair_target", "route_proxy")
            lines=Path(identity["source_path"]).read_text(encoding="utf-8").splitlines()
            mapping.append(dict(operator_id=identity["operator_id"],source_hash=h,
                anchors=[dict(line=i,text=line.strip()) for i,line in enumerate(lines,1) if any(t in line for t in tokens)],
                observed_changes="actual H/V/turning workload and Manhattan geometry enter insertion scores; projected route costs update after each placement; no online evaluator",
                limits="min(H,V) does not guarantee compatible corner/parity states. No controlled ablation separates geometry, regret, calibration or D-conditioning effects."))
        for a,b in pairs:
            if b["parent_relative_improvement"]<0 or (identity in children and a["parent_relative_improvement"]<0):
                cases.append(dict(operator_id=identity["operator_id"],input_id=a["input_id"],
                    full_parent_makespan=a["parent_makespan"],R_star_makespan=b["candidate_makespan"],repair_makespan=a["candidate_makespan"],
                    removed_task_moves=a["removed_task_moves"],parent_route_costs=a["parent_route_costs"],candidate_route_costs=a["candidate_route_costs"],
                    parent_to_candidate_behavior=a["parent_to_candidate_behavior"],R_star_to_candidate_behavior=a["exact_dp_behavior"] if identity in children else "same repair",
                    source=str(output/"fixed_evaluations.json")+"#"+h))
    write_json(output/"evolution_summary.json",comparisons);_write_csv(output/"evolution_summary.csv",comparisons)
    write_json(output/"knowledge_to_code.json",mapping);write_json(output/"remaining_failure_cases.json",cases)
    hashes={str(Path(__file__)):digest(__file__)}
    for rel in ("llm/operator_evolution/evaluator.py","llm/operator_evolution/feedback_builder.py","llm/prompts/operator_revision.py"):
        path=ROOT/"src/mrta_rect_coverage"/rel;hashes[str(path)]=digest(path)
    write_json(output/"implementation_hashes.json",hashes)
    lines=["# E7: paired Exact-DP-guided repair revision", "",
        "Development/exploratory results; selection and comparison instances are disjoint. The comparison instances were used previously in E5/E6.", "",
        "Frozen B1 and E6 selection are unchanged. V1 uses independent selection; V2 uses the frozen original pair; V3 uses the same coupled mechanism with the selected repair. All pools are 4 x 4.", "",
        "Workflow: freeze D*/R* -> execute D* once per parent/seed -> evaluate R* and canonical DP evidence -> one real repair revision request -> evaluate children on identical saved partials -> select using short full ALNS -> freeze repair -> run disjoint V1/V2/V3 comparison.", "",
        f"One real revision returned {len(children)} children. Provider metadata: `{output/'provider_call.json'}`. Original source, hashes, prompt, response and lineage are retained.", "",
        "| Repair | Fixed makespan | Fixed paired improvement | W/T/L vs R* | Short ALNS makespan | Short paired improvement |",
        "|---|---:|---:|---|---:|---:|"]
    for r in comparisons:
        if r['short_mean_makespan'] is not None:
            lines.append(f"| {r['operator_id']} | {r['fixed_mean_makespan']:.3f} | {r['fixed_paired_improvement_pct']:+.3f}% | {r['fixed_wtl']} | {r['short_mean_makespan']:.3f} | {r['short_paired_improvement_pct']:+.3f}% |")
    lines += ["",f"Selected deployment repair: `{selected['selected']['operator_id']}` / `{selected['selected']['source_hash']}`. Child adopted: {selected['adopted_child']}. Original R* is retained.", ""]
    if not selected['adopted_child']:
        lines += ["No child passed the predeclared full-ALNS quality rule. V3 therefore retains R*: it is structurally identical to V2, and any difference between separately timed repeats is not evidence of cooperative evolution improvement.", ""]
    lines += ["| Method | Mean makespan | Paired improvement vs V1 | Paired improvement vs V2 | W/T/L vs V2 | Mean seconds | Mean iterations |",
        "|---|---:|---:|---:|---|---:|---:|"]
    for r in summary:
        lines.append(f"| {r['method']} | {r['mean_makespan']:.3f} | {r['paired_improvement_vs_V1_pct']:+.3f}% | {r['paired_improvement_vs_V2_pct']:+.3f}% | {r['wtl_vs_V2']} | {r['mean_runtime_seconds']:.3f} | {r['mean_iterations']:.2f} |")
    lines += ["", "Each rate averages the 8 matched instance x seed relative changes (positive is better). Raw runs include full routes, iteration histories, DP calls/misses, generated execution and active-pair statistics. Time stops at iteration boundaries, so actual runtime can exceed the nominal budget.", "",
        "Knowledge reached executable decisions: the first child combines minimum sweep/turn workload with Manhattan center detours and dynamic regret; the second calibrates corner-link proxy increments against partial route costs and a fair-load target. Neither calls DP. Both leave state compatibility to the real evaluator.", "",
        "The returned code mainly changes general geometry/load heuristics. It does not explicitly reconstruct D*'s released edge bundles or model their interaction with retained routes. Online RepairContext has no original-route ownership or D identity; the offline source/evidence influences code generation only. This supports knowledge-to-code execution, not demonstrated pair-specific cooperation.", "",
        "Remaining limitations: min(H,V) ignores compatibility between entry/exit states; independent corner minima can use incompatible corners; clipped travel deltas can discard beneficial reconnections; regret across positions may not express scarcity across robots. These are code-level hypotheses, not established causes. Actual remaining regressions and DP changes are in remaining_failure_cases.json. No post-result repair edits or extra LLM requests were performed.", "",
        "The original request's raw evidence correctly shows a tied bottleneck shrinking from [0,1] to [0], but its category called this a transfer. That category has been corrected in code and annotated in feedback_corrected_annotation.json. The sent prompt/feedback are preserved; this case is not a newly introduced bottleneck. There were no new-bottleneck losses in the parent evidence.", "",
        "Marginal operator and pair action rewards overlap and are not additive causal contributions. Pair-use frequencies must be considered with makespan results. One evolution request and two solver seeds do not establish stable advantage.", "",
        "Reproduce from the repository root with the existing environment and PYTHONPATH=src. Existing stages resume saved artifacts; evolve does not request again when generated_candidates.json exists:", "", "```powershell",
        "$env:PYTHONPATH='src'",
        "foreach ($stage in @('prepare','evolve','evaluate','short','select','smoke','benchmark','analyze')) {",
        "  & G:\\Anaconda\\envs\\mrta_env\\python.exe -m mrta_rect_coverage.experiments.e7_cooperative_evolution --stage $stage",
        "  if ($LASTEXITCODE -ne 0) { throw \"E7 failed at $stage\" }",
        "}", "```", "", "A fresh output directory creates a new exploratory run; time-limited search is not bit-for-bit deterministic. Pause after E7; no C2/C3 work is included."]
    if (output/"runtime_anomaly.json").exists():
        lines += ["", "Runtime anomaly: the first R4_T40_0 / seed 1 / V1 run stalled during bounded import for about 1108 wall seconds (nominal solve budget 40 seconds; actual 1132.624 seconds). A tool wait simultaneously recorded about 1132 seconds despite a 30-second request. It was archived intact in runtime_anomalies, then rerun once with identical source/config/seed solely for timing comparability. No causal OS diagnosis is asserted. Other normal-duration timeout/fallback runs remain in the primary table. See runtime_anomaly.json for both records and the processing rule."]
    (output/"REPORT.md").write_text('\n'.join(lines)+'\n',encoding="utf-8")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    stages={"prepare":prepare,"evolve":evolve,"evaluate":evaluate,"short":short,"select":select,"smoke":smoke,"benchmark":benchmark,"analyze":analyze}
    parser.add_argument("--stage",choices=stages,required=True)
    parser.add_argument("--output",type=Path,default=ROOT/"outputs/e7_cooperative_evolution")
    args=parser.parse_args()
    stages[args.stage](args.output.resolve())


if __name__=="__main__":
    main()
