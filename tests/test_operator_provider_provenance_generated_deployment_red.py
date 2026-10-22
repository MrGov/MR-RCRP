from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.heuristics.alns_solver import ALNSConfig, ALNSSolver
from mrta_rect_coverage.llm.operator_evolution.eligibility_policy import (
    candidate_is_freeze_eligible,
    candidate_is_selection_eligible,
    validate_registry_metadata,
)
from mrta_rect_coverage.llm.operator_evolution.evolution_loop import _is_eligible
from mrta_rect_coverage.llm.operator_evolution.feedback_builder import (
    build_feedback_payload,
)
from mrta_rect_coverage.llm.operator_evolution.freezing import (
    freeze_best_operators,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INSTANCE_PATH = PROJECT_ROOT / "data" / "R2_T6_0.txt"
RUNTIME_AUTHORIZATION_SOURCE = "current_runtime_config"
GENERATED_ARTIFACT_TYPE = "generated_frozen_operator"
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

CLAIMED_PROVIDERS = (
    "mock",
    "file",
    "manual",
    "rule_based",
    "langchain_openai_compatible",
    "openai",
    "deepseek",
    "unknown",
)

NON_BOOLEAN_VALUES = (
    pytest.param("true", id="string-true"),
    pytest.param("false", id="string-false"),
    pytest.param(1, id="integer-one"),
    pytest.param(0, id="integer-zero"),
    pytest.param(None, id="none"),
    pytest.param([], id="empty-list"),
    pytest.param({}, id="empty-dict"),
    pytest.param("arbitrary-non-empty-string", id="arbitrary-string"),
)


def _code_hash(source_text: str) -> str:
    return hashlib.sha256(source_text.encode("utf-8")).hexdigest()


def _complete_generated_row(
    operator_path: Path,
    *,
    claimed_provider: str = "mock",
) -> dict:
    code_hash = _code_hash(operator_path.read_text(encoding="utf-8"))
    return {
        "name": operator_path.stem,
        "operator_id": operator_path.stem,
        "operator_type": "repair",
        "file_path": str(operator_path),
        "source_round": 0,
        "round_id": 0,
        "artifact_type": GENERATED_ARTIFACT_TYPE,
        "code_hash": code_hash,
        "validation_status": "valid",
        "execution_status": "success",
        "failure_type": "success",
        # Both fields below are artifact claims, never runtime authority.
        "source_provider": claimed_provider,
        "claimed_source_provider": claimed_provider,
        "provider_provenance": {
            "trust_level": "artifact_claim",
            "claimed_provider": claimed_provider,
            "authority": "artifact_metadata",
        },
        "generation_run_id": "generation-run-001",
        "artifact_identity": f"generated:{code_hash}",
        "lineage": {
            "generation_run_id": "generation-run-001",
            "parent_operator_ids": [],
        },
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


def _write_registry(tmp_path: Path, row: dict, *, suffix: str = "") -> Path:
    registry_path = tmp_path / f"operator_registry{suffix}.json"
    registry_path.write_text(
        json.dumps({"repair": [row], "destroy": []}),
        encoding="utf-8",
    )
    return registry_path


def _make_solver(
    registry_path: Path,
    *,
    allow_deployment=_MISSING,
    explicit_risk_ack=_MISSING,
    authorization_source=_MISSING,
    iterations: int = 0,
) -> ALNSSolver:
    config = ALNSConfig(
        iterations=iterations,
        frozen_operator_registry_path=str(registry_path),
        use_frozen_repair=True,
        random_seed=0,
    )
    if allow_deployment is not _MISSING:
        # The first name is the current Phase 4F API.  The second expresses the
        # Phase 4G policy without requiring a production symbol during RED.
        config.allow_real_provider_frozen_deployment = allow_deployment
        config.allow_generated_frozen_deployment = allow_deployment
    if explicit_risk_ack is not _MISSING:
        config.explicit_runtime_risk_ack = explicit_risk_ack
    if authorization_source is not _MISSING:
        config.runtime_authorization_source = authorization_source
    return ALNSSolver(load_instance(INSTANCE_PATH), config=config)


def _assert_generated_deployment_blocked(
    solver: ALNSSolver,
    operator_name: str,
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
            "missing_provider_provenance",
            "missing_runtime_authorization",
            "generated_artifact_deployment_blocked",
            "provider provenance",
            "runtime authorization",
        )
    )


def _write_operator(tmp_path: Path, name: str = "generated_repair") -> Path:
    operator_path = tmp_path / f"{name}.py"
    operator_path.write_text(VALID_REPAIR_CODE, encoding="utf-8")
    return operator_path


def test_real_provider_relabelled_as_mock_is_still_blocked_without_runtime_authorization(
    tmp_path: Path,
) -> None:
    operator_path = _write_operator(tmp_path, "relabelled_provider")
    rows = {
        "real": _complete_generated_row(
            operator_path,
            claimed_provider="langchain_openai_compatible",
        ),
        "mock": _complete_generated_row(operator_path, claimed_provider="mock"),
    }

    for label, row in rows.items():
        solver = _make_solver(
            _write_registry(tmp_path, row, suffix=f"_{label}")
        )
        _assert_generated_deployment_blocked(solver, operator_path.stem)


@pytest.mark.parametrize("claimed_provider", CLAIMED_PROVIDERS)
def test_every_generated_frozen_provider_claim_requires_runtime_authorization(
    tmp_path: Path,
    claimed_provider: str,
) -> None:
    operator_path = _write_operator(tmp_path, f"claimed_{claimed_provider}")
    row = _complete_generated_row(
        operator_path,
        claimed_provider=claimed_provider,
    )

    solver = _make_solver(_write_registry(tmp_path, row))

    _assert_generated_deployment_blocked(solver, operator_path.stem)


def test_current_runtime_authorization_is_positive_anchor_for_generated_deployment(
    tmp_path: Path,
) -> None:
    operator_path = _write_operator(tmp_path, "runtime_authorized_mock")
    row = _complete_generated_row(operator_path, claimed_provider="mock")

    solver = _make_solver(
        _write_registry(tmp_path, row),
        allow_deployment=True,
        explicit_risk_ack=True,
        authorization_source=RUNTIME_AUTHORIZATION_SOURCE,
    )

    assert operator_path.stem in solver.frozen_repair_ops


@pytest.mark.parametrize(
    "missing_field",
    (
        "claimed_source_provider",
        "provider_provenance",
        "lineage",
        "generation_run_id",
        "artifact_identity",
    ),
)
def test_generated_artifact_metadata_missing_provenance_or_lineage_fails_closed(
    tmp_path: Path,
    missing_field: str,
) -> None:
    operator_path = _write_operator(tmp_path, f"missing_{missing_field}")
    row = _complete_generated_row(operator_path)
    row.pop(missing_field)

    metadata_valid, reason, _ = validate_registry_metadata(row)

    assert metadata_valid is False
    assert missing_field in reason or "provenance" in reason or "lineage" in reason
    assert candidate_is_selection_eligible(row) is False
    assert candidate_is_freeze_eligible(row) is False


@pytest.mark.parametrize(
    "invalid_provenance",
    (
        pytest.param("unknown", id="unknown-string"),
        pytest.param(None, id="none"),
        pytest.param([], id="list"),
        pytest.param({}, id="empty-object"),
        pytest.param(
            {
                "trust_level": "unknown",
                "claimed_provider": "mock",
                "authority": "artifact_metadata",
            },
            id="unknown-trust-level",
        ),
    ),
)
def test_unknown_or_malformed_provider_provenance_fails_closed(
    tmp_path: Path,
    invalid_provenance,
) -> None:
    operator_path = _write_operator(tmp_path, "invalid_provenance")
    row = _complete_generated_row(operator_path)
    row["provider_provenance"] = invalid_provenance

    metadata_valid, reason, _ = validate_registry_metadata(row)

    assert metadata_valid is False
    assert "provenance" in reason.lower()
    assert candidate_is_selection_eligible(row) is False
    assert candidate_is_freeze_eligible(row) is False


def test_claimed_provider_and_provenance_provider_mismatch_fails_closed(
    tmp_path: Path,
) -> None:
    operator_path = _write_operator(tmp_path, "provider_mismatch")
    row = _complete_generated_row(operator_path, claimed_provider="mock")
    row["provider_provenance"]["claimed_provider"] = "file"

    metadata_valid, reason, _ = validate_registry_metadata(row)

    assert metadata_valid is False
    assert "provider" in reason.lower()
    assert candidate_is_selection_eligible(row) is False
    assert candidate_is_freeze_eligible(row) is False


@pytest.mark.parametrize(
    "field_name",
    (
        "allow_deployment",
        "explicit_risk_ack",
    ),
)
@pytest.mark.parametrize("invalid_value", NON_BOOLEAN_VALUES)
def test_non_boolean_runtime_authorization_never_enables_generated_deployment(
    tmp_path: Path,
    field_name: str,
    invalid_value,
) -> None:
    operator_path = _write_operator(tmp_path, f"strict_bool_{field_name}")
    row = _complete_generated_row(operator_path, claimed_provider="mock")
    runtime_values = {
        "allow_deployment": True,
        "explicit_risk_ack": True,
        "authorization_source": RUNTIME_AUTHORIZATION_SOURCE,
    }
    runtime_values[field_name] = invalid_value

    solver = _make_solver(_write_registry(tmp_path, row), **runtime_values)

    _assert_generated_deployment_blocked(solver, operator_path.stem)


def test_relabelled_generated_operator_is_absent_from_usage_and_reward_records(
    tmp_path: Path,
) -> None:
    operator_path = _write_operator(tmp_path, "relabelled_reward")
    row = _complete_generated_row(operator_path, claimed_provider="mock")
    solver = _make_solver(_write_registry(tmp_path, row), iterations=0)

    result = solver.solve()

    _assert_generated_deployment_blocked(solver, operator_path.stem)
    assert operator_path.stem not in result.operator_usage_stats["repair"]
    assert all(
        history_row.get("llm_operator_success") is False
        for history_row in result.iteration_history
    )


@pytest.mark.parametrize("claimed_provider", ("mock", "file"))
def test_claimed_provider_does_not_lower_selection_freezing_or_feedback_gate(
    tmp_path: Path,
    claimed_provider: str,
) -> None:
    operator_path = _write_operator(tmp_path, f"feedback_{claimed_provider}")
    row = _complete_generated_row(
        operator_path,
        claimed_provider=claimed_provider,
    )
    row.pop("provider_provenance")

    assert candidate_is_selection_eligible(row) is False
    assert candidate_is_freeze_eligible(row) is False
    assert _is_eligible(row) is False
    feedback = build_feedback_payload([row], top_k=1)
    assert feedback["top_operators"] == []
    assert feedback["weak_operators"] == []


def test_freezing_records_claimed_provider_without_promoting_it_to_trusted_provenance(
    tmp_path: Path,
) -> None:
    operator_id = "freeze_claimed_provider"
    generated_root = tmp_path / "generated"
    source_dir = generated_root / "round_000"
    source_dir.mkdir(parents=True)
    operator_path = source_dir / f"{operator_id}.py"
    operator_path.write_text(VALID_REPAIR_CODE, encoding="utf-8")
    row = _complete_generated_row(operator_path, claimed_provider="mock")
    best_path = tmp_path / "best_operators.json"
    best_path.write_text(
        json.dumps({"repair": row, "destroy": {}}),
        encoding="utf-8",
    )

    result = freeze_best_operators(
        project_root=PROJECT_ROOT,
        best_operators_json=best_path,
        generated_root=generated_root,
        target_dir=tmp_path / "frozen",
        registry_path=tmp_path / "frozen" / "operator_registry.json",
    )
    registry = json.loads(Path(result.registry_path).read_text(encoding="utf-8"))
    frozen_row = registry["repair"][0]

    assert frozen_row.get("claimed_source_provider") == "mock"
    assert frozen_row.get("trusted_provider_provenance") in (None, "unknown")
    provenance = frozen_row.get("provider_provenance", {})
    assert provenance.get("trust_level") != "trusted"


def test_formal_spec_distinguishes_claimed_provider_from_trusted_provenance() -> None:
    content = (
        PROJECT_ROOT / "docs" / "llm_operator_evolution_spec.md"
    ).read_text(encoding="utf-8")
    lowered = content.lower()

    assert "source_provider" in lowered
    assert "claimed" in lowered or "自报" in content or "声称" in content
    assert "provider provenance" in lowered or "provider 来源证明" in content
    assert "generated frozen" in lowered
    assert "runtime authorization" in lowered or "运行时授权" in content
    assert "capability token" in lowered or "不可伪造" in content
    assert "not" in lowered or "不是" in content or "不能" in content
