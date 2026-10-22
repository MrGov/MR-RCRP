"""Candidate module persistence, controlled loading, and validation."""
from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List

from ...core.models import Instance, MultiRobotSolution
from .candidate_execution import CandidateProxy
from .candidate_security import code_sha256, validate_candidate_source
from .eligibility_policy import (
    candidate_is_execution_eligible,
    configure_candidate_preexecution_policy,
    mark_candidate_execution_blocked,
)
from .protocols import DestroyContext, RepairContext
from .schemas import GeneratedOperatorDraft, OperatorValidationResult, resolve_round_dir


@dataclass
class LoadedOperator:
    validation: OperatorValidationResult
    callable_obj: Callable | None = None


def persist_operator_drafts(base_dir: Path, drafts: List[GeneratedOperatorDraft]) -> List[Path]:
    paths: List[Path] = []
    for draft in drafts:
        round_dir = resolve_round_dir(base_dir, draft.round_id)
        round_dir.mkdir(parents=True, exist_ok=True)
        target = round_dir / draft.module_filename
        target.write_text(draft.code, encoding="utf-8")
        paths.append(target)
    return paths


def load_and_validate_candidate(
    *,
    path: Path,
    operator_type: str,
    round_id: int,
    source: str,
    description: str,
    allow_unsafe_candidate_execution: bool = False,
) -> LoadedOperator:
    operator_id = path.stem
    base_validation = OperatorValidationResult(
        operator_id=operator_id,
        operator_type=operator_type,
        round_id=round_id,
        name=operator_id,
        description=description,
        source=source,
        file_path=str(path),
        validation_status="invalid",
        safe_to_execute=False,
        requires_human_risk_ack=True,
    )

    try:
        source_text = path.read_text(encoding="utf-8")
        base_validation.code_hash = code_sha256(source_text)
    except (OSError, UnicodeError) as exc:
        base_validation.failure_type = "source_read_failed"
        base_validation.execution_status = "source_read_failed"
        base_validation.error_message = f"{type(exc).__name__}: {exc}"
        return LoadedOperator(validation=base_validation, callable_obj=None)

    try:
        validate_candidate_source(source_text, operator_type)
        try:
            configure_candidate_preexecution_policy(
                base_validation,
                allow_unsafe_candidate_execution,
            )
        except TypeError as exc:
            base_validation.safe_to_execute = False
            base_validation.execution_status = "config_invalid"
            base_validation.failure_type = "config_invalid"
            base_validation.error_message = str(exc)
            return LoadedOperator(validation=base_validation, callable_obj=None)
        proxy = CandidateProxy(
            path=path,
            operator_type=operator_type,
            expected_code_hash=base_validation.code_hash,
        )
        if not candidate_is_execution_eligible(
            base_validation,
            proxy,
            allow_unsafe_candidate_execution,
        ):
            if base_validation.failure_type == "success":
                mark_candidate_execution_blocked(
                    base_validation,
                    "Candidate rejected by shared execution eligibility policy",
                )
            return LoadedOperator(validation=base_validation, callable_obj=None)
        smoke = _smoke_test(proxy, operator_type)
        base_validation.runtime_ms = smoke.runtime_ms
        base_validation.wall_time_ms = smoke.wall_time_ms
        base_validation.exit_code = smoke.exit_code
        base_validation.stdout = smoke.stdout
        base_validation.stderr = smoke.stderr
        base_validation.stdout_truncated = smoke.stdout_truncated
        base_validation.stderr_truncated = smoke.stderr_truncated
        base_validation.execution_status = smoke.status
        base_validation.failure_type = smoke.status
        if smoke.status != "success":
            raise RuntimeError(smoke.error_message or f"Smoke test {smoke.status}")

        base_validation.execution_status = "success"
        base_validation.failure_type = "success"
        return LoadedOperator(validation=base_validation, callable_obj=proxy)
    except Exception as exc:  # noqa: BLE001 - keep robust error capture for generated code.
        base_validation.error_message = str(exc)
        return LoadedOperator(validation=base_validation, callable_obj=None)


def _smoke_test(proxy: CandidateProxy, operator_type: str):
    dummy_instance = Instance(
        name="dummy",
        depot=(0.0, 0.0),
        robot_count=2,
        sweep_speed=1.0,
        travel_speed=1.0,
        sweep_width=1.0,
        turning_time=0.0,
        tasks=[],
    )
    rng = random.Random(0)

    if operator_type == "repair":
        partial = MultiRobotSolution(routes=[[], []])
        context = RepairContext(
            instance=dummy_instance,
            per_robot_costs=[0.0, 0.0],
            route_costs_makespan=0.0,
            bottleneck_route_id=0,
        )
        outcome = proxy.execute((partial, [], context, rng), timeout_ms=1000.0)
        if outcome.status == "success" and not hasattr(outcome.result, "solution"):
            raise ValueError("Repair result must expose .solution")
        return outcome
    else:
        full_solution = MultiRobotSolution(routes=[[1], []])
        context = DestroyContext(
            instance=dummy_instance,
            per_robot_costs=[0.0, 0.0],
            route_costs_makespan=0.0,
            remove_count=1,
        )
        outcome = proxy.execute((full_solution, context, rng), timeout_ms=1000.0)
        if outcome.status == "success" and (
            not hasattr(outcome.result, "partial_solution")
            or not hasattr(outcome.result, "removed_tasks")
        ):
            raise ValueError("Destroy result must expose .partial_solution and .removed_tasks")
        return outcome
