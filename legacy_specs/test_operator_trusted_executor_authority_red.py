from __future__ import annotations

from dataclasses import fields
import hashlib
import json
from pathlib import Path

import pytest

from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.heuristics.alns_solver import ALNSConfig, ALNSSolver
from mrta_rect_coverage.llm.operator_evolution import candidate_loader as loader_module
from mrta_rect_coverage.llm.operator_evolution import evolution_loop as loop_module
from mrta_rect_coverage.llm.operator_evolution.candidate_execution import (
    CandidateExecutionResult,
    execute_candidate_process,
)
from mrta_rect_coverage.llm.operator_evolution.candidate_loader import (
    LoadedOperator,
    load_and_validate_candidate,
)
from mrta_rect_coverage.llm.operator_evolution.eligibility_policy import (
    build_generated_artifact_metadata,
    candidate_is_execution_eligible,
    candidate_is_freeze_eligible,
    candidate_is_selection_eligible,
)
from mrta_rect_coverage.llm.operator_evolution.evolution_loop import (
    EvolutionLoopConfig,
    _can_enter_benchmark,
    run_evolution_loop,
)
from mrta_rect_coverage.llm.operator_evolution.feedback_builder import (
    build_feedback_payload,
)
from mrta_rect_coverage.llm.operator_evolution.freezing import freeze_best_operators
from mrta_rect_coverage.llm.operator_evolution.schemas import (
    GeneratedOperatorDraft,
    OperatorValidationResult,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INSTANCE_PATH = PROJECT_ROOT / "data" / "R2_T6_0.txt"
REAL_PROVIDER = "langchain_openai_compatible"
BLOCKED_FAILURE_TYPES = {
    "untrusted_sandbox_claim",
    "execution_blocked",
    "risk_ack_required",
}

VALID_REPAIR_CODE = '''\
from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import RepairResult

def repair(partial_solution, unassigned_tasks, context, rng):
    routes = [list(route) for route in partial_solution.routes]
    for task_id in unassigned_tasks:
        routes[0].append(task_id)
    return RepairResult(solution=MultiRobotSolution(routes=routes))
'''


class _StaticRealProvider:
    def generate_operator_candidates(self, prompt, n, operator_type, round_id):
        return [
            GeneratedOperatorDraft(
                operator_id="blocked_real_candidate",
                operator_type=operator_type,
                round_id=round_id,
                name="blocked_real_candidate",
                description="static real-provider provenance",
                source=REAL_PROVIDER,
                code=VALID_REPAIR_CODE,
                module_filename="blocked_real_candidate.py",
            )
        ]

    def revise_operator_candidates(
        self, prompt, previous_results, n, operator_type, round_id
    ):
        return self.generate_operator_candidates(
            prompt, n, operator_type, round_id
        )


class _MixedStaticProvider:
    def generate_operator_candidates(self, prompt, n, operator_type, round_id):
        return [
            GeneratedOperatorDraft(
                operator_id="eligible_mock_candidate",
                operator_type=operator_type,
                round_id=round_id,
                name="eligible_mock_candidate",
                description="eligible feedback candidate",
                source="mock",
                code=VALID_REPAIR_CODE,
                module_filename="eligible_mock_candidate.py",
            ),
            GeneratedOperatorDraft(
                operator_id="blocked_real_candidate",
                operator_type=operator_type,
                round_id=round_id,
                name="blocked_real_candidate",
                description="must remain outside leaderboard feedback",
                source=REAL_PROVIDER,
                code=VALID_REPAIR_CODE,
                module_filename="blocked_real_candidate.py",
            ),
        ]

    def revise_operator_candidates(
        self, prompt, previous_results, n, operator_type, round_id
    ):
        return self.generate_operator_candidates(
            prompt, n, operator_type, round_id
        )


def _code_hash(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _validation_with_claimed_capability() -> OperatorValidationResult:
    validation = OperatorValidationResult(
        operator_id="claimed_capability",
        operator_type="repair",
        round_id=0,
        name="claimed_capability",
        description="artifact claim must not grant authority",
        source=REAL_PROVIDER,
        file_path="candidate.py",
        validation_status="valid",
        execution_status="success",
        failure_type="success",
        sandbox_level="capability_sandbox",
        safe_to_execute=True,
        requires_human_risk_ack=False,
        code_hash="abc123",
    )
    # Candidate-owned fields must not override trusted runtime authority.
    validation.effective_sandbox_level = "timeout_only"
    validation.executor_identity = "timeout_only_subprocess_v1"
    return validation


def _complete_candidate_row() -> dict:
    return {
        "operator_id": "complete_candidate",
        "operator_type": "repair",
        "round_id": 0,
        "validation_status": "valid",
        "execution_status": "success",
        "failure_type": "success",
        "safe_to_execute": True,
        "requires_human_risk_ack": False,
        "sandbox_level": "timeout_only",
        "effective_sandbox_level": "timeout_only",
        "executor_identity": "timeout_only_subprocess_v1",
        **build_generated_artifact_metadata(
            claimed_source_provider="mock", round_id=0, code_hash="abc123"
        ),
        "fallback_used": False,
        "error_rate": 0.0,
        "timeout_rate": 0.0,
        "invalid_solution_rate": 0.0,
        "validation_failed_rate": 0.0,
        "execution_blocked_rate": 0.0,
        "timeout_ms": 100.0,
        "code_hash": "abc123",
        "avg_relative_improvement": 0.1,
        "success_rate": 1.0,
    }


def _complete_registry_row(path: Path) -> dict:
    row = _complete_candidate_row()
    row.update(
        {
            "name": path.stem,
            "file_path": str(path),
            "code_hash": _code_hash(path.read_text(encoding="utf-8")),
        }
    )
    return row


def _write_registry(tmp_path: Path, row: dict) -> Path:
    registry = tmp_path / "operator_registry.json"
    registry.write_text(
        json.dumps({"repair": [row], "destroy": []}),
        encoding="utf-8",
    )
    return registry


def _make_solver(registry: Path) -> ALNSSolver:
    return ALNSSolver(
        load_instance(INSTANCE_PATH),
        config=ALNSConfig(
            iterations=0,
            frozen_operator_registry_path=str(registry),
            use_frozen_repair=True,
            allow_generated_frozen_deployment=True,
            explicit_runtime_deployment_ack=True,
            runtime_authorization_source="current_runtime_config",
        ),
    )


def _evolution_config(
    tmp_path: Path,
    *,
    operator_types=("repair",),
    provider_name="mock",
    allow_unsafe=False,
) -> EvolutionLoopConfig:
    return EvolutionLoopConfig(
        project_root=PROJECT_ROOT,
        generated_dir=tmp_path / "generated",
        output_dir=tmp_path / "outputs",
        round_count=1,
        repair_candidates_per_round=2,
        destroy_candidates_per_round=0,
        benchmark_instance_glob="data/R2_T6_0.txt",
        seeds=(0,),
        top_k_to_keep=2,
        operator_types_to_evolve=operator_types,
        provider_name=provider_name,
        allow_unsafe_candidate_execution=allow_unsafe,
    )


def test_real_provider_capability_claim_does_not_grant_execution() -> None:
    validation = _validation_with_claimed_capability()

    assert candidate_is_execution_eligible(validation, lambda: None, False) is False


def test_real_provider_capability_claim_does_not_grant_benchmark() -> None:
    loaded = LoadedOperator(
        validation=_validation_with_claimed_capability(),
        callable_obj=lambda: None,
    )

    assert _can_enter_benchmark(loaded, False) is False


@pytest.mark.parametrize("gate", ["selection", "freezing"])
def test_real_provider_capability_claim_does_not_pass_artifact_gates(
    gate: str,
) -> None:
    row = _complete_candidate_row()
    row.update(
        {
            "source_provider": REAL_PROVIDER,
            "sandbox_level": "capability_sandbox",
            "effective_sandbox_level": "timeout_only",
        }
    )

    eligible = (
        candidate_is_selection_eligible(row)
        if gate == "selection"
        else candidate_is_freeze_eligible(row)
    )
    assert eligible is False


def test_separate_claimed_sandbox_field_cannot_hide_capability_claim() -> None:
    row = _complete_candidate_row()
    row["sandbox_level"] = "timeout_only"
    row["claimed_sandbox_level"] = "capability_sandbox"

    assert candidate_is_selection_eligible(row) is False
    assert candidate_is_freeze_eligible(row) is False


def test_capability_claimed_best_operator_is_not_frozen(tmp_path: Path) -> None:
    operator_id = "claimed_capability"
    generated_root = tmp_path / "generated"
    source_dir = generated_root / "round_000"
    source_dir.mkdir(parents=True)
    (source_dir / f"{operator_id}.py").write_text(
        VALID_REPAIR_CODE, encoding="utf-8"
    )
    row = _complete_candidate_row()
    row.update(
        {
            "operator_id": operator_id,
            "source_provider": REAL_PROVIDER,
            "sandbox_level": "capability_sandbox",
            "effective_sandbox_level": "timeout_only",
            "code_hash": _code_hash(VALID_REPAIR_CODE),
        }
    )
    best_path = tmp_path / "best_operators.json"
    best_path.write_text(
        json.dumps({"repair": row, "destroy": {}}), encoding="utf-8"
    )

    result = freeze_best_operators(
        project_root=PROJECT_ROOT,
        best_operators_json=best_path,
        generated_root=generated_root,
        target_dir=tmp_path / "frozen",
        registry_path=tmp_path / "frozen" / "registry.json",
    )

    assert result.copied_files == []
    registry = json.loads(Path(result.registry_path).read_text(encoding="utf-8"))
    assert registry["repair"] == []


def test_frozen_registry_rejects_untrusted_capability_claim(
    tmp_path: Path,
) -> None:
    operator_path = tmp_path / "claimed_capability.py"
    operator_path.write_text(VALID_REPAIR_CODE, encoding="utf-8")
    row = _complete_registry_row(operator_path)
    row.update(
        {
            "source_provider": REAL_PROVIDER,
            "sandbox_level": "capability_sandbox",
            "effective_sandbox_level": "timeout_only",
            "executor_identity": "forged_capability_executor",
        }
    )

    solver = _make_solver(_write_registry(tmp_path, row))

    assert operator_path.stem not in solver.frozen_repair_ops
    assert solver.fallback_events
    event = solver.fallback_events[-1]
    assert event["stage"] == "registry_validation"
    assert event["fallback_used"] is True
    assert any(
        token in event["fallback_reason"].lower()
        for token in ("sandbox", "executor", "untrusted")
    )


def test_execution_result_exposes_trusted_runtime_authority() -> None:
    field_names = {field.name for field in fields(CandidateExecutionResult)}

    assert "effective_sandbox_level" in field_names
    assert "executor_identity" in field_names
    outcome = CandidateExecutionResult(status="success", runtime_ms=0.0)
    assert outcome.effective_sandbox_level == "timeout_only"
    assert outcome.executor_identity


def test_evolution_does_not_benchmark_capability_claimed_real_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    benchmark_counts: list[int] = []

    def _claimed_capability_loader(**kwargs):
        return LoadedOperator(
            validation=_validation_with_claimed_capability(),
            callable_obj=lambda *args: None,
        )

    def _capture_benchmark(candidates, cases, *, seeds, timeout_ms):
        benchmark_counts.append(len(candidates))
        return []

    monkeypatch.setattr(
        loop_module, "load_and_validate_candidate", _claimed_capability_loader
    )
    monkeypatch.setattr(
        loop_module, "evaluate_repair_candidates", _capture_benchmark
    )

    run_evolution_loop(
        _StaticRealProvider(),
        _evolution_config(
            tmp_path,
            provider_name=REAL_PROVIDER,
            allow_unsafe=False,
        ),
    )

    assert benchmark_counts == [0]


@pytest.mark.parametrize(
    "missing_field",
    [
        "validation_failed_rate",
        "execution_blocked_rate",
        "timeout_ms",
        "fallback_used",
        "error_rate",
        "timeout_rate",
        "invalid_solution_rate",
    ],
)
def test_selection_and_freezing_require_complete_failure_evidence(
    missing_field: str,
) -> None:
    row = _complete_candidate_row()
    row.pop(missing_field)

    assert candidate_is_selection_eligible(row) is False
    assert candidate_is_freeze_eligible(row) is False


def test_direct_executor_revalidates_hashed_source_before_execution(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "dangerous_source_executed.txt"
    code = f'''\
def repair(partial_solution, unassigned_tasks, context, rng):
    with open({str(marker)!r}, "w", encoding="utf-8") as handle:
        handle.write("executed")
    return "dangerous source ran"
'''
    path = tmp_path / "correctly_hashed_but_dangerous.py"
    path.write_text(code, encoding="utf-8")

    outcome = execute_candidate_process(
        path=path,
        operator_type="repair",
        args=(None, [], None, None),
        timeout_ms=500.0,
        expected_code_hash=_code_hash(code),
    )

    assert outcome.status in {
        "validation_failed",
        "unsafe",
        "execution_blocked",
    }
    assert outcome.result is None
    assert marker.exists() is False


def test_candidate_loader_delegates_preexecution_decision_to_shared_policy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "loader_policy_candidate.py"
    path.write_text(VALID_REPAIR_CODE, encoding="utf-8")
    policy_calls: list[str] = []
    smoke_calls: list[str] = []

    def _deny_by_shared_policy(*args, **kwargs):
        policy_calls.append("called")
        return False

    def _unexpected_smoke(*args, **kwargs):
        smoke_calls.append("called")
        return CandidateExecutionResult(status="success", runtime_ms=0.0)

    monkeypatch.setattr(
        loader_module,
        "candidate_is_execution_eligible",
        _deny_by_shared_policy,
        raising=False,
    )
    monkeypatch.setattr(loader_module, "_smoke_test", _unexpected_smoke)

    loaded = load_and_validate_candidate(
        path=path,
        operator_type="repair",
        round_id=0,
        source=REAL_PROVIDER,
        description="shared policy must own preexecution decision",
        allow_unsafe_candidate_execution=True,
    )

    assert policy_calls == ["called"]
    assert smoke_calls == []
    assert loaded.callable_obj is None
    assert loaded.validation.failure_type in BLOCKED_FAILURE_TYPES


def test_operator_type_not_requested_is_reported_not_evolved(
    tmp_path: Path,
) -> None:
    artifacts = run_evolution_loop(
        _StaticRealProvider(),
        _evolution_config(
            tmp_path,
            operator_types=("repair",),
            provider_name=REAL_PROVIDER,
        ),
    )
    summary = json.loads(
        Path(artifacts.evolution_summary_path).read_text(encoding="utf-8")
    )

    assert summary["destroy_selection_status"] == "not_evolved"


def test_participating_type_without_eligible_candidate_is_no_valid_operator(
    tmp_path: Path,
) -> None:
    artifacts = run_evolution_loop(
        _StaticRealProvider(),
        _evolution_config(
            tmp_path,
            operator_types=("repair",),
            provider_name=REAL_PROVIDER,
        ),
    )
    summary = json.loads(
        Path(artifacts.evolution_summary_path).read_text(encoding="utf-8")
    )

    assert summary["repair_selection_status"] == "no_valid_operator"


def test_feedback_top_and_weak_pools_contain_only_eligible_candidates() -> None:
    eligible = _complete_candidate_row()
    eligible.update(
        {
            "operator_id": "eligible",
            "avg_relative_improvement": -0.5,
        }
    )
    blocked = _complete_candidate_row()
    blocked.update(
        {
            "operator_id": "blocked",
            "execution_status": "execution_blocked",
            "failure_type": "execution_blocked",
            "safe_to_execute": False,
            "avg_relative_improvement": 10.0,
        }
    )
    timeout = _complete_candidate_row()
    timeout.update(
        {
            "operator_id": "timeout",
            "execution_status": "timeout",
            "failure_type": "timeout",
            "timeout_rate": 1.0,
            "avg_relative_improvement": -10.0,
        }
    )
    fallback = _complete_candidate_row()
    fallback.update(
        {
            "operator_id": "fallback",
            "fallback_used": True,
            "avg_relative_improvement": 5.0,
        }
    )

    feedback = build_feedback_payload(
        [eligible, blocked, timeout, fallback], top_k=2
    )

    top_ids = {row["operator_id"] for row in feedback["top_operators"]}
    weak_ids = {row["operator_id"] for row in feedback["weak_operators"]}
    assert top_ids == {"eligible"}
    assert weak_ids == {"eligible"}


def test_round_leaderboard_excludes_ineligible_candidates(
    tmp_path: Path,
) -> None:
    artifacts = run_evolution_loop(
        _MixedStaticProvider(),
        _evolution_config(tmp_path, provider_name="mock"),
    )
    summary = json.loads(
        Path(artifacts.evolution_summary_path).read_text(encoding="utf-8")
    )
    leaderboard = summary["rounds"][0]["leaderboard"]

    assert leaderboard
    assert {row["operator_id"] for row in leaderboard} == {
        "eligible_mock_candidate"
    }
    assert all(candidate_is_selection_eligible(row) for row in leaderboard)


def test_formal_spec_assigns_sandbox_level_to_trusted_executor_policy() -> None:
    content = (
        PROJECT_ROOT / "docs" / "llm_operator_evolution_spec.md"
    ).read_text(encoding="utf-8").lower()

    assert "trusted executor" in content or "可信执行器" in content
    assert "artifact" in content or "registry" in content
    assert "self-declared" in content or "自声明" in content


def test_formal_spec_does_not_overstate_incomplete_evidence_gate() -> None:
    content = (
        PROJECT_ROOT / "docs" / "llm_operator_evolution_spec.md"
    ).read_text(encoding="utf-8")

    overstatement = (
        "selection、freezing 与 frozen registry deployment 要求完整 "
        "validation/execution/failure/safety/fallback/rate 证据，缺字段即拒绝"
    )
    assert overstatement not in content
