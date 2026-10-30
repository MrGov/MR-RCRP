from __future__ import annotations

import hashlib
import json
from pathlib import Path
from time import perf_counter

import pytest

from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.heuristics.alns_solver import ALNSConfig, ALNSSolver
from mrta_rect_coverage.llm.operator_evolution.candidate_loader import (
    load_and_validate_candidate,
)
from mrta_rect_coverage.llm.operator_evolution.evolution_loop import (
    EvolutionLoopConfig,
    run_evolution_loop,
)
from mrta_rect_coverage.llm.operator_evolution.eligibility_policy import (
    build_generated_artifact_metadata,
)
from mrta_rect_coverage.llm.operator_evolution.freezing import freeze_best_operators
from mrta_rect_coverage.llm.operator_evolution.schemas import GeneratedOperatorDraft


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INSTANCE_PATH = PROJECT_ROOT / "data" / "R2_T6_0.txt"


def _repair_code(body: str) -> str:
    indented = "\n".join(f"        {line}" for line in body.splitlines())
    return f'''\
from mrta_rect_coverage.llm.operator_evolution.protocols import RepairResult

def repair(partial_solution, unassigned_tasks, context, rng):
    if False:
{indented}
    return RepairResult(solution=partial_solution)
'''


@pytest.mark.parametrize(
    "forbidden_body",
    [
        "import os",
        "import subprocess",
        "import socket",
        'open("candidate-output.txt", "w")',
        'eval("1 + 1")',
        'exec("pass")',
        '__import__("os")',
        "from pathlib import Path",
        "from urllib.request import urlopen",
        'subprocess.Popen(["echo", "unsafe"])',
        'socket.create_connection(("example.com", 80))',
    ],
    ids=[
        "import-os",
        "import-subprocess",
        "import-socket",
        "open-file",
        "eval",
        "exec",
        "dunder-import",
        "pathlib-file-access",
        "urllib-network-access",
        "subprocess-popen",
        "socket-connect",
    ],
)
def test_static_validation_rejects_dangerous_candidate_capabilities(
    tmp_path: Path, forbidden_body: str
) -> None:
    candidate_path = tmp_path / "candidate.py"
    candidate_path.write_text(_repair_code(forbidden_body), encoding="utf-8")

    loaded = load_and_validate_candidate(
        path=candidate_path,
        operator_type="repair",
        round_id=0,
        source="test",
        description="candidate containing a statically forbidden capability",
    )

    assert loaded.validation.validation_status == "invalid"
    assert "forbidden" in loaded.validation.error_message.lower()
    assert loaded.callable_obj is None


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
        raise RuntimeError("benchmark runtime failure")
    return RepairResult(solution=partial_solution)
'''

TIMEOUT_REPAIR_CODE = VALID_REPAIR_PREFIX + '''\
import time

def repair(partial_solution, unassigned_tasks, context, rng):
    if unassigned_tasks:
        time.sleep(0.5)
    routes = [list(route) for route in partial_solution.routes]
    for task_id in unassigned_tasks:
        routes[0].append(task_id)
    return RepairResult(solution=MultiRobotSolution(routes=routes))
'''

INVALID_SOLUTION_REPAIR_CODE = VALID_REPAIR_PREFIX + '''\
def repair(partial_solution, unassigned_tasks, context, rng):
    return RepairResult(solution=partial_solution)
