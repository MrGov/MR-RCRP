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
from ..llm.prompts.operator_revision import build_paired_repair_revision_prompt

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


def select_behavioral_shortlist(
    candidates, *, anchor_hash: str, capacity: int, min_behavior_delta: float,
    max_runtime_ms: float | None = None,
):
    """Shortlist valid, non-dominated behaviors for matched short ALNS checks.

    Novelty is measured from paired Route-DP outcomes (pre/post local search and
    per-robot costs), never from source text or operator descriptions.
    """
    if capacity <= 0:
        return []
    anchor = next((item for item in candidates if item.get("hash") == anchor_hash), None)
    if not anchor or anchor.get("valid") is not True:
        return []

    def indexed_cases(item):
        cases = {}
        for row in item.get("cases", []):
            if row.get("status") != "success":
                return None
            key = (row.get("instance_id"), row.get("band"), row.get("case"))
            baseline = row.get("baseline_repair")
            candidate = row.get("candidate_repair")
            refined = row.get("candidate_after_local_search")
            base_costs = row.get("baseline_per_robot_costs")
            costs = row.get("per_robot_costs")
            if (not all(isinstance(value, (int, float)) for value in (baseline, candidate, refined))
                    or not isinstance(base_costs, list) or not isinstance(costs, list)
                    or len(base_costs) != len(costs)):
                return None
            cases[key] = (
                candidate - baseline,
                refined - baseline,
                *(cost - base for cost, base in zip(costs, base_costs)),
            )
        return cases or None

    anchor_cases = indexed_cases(anchor)
    if anchor_cases is None:
        return []
    options = []
    for item in candidates:
        if item is anchor or item.get("valid") is not True:
            continue
        if (max_runtime_ms is not None
                and float(item.get("runtime_ms", float("inf"))) > max_runtime_ms):
            continue
        cases = indexed_cases(item)
        if cases is None or cases.keys() != anchor_cases.keys():
            continue
        post_gains = [anchor_cases[key][1] - cases[key][1] for key in cases]
        # A behavior that is worse after the shared local-search pass on every
        # sampled state is not worth a short ALNS run, regardless of novelty.
        if not post_gains or max(post_gains) < -1e-9:
            continue
        novelty = max(
            sum(abs(a - b) for a, b in zip(cases[key], anchor_cases[key]))
            for key in cases
        )
        if novelty < min_behavior_delta:
            continue
        options.append((novelty, float(item.get("score", -1e12)), item))
    options.sort(key=lambda option: (option[0], option[1], option[2].get("hash", "")), reverse=True)
    return [
        {**item, "behavior_novelty": novelty,
         "shortlist_reason": "paired Route-DP outcome differs from anchor and is not dominated after fixed local search"}
        for novelty, _, item in options[:capacity]
    ]


