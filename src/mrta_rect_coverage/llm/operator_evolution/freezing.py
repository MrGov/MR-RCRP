"""Freeze top-performing generated operators into production registry."""
from __future__ import annotations

import json
import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from .eligibility_policy import (
    candidate_is_freeze_eligible,
    parse_positive_finite_timeout,
)
from .utils import write_json


@dataclass
class FreezeResult:
    copied_files: List[str]
    registry_path: str


def freeze_best_operators(
    *,
    project_root: Path,
    best_operators_json: Path,
    generated_root: Path,
    target_dir: Path | None = None,
    registry_path: Path | None = None,
) -> FreezeResult:
    if not best_operators_json.is_absolute():
        best_operators_json = project_root / best_operators_json
    if not generated_root.is_absolute():
        generated_root = project_root / generated_root

    if target_dir is None:
        target_dir = project_root / "src" / "mrta_rect_coverage" / "heuristics" / "generated_best"
    elif not target_dir.is_absolute():
        target_dir = project_root / target_dir

    if registry_path is None:
        registry_path = target_dir / "operator_registry.json"
    elif not registry_path.is_absolute():
        registry_path = project_root / registry_path

    target_dir.mkdir(parents=True, exist_ok=True)

    payload = json.loads(best_operators_json.read_text(encoding="utf-8"))
    copied: List[str] = []
    registry: Dict[str, List[dict]] = {"repair": [], "destroy": []}

    for op_type in ("repair", "destroy"):
        row = payload.get(op_type, {})
        if not _is_freezable(row):
            continue
        operator_id = row.get("operator_id")
        if not operator_id:
            continue
        round_id = int(row.get("round_id", 0))
        src = generated_root / f"round_{round_id:03d}" / f"{operator_id}.py"
        if not src.exists():
            continue
        code_hash = hashlib.sha256(
            src.read_text(encoding="utf-8").encode("utf-8")
        ).hexdigest()
        if code_hash != row.get("code_hash"):
            continue

        dst = target_dir / f"{operator_id}.py"
        shutil.copy2(src, dst)
        copied.append(str(dst))
        registry[op_type].append(
            {
                "name": operator_id,
                "operator_type": op_type,
                "file_path": str(dst),
                "source_round": round_id,
                "artifact_type": row["artifact_type"],
                "code_hash": code_hash,
                "validation_status": row["validation_status"],
                "execution_status": row["execution_status"],
                "failure_type": row["failure_type"],
                "source_provider": row["claimed_source_provider"],
                "claimed_source_provider": row["claimed_source_provider"],
                "provider_provenance": row["provider_provenance"],
                "provider_provenance_source": row.get(
                    "provider_provenance_source", "artifact_metadata"
                ),
                "generation_run_id": row["generation_run_id"],
                "artifact_identity": row["artifact_identity"],
                "lineage": row["lineage"],
                "deployment_authorization_status": (
                    "runtime_authorization_required"
                ),
                "sandbox_level": row["sandbox_level"],
                "claimed_sandbox_level": row.get(
                    "claimed_sandbox_level", row["sandbox_level"]
                ),
                "effective_sandbox_level": row["effective_sandbox_level"],
                "executor_identity": row["executor_identity"],
                "safe_to_execute": row["safe_to_execute"],
                "requires_human_risk_ack": row["requires_human_risk_ack"],
                "fallback_used": row["fallback_used"],
                "error_rate": row["error_rate"],
                "timeout_rate": row["timeout_rate"],
                "invalid_solution_rate": row["invalid_solution_rate"],
                "validation_failed_rate": row["validation_failed_rate"],
                "execution_blocked_rate": row["execution_blocked_rate"],
                "timeout_ms": parse_positive_finite_timeout(
                    row["timeout_ms"]
                ),
            }
        )

    init_path = target_dir / "__init__.py"
    if not init_path.exists():
        init_path.write_text('"""Frozen generated operators."""\n', encoding="utf-8")

    write_json(registry_path, registry)
    return FreezeResult(copied_files=copied, registry_path=str(registry_path))


def _is_freezable(row: dict) -> bool:
    return candidate_is_freeze_eligible(row)
