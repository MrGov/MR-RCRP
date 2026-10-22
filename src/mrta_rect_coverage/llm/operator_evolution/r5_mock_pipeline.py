"""Trusted-fixture-only R5 research pipeline.

This module deliberately does not load or execute candidate Python source. It
implements the frozen R4 research contracts over structured trusted fixtures so
that plumbing, lineage, selection, accounting and audit artifacts can be tested
without a provider or untrusted runtime.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import csv
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence



PROFILE_SCHEMA_VERSION = "r5-operator-behavior-v1"
FEEDBACK_SCHEMA_VERSION = "r5-structured-feedback-v1"
ARCHIVE_SCHEMA_VERSION = "r5-operator-archive-v1"
LEDGER_SCHEMA_VERSION = "r5-budget-ledger-v1"
EVALUATION_SCHEMA_VERSION = "r5-candidate-evaluation-v1"
FIXTURE_MANIFEST_SCHEMA_VERSION = "r5-fixture-manifest-v1"
FEEDBACK_MODES = ("F0", "F1", "F2", "F3")
COUNTEREXAMPLE_MODES = ("C0", "C1", "C2", "C3")
ALLOWED_SPLITS = (
    "evolution-development",
    "selection-validation",
    "confirmatory-heldout",
)
FORBIDDEN_SPLITS = {"final-test", "diagnostic-heldout-consumed", "held-out"}


def _finite(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field_name} must be finite")
    return result


@dataclass
class OperatorBehaviorProfile:
    baseline_makespan: float
    candidate_makespan: float
    absolute_improvement: float
    relative_improvement: float
    success_rate: float
    assignment_change_count: int
    tasks_moved_out_of_bottleneck: int
    tasks_moved_into_bottleneck: int
    bottleneck_relief_mean: float
    bottleneck_relief_rate: float
    max_route_cost_change: float
    route_cost_cv_change: float
    dp_state_switch_fraction: float
    hv_mode_switch_fraction: float
    entry_corner_switch_fraction: float
    exit_corner_switch_fraction: float
    dp_cascade_count: int
    dp_cascade_ratio: float
    travel_time_change: float
    coverage_time_change: float
    turning_time_change: float
    valid_solution_rate: float
    runtime_error_rate: float
    timeout_rate: float
    fallback_rate: float
    contract_rejection_rate: float
    candidate_runtime: float
    route_dp_evaluation_count: int
    cache_hit_rate: float | None
    regime_context: dict[str, float | str] = field(default_factory=dict)
    llm_call_count: int | None = None
    llm_token_count: int | None = None
    llm_cost: float | None = None

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if name in {"regime_context", "cache_hit_rate", "llm_call_count", "llm_token_count", "llm_cost"}:
                continue
            if name.endswith("_count") or name == "route_dp_evaluation_count":
                if type(value) is not int or value < 0:
                    raise TypeError(f"{name} must be a non-negative integer")
            elif name not in {"regime_context"}:
                _finite(value, name)
        for name in ("cache_hit_rate", "llm_cost"):
            value = getattr(self, name)
            if value is not None:
                _finite(value, name)
        for name in (
            "success_rate", "bottleneck_relief_rate", "dp_state_switch_fraction",
            "hv_mode_switch_fraction", "entry_corner_switch_fraction",
            "exit_corner_switch_fraction", "dp_cascade_ratio", "valid_solution_rate",
            "runtime_error_rate", "timeout_rate", "fallback_rate",
            "contract_rejection_rate",
        ):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
        for name in ("llm_call_count", "llm_token_count"):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value < 0):
                raise TypeError(f"{name} must be a non-negative integer or None")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["schema_version"] = PROFILE_SCHEMA_VERSION
        return {"schema_version": payload.pop("schema_version"), **payload}

    def behavioral_vector(self) -> tuple[float, ...]:
        return (
            self.dp_state_switch_fraction,
            self.hv_mode_switch_fraction,
            self.entry_corner_switch_fraction,
            self.exit_corner_switch_fraction,
            self.dp_cascade_ratio,
            self.bottleneck_relief_mean,
            self.travel_time_change,
            self.coverage_time_change,
            self.turning_time_change,
        )


@dataclass
class OperatorCandidate:
    candidate_id: str
    operator_type: str
    source_hash: str
    generation: int
    generation_seed: int
    parent_operator_ids: tuple[str, ...]
    parent_source_hashes: tuple[str, ...] = ()
    prompt_version: str = ""
    creation_mode: str = ""
    split: str = ""
    profile: OperatorBehaviorProfile | None = None
    structural_regimes: tuple[str, ...] = ()
    syntax_valid: bool = True
    contract_valid: bool = True
    feasible: bool = True
    deployable: bool = True
    timeout_heavy: bool = False
    fallback_heavy: bool = False
    runtime_acceptable: bool = True
    trusted_fixture_id: str = ""
    intrinsic_features: dict[str, float] | None = None
    before_state_chain: dict[int, tuple[str, str, str]] | None = None
    after_state_chain: dict[int, tuple[str, str, str]] | None = None
    affected_task_ids: tuple[int, ...] = ()
    directly_moved_task_ids: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.operator_type or not self.source_hash:
            raise ValueError("candidate identity fields are required")
        if type(self.generation) is not int or self.generation < 0:
            raise TypeError("generation must be a non-negative integer")
        if type(self.generation_seed) is not int:
            raise TypeError("generation_seed must be an integer")
        if self.profile is None:
            raise ValueError("candidate profile is required")
        if self.generation > 0 and len(self.parent_source_hashes) != len(self.parent_operator_ids):
            raise ValueError("each parent ID requires a parent source hash")
        if self.split in FORBIDDEN_SPLITS:
            raise ValueError(f"forbidden split: {self.split}")
        for flag_name in (
            "syntax_valid", "contract_valid", "feasible", "deployable",
            "timeout_heavy", "fallback_heavy", "runtime_acceptable",
        ):
            if type(getattr(self, flag_name)) is not bool:
                raise TypeError(f"{flag_name} must be a literal boolean")
        required_features = {
            "task_robot_ratio", "heavy_task_ratio", "spatial_dispersion",
            "hv_gap", "travel_coverage_ratio",
        }
        feature_source = self.intrinsic_features
        if feature_source is None and required_features <= set(self.profile.regime_context):
            feature_source = {
                name: float(self.profile.regime_context[name])
                for name in required_features
            }
        if feature_source is not None:
            derived = derive_structural_regimes(feature_source)
            if tuple(self.structural_regimes) != tuple(derived):
                raise ValueError("candidate structural regimes must match intrinsic structural regimes")
            self.intrinsic_features = dict(feature_source)
        if self.before_state_chain is not None or self.after_state_chain is not None:
            if self.before_state_chain is None or self.after_state_chain is None:
                raise ValueError("both before and after state chains are required")
            bound = bind_dp_behavior_metrics(
                self.profile,
                before=self.before_state_chain,
                after=self.after_state_chain,
                affected_task_ids=self.affected_task_ids,
                directly_moved_task_ids=self.directly_moved_task_ids,
            )
            self.profile = bound

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["parent_operator_ids"] = list(self.parent_operator_ids)
        payload["structural_regimes"] = list(self.structural_regimes)
        payload["profile"] = self.profile.to_dict()
        payload["eligibility_reasons"] = list(eligibility_reasons(self))
        payload["eligible"] = candidate_is_eligible(self)
        return payload


class OperatorArchive:
    """Deterministic structured archive, separate from a deployable set."""

    def __init__(self) -> None:
        self.schema_version = ARCHIVE_SCHEMA_VERSION
        self._records: dict[str, OperatorCandidate] = {}
        self._elites: dict[int, list[str]] = {}

    def add(self, candidate: OperatorCandidate) -> None:
        if candidate.candidate_id in self._records:
            raise ValueError(f"duplicate candidate_id: {candidate.candidate_id}")
        if candidate.generation > 0 and not candidate.parent_operator_ids:
            raise ValueError("generation > 0 candidate requires a parent")
        missing = [parent for parent in candidate.parent_operator_ids if parent not in self._records]
        if missing:
            raise ValueError(f"parent candidates missing: {', '.join(missing)}")
        for parent_id, supplied_hash in zip(
            candidate.parent_operator_ids, candidate.parent_source_hashes
        ):
            if self._records[parent_id].source_hash != supplied_hash:
                raise ValueError(f"parent source hash mismatch: {parent_id}")
        self._records[candidate.candidate_id] = candidate

    def get(self, candidate_id: str) -> OperatorCandidate:
        return self._records[candidate_id]

    def records(self) -> list[OperatorCandidate]:
        return [self._records[key] for key in sorted(self._records)]

    def retain_elite(self, candidate_id: str, *, generation: int) -> None:
        candidate = self.get(candidate_id)
        if candidate.generation != generation:
            raise ValueError("elite generation does not match candidate generation")
        self._elites.setdefault(generation, [])
        if candidate_id not in self._elites[generation]:
            self._elites[generation].append(candidate_id)
            self._elites[generation].sort()

    def elites_for_generation(self, generation: int) -> tuple[str, ...]:
        return tuple(self._elites.get(generation, ()))

    def to_jsonl(self) -> str:
        return "".join(json.dumps(record.to_dict(), sort_keys=True) + "\n" for record in self.records())


def eligibility_reasons(candidate: OperatorCandidate) -> tuple[str, ...]:
    reasons: list[str] = []
    checks = (
        (not candidate.syntax_valid, "syntax-invalid"),
        (not candidate.contract_valid, "contract-invalid"),
        (not candidate.feasible, "infeasible"),
        (candidate.timeout_heavy, "timeout-heavy"),
        (candidate.fallback_heavy, "fallback-heavy"),
        (not candidate.runtime_acceptable, "runtime-unacceptable"),
        (not candidate.deployable, "not-deployable"),
        (candidate.profile.runtime_error_rate > 0.0, "runtime-error"),
        (candidate.profile.timeout_rate > 0.0, "timeout-heavy-profile"),
        (candidate.profile.fallback_rate > 0.0, "fallback-heavy-profile"),
        (candidate.profile.contract_rejection_rate > 0.0, "contract-invalid-profile"),
        (candidate.profile.valid_solution_rate < 1.0, "invalid-solution-rate"),
    )
    return tuple(reason for failed, reason in checks if failed)


def candidate_is_eligible(candidate: OperatorCandidate) -> bool:
    return not eligibility_reasons(candidate)


def bind_dp_behavior_metrics(
    profile: OperatorBehaviorProfile,
    *,
    before: Mapping[int, tuple[str, str, str]],
    after: Mapping[int, tuple[str, str, str]],
    affected_task_ids: Iterable[int],
    directly_moved_task_ids: Iterable[int],
) -> OperatorBehaviorProfile:
    """Bind R5 profile fields to the canonical R3 state-chain computation."""
    affected_task_ids = tuple(affected_task_ids)
    directly_moved_task_ids = tuple(directly_moved_task_ids)
    from ...experiments.r3_diagnostics import state_chain_diff

    metrics = state_chain_diff(
        before,
        after,
        affected_task_ids=affected_task_ids,
        directly_moved_task_ids=directly_moved_task_ids,
    )
    comparable = len(set(affected_task_ids) & set(before) & set(after))
    denominator = max(1, comparable)
    return replace(
        profile,
        dp_state_switch_fraction=float(metrics["state_changed_fraction"]),
        hv_mode_switch_fraction=float(metrics["mode_switch_fraction"]),
        entry_corner_switch_fraction=float(metrics["entry_corner_changed_count"]) / denominator,
        exit_corner_switch_fraction=float(metrics["exit_corner_changed_count"]) / denominator,
        dp_cascade_count=int(metrics["cascade_count"]),
        dp_cascade_ratio=float(metrics["dp_cascade_ratio"]),
    )


@dataclass(frozen=True)
class SelectionConfig:
    minimum_quality_floor: float = 0.0
    set_size: int = 1
    selection_split: str = "selection-validation"
    minimum_valid_solution_rate: float = 1.0

    def __post_init__(self) -> None:
        if not 1 <= self.set_size <= 4:
            raise ValueError("set_size must be in [1, 4]")
        _finite(self.minimum_quality_floor, "minimum_quality_floor")
        if not 0.0 <= self.minimum_valid_solution_rate <= 1.0:
            raise ValueError("minimum_valid_solution_rate must be in [0, 1]")
        if self.selection_split != "selection-validation":
            raise ValueError("selection must be frozen on selection-validation")


@dataclass
class SelectionResult:
    selected: list[OperatorCandidate]
    trace: list[str]


def _quality(candidate: OperatorCandidate) -> float:
    return candidate.profile.relative_improvement


def normalized_behavioral_vector(profile: OperatorBehaviorProfile) -> tuple[float, ...]:
    """Return a fixed, interpretable normalization for the DP response vector."""
    raw = profile.behavioral_vector()
    normalized: list[float] = []
    for index, value in enumerate(raw):
        if index <= 5:
            normalized.append(max(-1.0, min(1.0, value)))
        else:
            normalized.append(math.tanh(value))
    return tuple(normalized)


def dp_behavior_distance(first: OperatorCandidate, second: OperatorCandidate) -> float:
    left, right = normalized_behavioral_vector(first.profile), normalized_behavioral_vector(second.profile)
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(left, right)))


def select_complementary_set(
    candidates: Sequence[OperatorCandidate], config: SelectionConfig
) -> SelectionResult:
    trace: list[str] = []
    eligible: list[OperatorCandidate] = []
    for candidate in sorted(candidates, key=lambda item: item.candidate_id):
        reasons = eligibility_reasons(candidate)
        if reasons:
            trace.append(f"{candidate.candidate_id} rejected: ineligible ({', '.join(reasons)})")
        elif candidate.split != config.selection_split:
            trace.append(f"{candidate.candidate_id} rejected: split is not {config.selection_split}")
        else:
            eligible.append(candidate)
    floored = [
        candidate
        for candidate in eligible
        if _quality(candidate) >= config.minimum_quality_floor
        and candidate.profile.valid_solution_rate >= config.minimum_valid_solution_rate
    ]
    for candidate in eligible:
        if candidate not in floored:
            reason = "below quality floor" if _quality(candidate) < config.minimum_quality_floor else "below reliability floor"
            trace.append(f"{candidate.candidate_id} rejected: {reason}")
    if not floored:
        trace.append("no_eligible_operator_set")
        return SelectionResult([], trace)

    anchor = sorted(floored, key=lambda item: (-_quality(item), item.candidate_id))[0]
    selected = [anchor]
    trace.append(f"{anchor.candidate_id} selected: quality anchor")
    if config.set_size == 1:
        return SelectionResult(selected, trace)

    while len(selected) < config.set_size:
        pool = [candidate for candidate in floored if candidate not in selected]
        if not pool:
            break
        covered = set().union(*(set(item.structural_regimes) for item in selected))
        marginal = {item.candidate_id: len(set(item.structural_regimes) - covered) for item in pool}
        maximum = max(marginal.values())
        stage4 = [item for item in pool if marginal[item.candidate_id] == maximum]
        if maximum:
            trace.append("stage 4: maximum marginal structural-regime coverage")
        else:
            trace.append("stage 4: no new structural regime; use DP tie-break")
        if len(stage4) > 1 or maximum == 0:
            distances = {
                item.candidate_id: min(dp_behavior_distance(item, chosen) for chosen in selected)
                for item in stage4
            }
            best_distance = max(distances.values())
            stage5 = [item for item in stage4 if math.isclose(distances[item.candidate_id], best_distance)]
            chosen = sorted(stage5, key=lambda item: (-_quality(item), item.candidate_id))[0]
            trace.append(f"{chosen.candidate_id} selected: exact-DP behavioral complementarity tie-break")
        else:
            chosen = sorted(stage4, key=lambda item: (-_quality(item), item.candidate_id))[0]
            trace.append(f"{chosen.candidate_id} selected: marginal structural-regime coverage")
        selected.append(chosen)
    return SelectionResult(selected, trace)


@dataclass
class Counterexample:
    failure_axis: str
    failure_code: str
    comparator: str
    regime_context: dict[str, Any]
    structural_evidence: dict[str, Any]
    expected_invariant: str

    def __post_init__(self) -> None:
        if self.failure_axis not in {"execution", "feasibility", "optimization", "generalization"}:
            raise ValueError("invalid counterexample failure_axis")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_counterexample_feedback(counterexample: Counterexample, *, mode: str) -> dict[str, Any]:
    if mode not in COUNTEREXAMPLE_MODES:
        raise ValueError(f"unsupported counterexample mode: {mode}")
    if mode == "C0":
        return {"schema_version": "r5-counterexample-v1", "mode": mode}
    payload = {"mode": mode, "failure_axis": counterexample.failure_axis}
    if mode == "C1":
        payload["failure_code"] = counterexample.failure_code
    else:
        payload["counterexample"] = counterexample.to_dict()
    if mode == "C3":
        payload["mismatch_control"] = True
    return {"schema_version": "r5-counterexample-v1", **payload}


def build_structured_feedback(
    candidates: Sequence[OperatorCandidate], *, mode: str, top_k: int = 2,
    counterexample: Counterexample | None = None,
) -> dict[str, Any]:
    if mode not in FEEDBACK_MODES:
        raise ValueError(f"unsupported feedback mode: {mode}")
    if top_k < 1:
        raise ValueError("top_k must be positive")
    ordered = sorted(candidates, key=lambda item: (-_quality(item), item.candidate_id))
    payload: dict[str, Any] = {
        "schema_version": FEEDBACK_SCHEMA_VERSION,
        "mode": mode,
        "scalar_quality": [{"candidate_id": item.candidate_id, "relative_improvement": _quality(item)} for item in ordered],
    }
    if mode in {"F1", "F2", "F3"}:
        payload["top_operators"] = [item.candidate_id for item in ordered[:top_k]]
        payload["weak_operators"] = [item.candidate_id for item in ordered[-top_k:]]
    if mode in {"F2", "F3"}:
        payload["behavior_profiles"] = [item.profile.to_dict() | {"candidate_id": item.candidate_id} for item in ordered]
    if mode == "F3":
        payload["counterexamples"] = [] if counterexample is None else [build_counterexample_feedback(counterexample, mode="C2")]
    return payload


@dataclass(frozen=True)
class SplitManifest:
    manifest_id: str
    split: str
    entry_ids: tuple[str, ...]
    provenance: str = "r5-fresh-trusted-fixture"


def validate_split_manifests(manifests: Sequence[SplitManifest]) -> None:
    seen: set[str] = set()
    for manifest in manifests:
        if manifest.split in FORBIDDEN_SPLITS:
            raise ValueError(f"{manifest.split} is diagnostic-heldout-consumed or locked")
        if manifest.split not in ALLOWED_SPLITS:
            raise ValueError(f"unsupported R5 split: {manifest.split}")
        for entry_id in manifest.entry_ids:
            if entry_id in seen:
                raise ValueError(f"split leakage for entry: {entry_id}")
            seen.add(entry_id)


def build_r5_split_manifests(*, consumed: bool = False) -> list[SplitManifest]:
    if consumed:
        return [SplitManifest("r3-consumed", "diagnostic-heldout-consumed", ("r3-heldout-001",))]
    manifests = [
        SplitManifest("r5-development-v1", "evolution-development", ("r5-dev-001", "r5-dev-002")),
        SplitManifest("r5-selection-v1", "selection-validation", ("r5-sel-001", "r5-sel-002")),
        SplitManifest("r5-confirmatory-v1", "confirmatory-heldout", ("r5-conf-001", "r5-conf-002")),
    ]
    validate_split_manifests(manifests)
    return manifests


@dataclass(frozen=True)
class BudgetEntry:
    evolution_run_id: str
    generation: int
    candidate_count: int
    evaluation_count: int
    provider_call_count: int
    token_count: int | None
    cost: float | None
    wall_clock_ms: float
    status: str
    candidate_id: str = ""
    instance_id: str = ""
    solver_seed: int | None = None


@dataclass(frozen=True)
class EvaluationAddress:
    evolution_run_id: str
    generation: int
    candidate_id: str
    instance_id: str
    solver_seed: int
    instance_replicate_id: str = "replicate-000"
    result: dict[str, Any] = field(default_factory=dict)
    evaluation_id: str = ""

    def __post_init__(self) -> None:
        if not self.evolution_run_id or not self.candidate_id or not self.instance_id:
            raise ValueError("evaluation hierarchy identifiers are required")
        if self.generation < 0:
            raise ValueError("generation must be non-negative")
        if not self.instance_replicate_id:
            raise ValueError("instance_replicate_id is required")
        expected = _evaluation_id(self)
        if self.evaluation_id and self.evaluation_id != expected:
            raise ValueError("evaluation_id does not match evaluation address")
        object.__setattr__(self, "evaluation_id", expected)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "EvaluationAddress":
        return cls(**dict(value))


def _evaluation_id(address: EvaluationAddress) -> str:
    payload = {
        "schema_version": EVALUATION_SCHEMA_VERSION,
        "evolution_run_id": address.evolution_run_id,
        "generation": address.generation,
        "candidate_id": address.candidate_id,
        "instance_id": address.instance_id,
        "instance_replicate_id": address.instance_replicate_id,
        "solver_seed": address.solver_seed,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class EliteRetentionEvent:
    evolution_run_id: str
    generation_from: int
    generation_to: int
    elite_candidate_id: str
    elite_source_hash: str
    retention_mode: str


def validate_elite_retention_events(
    archive: OperatorArchive, events: Sequence[EliteRetentionEvent]
) -> bool:
    records = archive.records()
    for event in events:
        if event.retention_mode not in {"unchanged", "selected_as_parent"}:
            raise ValueError("invalid elite retention mode")
        try:
            elite = archive.get(event.elite_candidate_id)
        except KeyError as exc:
            raise ValueError("elite candidate missing") from exc
        if elite.source_hash != event.elite_source_hash:
            raise ValueError("elite source hash mismatch")
        if event.generation_from != elite.generation or event.generation_to <= event.generation_from:
            raise ValueError("elite generation transition is invalid")
        unchanged = any(
            item.generation == event.generation_to
            and item.candidate_id == event.elite_candidate_id
            and item.source_hash == event.elite_source_hash
            for item in records
        )
        parent_reuse = any(
            item.generation == event.generation_to
            and any(
                parent_id == event.elite_candidate_id
                and parent_hash == event.elite_source_hash
                for parent_id, parent_hash in zip(
                    item.parent_operator_ids, item.parent_source_hashes
                )
            )
            for item in records
        )
        if event.retention_mode == "unchanged" and not unchanged:
            raise ValueError("elite unchanged retention is not present")
        if event.retention_mode == "selected_as_parent" and not parent_reuse:
            raise ValueError("elite parent reuse is not present")
    return True


class BudgetLedger:
    def __init__(self) -> None:
        self.schema_version = LEDGER_SCHEMA_VERSION
        self.entries: list[BudgetEntry] = []
        self.evaluations: list[EvaluationAddress] = []

    def record(self, entry: BudgetEntry) -> None:
        if entry.generation < 0 or entry.candidate_count < 0 or entry.evaluation_count < 0:
            raise ValueError("budget counts must be non-negative")
        self.entries.append(entry)

    def record_evaluation(self, address: EvaluationAddress) -> None:
        if any(item.evaluation_id == address.evaluation_id for item in self.evaluations):
            raise ValueError(f"duplicate evaluation: {address.evaluation_id}")
        self.evaluations.append(address)

    def assert_equal_budget(self) -> bool:
        if not self.entries:
            return True
        baseline = tuple(
            (entry.candidate_count, entry.evaluation_count, entry.provider_call_count, entry.token_count, entry.cost)
            for entry in self.entries
        )
        return len(set(baseline)) == 1

    def to_dicts(self) -> list[dict[str, Any]]:
        return [asdict(entry) for entry in self.entries]


def aggregate_yields(records: Sequence[OperatorCandidate], *, quality_floor: float = 0.5) -> dict[str, float]:
    if not records:
        return {name: 0.0 for name in ("syntax_valid_yield", "contract_valid_yield", "feasible_yield", "deployable_yield", "quality_conditioned_yield")}
    n = len(records)
    return {
        "syntax_valid_yield": sum(item.syntax_valid for item in records) / n,
        "contract_valid_yield": sum(item.contract_valid for item in records) / n,
        "feasible_yield": sum(item.feasible for item in records) / n,
        "deployable_yield": sum(item.deployable for item in records) / n,
        "quality_conditioned_yield": sum(candidate_is_eligible(item) and _quality(item) >= quality_floor for item in records) / n,
    }


def aggregate_evaluation_results(
    records: Sequence[EvaluationAddress],
) -> dict[str, dict[str, float]]:
    """Derive candidate aggregates from persisted candidate×trial records."""
    grouped: dict[str, list[float]] = {}
    for record in records:
        value = record.result.get("relative_improvement")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("evaluation result is missing relative_improvement")
        grouped.setdefault(record.candidate_id, []).append(float(value))
    return {
        candidate_id: {
            "trial_count": float(len(values)),
            "mean_relative_improvement": sum(values) / len(values),
        }
        for candidate_id, values in sorted(grouped.items())
    }


def deploy_operator(
    selected: Sequence[OperatorCandidate], *, policy: str, seed: int = 0,
    instance_regimes: Sequence[str] = (),
) -> OperatorCandidate:
    if not selected:
        raise ValueError("cannot deploy an empty operator set")
    if policy == "P0":
        return sorted(selected, key=lambda item: (-_quality(item), item.candidate_id))[0]
    if policy == "P1":
        return random.Random(seed).choice(list(selected))
    if policy == "P2":
        target = set(instance_regimes)
        return sorted(selected, key=lambda item: (-len(target & set(item.structural_regimes)), -_quality(item), item.candidate_id))[0]
    raise ValueError("P3 is not implemented in R5")


@dataclass
class MockPipelineResult:
    archive: OperatorArchive
    budget_ledger: BudgetLedger
    selected_set: list[OperatorCandidate]
    feedback_payloads: dict[str, dict[str, Any]]
    selection_trace: list[str]
    scenarios: dict[str, bool]
    output_contract: dict[str, Any]
    elite_retention_events: list[EliteRetentionEvent]


@dataclass(frozen=True)
class TrustedFixtureEntry:
    fixture_id: str
    relative_path: str
    expected_sha256: str
    fixture_type: str
    schema_version: str


class TrustedFixtureRegistry:
    """Allowlisted, hash-bound, root-confined trusted fixture registry."""

    def __init__(self, root: str | Path, entries: Sequence[TrustedFixtureEntry]) -> None:
        self.root = Path(root).resolve(strict=True)
        self.entries = {entry.fixture_id: entry for entry in entries}
        if len(self.entries) != len(entries):
            raise ValueError("duplicate trusted fixture ID")
        for entry in entries:
            self.validate_path(entry.relative_path)
            if len(entry.expected_sha256) != 64 or any(c not in "0123456789abcdef" for c in entry.expected_sha256.lower()):
                raise ValueError("invalid trusted fixture SHA-256")

    def validate_path(self, relative_path: str) -> Path:
        candidate = Path(relative_path)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError("fixture path is not confined")
        resolved = (self.root / candidate).resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("fixture path is not confined") from exc
        return resolved

    def resolve(self, fixture_id: str) -> TrustedFixtureEntry:
        try:
            return self.entries[fixture_id]
        except KeyError as exc:
            raise ValueError(f"fixture is not registered: {fixture_id}") from exc

    def verify_content(self, entry: TrustedFixtureEntry) -> Path:
        path = self.validate_path(entry.relative_path)
        if not path.is_file():
            raise ValueError("registered fixture file is missing")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != entry.expected_sha256:
            raise ValueError("trusted fixture content hash mismatch")
        return path


class TrustedFixtureFileProvider:
    """Explicit JSON fixture manifest reader; never imports or executes source."""

    def __init__(self, manifest_path: str | Path, *, registry: TrustedFixtureRegistry | None = None, dry_run: bool = True) -> None:
        if dry_run is not True:
            raise ValueError("R5 file provider requires dry_run=True")
        if registry is None:
            raise ValueError("R5 file provider requires a trusted fixture registry")
        self.manifest_path = Path(manifest_path)
        self.registry = registry
        self.executed_source_paths: list[str] = []

    def load_fixture_ids(self) -> list[str]:
        document = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        if set(document) != {"schema_version", "fixtures"} or document["schema_version"] != FIXTURE_MANIFEST_SCHEMA_VERSION:
            raise ValueError("invalid trusted fixture manifest")
        if type(document["fixtures"]) is not list:
            raise ValueError("fixtures must be a list")
        ids: list[str] = []
        for fixture in document["fixtures"]:
            if type(fixture) is not dict or set(fixture) != {"fixture_id", "operator_type", "source_hash"}:
                raise ValueError("fixture manifest entries must be explicit metadata")
            entry = self.registry.resolve(fixture["fixture_id"])
            if entry.schema_version != document["schema_version"] or entry.fixture_type != "json":
                raise ValueError("trusted fixture schema/type mismatch")
            if fixture["source_hash"] != entry.expected_sha256:
                raise ValueError("fixture source hash does not match registry")
            self.registry.verify_content(entry)
            ids.append(fixture["fixture_id"])
        return ids


class TrustedFixtureMockProvider:
    """Deterministic provider that returns structured fixture records only."""

    def __init__(self, fixtures: Sequence[OperatorCandidate]) -> None:
        self.fixtures = tuple(fixtures)
        self.provider_call_count = 0

    def generate(self, *, generation: int, feedback_mode: str) -> list[OperatorCandidate]:
        if generation < 0:
            raise ValueError("generation must be non-negative")
        if feedback_mode not in FEEDBACK_MODES:
            raise ValueError(f"unsupported feedback mode: {feedback_mode}")
        self.provider_call_count += 1
        if generation == 0:
            return list(self.fixtures)
        return [
            replace(
                candidate,
                candidate_id=f"{candidate.candidate_id}-g{generation}",
                source_hash=hashlib.sha256(f"{candidate.source_hash}:{generation}".encode()).hexdigest(),
                generation=generation,
                generation_seed=generation,
                parent_operator_ids=(candidate.candidate_id,),
                parent_source_hashes=(candidate.source_hash,),
                creation_mode="revision",
            )
            for candidate in self.fixtures
        ]


def derive_structural_regimes(features: Mapping[str, float]) -> tuple[str, ...]:
    """Bin only intrinsic instance features; solver outcomes are not accepted."""
    required = {"task_robot_ratio", "heavy_task_ratio", "spatial_dispersion", "hv_gap", "travel_coverage_ratio"}
    missing = required - set(features)
    if missing:
        raise ValueError(f"missing intrinsic features: {sorted(missing)}")
    ratio = features["task_robot_ratio"]
    load = "load:low" if ratio < 5 else "load:medium" if ratio <= 8 else "load:high"
    heavy = "heavy:low" if features["heavy_task_ratio"] < 1.5 else "heavy:high"
    spatial = "spatial:compact" if features["spatial_dispersion"] < 5 else "spatial:dispersed"
    hv = "hv:low" if features["hv_gap"] < 1.0 else "hv:high"
    travel = "travel-dominated" if features["travel_coverage_ratio"] >= 1.0 else "coverage-dominated"
    return (load, heavy, spatial, hv, travel)


def _fixture_profile(quality: float, *, regime: dict[str, str | float]) -> OperatorBehaviorProfile:
    return OperatorBehaviorProfile(
        baseline_makespan=100.0,
        candidate_makespan=100.0 - 10.0 * quality,
        absolute_improvement=10.0 * quality,
        relative_improvement=quality,
        success_rate=1.0,
        assignment_change_count=1,
        tasks_moved_out_of_bottleneck=1,
        tasks_moved_into_bottleneck=0,
        bottleneck_relief_mean=quality,
        bottleneck_relief_rate=1.0,
        max_route_cost_change=-quality,
        route_cost_cv_change=-quality / 2,
        dp_state_switch_fraction=0.2 + quality / 2,
        hv_mode_switch_fraction=0.1 + quality / 3,
        entry_corner_switch_fraction=0.1,
        exit_corner_switch_fraction=0.1,
        dp_cascade_count=1,
        dp_cascade_ratio=0.1 + quality / 3,
        travel_time_change=-quality,
        coverage_time_change=-quality / 2,
        turning_time_change=0.0,
        valid_solution_rate=1.0,
        runtime_error_rate=0.0,
        timeout_rate=0.0,
        fallback_rate=0.0,
        contract_rejection_rate=0.0,
        candidate_runtime=10.0,
        route_dp_evaluation_count=4,
        cache_hit_rate=0.5,
        regime_context=regime,
    )


def build_trusted_fixtures() -> list[OperatorCandidate]:
    specs = (
        ("bottleneck-relief", 0.80, ("load:high", "travel:balanced"), True, True),
        ("geometry-sensitive", 0.65, ("hv:high", "spatial:dispersed"), True, True),
        ("load-agnostic", 0.55, ("load:medium", "travel:coverage"), True, True),
        ("weak-valid", 0.10, ("load:low",), True, True),
        ("invalid-metadata", 0.75, ("load:high",), False, False),
    )
    records: list[OperatorCandidate] = []
    fixture_states = {
        fixture_id: (
            {1: ("H", "LB", "RT"), 2: ("H", "LB", "RT"), 3: ("V", "LT", "RB")},
            {1: ("V", "LB", "RT"), 2: ("H", "RB", "RT"), 3: ("V", "LT", "LB")},
        )
        for fixture_id, *_ in specs
    }
    for fixture_id, quality, regimes, contract_valid, deployable in specs:
        before, after = fixture_states[fixture_id]
        features = {
            "task_robot_ratio": 10.0 if fixture_id == "bottleneck-relief" else 3.0,
            "heavy_task_ratio": 2.0 if fixture_id == "geometry-sensitive" else 1.0,
            "spatial_dispersion": 8.0 if fixture_id == "geometry-sensitive" else 2.0,
            "hv_gap": 2.0 if fixture_id == "geometry-sensitive" else 0.2,
            "travel_coverage_ratio": 1.5 if fixture_id == "bottleneck-relief" else 0.5,
        }
        records.append(
            OperatorCandidate(
                candidate_id=fixture_id,
                operator_type="repair",
                source_hash=hashlib.sha256(f"trusted-fixture:{fixture_id}".encode()).hexdigest(),
                generation=0,
                generation_seed=0,
                parent_operator_ids=(),
                prompt_version="r5-fixture-v1",
                creation_mode="scripted_fixture",
                split="selection-validation",
                profile=_fixture_profile(quality, regime=features),
                structural_regimes=derive_structural_regimes(features),
                contract_valid=contract_valid,
                deployable=deployable,
                trusted_fixture_id=fixture_id,
                intrinsic_features=features,
                before_state_chain=before,
                after_state_chain=after,
                affected_task_ids=(1, 2, 3),
                directly_moved_task_ids=(1,),
            )
        )
    return records


def _write_outputs(result: MockPipelineResult, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "metadata.json").write_text(json.dumps(result.output_contract, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (output_dir / "candidate_archive.jsonl").write_text(result.archive.to_jsonl(), encoding="utf-8")
    (output_dir / "evolution_runs.jsonl").write_text(
        "".join(json.dumps({"evolution_run_id": entry.evolution_run_id, "generation": entry.generation}, sort_keys=True) + "\n" for entry in result.budget_ledger.entries),
        encoding="utf-8",
    )
    (output_dir / "behavior_profiles.jsonl").write_text(
        "".join(json.dumps({"candidate_id": item.candidate_id, **item.profile.to_dict()}, sort_keys=True) + "\n" for item in result.archive.records()),
        encoding="utf-8",
    )
    (output_dir / "budget_ledger.json").write_text(json.dumps(result.budget_ledger.to_dicts(), sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (output_dir / "evaluation_records.jsonl").write_text(
        "".join(json.dumps(item.to_dict(), sort_keys=True) + "\n" for item in result.budget_ledger.evaluations),
        encoding="utf-8",
    )
    (output_dir / "elite_retention_events.jsonl").write_text(
        "".join(json.dumps(asdict(item), sort_keys=True) + "\n" for item in result.elite_retention_events),
        encoding="utf-8",
    )
    with (output_dir / "budget_ledger.csv").open("w", encoding="utf-8", newline="") as handle:
        if result.budget_ledger.entries:
            writer = csv.DictWriter(handle, fieldnames=list(asdict(result.budget_ledger.entries[0]).keys()))
            writer.writeheader()
            writer.writerows(result.budget_ledger.to_dicts())
    (output_dir / "yield_summary.json").write_text(json.dumps(aggregate_yields(result.archive.records()), sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (output_dir / "operator_sets.json").write_text(json.dumps([item.to_dict() for item in result.selected_set], sort_keys=True, indent=2) + "\n", encoding="utf-8")
    trace_dir = output_dir / "selection_traces"
    trace_dir.mkdir(exist_ok=True)
    (trace_dir / "selection.json").write_text(json.dumps(result.selection_trace, indent=2) + "\n", encoding="utf-8")
    feedback_dir = output_dir / "feedback_payloads"
    feedback_dir.mkdir(exist_ok=True)
    for mode, payload in result.feedback_payloads.items():
        (feedback_dir / f"{mode}.json").write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def run_mock_pipeline(
    fixtures: Sequence[OperatorCandidate], *, generations: int = 2, set_size: int = 2,
    output_dir: str | Path | None = None,
) -> MockPipelineResult:
    if generations < 1:
        raise ValueError("generations must be positive")
    archive = OperatorArchive()
    ledger = BudgetLedger()
    initial = list(fixtures)
    for candidate in initial:
        archive.add(candidate)
    provider = TrustedFixtureMockProvider(initial)
    feedback_payloads: dict[str, dict[str, Any]] = {}
    elite_events: list[EliteRetentionEvent] = []
    run_id = "r5-mock-run-000"
    for generation in range(generations):
        current = provider.generate(generation=generation, feedback_mode="F2" if generation else "F0")
        if generation > 0:
            for candidate in current:
                archive.add(candidate)
        eligible = [candidate for candidate in current if candidate_is_eligible(candidate)]
        if eligible:
            elite = sorted(eligible, key=lambda item: (-_quality(item), item.candidate_id))[0]
            archive.retain_elite(elite.candidate_id, generation=generation)
            if generation + 1 < generations:
                elite_events.append(EliteRetentionEvent(
                    evolution_run_id=run_id,
                    generation_from=generation,
                    generation_to=generation + 1,
                    elite_candidate_id=elite.candidate_id,
                    elite_source_hash=elite.source_hash,
                    retention_mode="selected_as_parent",
                ))
        for candidate in current:
            ledger.record_evaluation(EvaluationAddress(
                run_id, generation, candidate.candidate_id,
                "r5-fixture-instance-001", 0,
                instance_replicate_id="replicate-000",
                result={"relative_improvement": _quality(candidate)},
            ))
        feedback = build_structured_feedback(current, mode="F2" if generation else "F0")
        feedback_payloads[f"generation-{generation}-F{2 if generation else 0}"] = feedback
        ledger.record(BudgetEntry(run_id, generation, len(current), len(current), 1, 0, 0.0, 0.0, "complete"))

    all_records = archive.records()
    selection = select_complementary_set(all_records, SelectionConfig(minimum_quality_floor=0.5, set_size=set_size))
    selected = selection.selected
    counterexample = Counterexample(
        failure_axis="optimization",
        failure_code="bottleneck_regression",
        comparator="trusted-baseline",
        regime_context={"load_pressure": "high"},
        structural_evidence={"dp_cascade_ratio": 0.4},
        expected_invariant="candidate remains contract-valid",
    )
    feedback_payloads["F3"] = build_structured_feedback(all_records[:3], mode="F3", counterexample=counterexample)
    naive = sorted([item for item in all_records if candidate_is_eligible(item)], key=lambda item: (-_quality(item), item.candidate_id))[:set_size]
    scenarios = {
        "A": "generation-0-F0" in feedback_payloads and "generation-1-F2" in feedback_payloads and "dp_state_switch_fraction" not in json.dumps(feedback_payloads["generation-0-F0"]),
        "B": bool(archive.elites_for_generation(0)) and any(candidate.parent_operator_ids for candidate in all_records if candidate.generation > 0),
        "C": bool(selected) and [item.candidate_id for item in selected] != [item.candidate_id for item in naive],
        "D": feedback_payloads["F3"].get("counterexamples") is not None,
    }
    validate_elite_retention_events(archive, elite_events)
    result = MockPipelineResult(
        archive=archive,
        budget_ledger=ledger,
        selected_set=selected,
        feedback_payloads=feedback_payloads,
        selection_trace=selection.trace,
        scenarios=scenarios,
        output_contract={
            "mock_mode": True,
            "real_provider_used": False,
            "untrusted_candidate_executed": False,
            "pilot_executed": False,
            "formal_experiment_executed": False,
            "final_test_accessed": False,
            "gate_p2": "OPEN",
            "t6_authorized": False,
            "r5_schema_versions": {
                "profile": PROFILE_SCHEMA_VERSION,
                "feedback": FEEDBACK_SCHEMA_VERSION,
                "archive": ARCHIVE_SCHEMA_VERSION,
                "ledger": LEDGER_SCHEMA_VERSION,
            },
            "selected_set_size": len(selected),
            "scenarios": scenarios,
        },
        elite_retention_events=elite_events,
    )
    if output_dir is not None:
        _write_outputs(result, Path(output_dir))
    return result


__all__ = [
    "FEEDBACK_MODES", "OperatorBehaviorProfile", "OperatorCandidate", "OperatorArchive",
    "SelectionConfig", "SelectionResult", "Counterexample", "BudgetEntry", "EvaluationAddress", "BudgetLedger",
    "EliteRetentionEvent", "validate_elite_retention_events",
    "TrustedFixtureEntry", "TrustedFixtureRegistry", "TrustedFixtureFileProvider", "TrustedFixtureMockProvider", "aggregate_yields", "build_counterexample_feedback",
    "build_structured_feedback", "build_r5_split_manifests", "validate_split_manifests",
    "build_trusted_fixtures", "select_complementary_set", "deploy_operator",
    "run_mock_pipeline", "MockPipelineResult", "eligibility_reasons", "candidate_is_eligible",
    "normalized_behavioral_vector", "dp_behavior_distance", "derive_structural_regimes",
]
