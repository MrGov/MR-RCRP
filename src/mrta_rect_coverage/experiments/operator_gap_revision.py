"""Bounded real-provider repair lineage on already consumed development states.

This deliberately small driver reuses the paired evaluation and ALNS machinery.
An output directory is single-use; failed requests are charged before invocation.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
from dataclasses import asdict, replace
from pathlib import Path
from statistics import mean
from time import perf_counter
from types import SimpleNamespace

from .operator_portfolio_evolution import (
    ROOT, _evaluate_candidate, _revision_gap_feedback, select_behavioral_shortlist,
)
from ..core.instance_loader import load_instance
from ..heuristics.alns_solver import ALNSConfig, ALNSSolver
from ..heuristics.priced_local_search import run_priced_local_search
from ..llm.operator_evolution.candidate_loader import load_and_validate_candidate
from ..llm.operator_evolution.langchain_provider import LangChainOperatorEvolutionProvider
from ..llm.operator_evolution.protocols import RepairResult
from ..llm.prompts.operator_revision import build_paired_repair_revision_prompt
from ..llm.runtime.client_factory import build_langchain_chat_model
from ..llm.runtime.config import load_from_env


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def digest(path):
    return hashlib.sha256(path.read_text(encoding="utf-8").encode()).hexdigest()


def load_proxy(path, round_id=0):
    return load_and_validate_candidate(
        path=path, operator_type="repair", round_id=round_id,
        source="langchain_openai_compatible", description="real gap revision batch",
        allow_unsafe_candidate_execution=True,
    )


class ManualProxy:
    def __init__(self, solver, name):
        self.solver, self.name = solver, name

    def execute(self, args, timeout_ms):
        partial, removed, _, _ = args
        solution = self.solver.repair_ops[self.name](
            partial, removed, self.solver.solution_evaluator.evaluate_partial(partial))
        return SimpleNamespace(status="success", result=RepairResult(solution))


def evaluate(path, entries, cases, manual=None):
    record = {"id": manual or path.stem, "path": str(path) if path else None,
              "hash": manual or digest(path), "valid": True, "cases": [], "gains": [],
              "raw_repair_gains": [], "runtime_samples": []}
    loaded = None if manual else load_proxy(path)
    if loaded and loaded.callable_obj is None:
        return {**record, "valid": False, "validation": asdict(loaded.validation), "score": -1e12}
    for entry in entries:
        solver = ALNSSolver(load_instance(ROOT / "data/structural_benchmark_v1" / entry["path"]),
                            config=ALNSConfig.enhanced(iterations=1, random_seed=0))
        solver.local_search = lambda solution: run_priced_local_search(
            solution, solver.solution_evaluator, solver.insertion_pricer, max_iterations=1)
        proxy = ManualProxy(solver, manual) if manual else loaded.callable_obj
        subset = [c for c in cases if c["instance_id"] == entry["instance_id"]]
        metrics = _evaluate_candidate(solver, {"proxy": proxy}, subset)
        record["valid"] &= metrics["valid"]
        for key in ("cases", "gains", "raw_repair_gains"):
            record[key].extend(metrics[key])
        record["runtime_samples"].append(metrics["runtime_ms"])
    record["runtime_ms"] = mean(record.pop("runtime_samples"))
    record["score"] = mean(record["gains"]) if record["valid"] else -1e12
    return record


def deploy(paths, entries, config):
    rows = []
    for entry in entries:
        for seed in config["seeds"]:
            started = perf_counter()
            solver = ALNSSolver(load_instance(ROOT / "data/structural_benchmark_v1" / entry["path"]),
                config=ALNSConfig.enhanced(iterations=None,
                    max_runtime_seconds=config["deployment_seconds"], random_seed=seed,
                    segment_length=4, priced_local_search=True, operator_minimum_uses=1))
            names = {}
            for path in paths:
                name = "generated_" + digest(path)[:12]
                names[name] = digest(path)
                solver.register_development_repair(load_proxy(path).callable_obj, name=name)
            weights = {"destroy": dict(solver.destroy_weights), "repair": dict(solver.repair_weights)}
            result = solver.solve()
            stats = {}
            for group in ("destroy", "repair"):
                stats[group] = {
                    name: {"calls": rec.uses, "shared_reward": rec.score,
                        "accepted": sum(r[group] == name and r["accepted"] for r in result.iteration_history),
                        "improved_current": sum(r[group] == name and r["candidate_delta"] < -1e-9 for r in result.iteration_history),
                        "improved_best": sum(r[group] == name and r["score_raw"] >= 8 for r in result.iteration_history),
                        "seconds": result.operator_time_stats[group][name][0]}
                    for name, rec in result.operator_usage_stats[group].items()}
            rows.append({"instance_id": entry["instance_id"], "seed": seed,
                "makespan": result.best_evaluation.makespan, "runtime_seconds": result.runtime_seconds,
                "total_wall_seconds": perf_counter()-started, "iterations": result.iterations_completed,
                "valid": solver._is_valid_full_solution(result.best_solution),
                "fallback_events": result.fallback_events, "operator_stats": stats,
                "generated_members": names, "initial_weights": weights, "config": asdict(solver.config),
                "history": result.iteration_history})
    return rows


def eligible(rows):
    return bool(rows) and all(r["valid"] and not r["fallback_events"] and all(
        r["operator_stats"]["repair"][name]["calls"] > 0 for name in r["generated_members"]
    ) for r in rows)


def request(provider, prompt, folder, ledger, limit, round_id, kind):
    if len(ledger) >= limit:
        raise RuntimeError("hard request budget exhausted")
    folder.mkdir()
    (folder / "prompt.txt").write_text(prompt, encoding="utf-8")
    row = {"request": len(ledger)+1, "round": round_id, "kind": kind,
           "status": "started", "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()}
    ledger.append(row)
    save(folder.parent / "requests.json", ledger)
    provider._raw_dir = folder
    started = perf_counter()
    try:
        drafts = provider.revise_operator_candidates(prompt, {}, n=1, operator_type="repair", round_id=round_id)
        row.update(status="success" if drafts else "parse_failure", metadata=dict(provider.last_call_metadata))
    except Exception as exc:
        # Do not persist credentials/endpoint potentially embedded in an SDK exception.
        row.update(status="provider_failure", error_type=type(exc).__name__,
                   status_code=getattr(exc, "status_code", None))
        drafts = []
    row["wall_seconds"] = perf_counter()-started
    save(folder.parent / "requests.json", ledger)
    return drafts


def run(config_path):
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if not (1 <= config["max_requests"] <= 16 and 2 <= config["max_rounds"] <= 3
            and config["candidates_per_round"] == 1 and config["max_repairs_per_candidate"] <= 1):
        raise ValueError("batch exceeds authorization or this single-lineage driver")
    out = ROOT / config["output_dir"]
    out.mkdir(parents=True, exist_ok=False)
    save(out / "config.json", config)
    started = perf_counter()
    replay = json.loads((ROOT / config["replay"]).read_text(encoding="utf-8"))
    cases = replay["cases"]
    manifest = json.loads((ROOT / "data/structural_benchmark_v1/manifest.json").read_text(encoding="utf-8"))
    all_entries = manifest["entries"]
    entries = [e for e in all_entries if e["instance_id"] in {c["instance_id"] for c in cases}]
    if len(entries) != 2 or any(e["split"] != "development" for e in entries):
        raise ValueError("expected exactly two consumed development instances")
    for e in entries:
        if hashlib.sha256((ROOT / "data/structural_benchmark_v1" / e["path"]).read_bytes()).hexdigest() != e["sha256"]:
            raise ValueError("manifest mismatch")
    parent_path = ROOT / next(c["path"] for c in replay["candidates"] if c["hash"] == replay["revision_parent_hash"])
    anchor = evaluate(parent_path, entries, cases)
    manuals = [evaluate(None, entries, cases, manual=name) for name in
               ("greedy_insertion", "regret_k_insertion", "bottleneck_balancing_insertion")]
    artifact = {"config": config, "cases": cases, "anchor": anchor, "manuals": manuals,
                "rounds": [], "requests": [], "check_status": "No unused independent development instance established; no independent validation claimed.",
                "selection_rule": "Feasible and <=500ms; paired novelty >=2 and not worse on every state permits addition trial. Retain only if mean short-ALNS makespan improves by >=0.001 with no fallback and every generated member called. Manual-only eligible. Two fixed seeds; development evidence only.",
                "policy": "spatial_sort; one-pass priced local search; unchanged enhanced ALNS acceptance; minimum uses=1 then independent adaptive roulette; initial weights=1; shared pair rewards 8/3/1; segment=4"}
    groups = {"manual": deploy([], entries, config), "current": deploy([parent_path], entries, config)}
    artifact["baseline_deployment"] = groups
    save(out / "results.json", artifact)
    runtime = replace(load_from_env(), max_retries=0, temperature=None, max_output_tokens=config["max_output_tokens"])
    if runtime.provider != "langchain_openai_compatible":
        raise ValueError("configured provider is not the existing real compatible provider")
    chat = build_langchain_chat_model(runtime)
    if chat.temperature is not None or chat.max_retries != 0:
        raise ValueError("automatic retry guard failed")
    provider = LangChainOperatorEvolutionProvider(chat_model=chat, requested_temperature=None)
    artifact["provider"] = {"name": runtime.provider, "model": runtime.model, "max_retries": 0,
                            "temperature": None, "max_output_tokens": runtime.max_output_tokens}
    current_paths = [parent_path]
    current_metrics = anchor
    best_name = min((g for g in groups if eligible(groups[g])), key=lambda g: mean(r["makespan"] for r in groups[g]))
    best_paths = [] if best_name == "manual" else [parent_path]
    best_mean = mean(r["makespan"] for r in groups[best_name])
    for generation in range(1, config["max_rounds"]+1):
        feedback = _revision_gap_feedback([current_metrics], [current_metrics["hash"]], cases)
        feedback.update(manual_paired_outcomes=manuals, parent_paired_outcomes=current_metrics,
            current_composition=[str(p.relative_to(ROOT)) for p in current_paths],
            target="Improve latent non-bottleneck route insertion ordering under makespan ties; exploit inexpensive entry/exit parity compatibility. No DP implementation. Preserve useful parent behavior.")
        if artifact["rounds"]:
            previous = artifact["rounds"][-1]
            feedback["actual_previous_deployment"] = {k: previous.get(k) for k in ("admission", "deployment_mean", "parent_delta", "retained")}
            feedback["revision_instruction"] = "Revise the actual parent behavior using its paired losses and deployment result. If gains vanished, reduce unnecessary route perturbations/cost. Do not repeat identical behavior."
        folder = out / f"request_{len(artifact['requests'])+1:02d}"
        prompt = build_paired_repair_revision_prompt(parent={"operator_id": parent_path.stem,
            "source_path": str(parent_path), "source_hash": digest(parent_path)}, feedback=feedback, n=1)
        drafts = request(provider, prompt, folder, artifact["requests"], config["max_requests"], generation, "algorithm_revision")
        if not drafts:
            artifact["stop_reason"] = artifact["requests"][-1]["status"]
            break
        path = folder / "candidate.py"
        path.write_text(drafts[0].code, encoding="utf-8")
        save(folder / "draft.json", asdict(drafts[0]))
        metrics = evaluate(path, entries, cases)
        # At most one repair request per original invalid candidate, separately labelled.
        if not metrics["valid"] and config["max_repairs_per_candidate"]:
            save(folder / "failed_evaluation.json", metrics)
            fix_prompt = prompt + "\nEngineering repair ONLY, not algorithm progress. Failed source:\n" + drafts[0].code + "\nExecution evidence:\n" + json.dumps(metrics)
            folder = out / f"request_{len(artifact['requests'])+1:02d}"
            fixes = request(provider, fix_prompt, folder, artifact["requests"], config["max_requests"], generation, "engineering_fix")
            if fixes:
                path = folder / "candidate.py"
                path.write_text(fixes[0].code, encoding="utf-8")
                save(folder / "draft.json", asdict(fixes[0]))
                metrics = evaluate(path, entries, cases)
        diff = ''.join(difflib.unified_diff(parent_path.read_text(encoding="utf-8").splitlines(True),
                        path.read_text(encoding="utf-8").splitlines(True), fromfile=str(parent_path), tofile=str(path)))
        (folder / "parent.diff").write_text(diff, encoding="utf-8")
        row = {"generation": generation, "parent_hash": digest(parent_path), "child_hash": digest(path),
               "evaluation": metrics, "retained": False}
        shortlist = select_behavioral_shortlist([anchor, metrics], anchor_hash=anchor["hash"], capacity=1,
            min_behavior_delta=config["min_behavior_delta"], max_runtime_ms=config["runtime_cap_ms"])
        row["parent_delta"] = [a-b for a,b in zip(metrics["gains"], current_metrics["gains"])] if metrics["valid"] else []
        row["admission"] = "paired_behavior_trial" if shortlist else "paired_rejection"
        if shortlist:
            trial_paths = [current_paths[0], path]
            row["deployment"] = deploy(trial_paths, entries, config)
            row["deployment_mean"] = mean(r["makespan"] for r in row["deployment"])
            if eligible(row["deployment"]) and row["deployment_mean"] < best_mean-config["minimum_gain"]:
                best_paths, best_mean = trial_paths, row["deployment_mean"]
                row["retained"] = True
        artifact["rounds"].append(row)
        save(out / "results.json", artifact)
        print(json.dumps({"generation": generation, "valid": metrics["valid"], "gains": metrics["gains"],
                          "admission": row["admission"], "deployment_mean": row.get("deployment_mean"), "retained": row["retained"]}), flush=True)
        if not metrics["valid"]:
            artifact["stop_reason"] = "candidate invalid after at most one engineering repair"
            break
        parent_path, current_metrics = path, metrics
    artifact.setdefault("stop_reason", "predeclared two-generation batch completed; no automatic additional generation")
    artifact["final_generated_members"] = [{"path": str(p.relative_to(ROOT)), "hash": digest(p)} for p in best_paths]
    artifact["final_development_mean"] = best_mean
    artifact["wall_seconds"] = perf_counter()-started
    artifact["token_usage"] = {key: sum((r.get("metadata", {}).get(key) or 0) for r in artifact["requests"])
                              for key in ("prompt_tokens", "completion_tokens", "total_tokens")}
    artifact["cost_usd"] = None
    save(out / "results.json", artifact)
    print(json.dumps({"stop": artifact["stop_reason"], "requests": len(artifact["requests"]), "tokens": artifact["token_usage"], "members": artifact["final_generated_members"]}), flush=True)
    return artifact


def deploy_selected(result_path, output_path):
    """Load the frozen batch choice into ALNS without any provider request.

    This is a consumed-development replay, never an independent validation.
    """
    if output_path.exists():
        raise FileExistsError("preserving existing deployment output")
    artifact = json.loads(result_path.read_text(encoding="utf-8"))
    paths = []
    for member in artifact["final_generated_members"]:
        path = ROOT / member["path"]
        if digest(path) != member["hash"]:
            raise ValueError("frozen member source hash mismatch")
        paths.append(path)
    manifest = json.loads((ROOT / "data/structural_benchmark_v1/manifest.json").read_text(encoding="utf-8"))
    ids = {c["instance_id"] for c in artifact["cases"]}
    entries = [e for e in manifest["entries"] if e["instance_id"] in ids]
    if len(entries) != len(ids) or not entries or any(e["split"] != "development" for e in entries):
        raise ValueError("deployment replay restricted to recorded development identities")
    for entry in entries:
        path = ROOT / "data/structural_benchmark_v1" / entry["path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError("development manifest hash mismatch")
    rows = deploy(paths, entries, artifact["config"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    save(output_path, {"source_result": str(result_path), "role": "consumed_development_deployment_replay",
                      "llm_calls": 0, "selection_changed": False, "deployment": rows})
    print(json.dumps({"llm_calls": 0, "generated_members": len(paths), "eligible": eligible(rows),
                      "makespans": [r["makespan"] for r in rows]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/operator_gap_revision.json")
    parser.add_argument("--deploy-result", type=Path)
    parser.add_argument("--deployment-output", type=Path)
    args = parser.parse_args()
    if args.deploy_result:
        if not args.deployment_output:
            parser.error("--deploy-result requires a fresh --deployment-output")
        deploy_selected(args.deploy_result, args.deployment_output)
    else:
        run(args.config)
