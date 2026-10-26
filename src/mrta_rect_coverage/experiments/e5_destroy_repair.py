"""Small real E5 destroy evolution and additive B1 deployment experiment."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import difflib
import hashlib
import json
from pathlib import Path
import random
from statistics import mean
import subprocess
from time import perf_counter

from .e3_alns import ROOT, INSTANCES, SEEDS, write_json
from .e2_c1_pilot import _write_csv
from .e1_real_llm_pilot import (compute_exact_dp_behavior, build_destroy_feedback,
                               destroy_revision_prompt, _invalid_row)
from ..core.instance_loader import load_instance
from ..heuristics.alns_solver import ALNSConfig, ALNSSolver
from ..llm.operator_evolution.candidate_loader import load_and_validate_candidate, persist_operator_drafts
from ..llm.operator_evolution.evaluator import build_destroy_benchmark_cases, evaluate_destroy_candidates
from ..llm.prompts.operator_generation import build_destroy_generation_prompt

METHODS = ("B1", "B1+R", "B1+D", "B1+D+R")
D_NAME, R_NAME = "e5_llm_destroy", "e5_frozen_repair"


def digest(path):
    return hashlib.sha256(Path(path).read_text(encoding="utf-8").encode()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_choice(choice, kind):
    if digest(choice["source_path"]) != choice["source_hash"]:
        raise ValueError(f"{kind} source hash changed")
    loaded = load_and_validate_candidate(path=Path(choice["source_path"]), operator_type=kind,
        round_id=choice["generation"], source="langchain_openai_compatible",
        description="E5 development operator", allow_unsafe_candidate_execution=True)
    if loaded.callable_obj is None or loaded.validation.code_hash != choice["source_hash"]:
        raise ValueError(f"{kind} failed candidate loader: {loaded.validation}")
    return loaded


def setup(output):
    output.mkdir(parents=True, exist_ok=True)
    target = output / "experiment_config.json"
    if not target.exists():
        selected = read(ROOT / "outputs/e2r_c1_pilot/selected_operators.json")["L2"]
        load_choice(selected, "repair")
        source = Path(selected["source_path"]).read_text(encoding="utf-8")
        path = (output / "frozen_repair.py").resolve()
        path.write_text(source, encoding="utf-8")
        repair = dict(selected, source_path=str(path), original_source_path=selected["source_path"],
                      selection_reason="E2-R L2 selected earlier; E4-A B1 compatibility 5/2/1 vs B1; fixed before E5 destroy generation")
        frozen = [ROOT / "src/mrta_rect_coverage/core/dp_evaluator.py",
                  ROOT / "src/mrta_rect_coverage/heuristics/alns_solver.py",
                  ROOT / "configs/e3_b1.yaml", Path(selected["source_path"]), path]
        frozen += [ROOT / "data" / f"{n}.txt" for n in INSTANCES]
        git = "C:/Program Files/Git/cmd/git.exe"
        head = subprocess.check_output([git, "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        status = subprocess.check_output([git, "status", "--short"], cwd=ROOT, text=True)
        write_json(target, dict(phase="E5", git_head=head, working_tree_after_minimal_implementation=status,
            repair=repair, instances=INSTANCES, seeds=SEEDS, constructor="spatial_sort",
            interpretation="development/exploratory; four additive operator-pool configurations; no confirmatory claim",
            B1=asdict(ALNSConfig.enhanced()), alpha=1.0, rounds=2, candidates_per_round=2,
            candidate_timeout_ms=2000, evaluation_trials_per_candidate=len(INSTANCES)*len(SEEDS),
            reference_destroy="existing ALNSSolver._random_destroy with independent Random(seed)",
            remove_count="max(1,task_count//4), identical reference/candidate; fixed repair receives a fresh Random(seed)",
            selection="best fully feasible candidate across parents and children by paired mean final makespan improvement; frozen before ALNS comparison",
            final_test_accessed=False, frozen_hashes={str(p):digest(p) for p in frozen},
            commands=["python -m mrta_rect_coverage.experiments.e5_destroy_repair --stage " + s
                      for s in ("evolve", "smoke", "benchmark", "analyze")]))
    config = read(target)
    for path, expected in config["frozen_hashes"].items():
        if digest(path) != expected:
            raise ValueError(f"frozen experiment input changed: {path}")
    return config


def reference_destroy(solution, evaluation, count, rng):
    # Reuse the manual operator directly; it needs only self.rng and _remove_tasks.
    from types import SimpleNamespace, MethodType
    owner = SimpleNamespace(rng=rng)
    owner._remove_tasks = MethodType(ALNSSolver._remove_tasks, owner)
    return ALNSSolver._random_destroy(owner, solution, evaluation, count)


def evolve(output):
    config = setup(output)
    repair = load_choice(config["repair"], "repair")
    cases = build_destroy_benchmark_cases([ROOT / "data" / f"{n}.txt" for n in config["instances"]],
                                         constructor=config["constructor"])
    all_rows = []
    for generation in range(config["rounds"]):
        branch = output / f"round_{generation:03d}"
        branch.mkdir(parents=True, exist_ok=True)
        parent = max((r for r in all_rows if r.get("feasible_count")==len(cases)*len(SEEDS)),
                     key=lambda r:r["avg_relative_improvement"], default=None)
        if generation and parent is None:
            raise RuntimeError("no fully feasible destroy parent; saved work retained")
        if generation:
            feedback = build_destroy_feedback(all_rows, parent=parent)
            write_json(branch / "feedback.json", feedback)
            prompt = destroy_revision_prompt(parent, feedback, n=2)
            write_json(branch / "parent.json", parent)
            (branch / "parent.py").write_text(Path(parent["source_path"]).read_text(encoding="utf-8"), encoding="utf-8")
        else:
            prompt = build_destroy_generation_prompt(round_id=0, n=2)
            feedback = None
        prompt += ("\nE5 evaluation: identical complete parent and remove_count; candidate destroy + fixed repair "
            "versus manual random destroy + the SAME frozen repair. Final feasible Exact-DP makespan is the objective. "
            "Design original task-removal decisions to open bottleneck relief, assignment changes and search opportunities; "
            "do not copy a manual destroy. No evaluator or state chain is exposed. Per-robot costs are full route times. "
            "Instance.depot is a coordinate tuple (x,y), accessed with [0]/[1]; task widths/heights and sweep/travel parameters are available. "
            "Processing H=ceil(height/sweep_width)*width/sweep_speed+(ceil(height/sweep_width)-1)*turning_time; "
            "V swaps width/height. Manhattan/travel_speed is movement time. These are heuristic hints, not exact route insertion values.\n"
            f"Frozen Repair hash: {config['repair']['source_hash']}\nFrozen Repair source (do not modify):\n```python\n"
            + Path(config["repair"]["source_path"]).read_text(encoding="utf-8") + "\n```\n")
        generated = branch / "generated_candidates.json"
        if not generated.exists():
            (branch / "prompt.txt").write_text(prompt, encoding="utf-8")
            from ..llm.operator_evolution.provider_factory import build_provider
            from ..llm.runtime.config import load_from_env
            cfg = load_from_env()
            write_json(output / "provider_config.json", {k:v for k,v in asdict(cfg).items() if k != "api_key"})
            provider = build_provider("langchain_openai_compatible", raw_response_dir=branch / "raw_responses")
            started = perf_counter()
            try:
                drafts = (provider.generate_operator_candidates(prompt, 2, "destroy", generation) if not generation
                          else provider.revise_operator_candidates(prompt, feedback, 2, "destroy", generation))
            except Exception as exc:
                write_json(branch / "provider_failure.json", dict(error=f"{type(exc).__name__}: {exc}", wall_seconds=perf_counter()-started))
                raise
            paths = persist_operator_drafts(branch / "generated", list(drafts)[:2])
            write_json(branch / "provider_call.json", dict(metadata=provider.last_call_metadata,
                wall_seconds=perf_counter()-started, requested_cap=2, parsed_count=len(drafts)))
            write_json(generated, [dict(operator_id=d.operator_id, generation=generation,
                source_path=str(p.resolve()), source_hash=digest(p), description=d.description,
                parent_source_hash=parent["source_hash"] if parent else None) for p,d in zip(paths,drafts)])
            print(f"Round {generation}: saved {len(paths)} real destroy candidates", flush=True)
        for draft in read(generated):
            result_path = branch / f"{draft['operator_id']}_evaluation.json"
            if result_path.exists():
                row = read(result_path)
            else:
                loaded = load_and_validate_candidate(path=Path(draft["source_path"]), operator_type="destroy",
                    round_id=generation, source="langchain_openai_compatible", description=draft["description"],
                    allow_unsafe_candidate_execution=True)
                write_json(branch / f"{draft['operator_id']}_validation.json", asdict(loaded.validation))
                if loaded.validation.code_hash != draft["source_hash"]:
                    raise ValueError("candidate hash changed")
                row = (evaluate_destroy_candidates([loaded], cases, seeds=SEEDS, timeout_ms=2000,
                    fixed_repair=repair, reference_destroy=reference_destroy,
                    behavior_callback=compute_exact_dp_behavior)[0] if loaded.callable_obj is not None
                    else _invalid_row(loaded.validation))
                row.update(draft)
                write_json(result_path, row)
            all_rows.append(row)
            print(f"Round {generation} {draft['operator_id']}: feasible {row.get('feasible_count',0)}/{row.get('executed_count',0)}, paired improvement {100*row.get('avg_relative_improvement',0):+.4f}%", flush=True)
        write_json(output / "candidate_metrics.json", all_rows)
        elite = sorted((r for r in all_rows if r.get("feasible_count")==len(cases)*len(SEEDS)),
                       key=lambda r:r["avg_relative_improvement"], reverse=True)
        write_json(output / "elite_archive.json", elite)
    if not elite:
        raise RuntimeError("no qualified destroy candidate; no substitution")
    selected = {k:elite[0][k] for k in ("source_path","source_hash","operator_id","generation","parent_source_hash","avg_relative_improvement")}
    write_json(output / "selected_operators.json", dict(destroy=selected, repair=config["repair"]))


def make_solver(instance, seed, budget, selected, *, use_d, use_r, iterations=None):
    solver = ALNSSolver(instance, config=ALNSConfig.enhanced(iterations=iterations,
        max_runtime_seconds=budget, random_seed=seed))
    if use_d:
        solver.register_development_destroy(load_choice(selected["destroy"], "destroy").callable_obj, name=D_NAME)
    if use_r:
        solver.register_development_repair(load_choice(selected["repair"], "repair").callable_obj, name=R_NAME)
    return solver


def smoke(output):
    setup(output)
    selected=read(output / "selected_operators.json")
    solver=make_solver(load_instance(ROOT / "data/R2_T10_0.txt"),0,None,selected,use_d=True,use_r=True,iterations=2)
    # Force joint use only for integration smoke; comparative runs retain all manual operators.
    solver._select_operators=lambda ctx:(D_NAME,R_NAME,"joint_smoke")
    result=solver.solve()
    verified=solver.solution_evaluator.evaluate(result.best_solution)
    write_json(output / "joint_smoke.json", dict(feasible=True,makespan=verified.makespan,
        fallback_events=result.fallback_events,history=result.iteration_history))
    if result.fallback_events or not all(h["llm_operator_success"] for h in result.iteration_history):
        raise RuntimeError("joint destroy-repair integration failed; see saved smoke")
    print("Joint bounded destroy + frozen repair smoke passed",flush=True)


def benchmark(output):
    config=setup(output); selected=read(output / "selected_operators.json")
    if not (output / "joint_smoke.json").exists():
        raise RuntimeError("run joint smoke before comparison")
    rows=[]
    for name in config["instances"]:
        instance=load_instance(ROOT / "data" / f"{name}.txt")
        for seed in SEEDS:
            order=METHODS if seed==0 else tuple(reversed(METHODS))
            for method in order:
                target=output / "runs" / f"{name}_{method}_s{seed}.json"
                if target.exists():
                    saved=read(target)
                    if saved["selected"]!=selected or saved["config"]!=asdict(ALNSConfig.enhanced(iterations=None,max_runtime_seconds=instance.task_count,random_seed=seed)):
                        raise ValueError("incompatible saved run")
                    rows.append(saved["result"]); continue
                record=dict(method=method,instance=name,seed=seed,tasks=instance.task_count,robots=instance.robot_count,
                            budget_seconds=float(instance.task_count),feasible=False,status="error")
                started=perf_counter()
                try:
                    solver=make_solver(instance,seed,float(instance.task_count),selected,
                                       use_d=method in ("B1+D","B1+D+R"),use_r=method in ("B1+R","B1+D+R"))
                    setup_seconds=perf_counter()-started
                    result=solver.solve()
                    verified=solver.solution_evaluator.evaluate(result.best_solution)
                    assert abs(verified.makespan-result.best_evaluation.makespan)<1e-9
                    history=result.iteration_history
                    uses_d=sum(h["destroy"]==D_NAME for h in history)
                    uses_r=sum(h["repair"]==R_NAME for h in history)
                    record.update(feasible=True,status="fallback" if result.fallback_events else "ok",
                        makespan=verified.makespan,initial_makespan=result.initial_makespan,
                        runtime_seconds=result.runtime_seconds,setup_seconds=setup_seconds,
                        iterations=result.iterations_completed,route_dp_calls=result.route_dp_calls,
                        route_dp_cache_misses=result.route_dp_cache_misses,
                        llm_destroy_uses=uses_d,llm_repair_uses=uses_r,
                        joint_uses=sum(h["destroy"]==D_NAME and h["repair"]==R_NAME for h in history),
                        successful_generated_iterations=sum(h["llm_operator_success"] for h in history),
                        fallback_count=len(result.fallback_events),destroy_pool_size=len(solver.destroy_ops),
                        repair_pool_size=len(solver.repair_ops),overrun_seconds=max(0,result.runtime_seconds-instance.task_count))
                    write_json(target,dict(result=record,selected=selected,config=asdict(solver.config),
                        operator_pools=dict(destroy=list(solver.destroy_ops),repair=list(solver.repair_ops)),
                        initial_routes=solver.initial_solution.routes,best_routes=result.best_solution.routes,
                        per_robot_costs=verified.per_robot_costs,history=history,fallback_events=result.fallback_events))
                except Exception as exc:
                    record.update(error=f"{type(exc).__name__}: {exc}",wall_seconds=perf_counter()-started)
                    write_json(target.with_suffix(".error.json"),record)
                rows.append(record)
                write_json(output / "results.json",rows); _write_csv(output / "results.csv",rows)
                print(json.dumps(record),flush=True)
    write_json(output / "results.json",rows); _write_csv(output / "results.csv",rows)


def analyze(output):
    config=setup(output); rows=read(output / "results.json")
    assert len(rows)==len(config["instances"])*len(SEEDS)*len(METHODS)
    reference={(r["instance"],r["seed"]):r for r in rows if r["method"]=="B1" and r["feasible"]}
    summary=[]
    for method in METHODS:
        group=[r for r in rows if r["method"]==method and r["feasible"]]
        pairs=[(r,reference[(r["instance"],r["seed"])]) for r in group if (r["instance"],r["seed"]) in reference]
        summary.append(dict(method=method,feasible_runs=len(group),
            **{f"mean_{key}":mean(r[key] for r in group) if group else None for key in
               ("makespan","runtime_seconds","iterations","route_dp_calls","llm_destroy_uses","llm_repair_uses","joint_uses")},
            paired_improvement_vs_b1_pct=mean(100*(1-a["makespan"]/b["makespan"]) for a,b in pairs) if pairs else None,
            wins=sum(a["makespan"]<b["makespan"]-1e-9 for a,b in pairs),
            ties=sum(abs(a["makespan"]-b["makespan"])<1e-9 for a,b in pairs),
            losses=sum(a["makespan"]>b["makespan"]+1e-9 for a,b in pairs)))
    for name in config["instances"]:
        records=[read(output / "runs" / f"{name}_{m}_s{s}.json") for m in METHODS for s in SEEDS
                 if (output / "runs" / f"{name}_{m}_s{s}.json").exists()]
        assert all(r["initial_routes"]==records[0]["initial_routes"] for r in records)
        verifier=ALNSSolver(load_instance(ROOT / "data" / f"{name}.txt"))
        from ..core.models import MultiRobotSolution
        for r in records:
            assert len(r["history"])==r["result"]["iterations"]
            result=r["result"]
            measured=verifier.solution_evaluator.evaluate(MultiRobotSolution(r["best_routes"]))
            assert abs(measured.makespan-result["makespan"])<1e-9
            assert r["config"]==asdict(ALNSConfig.enhanced(iterations=None,max_runtime_seconds=result["tasks"],random_seed=result["seed"]))
            assert sum(h["destroy"]==D_NAME for h in r["history"])==result["llm_destroy_uses"]
            assert sum(h["repair"]==R_NAME for h in r["history"])==result["llm_repair_uses"]
            assert sum(h["destroy"]==D_NAME and h["repair"]==R_NAME for h in r["history"])==result["joint_uses"]
            assert all(b["best_makespan"]<=a["best_makespan"]+1e-9 for a,b in zip(r["history"],r["history"][1:]))
    write_json(output / "verification_summary.json",dict(recorded_runs=len(rows),
        feasible_runs=sum(r["feasible"] for r in rows),fallback_count=sum(r.get("fallback_count",0) for r in rows),
        error_runs=[r for r in rows if not r["feasible"]],
        independent_complete_solution_evaluation=True,matched_starts_and_configs=True,
        usage_and_joint_counts_checked=True,global_best_monotonic=True,
        frozen_hashes_checked=True,post_result_operator_reselection=False,
        interruption_archive="interrupted_R8_T80_0_seed1" if (output / "interrupted_R8_T80_0_seed1").exists() else None))
    write_json(output / "summary.json",summary); _write_csv(output / "summary.csv",summary)
    per_instance=[]
    for name in config["instances"]:
        for method in METHODS:
            group=[r for r in rows if r["instance"]==name and r["method"]==method and r["feasible"]]
            if group:
                per_instance.append(dict(instance=name,method=method,
                    **{f"mean_{k}":mean(r[k] for r in group) for k in
                       ("makespan","runtime_seconds","iterations","route_dp_calls","llm_destroy_uses","llm_repair_uses","joint_uses")}))
    _write_csv(output / "per_instance_results.csv",per_instance)
    metrics=read(output / "candidate_metrics.json")
    selected=read(output / "selected_operators.json")
    candidate_table=[]; trials=[]
    for candidate in metrics:
        assert digest(candidate["source_path"])==candidate["source_hash"]
        candidate_table.append({k:candidate.get(k) for k in (
            "operator_id","source_hash","parent_source_hash","generation","validation_status",
            "feasible_count","executed_count","avg_relative_improvement","avg_runtime_ms")})
        trials.extend(dict(t,operator_id=candidate["operator_id"],source_hash=candidate["source_hash"],
                           generation=candidate["generation"]) for t in candidate.get("trials",[]))
    _write_csv(output / "evolution_results.csv",candidate_table)
    write_json(output / "destroy_trials.json",trials)
    calls=[read(output / f"round_{g:03d}/provider_call.json") for g in range(2)]
    write_json(output / "provider_summary.json",dict(successful_requests=len(calls),
        requested_candidate_slots=4,parsed_candidates=sum(c["parsed_count"] for c in calls),
        total_tokens=sum(c["metadata"]["total_tokens"] for c in calls),
        wall_seconds=sum(c["wall_seconds"] for c in calls),estimated_cost_usd=None,rounds=calls))
    write_json(output / "lineage.json",dict(selected=selected,elite_hashes=[r["source_hash"] for r in read(output / "elite_archive.json")],
        candidates=[{k:r.get(k) for k in ("source_hash","source_path","parent_source_hash","generation",
                    "original_source_hash","original_source_path","interface_correction")} for r in metrics],
        raw_round0=read(output / "round_000/original_generated_candidates.json") if (output / "round_000/original_generated_candidates.json").exists() else [],
        selection=config["selection"]))
    parent_source=(output / "round_001/parent.py").read_text(encoding="utf-8")
    for child in [r for r in metrics if r["generation"]==1]:
        diff="".join(difflib.unified_diff(parent_source.splitlines(True),Path(child["source_path"]).read_text(encoding="utf-8").splitlines(True),fromfile="actual_parent",tofile=child["operator_id"]))
        (output / f"{child['operator_id']}_revision.diff").write_text(diff,encoding="utf-8")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,2,figsize=(11,7),constrained_layout=True)
    for name,ax in zip(config["instances"],axes.flat):
        for method,color in zip(METHODS,("#264653","#2A9D8F","#E9C46A","#E76F51")):
            for seed in SEEDS:
                path=output / "runs" / f"{name}_{method}_s{seed}.json"
                if not path.exists(): continue
                run=read(path); h=run["history"]; r=run["result"]
                ax.step([0]+[v["elapsed_seconds"] for v in h]+[r["runtime_seconds"]],
                    [r["initial_makespan"]]+[v["best_makespan"] for v in h]+[r["makespan"]],
                    where="post",color=color,linestyle="-" if seed==0 else "--",label=f"{method}, seed {seed}")
        ax.set(title=name,xlabel="Solve time (s)",ylabel="Best makespan"); ax.grid(alpha=.2)
    axes.flat[0].legend(fontsize=7)
    fig.savefig(output / "convergence.png",dpi=180);fig.savefig(output / "convergence.pdf");plt.close(fig)
    print(json.dumps(summary,indent=2),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage",required=True,choices=("evolve","smoke","benchmark","analyze"))
    parser.add_argument("--output",type=Path,default=ROOT / "outputs/e5_llm_destroy_repair")
    args=parser.parse_args()
    {"evolve":evolve,"smoke":smoke,"benchmark":benchmark,"analyze":analyze}[args.stage](args.output.resolve())


if __name__=="__main__":
    main()
