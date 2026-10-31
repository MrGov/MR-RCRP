"""End-to-end offline operator evolution loop."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .candidate_loader import load_and_validate_candidate, persist_operator_drafts
from .evaluator import (
    build_destroy_benchmark_cases,
    build_repair_benchmark_cases,
    evaluate_destroy_candidates,
    evaluate_repair_candidates,
)
from .feedback_builder import build_dataset_evidence, build_feedback_payload
from .eligibility_policy import (
    build_generated_artifact_metadata,
    candidate_is_benchmark_eligible,
    candidate_is_selection_eligible,
    parse_strict_bool,
)
from . import prompt_builder
from .provider_interface import OperatorEvolutionProvider
from .utils import write_csv, write_json


@dataclass
class EvolutionLoopConfig:
    project_root: Path
    generated_dir: Path = Path("generated_operators")
    output_dir: Path = Path("outputs/operator_evolution")
    round_count: int = 2
    repair_candidates_per_round: int = 3
    destroy_candidates_per_round: int = 1
    benchmark_instance_glob: str = "data/R*_T*_*.txt"
    # Optional explicit instance list (JSON array of paths); overrides the glob when set.
    benchmark_instance_list: str = ""
    # P2 evidence: glob of e14 state-regret reports used to build dataset evidence.
    evidence_report_glob: str = ""
    evidence_budget_bytes: int = 2500
    seeds: Sequence[int] = (0, 1)
    timeout_ms: float = 1000.0
    top_k_to_keep: int = 2
    operator_types_to_evolve: Sequence[str] = ("repair", "destroy")
    # Provider selection: "mock", "file", "langchain_openai_compatible"
    provider_name: str = "mock"
    # For file provider
    exchange_dir: Optional[Path] = None
    # Enable rich structured prompts (auto-enabled for langchain provider)
    use_rich_prompts: Optional[bool] = None
    allow_unsafe_candidate_execution: bool = False

    def __post_init__(self) -> None:
        self.allow_unsafe_candidate_execution = parse_strict_bool(
            self.allow_unsafe_candidate_execution,
            field_name="allow_unsafe_candidate_execution",
        )


@dataclass
class EvolutionArtifacts:
    round_metrics_files: List[str] = field(default_factory=list)
    evolution_summary_path: str = ""
    best_operators_path: str = ""


def run_evolution_loop(
    provider: OperatorEvolutionProvider,
    config: EvolutionLoopConfig,
) -> EvolutionArtifacts:
    generated_root = _resolve(config.project_root, config.generated_dir)
    output_root = _resolve(config.project_root, config.output_dir)
    generated_root.mkdir(parents=True, exist_ok=True)
    output_root.mkdir(parents=True, exist_ok=True)

    # Activate rich prompts when explicitly requested or when using a real LLM
    if config.use_rich_prompts is True or (
        config.use_rich_prompts is None
        and config.provider_name == "langchain_openai_compatible"
    ):
        prompt_builder.use_rich_prompts = True
    else:
        prompt_builder.use_rich_prompts = False

    if config.benchmark_instance_list:
        list_path = _resolve(config.project_root, Path(config.benchmark_instance_list))
        if not list_path.is_file():
            raise ValueError(f"Benchmark instance list not found: {list_path}")
        relatives = json.loads(list_path.read_text(encoding="utf-8"))
        if not isinstance(relatives, list) or not relatives:
            raise ValueError(f"Benchmark instance list must be a non-empty JSON array: {list_path}")
        instance_paths = [_resolve(config.project_root, Path(rel)) for rel in relatives]
    else:
        instance_paths = sorted(config.project_root.glob(config.benchmark_instance_glob))
    if not instance_paths:
        raise ValueError(f"No benchmark instances matched: {config.benchmark_instance_glob}")
    missing = [str(path) for path in instance_paths if not path.is_file()]
    if missing:
        raise ValueError(f"Benchmark instances missing on disk: {missing}")

    evidence: Optional[dict] = None
    if config.evidence_report_glob:
        evidence = _build_evidence(
            config.project_root, config.evidence_report_glob, config.evidence_budget_bytes
        )
        write_json(output_root / "evidence.json", evidence)

    previous_feedback: Dict[str, Dict[str, object]] = {}
    all_rounds: List[dict] = []
    all_candidate_rows: List[dict] = []
    best_rows: Dict[str, dict] = {}
    metrics_files: List[str] = []

    for round_id in range(config.round_count):
        round_rows: List[dict] = []
        prompts: Dict[str, str] = {}

        if "repair" in config.operator_types_to_evolve:
            repair_rows, repair_prompt, repair_feedback = _run_one_type(
                provider=provider,
                operator_type="repair",
                round_id=round_id,
                previous_feedback=previous_feedback.get("repair"),
                count=config.repair_candidates_per_round,
                generated_root=generated_root,
                instance_paths=instance_paths,
                seeds=config.seeds,
                timeout_ms=config.timeout_ms,
                top_k_to_keep=config.top_k_to_keep,
                source_provider=config.provider_name,
                allow_unsafe_candidate_execution=config.allow_unsafe_candidate_execution,
                evidence=evidence,
            )
            round_rows.extend(repair_rows)
            prompts["repair"] = repair_prompt
            previous_feedback["repair"] = repair_feedback

        if "destroy" in config.operator_types_to_evolve:
            destroy_rows, destroy_prompt, destroy_feedback = _run_one_type(
                provider=provider,
                operator_type="destroy",
                round_id=round_id,
                previous_feedback=previous_feedback.get("destroy"),
                count=config.destroy_candidates_per_round,
                generated_root=generated_root,
                instance_paths=instance_paths,
                seeds=config.seeds,
                timeout_ms=config.timeout_ms,
                top_k_to_keep=config.top_k_to_keep,
                source_provider=config.provider_name,
                allow_unsafe_candidate_execution=config.allow_unsafe_candidate_execution,
                evidence=evidence,
            )
            round_rows.extend(destroy_rows)
            prompts["destroy"] = destroy_prompt
            previous_feedback["destroy"] = destroy_feedback

        metrics_path = output_root / f"round_{round_id:03d}_metrics.csv"
        write_csv(
            metrics_path,
            round_rows,
            fieldnames=[
                "operator_id",
                "operator_type",
                "round_id",
                "name",
                "validation_status",
                "execution_status",
                "failure_type",
                "failure_type_breakdown",
                "fallback_used",
                "fallback_reason",
                "runtime_ms",
                "code_hash",
                "artifact_type",
                "source_provider",
                "claimed_source_provider",
                "provider_provenance",
                "provider_provenance_source",
                "generation_run_id",
                "artifact_identity",
                "lineage",
                "sandbox_level",
                "claimed_sandbox_level",
                "effective_sandbox_level",
                "executor_identity",
                "safe_to_execute",
                "requires_human_risk_ack",
                "timeout_ms",
                "avg_makespan_delta",
                "avg_relative_improvement",
                "success_rate",
                "avg_runtime_ms",
                "timeout_rate",
                "error_rate",
                "invalid_solution_rate",
                "validation_failed_rate",
                "execution_blocked_rate",
            ],
        )
        metrics_files.append(str(metrics_path))

        for op_type, prompt in prompts.items():
            (output_root / f"round_{round_id:03d}_{op_type}_prompt.txt").write_text(prompt, encoding="utf-8")

        # Save per-round candidates and validation results for traceability
        write_json(
            output_root / f"round_{round_id:03d}_candidates.json",
            round_rows,
        )

        all_candidate_rows.extend(round_rows)
        leaderboard = sorted(
            [row for row in round_rows if _is_eligible(row)],
            key=lambda r: (r.get("avg_relative_improvement", 0.0), r.get("success_rate", 0.0)),
            reverse=True,
        )
        all_rounds.append(
            {
                "round_id": round_id,
                "leaderboard": leaderboard,
            }
        )

        for op_type in ("repair", "destroy"):
            typed_rows = [
                row
                for row in round_rows
                if row["operator_type"] == op_type and _is_eligible(row)
            ]
            if not typed_rows:
                continue
            best = sorted(typed_rows, key=lambda r: r["avg_relative_improvement"], reverse=True)[0]
            prev = best_rows.get(op_type)
            if prev is None or best["avg_relative_improvement"] > prev["avg_relative_improvement"]:
                best_rows[op_type] = best

    failure_type_breakdown: Dict[str, int] = {}
    for row in all_candidate_rows:
        for failure_type, count in row.get("failure_type_breakdown", {}).items():
            failure_type_breakdown[failure_type] = (
                failure_type_breakdown.get(failure_type, 0) + int(count)
            )

    summary = {
        "rounds": all_rounds,
        "best_repair_operator_id": best_rows.get("repair", {}).get("operator_id", ""),
        "best_destroy_operator_id": best_rows.get("destroy", {}).get("operator_id", ""),
        "repair_selection_status": _selection_status("repair", config, best_rows),
        "destroy_selection_status": _selection_status("destroy", config, best_rows),
        "failure_type_breakdown": failure_type_breakdown,
    }
    best_json = {
        "repair": best_rows.get("repair", {}),
        "destroy": best_rows.get("destroy", {}),
    }

    summary_path = output_root / "evolution_summary.json"
    best_path = output_root / "best_operators.json"
    write_json(summary_path, summary)
    write_json(best_path, best_json)

    return EvolutionArtifacts(
        round_metrics_files=metrics_files,
        evolution_summary_path=str(summary_path),
        best_operators_path=str(best_path),
    )


def _run_one_type(
    *,
    provider: OperatorEvolutionProvider,
    operator_type: str,
    round_id: int,
    previous_feedback: Dict[str, object] | None,
    count: int,
    generated_root: Path,
    instance_paths: Sequence[Path],
    seeds: Sequence[int],
    timeout_ms: float,
    top_k_to_keep: int,
    source_provider: str,
    allow_unsafe_candidate_execution: bool,
    evidence: Optional[dict] = None,
) -> tuple[List[dict], str, Dict[str, object]]:
    if previous_feedback:
        prompt = prompt_builder.build_revision_prompt(
            operator_type=operator_type,
            round_id=round_id,
            previous_summary=previous_feedback.get("summary", {}),
            top_operators=previous_feedback.get("top_operators", []),
            weak_operators=previous_feedback.get("weak_operators", []),
            evidence=evidence,
        )
        drafts = provider.revise_operator_candidates(
            prompt,
            previous_feedback,
            count,
            operator_type,
            round_id,
        )
    else:
        prompt = prompt_builder.build_initial_generation_prompt(
            operator_type=operator_type, round_id=round_id, evidence=evidence
        )
        drafts = provider.generate_operator_candidates(
            prompt,
            count,
            operator_type,
            round_id,
        )

    persisted = persist_operator_drafts(generated_root, drafts)
    loaded = []
    for path, draft in zip(persisted, drafts):
        draft_source = getattr(draft, "source", "")
        effective_source = (
            "langchain_openai_compatible"
            if "langchain_openai_compatible" in {source_provider, draft_source}
            else (draft_source or source_provider)
        )
        loaded.append(
            load_and_validate_candidate(
                path=path,
                operator_type=operator_type,
                round_id=round_id,
                source=effective_source,
                description="generated candidate",
                allow_unsafe_candidate_execution=allow_unsafe_candidate_execution,
            )
        )

    valid = [
        item
        for item in loaded
        if _can_enter_benchmark(item, allow_unsafe_candidate_execution)
    ]
    invalid_rows = [
        {
            "operator_id": item.validation.operator_id,
            "operator_type": operator_type,
            "round_id": round_id,
            "name": item.validation.name,
            "validation_status": item.validation.validation_status,
            "execution_status": item.validation.execution_status,
            "failure_type": item.validation.failure_type,
            "failure_type_breakdown": {item.validation.failure_type: 1},
            "fallback_used": False,
            "fallback_reason": "",
            "runtime_ms": item.validation.runtime_ms,
            "code_hash": item.validation.code_hash,
            **build_generated_artifact_metadata(
                claimed_source_provider=item.validation.source,
                round_id=round_id,
                code_hash=item.validation.code_hash,
            ),
            "sandbox_level": item.validation.sandbox_level,
            "claimed_sandbox_level": item.validation.claimed_sandbox_level,
            "effective_sandbox_level": item.validation.effective_sandbox_level,
            "executor_identity": item.validation.executor_identity,
            "safe_to_execute": item.validation.safe_to_execute,
            "requires_human_risk_ack": item.validation.requires_human_risk_ack,
            "timeout_ms": timeout_ms,
            "avg_makespan_delta": 0.0,
            "avg_relative_improvement": 0.0,
            "success_rate": 0.0,
            "avg_runtime_ms": 0.0,
            "timeout_rate": 1.0
            if item.validation.failure_type == "timeout"
            else 0.0,
            "error_rate": 1.0
            if item.validation.failure_type == "runtime_error"
            else 0.0,
            "invalid_solution_rate": 1.0
            if item.validation.failure_type == "invalid_solution"
            else 0.0,
            "validation_failed_rate": 1.0
            if item.validation.failure_type
            in {"validation_failed", "source_read_failed"}
            else 0.0,
            "execution_blocked_rate": 1.0
            if item.validation.failure_type
            in {
                "config_invalid",
                "execution_blocked",
                "risk_ack_required",
                "untrusted_sandbox_claim",
            }
            else 0.0,
        }
        for item in loaded
        if not _can_enter_benchmark(item, allow_unsafe_candidate_execution)
    ]

    if operator_type == "repair":
        cases = build_repair_benchmark_cases(instance_paths)
        evaluated_rows = evaluate_repair_candidates(valid, cases, seeds=seeds, timeout_ms=timeout_ms)
    else:
        cases = build_destroy_benchmark_cases(instance_paths)
        evaluated_rows = evaluate_destroy_candidates(valid, cases, seeds=seeds, timeout_ms=timeout_ms)

    rows = evaluated_rows + invalid_rows
    feedback = build_feedback_payload(rows, top_k=top_k_to_keep)
    return rows, prompt, feedback


def _build_evidence(
    project_root: Path, report_glob: str, budget_bytes: int
) -> dict:
    """Aggregate e14 state-regret reports into one dataset-level evidence payload."""
    # Any *_summary.json is an aggregate, not a report; feeding it back in would
    # add a phantom instance with no makespan and no position table.
    report_paths = [
        path
        for path in sorted(project_root.glob(report_glob))
        if not path.name.endswith("_summary.json")
    ]
    if not report_paths:
        raise ValueError(f"No evidence reports matched: {report_glob}")
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in report_paths]
    return build_dataset_evidence(reports, budget_bytes=budget_bytes)


def _is_eligible(row: dict) -> bool:
    return candidate_is_selection_eligible(row)


def _selection_status(
    operator_type: str,
    config: EvolutionLoopConfig,
    best_rows: Dict[str, dict],
) -> str:
    if operator_type not in config.operator_types_to_evolve:
        return "not_evolved"
    return "selected" if best_rows.get(operator_type) else "no_valid_operator"


def _can_enter_benchmark(item, allow_unsafe_candidate_execution: bool) -> bool:
    return candidate_is_benchmark_eligible(
        item.validation,
        item.callable_obj,
        allow_unsafe_candidate_execution,
    )


def _resolve(project_root: Path, maybe_relative: Path) -> Path:
    if maybe_relative.is_absolute():
        return maybe_relative
    return project_root / maybe_relative
