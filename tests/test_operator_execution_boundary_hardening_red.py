from __future__ import annotations

from collections import Counter
import hashlib
import inspect
import json
from pathlib import Path
import sys
from time import perf_counter

import pytest

from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.heuristics.alns_solver import ALNSConfig, ALNSSolver
from mrta_rect_coverage.llm.operator_evolution.candidate_execution import (
    execute_candidate_process,
)
from mrta_rect_coverage.llm.operator_evolution.candidate_loader import (
    load_and_validate_candidate,
)
from mrta_rect_coverage.llm.operator_evolution.evolution_loop import (
    EvolutionLoopConfig,
    _is_eligible,
    run_evolution_loop,
)
from mrta_rect_coverage.llm.operator_evolution.eligibility_policy import (
    build_generated_artifact_metadata,
)
from mrta_rect_coverage.llm.operator_evolution.schemas import GeneratedOperatorDraft
from mrta_rect_coverage.llm.operator_evolution.utils import is_solution_complete


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INSTANCE_PATH = PROJECT_ROOT / "data" / "R2_T6_0.txt"


VALID_REPAIR_PREFIX = '''\
from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import RepairResult
'''

SUCCESS_REPAIR_CODE = VALID_REPAIR_PREFIX + '''\
def repair(partial_solution, unassigned_tasks, context, rng):
    routes = [list(route) for route in partial_solution.routes]
    for task_id in unassigned_tasks:
        routes[0].append(task_id)
    return RepairResult(solution=MultiRobotSolution(routes=routes))
'''

RUNTIME_ERROR_REPAIR_CODE = VALID_REPAIR_PREFIX + '''\
def repair(partial_solution, unassigned_tasks, context, rng):
    if unassigned_tasks:
        raise RuntimeError("frozen repair runtime failure")
    return RepairResult(solution=partial_solution)
'''

TIMEOUT_REPAIR_CODE = VALID_REPAIR_PREFIX + '''\
import time

def repair(partial_solution, unassigned_tasks, context, rng):
    if unassigned_tasks:
        time.sleep(2.0)
    routes = [list(route) for route in partial_solution.routes]
    for task_id in unassigned_tasks:
        routes[0].append(task_id)
    return RepairResult(solution=MultiRobotSolution(routes=routes))
'''

MISSING_TASK_REPAIR_CODE = VALID_REPAIR_PREFIX + '''\
def repair(partial_solution, unassigned_tasks, context, rng):
    return RepairResult(solution=partial_solution)
'''

DUPLICATE_TASK_REPAIR_CODE = VALID_REPAIR_PREFIX + '''\
def repair(partial_solution, unassigned_tasks, context, rng):
    routes = [list(route) for route in partial_solution.routes]
    for task_id in unassigned_tasks:
        routes[0].extend([task_id, task_id])
    return RepairResult(solution=MultiRobotSolution(routes=routes))
'''

SYNTAX_INVALID_REPAIR_CODE = "def repair(:\n    pass\n"


class _StaticRepairProvider:
    def __init__(self, candidates: dict[str, str], source: str = "generated"):
        self.candidates = candidates
        self.source = source

    def generate_operator_candidates(self, prompt, n, operator_type, round_id):
        return [
            GeneratedOperatorDraft(
                operator_id=operator_id,
                operator_type="repair",
                round_id=round_id,
                name=operator_id,
                description="Phase 4B execution-boundary candidate",
                source=self.source,
                code=code,
                module_filename=f"{operator_id}.py",
            )
            for operator_id, code in self.candidates.items()
        ]

    def revise_operator_candidates(
        self, prompt, previous_results, n, operator_type, round_id
    ):
        return self.generate_operator_candidates(prompt, n, operator_type, round_id)


def _run_repair_candidates(
    tmp_path: Path,
    candidates: dict[str, str],
    *,
    timeout_ms: float = 100.0,
    provider_name: str = "mock",
):
    artifacts = run_evolution_loop(
        _StaticRepairProvider(candidates, source=provider_name),
        EvolutionLoopConfig(
            project_root=PROJECT_ROOT,
            generated_dir=tmp_path / "generated",
            output_dir=tmp_path / "outputs",
            round_count=1,
            repair_candidates_per_round=len(candidates),
            destroy_candidates_per_round=0,
            benchmark_instance_glob="data/R2_T6_0.txt",
            seeds=(0,),
            timeout_ms=timeout_ms,
            operator_types_to_evolve=("repair",),
            provider_name=provider_name,
        ),
    )
    rows = json.loads(
        (tmp_path / "outputs" / "round_000_candidates.json").read_text("utf-8")
    )
    return artifacts, rows


