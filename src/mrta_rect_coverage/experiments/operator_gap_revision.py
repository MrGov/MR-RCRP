"""Bounded real-provider repair lineage on already consumed development states.

This deliberately small driver reuses the paired evaluation and ALNS machinery.
An output directory is single-use; failed requests are charged before invocation.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
from contextlib import ExitStack, contextmanager
from dataclasses import asdict, replace
from pathlib import Path
from statistics import mean
from time import perf_counter
from types import SimpleNamespace

from .operator_portfolio_evolution import (
    ROOT, _evaluate_candidate, select_behavioral_shortlist,
)
from ..core.instance_loader import load_instance
from ..core.models import MultiRobotSolution
from ..heuristics.alns_solver import ALNSConfig, ALNSSolver
from ..heuristics.priced_local_search import run_priced_local_search
from ..llm.operator_evolution.candidate_loader import load_and_validate_candidate
from ..llm.operator_evolution.candidate_execution import CandidateProxy
from ..llm.operator_evolution.persistent_candidate_execution import PersistentCandidateProxy
from ..llm.operator_evolution.langchain_provider import LangChainOperatorEvolutionProvider
from ..llm.operator_evolution.protocols import RepairResult
from ..llm.prompts.operator_revision import build_compact_gap_revision_prompt
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


class MeasuredRepairProxy(CandidateProxy):
    """One reviewed executor with bounded output validation and call accounting."""

    def __init__(self, backend, validation_seconds):
        super().__init__(backend.path, backend.operator_type, backend.expected_code_hash,
                         backend.timeout_ms, backend.max_output_chars, backend.import_timeout_s)
        self.backend = backend
        self.validation_seconds = validation_seconds
        self.samples = []
        self.closed = False

    def close(self):
        if isinstance(self.backend, PersistentCandidateProxy):
            self.backend.close()
        self.closed = True

    def execute(self, args, *, timeout_ms):
        if self.closed:
            raise RuntimeError("executor already closed")
        started = perf_counter()
        try:
            result = self.backend.execute(args, timeout_ms=timeout_ms)
            if result.status == "success":
                payload = result.result
                instance = args[2].instance
                valid = isinstance(payload, RepairResult) and isinstance(payload.solution, MultiRobotSolution)
                if valid:
                    routes = payload.solution.routes
                    try:
                        valid = (len(routes) == instance.robot_count and
                                 sorted(t for route in routes for t in route) == sorted(t.task_id for t in instance.tasks))
                    except (TypeError, AttributeError):
                        valid = False
                if not valid:
                    result = replace(result, status="invalid_solution", result=None,
                                     error_message="repair return contract/exactly-once coverage failed")
            if result.status != "success" and isinstance(self.backend, PersistentCandidateProxy):
                self.backend.close()
            self.samples.append({"status": result.status, "wall_ms": (perf_counter()-started)*1000,
                                 "startup_ms": result.startup_ms,
                                 "validation_import_ms": result.validation_import_ms,
                                 "execution_ipc_ms": result.runtime_ms})
            return result
        except BaseException:
            self.close()
            raise

    def statistics(self):
        return {"validation_and_smoke_seconds": self.validation_seconds, "calls": len(self.samples),
                "first_call_ms": self.samples[0]["wall_ms"] if self.samples else None,
                "subsequent_mean_ms": mean(s["wall_ms"] for s in self.samples[1:]) if len(self.samples)>1 else None,
                "startup_ms": sum(s["startup_ms"] for s in self.samples),
                "process_starts": self.backend.process_starts if isinstance(self.backend, PersistentCandidateProxy) else len(self.samples),
                "closed": self.closed, "samples": self.samples}


@contextmanager
def managed_executor(path, executor="original", *, reviewed_hashes=()):
    """Reuse the E6 finally/close pattern; never execute candidates in the parent."""
    if executor not in {"original", "warm"}:
        raise ValueError("unknown executor")
    if executor == "warm" and digest(path) not in reviewed_hashes:
        raise ValueError("warm execution requires explicit source-hash review")
    started = perf_counter()
    loaded = load_proxy(path)
    if loaded.callable_obj is None:
        raise ValueError(loaded.validation.error_message or "candidate validation failed")
    if executor == "warm" and loaded.validation.code_hash not in reviewed_hashes:
        raise ValueError("source changed after review")
    backend = (PersistentCandidateProxy.from_validated(loaded.callable_obj)
               if executor == "warm" else loaded.callable_obj)
    proxy = MeasuredRepairProxy(backend, perf_counter()-started)
    try:
        yield proxy
    finally:
        proxy.close()


def trial_compositions(current_paths, candidate, *, allow_addition):
    """Always test a feasible replacement; behavior novelty only gates additions."""
    trials = {"replacement": [candidate]}
    if allow_addition and current_paths and len(current_paths) < 2 and candidate not in current_paths:
        trials["addition"] = [*current_paths, candidate]
    elif len(current_paths) == 2:
        for index in range(2):
            trial = list(current_paths)
            trial[index] = candidate
            if len(set(trial)) == 2:
                trials[f"replace_member_{index}"] = trial
    return trials


def compact_gap_feedback(parent, lineage_parent, metrics, current_paths, cases, *, evidence_file, deployment_summary):
    """Three deterministic cases, including the worst case; full traces stay local."""
    gains = parent["gains"]
    raw_delta = [a-b for a,b in zip(parent["raw_repair_gains"], lineage_parent["raw_repair_gains"])]
    choices = []
    rules = [("worst_post_ls", sorted(range(len(cases)), key=lambda i: (gains[i], i))),
             ("largest_lineage_raw_change", sorted(range(len(cases)), key=lambda i: (-abs(raw_delta[i]), i))),
             ("strongest_remaining_gain", sorted(range(len(cases)), key=lambda i: (-gains[i], i)))]
    for rule, order in rules:
        index = next((i for i in order if i not in [c[1] for c in choices]), None)
        if index is not None:
            choices.append((rule, index))

    def task_port(trace, task):
        for robot, route in enumerate(trace):
            if task in route["route_task_ids"]:
                i = route["route_task_ids"].index(task)
                tasks = route["route_task_ids"]
                return {"robot": robot, "state": route["state_ids"][i],
                        "entry": route["entry_points"][i], "exit": route["exit_points"][i],
                        "previous": tasks[i-1] if i else "depot",
                        "next": tasks[i+1] if i+1<len(tasks) else "depot",
                        "incoming_cost": route["transition_costs"][i],
                        "outgoing_cost": route["transition_costs"][i+1]}
        return None

    selected = []
    for rule, index in choices:
        case, row = cases[index], parent["cases"][index]
        stable_id = hashlib.sha256(json.dumps(case, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]
        traces = row["route_dp"]
        selected.append({"case_id": stable_id, "rule": rule, "instance": case["instance_id"], "band": case["band"],
            "evidence_ref": f"{evidence_file}#/paired/{parent['hash']}/cases/{index}",
            "partial_routes": case["partial_routes"], "removed": case["removed_tasks"], "seed": case["seed"],
            "partial_costs": case["partial_costs"], "manual_trace_repair": case["baseline_repair_operator"],
            "outcomes": {name: {"routes": [r["route_task_ids"] for r in trace],
                                "costs": [r["cost"] for r in trace],
                                "bottleneck": max(range(len(trace)), key=lambda i: trace[i]["cost"])}
                         for name, trace in traces.items()},
            "ports_of_first_two_removed_tasks": {
                str(task): {name: task_port(trace, task) for name, trace in traces.items()}
                for task in case["removed_tasks"][:2]}})
    return {"evolution_parent_hash": parent["hash"], "lineage_parent_hash": lineage_parent["hash"],
        "current_composition": {"manual_repairs": ["greedy_insertion", "regret_k_insertion", "bottleneck_balancing_insertion"],
                                "generated_members": [{"path": str(p.relative_to(ROOT)), "hash": digest(p)} for p in current_paths]},
        "paired_summary": [{"hash": m["hash"], "raw_mean_gain": mean(m["raw_repair_gains"]),
                            "post_ls_mean_gain": mean(m["gains"]), "post_ls_gains": m["gains"]} for m in metrics if m["valid"]],
        "deployment_summary": deployment_summary, "selected_cases": selected,
        "limits": "Development only. Manual trace is the actual recorded repair, not a portfolio oracle. Entry/exit records are fixed-route DP results, not exact joint marginal contributions or online features. Full traces remain at evidence_ref."}


class ManualProxy:
    def __init__(self, solver, name):
        self.solver, self.name = solver, name

    def execute(self, args, timeout_ms):
        partial, removed, _, _ = args
        solution = self.solver.repair_ops[self.name](
            partial, removed, self.solver.solution_evaluator.evaluate_partial(partial))
        return SimpleNamespace(status="success", result=RepairResult(solution))


def evaluate(path, entries, cases, manual=None, *, executor="original", reviewed_hashes=()):
    record = {"id": manual or path.stem, "path": str(path) if path else None,
              "hash": manual or digest(path), "valid": True, "cases": [], "gains": [],
              "raw_repair_gains": [], "runtime_samples": []}
    with ExitStack() as stack:
        try:
            generated = None if manual else stack.enter_context(managed_executor(
                path, executor, reviewed_hashes=reviewed_hashes))
        except ValueError as exc:
            return {**record, "valid": False, "validation_error": str(exc), "score": -1e12}
        for entry in entries:
            solver = ALNSSolver(load_instance(ROOT / "data/structural_benchmark_v1" / entry["path"]),
                                config=ALNSConfig.enhanced(iterations=1, random_seed=0))
            solver.local_search = lambda solution: run_priced_local_search(
                solution, solver.solution_evaluator, solver.insertion_pricer, max_iterations=1)
            proxy = ManualProxy(solver, manual) if manual else generated
            subset = [c for c in cases if c["instance_id"] == entry["instance_id"]]
            metrics = _evaluate_candidate(solver, {"proxy": proxy}, subset)
            record["valid"] &= metrics["valid"]
            for key in ("cases", "gains", "raw_repair_gains"):
                record[key].extend(metrics[key])
            record["runtime_samples"].append(metrics["runtime_ms"])
    if generated:
        record["executor_statistics"] = generated.statistics()
    record["runtime_ms"] = mean(record.pop("runtime_samples"))
    record["score"] = mean(record["gains"]) if record["valid"] else -1e12
    return record


def deploy(paths, entries, config):
    rows = []
    for entry in entries:
        for seed in config["seeds"]:
            started = perf_counter()
            iterations = config.get("deployment_iterations")
            deadline = None if iterations is not None else config["deployment_seconds"]
            solver = ALNSSolver(load_instance(ROOT / "data/structural_benchmark_v1" / entry["path"]),
                config=ALNSConfig.enhanced(iterations=iterations,
                    max_runtime_seconds=deadline, random_seed=seed,
                    capture_operator_states=iterations is not None,
                    segment_length=4, priced_local_search=True, operator_minimum_uses=1))
            names = {}
            proxies = {}
            with ExitStack() as stack:
                for path in paths:
                    name = "generated_" + digest(path)[:12]
                    names[name] = digest(path)
                    proxies[name] = stack.enter_context(managed_executor(path, config.get("executor", "original"),
                        reviewed_hashes=config.get("reviewed_warm_hashes", ())))
                    solver.register_development_repair(proxies[name], name=name)
                weights = {"destroy": dict(solver.destroy_weights), "repair": dict(solver.repair_weights)}
                result = solver.solve()
            total_wall_seconds = perf_counter()-started
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
                "total_wall_seconds": total_wall_seconds, "iterations": result.iterations_completed,
                "executor": config.get("executor", "original"),
                "executor_statistics": {name: proxy.statistics() for name, proxy in proxies.items()},
                "deadline_overshoot_seconds": max(0., result.runtime_seconds-deadline) if deadline else 0.,
                "best_routes": result.best_solution.routes,
                "route_dp_calls": result.route_dp_calls, "route_dp_cache_misses": result.route_dp_cache_misses,
                "dp_work_including_setup": solver.route_dp.statistics(),
                "insertion_pricing_work": solver.insertion_pricer.statistics(),
                "phase_seconds": result.timing_breakdown_seconds,
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
                "selection_rule": "Feasible and <=500ms permits replacement; paired novelty >=2 and not worse on every state additionally permits an addition trial to the current actual winner. Retain only if mean short-ALNS makespan improves by >=0.001 with no fallback and every generated member called. Manual-only eligible. Two fixed seeds; development evidence only.",
                "policy": "spatial_sort; one-pass priced local search; unchanged enhanced ALNS acceptance; minimum uses=1 then independent adaptive roulette; initial weights=1; shared pair rewards 8/3/1; segment=4"}
    groups = {"manual": deploy([], entries, config), "current": deploy([parent_path], entries, config)}
    artifact["baseline_deployment"] = groups
    artifact["paired"] = {m["hash"]: m for m in [*manuals, anchor]}
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
    # Evolution parent is a lineage identity, independent of the deployed winner.
    evolution_parent_metrics = anchor
    lineage_parent_metrics = anchor
    best_name = min((g for g in groups if eligible(groups[g])), key=lambda g: mean(r["makespan"] for r in groups[g]))
    best_paths = [] if best_name == "manual" else [parent_path]
    best_mean = mean(r["makespan"] for r in groups[best_name])
    for generation in range(1, config["max_rounds"]+1):
        feedback = compact_gap_feedback(evolution_parent_metrics, lineage_parent_metrics,
            list(artifact["paired"].values()), best_paths, cases,
            evidence_file=str(out / "results.json"),
            deployment_summary={"current_mean": best_mean,
                                "previous_trials": [{"generation": r["generation"], "mean": r.get("deployment_mean")} for r in artifact["rounds"]]})
        if artifact["rounds"]:
            previous = artifact["rounds"][-1]
            feedback["actual_previous_deployment"] = {k: previous.get(k) for k in ("admission", "deployment_mean", "parent_delta", "retained")}
            feedback["revision_instruction"] = "Revise the actual parent behavior using its paired losses and deployment result. If gains vanished, reduce unnecessary route perturbations/cost. Do not repeat identical behavior."
        folder = out / f"request_{len(artifact['requests'])+1:02d}"
        prompt = build_compact_gap_revision_prompt(parent={"operator_id": parent_path.stem,
            "source_path": str(parent_path), "source_hash": digest(parent_path)}, feedback=feedback,
            target="Address the observed deployment/paired gap relative to the actual composition. Preserve useful behavior; propose a bounded structural change, not an average-score-only objective.")
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
               "evaluation": metrics, "retained": False,
               "composition_before": [digest(p) for p in best_paths], "trials": {}}
        shortlist = select_behavioral_shortlist([anchor, metrics], anchor_hash=anchor["hash"], capacity=1,
            min_behavior_delta=config["min_behavior_delta"], max_runtime_ms=config["runtime_cap_ms"])
        row["parent_delta"] = [a-b for a,b in zip(metrics["gains"], evolution_parent_metrics["gains"])] if metrics["valid"] else []
        feasible = metrics["valid"] and metrics["runtime_ms"] <= config["runtime_cap_ms"]
        row["admission"] = "replacement_and_optional_addition" if feasible else "invalid_or_cost_rejection"
        if feasible:
            proposals = trial_compositions(best_paths, path, allow_addition=bool(shortlist))
            for kind, trial_paths in proposals.items():
                deployment = deploy(trial_paths, entries, config)
                trial_mean = mean(r["makespan"] for r in deployment)
                row["trials"][kind] = {"hashes": [digest(p) for p in trial_paths],
                                       "deployment": deployment, "mean": trial_mean}
                if eligible(deployment) and trial_mean < best_mean-config["minimum_gain"]:
                    best_paths, best_mean = trial_paths, trial_mean
                    row["retained"] = True
            best_trial = min(row["trials"].values(), key=lambda t: t["mean"])
            row["deployment_mean"] = best_trial["mean"]
        row["composition_after"] = [digest(p) for p in best_paths]
        artifact["rounds"].append(row)
        artifact["paired"][metrics["hash"]] = metrics
        save(out / "results.json", artifact)
        print(json.dumps({"generation": generation, "valid": metrics["valid"], "gains": metrics["gains"],
                          "admission": row["admission"], "deployment_mean": row.get("deployment_mean"), "retained": row["retained"]}), flush=True)
        if not metrics["valid"]:
            artifact["stop_reason"] = "candidate invalid after at most one engineering repair"
            break
        lineage_parent_metrics = evolution_parent_metrics
        parent_path, evolution_parent_metrics = path, metrics
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
    rows = deploy(paths, entries, artifact.get("deployment_config", artifact["config"]))
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
