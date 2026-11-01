"""One development-only, zero-LLM recheck of the existing three-repair lineage."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import random
from pathlib import Path
from statistics import mean
from time import perf_counter

from .operator_gap_revision import (
    ROOT, compact_gap_feedback, deploy, digest, eligible, evaluate, managed_executor, save,
)
from ..core.instance_loader import load_instance
from ..core.models import MultiRobotSolution
from ..llm.operator_evolution.protocols import RepairContext
from ..llm.prompts.operator_revision import build_compact_gap_revision_prompt


def semantic_trace(row):
    keys = ("destroy", "repair", "accepted", "accept_reason", "temperature", "current_makespan",
            "best_makespan", "candidate_makespan", "candidate_delta", "fallback_used", "removed_tasks",
            "partial_routes", "repaired_routes", "refined_routes", "route_dp_calls", "route_dp_cache_misses")
    return [[r[k] for k in keys] for r in row["history"]]


def make_args(case, entry):
    instance = load_instance(ROOT / "data/structural_benchmark_v1" / entry["path"])
    costs = list(case["partial_costs"])
    return (MultiRobotSolution([list(r) for r in case["partial_routes"]]), list(case["removed_tasks"]),
            RepairContext(instance, costs, max(costs), max(range(len(costs)), key=costs.__getitem__)),
            random.Random(case["seed"]))


def review_sources(paths, hashes):
    rows = []
    for path in paths:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = sorted(n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom))
        module_assignments = [type(n).__name__ for n in tree.body if not isinstance(n, (ast.ImportFrom, ast.FunctionDef))]
        shared_bindings = [type(n).__name__ for n in ast.walk(tree) if isinstance(n, (ast.Global, ast.Nonlocal))]
        if (digest(path) not in hashes or module_assignments or shared_bindings or
                set(imports) - {"math", "mrta_rect_coverage.core.models", "mrta_rect_coverage.llm.operator_evolution.protocols"}):
            raise ValueError("source no longer matches this narrow stateless review")
        rows.append({"path": str(path.relative_to(ROOT)), "hash": digest(path), "imports": imports,
            "module_assignments": module_assignments, "global_nonlocal_bindings": shared_bindings,
            "review": "Exact sources inspected: local route copies/caches, supplied RNG only, no imported-module mutation; fresh candidate namespace each call. Not a general statelessness proof or OS sandbox."})
    return rows


def calibrate(paths, case, entry, config):
    rows = []
    for path in paths:
        modes = {}
        for mode in ("original", "warm"):
            with managed_executor(path, mode, reviewed_hashes=config["reviewed_warm_hashes"]) as proxy:
                count = 2 if mode == "original" else 1+config["calibration_subsequent_calls"]
                for _ in range(count):
                    outcome = proxy.execute(make_args(case, entry), timeout_ms=2000)
                    if outcome.status != "success":
                        raise RuntimeError("calibration execution failed: " + outcome.status)
            modes[mode] = proxy.statistics()
        rows.append({"hash": digest(path), **modes})
    setup = sorted((r["warm"]["validation_and_smoke_seconds"] + r["warm"]["samples"][0]["startup_ms"]/1000 for r in rows), reverse=True)
    steady = max(r["warm"]["subsequent_mean_ms"] for r in rows)/1000
    seconds = math.ceil(10*max(config["minimum_seconds"],
        config["calibration_startup_multiplier"]*sum(setup[:2]) + config["calibration_call_multiplier"]*steady))/10
    return {"measurements": rows, "frozen_seconds": seconds,
            "rule": "Round up to 0.1s: max(1s, 3*(largest two validation+startup costs)+100*slowest mean subsequent warm call). No objective is used for calibration. Cold worker startup occurs inside solve; validation/smoke outside solve is included in end-to-end time.",
            "case": {"instance": case["instance_id"], "band": case["band"]}}


def summarize(groups):
    return {name: {"mean_makespan": mean(r["makespan"] for r in rows),
                   "makespans": [r["makespan"] for r in rows],
                   "iterations": [r["iterations"] for r in rows],
                   "solve_seconds": sum(r["runtime_seconds"] for r in rows),
                   "end_to_end_seconds": sum(r["total_wall_seconds"] for r in rows),
                   "route_dp_calls": sum(r["route_dp_calls"] for r in rows),
                   "dp_cache_misses": sum(r["route_dp_cache_misses"] for r in rows),
                   "insertion_prices": sum(r["insertion_pricing_work"]["insertion_prices"] for r in rows),
                   "max_deadline_overshoot_seconds": max(r["deadline_overshoot_seconds"] for r in rows)}
            for name, rows in groups.items()}


def run(config_path, *, output_dir=None):
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if output_dir is not None:
        config["output_dir"] = str(output_dir)
    if config["llm_calls"] != 0:
        raise ValueError("this recheck never calls a model")
    out = ROOT / config["output_dir"]
    out.mkdir(parents=True, exist_ok=False)
    save(out / "config.json", config)
    started = perf_counter()
    prior = json.loads((ROOT / config["source_result"]).read_text(encoding="utf-8"))
    paths = [Path(prior["anchor"]["path"])] + [Path(r["evaluation"]["path"]) for r in prior["rounds"]]
    expected = [prior["anchor"]["hash"]] + [r["child_hash"] for r in prior["rounds"]]
    if [digest(path) for path in paths] != expected or expected != config["reviewed_warm_hashes"]:
        raise ValueError("frozen lineage identities do not match the reviewed sources")
    cases = prior["cases"]
    manifest = json.loads((ROOT / "data/structural_benchmark_v1/manifest.json").read_text(encoding="utf-8"))
    ids = {c["instance_id"] for c in cases}
    entries = [e for e in manifest["entries"] if e["instance_id"] in ids]
    if len(entries) != 2 or any(e["split"] != "development" for e in entries):
        raise ValueError("only the two previously consumed development identities are allowed")
    for entry in entries:
        if hashlib.sha256((ROOT / "data/structural_benchmark_v1" / entry["path"]).read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError("manifest source mismatch")
    review = review_sources(paths, config["reviewed_warm_hashes"])
    groups = {"manual": [], "historical": paths[:1], "generation_1": paths[1:2],
              "generation_2": paths[2:3], "historical_plus_generation_2": [paths[0], paths[2]]}
    artifact = {"config": config, "source_review": review, "cases": cases, "llm_calls": 0,
                "evolution_parent": {"path": str(paths[2].relative_to(ROOT)), "hash": digest(paths[2])},
                "initial_deployment_members": prior["final_generated_members"],
                "proposal_groups": {name: [digest(p) for p in members] for name, members in groups.items()},
                "paired": {}, "paired_equivalence": [], "fixed": {}, "timed": {}}
    for path in paths:
        original = evaluate(path, entries, cases)
        warm = evaluate(path, entries, cases, executor="warm", reviewed_hashes=config["reviewed_warm_hashes"])
        same = (original["valid"] and warm["valid"] and original["gains"] == warm["gains"]
                and original["raw_repair_gains"] == warm["raw_repair_gains"]
                and [r["route_dp"] for r in original["cases"]] == [r["route_dp"] for r in warm["cases"]])
        artifact["paired"][digest(path)] = warm
        artifact["paired_equivalence"].append({"hash": digest(path), "same": same, "original": original})
        save(out / "results.json", artifact)
        if not same:
            raise RuntimeError("paired executor discrepancy; deployment study stopped")
    for name in ("greedy_insertion", "regret_k_insertion", "bottleneck_balancing_insertion"):
        artifact["paired"][name] = evaluate(None, entries, cases, manual=name)
    fixed_config = {"seeds": config["seeds"], "deployment_iterations": config["fixed_iterations"],
                    "reviewed_warm_hashes": config["reviewed_warm_hashes"]}
    for mode in ("original", "warm"):
        artifact["fixed"][mode] = {}
        for name, members in groups.items():
            artifact["fixed"][mode][name] = deploy(members, entries, {**fixed_config, "executor": mode})
            print(f"fixed {mode} {name} complete", flush=True)
            save(out / "results.json", artifact)
    equality = {}
    for name in groups:
        left, right = artifact["fixed"]["original"][name], artifact["fixed"]["warm"][name]
        equality[name] = all(semantic_trace(a) == semantic_trace(b) and a["best_routes"] == b["best_routes"]
            and a["insertion_pricing_work"] == b["insertion_pricing_work"] for a,b in zip(left,right))
    artifact["fixed_equivalence"] = equality
    save(out / "results.json", artifact)
    if not all(equality.values()):
        raise RuntimeError("fixed-iteration executor discrepancy; timing study stopped")
    calibration = calibrate(paths, cases[0], entries[0], config)
    save(out / "calibration.json", calibration)  # frozen before any timed objective is observed
    timed_config = {"seeds": config["seeds"], "executor": "warm", "deployment_seconds": calibration["frozen_seconds"],
                    "reviewed_warm_hashes": config["reviewed_warm_hashes"]}
    artifact["deployment_config"] = timed_config
    print(json.dumps({"frozen_seconds": calibration["frozen_seconds"], "fixed_equivalence": equality}), flush=True)
    for name, members in groups.items():
        artifact["timed"][name] = deploy(members, entries, timed_config)
        print(f"timed {name} complete", flush=True)
        save(out / "results.json", artifact)
    summary = {"fixed_original": summarize(artifact["fixed"]["original"]),
               "fixed_warm": summarize(artifact["fixed"]["warm"]), "timed_warm": summarize(artifact["timed"])}
    selected = "manual"
    selected_mean = summary["timed_warm"][selected]["mean_makespan"]
    for name in groups:
        value = summary["timed_warm"][name]["mean_makespan"]
        if eligible(artifact["timed"][name]) and value < selected_mean-config["minimum_gain"]:
            selected, selected_mean = name, value
    artifact["summary"] = summary
    artifact["selected_group"] = selected
    artifact["final_generated_members"] = [{"path": str(p.relative_to(ROOT)), "hash": digest(p)} for p in groups[selected]]
    artifact["stop_reason"] = "predeclared five groups, fixed-iteration equivalence and one calibrated time budget completed; zero LLM requests"
    artifact["wall_seconds"] = perf_counter()-started
    feedback = compact_gap_feedback(artifact["paired"][digest(paths[2])], artifact["paired"][digest(paths[1])],
        list(artifact["paired"].values()), groups[selected], cases,
        evidence_file=str((out / "results.json").relative_to(ROOT)), deployment_summary=summary)
    target = ("The existing local insertion proxy independently minimizes neighbor ports, while one coherent route "
              "must share their states. Test a bounded alternative that evaluates both orders of the first two "
              "unassigned tasks with one consistent local predecessor/successor state choice, and leaves unrelated "
              "route order unchanged. Treat this as an untested hypothesis; do not assume diversity or code change is benefit. "
              "The recorded selection and negative states must govern any future revision decision.")
    prompt = build_compact_gap_revision_prompt(parent={"source_path": str(paths[2]), "source_hash": digest(paths[2])},
                                               feedback=feedback, target=target)
    (out / "next_prompt.txt").write_text(prompt, encoding="utf-8")
    save(out / "next_feedback.json", feedback)
    old_prompts = [ROOT / "outputs/operator_gap_revision/batch_001" / f"request_{i:02d}/prompt.txt" for i in (1,2)]
    lengths = {"new_characters": len(prompt), "new_utf8_bytes": len(prompt.encode()),
               "old_characters": [len(p.read_text(encoding="utf-8")) for p in old_prompts],
               "selected_case_count": len(feedback["selected_cases"]),
               "parent_source_occurrences": prompt.count(paths[2].read_text(encoding="utf-8")),
               "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(), "llm_calls": 0}
    save(out / "prompt_lengths.json", lengths)
    save(out / "results.json", artifact)
    save(out / "summary.json", {"summary": summary, "selected_group": selected, "final_generated_members": artifact["final_generated_members"],
                                "fixed_equivalence": equality, "calibration_seconds": calibration["frozen_seconds"],
                                "wall_seconds": artifact["wall_seconds"], "llm_calls": 0})
    print(json.dumps({"summary": summary, "selected_group": selected, "prompt_lengths": lengths}), flush=True)
    return artifact


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/operator_gap_recheck.json")
    parser.add_argument("--output", type=Path, help="Fresh output directory; never overwrite an existing run")
    args = parser.parse_args()
    run(args.config, output_dir=args.output)
