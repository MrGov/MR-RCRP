"""Small, development-only real-provider operator evolution pilot.

This module deliberately keeps E1 separate from the historical offline runner:
only repair operators, manifest-scoped development instances, and equal F1/F2
budgets are supported.  It does not freeze or deploy generated operators.
"""
from __future__ import annotations

import hashlib
import csv
import json
from importlib.metadata import PackageNotFoundError, version
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import Any, Mapping, Sequence

from ..core.instance_loader import load_instance
from ..core.models import MultiRobotSolution
from ..experiments.dataset_protocol import load_manifest
from ..llm.operator_evolution.candidate_loader import (
    load_and_validate_candidate,
    persist_operator_drafts,
)
from ..llm.operator_evolution.evaluator import (
    _fixed_greedy_repair,
    build_repair_benchmark_cases,
)
from ..llm.operator_evolution.provider_factory import build_provider
from ..llm.operator_evolution.schemas import GeneratedOperatorDraft
from ..llm.operator_evolution import prompt_builder
from ..llm.operator_evolution.protocols import RepairContext
from ..llm.operator_evolution.utils import clone_solution
from ..experiments.r3_diagnostics import state_chain_diff, state_chain_signatures


@dataclass
class E1PilotConfig:
    project_root: Path
    manifest_path: Path | None
    output_dir: Path = Path("outputs/e1_real_llm_pilot")
    provider_name: str = "langchain_openai_compatible"
    generations: int = 2
    candidates_per_generation: int = 2
    solver_seeds: tuple[int, ...] = (0, 1)
    timeout_ms: float = 2000.0
    max_provider_calls: int = 4
    development_instance_paths: tuple[Path, ...] = ()
    modes: tuple[str, ...] = ("F1", "F2")
    resume: bool = False
    shared_f1_initial_pool: bool = False
    continue_on_provider_error: bool = False

    def __post_init__(self) -> None:
        if self.generations != 2 or self.candidates_per_generation < 1:
            raise ValueError("E1 requires exactly two generations and at least one candidate")
        if not self.solver_seeds:
            raise ValueError("E1 requires at least one solver seed")
        if self.max_provider_calls != self.generations * len(self.modes):
            raise ValueError("provider call budget must match generations times feedback modes")


def load_development_instance_paths(manifest_path: Path) -> list[Path]:
    """Return only paths recorded by a development manifest."""
    try:
        manifest = load_manifest(manifest_path, expected_split="development")
    except ValueError as exc:
        raise ValueError(f"manifest is not a development manifest: {exc}") from exc
    root = manifest_path.parent.parent.resolve()
    paths: list[Path] = []
    for entry in manifest["entries"]:
        if entry.get("split") != "development":
            raise ValueError("development manifest contains a non-development entry")
        candidate = (root / entry["file_path"]).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ValueError("development manifest path escapes dataset root") from exc
        if not candidate.is_file():
            raise ValueError(f"development instance is missing: {candidate}")
        paths.append(candidate)
    return paths


def compute_exact_dp_behavior(
    before_solution: MultiRobotSolution,
    after_solution: MultiRobotSolution,
    before_evaluation: Any,
    after_evaluation: Any,
    *,
    instance: Any | None = None,
) -> dict[str, float | int]:
    """Compute E1 behavior fields using the canonical R3 state-chain helper."""
    before_signatures = state_chain_signatures(before_evaluation)
    after_signatures = state_chain_signatures(after_evaluation)
    before_routes = {
        task_id: route_id
        for route_id, route in enumerate(before_solution.routes)
        for task_id in route
    }
    after_routes = {
        task_id: route_id
        for route_id, route in enumerate(after_solution.routes)
        for task_id in route
    }
    affected = set(before_signatures) | set(after_signatures)
    directly_moved = {
        task_id
        for task_id in affected
        if before_routes.get(task_id) != after_routes.get(task_id)
    }
    diff = state_chain_diff(
        before_signatures,
        after_signatures,
        affected_task_ids=affected,
        directly_moved_task_ids=directly_moved,
    )
    denominator = max(1, len(affected))
    result: dict[str, float | int] = {
        "dp_state_switch_fraction": float(diff["state_changed_fraction"]),
        "hv_mode_switch_fraction": float(diff["mode_switch_fraction"]),
        "entry_corner_switch_fraction": float(diff["entry_corner_changed_count"]) / denominator,
        "exit_corner_switch_fraction": float(diff["exit_corner_changed_count"]) / denominator,
        "dp_cascade_count": int(diff["cascade_count"]),
        "dp_cascade_ratio": float(diff["dp_cascade_ratio"]),
    }
    if instance is not None:
        from .r3_diagnostics import objective_decomposition

        before_obj = objective_decomposition(instance, before_evaluation)
        after_obj = objective_decomposition(instance, after_evaluation)
        result.update(
            {
                "bottleneck_relief": float(before_evaluation.makespan - after_evaluation.makespan),
                "travel_change": float(after_obj["travel_time"] - before_obj["travel_time"]),
                "coverage_change": float(
                    after_obj["coverage_traversal_time"] - before_obj["coverage_traversal_time"]
                ),
                "turning_change": float(after_obj["turning_time"] - before_obj["turning_time"]),
            }
        )
    return result


