"""Structured schemas for offline operator evolution artifacts."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List


@dataclass
class GeneratedOperatorDraft:
    operator_id: str
    operator_type: str
    round_id: int
    name: str
    description: str
    source: str
    code: str
    module_filename: str


@dataclass
class OperatorValidationResult:
    operator_id: str
    operator_type: str
    round_id: int
    name: str
    description: str
    source: str
    file_path: str
    validation_status: str
    error_message: str = ""
    execution_status: str = "validation_failed"
    runtime_ms: float = 0.0
    code_hash: str = ""
    failure_type: str = "validation_failed"
    sandbox_level: str = "unknown"
    claimed_sandbox_level: str = "unknown"
    effective_sandbox_level: str = "unknown"
    executor_identity: str = "unknown"
    safe_to_execute: bool = False
    requires_human_risk_ack: bool = True
    runtime_authorization_source: str = ""
    allow_real_provider_frozen_deployment: bool = False
    explicit_runtime_risk_ack: bool = False
    exit_code: int | None = None
    wall_time_ms: float = 0.0
    stdout: str = ""
    stderr: str = ""
    stdout_truncated: bool = False
    stderr_truncated: bool = False


@dataclass
class OperatorMetricsSummary:
    avg_makespan_delta: float
    avg_relative_improvement: float
    success_rate: float
    avg_runtime_ms: float
    timeout_rate: float
    error_rate: float
    invalid_solution_rate: float


@dataclass
class OperatorRecord:
    operator_id: str
    operator_type: str
    round_id: int
    name: str
    description: str
    source: str
    file_path: str
    validation_status: str
    metrics_summary: OperatorMetricsSummary | None = None


@dataclass
class RoundResult:
    round_id: int
    repair_leaderboard: List[Dict[str, object]] = field(default_factory=list)
    destroy_leaderboard: List[Dict[str, object]] = field(default_factory=list)


@dataclass
class EvolutionSummary:
    rounds: List[RoundResult]
    best_repair_operator_id: str = ""
    best_destroy_operator_id: str = ""


def dataclass_to_dict(obj) -> Dict[str, object]:
    return asdict(obj)


def resolve_round_dir(base_dir: Path, round_id: int) -> Path:
    return base_dir / f"round_{round_id:03d}"
