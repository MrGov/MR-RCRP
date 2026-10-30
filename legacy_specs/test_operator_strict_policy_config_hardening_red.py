from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.experiments.operator_evolution_runner import (
    _build_evolution_config,
    _load_yaml_config,
)
from mrta_rect_coverage.heuristics.alns_solver import ALNSConfig, ALNSSolver
from mrta_rect_coverage.llm.operator_evolution import candidate_loader as loader_module
from mrta_rect_coverage.llm.operator_evolution import evolution_loop as loop_module
from mrta_rect_coverage.llm.operator_evolution.candidate_execution import (
    CandidateExecutionResult,
    CandidateProxy,
    execute_candidate_process,
)
from mrta_rect_coverage.llm.operator_evolution.candidate_loader import (
    LoadedOperator,
    load_and_validate_candidate,
)
from mrta_rect_coverage.llm.operator_evolution.evolution_loop import (
    EvolutionLoopConfig,
    _can_enter_benchmark,
    _is_eligible,
    run_evolution_loop,
)
from mrta_rect_coverage.llm.operator_evolution.eligibility_policy import (
    build_generated_artifact_metadata,
)
from mrta_rect_coverage.llm.operator_evolution.freezing import _is_freezable
from mrta_rect_coverage.llm.operator_evolution.schemas import (
    GeneratedOperatorDraft,
    OperatorValidationResult,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INSTANCE_PATH = PROJECT_ROOT / "data" / "R2_T6_0.txt"
BLOCKED_STATUSES = {
    "config_invalid",
    "execution_blocked",
    "risk_ack_required",
}
MISSING_HASH_STATUSES = {
    "config_invalid",
    "execution_blocked",
    "source_hash_missing",
    "validation_failed",
    "unsafe",
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

NO_HASH_EXECUTION_CODE = '''\
def repair(partial_solution, unassigned_tasks, context, rng):
    return "EXECUTED_WITHOUT_EXPECTED_HASH"
'''


NON_BOOLEAN_UNSAFE_VALUES = [
    pytest.param("false", id="string-false"),
    pytest.param("true", id="string-true"),
    pytest.param("0", id="string-zero"),
    pytest.param("1", id="string-one"),
    pytest.param(0, id="integer-zero"),
    pytest.param(1, id="integer-one"),
    pytest.param(None, id="none"),
    pytest.param([], id="empty-list"),
    pytest.param({}, id="empty-dict"),
    pytest.param("unexpected-non-empty-value", id="arbitrary-string"),
]


class _StaticRealProvider:
    def generate_operator_candidates(self, prompt, n, operator_type, round_id):
        return [
            GeneratedOperatorDraft(
                operator_id="strict_policy_candidate",
                operator_type="repair",
                round_id=round_id,
                name="strict_policy_candidate",
                description="must not execute for non-bool allow values",
                source="langchain_openai_compatible",
                code=VALID_REPAIR_CODE,
                module_filename="strict_policy_candidate.py",
            )
        ]

    def revise_operator_candidates(
        self, prompt, previous_results, n, operator_type, round_id
    ):
        return self.generate_operator_candidates(
            prompt, n, operator_type, round_id
        )


def _code_hash(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _write_yaml_config(tmp_path: Path, unsafe_value) -> Path:
    path = tmp_path / "operator_evolution.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "operator_evolution": {
                    "allow_unsafe_candidate_execution": unsafe_value,
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return path


def _complete_candidate_row() -> dict:
    return {
        "operator_id": "complete_candidate",
        "operator_type": "repair",
        "validation_status": "valid",
        "execution_status": "success",
        "failure_type": "success",
        "safe_to_execute": True,
        "requires_human_risk_ack": False,
        "sandbox_level": "timeout_only",
        **build_generated_artifact_metadata(
            claimed_source_provider="mock", round_id=0, code_hash="abc123"
        ),
        "fallback_used": False,
        "error_rate": 0.0,
        "timeout_rate": 0.0,
        "invalid_solution_rate": 0.0,
        "code_hash": "abc123",
    }


def _complete_registry_row(path: Path, *, timeout_ms=100.0) -> dict:
    code_hash = _code_hash(path.read_text(encoding="utf-8"))
    return {
        "name": path.stem,
        "operator_type": "repair",
        "file_path": str(path),
        "code_hash": code_hash,
        "validation_status": "valid",
        "execution_status": "success",
        "failure_type": "success",
        **build_generated_artifact_metadata(
            claimed_source_provider="mock", round_id=0, code_hash=code_hash
        ),
        "sandbox_level": "timeout_only",
        "effective_sandbox_level": "timeout_only",
        "executor_identity": "timeout_only_subprocess_v1",
        "safe_to_execute": True,
        "requires_human_risk_ack": False,
        "fallback_used": False,
        "error_rate": 0.0,
        "timeout_rate": 0.0,
        "invalid_solution_rate": 0.0,
        "validation_failed_rate": 0.0,
        "execution_blocked_rate": 0.0,
        "timeout_ms": timeout_ms,
    }


def _write_registry(tmp_path: Path, row: dict) -> Path:
    path = tmp_path / "operator_registry.json"
    path.write_text(
        json.dumps({"repair": [row], "destroy": []}),
        encoding="utf-8",
    )
    return path


def _make_solver(registry_path: Path) -> ALNSSolver:
    return ALNSSolver(
        load_instance(INSTANCE_PATH),
        config=ALNSConfig(
            iterations=0,
            frozen_operator_registry_path=str(registry_path),
            use_frozen_repair=True,
            allow_generated_frozen_deployment=True,
            explicit_runtime_deployment_ack=True,
            runtime_authorization_source="current_runtime_config",
        ),
    )


@pytest.mark.parametrize("unsafe_value", NON_BOOLEAN_UNSAFE_VALUES)
def test_yaml_non_boolean_unsafe_execution_is_rejected_or_disabled(
    tmp_path: Path, unsafe_value
) -> None:
    yaml_path = _write_yaml_config(tmp_path, unsafe_value)
    parsed = _load_yaml_config(yaml_path)

    try:
        config = _build_evolution_config(PROJECT_ROOT, parsed)
    except (TypeError, ValueError):
        return

    assert config.allow_unsafe_candidate_execution is False


def test_yaml_literal_booleans_remain_strict_booleans(tmp_path: Path) -> None:
    false_config = _build_evolution_config(
        PROJECT_ROOT,
        _load_yaml_config(_write_yaml_config(tmp_path, False)),
    )
    true_config = _build_evolution_config(
        PROJECT_ROOT,
        _load_yaml_config(_write_yaml_config(tmp_path, True)),
    )

    assert false_config.allow_unsafe_candidate_execution is False
    assert true_config.allow_unsafe_candidate_execution is True


@pytest.mark.parametrize("unsafe_value", NON_BOOLEAN_UNSAFE_VALUES)
def test_loader_non_boolean_allow_value_never_reaches_smoke(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    unsafe_value,
) -> None:
    path = tmp_path / "strict_loader_candidate.py"
    path.write_text(VALID_REPAIR_CODE, encoding="utf-8")
    smoke_calls: list[str] = []

    def _unexpected_smoke(*args, **kwargs):
        smoke_calls.append("called")
        return CandidateExecutionResult(status="success", runtime_ms=0.0)

    monkeypatch.setattr(loader_module, "_smoke_test", _unexpected_smoke)

    loaded = load_and_validate_candidate(
        path=path,
        operator_type="repair",
        round_id=0,
        source="langchain_openai_compatible",
        description="strict non-bool loader gate",
        allow_unsafe_candidate_execution=unsafe_value,
    )

    assert smoke_calls == []
    assert loaded.callable_obj is None
    assert loaded.validation.safe_to_execute is False
    assert loaded.validation.requires_human_risk_ack is True
    assert loaded.validation.execution_status in BLOCKED_STATUSES
    assert loaded.validation.failure_type in BLOCKED_STATUSES


@pytest.mark.parametrize(
    "unsafe_value",
    [pytest.param("false", id="string-false"), pytest.param(1, id="integer-one")],
)
def test_evolution_non_boolean_allow_value_never_enters_benchmark_or_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    unsafe_value,
) -> None:
    smoke_calls: list[str] = []
    benchmark_candidate_counts: list[int] = []

    def _unexpected_smoke(*args, **kwargs):
        smoke_calls.append("called")
        return CandidateExecutionResult(status="success", runtime_ms=0.0)

    def _capture_benchmark(candidates, cases, *, seeds, timeout_ms):
        benchmark_candidate_counts.append(len(candidates))
        return []

    monkeypatch.setattr(loader_module, "_smoke_test", _unexpected_smoke)
    monkeypatch.setattr(loop_module, "evaluate_repair_candidates", _capture_benchmark)

    try:
        config = EvolutionLoopConfig(
            project_root=PROJECT_ROOT,
            generated_dir=tmp_path / "generated",
            output_dir=tmp_path / "outputs",
            round_count=1,
            repair_candidates_per_round=1,
            destroy_candidates_per_round=0,
            benchmark_instance_glob="data/R2_T6_0.txt",
            seeds=(0,),
            operator_types_to_evolve=("repair",),
            provider_name="langchain_openai_compatible",
            allow_unsafe_candidate_execution=unsafe_value,
        )
        artifacts = run_evolution_loop(_StaticRealProvider(), config)
    except (TypeError, ValueError):
        assert smoke_calls == []
        assert benchmark_candidate_counts == []
        return

    assert smoke_calls == []
    assert benchmark_candidate_counts == [0]
    rows = json.loads(
        (tmp_path / "outputs" / "round_000_candidates.json").read_text("utf-8")
    )
    assert rows[0]["execution_status"] in BLOCKED_STATUSES
    assert _is_freezable(rows[0]) is False
    summary = json.loads(Path(artifacts.evolution_summary_path).read_text("utf-8"))
    assert summary["repair_selection_status"] == "no_valid_operator"


def test_literal_true_can_reach_smoke_only_as_explicit_acknowledgement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "explicit_true_candidate.py"
    path.write_text(VALID_REPAIR_CODE, encoding="utf-8")
    smoke_calls: list[str] = []

    def _successful_smoke(*args, **kwargs):
        smoke_calls.append("called")
        return CandidateExecutionResult(status="success", runtime_ms=0.0)

    monkeypatch.setattr(loader_module, "_smoke_test", _successful_smoke)
    loaded = load_and_validate_candidate(
        path=path,
        operator_type="repair",
        round_id=0,
        source="langchain_openai_compatible",
        description="literal true explicit acknowledgement",
        allow_unsafe_candidate_execution=True,
    )

    assert smoke_calls == ["called"]
    assert loaded.validation.validation_status == "valid"
    assert loaded.validation.execution_status == "success"
    assert loaded.validation.safe_to_execute is True
    assert loaded.validation.requires_human_risk_ack is False


@pytest.mark.parametrize(
    ("field_name", "unsafe_value"),
    [
        pytest.param("validation_status", "invalid", id="validation"),
        pytest.param("execution_status", "runtime_error", id="execution"),
        pytest.param("failure_type", "runtime_error", id="failure"),
        pytest.param("safe_to_execute", False, id="safe-flag"),
        pytest.param("requires_human_risk_ack", True, id="risk-ack"),
        pytest.param("sandbox_level", "unknown", id="sandbox"),
        pytest.param("source", "", id="provider"),
        pytest.param("code_hash", "", id="hash"),
    ],
)
def test_literal_true_does_not_bypass_other_execution_evidence(
    field_name: str, unsafe_value
) -> None:
    validation = OperatorValidationResult(
        operator_id="policy_candidate",
        operator_type="repair",
        round_id=0,
        name="policy_candidate",
        description="strict execution evidence",
        source="langchain_openai_compatible",
        file_path="in-memory",
        validation_status="valid",
        execution_status="success",
        failure_type="success",
        sandbox_level="timeout_only",
        claimed_sandbox_level="timeout_only",
        effective_sandbox_level="timeout_only",
        executor_identity="timeout_only_subprocess_v1",
        safe_to_execute=True,
        requires_human_risk_ack=False,
        runtime_authorization_source="operator_evolution_runner_policy",
        allow_real_provider_frozen_deployment=True,
        explicit_runtime_risk_ack=True,
        code_hash="abc123",
    )
    setattr(validation, field_name, unsafe_value)
    loaded = LoadedOperator(
        validation=validation,
        callable_obj=CandidateProxy(
            path=Path("in-memory"),
            operator_type="repair",
            expected_code_hash="abc123",
            timeout_ms=100.0,
        ),
    )

    assert _can_enter_benchmark(loaded, True) is False


def test_literal_true_with_complete_execution_evidence_is_eligible() -> None:
    validation = OperatorValidationResult(
        operator_id="policy_candidate",
        operator_type="repair",
        round_id=0,
        name="policy_candidate",
        description="strict execution evidence",
        source="langchain_openai_compatible",
        file_path="in-memory",
        validation_status="valid",
        execution_status="success",
        failure_type="success",
        sandbox_level="timeout_only",
        claimed_sandbox_level="timeout_only",
        effective_sandbox_level="timeout_only",
        executor_identity="timeout_only_subprocess_v1",
        safe_to_execute=True,
        requires_human_risk_ack=False,
        runtime_authorization_source="operator_evolution_runner_policy",
        allow_real_provider_frozen_deployment=True,
        explicit_runtime_risk_ack=True,
        code_hash="abc123",
    )
    loaded = LoadedOperator(
        validation=validation,
        callable_obj=CandidateProxy(
            path=Path("in-memory"),
            operator_type="repair",
            expected_code_hash="abc123",
            timeout_ms=100.0,
        ),
    )

    assert _can_enter_benchmark(loaded, True) is True


def test_direct_path_execution_without_expected_hash_is_rejected(
    tmp_path: Path,
) -> None:
    path = tmp_path / "direct_missing_hash.py"
    path.write_text(NO_HASH_EXECUTION_CODE, encoding="utf-8")

    outcome = execute_candidate_process(
        path=path,
        operator_type="repair",
        args=(None, [], None, None),
        timeout_ms=500.0,
    )

    assert outcome.status in MISSING_HASH_STATUSES
    assert outcome.result is None


def test_candidate_proxy_without_expected_hash_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "proxy_missing_hash.py"
    path.write_text(NO_HASH_EXECUTION_CODE, encoding="utf-8")
    proxy = CandidateProxy(path=path, operator_type="repair")

    outcome = proxy.execute((None, [], None, None), timeout_ms=500.0)

    assert outcome.status in MISSING_HASH_STATUSES
    assert outcome.result is None


@pytest.mark.parametrize(
    "missing_field",
    [
        "failure_type",
        "source_provider",
        "sandbox_level",
        "requires_human_risk_ack",
        "fallback_used",
        "error_rate",
        "timeout_rate",
        "invalid_solution_rate",
    ],
)
def test_frozen_registry_missing_complete_evidence_is_rejected(
    tmp_path: Path, missing_field: str
) -> None:
    operator_path = tmp_path / f"missing_{missing_field}_repair.py"
    operator_path.write_text(VALID_REPAIR_CODE, encoding="utf-8")
    row = _complete_registry_row(operator_path)
    row.pop(missing_field)
    registry = _write_registry(tmp_path, row)

    solver = _make_solver(registry)

    assert operator_path.stem not in solver.frozen_repair_ops
    assert solver.fallback_events
    event = solver.fallback_events[-1]
    assert event["stage"] == "registry_validation"
    assert event["fallback_used"] is True
    assert missing_field in event["fallback_reason"]


@pytest.mark.parametrize(
    "timeout_ms",
    [
        pytest.param("abc", id="string"),
        pytest.param(float("nan"), id="nan"),
        pytest.param(float("inf"), id="infinity"),
        pytest.param(0, id="zero"),
        pytest.param(-1, id="negative"),
        pytest.param(None, id="none"),
    ],
)
def test_invalid_registry_timeout_is_structured_fallback(
    tmp_path: Path, timeout_ms
) -> None:
    operator_path = tmp_path / "invalid_timeout_repair.py"
    operator_path.write_text(VALID_REPAIR_CODE, encoding="utf-8")
    registry = _write_registry(
        tmp_path,
        _complete_registry_row(operator_path, timeout_ms=timeout_ms),
    )

    solver = _make_solver(registry)

    assert operator_path.stem not in solver.frozen_repair_ops
    assert solver.fallback_events
    event = solver.fallback_events[-1]
    assert event["stage"] == "registry_validation"
    assert event["fallback_used"] is True
    assert "timeout" in event["fallback_reason"].lower()


def test_positive_finite_registry_timeout_remains_valid(tmp_path: Path) -> None:
    operator_path = tmp_path / "valid_timeout_repair.py"
    operator_path.write_text(VALID_REPAIR_CODE, encoding="utf-8")
    registry = _write_registry(
        tmp_path,
        _complete_registry_row(operator_path, timeout_ms=100.0),
    )

    solver = _make_solver(registry)

    assert operator_path.stem in solver.frozen_repair_ops


@pytest.mark.parametrize(
    "missing_field",
    ["fallback_used", "error_rate", "timeout_rate", "invalid_solution_rate"],
)
def test_selection_and_freezing_reject_missing_failure_evidence(
    missing_field: str,
) -> None:
    row = _complete_candidate_row()
    row.pop(missing_field)

    assert _is_eligible(row) is False
    assert _is_freezable(row) is False


@pytest.mark.parametrize(
    "obsolete_statement",
    [
        "loader 仍会在主进程动态 import",
        "timeout 为执行完成后的软标记",
        "registry hash 尚未强校验",
        "frozen operator 返回值/feasibility 与 registry hash 尚未强校验",
    ],
)
def test_formal_spec_removes_obsolete_pre_hardening_statements(
    obsolete_statement: str,
) -> None:
    content = (
        PROJECT_ROOT / "docs" / "llm_operator_evolution_spec.md"
    ).read_text(encoding="utf-8")

    assert obsolete_statement not in content


def test_formal_spec_records_current_timeout_only_residual_risk() -> None:
    content = (
        PROJECT_ROOT / "docs" / "llm_operator_evolution_spec.md"
    ).read_text(encoding="utf-8").lower()

    assert "timeout_only" in content or "timeout-only" in content
    assert "not a capability sandbox" in content or "不是完整" in content
