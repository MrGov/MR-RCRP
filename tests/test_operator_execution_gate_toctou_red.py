from __future__ import annotations

from dataclasses import fields
import hashlib
import inspect
import json
from pathlib import Path

import pytest

from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.core.models import MultiRobotSolution
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
from mrta_rect_coverage.llm.operator_evolution.candidate_security import (
    validate_candidate_source,
)
from mrta_rect_coverage.llm.operator_evolution.evaluator import (
    build_repair_benchmark_cases,
    evaluate_repair_candidates,
)
from mrta_rect_coverage.llm.operator_evolution.eligibility_policy import (
    build_generated_artifact_metadata,
)
from mrta_rect_coverage.llm.operator_evolution.evolution_loop import (
    EvolutionLoopConfig,
    _is_eligible,
    run_evolution_loop,
)
from mrta_rect_coverage.llm.operator_evolution.freezing import _is_freezable
from mrta_rect_coverage.llm.operator_evolution.protocols import RepairResult
from mrta_rect_coverage.llm.operator_evolution.schemas import (
    GeneratedOperatorDraft,
    OperatorValidationResult,
)
from mrta_rect_coverage.llm.operator_evolution.utils import is_solution_complete


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INSTANCE_PATH = PROJECT_ROOT / "data" / "R2_T6_0.txt"
BLOCKED_STATUSES = {"execution_blocked", "risk_ack_required"}

VALID_REPAIR_CODE = '''\
from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import RepairResult

def repair(partial_solution, unassigned_tasks, context, rng):
    routes = [list(route) for route in partial_solution.routes]
    for task_id in unassigned_tasks:
        routes[0].append(task_id)
    return RepairResult(solution=MultiRobotSolution(routes=routes))
'''

ALTERNATE_VALID_REPAIR_CODE = '''\
from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import RepairResult

def repair(partial_solution, unassigned_tasks, context, rng):
    routes = [list(route) for route in partial_solution.routes]
    for task_id in unassigned_tasks:
        routes[-1].append(task_id)
    return RepairResult(solution=MultiRobotSolution(routes=routes))
'''


class _StaticRepairProvider:
    def generate_operator_candidates(self, prompt, n, operator_type, round_id):
        return [
            GeneratedOperatorDraft(
                operator_id="real_provider_candidate",
                operator_type="repair",
                round_id=round_id,
                name="real_provider_candidate",
                description="must be blocked before execution",
                source="langchain_openai_compatible",
                code=VALID_REPAIR_CODE,
                module_filename="real_provider_candidate.py",
            )
        ]

    def revise_operator_candidates(
        self, prompt, previous_results, n, operator_type, round_id
    ):
        return self.generate_operator_candidates(prompt, n, operator_type, round_id)


