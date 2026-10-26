"""Adaptive Large Neighborhood Search for MRTA rectangular coverage."""
from __future__ import annotations

from collections import Counter
import json
import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Callable, Dict, List, Sequence

from ..core.cost_matrix import CostMatrix
from ..core.dp_evaluator import RouteDPEvaluator
from ..core.models import Instance, MultiRobotSolution, SolutionEvaluation
from ..core.solution_evaluator import MultiRobotSolutionEvaluator
from ..core.state_generator import generate_all_states
from ..llm.advisor_interface import Advisor, SearchContext
from ..llm.operator_evolution.protocols import DestroyContext, RepairContext
from ..llm.operator_evolution.candidate_execution import (
    CandidateExecutionResult,
    CandidateProxy,
    TRUSTED_EXECUTOR_IDENTITY,
    TRUSTED_EXECUTOR_SANDBOX_LEVEL,
)
from ..llm.operator_evolution.eligibility_policy import (
    validate_frozen_deployment_authorization,
    validate_registry_metadata,
)
from ..llm.operator_evolution.candidate_security import (
    code_sha256,
    validate_candidate_source,
)
from ..llm.operator_evolution.utils import is_solution_complete
from .baseline_solver import resolve_constructor
from .local_search import run_stronger_local_search

DestroyFn = Callable[[MultiRobotSolution, SolutionEvaluation, int], tuple[MultiRobotSolution, List[int]]]
RepairFn = Callable[[MultiRobotSolution, List[int], SolutionEvaluation], MultiRobotSolution]


@dataclass
class ALNSConfig:
    iterations: int | None = 200
    max_runtime_seconds: float | None = None  # Both limits: stop at the first reached.
    destroy_fraction: float = 0.25
    acceptance: str = "improvement_only"  # or "simulated_annealing"
    initial_temperature: float | None = 5.0  # None calibrates from initial makespan.
    cooling_rate: float = 0.985
    cooling_schedule: str = "iteration"  # Legacy, or "progress" (time when bounded).
    initial_worsening_fraction: float = 0.01
    initial_acceptance_probability: float = 0.5
    final_temperature_ratio: float = 0.01
    weight_update: str = "cumulative"  # Legacy, or "segment".
    segment_length: int = 20
    reaction_factor: float = 0.2
    pair_selection_mode: str = "independent"  # Legacy V1, or "coupled" adaptive pair action.
    coupled_destroy_operator: str | None = None
    coupled_repair_operator: str | None = None
    random_seed: int = 0
    use_dp_aware_insertion: bool = False
    frozen_operator_registry_path: str | None = None
    use_frozen_repair: bool = False
    use_frozen_destroy: bool = False
    allow_generated_frozen_deployment: bool = False
    explicit_runtime_deployment_ack: bool = False
    allow_real_provider_frozen_deployment: bool = False
    explicit_runtime_risk_ack: bool = False
    runtime_authorization_source: str = ""

    @classmethod
    def enhanced(cls, **overrides) -> "ALNSConfig":
        """B1 preset; use iterations=None and max_runtime_seconds=n_tasks for E3."""
        options = dict(acceptance="simulated_annealing", initial_temperature=None,
                       cooling_schedule="progress", weight_update="segment")
        options.update(overrides)
        return cls(**options)

    def __post_init__(self) -> None:
        if self.iterations is None and self.max_runtime_seconds is None:
            raise ValueError("at least one termination limit is required")
        if self.iterations is not None and self.iterations < 0:
            raise ValueError("iterations must be nonnegative")
        if self.max_runtime_seconds is not None and (not math.isfinite(self.max_runtime_seconds) or self.max_runtime_seconds <= 0):
            raise ValueError("max_runtime_seconds must be finite and positive")
        if self.acceptance not in {"improvement_only", "simulated_annealing"}:
            raise ValueError("unknown acceptance strategy")
        if self.weight_update not in {"cumulative", "segment"} or self.cooling_schedule not in {"iteration", "progress"}:
            raise ValueError("unknown weight update or cooling schedule")
        if self.segment_length < 1 or not 0 < self.reaction_factor <= 1:
            raise ValueError("segment_length >= 1 and 0 < reaction_factor <= 1 required")
        if not 0 < self.initial_acceptance_probability < 1 or not 0 < self.initial_worsening_fraction < 1:
            raise ValueError("initial probability and worsening fraction must be in (0, 1)")
        if not 0 < self.final_temperature_ratio <= 1 or not 0 < self.cooling_rate <= 1:
            raise ValueError("cooling factors must be in (0, 1]")
        if self.initial_temperature is not None and (not math.isfinite(self.initial_temperature) or self.initial_temperature <= 0):
            raise ValueError("initial_temperature must be finite and positive")


@dataclass
class OperatorRecord:
    uses: int = 0
    score: float = 0.0


@dataclass
class ALNSResult:
    best_solution: MultiRobotSolution
    best_evaluation: SolutionEvaluation
    iteration_history: List[dict]
    operator_usage_stats: Dict[str, Dict[str, OperatorRecord]]
    fallback_events: List[dict] = field(default_factory=list)
    runtime_seconds: float = 0.0  # solve(), including initial evaluation, excluding setup.
    iterations_completed: int = 0
    route_dp_calls: int = 0
    route_dp_cache_misses: int = 0
    termination_reason: str = "iterations"
    initial_temperature: float = 0.0
    initial_makespan: float = 0.0
    pair_action_stats: Dict[str, float | int] = field(default_factory=dict)
    timing_breakdown_seconds: Dict[str, float] = field(default_factory=dict)
    generated_operator_execution: Dict[str, Dict[str, dict]] = field(default_factory=dict)