def request_bounded_revisions(provider, prompt: str, *, round_id: int, n: int,
                              parent_hashes: list[str], call_budget: int,
                              token_budget: int, calls_used: int = 0,
                              tokens_used: int = 0, max_output_tokens: int = 1800):
    """Call the existing offline provider only after a per-run budget preflight."""
    if calls_used >= call_budget:
        raise RuntimeError("LLM call budget exhausted")
    estimated_input = (len(prompt) + 3) // 4
    reserved_output = max_output_tokens
    reserved_total = estimated_input + reserved_output
    if tokens_used + reserved_total > token_budget:
        raise RuntimeError("revision prompt exceeds the configured token budget")
    drafts = provider.revise_operator_candidates(
        prompt, {"parent_hashes": list(parent_hashes)}, n=n,
        operator_type="repair", round_id=round_id,
    )
    metadata = getattr(provider, "last_call_metadata", {})
    actual = metadata.get("total_tokens")
    charged_tokens = actual if isinstance(actual, (int, float)) else reserved_total
    provenance = {
        "round_id": round_id,
        "parent_hashes": list(parent_hashes),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "estimated_input_tokens": estimated_input,
        "reserved_output_tokens": reserved_output,
        "reserved_total_tokens": reserved_total,
        "actual_tokens": actual,
        "budget_tokens_charged": charged_tokens,
        "budget_exceeded": tokens_used + charged_tokens > token_budget,
        "calls_charged": 1,
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
    gains, raw_gains, runtimes, evaluation_runtimes, outcomes = [], [], [], [], []
    for case_id, item in enumerate(trace):
        case_started = perf_counter()
        dp_before = solver.route_dp.statistics()
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
            outcomes.append({"case": case_id, "status": result.status if result.status != "success" else "invalid_solution",
                             "error_message": getattr(result, "error_message", ""),
                             "instance_id": item["instance_id"], "band": item["band"]})
            gains.append(float("nan"))
            raw_gains.append(float("nan"))
            continue
        candidate_solution = result.result.solution
        baseline_eval = solver.solution_evaluator.evaluate(
            MultiRobotSolution(routes=[list(r) for r in item["baseline_repaired_routes"]])
        )
        candidate_eval = solver.solution_evaluator.evaluate(candidate_solution)
        raw_gains.append(baseline_eval.makespan - candidate_eval.makespan)
        baseline_ls_started = perf_counter()
        baseline_refined, baseline_refined_eval = solver.local_search(
            MultiRobotSolution(routes=[list(r) for r in item["baseline_repaired_routes"]])
        )
        baseline_local_search_ms = (perf_counter() - baseline_ls_started) * 1000
        candidate_ls_started = perf_counter()
        refined, refined_eval = solver.local_search(
            MultiRobotSolution(routes=[list(r) for r in candidate_solution.routes])
        )
        candidate_local_search_ms = (perf_counter() - candidate_ls_started) * 1000
        gains.append(baseline_refined_eval.makespan - refined_eval.makespan)

        def dp_trace(evaluation):
            return [
                {
                    "route_task_ids": route.route_task_ids,
                    "cost": route.total_cost,
                    "state_ids": route.chosen_state_ids,
                    "entry_points": route.entry_points,
                    "exit_points": route.exit_points,
                    "transition_costs": route.transition_costs,
                }
                for route in evaluation.route_evaluations
            ]

        dp_after = solver.route_dp.statistics()
        paired_evaluation_ms = (perf_counter() - case_started) * 1000
        evaluation_runtimes.append(paired_evaluation_ms)
        outcomes.append({
            "case": case_id, "status": "success", "band": item["band"],
            "instance_id": item["instance_id"],
            "baseline_repair": baseline_eval.makespan,
            "baseline_per_robot_costs": list(baseline_eval.per_robot_costs),
            "baseline_bottleneck_robot": max(range(len(baseline_eval.per_robot_costs)),
                                                key=baseline_eval.per_robot_costs.__getitem__),
            "baseline_after_local_search": baseline_refined_eval.makespan,
            "baseline_after_local_search_per_robot_costs": list(baseline_refined_eval.per_robot_costs),
            "candidate_repair": candidate_eval.makespan,
            "candidate_bottleneck_robot": max(range(len(candidate_eval.per_robot_costs)),
                                                 key=candidate_eval.per_robot_costs.__getitem__),
            "candidate_after_local_search": refined_eval.makespan,
            "per_robot_costs": list(candidate_eval.per_robot_costs),
            "after_local_search_per_robot_costs": list(refined_eval.per_robot_costs),
            "route_dp": {
                "baseline_repair": dp_trace(baseline_eval),
                "candidate_repair": dp_trace(candidate_eval),
                "baseline_after_local_search": dp_trace(baseline_refined_eval),
                "candidate_after_local_search": dp_trace(refined_eval),
            },
            "candidate_execution_ms": wall_ms,
            "baseline_local_search_ms": baseline_local_search_ms,
            "candidate_local_search_ms": candidate_local_search_ms,
            "paired_evaluation_ms": paired_evaluation_ms,
            "route_dp_calls": dp_after["calls"] - dp_before["calls"],
            "route_dp_cache_misses": dp_after["cache_misses"] - dp_before["cache_misses"],
        })
    valid = bool(gains) and all(value == value for value in gains)
    return {
        "valid": valid,
        "score": mean(gains) if valid else -1e12,
        "gains": gains if valid else [],
        "raw_repair_gains": [value if value == value else None for value in raw_gains],
        "runtime_ms": mean(runtimes) if runtimes else 0.0,
        "paired_evaluation_runtime_ms": mean(evaluation_runtimes) if evaluation_runtimes else 0.0,
        "route_dp_calls": sum(row.get("route_dp_calls", 0) for row in outcomes),
        "route_dp_cache_misses": sum(row.get("route_dp_cache_misses", 0) for row in outcomes),
        "cases": outcomes,
    }


def _revision_gap_feedback(candidates, selected_hashes, cases, *, max_states: int = 3):
    """Summarize unresolved paired states without attributing pair rewards."""
    selected = {item["hash"]: item for item in candidates if item["hash"] in selected_hashes}
    feedback = {
        "feedback_source": "development paired-repair Route-DP outcomes",
        "current_generated_members": [
            {"hash": item["hash"], "score": item["score"]} for item in selected.values()
        ],
        "manual_pool": ["greedy_insertion", "regret_k_insertion", "bottleneck_balancing_insertion"],
        "selection_reward_attribution": (
            "ALNS iteration reward is shared by the selected destroy/repair pair; it is not a repair-only effect. "
            "The state records below are paired repair outcomes against the manual repair selected on that trace."
        ),
        "candidate_runtime_constraint_ms": 500.0,
        "unresolved_states": [],
    }
    unresolved = []
    for member in selected.values():
        for row in member.get("cases", []):
            if row.get("status") != "success":
                continue
            post_gain = row["baseline_after_local_search"] - row["candidate_after_local_search"]
            if post_gain > 1e-9:
                continue
            unresolved.append((post_gain, member, row))
    unresolved.sort(key=lambda item: (item[0], item[1]["hash"], item[2]["case"]))
    case_index = {
        (row["instance_id"], row["band"]): row for row in cases
    }
    for post_gain, member, row in unresolved[:max_states]:
        state = case_index.get((row["instance_id"], row["band"]), {})
        feedback["unresolved_states"].append({
            "candidate_hash": member["hash"],
            "instance_id": row["instance_id"], "band": row["band"],
            "partial_routes": state.get("partial_routes"),
            "removed_tasks": state.get("removed_tasks"),
            "manual_repair_operator": state.get("baseline_repair_operator"),
            "baseline_fallback_used": state.get("baseline_fallback_used"),
            "trace_iteration": state.get("trace_iteration"),
            "repair_makespans": {
                "manual": row["baseline_repair"], "candidate": row["candidate_repair"],
                "manual_after_fixed_local_search": row["baseline_after_local_search"],
                "candidate_after_fixed_local_search": row["candidate_after_local_search"],
                "candidate_gain_after_local_search": post_gain,
            },
            "per_robot_costs": {
                "partial": state.get("partial_costs"),
                "manual": row["baseline_per_robot_costs"],
                "candidate": row["per_robot_costs"],
                "manual_after_fixed_local_search": row["baseline_after_local_search_per_robot_costs"],
                "candidate_after_fixed_local_search": row["after_local_search_per_robot_costs"],
            },
            "bottleneck_robot": {
                "manual": row["baseline_bottleneck_robot"],
                "candidate": row["candidate_bottleneck_robot"],
            },
            "route_dp_state_chain": row["route_dp"],
            "evaluation_cost": {
                key: row[key] for key in (
                    "candidate_execution_ms", "baseline_local_search_ms",
                    "candidate_local_search_ms", "paired_evaluation_ms",
                    "route_dp_calls", "route_dp_cache_misses",
                )
            },
            "interpretation_limit": (
                "Route-DP optimizes state chains for each recorded route; it does not make this repair outcome "
                "a joint marginal contribution of the full ALNS portfolio."
            ),
        })
    return feedback


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
            "gains": [], "cases": [], "runtime_samples": [],
            "evaluation_runtime_samples": [], "route_dp_calls": 0,
            "route_dp_cache_misses": 0, "valid": True,
        }
        for candidate in source_candidates
    }
    initialization_check = []
    for entry in screen_entries:
        instance = load_instance(project_root / "data/structural_benchmark_v1" / entry["path"])
        for constructor in ("spatial_sort", "dp_greedy"):
            started = perf_counter()
            initial_solver = ALNSSolver(instance, constructor=constructor,
                                        config=ALNSConfig(iterations=0, random_seed=int(config["seed"])))
            initial_eval = initial_solver.solution_evaluator.evaluate(initial_solver.initial_solution)
            initialization_check.append({
                "instance_id": entry["instance_id"], "role": "development_selection",
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
            partial = MultiRobotSolution(routes=[list(r) for r in row["partial_routes"]])
            partial_eval = solver.solution_evaluator.evaluate_partial(partial)
            # Use the exact repair output from this ALNS iteration, not a replay
            # that could diverge through stateful/random implementation details.
            baseline_repaired_routes = [list(route) for route in row["repaired_routes"]]
            instance_cases.append({
                "instance_id": entry["instance_id"], "band": band,
                "partial_routes": partial.routes, "removed_tasks": row["removed_tasks"],
                "partial_costs": partial_eval.per_robot_costs,
                "baseline_repaired_routes": baseline_repaired_routes,
                "baseline_repair_operator": row["repair"],
                "baseline_fallback_used": row["fallback_used"],
                "trace_iteration": row["iteration"],
                "trace_seed": int(config["seed"]),
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
            acc["evaluation_runtime_samples"].append(metrics["paired_evaluation_runtime_ms"])
            acc["route_dp_calls"] += metrics["route_dp_calls"]
            acc["route_dp_cache_misses"] += metrics["route_dp_cache_misses"]

    candidate_records = []
    for item in candidate_accumulator.values():
        item["score"] = mean(item["gains"]) if item["valid"] and item["gains"] else -1e12
        item["runtime_ms"] = mean(item.pop("runtime_samples")) if item["gains"] else 0.0
        evaluation_samples = item.pop("evaluation_runtime_samples")
        item["paired_evaluation_runtime_ms"] = mean(evaluation_samples) if evaluation_samples else 0.0
        if not item["valid"]:
            item["gains"] = []
        candidate_records.append(item)

    selection = select_complementary_repairs(
        candidate_records, capacity=int(config["deployment_capacity"]),
        min_gain=max(float(config["min_state_gain"]), float(config["minimum_effective_improvement"]))
    )
    top_k = sorted((row for row in candidate_records if row.get("valid")),
                   key=lambda row: row["score"], reverse=True)[:int(config["deployment_capacity"])]
    anchor_hash = top_k[0]["hash"] if top_k else ""
    behavioral_shortlist = select_behavioral_shortlist(
        candidate_records, anchor_hash=anchor_hash,
        capacity=int(config.get("behavior_shortlist_capacity", 2)),
        min_behavior_delta=float(config.get("min_behavior_delta", 2.0)),
        max_runtime_ms=float(config.get("max_candidate_runtime_ms", 500.0)),
    )
    decision = {
        "method": "problem-state coverage greedy complementarity; mean post-local-search gain is the per-state utility",
        "selected_hashes": [row["hash"] for row in selection],
        "top_k_hashes": [row["hash"] for row in top_k],
        "selection_matches_top_k": [row["hash"] for row in selection] == [row["hash"] for row in top_k],
        "behavioral_shortlist_hashes": [row["hash"] for row in behavioral_shortlist],
        "behavioral_shortlist_rule": (
            "paired Route-DP outcome vectors differ from the best valid anchor by the configured threshold; "
            "candidate is feasible, under its measured execution-time cap, and not dominated after identical local search; "
            "short ALNS decides inclusion"
        ),
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
    for row in behavioral_shortlist:
        if row["hash"] != anchor_hash:
            run_sets[f"behavior_add_{row['hash'][:8]}"] = [anchor_hash, row["hash"]]
    selected_source = {item["hash"]: item for item in source_candidates}

    def run_deployment_case(method, hashes, entry, role):
        instance = load_instance(project_root / "data/structural_benchmark_v1" / entry["path"])
        solver = ALNSSolver(instance, config=ALNSConfig.enhanced(
            iterations=None,
            max_runtime_seconds=float(config["deployment_runtime_seconds"]),
            random_seed=int(config["seed"]),
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
        initial_weights = dict(solver.repair_weights)
        result = solver.solve()
        repair_stats = result.operator_usage_stats["repair"]
        return {
            "method": method, "instance_id": entry["instance_id"], "role": role,
            "makespan": result.best_evaluation.makespan,
            "runtime_seconds": result.runtime_seconds,
            "wall_clock_budget_seconds": solver.config.max_runtime_seconds,
            "iterations": result.iterations_completed,
            "initial_repair_weights": initial_weights,
            "selection_and_reward": {
                "selection": "minimum-use exploration then independent roulette over adaptive repair weights",
                "minimum_uses": solver.config.operator_minimum_uses,
                "iteration_rewards": "8 global best, 3 current improvement, 1 accepted; shared by selected destroy/repair",
                "weight_update": "segment-reactive mean reward with a weight floor; same ALNS policy for every group",
            },
            "operator_stats": {
                name: {
                    "calls": record.uses,
                    "shared_iteration_reward": record.score,
                    "accepted_iterations": sum(
                        row["repair"] == name and row["accepted"] for row in result.iteration_history
                    ),
                    "global_best_improvements": sum(
                        row["repair"] == name and row["score_raw"] >= 8.0 for row in result.iteration_history
                    ),
                    "execution_seconds": result.operator_time_stats["repair"][name][0],
                }
                for name, record in repair_stats.items()
            },
            "fallback_events": len(result.fallback_events),
            "repair_hashes": hashes,
            "exploration_minimum_uses": solver.config.operator_minimum_uses if hashes else 0,
        }

    for method, hashes in run_sets.items():
        for entry in screen_entries:
            deployment.append(run_deployment_case(method, hashes, entry, "development_selection"))
    candidate_groups = ["single_champion", "complementary", "single_score_top_k", *[
        name for name in run_sets if name.startswith("behavior_add_")
    ]]
    group_means = {
        name: mean(row["makespan"] for row in deployment
                   if row["method"] == name and row["role"] == "development_selection")
        for name in candidate_groups
        if any(row["method"] == name for row in deployment)
        and all(row["fallback_events"] == 0 for row in deployment
                if row["method"] == name and row["role"] == "development_selection")
    }
    deployed_method = min(group_means, key=group_means.get) if group_means else "manual_pool"
    decision["short_alns_group_means"] = group_means
    decision["deployed_method"] = deployed_method
    decision["deployed_hashes"] = run_sets.get(deployed_method, [])
    decision["deployment_reason"] = (
        "lowest mean makespan among feasible, no-fallback matched short-ALNS groups on selection instances; "
        "the behavior shortlist is a diagnostic comparison, not an automatic portfolio slot"
    )
    if check_entries:
        # This one held-aside development check is run only after the composition
        # is frozen from selection data; it cannot change the deployment choice.
        deployment.append(run_deployment_case(
            deployed_method, run_sets.get(deployed_method, []), check_entries[0],
            "round_heldout_development_check",
        ))
    revision_feedback = _revision_gap_feedback(
        candidate_records, decision["deployed_hashes"] or ([anchor_hash] if anchor_hash else []), all_cases
    )
    revision_parent_hash = (
        revision_feedback["unresolved_states"][0]["candidate_hash"]
        if revision_feedback["unresolved_states"] else anchor_hash
    )
    revision_parent = next((row for row in candidate_records if row["hash"] == revision_parent_hash), None)
    if revision_parent is None:
        raise RuntimeError("no generated repair parent is available for a bounded revision prompt")
    revision_prompt = build_paired_repair_revision_prompt(
        parent={"operator_id": revision_parent["id"],
                "source_path": str(project_root / revision_parent["path"]),
                "source_hash": revision_parent["hash"]},
        feedback=revision_feedback,
        n=1,
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
        "revision_parent_hash": revision_parent_hash,
        "revision_prompt": revision_prompt,
        "revision_prompt_sha256": hashlib.sha256(revision_prompt.encode("utf-8")).hexdigest(),
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