def build_f1_feedback(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Build scalar/top-weak feedback without DP behavior fields."""
    ranked = sorted(rows, key=lambda row: float(row.get("avg_relative_improvement", 0.0)), reverse=True)
    top_count = min(2, (len(ranked) + 1) // 2)
    weak_count = min(2, len(ranked) - top_count)
    return {
        "feedback_mode": "F1",
        "summary": _scalar_summary(rows),
        "top_candidates": [_feedback_row(row) for row in ranked[:top_count]],
        "weak_candidates": [_feedback_row(row) for row in ranked[-weak_count:]] if weak_count else [],
    }


def build_f2_feedback(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Build F1 feedback augmented with deterministic Exact-DP response."""
    payload = build_f1_feedback(rows)
    payload["feedback_mode"] = "F2"
    payload["behavior_diagnosis"] = build_behavior_diagnosis(rows)
    return payload


def build_f2d_feedback(rows: Sequence[Mapping[str, Any]], *, parent: Mapping[str, Any],
                      source_reference: str) -> dict[str, Any]:
    """F1 scalar base plus measured, parent-specific decision knowledge."""
    from ..llm.operator_evolution.feedback_builder import select_decision_knowledge
    payload = build_f1_feedback(rows)
    payload["feedback_mode"] = "F2-D"
    payload["decision_knowledge"] = select_decision_knowledge(
        list(rows), parent_id=parent["operator_id"],
        parent_source=Path(parent["source_path"]).read_text(encoding="utf-8"),
        source_reference=source_reference)
    return payload


def build_f2g_feedback(rows: Sequence[Mapping[str, Any]], *, parent: Mapping[str, Any],
                      diagnosed_operator: Mapping[str, Any], source_reference: str) -> dict[str, Any]:
    """F1 scalar feedback plus the focused E4-B coverage-workload knowledge."""
    from ..llm.operator_evolution.feedback_builder import coverage_mode_knowledge
    payload = build_f1_feedback(rows)
    payload["feedback_mode"] = "F2-G"
    payload["geometry_knowledge"] = coverage_mode_knowledge(
        parent=dict(parent), diagnosed_operator=dict(diagnosed_operator), source_reference=source_reference)
    return payload


def build_behavior_diagnosis(rows: Sequence[Mapping[str, Any]]) -> str:
    """Condense evaluator-derived trials into cautious revision guidance."""
    trials = [
        (str(row.get("operator_id", "")), trial)
        for row in rows
        for trial in row.get("trials", [])
        if trial.get("feasible") and isinstance(trial.get("exact_dp_behavior"), Mapping)
    ]
    if not trials:
        return "Exact-DP behavior unavailable: no feasible evaluated trial. Do not infer DP effects."
    ordered = sorted(trials, key=lambda pair: float(pair[1]["relative_improvement"]))
    selected = [ordered[0]]
    if len(ordered) > 1 and ordered[-1] != ordered[0]:
        selected.append(ordered[-1])
    if len(ordered) > 2 and ordered[len(ordered) // 2] not in selected:
        selected.append(ordered[len(ordered) // 2])
    changes = [float(trial['relative_improvement']) for _, trial in trials]
    lines = [
        f"Feasible trial summary: {sum(v > 1e-9 for v in changes)} improved, "
        f"{sum(v < -1e-9 for v in changes)} degraded, "
        f"{sum(abs(v) <= 1e-9 for v in changes)} tied; "
        f"mean relative improvement {mean(changes):+.4f}.",
        "Evaluator-derived representative cases (associations only, not causal proof):",
    ]
    for operator_id, trial in selected:
        dp = trial["exact_dp_behavior"]
        lines.append(
            f"- {operator_id} on {trial['instance_id']} seed {trial['solver_seed']}: "
            f"baseline {trial['baseline_makespan']:.3f}, candidate {trial['candidate_makespan']:.3f}, "
            f"makespan relief {trial['baseline_makespan'] - trial['candidate_makespan']:.3f}; "
            f"DP state switches {float(dp.get('dp_state_switch_fraction', 0.0)):.3f}, "
            f"H/V switches {float(dp.get('hv_mode_switch_fraction', 0.0)):.3f}, "
            f"cascade ratio {float(dp.get('dp_cascade_ratio', 0.0)):.3f}, "
            f"travel/coverage/turning changes "
            f"{float(dp.get('travel_change', 0.0)):+.3f}/"
            f"{float(dp.get('coverage_change', 0.0)):+.3f}/"
            f"{float(dp.get('turning_change', 0.0)):+.3f}."
        )
        if 'candidate_route_costs' in trial:
            lines.append(
                f"  Route costs {trial['baseline_route_costs']} -> {trial['candidate_route_costs']}; "
                f"reassigned tasks {trial['reassigned_task_count']}. "
                "Cost-component changes are solution totals; makespan is the maximum route cost."
            )
        if float(trial['relative_improvement']) < -1e-9:
            lines.append(
                "  Inspect insertion order and route slack: reassignment/state changes accompanied "
                "a worse bottleneck. Avoid chasing aggregate travel savings at the expense of the slowest route."
            )
        elif float(dp.get('hv_mode_switch_fraction', 0)) > 0:
            lines.append(
                "  H/V changes accompanied this repair; inspect geometric insertion neighbours "
                "and coverage/turning trade-offs while leaving state choice to Exact-DP."
            )
    lines.append(
        "Consider whether insertion order or bottleneck-route load balancing may be worth revising; "
        "retain full-solution feasibility and exact makespan as final criteria. "
        "Do not invent DP measurements or replace the Route-DP evaluator."
    )
    return "\n".join(lines)


def revision_prompt(parent: Mapping[str, Any], feedback: Mapping[str, Any], *, round_id: int = 1, n: int = 2) -> str:
    """Build a parent-grounded revision request from evaluated Round 0 evidence."""
    parent_path = Path(parent["source_path"])
    source = parent_path.read_text(encoding="utf-8")
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    if digest != parent["source_hash"]:
        raise ValueError("parent source hash changed before revision")
    mode = feedback["feedback_mode"]
    scalar = {
        "summary": feedback["summary"],
        "top_candidates": feedback["top_candidates"],
        "weak_candidates": feedback["weak_candidates"],
    }
    trials = [{key: trial.get(key) for key in (
        "instance_id", "solver_seed", "baseline_makespan", "candidate_makespan",
        "relative_improvement", "feasible")}
        for trial in parent.get("trials", [])]
    diagnosis = (f"Behavioral diagnosis (F2 only):\n{feedback['behavior_diagnosis']}\n"
                 if mode == "F2" else "")
    if mode == "F2-D":
        diagnosis = "Decision-oriented evaluator evidence and revision directions:\n" + json.dumps(feedback["decision_knowledge"], sort_keys=True) + "\n"
    if mode == "F2-G":
        diagnosis = "Coverage-mode-aware workload knowledge (authoritative scope and formulas):\n" + json.dumps(feedback["geometry_knowledge"], sort_keys=True) + "\n"
    return (
        f"E2 feedback mode: {mode}\nParent candidate ID: {parent['operator_id']}\n"
        f"Parent source SHA-256: {digest}\nParent source:\n```python\n{source}\n```\n"
        f"Parent evaluated performance: {json.dumps(trials, sort_keys=True)}\n"
        f"Scalar feedback: {json.dumps(scalar, sort_keys=True)}\n{diagnosis}"
        "Revise this actual parent to improve feasible makespan by better insertion order "
        "or bottleneck load balancing. Treat observed DP changes as associations, not causal proof. "
        "Do not infer DP effects without measurements. Preserve the exact interface "
        "repair(partial_solution, unassigned_tasks, context, rng) -> RepairResult. "
        "Return complete solutions and leave coverage state optimization to Exact Route-DP.\n"
        + prompt_builder.build_revision_prompt(
            operator_type="repair", round_id=round_id,
            previous_summary=feedback["summary"],
            top_operators=feedback["top_candidates"],
            weak_operators=feedback["weak_candidates"],
            n=n,
        )
        + ("\nF2-G scope reminder: apply the coverage-workload formulas to actual insertion workload and bottleneck hints; use only the listed real context attributes. No evaluator is exposed. Do not add mode-switch penalties or reimplement Route-DP. The geometry knowledge above overrides generic heuristic suggestions.\n" if mode == "F2-G" else "")
    )


def classify_provider_error(error: object) -> str:
    """Map a preflight/provider failure to the E1 blocker taxonomy."""
    message = str(error).lower()
    if "401" in message or "403" in message or "unauthorized" in message or "forbidden" in message:
        return "PROVIDER_AUTH_BLOCKER"
    if "429" in message or "rate limit" in message or "quota" in message:
        return "PROVIDER_RATE_OR_QUOTA_BLOCKER"
    if "404" in message or "model-not-found" in message or "endpoint-not-found" in message:
        return "PROVIDER_ENDPOINT_OR_MODEL_BLOCKER"
    if (
        "400" in message
        or "422" in message
        or "unsupported_parameter" in message
        or "invalid parameter" in message
        or "temperature" in message and "support" in message
    ):
        return "PROVIDER_REQUEST_COMPATIBILITY_BLOCKER"
    if "timeout" in message or "timed out" in message or "connection" in message:
        return "PROVIDER_NETWORK_BLOCKER"
    return "PROVIDER_RUNTIME_BLOCKER"


def run_provider_preflight(*, project_root: Path, output_dir: Path) -> dict[str, Any]:
    """Send the minimal E1 Responses-path probe and persist redacted evidence."""
    from ..llm.runtime.config import load_from_env

    cfg = load_from_env()
    target = output_dir if output_dir.is_absolute() else project_root / output_dir
    target.mkdir(parents=True, exist_ok=True)
    redacted = {
        "provider": cfg.provider,
        "base_url": cfg.base_url,
        "model": cfg.model,
        "temperature_requested": cfg.temperature,
        "timeout": cfg.timeout,
        "max_retries": cfg.max_retries,
        "api_key_configured": bool(cfg.api_key),
        "wire_protocol": "Responses API",
    }
    (target / "provider_config_redacted.json").write_text(
        json.dumps(redacted, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    result: dict[str, Any] = {
        "request": "Reply exactly with: OK",
        "success": False,
        "provider": cfg.provider,
        "model": cfg.model,
        "wire_protocol": "Responses API",
        "sdk_versions": {
            name: _package_version(name)
            for name in ("langchain-openai", "langchain-core", "openai")
        },
    }
    if cfg.provider != "langchain_openai_compatible" or not cfg.api_key:
        result["blocker"] = "PROVIDER_CONFIG_BLOCKER"
        (target / "preflight.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return result
    try:
        provider = build_provider(
            cfg.provider,
            raw_response_dir=target / "raw_responses",
        )
        started = perf_counter()
        response_text = provider._invoke("Reply exactly with: OK")
        elapsed_ms = (perf_counter() - started) * 1000.0
        metadata = dict(getattr(provider, "last_call_metadata", {}) or {})
        (target / "preflight_response.txt").write_text(response_text, encoding="utf-8")
        result.update(
            {
                "success": bool(response_text.strip()),
                "response_text": response_text,
                "latency_ms": elapsed_ms,
                "provider_metadata": metadata,
                "temperature_sent": metadata.get("temperature_sent"),
                "status": "ok",
            }
        )
    except Exception as exc:  # noqa: BLE001 - classify external provider errors.
        result.update(
            {
                "blocker": classify_provider_error(exc),
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            }
        )
    (target / "preflight.json").write_text(
        json.dumps(result, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
    return result


def _package_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def run_e1_pilot(config: E1PilotConfig, *, provider: Any | None = None) -> dict[str, Any]:
    """Run equal-budget F1/F2 E1 branches and persist an auditable summary."""
    instance_paths = (list(config.development_instance_paths) if config.development_instance_paths
                      else load_development_instance_paths(config.manifest_path))
    output_root = config.output_dir if config.output_dir.is_absolute() else config.project_root / config.output_dir
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "metadata.json").write_text(
        json.dumps(
            {
                "phase": "E1",
                "development_instance_count": len(instance_paths),
                "development_instances": [path.as_posix() for path in instance_paths],
                "provider_name": config.provider_name,
                "generations": config.generations,
                "candidates_per_generation": config.candidates_per_generation,
                "solver_seeds": list(config.solver_seeds),
                "final_test_accessed": False,
                "heldout_accessed": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    if config.provider_name == "langchain_openai_compatible":
        from ..llm.runtime.config import load_from_env

        runtime = load_from_env()
        provider_config = {
            "provider": runtime.provider,
            "model": runtime.model,
            "base_url": runtime.base_url,
            "temperature": runtime.temperature,
            "timeout": runtime.timeout,
            "max_retries": runtime.max_retries,
            "api_key_configured": bool(runtime.api_key),
        }
    else:
        provider_config = {"provider": config.provider_name, "api_key_configured": False}
    (output_root / "provider_config_redacted.json").write_text(
        json.dumps(provider_config, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    total_provider_calls = 0
    branch_summaries: dict[str, Any] = {}
    previous_prompt_mode = prompt_builder.use_rich_prompts
    prompt_builder.use_rich_prompts = True
    try:
        for mode in config.modes:
            branch = output_root / mode
            for name in ("prompts", "raw_responses", "generated", "parsed_candidates"):
                (branch / name).mkdir(parents=True, exist_ok=True)
            if provider is None:
                branch_provider = build_provider(
                    config.provider_name,
                    raw_response_dir=branch / "raw_responses",
                )
            else:
                branch_provider = provider
            if mode == "F2" and config.shared_f1_initial_pool and not (branch / "candidate_metrics.jsonl").exists():
                source_branch = output_root / "F1"
                initial_rows = [json.loads(line) for line in (source_branch / "candidate_metrics.jsonl").read_text(encoding="utf-8").splitlines()
                                if json.loads(line)["generation"] == 0]
                for row in initial_rows:
                    row["feedback_mode"] = "F2"
                    row["shared_initial_pool_from"] = "F1"
                (branch / "candidate_metrics.jsonl").write_text("".join(json.dumps(row) + "\n" for row in initial_rows), encoding="utf-8")
                (branch / "feedback_round_000.json").write_text(json.dumps(build_f2_feedback(initial_rows), indent=2), encoding="utf-8")
                for filename in ("trial_metrics.jsonl", "validation_results.jsonl", "behavior_profiles.jsonl", "provider_calls.jsonl"):
                    records = [json.loads(line) for line in (source_branch / filename).read_text(encoding="utf-8").splitlines()]
                    records = [r for r in records if r.get("generation", r.get("round_id")) == 0]
                    if filename == "provider_calls.jsonl":
                        for record in records:
                            record["metadata"] = {"shared_call_from": "F1 Round 0", "actual_provider_call": False}
                    (branch / filename).write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
                (branch / "lineage.jsonl").write_text("", encoding="utf-8")
                (branch / "prompts" / "round_000.txt").write_text((source_branch / "prompts" / "round_000.txt").read_text(encoding="utf-8"), encoding="utf-8")
            try:
                branch_summary, calls = _run_branch(config, branch_provider, mode, instance_paths, branch)
            except Exception as exc:
                if not config.continue_on_provider_error:
                    raise
                failure = {"status": "incomplete", "error_type": type(exc).__name__, "error": str(exc)}
                (branch / "failure.json").write_text(json.dumps(failure, indent=2), encoding="utf-8")
                branch_summaries[mode] = failure
                continue
            if (branch / "failure.json").exists():
                previous_failure = json.loads((branch / "failure.json").read_text(encoding="utf-8"))
                if previous_failure.get("status") == "incomplete":
                    (branch / "failure.json").write_text(json.dumps({"status": "recovered", "previous_error": previous_failure}), encoding="utf-8")
            total_provider_calls += calls
            branch_summaries[mode] = branch_summary
    finally:
        prompt_builder.use_rich_prompts = previous_prompt_mode

    summary = {
        "phase": "E1",
        "development_instance_count": len(instance_paths),
        "provider_calls": total_provider_calls,
        "branches": branch_summaries,
        "equal_budget": all("provider_calls" in item for item in branch_summaries.values()) and len({item["provider_calls"] for item in branch_summaries.values()}) == 1,
        "complete": all("provider_calls" in item for item in branch_summaries.values()),
    }
    with (output_root / "budget_ledger.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("feedback_mode", "provider_calls", "candidate_budget", "evaluation_budget"),
        )
        writer.writeheader()
        for mode, branch_summary in branch_summaries.items():
            writer.writerow(
                {
                    "feedback_mode": mode,
                    "provider_calls": branch_summary.get("provider_calls"),
                    "candidate_budget": config.generations * config.candidates_per_generation,
                    "evaluation_budget": config.generations * config.candidates_per_generation * len(instance_paths) * len(config.solver_seeds),
                }
            )
    (output_root / "pilot_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
    return summary


def _run_branch(config, provider, mode, instance_paths, branch) -> tuple[dict[str, Any], int]:
    cases = build_repair_benchmark_cases(instance_paths)
    feedback: dict[str, Any] | None = None
    previous_best: dict[str, Any] | None = None
    all_rows: list[dict[str, Any]] = []
    provider_records: list[dict[str, Any]] = []
    lineage_path = branch / "lineage.jsonl"
    validation_path = branch / "validation_results.jsonl"
    trials_path = branch / "trial_metrics.jsonl"
    behavior_path = branch / "behavior_profiles.jsonl"
    provider_calls_path = branch / "provider_calls.jsonl"
    start_generation = 0
    if config.resume and (branch / "candidate_metrics.jsonl").exists():
        all_rows = [json.loads(line) for line in (branch / "candidate_metrics.jsonl").read_text(encoding="utf-8").splitlines()]
        completed = sorted({row["generation"] for row in all_rows})
        if completed == list(range(len(completed))):
            start_generation = len(completed)
            if completed:
                feedback = json.loads((branch / f"feedback_round_{completed[-1]:03d}.json").read_text(encoding="utf-8"))
                eligible = [row for row in all_rows if row["generation"] == completed[-1] and row.get("feasible_count", 0) > 0]
                previous_best = max(eligible, key=lambda row: float(row["avg_relative_improvement"])) if eligible else None
            provider_records = [json.loads(line)["metadata"] for line in provider_calls_path.read_text(encoding="utf-8").splitlines()]
        else:
            raise ValueError("cannot resume non-contiguous evolution generations")
    if start_generation == 0:
        for path in (lineage_path, validation_path, trials_path, behavior_path, provider_calls_path):
            path.write_text("", encoding="utf-8")
    calls = len(provider_records)
    for generation in range(start_generation, config.generations):
        if generation == 0 or mode == "L0":
            prompt = prompt_builder.build_initial_generation_prompt(
                operator_type="repair", round_id=generation
            )
            prompt = f"E2 feedback mode: {mode}\nDevelopment-only repair pilot.\n{prompt}"
            (branch / "prompts" / f"round_{generation:03d}.txt").write_text(prompt, encoding="utf-8")
            drafts = provider.generate_operator_candidates(
                prompt, config.candidates_per_generation, "repair", generation
            )
        else:
            assert feedback is not None
            if previous_best is None:
                raise RuntimeError("Round 1 requires a persisted Round 0 parent")
            prompt = revision_prompt(previous_best, feedback, round_id=generation,
                                     n=config.candidates_per_generation)
            (branch / "prompts" / f"round_{generation:03d}.txt").write_text(prompt, encoding="utf-8")
            drafts = provider.revise_operator_candidates(
                prompt, feedback, config.candidates_per_generation, "repair", generation
            )
        calls += 1
        with provider_calls_path.open("a", encoding="utf-8") as handle:
            call_metadata = dict(getattr(provider, "last_call_metadata", {}) or {})
            provider_records.append(call_metadata)
            handle.write(
                json.dumps(
                    {
                        "generation": generation,
                        "feedback_mode": mode,
                        "phase": "generate" if generation == 0 or mode == "L0" else "revise",
                        "metadata": call_metadata,
                    },
                    sort_keys=True,
                    default=str,
                )
                + "\n"
            )
        generated_dir = branch / "generated" / f"round_{generation:03d}"
        generated_dir.mkdir(parents=True, exist_ok=True)
        persisted = persist_operator_drafts(generated_dir, list(drafts))
        rows: list[dict[str, Any]] = []
        for path, draft in zip(persisted, drafts):
            loaded = load_and_validate_candidate(
                path=path,
                operator_type="repair",
                round_id=generation,
                source="langchain_openai_compatible" if config.provider_name != "fake" else "fake",
                description=draft.description,
                allow_unsafe_candidate_execution=True,
            )
            validation = asdict(loaded.validation)
            with validation_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(validation, sort_keys=True, default=str) + "\n")
            if loaded.callable_obj is None:
                row = _invalid_row(loaded.validation)
            else:
                row = _evaluate_candidate(loaded, cases, config.solver_seeds, config.timeout_ms)
            row.update(
                {
                    "operator_id": draft.operator_id,
                    "generation": generation,
                    "feedback_mode": mode,
                    "source_hash": validation.get("code_hash", ""),
                    "source_path": str(path),
                }
            )
            if generation > 0 and previous_best and mode != "L0":
                row["parent_candidate_id"] = previous_best.get("operator_id", "")
                row["parent_source_hash"] = previous_best.get("source_hash", "")
                with lineage_path.open("a", encoding="utf-8") as handle:
                    handle.write(
                        json.dumps(
                            {
                                "generation": generation,
                                "candidate_id": draft.operator_id,
                                "parent_candidate_id": row["parent_candidate_id"],
                                "parent_source_hash": row["parent_source_hash"],
                                "feedback_mode": mode,
                            },
                            sort_keys=True,
                        )
                        + "\n"
                    )
            rows.append(row)
            with trials_path.open("a", encoding="utf-8") as handle:
                for trial in row.get("trials", []):
                    trial.update(operator_id=draft.operator_id, generation=generation)
                    handle.write(json.dumps(trial, sort_keys=True, default=str) + "\n")
            with behavior_path.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(
                        {
                            "operator_id": draft.operator_id,
                            "generation": generation,
                            "exact_dp_behavior": row.get("exact_dp_behavior", {}),
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
        all_rows.extend(rows)
        with (branch / "candidate_metrics.jsonl").open("w", encoding="utf-8") as handle:
            for item in all_rows:
                handle.write(json.dumps(item, default=str) + "\n")
        feedback = build_f2_feedback(rows) if mode == "F2" else build_f1_feedback(rows)
        (branch / f"feedback_round_{generation:03d}.json").write_text(
            json.dumps(feedback, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
        )
        eligible = [row for row in rows if row.get("feasible_count", 0) > 0]
        if not eligible and mode != "L0":
            previous_best = None
            break
        if eligible:
            previous_best = max(eligible, key=lambda row: float(row.get("avg_relative_improvement", 0.0)))
    elite = sorted(
        (row for row in all_rows if row.get("feasible_count", 0) == row.get("executed_count", 0)
         and row.get("executed_count", 0) > 0),
        key=lambda row: float(row["avg_relative_improvement"]), reverse=True,
    )
    (branch / "elite_archive.json").write_text(
        json.dumps(elite, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
    provider_meta = getattr(provider, "last_call_metadata", {})
    raw_counts = [record.get("raw_response_candidate_count") for record in provider_records]
    parsed_counts = [record.get("parsed_candidate_count") for record in provider_records]
    total_tokens = [record.get("total_tokens") for record in provider_records]
    prompt_tokens = [record.get("prompt_tokens") for record in provider_records]
    completion_tokens = [record.get("completion_tokens") for record in provider_records]
    latencies = [record.get("latency_ms") for record in provider_records]
    provider_usage = {
        "provider_call_count": calls,
        "actual_successful_provider_calls": sum(record.get("actual_provider_call", True) for record in provider_records),
        "shared_initial_pool": any(record.get("actual_provider_call") is False for record in provider_records),
        "prompt_tokens": sum(int(value) for value in prompt_tokens if isinstance(value, (int, float))),
        "completion_tokens": sum(int(value) for value in completion_tokens if isinstance(value, (int, float))),
        "total_tokens": sum(int(value) for value in total_tokens if isinstance(value, (int, float))),
        "total_latency_ms": sum(float(value) for value in latencies if isinstance(value, (int, float))),
        "mean_latency_ms": (
            sum(float(value) for value in latencies if isinstance(value, (int, float)))
            / max(1, sum(isinstance(value, (int, float)) for value in latencies))
        ),
        "estimated_cost_usd": None,
    }
    summary = {
        "feedback_mode": mode,
        "provider_calls": calls,
        "generated_count": len(all_rows),
        "requested_candidate_count": calls * config.candidates_per_generation,
        "raw_response_candidate_count": (
            sum(int(value) for value in raw_counts)
            if raw_counts and all(isinstance(value, int) for value in raw_counts)
            else None
        ),
        "parsed_candidate_count": (
            sum(int(value) for value in parsed_counts)
            if parsed_counts and all(isinstance(value, int) for value in parsed_counts)
            else None
        ),
        "parse_failure_count": sum(int(record.get("parse_failure_count", 0) or 0) for record in provider_records),
        "contract_valid_count": sum(row.get("validation_status") == "valid" for row in all_rows),
        "executed_count": sum(row.get("executed_count", 0) for row in all_rows),
        "feasible_count": sum(row.get("feasible_count", 0) for row in all_rows),
        "elite_count": len(elite),
        "provider_usage": provider_usage,
    }
    (branch / "yield_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary, calls


def _evaluate_candidate(loaded, cases, seeds, timeout_ms) -> dict[str, Any]:
    trials: list[dict[str, Any]] = []
    for case in cases:
        baseline_solution = _fixed_greedy_repair(case.partial_solution, case.removed_tasks, case.evaluator)
        baseline_eval = case.evaluator.evaluate(baseline_solution)
        for seed in seeds:
            import random

            context = RepairContext(
                instance=case.instance,
                per_robot_costs=list(case.partial_evaluation.per_robot_costs),
                route_costs_makespan=case.partial_evaluation.makespan,
                bottleneck_route_id=max(range(len(case.partial_evaluation.per_robot_costs)), key=case.partial_evaluation.per_robot_costs.__getitem__),
            )
            started = perf_counter()
            outcome = loaded.callable_obj.execute(
                (clone_solution(case.partial_solution), list(case.removed_tasks), context, random.Random(seed)),
                timeout_ms=timeout_ms,
            )
            trial: dict[str, Any] = {
                "instance_id": case.instance.name,
                "solver_seed": seed,
                "status": outcome.status,
                "runtime_ms": outcome.runtime_ms or (perf_counter() - started) * 1000.0,
                "feasible": False,
                "error": outcome.error_message,
                "route_dp_calls": outcome.route_dp_calls,
                "route_dp_cache_misses": outcome.route_dp_cache_misses,
                "wall_time_ms": (perf_counter() - started) * 1000.0,
            }
            if outcome.status == "success":
                try:
                    candidate_solution = outcome.result.solution
                    candidate_eval = case.evaluator.evaluate(candidate_solution)
                    behavior = compute_exact_dp_behavior(
                        baseline_solution,
                        candidate_solution,
                        baseline_eval,
                        candidate_eval,
                        instance=case.instance,
                    )
                    trial.update(
                        {
                            "feasible": True,
                            "baseline_makespan": baseline_eval.makespan,
                            "candidate_makespan": candidate_eval.makespan,
                            "absolute_improvement": baseline_eval.makespan - candidate_eval.makespan,
                            "relative_improvement": (baseline_eval.makespan - candidate_eval.makespan) / max(1e-9, baseline_eval.makespan),
                            "exact_dp_behavior": behavior,
                            "baseline_route_costs": list(baseline_eval.per_robot_costs),
                            "candidate_route_costs": list(candidate_eval.per_robot_costs),
                            "reassigned_task_count": sum(
                                {t: r for r, route in enumerate(baseline_solution.routes) for t in route}[t] != r
                                for r, route in enumerate(candidate_solution.routes) for t in route
                            ),
                        }
                    )
                except (AttributeError, TypeError, ValueError) as exc:
                    trial["error"] = f"{type(exc).__name__}: {exc}"
            trials.append(trial)
    feasible = [trial for trial in trials if trial["feasible"]]
    behavior_values = [trial["exact_dp_behavior"] for trial in feasible if "exact_dp_behavior" in trial]
    behavior = {
        key: mean(float(item[key]) for item in behavior_values)
        for key in (
            "dp_state_switch_fraction",
            "hv_mode_switch_fraction",
            "entry_corner_switch_fraction",
            "exit_corner_switch_fraction",
            "dp_cascade_count",
            "dp_cascade_ratio",
            "bottleneck_relief",
            "travel_change",
            "coverage_change",
            "turning_change",
        )
        if behavior_values
    }
    return {
        "validation_status": loaded.validation.validation_status,
        "execution_status": loaded.validation.execution_status,
        "avg_relative_improvement": mean(float(t.get("relative_improvement", 0.0)) for t in trials) if trials else 0.0,
        "success_rate": sum(bool(t["feasible"]) for t in trials) / len(trials) if trials else 0.0,
        "feasible_count": len(feasible),
        "executed_count": len(trials),
        "exact_dp_behavior": behavior,
        "trials": trials,
    }


def _invalid_row(validation) -> dict[str, Any]:
    return {
        "validation_status": validation.validation_status,
        "execution_status": validation.execution_status,
        "avg_relative_improvement": 0.0,
        "success_rate": 0.0,
        "feasible_count": 0,
        "executed_count": 0,
        "exact_dp_behavior": {},
        "trials": [],
    }


def _scalar_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "candidate_count": len(rows),
        "mean_relative_improvement": mean(float(row.get("avg_relative_improvement", 0.0)) for row in rows) if rows else 0.0,
        "mean_success_rate": mean(float(row.get("success_rate", 0.0)) for row in rows) if rows else 0.0,
    }


def _feedback_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "operator_id": row.get("operator_id", ""),
        "validation_status": row.get("validation_status", ""),
        "execution_status": row.get("execution_status", ""),
        "avg_relative_improvement": row.get("avg_relative_improvement", 0.0),
        "success_rate": row.get("success_rate", 0.0),
    }


__all__ = [
    "E1PilotConfig",
    "build_f1_feedback",
    "build_f2_feedback",
    "classify_provider_error",
    "compute_exact_dp_behavior",
    "load_development_instance_paths",
    "run_provider_preflight",
    "run_e1_pilot",
]