'''

SYNTAX_INVALID_REPAIR_CODE = "def repair(:\n    pass\n"


class _CodeProvider:
    def __init__(self, candidates: dict[str, str]):
        self.candidates = candidates

    def generate_operator_candidates(self, prompt, n, operator_type, round_id):
        return [
            GeneratedOperatorDraft(
                operator_id=operator_id,
                operator_type="repair",
                round_id=round_id,
                name=operator_id,
                description="execution-boundary test candidate",
                source="test",
                code=code,
                module_filename=f"{operator_id}.py",
            )
            for operator_id, code in self.candidates.items()
        ]

    def revise_operator_candidates(
        self, prompt, previous_results, n, operator_type, round_id
    ):
        return self.generate_operator_candidates(prompt, n, operator_type, round_id)


def _run_candidates(tmp_path: Path, candidates: dict[str, str], timeout_ms: float):
    return run_evolution_loop(
        _CodeProvider(candidates),
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
        ),
    )


def test_candidate_records_distinguish_validation_and_execution_outcomes(
    tmp_path: Path,
) -> None:
    candidates = {
        "validation_failed": SYNTAX_INVALID_REPAIR_CODE,
        "runtime_error": RUNTIME_ERROR_REPAIR_CODE,
        "timed_out": TIMEOUT_REPAIR_CODE,
        "invalid_solution": INVALID_SOLUTION_REPAIR_CODE,
        "successful": SUCCESS_REPAIR_CODE,
    }
    artifacts = _run_candidates(tmp_path, candidates, timeout_ms=100.0)
    rows = json.loads(
        (tmp_path / "outputs" / "round_000_candidates.json").read_text("utf-8")
    )
    by_id = {row["operator_id"]: row for row in rows}

    assert by_id["validation_failed"]["validation_status"] == "invalid"
    assert by_id["validation_failed"]["execution_status"] == "validation_failed"
    assert by_id["runtime_error"]["validation_status"] == "valid"
    assert by_id["runtime_error"]["execution_status"] == "runtime_error"
    assert by_id["timed_out"]["execution_status"] == "timeout"
    assert by_id["invalid_solution"]["execution_status"] == "invalid_solution"
    assert by_id["successful"]["execution_status"] == "success"

    required_fields = {
        "validation_status",
        "execution_status",
        "fallback_used",
        "fallback_reason",
        "runtime_ms",
        "code_hash",
    }
    for operator_id, code in candidates.items():
        row = by_id[operator_id]
        assert required_fields <= row.keys()
        assert row["fallback_used"] is False
        assert row["fallback_reason"] == ""
        assert row["runtime_ms"] >= 0.0
        assert row["code_hash"] == hashlib.sha256(code.encode("utf-8")).hexdigest()

    # Keep the artifacts variable meaningful: records must be the loop's official output.
    assert Path(artifacts.best_operators_path).exists()


def test_benchmark_timeout_is_hard_and_recorded(tmp_path: Path) -> None:
    slow_code = TIMEOUT_REPAIR_CODE.replace("time.sleep(0.5)", "time.sleep(2.0)")

    started = perf_counter()
    _run_candidates(tmp_path, {"slow_candidate": slow_code}, timeout_ms=100.0)
    elapsed = perf_counter() - started
    row = json.loads(
        (tmp_path / "outputs" / "round_000_candidates.json").read_text("utf-8")
    )[0]

    assert elapsed < 1.0
    assert row["execution_status"] == "timeout"
    assert row["timeout_rate"] == 1.0


@pytest.mark.parametrize(
    ("operator_id", "code", "timeout_ms"),
    [
        ("invalid", SYNTAX_INVALID_REPAIR_CODE, 1000.0),
        ("error", RUNTIME_ERROR_REPAIR_CODE, 1000.0),
        ("timeout", TIMEOUT_REPAIR_CODE, 100.0),
        ("invalid_solution", INVALID_SOLUTION_REPAIR_CODE, 1000.0),
    ],
    ids=["validation-failed", "runtime-error", "timeout", "invalid-solution"],
)
def test_no_eligible_candidate_is_explicit_and_cannot_freeze(
    tmp_path: Path, operator_id: str, code: str, timeout_ms: float
) -> None:
    artifacts = _run_candidates(tmp_path, {operator_id: code}, timeout_ms=timeout_ms)
    summary = json.loads(Path(artifacts.evolution_summary_path).read_text("utf-8"))
    best = json.loads(Path(artifacts.best_operators_path).read_text("utf-8"))

    assert summary["repair_selection_status"] == "no_valid_operator"
    assert summary["best_repair_operator_id"] == ""
    assert best["repair"] == {}

    frozen = freeze_best_operators(
        project_root=PROJECT_ROOT,
        best_operators_json=Path(artifacts.best_operators_path),
        generated_root=tmp_path / "generated",
        target_dir=tmp_path / "frozen",
    )
    registry = json.loads(Path(frozen.registry_path).read_text("utf-8"))
    assert frozen.copied_files == []
    assert registry["repair"] == []


def test_frozen_runtime_fallback_is_not_credited_as_generated_success(
    tmp_path: Path,
) -> None:
    operator_path = tmp_path / "broken_repair.py"
    operator_path.write_text(RUNTIME_ERROR_REPAIR_CODE, encoding="utf-8")
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(
        json.dumps(
            {
                "repair": [
                    {
                        "name": "broken_repair",
                        "file_path": str(operator_path),
                            "code_hash": hashlib.sha256(
                                RUNTIME_ERROR_REPAIR_CODE.encode("utf-8")
                            ).hexdigest(),
                            "validation_status": "valid",
                            "execution_status": "success",
                            "failure_type": "success",
                            "safe_to_execute": True,
                            "requires_human_risk_ack": False,
                            **build_generated_artifact_metadata(
                                claimed_source_provider="test",
                                round_id=0,
                                code_hash=hashlib.sha256(
                                    RUNTIME_ERROR_REPAIR_CODE.encode("utf-8")
                                ).hexdigest(),
                            ),
                            "sandbox_level": "timeout_only",
                            "effective_sandbox_level": "timeout_only",
                            "executor_identity": "timeout_only_subprocess_v1",
                            "fallback_used": False,
                            "error_rate": 0.0,
                            "timeout_rate": 0.0,
                            "invalid_solution_rate": 0.0,
                            "validation_failed_rate": 0.0,
                            "execution_blocked_rate": 0.0,
                            "timeout_ms": 1000.0,
                        }
                ],
                "destroy": [],
            }
        ),
        encoding="utf-8",
    )
    solver = ALNSSolver(
        load_instance(INSTANCE_PATH),
        config=ALNSConfig(
            iterations=1,
            frozen_operator_registry_path=str(registry_path),
            use_frozen_repair=True,
            allow_generated_frozen_deployment=True,
            explicit_runtime_deployment_ack=True,
            runtime_authorization_source="current_runtime_config",
        ),
    )
    solver._select_operators = lambda context: (  # type: ignore[method-assign]
        "random_destroy",
        "broken_repair",
        "test",
    )

    result = solver.solve()
    history = result.iteration_history[0]
    event = result.fallback_events[0]

    assert event["fallback_used"] is True
    assert event["fallback_reason"]
    assert history["fallback_used"] is True
    assert history["fallback_reason"]
    assert history["llm_operator_success"] is False
    assert result.operator_usage_stats["repair"]["broken_repair"].score == 0.0