def _code_hash(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _registry_entry(
    path: Path,
    operator_type: str,
    *,
    name: str | None = None,
) -> dict:
    code_hash = _code_hash(path.read_text(encoding="utf-8"))
    return {
        "name": name or path.stem,
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


def _write_registry(
    tmp_path: Path,
    *,
    repair: list[dict] | None = None,
    destroy: list[dict] | None = None,
) -> Path:
    path = tmp_path / "operator_registry.json"
    path.write_text(
        json.dumps({"repair": repair or [], "destroy": destroy or []}),
        encoding="utf-8",
    )
    return path


def _make_solver(
    registry_path: Path,
    *,
    iterations: int = 0,
    repair: bool = False,
    destroy: bool = False,
) -> ALNSSolver:
    return ALNSSolver(
        load_instance(INSTANCE_PATH),
        config=ALNSConfig(
            iterations=iterations,
            frozen_operator_registry_path=str(registry_path),
            use_frozen_repair=repair,
            use_frozen_destroy=destroy,
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
    partial_eval = solver.solution_evaluator.evaluate(partial)
    return partial, [removed_task], partial_eval


def _assert_valid_destroy_partition(
    original: MultiRobotSolution,
    partial: MultiRobotSolution,
    removed_tasks: list[int],
) -> None:
    original_tasks = [task for route in original.routes for task in route]
    remaining_tasks = [task for route in partial.routes for task in route]
    assert Counter(remaining_tasks) + Counter(removed_tasks) == Counter(original_tasks)
    assert not (set(remaining_tasks) & set(removed_tasks))
    assert len(removed_tasks) == len(set(removed_tasks))


def test_execution_result_declares_timeout_only_not_capability_sandbox(
    tmp_path: Path,
) -> None:
    path = tmp_path / "simple_repair.py"
    path.write_text(
        "def repair(partial_solution, unassigned_tasks, context, rng):\n"
        "    return 'ok'\n",
        encoding="utf-8",
    )

    outcome = execute_candidate_process(
        path=path,
        operator_type="repair",
        args=(None, [], None, None),
        timeout_ms=500.0,
        expected_code_hash=_code_hash(path.read_text(encoding="utf-8")),
    )

    assert outcome.status == "success"
    assert outcome.sandbox_level == "timeout_only"
    assert outcome.sandbox_level != "capability_sandbox"


def test_real_llm_candidate_is_not_marked_safe_under_timeout_only_boundary(
    tmp_path: Path,
) -> None:
    _, rows = _run_repair_candidates(
        tmp_path,
        {"real_provider_candidate": SUCCESS_REPAIR_CODE},
        provider_name="langchain_openai_compatible",
    )
    row = rows[0]

    assert row.get("sandbox_level") == "timeout_only"
    assert row.get("safe_to_execute") is False


@pytest.mark.parametrize(
    "missing_field",
    ["code_hash", "validation_status", "execution_status", "safe_to_execute"],
)
def test_frozen_operator_missing_required_metadata_is_rejected(
    tmp_path: Path, missing_field: str
) -> None:
    operator_path = tmp_path / f"missing_{missing_field}_repair.py"
    operator_path.write_text(SUCCESS_REPAIR_CODE, encoding="utf-8")
    entry = _registry_entry(operator_path, "repair")
    entry.pop(missing_field)
    registry = _write_registry(tmp_path, repair=[entry])

    solver = _make_solver(registry, repair=True)

    assert operator_path.stem not in solver.frozen_repair_ops
    event = solver.fallback_events[-1]
    assert event["stage"] == "registry_validation"
    assert event["fallback_used"] is True
    assert missing_field in event["fallback_reason"]


def test_frozen_operator_source_is_ast_validated_again_before_loading(
    tmp_path: Path,
) -> None:
    operator_path = tmp_path / "forbidden_frozen_repair.py"
    operator_path.write_text(
        "import os\n" + SUCCESS_REPAIR_CODE,
        encoding="utf-8",
    )
    registry = _write_registry(
        tmp_path, repair=[_registry_entry(operator_path, "repair")]
    )

    solver = _make_solver(registry, repair=True)

    assert operator_path.stem not in solver.frozen_repair_ops
    event = solver.fallback_events[-1]
    assert event["stage"] == "security_validation"
    assert event["execution_status"] == "validation_failed"
    assert "forbidden" in event["fallback_reason"].lower()


def test_frozen_operator_is_not_imported_into_alns_main_process(
    tmp_path: Path,
) -> None:
    operator_path = tmp_path / "isolated_frozen_repair.py"
    operator_path.write_text(SUCCESS_REPAIR_CODE, encoding="utf-8")
    registry = _write_registry(
        tmp_path, repair=[_registry_entry(operator_path, "repair")]
    )
    module_name = f"frozen_operator_{operator_path.stem}"
    sys.modules.pop(module_name, None)

    try:
        solver = _make_solver(registry, repair=True)
        assert operator_path.stem in solver.frozen_repair_ops
        assert module_name not in sys.modules
    finally:
        sys.modules.pop(module_name, None)


@pytest.mark.parametrize(
    ("code", "expected_status"),
    [
        (RUNTIME_ERROR_REPAIR_CODE, "runtime_error"),
        (TIMEOUT_REPAIR_CODE, "timeout"),
    ],
    ids=["runtime-error", "timeout"],
)
def test_frozen_repair_failure_uses_fallback_and_records_distinct_status(
    tmp_path: Path, code: str, expected_status: str
) -> None:
    operator_path = tmp_path / f"frozen_{expected_status}_repair.py"
    operator_path.write_text(code, encoding="utf-8")
    registry = _write_registry(
        tmp_path, repair=[_registry_entry(operator_path, "repair")]
    )
    solver = _make_solver(registry, repair=True)
    partial, removed_tasks, partial_eval = _remove_one_task(solver)

    started = perf_counter()
    repaired = solver.repair_ops[operator_path.stem](
        partial, removed_tasks, partial_eval
    )
    elapsed = perf_counter() - started

    if expected_status == "timeout":
        assert elapsed < 1.0
    event = solver.fallback_events[-1]
    assert event["execution_status"] == expected_status
    assert event["fallback_used"] is True
    assert event["fallback_reason"]
    assert is_solution_complete(repaired, solver.instance)


@pytest.mark.parametrize(
    "code",
    [MISSING_TASK_REPAIR_CODE, DUPLICATE_TASK_REPAIR_CODE],
    ids=["missing-task", "duplicate-task"],
)
def test_frozen_repair_invalid_solution_falls_back_to_complete_unique_solution(
    tmp_path: Path, code: str
) -> None:
    operator_path = tmp_path / "invalid_contract_repair.py"
    operator_path.write_text(code, encoding="utf-8")
    registry = _write_registry(
        tmp_path, repair=[_registry_entry(operator_path, "repair")]
    )
    solver = _make_solver(registry, repair=True)
    partial, removed_tasks, partial_eval = _remove_one_task(solver)

    repaired = solver.repair_ops[operator_path.stem](
        partial, removed_tasks, partial_eval
    )

    event = solver.fallback_events[-1]
    assert event["execution_status"] == "invalid_solution"
    assert event["fallback_used"] is True
    assert is_solution_complete(repaired, solver.instance)


@pytest.mark.parametrize("mode", ["lost-task", "overlap-and-duplicate"])
def test_frozen_destroy_invalid_partition_is_rejected(
    tmp_path: Path, mode: str
) -> None:
    if mode == "lost-task":
        body = '''\
    routes = [list(route) for route in solution.routes]
    route = next(route for route in routes if route)
    route.pop()
    return DestroyResult(partial_solution=MultiRobotSolution(routes=routes), removed_tasks=[])
'''
    else:
        body = '''\
    task_id = next(task for route in solution.routes for task in route)
    return DestroyResult(partial_solution=solution, removed_tasks=[task_id, task_id])
'''
    code = (
        "from mrta_rect_coverage.core.models import MultiRobotSolution\n"
        "from mrta_rect_coverage.llm.operator_evolution.protocols import DestroyResult\n\n"
        "def destroy(solution, context, rng):\n"
        + body
    )
    operator_path = tmp_path / f"invalid_{mode}_destroy.py"
    operator_path.write_text(code, encoding="utf-8")
    registry = _write_registry(
        tmp_path, destroy=[_registry_entry(operator_path, "destroy")]
    )
    solver = _make_solver(registry, destroy=True)

    outcome = None
    if operator_path.stem in solver.frozen_destroy_ops:
        outcome = solver.destroy_ops[operator_path.stem](
            solver.initial_solution,
            solver.solution_evaluator.evaluate(solver.initial_solution),
            1,
        )

    event = solver.fallback_events[-1]
    assert event["execution_status"] == "invalid_solution"
    assert event["fallback_used"] is True
    if outcome is not None:
        partial, removed_tasks = outcome
        _assert_valid_destroy_partition(
            solver.initial_solution, partial, removed_tasks
        )


def test_frozen_invalid_solution_is_not_rewarded_as_generated_success(
    tmp_path: Path,
) -> None:
    operator_path = tmp_path / "reward_invalid_repair.py"
    operator_path.write_text(MISSING_TASK_REPAIR_CODE, encoding="utf-8")
    registry = _write_registry(
        tmp_path, repair=[_registry_entry(operator_path, "repair")]
    )
    solver = _make_solver(registry, iterations=1, repair=True)
    solver._select_operators = lambda context: (  # type: ignore[method-assign]
        "random_destroy",
        operator_path.stem,
        "test",
    )

    result = solver.solve()

    event = result.fallback_events[-1]
    history = result.iteration_history[0]
    assert event["execution_status"] == "invalid_solution"
    assert history["llm_operator_success"] is False
    assert result.operator_usage_stats["repair"][operator_path.stem].score == 0.0
    assert is_solution_complete(result.best_solution, solver.instance)


@pytest.mark.parametrize(
    ("operator_type", "broken_code"),
    [
        ("repair", RUNTIME_ERROR_REPAIR_CODE),
        (
            "destroy",
            '''\
from mrta_rect_coverage.llm.operator_evolution.protocols import DestroyResult

def destroy(solution, context, rng):
    raise RuntimeError("frozen destroy runtime failure")
''',
        ),
    ],
    ids=["repair-fallback", "destroy-fallback"],
)
def test_joint_fallback_reward_has_explicit_non_polluting_attribution(
    tmp_path: Path, operator_type: str, broken_code: str
) -> None:
    success_destroy_code = '''\
from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import DestroyResult

def destroy(solution, context, rng):
    routes = [list(route) for route in solution.routes]
    route = next(route for route in routes if route)
    removed = [route.pop()]
    return DestroyResult(partial_solution=MultiRobotSolution(routes=routes), removed_tasks=removed)
'''
    repair_path = tmp_path / "paired_repair.py"
    destroy_path = tmp_path / "paired_destroy.py"
    repair_path.write_text(
        broken_code if operator_type == "repair" else SUCCESS_REPAIR_CODE,
        encoding="utf-8",
    )
    destroy_path.write_text(
        broken_code if operator_type == "destroy" else success_destroy_code,
        encoding="utf-8",
    )
    registry = _write_registry(
        tmp_path,
        repair=[_registry_entry(repair_path, "repair")],
        destroy=[_registry_entry(destroy_path, "destroy")],
    )
    solver = _make_solver(registry, iterations=1, repair=True, destroy=True)
    solver._select_operators = lambda context: (  # type: ignore[method-assign]
        destroy_path.stem,
        repair_path.stem,
        "test",
    )

    result = solver.solve()
    history = result.iteration_history[0]
    repair_score = result.operator_usage_stats["repair"][repair_path.stem].score
    destroy_score = result.operator_usage_stats["destroy"][destroy_path.stem].score

    if history.get("attribution_ambiguous") is True:
        assert repair_score == 0.0
        assert destroy_score == 0.0
    else:
        attribution = history.get("reward_attribution")
        assert attribution == {
            operator_type: "fallback_excluded",
            ("destroy" if operator_type == "repair" else "repair"): "credited",
        }
        failed_score = repair_score if operator_type == "repair" else destroy_score
        assert failed_score == 0.0


@pytest.mark.parametrize(
    ("operator_id", "code", "timeout_ms", "failure_type", "rates"),
    [
        (
            "validation_failed",
            SYNTAX_INVALID_REPAIR_CODE,
            100.0,
            "validation_failed",
            {"error_rate": 0.0, "timeout_rate": 0.0, "invalid_solution_rate": 0.0},
        ),
        (
            "runtime_error",
            RUNTIME_ERROR_REPAIR_CODE,
            100.0,
            "runtime_error",
            {"error_rate": 1.0, "timeout_rate": 0.0, "invalid_solution_rate": 0.0},
        ),
        (
            "timeout",
            TIMEOUT_REPAIR_CODE,
            100.0,
            "timeout",
            {"error_rate": 0.0, "timeout_rate": 1.0, "invalid_solution_rate": 0.0},
        ),
        (
            "invalid_solution",
            MISSING_TASK_REPAIR_CODE,
            100.0,
            "invalid_solution",
            {"error_rate": 0.0, "timeout_rate": 0.0, "invalid_solution_rate": 1.0},
        ),
    ],
    ids=["validation-failed", "runtime-error", "timeout", "invalid-solution"],
)
def test_failure_types_are_mutually_exclusive_in_candidate_metrics(
    tmp_path: Path,
    operator_id: str,
    code: str,
    timeout_ms: float,
    failure_type: str,
    rates: dict[str, float],
) -> None:
    _, rows = _run_repair_candidates(
        tmp_path, {operator_id: code}, timeout_ms=timeout_ms
    )
    row = rows[0]

    for field, expected in rates.items():
        assert row[field] == expected
    assert row.get("failure_type") == failure_type
    breakdown = row.get("failure_type_breakdown")
    assert breakdown is not None
    assert breakdown[failure_type] == 1
    assert sum(breakdown.values()) == 1


def test_evolution_summary_preserves_failure_type_breakdown(tmp_path: Path) -> None:
    artifacts, _ = _run_repair_candidates(
        tmp_path,
        {
            "validation_failed": SYNTAX_INVALID_REPAIR_CODE,
            "runtime_error": RUNTIME_ERROR_REPAIR_CODE,
            "timeout": TIMEOUT_REPAIR_CODE,
            "invalid_solution": MISSING_TASK_REPAIR_CODE,
        },
        timeout_ms=100.0,
    )
    summary = json.loads(Path(artifacts.evolution_summary_path).read_text("utf-8"))

    assert summary.get("failure_type_breakdown") == {
        "validation_failed": 1,
        "runtime_error": 1,
        "timeout": 1,
        "invalid_solution": 1,
    }


def _assert_source_read_failure(path: Path) -> None:
    loaded = load_and_validate_candidate(
        path=path,
        operator_type="repair",
        round_id=0,
        source="test",
        description="source-read failure candidate",
    )

    validation = loaded.validation
    assert validation.failure_type == "source_read_failed"
    assert validation.validation_status != "valid"
    assert validation.execution_status != "success"
    assert validation.error_message
    assert loaded.callable_obj is None
    assert _is_eligible(
        {
            "validation_status": validation.validation_status,
            "execution_status": validation.execution_status,
            "failure_type": validation.failure_type,
        }
    ) is False


def test_missing_candidate_source_returns_source_read_failed(tmp_path: Path) -> None:
    _assert_source_read_failure(tmp_path / "missing_candidate.py")


def test_invalid_utf8_candidate_source_returns_source_read_failed(
    tmp_path: Path,
) -> None:
    path = tmp_path / "invalid_utf8_candidate.py"
    path.write_bytes(b"\xff\xfe\x00\x80")
    _assert_source_read_failure(path)


def test_candidate_source_os_read_error_returns_source_read_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "unreadable_candidate.py"
    path.write_text(SUCCESS_REPAIR_CODE, encoding="utf-8")
    original_read_text = Path.read_text

    def _fail_only_candidate(self: Path, *args, **kwargs):
        if self == path:
            raise PermissionError("simulated candidate read denial")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _fail_only_candidate)
    _assert_source_read_failure(path)


def test_candidate_output_is_captured_bounded_and_reports_wall_time(
    tmp_path: Path,
) -> None:
    assert "max_output_chars" in inspect.signature(
        execute_candidate_process
    ).parameters
    path = tmp_path / "noisy_candidate.py"
    path.write_text(
        "import warnings\n\n"
        "def repair(partial_solution, unassigned_tasks, context, rng):\n"
        "    print('stdout-marker-' + 'o' * 500)\n"
        "    warnings.warn('stderr-marker-' + 'e' * 500)\n"
        "    return 'ok'\n",
        encoding="utf-8",
    )

    outcome = execute_candidate_process(
        path=path,
        operator_type="repair",
        args=(None, [], None, None),
        timeout_ms=500.0,
        max_output_chars=64,
        expected_code_hash=_code_hash(path.read_text(encoding="utf-8")),
    )

    assert outcome.exit_code == 0
    assert "stdout-marker" in outcome.stdout
    assert "stderr-marker" in outcome.stderr
    assert len(outcome.stdout) <= 64
    assert len(outcome.stderr) <= 64
    assert outcome.stdout_truncated is True
    assert outcome.stderr_truncated is True
    assert outcome.wall_time_ms >= outcome.runtime_ms >= 0.0


def test_timeout_records_exit_code_and_wall_time(tmp_path: Path) -> None:
    path = tmp_path / "timed_out_candidate.py"
    path.write_text(
        "import time\n\n"
        "def repair(partial_solution, unassigned_tasks, context, rng):\n"
        "    time.sleep(1.0)\n"
        "    return 'late'\n",
        encoding="utf-8",
    )

    outcome = execute_candidate_process(
        path=path,
        operator_type="repair",
        args=(None, [], None, None),
        timeout_ms=50.0,
        expected_code_hash=_code_hash(path.read_text(encoding="utf-8")),
    )

    assert outcome.status == "timeout"
    assert isinstance(outcome.exit_code, int)
    assert outcome.wall_time_ms >= outcome.runtime_ms >= 0.0
