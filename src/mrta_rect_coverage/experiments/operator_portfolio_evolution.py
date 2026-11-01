"""Small, development-only complementarity study for generated repair operators."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path
from statistics import mean
from time import perf_counter

from ..core.instance_loader import load_instance
from ..core.models import MultiRobotSolution
from ..heuristics.alns_solver import ALNSConfig, ALNSSolver
from ..heuristics.priced_local_search import run_priced_local_search
from ..llm.operator_evolution.candidate_loader import load_and_validate_candidate
from ..llm.operator_evolution.candidate_security import code_sha256
from ..llm.operator_evolution.protocols import RepairContext
from ..llm.operator_evolution.prompt_builder import build_revision_prompt

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = ROOT / "configs/operator_portfolio_evolution.json"


def select_complementary_repairs(candidates, *, capacity: int, min_gain: float):
    """Keep the best valid anchor, then candidates adding useful state coverage."""
    valid = [
        item for item in candidates
        if item.get("valid") is True
        and item.get("gains")
        and all(isinstance(value, (int, float)) for value in item["gains"])
        and max(item["gains"]) >= min_gain
    ]
    if capacity <= 0 or not valid:
        return []
    selected = [max(valid, key=lambda item: (item["score"], item["id"]))]
    covered = {i for i, value in enumerate(selected[0]["gains"]) if value >= min_gain}
    while len(selected) < capacity:
        options = []
        for item in valid:
            if item in selected:
                continue
            new = {
                index for index, value in enumerate(item["gains"])
                if index not in covered and value >= min_gain
            }
            contribution = sum(max(0.0, item["gains"][i]) for i in new)
            if new and contribution >= min_gain:
                options.append((contribution, item["score"], item["id"], item, new))
        if not options:
            break
        _, _, _, chosen, new_cases = max(options)
        selected.append(chosen)
        covered.update(new_cases)
    return selected


def request_bounded_revisions(provider, prompt: str, *, round_id: int, n: int,
                              parent_hashes: list[str], call_budget: int,
                              token_budget: int, calls_used: int = 0):
    """Call the existing offline provider only after a per-run budget preflight."""
    if calls_used >= call_budget:
        raise RuntimeError("LLM call budget exhausted")
    estimated_input = (len(prompt) + 3) // 4
    reserved_output = 256 * n
    if estimated_input + reserved_output > token_budget:
        raise RuntimeError("revision prompt exceeds the configured token budget")
    drafts = provider.revise_operator_candidates(
        prompt, {"parent_hashes": list(parent_hashes)}, n=n,
        operator_type="repair", round_id=round_id,
    )
    metadata = getattr(provider, "last_call_metadata", {})
    actual = metadata.get("total_tokens")
    if isinstance(actual, (int, float)) and actual > token_budget:
        raise RuntimeError("provider response exceeded the configured token budget")
    provenance = {
        "round_id": round_id,
        "parent_hashes": list(parent_hashes),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "estimated_input_tokens": estimated_input,
        "reserved_output_tokens": reserved_output,
        "actual_tokens": actual,
        "provider_call_metadata": metadata,
    }
    return drafts, provenance


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _development_entries(manifest: dict, limit: int) -> list[dict]:
    entries = [entry for entry in manifest["entries"] if entry["split"] == "development"]
    return entries[:limit]


def _source_candidates(project_root: Path, max_candidates: int) -> list[dict]:
    """Read only artifacts with a matching E17 raw response and candidate record."""
    root = project_root / "outputs/e17_evidence_arms/F2_dataset"
    sources = {}
    for metrics in sorted(root.glob("rep*/round_*_candidates.json")):
        rows = json.loads(metrics.read_text(encoding="utf-8"))
        round_id = int(metrics.stem.split("_")[1])
        rep = metrics.parent.name
        raw = list(metrics.parent.glob(f"*repair*round_{round_id:03d}_raw.txt"))
        raw_items = []
        for raw_path in raw:
            try:
                raw_items.extend(json.loads(raw_path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, TypeError):
                pass
        for row in rows:
            if row.get("operator_type") != "repair" or not row.get("code_hash"):
                continue
            path = project_root / "generated_operators/e17/F2_dataset" / rep / f"round_{round_id:03d}" / f"{row['operator_id']}.py"
            if not path.is_file() or code_sha256(path.read_text(encoding="utf-8")) != row["code_hash"]:
                continue
            source = path.read_text(encoding="utf-8")
            if not any(item.get("code", "").strip() == source.strip() for item in raw_items):
                continue
            sources.setdefault(row["code_hash"], {
                "id": row["operator_id"], "path": path, "hash": row["code_hash"],
                "round": round_id, "metrics": row, "raw": [str(p.relative_to(project_root)) for p in raw],
            })
    return sorted(sources.values(), key=lambda item: item["hash"])[:max_candidates]


def _sample_trace(history: list[dict], stagnation_patience: int) -> list[tuple[str, dict]]:
    if not history:
        return []
    n = len(history)
    best = float("inf")
    last_improvement = 0
    for index, row in enumerate(history):
        if row["best_makespan"] < best - 1e-9:
            best = row["best_makespan"]
            last_improvement = index
    stagnation = history[-1] if len(history) - last_improvement >= stagnation_patience else None
    points = [
        ("early", history[min(n - 1, max(0, n // 10))]),
        ("middle", history[min(n - 1, n // 2)]),
        (("stagnation" if stagnation else "late_no_stagnation_point"), stagnation or history[-1]),
    ]
    unique = []
    seen = set()
    for band, row in points:
        key = row["iteration"]
        if key not in seen:
            seen.add(key)
            unique.append((band, row))
    return unique


def _evaluate_candidate(solver, candidate, trace):
    proxy = candidate["proxy"]
    gains, raw_gains, runtimes, outcomes = [], [], [], []
    for case_id, item in enumerate(trace):
        partial = MultiRobotSolution(routes=[list(r) for r in item["partial_routes"]])
        removed = list(item["removed_tasks"])
        costs = list(item["partial_costs"])
        context = RepairContext(
            instance=solver.instance,
            per_robot_costs=costs,
            route_costs_makespan=max(costs, default=0.0),
            bottleneck_route_id=max(range(len(costs)), key=costs.__getitem__) if costs else 0,
        )
        started = perf_counter()
        result = proxy.execute((partial, removed, context, random.Random(item["seed"])), timeout_ms=2000)
        wall_ms = (perf_counter() - started) * 1000
        runtimes.append(wall_ms)
        if result.status != "success" or not solver._is_valid_full_solution(result.result.solution):
            outcomes.append({"case": case_id, "status": result.status if result.status != "success" else "invalid_solution"})
            gains.append(float("nan"))
            raw_gains.append(float("nan"))
            continue
        candidate_solution = result.result.solution
        baseline_eval = solver.solution_evaluator.evaluate(
            MultiRobotSolution(routes=[list(r) for r in item["baseline_repaired_routes"]])
        )
        candidate_eval = solver.solution_evaluator.evaluate(candidate_solution)
        raw_gains.append(baseline_eval.makespan - candidate_eval.makespan)
        refined, refined_eval = solver.local_search(candidate_solution)
        gains.append(baseline_eval.makespan - refined_eval.makespan)
        outcomes.append({
            "case": case_id, "status": "success", "band": item["band"],
            "instance_id": item["instance_id"],
            "baseline_repair": baseline_eval.makespan,
            "baseline_per_robot_costs": list(baseline_eval.per_robot_costs),
            "baseline_bottleneck_robot": max(range(len(baseline_eval.per_robot_costs)),
                                                key=baseline_eval.per_robot_costs.__getitem__),
            "candidate_repair": candidate_eval.makespan,
            "candidate_bottleneck_robot": max(range(len(candidate_eval.per_robot_costs)),
                                                 key=candidate_eval.per_robot_costs.__getitem__),
            "candidate_after_local_search": refined_eval.makespan,
            "per_robot_costs": list(candidate_eval.per_robot_costs),
            "after_local_search_per_robot_costs": list(refined_eval.per_robot_costs),
            "runtime_ms": wall_ms,
        })
    valid = bool(gains) and all(value == value for value in gains)
    return {
        "valid": valid,
        "score": mean(gains) if valid else -1e12,
        "gains": gains if valid else [],
        "raw_repair_gains": raw_gains,
        "runtime_ms": mean(runtimes) if runtimes else 0.0,
        "cases": outcomes,
    }


def run(config_path: Path = DEFAULT_CONFIG) -> dict:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    project_root = config_path.resolve().parents[1]
    manifest_path = project_root / config["manifest"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = _development_entries(
        manifest, int(config["development_instances"]) + int(config["check_instances"])
    )
    screen_entries = entries[:int(config["development_instances"])]
    check_entries = entries[int(config["development_instances"]):]
    if any(entry["split"] != "development" for entry in entries):
        raise ValueError("portfolio development inputs may only use development split")
    source_candidates = _source_candidates(project_root, int(config["candidate_archive_capacity"]))
    if not source_candidates:
        raise RuntimeError("No hash-matched E17 repair with a matching raw LLM response")
    expected_candidate_evaluations = (
        len(source_candidates) * len(screen_entries) * 3
    )
    if expected_candidate_evaluations > int(config["candidate_evaluation_budget"]):
        raise ValueError("candidate archive and development trace exceed the configured evaluation budget")

    candidate_accumulator = {
        candidate["hash"]: {
            "id": candidate["id"], "hash": candidate["hash"],
            "path": str(candidate["path"].relative_to(project_root)),
            "lineage": {"parent": "E17", "round": candidate["round"], "raw_response_sources": candidate["raw"]},
            "source_metrics": {key: candidate["metrics"].get(key) for key in ("avg_relative_improvement", "success_rate")},
            "gains": [], "cases": [], "runtime_samples": [], "valid": True,
        }
        for candidate in source_candidates
    }
    initialization_check = []
    for entry in entries:
        instance = load_instance(project_root / "data/structural_benchmark_v1" / entry["path"])
        for constructor in ("spatial_sort", "dp_greedy"):
            started = perf_counter()
            initial_solver = ALNSSolver(instance, constructor=constructor,
                                        config=ALNSConfig(iterations=0, random_seed=int(config["seed"])))
            initial_eval = initial_solver.solution_evaluator.evaluate(initial_solver.initial_solution)
            initialization_check.append({
                "instance_id": entry["instance_id"], "role": "stage_end_check" if entry in check_entries else "development_selection",
                "constructor": constructor, "initial_makespan": initial_eval.makespan,
                "construction_plus_solver_setup_seconds": perf_counter() - started,
                "per_robot_costs": list(initial_eval.per_robot_costs),
                "routes": initial_solver.initial_solution.routes,
            })
    all_cases = []
    baseline_runs = []
    for entry in screen_entries:
        path = project_root / "data/structural_benchmark_v1" / entry["path"]
        if _digest(path) != entry["sha256"]:
            raise ValueError(f"development manifest hash mismatch: {entry['instance_id']}")
        instance = load_instance(path)
        solver = ALNSSolver(instance, config=ALNSConfig.enhanced(
            iterations=int(config["trace_iterations"]), random_seed=int(config["seed"]),
            capture_operator_states=True,
            priced_local_search=True,
        ))
        baseline = solver.solve()
        baseline_runs.append({
            "instance_id": entry["instance_id"], "makespan": baseline.best_evaluation.makespan,
            "runtime_seconds": baseline.runtime_seconds, "iterations": baseline.iterations_completed,
            "routes": baseline.best_solution.routes,
        })
        sampled = _sample_trace(baseline.iteration_history, int(config["stagnation_patience"]))
        instance_cases = []
        for band, row in sampled:
            repairs = solver.repair_ops[row["repair"]]
            partial = MultiRobotSolution(routes=[list(r) for r in row["partial_routes"]])
            partial_eval = solver.solution_evaluator.evaluate_partial(partial)
            baseline_repair = repairs(partial, list(row["removed_tasks"]), partial_eval)
            instance_cases.append({
                "instance_id": entry["instance_id"], "band": band,
                "partial_routes": partial.routes, "removed_tasks": row["removed_tasks"],
                "partial_costs": partial_eval.per_robot_costs,
                "baseline_repaired_routes": baseline_repair.routes,
                "seed": int(config["seed"]) + row["iteration"],
            })
        all_cases.extend(instance_cases)
        for candidate in source_candidates:
            loaded = load_and_validate_candidate(
                path=candidate["path"], operator_type="repair", round_id=candidate["round"],
                source="langchain_openai_compatible", description="E17 raw-record matched candidate",
                allow_unsafe_candidate_execution=True,
            )
            if loaded.callable_obj is None or loaded.validation.code_hash != candidate["hash"]:
                candidate_accumulator[candidate["hash"]].update(
                    valid=False, reason=loaded.validation.error_message or "hash mismatch")
                continue
            proxy = loaded.callable_obj
            case_solver = ALNSSolver(instance, config=ALNSConfig.enhanced(iterations=1, random_seed=0))
            case_solver.local_search = lambda solution: run_priced_local_search(
                solution, case_solver.solution_evaluator, case_solver.insertion_pricer, max_iterations=1
            )
            metrics = _evaluate_candidate(case_solver, {**candidate, "proxy": proxy}, instance_cases)
            acc = candidate_accumulator[candidate["hash"]]
            acc["valid"] = acc["valid"] and metrics["valid"]
            acc["gains"].extend(metrics["gains"])
            acc["cases"].extend(metrics["cases"])
            acc["runtime_samples"].append(metrics["runtime_ms"])

    candidate_records = []
    for item in candidate_accumulator.values():
        item["score"] = mean(item["gains"]) if item["valid"] and item["gains"] else -1e12
        item["runtime_ms"] = mean(item.pop("runtime_samples")) if item["gains"] else 0.0
        if not item["valid"]:
            item["gains"] = []
        candidate_records.append(item)

    selection = select_complementary_repairs(
        candidate_records, capacity=int(config["deployment_capacity"]),
        min_gain=max(float(config["min_state_gain"]), float(config["minimum_effective_improvement"]))
    )
    top_k = sorted((row for row in candidate_records if row.get("valid")),
                   key=lambda row: row["score"], reverse=True)[:int(config["deployment_capacity"])]
    decision = {
        "method": "problem-state coverage greedy complementarity; mean post-local-search gain is the per-state utility",
        "selected_hashes": [row["hash"] for row in selection],
        "top_k_hashes": [row["hash"] for row in top_k],
        "selection_matches_top_k": [row["hash"] for row in selection] == [row["hash"] for row in top_k],
        "selection_reasons": [
            {
                "id": row["id"], "score": row["score"],
                "covered_states": [
                    f"{case['instance_id']}:{case['band']}"
                    for case_index, case in enumerate(row["cases"])
                    if case.get("status") == "success"
                    and row["gains"][case_index] >= max(
                        float(config["min_state_gain"]), float(config["minimum_effective_improvement"])
                    )
                ],
            }
            for row in selection
        ],
    }
    deployment = []
    run_sets = {
        "manual_pool": [],
        "single_champion": [top_k[0]["hash"]] if top_k else [],
        "complementary": [row["hash"] for row in selection],
        "single_score_top_k": [row["hash"] for row in top_k],
    }
    selected_source = {item["hash"]: item for item in source_candidates}
    for method, hashes in run_sets.items():
        for entry in entries:
            instance = load_instance(project_root / "data/structural_benchmark_v1" / entry["path"])
            solver = ALNSSolver(instance, config=ALNSConfig.enhanced(
                iterations=int(config["deployment_iterations"]), random_seed=int(config["seed"]),
                segment_length=4, priced_local_search=True, operator_minimum_uses=1,
            ))
            for index, code_hash in enumerate(hashes):
                candidate = selected_source[code_hash]
                loaded = load_and_validate_candidate(
                    path=candidate["path"], operator_type="repair", round_id=candidate["round"],
                    source="langchain_openai_compatible", description="selected E17 repair",
                    allow_unsafe_candidate_execution=True,
                )
                if loaded.callable_obj is None or loaded.validation.code_hash != code_hash:
                    raise RuntimeError(f"selected operator failed deployment validation: {code_hash}")
                solver.register_development_repair(loaded.callable_obj, name=f"portfolio_repair_{index}")
            result = solver.solve()
            repair_stats = result.operator_usage_stats["repair"]
            deployment.append({
                "method": method, "instance_id": entry["instance_id"],
                "role": "stage_end_check" if entry in check_entries else "development_selection",
                "makespan": result.best_evaluation.makespan,
                "runtime_seconds": result.runtime_seconds,
                "iterations": result.iterations_completed,
                "operator_stats": {
                    name: {
                        "calls": record.uses,
                        "shared_iteration_reward": record.score,
                        "accepted_iterations": sum(
                            row["repair"] == name and row["accepted"] for row in result.iteration_history
                        ),
                        "global_best_iterations": sum(
                            row["repair"] == name and row["score_raw"] >= 8.0 for row in result.iteration_history
                        ),
                        "execution_seconds": result.operator_time_stats["repair"][name][0],
                    }
                    for name, record in repair_stats.items()
                },
                "fallback_events": len(result.fallback_events),
                "repair_hashes": hashes,
                "exploration_minimum_uses": 1 if hashes else 0,
            })
    candidate_groups = ["single_champion", "complementary", "single_score_top_k"]
    group_means = {
        name: mean(row["makespan"] for row in deployment
                   if row["method"] == name and row["role"] == "development_selection")
        for name in candidate_groups if any(row["method"] == name for row in deployment)
    }
    deployed_method = min(group_means, key=group_means.get) if group_means else "manual_pool"
    decision["short_alns_group_means"] = group_means
    decision["deployed_method"] = deployed_method
    decision["deployed_hashes"] = run_sets.get(deployed_method, [])
    decision["deployment_reason"] = (
        "lowest mean development makespan among matched short-ALNS candidate groups; "
        "one seed and two development instances, exploratory only"
    )
    revision_feedback = []
    for candidate in sorted((row for row in candidate_records if row.get("valid")),
                            key=lambda row: row["score"], reverse=True)[:3]:
        improved = [case for case in candidate["cases"]
                    if case.get("status") == "success"
                    and case["candidate_after_local_search"] < case["baseline_repair"] - 1e-9]
        failed = [case for case in candidate["cases"]
                  if case.get("status") == "success"
                  and case["candidate_after_local_search"] >= case["baseline_repair"] - 1e-9]
        revision_feedback.append({
            "candidate_hash": candidate["hash"],
            "effective_states": [f"{case['instance_id']}:{case['band']}" for case in improved],
            "ineffective_states": [f"{case['instance_id']}:{case['band']}" for case in failed],
            "local_search_absorbed_gain_states": [
                f"{case['instance_id']}:{case['band']}" for case in candidate["cases"]
                if case.get("status") == "success"
                and case["candidate_repair"] < case["baseline_repair"] - 1e-9
                and case["candidate_after_local_search"] >= case["baseline_repair"] - 1e-9
            ],
            "suggested_revision": (
                "Use exact post-insertion Route-DP makespan deltas to break ties in the uncovered state classes; "
                "keep a distinct ordering strategy only when its gain survives the fixed local-search pass."
            ),
        })
    best_feedback = revision_feedback[0] if revision_feedback else {}
    revision_prompt = build_revision_prompt(
        operator_type="repair", round_id=1,
        previous_summary={
            "parent_hash": best_feedback.get("candidate_hash"),
            "effective_states": best_feedback.get("effective_states", []),
            "ineffective_states": best_feedback.get("ineffective_states", []),
            "local_search_absorbed_gain_states": best_feedback.get("local_search_absorbed_gain_states", []),
            "suggested_revision": best_feedback.get("suggested_revision", ""),
        },
        top_operators=[{"source_hash": row["hash"], "mean_post_local_search_gain": row["score"]}
                       for row in sorted((row for row in candidate_records if row.get("valid")),
                                         key=lambda row: row["score"], reverse=True)[:2]],
        weak_operators=[{"source_hash": row["hash"], "state_gains": row["gains"]}
                        for row in sorted((row for row in candidate_records if row.get("valid")),
                                          key=lambda row: row["score"])[:2]],
        evidence={"paired_route_dp_cases": best_feedback},
        n=int(config["llm"]["candidates_per_round"]),
    )
    artifact = {
        "schema_version": 1, "config": config, "manifest_sha256": _digest(manifest_path),
        "implementation_hashes": {
            name: _digest(project_root / relative)
            for name, relative in {
                "runner": "src/mrta_rect_coverage/experiments/operator_portfolio_evolution.py",
                "alns": "src/mrta_rect_coverage/heuristics/alns_solver.py",
                "route_dp": "src/mrta_rect_coverage/core/dp_evaluator.py",
                "priced_local_search": "src/mrta_rect_coverage/heuristics/priced_local_search.py",
                "candidate_security": "src/mrta_rect_coverage/llm/operator_evolution/candidate_security.py",
            }.items()
        },
        "baseline_runs": baseline_runs, "initialization_check": initialization_check,
        "cases": all_cases, "candidates": candidate_records,
        "selection": decision, "deployment": deployment,
        "revision_feedback": revision_feedback,
        "revision_prompt": revision_prompt,
        "llm_calls": 0, "llm_status": "no new provider authorization; historical E17 artifacts replayed",
        "candidate_evaluations": expected_candidate_evaluations,
        "stop_reason": (
            f"offline replay completed at max_rounds={config['max_rounds']}; "
            "candidate archive exhausted and the configured LLM call/token budget is zero"
        ),
    }
    artifact_path = project_root / config["output_dir"] / "portfolio_evolution.json"
    if artifact_path.exists():
        raise FileExistsError(f"preserving existing output; choose a fresh output_dir: {artifact_path}")
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact, indent=2, allow_nan=False), encoding="utf-8")
    return artifact


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    artifact = run(args.config)
    print(json.dumps(artifact["selection"], indent=2))


if __name__ == "__main__":
    main()
