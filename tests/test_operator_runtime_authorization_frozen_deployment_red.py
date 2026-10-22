from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.heuristics.alns_solver import ALNSConfig, ALNSSolver
from mrta_rect_coverage.llm.operator_evolution.candidate_execution import (
    CandidateProxy,
    TRUSTED_EXECUTOR_IDENTITY,
    TRUSTED_EXECUTOR_SANDBOX_LEVEL,
)
from mrta_rect_coverage.llm.operator_evolution.eligibility_policy import (
    build_generated_artifact_metadata,
    candidate_is_execution_eligible,
    candidate_is_freeze_eligible,
    candidate_is_selection_eligible,
)
from mrta_rect_coverage.llm.operator_evolution.schemas import (
    OperatorValidationResult,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INSTANCE_PATH = PROJECT_ROOT / "data" / "R2_T6_0.txt"
REAL_PROVIDER = "langchain_openai_compatible"
RUNTIME_AUTHORIZATION_SOURCE = "current_runtime_config"
_MISSING = object()

VALID_REPAIR_CODE = '''\
from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import RepairResult

def repair(partial_solution, unassigned_tasks, context, rng):
    routes = [list(route) for route in partial_solution.routes]
    for task_id in unassigned_tasks:
        routes[0].append(task_id)
    return RepairResult(solution=MultiRobotSolution(routes=routes))
'''

NON_BOOLEAN_VALUES = [
    pytest.param("true", id="string-true"),
    pytest.param("false", id="string-false"),
    pytest.param("0", id="string-zero"),
    pytest.param("1", id="string-one"),
    pytest.param(1, id="integer-one"),
    pytest.param(0, id="integer-zero"),
    pytest.param(None, id="none"),
    pytest.param([], id="empty-list"),
    pytest.param({}, id="empty-dict"),
    pytest.param("arbitrary-non-empty-string", id="arbitrary-string"),
]


def _code_hash(source_text: str) -> str:
    return hashlib.sha256(source_text.encode("utf-8")).hexdigest()


def _complete_real_provider_registry_row(operator_path: Path) -> dict:
    code_hash = _code_hash(operator_path.read_text(encoding="utf-8"))
    return {
        "name": operator_path.stem,
        "operator_type": "repair",
        "file_path": str(operator_path),
        "source_round": 0,
        "code_hash": code_hash,
        "validation_status": "valid",
        "execution_status": "success",
        "failure_type": "success",
        **build_generated_artifact_metadata(
            claimed_source_provider=REAL_PROVIDER, round_id=0, code_hash=code_hash
        ),
        "sandbox_level": "timeout_only",
        "claimed_sandbox_level": "timeout_only",
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
        "timeout_ms": 100.0,
        "avg_relative_improvement": 0.1,
        "success_rate": 1.0,
    }


def _write_registry(tmp_path: Path, row: dict) -> Path:
    registry_path = tmp_path / "operator_registry.json"
    registry_path.write_text(
        json.dumps({"repair": [row], "destroy": []}),
        encoding="utf-8",
    )
    return registry_path


def _make_solver(
    registry_path: Path,
    *,
    allow_real_provider_frozen_deployment=_MISSING,
    explicit_runtime_risk_ack=_MISSING,
    runtime_authorization_source=_MISSING,
    iterations: int = 0,
) -> ALNSSolver:
    config = ALNSConfig(
        iterations=iterations,
        frozen_operator_registry_path=str(registry_path),
        use_frozen_repair=True,
        random_seed=0,
    )
    # These attributes intentionally model current-session authority. They are
    # attached to the runtime config, never copied from the artifact row.
    if allow_real_provider_frozen_deployment is not _MISSING:
        config.allow_real_provider_frozen_deployment = (
            allow_real_provider_frozen_deployment
        )
    if explicit_runtime_risk_ack is not _MISSING:
        config.explicit_runtime_risk_ack = explicit_runtime_risk_ack
    if runtime_authorization_source is not _MISSING:
        config.runtime_authorization_source = runtime_authorization_source
    return ALNSSolver(load_instance(INSTANCE_PATH), config=config)


def _write_real_provider_fixture(tmp_path: Path) -> tuple[Path, dict, Path]:
    operator_path = tmp_path / "real_provider_frozen_repair.py"
    operator_path.write_text(VALID_REPAIR_CODE, encoding="utf-8")
    row = _complete_real_provider_registry_row(operator_path)
    return operator_path, row, _write_registry(tmp_path, row)


def _assert_runtime_authorization_fallback(
    solver: ALNSSolver, operator_name: str
) -> None:
    assert operator_name not in solver.frozen_repair_ops
    assert operator_name not in solver.repair_ops
    assert "greedy_insertion" in solver.repair_ops
    assert solver.fallback_events
    event = solver.fallback_events[-1]
    assert event["fallback_used"] is True
    reason = str(event["fallback_reason"]).lower()
    assert any(
        token in reason
        for token in (
            "missing_runtime_authorization",
            "real_provider_deployment_blocked",
            "runtime authorization",
            "risk ack",
        )
    )


def test_forged_real_provider_artifact_is_rejected_without_runtime_authorization(
    tmp_path: Path,
) -> None:
    operator_path, row, registry_path = _write_real_provider_fixture(tmp_path)

    # Evaluation evidence may be complete; deployment authority is a separate
    # current-runtime decision and cannot come from this row.
    assert candidate_is_selection_eligible(row) is True
    assert candidate_is_freeze_eligible(row) is True

    solver = _make_solver(registry_path)

    _assert_runtime_authorization_fallback(solver, operator_path.stem)


def test_artifact_self_reported_runtime_ack_is_not_trusted(
    tmp_path: Path,
) -> None:
    operator_path, row, _ = _write_real_provider_fixture(tmp_path)
    row.update(
        {
            "allow_real_provider_frozen_deployment": True,
            "explicit_runtime_risk_ack": True,
            "runtime_authorization_source": RUNTIME_AUTHORIZATION_SOURCE,
        }
    )
    registry_path = _write_registry(tmp_path, row)

    solver = _make_solver(registry_path)

    _assert_runtime_authorization_fallback(solver, operator_path.stem)


def test_rejected_real_provider_frozen_operator_is_not_success_or_rewarded(
    tmp_path: Path,
) -> None:
    operator_path, _, registry_path = _write_real_provider_fixture(tmp_path)
    solver = _make_solver(registry_path, iterations=1)

    result = solver.solve()

    _assert_runtime_authorization_fallback(solver, operator_path.stem)
    assert operator_path.stem not in result.operator_usage_stats["repair"]
    assert all(
        row.get("llm_operator_success") is False
        for row in result.iteration_history
    )


@pytest.mark.parametrize(
    "field_name",
    [
        "allow_real_provider_frozen_deployment",
        "explicit_runtime_risk_ack",
    ],
)
@pytest.mark.parametrize("invalid_value", NON_BOOLEAN_VALUES)
def test_non_boolean_runtime_authorization_flags_fail_closed(
    tmp_path: Path,
    field_name: str,
    invalid_value,
) -> None:
    operator_path, _, registry_path = _write_real_provider_fixture(tmp_path)
    runtime_values = {
        "allow_real_provider_frozen_deployment": True,
        "explicit_runtime_risk_ack": True,
    }
    runtime_values[field_name] = invalid_value

    solver = _make_solver(
        registry_path,
        **runtime_values,
        runtime_authorization_source=RUNTIME_AUTHORIZATION_SOURCE,
    )

    _assert_runtime_authorization_fallback(solver, operator_path.stem)


@pytest.mark.parametrize(
    ("allow_deployment", "risk_ack"),
    [
        pytest.param(False, True, id="allow-false"),
        pytest.param(True, False, id="ack-false"),
        pytest.param(False, False, id="both-false"),
    ],
)
def test_literal_false_runtime_authorization_flags_block_deployment(
    tmp_path: Path,
    allow_deployment: bool,
    risk_ack: bool,
) -> None:
    operator_path, _, registry_path = _write_real_provider_fixture(tmp_path)

    solver = _make_solver(
        registry_path,
        allow_real_provider_frozen_deployment=allow_deployment,
        explicit_runtime_risk_ack=risk_ack,
        runtime_authorization_source=RUNTIME_AUTHORIZATION_SOURCE,
    )

    _assert_runtime_authorization_fallback(solver, operator_path.stem)


def test_runtime_authorization_source_is_required_for_real_provider_deployment(
    tmp_path: Path,
) -> None:
    operator_path, _, registry_path = _write_real_provider_fixture(tmp_path)

    solver = _make_solver(
        registry_path,
        allow_real_provider_frozen_deployment=True,
        explicit_runtime_risk_ack=True,
    )

    _assert_runtime_authorization_fallback(solver, operator_path.stem)


def test_literal_runtime_allow_and_ack_permit_timeout_only_deployment(
    tmp_path: Path,
) -> None:
    operator_path, _, registry_path = _write_real_provider_fixture(tmp_path)

    solver = _make_solver(
        registry_path,
        allow_real_provider_frozen_deployment=True,
        explicit_runtime_risk_ack=True,
        runtime_authorization_source=RUNTIME_AUTHORIZATION_SOURCE,
    )

    assert operator_path.stem in solver.frozen_repair_ops
    assert TRUSTED_EXECUTOR_SANDBOX_LEVEL == "timeout_only"
    assert "capability" not in TRUSTED_EXECUTOR_SANDBOX_LEVEL


def _complete_runtime_authorized_validation() -> OperatorValidationResult:
    validation = OperatorValidationResult(
        operator_id="runtime_authorized_candidate",
        operator_type="repair",
        round_id=0,
        name="runtime_authorized_candidate",
        description="runtime authority evidence is mandatory",
        source=REAL_PROVIDER,
        file_path="candidate.py",
        validation_status="valid",
        execution_status="success",
        failure_type="success",
        sandbox_level="timeout_only",
        claimed_sandbox_level="timeout_only",
        effective_sandbox_level=TRUSTED_EXECUTOR_SANDBOX_LEVEL,
        executor_identity=TRUSTED_EXECUTOR_IDENTITY,
        safe_to_execute=True,
        requires_human_risk_ack=False,
        code_hash="abc123",
    )
    validation.runtime_authorization_source = RUNTIME_AUTHORIZATION_SOURCE
    validation.allow_real_provider_frozen_deployment = True
    validation.explicit_runtime_risk_ack = True
    return validation


def _trusted_proxy() -> CandidateProxy:
    return CandidateProxy(
        path=Path("candidate.py"),
        operator_type="repair",
        expected_code_hash="abc123",
        timeout_ms=100.0,
    )


@pytest.mark.parametrize(
    "missing_field",
    [
        "effective_sandbox_level",
        "executor_identity",
        "runtime_authorization_source",
        "allow_real_provider_frozen_deployment",
        "explicit_runtime_risk_ack",
    ],
)
def test_execution_policy_missing_runtime_authority_evidence_fails_closed(
    missing_field: str,
) -> None:
    validation = _complete_runtime_authorized_validation()
    delattr(validation, missing_field)

    assert (
        candidate_is_execution_eligible(validation, _trusted_proxy(), True)
        is False
    )


def test_arbitrary_callable_is_not_trusted_executor_authority() -> None:
    validation = _complete_runtime_authorized_validation()

    assert (
        candidate_is_execution_eligible(validation, lambda *args: None, True)
        is False
    )


def test_validation_schema_defaults_are_conservative() -> None:
    validation = OperatorValidationResult(
        operator_id="default_candidate",
        operator_type="repair",
        round_id=0,
        name="default_candidate",
        description="missing evidence must not imply trust",
        source=REAL_PROVIDER,
        file_path="candidate.py",
        validation_status="valid",
    )

    assert validation.safe_to_execute is not True
    assert validation.requires_human_risk_ack is not False
    assert validation.sandbox_level != TRUSTED_EXECUTOR_SANDBOX_LEVEL
    assert validation.effective_sandbox_level != TRUSTED_EXECUTOR_SANDBOX_LEVEL
    assert validation.executor_identity != TRUSTED_EXECUTOR_IDENTITY


def test_formal_spec_is_phase_4f_and_requires_runtime_frozen_authorization() -> None:
    content = (
        PROJECT_ROOT / "docs" / "llm_operator_evolution_spec.md"
    ).read_text(encoding="utf-8")
    lowered = content.lower()

    assert "截至 Phase 4D" not in content
    assert "frozen" in lowered
    assert "runtime authorization" in lowered or "运行时授权" in content
    assert "artifact 自证" in content or "artifact self" in lowered


def test_operator_evolution_docs_use_timeout_only_not_capability_sandbox_wording() -> None:
    content = (
        PROJECT_ROOT / "docs" / "operator_evolution.md"
    ).read_text(encoding="utf-8").lower()

    assert "no sandboxed execution for untrusted code" not in content
    assert "timeout-only" in content or "timeout_only" in content
    assert "not a complete capability sandbox" in content