class ALNSSolver:
    """A research-oriented ALNS framework with problem-specific operators."""

    def __init__(
        self,
        instance: Instance,
        *,
        constructor: str = "spatial_sort",
        config: ALNSConfig | None = None,
        advisor: Advisor | None = None,
    ):
        self.instance = instance
        self.config = config or ALNSConfig()
        if self.config.use_dp_aware_insertion:
            raise ValueError(
                "dp_aware_insertion is a compatibility alias for greedy_insertion, "
                "not an independent repair operator"
            )
        if self.config.pair_selection_mode not in {"independent", "coupled"}:
            raise ValueError("pair_selection_mode must be independent or coupled")
        if self.config.pair_selection_mode == "coupled" and not (
            self.config.coupled_destroy_operator and self.config.coupled_repair_operator
        ):
            raise ValueError("coupled selection requires a configured destroy/repair pair")
        self.advisor = advisor
        self.rng = random.Random(self.config.random_seed)

        self.states_by_task = generate_all_states(instance)
        self.cost_matrix = CostMatrix(
            instance.depot,
            self.states_by_task,
            travel_speed=instance.travel_speed,
        )
        self.route_dp = RouteDPEvaluator(self.cost_matrix, self.states_by_task)
        self.solution_evaluator = MultiRobotSolutionEvaluator(
            self.route_dp, instance=instance
        )
        self._full_evaluation_scope: str | None = None
        self._full_evaluation_time = {"initial": 0.0, "local_search": 0.0}
        original_full_evaluate = self.solution_evaluator.evaluate

        def timed_full_evaluate(solution):
            started = perf_counter()
            try:
                return original_full_evaluate(solution)
            finally:
                if self._full_evaluation_scope is not None:
                    self._full_evaluation_time[self._full_evaluation_scope] += perf_counter() - started

        self.solution_evaluator.evaluate = timed_full_evaluate

        self.initial_solution = resolve_constructor(constructor)(instance)

        self.destroy_ops: Dict[str, DestroyFn] = {
            "random_destroy": self._random_destroy,
            "bottleneck_route_destroy": self._bottleneck_route_destroy,
            "geometry_aware_destroy": self._geometry_aware_destroy,
        }
        self.repair_ops: Dict[str, RepairFn] = {
            "greedy_insertion": self._greedy_insertion,
            "regret_k_insertion": self._regret_k_insertion,
            "bottleneck_balancing_insertion": self._bottleneck_balancing_insertion,
        }
        self.fallback_events: List[dict] = []
        self.generated_route_dp_calls = 0
        self.generated_route_dp_cache_misses = 0
        self.frozen_repair_ops: set[str] = set()
        self.frozen_destroy_ops: set[str] = set()

        self._register_frozen_operators()

        self.destroy_weights = {name: 1.0 for name in self.destroy_ops}
        self.repair_weights = {}
        for name in self.repair_ops:
            self.repair_weights[name] = 1.0

        self.operator_stats: Dict[str, Dict[str, OperatorRecord]] = {
            "destroy": {name: OperatorRecord() for name in self.destroy_ops},
            "repair": {name: OperatorRecord() for name in self.repair_ops},
        }
        self.segment_stats = {
            group: {name: OperatorRecord() for name in records}
            for group, records in self.operator_stats.items()
        }
        self._last_selection_action = "independent"
        self.coupled_selection_preference = 1.0
        self.pair_action_stats = {
            "uses": 0,
            "successful_uses": 0,
            "accepted": 0,
            "global_best": 0,
            "reward": 0.0,
            "fallbacks": 0,
            "independent_coincidental_uses": 0,
        }
        self.pair_selection_segment = {
            "independent": OperatorRecord(),
            "coupled": OperatorRecord(),
        }
        self.generated_operator_execution = {"destroy": {}, "repair": {}}

    def register_development_repair(self, proxy: CandidateProxy, *, name: str) -> None:
        """Add a loader-validated, bounded repair for development experiments."""
        if not isinstance(proxy, CandidateProxy) or not proxy.expected_code_hash:
            raise ValueError("development repair requires a hash-bound CandidateProxy")
        if name in self.repair_ops:
            raise ValueError(f"duplicate repair name: {name}")
        self.repair_ops[name] = self._wrap_external_repair(proxy, name)
        self.frozen_repair_ops.add(name)
        self.repair_weights[name] = 1.0
        self.operator_stats["repair"][name] = OperatorRecord()
        self.segment_stats["repair"][name] = OperatorRecord()

    def register_development_destroy(self, proxy: CandidateProxy, *, name: str) -> None:
        """Add a loader-validated, bounded destroy to the existing adaptive pool."""
        if not isinstance(proxy, CandidateProxy) or not proxy.expected_code_hash:
            raise ValueError("development destroy requires a hash-bound CandidateProxy")
        if name in self.destroy_ops:
            raise ValueError(f"duplicate destroy name: {name}")
        self.destroy_ops[name] = self._wrap_external_destroy(proxy, name)
        self.frozen_destroy_ops.add(name)
        self.destroy_weights[name] = 1.0
        self.operator_stats["destroy"][name] = OperatorRecord()
        self.segment_stats["destroy"][name] = OperatorRecord()

    def solve(self) -> ALNSResult:
        started_at = perf_counter()
        if self.config.pair_selection_mode == "coupled" and (
            self.config.coupled_destroy_operator not in self.destroy_ops
            or self.config.coupled_repair_operator not in self.repair_ops
        ):
            raise ValueError("configured coupled pair must be registered before solve()")
        calls_start = self.route_dp.statistics()["calls"] + self.generated_route_dp_calls
        misses_start = self.route_dp.statistics()["cache_misses"] + self.generated_route_dp_cache_misses
        current_solution = MultiRobotSolution(routes=[list(route) for route in self.initial_solution.routes])
        self._full_evaluation_scope = "initial"
        current_eval = self.solution_evaluator.evaluate(current_solution)
        self._full_evaluation_scope = None
        initial_full_evaluation_seconds = self._full_evaluation_time["initial"]

        best_solution = MultiRobotSolution(routes=[list(route) for route in current_solution.routes])
        best_eval = current_eval
        history: List[dict] = []

        initial_makespan = current_eval.makespan
        initial_temperature = self._initial_temperature(initial_makespan)
        temperature = initial_temperature
        recent_best: List[float] = [best_eval.makespan]
        phase_seconds = {
            "destroy_execution_seconds": 0.0,
            "partial_evaluation_seconds": 0.0,
            "repair_execution_seconds": 0.0,
            "local_search_seconds": 0.0,
        }

        iteration = 0
        termination_reason = "iterations"
        while self.config.iterations is None or iteration < self.config.iterations:
            elapsed = perf_counter() - started_at
            if self.config.max_runtime_seconds is not None and elapsed >= self.config.max_runtime_seconds:
                termination_reason = "time"
                break
            iteration += 1
            iteration_started = perf_counter()
            if self.config.cooling_schedule == "progress":
                temperature = self._progress_temperature(initial_temperature, elapsed, iteration - 1)
            context = self._build_context(best_eval, current_eval, recent_best)
            self._last_selection_action = "independent"
            selection_probability = (self._coupled_selection_probability()
                                     if self.config.pair_selection_mode == "coupled" else 0.0)
            destroy_name, repair_name, phase = self._select_operators(context)

            destroy_fn = self.destroy_ops[destroy_name]
            repair_fn = self.repair_ops[repair_name]
            fallback_event_start = len(self.fallback_events)

            remove_count = max(1, int(self.config.destroy_fraction * self.instance.task_count))
            stage_started = perf_counter()
            partial_solution, removed_tasks = destroy_fn(current_solution, current_eval, remove_count)
            destroy_seconds = perf_counter() - stage_started
            phase_seconds["destroy_execution_seconds"] += destroy_seconds

            stage_started = perf_counter()
            partial_eval = self.solution_evaluator.evaluate_partial(partial_solution)
            partial_evaluation_seconds = perf_counter() - stage_started
            phase_seconds["partial_evaluation_seconds"] += partial_evaluation_seconds

            stage_started = perf_counter()
            repaired_solution = repair_fn(partial_solution, removed_tasks, partial_eval)
            repair_seconds = perf_counter() - stage_started
            phase_seconds["repair_execution_seconds"] += repair_seconds

            stage_started = perf_counter()
            self._full_evaluation_scope = "local_search"
            try:
                refined_solution, refined_eval = run_stronger_local_search(
                    repaired_solution,
                    self.solution_evaluator,
                    max_iterations=1,
                )
            finally:
                self._full_evaluation_scope = None
            local_search_seconds = perf_counter() - stage_started
            phase_seconds["local_search_seconds"] += local_search_seconds

            previous_eval = current_eval
            accepted, reason = self._accept(current_eval, refined_eval, temperature)
            if accepted:
                current_solution = refined_solution
                current_eval = refined_eval

            score = 0.0
            if refined_eval.makespan + 1e-9 < best_eval.makespan:
                best_solution = MultiRobotSolution(routes=[list(route) for route in refined_solution.routes])
                best_eval = refined_eval
                score = 8.0
            elif accepted and refined_eval.makespan + 1e-9 < previous_eval.makespan:
                score = 3.0
            elif accepted:
                score = 1.0

            iteration_fallbacks = self.fallback_events[fallback_event_start:]
            fallback_types = {
                event["operator_type"] for event in iteration_fallbacks
            }
            fallback_used = bool(iteration_fallbacks)
            fallback_reason = "; ".join(
                str(event["fallback_reason"]) for event in iteration_fallbacks
            )
            generated_selected = (
                destroy_name in self.frozen_destroy_ops
                or repair_name in self.frozen_repair_ops
            )
            generated_destroy = destroy_name in self.frozen_destroy_ops
            generated_repair = repair_name in self.frozen_repair_ops
            selected_configured_pair = (
                destroy_name == self.config.coupled_destroy_operator
                and repair_name == self.config.coupled_repair_operator
            )
            coupled_pair_selected = self._last_selection_action == "coupled" and selected_configured_pair
            attribution_ambiguous = (
                fallback_used and generated_destroy and generated_repair
            )
            if attribution_ambiguous:
                destroy_reward = 0.0
                repair_reward = 0.0
                reward_attribution = {
                    "destroy": "ambiguous_excluded",
                    "repair": "ambiguous_excluded",
                }
            else:
                destroy_reward = (
                    0.0
                    if generated_destroy and "destroy" in fallback_types
                    else score
                )
                repair_reward = (
                    0.0
                    if generated_repair and "repair" in fallback_types
                    else score
                )
                reward_attribution = {
                    "destroy": "fallback_excluded"
                    if generated_destroy and "destroy" in fallback_types
                    else "credited",
                    "repair": "fallback_excluded"
                    if generated_repair and "repair" in fallback_types
                    else "credited",
                }

            coupled_pair_fallback = coupled_pair_selected and fallback_used
            if coupled_pair_selected:
                self.pair_action_stats["uses"] += 1
                self.pair_selection_segment["coupled"].uses += 1
                if coupled_pair_fallback:
                    self.pair_action_stats["fallbacks"] += 1
                else:
                    self.pair_action_stats["successful_uses"] += 1
                    self.pair_action_stats["accepted"] += int(accepted)
                    new_global_best = score >= 8.0
                    self.pair_action_stats["global_best"] += int(new_global_best)
                    self.pair_action_stats["reward"] += score
                    self.pair_selection_segment["coupled"].score += score
            elif self.config.pair_selection_mode == "coupled":
                self.pair_selection_segment["independent"].uses += 1
                self.pair_selection_segment["independent"].score += score

            self._update_operator_stats("destroy", destroy_name, destroy_reward)
            self._update_operator_stats("repair", repair_name, repair_reward)
            if self.config.weight_update == "cumulative" or iteration % self.config.segment_length == 0:
                self._update_weights()
            if (self.config.pair_selection_mode == "coupled"
                    and iteration % self.config.segment_length == 0):
                self._update_coupled_selection_preference()

            iteration_elapsed = perf_counter() - iteration_started
            measured_stage_seconds = destroy_seconds + partial_evaluation_seconds + repair_seconds + local_search_seconds
            other_iteration_seconds = max(0.0, iteration_elapsed - measured_stage_seconds)

            history.append(
                {
                    "iteration": iteration,
                    "phase": phase,
                    "destroy": destroy_name,
                    "repair": repair_name,
                    "accepted": accepted,
                    "accept_reason": reason,
                    "current_makespan": current_eval.makespan,
                    "best_makespan": best_eval.makespan,
                    "temperature": temperature,
                    "elapsed_seconds": perf_counter() - started_at,
                    "route_dp_calls": self.route_dp.statistics()["calls"] + self.generated_route_dp_calls - calls_start,
                    "route_dp_cache_misses": self.route_dp.statistics()["cache_misses"] + self.generated_route_dp_cache_misses - misses_start,
                    "candidate_makespan": refined_eval.makespan,
                    "candidate_delta": refined_eval.makespan - previous_eval.makespan,
                    "fallback_used": fallback_used,
                    "fallback_reason": fallback_reason,
                    "llm_operator_success": generated_selected and not fallback_used,
                    "attribution_ambiguous": attribution_ambiguous,
                    "reward_attribution": reward_attribution,
                    "selection_action": self._last_selection_action,
                    "actively_selected_frozen_pair": coupled_pair_selected,
                    "independent_selection_coincidental_frozen_pair": (
                        self._last_selection_action == "independent"
                        and selected_configured_pair
                    ),
                    "coupled_pair_fallback": coupled_pair_fallback,
                    "stage_timings_seconds": {
                        "destroy_execution": destroy_seconds,
                        "partial_evaluation": partial_evaluation_seconds,
                        "repair_execution": repair_seconds,
                        "local_search": local_search_seconds,
                        "other": other_iteration_seconds,
                    },
                    "coupled_selection_probability": selection_probability,
                    "coupled_selection_preference": self.coupled_selection_preference,
                }
            )

            recent_best.append(best_eval.makespan)
            if len(recent_best) > 20:
                recent_best = recent_best[-20:]
            temperature = max(1e-4, temperature * self.config.cooling_rate)

        return ALNSResult(
            best_solution=best_solution,
            best_evaluation=best_eval,
            iteration_history=history,
            operator_usage_stats=self.operator_stats,
            fallback_events=list(self.fallback_events),
            runtime_seconds=perf_counter() - started_at,
            iterations_completed=iteration,
            route_dp_calls=self.route_dp.statistics()["calls"] + self.generated_route_dp_calls - calls_start,
            route_dp_cache_misses=self.route_dp.statistics()["cache_misses"] + self.generated_route_dp_cache_misses - misses_start,
            termination_reason=termination_reason,
            initial_temperature=initial_temperature,
            initial_makespan=initial_makespan,
            pair_action_stats=dict(self.pair_action_stats),
            timing_breakdown_seconds={
                **phase_seconds,
                "initial_full_evaluation_seconds": initial_full_evaluation_seconds,
                "local_search_full_evaluation_seconds": self._full_evaluation_time["local_search"],
                "full_evaluation_seconds": sum(self._full_evaluation_time.values()),
                "other_seconds": max(
                    0.0,
                    perf_counter() - started_at - initial_full_evaluation_seconds - sum(phase_seconds.values()),
                ),
            },
            generated_operator_execution=self.generated_operator_execution,
        )

    def _initial_temperature(self, makespan: float) -> float:
        if self.config.initial_temperature is not None:
            return self.config.initial_temperature
        # A 1% worsening has probability p at the start; no extra DP evaluations.
        return max(1e-9, -self.config.initial_worsening_fraction * makespan /
                   math.log(self.config.initial_acceptance_probability))

    def _progress_temperature(self, initial: float, elapsed: float, completed: int) -> float:
        progress = (elapsed / self.config.max_runtime_seconds
                    if self.config.max_runtime_seconds is not None
                    else completed / max(1, self.config.iterations or 1))
        return initial * self.config.final_temperature_ratio ** min(1.0, max(0.0, progress))

    def _register_frozen_operators(self) -> None:
        registry_path = self.config.frozen_operator_registry_path
        if not registry_path:
            return

        path = Path(registry_path)
        if not path.exists():
            return

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            self._record_fallback(
                "repair",
                "__registry__",
                "registry_validation",
                f"registry read failed: {type(exc).__name__}: {exc}",
            )
            return
        if not isinstance(payload, dict):
            self._record_fallback(
                "repair",
                "__registry__",
                "registry_validation",
                "registry top level must be an object",
            )
            return

        if self.config.use_frozen_repair:
            repair_rows = payload.get("repair", [])
            if not isinstance(repair_rows, list):
                self._record_fallback(
                    "repair", "__registry__", "registry_validation",
                    "registry repair field must be a list",
                )
                repair_rows = []
            for row in repair_rows:
                if not self._is_well_formed_registry_row(row):
                    self._record_fallback(
                        "repair", "__registry__", "registry_validation",
                        "malformed repair registry row",
                    )
                    continue
                name = row["name"]
                fn = self._load_external_function(
                    Path(row["file_path"]),
                    "repair",
                    name,
                    row,
                )
                if fn is not None:
                    self.repair_ops[name] = self._wrap_external_repair(fn, name)
                    self.frozen_repair_ops.add(name)

        if self.config.use_frozen_destroy:
            destroy_rows = payload.get("destroy", [])
            if not isinstance(destroy_rows, list):
                self._record_fallback(
                    "destroy", "__registry__", "registry_validation",
                    "registry destroy field must be a list",
                )
                destroy_rows = []
            for row in destroy_rows:
                if not self._is_well_formed_registry_row(row):
                    self._record_fallback(
                        "destroy", "__registry__", "registry_validation",
                        "malformed destroy registry row",
                    )
                    continue
                name = row["name"]
                fn = self._load_external_function(
                    Path(row["file_path"]),
                    "destroy",
                    name,
                    row,
                )
                if fn is not None:
                    self.destroy_ops[name] = self._wrap_external_destroy(fn, name)
                    self.frozen_destroy_ops.add(name)

    @staticmethod
    def _is_well_formed_registry_row(row) -> bool:
        return (
            isinstance(row, dict)
            and isinstance(row.get("name"), str)
            and bool(row.get("name"))
            and isinstance(row.get("file_path"), str)
            and bool(row.get("file_path"))
        )

    def _load_external_function(
        self,
        file_path: Path,
        operator_type: str,
        operator_name: str,
        metadata: dict,
    ):
        if not file_path.exists():
            self._record_fallback(
                operator_type, operator_name, "import", "file_not_found"
            )
            return None

        metadata_valid, metadata_reason, timeout_ms = validate_registry_metadata(
            metadata
        )
        if not metadata_valid:
            self._record_fallback(
                operator_type,
                operator_name,
                "registry_validation",
                metadata_reason,
            )
            return None

        deployment_allowed, failure_type, authorization_reason = (
            validate_frozen_deployment_authorization(
                metadata,
                allow_real_provider_frozen_deployment=(
                    self.config.allow_real_provider_frozen_deployment
                ),
                explicit_runtime_risk_ack=self.config.explicit_runtime_risk_ack,
                allow_generated_frozen_deployment=(
                    self.config.allow_generated_frozen_deployment
                ),
                explicit_runtime_deployment_ack=(
                    self.config.explicit_runtime_deployment_ack
                ),
                runtime_authorization_source=(
                    self.config.runtime_authorization_source
                ),
                effective_sandbox_level=TRUSTED_EXECUTOR_SANDBOX_LEVEL,
                executor_identity=TRUSTED_EXECUTOR_IDENTITY,
            )
        )
        if not deployment_allowed:
            self._record_fallback(
                operator_type,
                operator_name,
                "runtime_authorization",
                authorization_reason,
                execution_status=failure_type,
                failure_type=failure_type,
            )
            return None

        try:
            source_text = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            self._record_fallback(
                operator_type,
                operator_name,
                "source_read",
                f"{type(exc).__name__}: {exc}",
                execution_status="source_read_failed",
            )
            return None

        if code_sha256(source_text) != metadata["code_hash"]:
            self._record_fallback(
                operator_type, operator_name, "import", "hash_mismatch"
            )
            return None

        try:
            validate_candidate_source(source_text, operator_type)
        except Exception as exc:  # noqa: BLE001 - generated source validation.
            self._record_fallback(
                operator_type,
                operator_name,
                "security_validation",
                str(exc),
                execution_status="validation_failed",
            )
            return None

        return CandidateProxy(
            path=file_path,
            operator_type=operator_type,
            expected_code_hash=metadata["code_hash"],
            timeout_ms=timeout_ms,
        )

    def _record_fallback(
        self,
        operator_type: str,
        operator_name: str,
        stage: str,
        reason: str,
        *,
        execution_status: str | None = None,
        failure_type: str | None = None,
        outcome: CandidateExecutionResult | None = None,
    ) -> None:
        event = {
            "operator_type": operator_type,
            "operator_name": operator_name,
            "stage": stage,
            "reason": reason,
            "fallback_used": True,
            "fallback_reason": reason,
        }
        if execution_status is not None:
            event["execution_status"] = execution_status
        if failure_type is not None:
            event["failure_type"] = failure_type
        if outcome is not None:
            event.update(
                {
                    "runtime_ms": outcome.runtime_ms,
                    "wall_time_ms": outcome.wall_time_ms,
                    "exit_code": outcome.exit_code,
                    "stdout": outcome.stdout,
                    "stderr": outcome.stderr,
                    "stdout_truncated": outcome.stdout_truncated,
                    "stderr_truncated": outcome.stderr_truncated,
                    "sandbox_level": outcome.sandbox_level,
                    "effective_sandbox_level": outcome.effective_sandbox_level,
                    "executor_identity": outcome.executor_identity,
                }
            )
        self.fallback_events.append(event)

    def _execute_external(self, external_fn, args: tuple) -> CandidateExecutionResult:
        if isinstance(external_fn, CandidateProxy):
            outcome = external_fn.execute(args, timeout_ms=external_fn.timeout_ms)
            stats = self.generated_operator_execution[external_fn.operator_type]
            row = stats.setdefault(external_fn.path.stem, {
                "calls": 0,
                "successes": 0,
                "failures": 0,
                "wall_time_seconds": 0.0,
                "run_request_seconds": 0.0,
                "route_dp_calls": 0,
                "route_dp_cache_misses": 0,
            })
            row["calls"] += 1
            row["successes"] += int(outcome.status == "success")
            row["failures"] += int(outcome.status != "success")
            row["wall_time_seconds"] += outcome.wall_time_ms / 1000.0
            row["run_request_seconds"] += outcome.runtime_ms / 1000.0
            row["route_dp_calls"] += outcome.route_dp_calls
            row["route_dp_cache_misses"] += outcome.route_dp_cache_misses
            return outcome
        try:
            result = external_fn(*args)
            return CandidateExecutionResult(status="success", runtime_ms=0.0, result=result)
        except Exception as exc:  # noqa: BLE001 - trusted compatibility path.
            return CandidateExecutionResult(
                status="runtime_error",
                runtime_ms=0.0,
                error_message=f"{type(exc).__name__}: {exc}",
            )

    def _record_execution_fallback(
        self,
        operator_type: str,
        operator_name: str,
        outcome: CandidateExecutionResult,
    ) -> None:
        self._record_fallback(
            operator_type,
            operator_name,
            "runtime",
            outcome.error_message or f"candidate {outcome.status}",
            execution_status=outcome.status,
            outcome=outcome,
        )

    def _wrap_external_repair(self, external_fn, operator_name: str):
        def _wrapped(
            partial_solution: MultiRobotSolution,
            removed_tasks: List[int],
            partial_eval: SolutionEvaluation,
        ) -> MultiRobotSolution:
            bottleneck = 0
            if partial_eval.per_robot_costs:
                bottleneck = int(max(range(len(partial_eval.per_robot_costs)), key=partial_eval.per_robot_costs.__getitem__))
            context = RepairContext(
                instance=self.instance,
                per_robot_costs=list(partial_eval.per_robot_costs),
                route_costs_makespan=partial_eval.makespan,
                bottleneck_route_id=bottleneck,
            )
            outcome = self._execute_external(
                external_fn,
                (
                    MultiRobotSolution(routes=[list(route) for route in partial_solution.routes]),
                    list(removed_tasks),
                    context,
                    self.rng,
                ),
            )
            if outcome.status != "success":
                self._record_execution_fallback("repair", operator_name, outcome)
                return self._greedy_insertion(partial_solution, removed_tasks, partial_eval)

            self.generated_route_dp_calls += outcome.route_dp_calls
            self.generated_route_dp_cache_misses += outcome.route_dp_cache_misses

            try:
                repaired = outcome.result.solution
            except Exception as exc:  # noqa: BLE001 - generated return contract.
                contract_error = CandidateExecutionResult(
                    status="runtime_error",
                    runtime_ms=outcome.runtime_ms,
                    error_message=f"invalid repair result: {exc}",
                    wall_time_ms=outcome.wall_time_ms,
                    exit_code=outcome.exit_code,
                )
                self._record_execution_fallback("repair", operator_name, contract_error)
                return self._greedy_insertion(partial_solution, removed_tasks, partial_eval)

            if not self._is_valid_full_solution(repaired):
                self._record_fallback(
                    "repair",
                    operator_name,
                    "contract_validation",
                    "repair returned an invalid or incomplete solution",
                    execution_status="invalid_solution",
                    outcome=outcome,
                )
                return self._greedy_insertion(partial_solution, removed_tasks, partial_eval)
            return repaired

        return _wrapped

    def _wrap_external_destroy(self, external_fn, operator_name: str):
        def _wrapped(
            solution: MultiRobotSolution,
            evaluation: SolutionEvaluation,
            remove_count: int,
        ) -> tuple[MultiRobotSolution, List[int]]:
            context = DestroyContext(
                instance=self.instance,
                per_robot_costs=list(evaluation.per_robot_costs),
                route_costs_makespan=evaluation.makespan,
                remove_count=remove_count,
            )
            outcome = self._execute_external(
                external_fn,
                (
                    MultiRobotSolution(routes=[list(route) for route in solution.routes]),
                    context,
                    self.rng,
                ),
            )
            if outcome.status != "success":
                self._record_execution_fallback("destroy", operator_name, outcome)
                return self._random_destroy(solution, evaluation, remove_count)

            try:
                partial_solution = outcome.result.partial_solution
                removed_tasks = list(outcome.result.removed_tasks)
            except Exception as exc:  # noqa: BLE001 - generated return contract.
                contract_error = CandidateExecutionResult(
                    status="runtime_error",
                    runtime_ms=outcome.runtime_ms,
                    error_message=f"invalid destroy result: {exc}",
                    wall_time_ms=outcome.wall_time_ms,
                    exit_code=outcome.exit_code,
                )
                self._record_execution_fallback("destroy", operator_name, contract_error)
                return self._random_destroy(solution, evaluation, remove_count)

            if len(removed_tasks) != min(remove_count, self.instance.task_count) or not self._is_valid_destroy_partition(
                solution, partial_solution, removed_tasks
            ):
                self._record_fallback(
                    "destroy",
                    operator_name,
                    "contract_validation",
                    "destroy returned an inconsistent task partition",
                    execution_status="invalid_solution",
                    outcome=outcome,
                )
                return self._random_destroy(solution, evaluation, remove_count)
            return partial_solution, removed_tasks

        return _wrapped

    def _is_valid_full_solution(self, solution: MultiRobotSolution) -> bool:
        if not self._has_valid_route_shape(solution, self.instance.robot_count):
            return False
        try:
            return is_solution_complete(solution, self.instance)
        except (TypeError, ValueError, AttributeError):
            return False

    @staticmethod
    def _has_valid_route_shape(solution, expected_route_count: int) -> bool:
        return (
            isinstance(solution, MultiRobotSolution)
            and isinstance(solution.routes, list)
            and len(solution.routes) == expected_route_count
            and all(
                isinstance(route, list)
                and all(type(task_id) is int for task_id in route)
                for route in solution.routes
            )
        )

    def _is_valid_destroy_partition(
        self,
        original: MultiRobotSolution,
        partial: MultiRobotSolution,
        removed_tasks: List[int],
    ) -> bool:
        if not self._has_valid_route_shape(original, len(original.routes)):
            return False
        if not self._has_valid_route_shape(partial, len(original.routes)):
            return False
        if not isinstance(removed_tasks, list) or not all(
            type(task_id) is int for task_id in removed_tasks
        ):
            return False
        original_tasks = [task for route in original.routes for task in route]
        remaining_tasks = [task for route in partial.routes for task in route]
        return (
            Counter(remaining_tasks) + Counter(removed_tasks)
            == Counter(original_tasks)
            and not (set(remaining_tasks) & set(removed_tasks))
            and len(removed_tasks) == len(set(removed_tasks))
        )

    def _build_context(
        self,
        best_eval: SolutionEvaluation,
        current_eval: SolutionEvaluation,
        recent_best: List[float],
    ) -> SearchContext:
        bottleneck_route_id = 0
        if current_eval.per_robot_costs:
            bottleneck_route_id = int(
                max(range(len(current_eval.per_robot_costs)), key=current_eval.per_robot_costs.__getitem__)
            )

        operator_summary = {
            group: {
                name: {"uses": stat.uses, "score": stat.score}
                for name, stat in stats.items()
            }
            for group, stats in self.operator_stats.items()
        }

        return SearchContext(
            best_makespan=best_eval.makespan,
            per_route_costs=list(current_eval.per_robot_costs),
            bottleneck_route_id=bottleneck_route_id,
            recent_improvement_history=list(recent_best),
            operator_performance=operator_summary,
        )

    def _select_operators(self, context: SearchContext) -> tuple[str, str, str]:
        phase = "default"
        if self.advisor is not None:
            suggestion = self.advisor.suggest_destroy_repair(context)
            intensify = suggestion.get("intensify", False)
            phase = "intensify" if intensify else "diversify"
            destroy_name = suggestion.get("destroy_operator")
            repair_name = suggestion.get("repair_operator")
            if destroy_name in self.destroy_ops and repair_name in self.repair_weights:
                self._last_selection_action = "advisor"
                return str(destroy_name), str(repair_name), phase

        if self.config.pair_selection_mode == "coupled":
            if self.rng.random() < self._coupled_selection_probability():
                self._last_selection_action = "coupled"
                return (
                    str(self.config.coupled_destroy_operator),
                    str(self.config.coupled_repair_operator),
                    phase,
                )
        self._last_selection_action = "independent"
        destroy_name = self._weighted_pick(self.destroy_weights)
        repair_name = self._weighted_pick(self.repair_weights)
        if (destroy_name == self.config.coupled_destroy_operator
                and repair_name == self.config.coupled_repair_operator):
            self.pair_action_stats["independent_coincidental_uses"] += 1
        return destroy_name, repair_name, phase

    def _coupled_selection_probability(self) -> float:
        """Use the configured pair's independent roulette chance as its prior."""
        destroy_name = self.config.coupled_destroy_operator
        repair_name = self.config.coupled_repair_operator
        if destroy_name not in self.destroy_weights or repair_name not in self.repair_weights:
            return 0.0
        destroy_total = sum(max(1e-6, value) for value in self.destroy_weights.values())
        repair_total = sum(max(1e-6, value) for value in self.repair_weights.values())
        baseline = (
            max(1e-6, self.destroy_weights[destroy_name]) / destroy_total
            * max(1e-6, self.repair_weights[repair_name]) / repair_total
        )
        odds = (baseline / max(1e-12, 1.0 - baseline)) * self.coupled_selection_preference
        return min(0.5, max(1e-6, odds / (1.0 + odds)))

    def _update_coupled_selection_preference(self) -> None:
        """React to relative mean action reward while keeping the roulette prior."""
        pair = self.pair_selection_segment["coupled"]
        independent = self.pair_selection_segment["independent"]
        if pair.uses and independent.uses:
            pair_mean = max(0.1, pair.score / pair.uses)
            independent_mean = max(0.1, independent.score / independent.uses)
            self.coupled_selection_preference *= (
                pair_mean / independent_mean
            ) ** self.config.reaction_factor
            self.coupled_selection_preference = min(
                20.0, max(0.05, self.coupled_selection_preference)
            )
        pair.uses = pair.score = 0.0
        independent.uses = independent.score = 0.0

    def _weighted_pick(self, weights: Dict[str, float]) -> str:
        names = list(weights.keys())
        values = [max(1e-6, weights[name]) for name in names]
        chosen = self.rng.choices(names, weights=values, k=1)[0]
        return chosen

    def _accept(
        self,
        current_eval: SolutionEvaluation,
        candidate_eval: SolutionEvaluation,
        temperature: float,
    ) -> tuple[bool, str]:
        delta = candidate_eval.makespan - current_eval.makespan
        if delta <= 1e-9:
            return True, "improvement"

        if self.config.acceptance == "simulated_annealing":
            prob = math.exp(-delta / max(1e-6, temperature))
            if self.rng.random() < prob:
                return True, "sa"
        return False, "reject"

    def _update_operator_stats(self, group: str, name: str, reward: float) -> None:
        rec = self.operator_stats[group][name]
        rec.uses += 1
        rec.score += reward
        segment = self.segment_stats[group][name]
        segment.uses += 1
        segment.score += reward

    def _update_weights(self) -> None:
        if self.config.weight_update == "segment":
            # React to the last segment, retaining (1-rho) of the prior weight.
            # Unused operators retain their weight; a small floor keeps exploration.
            rho = self.config.reaction_factor
            for group, weights in (("destroy", self.destroy_weights), ("repair", self.repair_weights)):
                for name, rec in self.segment_stats[group].items():
                    if rec.uses:
                        weights[name] = max(0.1, (1 - rho) * weights[name] + rho * rec.score / rec.uses)
                    rec.uses = 0
                    rec.score = 0.0
            return
        for name, rec in self.operator_stats["destroy"].items():
            self.destroy_weights[name] = 1.0 + rec.score / max(1, rec.uses)
        for name in self.repair_weights:
            rec = self.operator_stats["repair"][name]
            self.repair_weights[name] = 1.0 + rec.score / max(1, rec.uses)

    def _task_map(self) -> Dict[int, object]:
        return {task.task_id: task for task in self.instance.tasks}

    def _remove_tasks(
        self,
        solution: MultiRobotSolution,
        tasks_to_remove: Sequence[int],
    ) -> tuple[MultiRobotSolution, List[int]]:
        remove_set = set(tasks_to_remove)
        new_routes: List[List[int]] = []
        removed: List[int] = []
        for route in solution.routes:
            kept = []
            for task_id in route:
                if task_id in remove_set:
                    removed.append(task_id)
                else:
                    kept.append(task_id)
            new_routes.append(kept)
        return MultiRobotSolution(routes=new_routes), removed

    def _random_destroy(
        self,
        solution: MultiRobotSolution,
        evaluation: SolutionEvaluation,
        remove_count: int,
    ) -> tuple[MultiRobotSolution, List[int]]:
        all_tasks = [task_id for route in solution.routes for task_id in route]
        sample = self.rng.sample(all_tasks, min(remove_count, len(all_tasks))) if all_tasks else []
        return self._remove_tasks(solution, sample)

    def _bottleneck_route_destroy(
        self,
        solution: MultiRobotSolution,
        evaluation: SolutionEvaluation,
        remove_count: int,
    ) -> tuple[MultiRobotSolution, List[int]]:
        if not evaluation.per_robot_costs:
            return self._random_destroy(solution, evaluation, remove_count)
        bottleneck = int(max(range(len(evaluation.per_robot_costs)), key=evaluation.per_robot_costs.__getitem__))
        route = solution.routes[bottleneck]
        if not route:
            return self._random_destroy(solution, evaluation, remove_count)
        ordered = list(route)
        self.rng.shuffle(ordered)
        return self._remove_tasks(solution, ordered[:remove_count])

    def _geometry_aware_destroy(
        self,
        solution: MultiRobotSolution,
        evaluation: SolutionEvaluation,
        remove_count: int,
    ) -> tuple[MultiRobotSolution, List[int]]:
        """Problem-specific destroy using rectangle aspect and sweep asymmetry."""

        task_lookup = self._task_map()
        mode_spread: Dict[int, float] = {}
        for task_id, states in self.states_by_task.items():
            proc = [state.processing_time for state in states]
            mode_spread[task_id] = max(proc) - min(proc)

        scored: List[tuple[float, int]] = []
        for route_idx, route in enumerate(solution.routes):
            route_weight = 1.0
            if evaluation.per_robot_costs and route_idx == int(
                max(range(len(evaluation.per_robot_costs)), key=evaluation.per_robot_costs.__getitem__)
            ):
                route_weight = 1.5
            for task_id in route:
                task = task_lookup[task_id]
                aspect = max(task.width / task.height, task.height / task.width)
                score = route_weight * (aspect + 0.1 * mode_spread.get(task_id, 0.0))
                scored.append((score, task_id))

        scored.sort(reverse=True)
        chosen = [task_id for _, task_id in scored[:remove_count]]
        if not chosen:
            return self._random_destroy(solution, evaluation, remove_count)
        return self._remove_tasks(solution, chosen)

    def _best_insertion_for_task(
        self,
        solution: MultiRobotSolution,
        base_costs: List[float],
        task_id: int,
        *,
        objective: str,
    ) -> tuple[int, int, float]:
        best_robot = 0
        best_index = 0
        best_score = float("inf")

        for robot_idx, route in enumerate(solution.routes):
            others_max = max((cost for idx, cost in enumerate(base_costs) if idx != robot_idx), default=0.0)
            for insert_idx in range(len(route) + 1):
                candidate_route = list(route)
                candidate_route.insert(insert_idx, task_id)
                route_eval = self.route_dp.evaluate_route(candidate_route)
                new_makespan = max(others_max, route_eval.total_cost)

                if objective == "balance":
                    projected = list(base_costs)
                    projected[robot_idx] = route_eval.total_cost
                    avg = sum(projected) / len(projected) if projected else 0.0
                    balance_penalty = sum(abs(v - avg) for v in projected) / max(1, len(projected))
                    score = new_makespan + 0.1 * balance_penalty
                else:
                    score = new_makespan

                if score < best_score - 1e-9:
                    best_robot = robot_idx
                    best_index = insert_idx
                    best_score = score

        return best_robot, best_index, best_score

    def _greedy_insertion(
        self,
        partial_solution: MultiRobotSolution,
        removed_tasks: List[int],
        partial_eval: SolutionEvaluation,
    ) -> MultiRobotSolution:
        routes = [list(route) for route in partial_solution.routes]
        base_costs = list(partial_eval.per_robot_costs)
        for task_id in removed_tasks:
            robot, insert_idx, _ = self._best_insertion_for_task(
                MultiRobotSolution(routes=routes),
                base_costs,
                task_id,
                objective="makespan",
            )
            routes[robot].insert(insert_idx, task_id)
            base_costs[robot] = self.route_dp.evaluate_route(routes[robot]).total_cost
        return MultiRobotSolution(routes=routes)

    def _regret_k_insertion(
        self,
        partial_solution: MultiRobotSolution,
        removed_tasks: List[int],
        partial_eval: SolutionEvaluation,
    ) -> MultiRobotSolution:
        routes = [list(route) for route in partial_solution.routes]
        base_costs = list(partial_eval.per_robot_costs)
        remaining = list(removed_tasks)

        while remaining:
            best_task = remaining[0]
            best_choice = (0, 0, float("inf"))
            best_regret = -float("inf")

            for task_id in remaining:
                choices: List[tuple[int, int, float]] = []
                for robot_idx, route in enumerate(routes):
                    others_max = max((cost for idx, cost in enumerate(base_costs) if idx != robot_idx), default=0.0)
                    for insert_idx in range(len(route) + 1):
                        candidate_route = list(route)
                        candidate_route.insert(insert_idx, task_id)
                        route_eval = self.route_dp.evaluate_route(candidate_route)
                        score = max(others_max, route_eval.total_cost)
                        choices.append((robot_idx, insert_idx, score))
                choices.sort(key=lambda x: x[2])
                best = choices[0]
                second = choices[1] if len(choices) > 1 else choices[0]
                regret = second[2] - best[2]
                if regret > best_regret:
                    best_regret = regret
                    best_task = task_id
                    best_choice = best

            robot, insert_idx, _ = best_choice
            routes[robot].insert(insert_idx, best_task)
            base_costs[robot] = self.route_dp.evaluate_route(routes[robot]).total_cost
            remaining.remove(best_task)

        return MultiRobotSolution(routes=routes)

    def _bottleneck_balancing_insertion(
        self,
        partial_solution: MultiRobotSolution,
        removed_tasks: List[int],
        partial_eval: SolutionEvaluation,
    ) -> MultiRobotSolution:
        routes = [list(route) for route in partial_solution.routes]
        base_costs = list(partial_eval.per_robot_costs)
        for task_id in removed_tasks:
            robot, insert_idx, _ = self._best_insertion_for_task(
                MultiRobotSolution(routes=routes),
                base_costs,
                task_id,
                objective="balance",
            )
            routes[robot].insert(insert_idx, task_id)
            base_costs[robot] = self.route_dp.evaluate_route(routes[robot]).total_cost
        return MultiRobotSolution(routes=routes)

    def _dp_aware_insertion(
        self,
        partial_solution: MultiRobotSolution,
        removed_tasks: List[int],
        partial_eval: SolutionEvaluation,
    ) -> MultiRobotSolution:
        """Compatibility alias; greedy insertion already uses exact Route DP."""

        return self._greedy_insertion(partial_solution, removed_tasks, partial_eval)


def solve_with_alns(
    instance: Instance,
    *,
    constructor: str = "spatial_sort",
    config: ALNSConfig | None = None,
    advisor: Advisor | None = None,
) -> ALNSResult:
    solver = ALNSSolver(instance, constructor=constructor, config=config, advisor=advisor)
    return solver.solve()