def _code_hash(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _registry_entry(path: Path, operator_type: str = "repair") -> dict:
    code_hash = _code_hash(path.read_text(encoding="utf-8"))
    return {
        "name": path.stem,
        "operator_type": operator_type,
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
        "timeout_ms": 100.0,
    }


def _write_registry(tmp_path: Path, repair_rows) -> Path:
    path = tmp_path / "operator_registry.json"
    path.write_text(
        json.dumps({"repair": repair_rows, "destroy": []}), encoding="utf-8"
    )
    return path


def _make_solver(registry_path: Path, *, iterations: int = 0) -> ALNSSolver:
    return ALNSSolver(
        load_instance(INSTANCE_PATH),
        config=ALNSConfig(
            iterations=iterations,
            frozen_operator_registry_path=str(registry_path),
            use_frozen_repair=True,
            allow_generated_frozen_deployment=True,
            explicit_runtime_deployment_ack=True,
            runtime_authorization_source="current_runtime_config",
        ),
    )


def _remove_one_task(solver: ALNSSolver):
    partial = MultiRobotSolution(
        routes=[list(route) for route in solver.initial_solution.routes]
    )
    route = next(route for route in partial.routes if route)
    removed_task = route.pop()
    return partial, [removed_task], solver.solution_evaluator.evaluate(partial)


def _valid_candidate_row() -> dict:
    return {
        "operator_id": "candidate",
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


def test_evolution_config_defaults_unsafe_candidate_execution_to_false() -> None:
    config_fields = {field.name: field for field in fields(EvolutionLoopConfig)}

    assert "allow_unsafe_candidate_execution" in config_fields
    assert config_fields["allow_unsafe_candidate_execution"].default is False


def test_real_provider_candidate_is_blocked_before_smoke_test(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "real_provider_candidate.py"
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
        description="real-provider execution gate",
    )

    assert loaded.validation.code_hash == _code_hash(VALID_REPAIR_CODE)
    assert smoke_calls == []
    assert loaded.validation.safe_to_execute is False
    assert loaded.validation.requires_human_risk_ack is True
    assert loaded.validation.execution_status in BLOCKED_STATUSES
    assert loaded.validation.failure_type in BLOCKED_STATUSES
    assert loaded.callable_obj is None


def test_real_provider_candidate_does_not_enter_benchmark_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    benchmark_candidate_counts: list[int] = []

    def _fake_smoke(*args, **kwargs):
        return CandidateExecutionResult(status="success", runtime_ms=0.0)

    def _capture_benchmark(candidates, cases, *, seeds, timeout_ms):
        benchmark_candidate_counts.append(len(candidates))
        return []

    monkeypatch.setattr(loader_module, "_smoke_test", _fake_smoke)
    monkeypatch.setattr(loop_module, "evaluate_repair_candidates", _capture_benchmark)

    artifacts = run_evolution_loop(
        _StaticRepairProvider(),
        EvolutionLoopConfig(
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
        ),
    )

    assert benchmark_candidate_counts == [0]
    rows = json.loads(
        (tmp_path / "outputs" / "round_000_candidates.json").read_text("utf-8")
    )
    assert len(rows) == 1
    assert rows[0]["execution_status"] in BLOCKED_STATUSES
    summary = json.loads(Path(artifacts.evolution_summary_path).read_text("utf-8"))
    assert summary["repair_selection_status"] == "no_valid_operator"


@pytest.mark.parametrize(
    "source",
    [
        '''\
from io import FileIO as F
def repair(partial_solution, unassigned_tasks, context, rng):
    return F
''',
        '''\
from pathlib import Path as P
def repair(partial_solution, unassigned_tasks, context, rng):
    return P
''',
        '''\
import importlib
def repair(partial_solution, unassigned_tasks, context, rng):
    return importlib
''',
        '''\
import builtins
def repair(partial_solution, unassigned_tasks, context, rng):
    return getattr(builtins, "open")
''',
        '''\
def repair(partial_solution, unassigned_tasks, context, rng):
    return object.__subclasses__()
''',
    ],
    ids=["fileio-alias", "pathlib-alias", "importlib", "builtins-getattr", "subclasses"],
)
def test_static_validation_rejects_capability_and_reflection_bypasses(
    source: str,
) -> None:
    with pytest.raises((SyntaxError, ValueError)):
        validate_candidate_source(source, "repair")


def test_path_execution_requires_expected_hash_and_rejects_changed_source(
    tmp_path: Path,
) -> None:
    proxy_parameters = inspect.signature(CandidateProxy).parameters
    executor_parameters = inspect.signature(execute_candidate_process).parameters
    assert "expected_code_hash" in proxy_parameters
    assert "expected_code_hash" in executor_parameters

    path = tmp_path / "mutable_candidate.py"
    path.write_text(VALID_REPAIR_CODE, encoding="utf-8")
    expected_hash = _code_hash(VALID_REPAIR_CODE)
    path.write_text(ALTERNATE_VALID_REPAIR_CODE, encoding="utf-8")

    outcome = execute_candidate_process(
        path=path,
        operator_type="repair",
        args=(None, [], None, None),
        timeout_ms=100.0,
        expected_code_hash=expected_hash,
    )

    assert outcome.status == "source_hash_mismatch"
    assert "hash" in outcome.error_message.lower()
    assert outcome.result is None


def test_frozen_operator_source_replacement_is_detected_before_call(
    tmp_path: Path,
) -> None:
    operator_path = tmp_path / "frozen_repair.py"
    operator_path.write_text(VALID_REPAIR_CODE, encoding="utf-8")
    registry = _write_registry(tmp_path, [_registry_entry(operator_path)])
    solver = _make_solver(registry)
    partial, removed_tasks, partial_eval = _remove_one_task(solver)
    replacement_marker = "REPLACED_SOURCE_WAS_CALLED"
    operator_path.write_text(
        '''\
def repair(partial_solution, unassigned_tasks, context, rng):
    raise RuntimeError("REPLACED_SOURCE_WAS_CALLED")
''',
        encoding="utf-8",
    )
    fallback_start = len(solver.fallback_events)

    repaired = solver.repair_ops[operator_path.stem](
        partial, removed_tasks, partial_eval
    )

    assert is_solution_complete(repaired, solver.instance)
    assert len(solver.fallback_events) == fallback_start + 1
    event = solver.fallback_events[-1]
    assert event["fallback_used"] is True
    assert event["execution_status"] == "source_hash_mismatch"
    assert "hash" in event["fallback_reason"].lower()
    assert replacement_marker not in event["fallback_reason"]


def test_frozen_source_replacement_is_not_generated_success_or_rewarded(
    tmp_path: Path,
) -> None:
    operator_path = tmp_path / "rewarded_frozen_repair.py"
    operator_path.write_text(VALID_REPAIR_CODE, encoding="utf-8")
    registry = _write_registry(tmp_path, [_registry_entry(operator_path)])
    solver = _make_solver(registry, iterations=1)
    solver._select_operators = lambda context: (  # type: ignore[method-assign]
        "random_destroy",
        operator_path.stem,
        "test",
    )
    operator_path.write_text(ALTERNATE_VALID_REPAIR_CODE, encoding="utf-8")

    result = solver.solve()

    history = result.iteration_history[0]
    assert history["fallback_used"] is True
    assert "hash" in history["fallback_reason"].lower()
    assert history["llm_operator_success"] is False
    assert result.operator_usage_stats["repair"][operator_path.stem].score == 0.0


MALFORMED_REPAIR_BODIES = {
    "routes-none": "return RepairResult(solution=MultiRobotSolution(routes=None))",
    "routes-not-list": '''\
routes = [list(route) for route in partial_solution.routes]
for task_id in unassigned_tasks:
    routes[0].append(task_id)
return RepairResult(solution=MultiRobotSolution(routes=tuple(routes)))
''',
    "route-not-list": '''\
routes = [list(route) for route in partial_solution.routes]
for task_id in unassigned_tasks:
    routes[0].append(task_id)
return RepairResult(solution=MultiRobotSolution(routes=[tuple(route) for route in routes]))
''',
    "invalid-task-id-type": '''\
routes = [list(route) for route in partial_solution.routes]
for task_id in unassigned_tasks:
    routes[0].append(str(task_id))
return RepairResult(solution=MultiRobotSolution(routes=routes))
''',
}


@pytest.mark.parametrize(
    ("case_id", "body"), MALFORMED_REPAIR_BODIES.items(), ids=MALFORMED_REPAIR_BODIES
)
def test_frozen_repair_malformed_shape_is_structured_invalid_fallback(
    tmp_path: Path, case_id: str, body: str
) -> None:
    code = (
        "from mrta_rect_coverage.core.models import MultiRobotSolution\n"
        "from mrta_rect_coverage.llm.operator_evolution.protocols import RepairResult\n\n"
        "def repair(partial_solution, unassigned_tasks, context, rng):\n"
        + "\n".join(f"    {line}" for line in body.splitlines())
        + "\n"
    )
    operator_path = tmp_path / f"malformed_{case_id}_repair.py"
    operator_path.write_text(code, encoding="utf-8")
    registry = _write_registry(tmp_path, [_registry_entry(operator_path)])
    solver = _make_solver(registry)
    partial, removed_tasks, partial_eval = _remove_one_task(solver)
    fallback_start = len(solver.fallback_events)

    repaired = solver.repair_ops[operator_path.stem](
        partial, removed_tasks, partial_eval
    )

    assert len(solver.fallback_events) == fallback_start + 1
    assert solver.fallback_events[-1]["execution_status"] == "invalid_solution"
    assert solver.fallback_events[-1]["fallback_used"] is True
    assert is_solution_complete(repaired, solver.instance)


def _loaded_in_memory_candidate(callable_obj) -> LoadedOperator:
    return LoadedOperator(
        validation=OperatorValidationResult(
            operator_id="malformed_benchmark_candidate",
            operator_type="repair",
            round_id=0,
            name="malformed_benchmark_candidate",
            description="malformed successful return",
            source="mock",
            file_path="in-memory",
            validation_status="valid",
            execution_status="success",
            failure_type="success",
            safe_to_execute=True,
        ),
        callable_obj=callable_obj,
    )


def _missing_result_fields(partial_solution, unassigned_tasks, context, rng):
    return object()


def _malformed_result_shape(partial_solution, unassigned_tasks, context, rng):
    return RepairResult(solution=MultiRobotSolution(routes=None))


@pytest.mark.parametrize(
    "callable_obj",
    [_missing_result_fields, _malformed_result_shape],
    ids=["missing-fields", "malformed-shape"],
)
def test_benchmark_malformed_success_is_structured_failure(callable_obj) -> None:
    rows = evaluate_repair_candidates(
        [_loaded_in_memory_candidate(callable_obj)],
        build_repair_benchmark_cases([INSTANCE_PATH]),
        seeds=(0,),
        timeout_ms=100.0,
    )

    assert len(rows) == 1
    assert rows[0]["failure_type"] in {"runtime_error", "invalid_solution"}
    assert rows[0]["execution_status"] == rows[0]["failure_type"]
    assert rows[0]["success_rate"] == 0.0


@pytest.mark.parametrize(
    "missing_field",
    [
        "safe_to_execute",
        "requires_human_risk_ack",
        "sandbox_level",
        "source_provider",
        "failure_type",
        "validation_status",
        "execution_status",
    ],
)
def test_selection_and_freeze_fail_closed_when_evidence_is_missing(
    missing_field: str,
) -> None:
    row = _valid_candidate_row()
    row.pop(missing_field)

    assert _is_eligible(row) is False
    assert _is_freezable(row) is False


def test_blocked_candidate_cannot_be_selected_or_frozen() -> None:
    row = _valid_candidate_row()
    row.update(
        {
            "execution_status": "risk_ack_required",
            "failure_type": "risk_ack_required",
            "safe_to_execute": False,
            "requires_human_risk_ack": True,
            "source_provider": "langchain_openai_compatible",
        }
    )

    assert _is_eligible(row) is False
    assert _is_freezable(row) is False


@pytest.mark.parametrize(
    "registry_case",
    ["invalid-json", "top-level-list", "row-not-object", "field-type-error"],
)
def test_malformed_frozen_registry_is_structured_fallback(
    tmp_path: Path, registry_case: str
) -> None:
    registry = tmp_path / "malformed_registry.json"
    if registry_case == "invalid-json":
        registry.write_text("{not valid json", encoding="utf-8")
    elif registry_case == "top-level-list":
        registry.write_text("[]", encoding="utf-8")
    elif registry_case == "row-not-object":
        registry.write_text(
            json.dumps({"repair": [None], "destroy": []}), encoding="utf-8"
        )
    else:
        registry.write_text(
            json.dumps(
                {
                    "repair": [
                        {
                            "name": ["not", "a", "string"],
                            "file_path": 123,
                            "code_hash": [],
                            "validation_status": "valid",
                            "execution_status": "success",
                            "safe_to_execute": True,
                        }
                    ],
                    "destroy": [],
                }
            ),
            encoding="utf-8",
        )

    solver = _make_solver(registry)

    assert solver.fallback_events
    event = solver.fallback_events[-1]
    assert event["stage"] == "registry_validation"
    assert event["fallback_used"] is True
    assert event["fallback_reason"]


def test_operator_evolution_docs_do_not_describe_obsolete_soft_timeout() -> None:
    content = (PROJECT_ROOT / "docs" / "operator_evolution.md").read_text(
        encoding="utf-8"
    ).lower()

    assert "timeout is soft" not in content
    assert "timeout_only" in content or "timeout-only" in content
    assert "not a complete" in content or "not a capability" in content


def test_readme_warns_before_real_llm_execution_command() -> None:
    content = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    lowered = content.lower()
    command = "--provider langchain_openai_compatible"
    command_index = lowered.index(command)
    prelude = lowered[max(0, command_index - 1800) : command_index]

    assert "warning" in prelude or "safety" in prelude or "安全" in prelude
    assert "timeout_only" in prelude or "timeout-only" in prelude
    assert "not a complete" in prelude or "not a capability" in prelude
