from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.heuristics.alns_solver import ALNSConfig, ALNSSolver
from mrta_rect_coverage.heuristics.local_search import run_stronger_local_search
from mrta_rect_coverage.llm.operator_evolution.candidate_loader import LoadedOperator
from mrta_rect_coverage.llm.operator_evolution.evaluator import (
    _fixed_greedy_repair,
    build_repair_benchmark_cases,
    evaluate_repair_candidates,
)
from mrta_rect_coverage.llm.operator_evolution.evolution_loop import (
    EvolutionLoopConfig,
    run_evolution_loop,
)
from mrta_rect_coverage.llm.operator_evolution.freezing import freeze_best_operators
from mrta_rect_coverage.llm.operator_evolution.mock_provider import (
    MockOperatorEvolutionProvider,
)
from mrta_rect_coverage.llm.operator_evolution.protocols import RepairResult
from mrta_rect_coverage.llm.operator_evolution.schemas import (
    GeneratedOperatorDraft,
    OperatorValidationResult,
)
from mrta_rect_coverage.llm.operator_evolution.eligibility_policy import (
    build_generated_artifact_metadata,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INSTANCE_PATH = PROJECT_ROOT / "data" / "R2_T6_0.txt"


def _loaded_repair(callable_obj) -> LoadedOperator:
    return LoadedOperator(
        validation=OperatorValidationResult(
            operator_id="candidate_repair",
            operator_type="repair",
            round_id=0,
            name="candidate_repair",
            description="test candidate",
            source="test",
            file_path="<in-memory>",
            validation_status="valid",
        ),
        callable_obj=callable_obj,
    )


def test_repair_metrics_compare_candidate_with_fixed_baseline_repair() -> None:
    case = build_repair_benchmark_cases([INSTANCE_PATH])[0]
    baseline_solution = _fixed_greedy_repair(
        case.partial_solution,
        case.removed_tasks,
        case.evaluator,
    )
    baseline_evaluation = case.evaluator.evaluate(baseline_solution)
    improved_solution, improved_evaluation = run_stronger_local_search(
        baseline_solution,
        case.evaluator,
        max_iterations=20,
    )
    assert improved_evaluation.makespan < baseline_evaluation.makespan

    def candidate(partial_solution, unassigned_tasks, context, rng):
        return RepairResult(solution=improved_solution)

    row = evaluate_repair_candidates(
        [_loaded_repair(candidate)],
        [case],
        seeds=[0],
        timeout_ms=1000,
    )[0]

    expected_delta = baseline_evaluation.makespan - improved_evaluation.makespan
    assert row["avg_makespan_delta"] == pytest.approx(expected_delta)
    assert row["avg_relative_improvement"] == pytest.approx(
        expected_delta / baseline_evaluation.makespan
    )
    assert row["success_rate"] == 1.0


class _StaticRepairProvider:
    def __init__(self, code: str):
        self.code = code

    def generate_operator_candidates(self, prompt, n, operator_type, round_id):
        return [
            GeneratedOperatorDraft(
                operator_id=f"repair_r{round_id:03d}_000",
                operator_type="repair",
                round_id=round_id,
                name="protocol_candidate",
                description="protocol test candidate",
                source="test",
                code=self.code,
                module_filename=f"repair_r{round_id:03d}_000.py",
            )
        ]

    def revise_operator_candidates(
        self, prompt, previous_results, n, operator_type, round_id
    ):
        return self.generate_operator_candidates(prompt, n, operator_type, round_id)


INVALID_REPAIR_CODE = "def repair(:\n    pass\n"
ERROR_REPAIR_CODE = """\
from mrta_rect_coverage.llm.operator_evolution.protocols import RepairResult

def repair(partial_solution, unassigned_tasks, context, rng):
    if unassigned_tasks:
        raise RuntimeError("candidate runtime failure")
    return RepairResult(solution=partial_solution)
"""
TIMEOUT_REPAIR_CODE = """\
import time
from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import RepairResult

def repair(partial_solution, unassigned_tasks, context, rng):
    if unassigned_tasks:
        time.sleep(0.02)
    routes = [list(route) for route in partial_solution.routes]
    for task_id in unassigned_tasks:
        routes[0].append(task_id)
    return RepairResult(solution=MultiRobotSolution(routes=routes))
"""


@pytest.mark.parametrize(
    ("code", "timeout_ms"),
    [
        (INVALID_REPAIR_CODE, 1000.0),
        (ERROR_REPAIR_CODE, 1000.0),
        (TIMEOUT_REPAIR_CODE, 1.0),
    ],
    ids=["invalid", "error", "timeout"],
)
def test_ineligible_candidate_is_not_selected_as_best(
    tmp_path: Path, code: str, timeout_ms: float
) -> None:
    artifacts = run_evolution_loop(
        _StaticRepairProvider(code),
        EvolutionLoopConfig(
            project_root=PROJECT_ROOT,
            generated_dir=tmp_path / "generated",
            output_dir=tmp_path / "outputs",
            round_count=1,
            repair_candidates_per_round=1,
            destroy_candidates_per_round=0,
            benchmark_instance_glob="data/R2_T6_0.txt",
            seeds=(0,),
            timeout_ms=timeout_ms,
            operator_types_to_evolve=("repair",),
        ),
    )

    summary = json.loads(Path(artifacts.evolution_summary_path).read_text("utf-8"))
    best = json.loads(Path(artifacts.best_operators_path).read_text("utf-8"))
    assert summary["best_repair_operator_id"] == ""
    assert best["repair"] == {}


def test_all_invalid_candidates_produce_no_frozen_operator(tmp_path: Path) -> None:
    generated = tmp_path / "generated"
    artifacts = run_evolution_loop(
        _StaticRepairProvider(INVALID_REPAIR_CODE),
        EvolutionLoopConfig(
            project_root=PROJECT_ROOT,
            generated_dir=generated,
            output_dir=tmp_path / "outputs",
            round_count=1,
            repair_candidates_per_round=1,
            destroy_candidates_per_round=0,
            benchmark_instance_glob="data/R2_T6_0.txt",
            seeds=(0,),
            operator_types_to_evolve=("repair",),
        ),
    )

    frozen = freeze_best_operators(
        project_root=PROJECT_ROOT,
        best_operators_json=Path(artifacts.best_operators_path),
        generated_root=generated,
        target_dir=tmp_path / "frozen",
    )
    registry = json.loads(Path(frozen.registry_path).read_text("utf-8"))
    assert frozen.copied_files == []
    assert registry["repair"] == []


class _FeedbackCapturingProvider(MockOperatorEvolutionProvider):
    def __init__(self):
        self.revision_feedback = None

    def revise_operator_candidates(
        self, prompt, previous_results, n, operator_type, round_id
    ):
        self.revision_feedback = previous_results
        return super().revise_operator_candidates(
            prompt, previous_results, n, operator_type, round_id
        )


def test_top_k_to_keep_limits_next_round_feedback(tmp_path: Path) -> None:
    provider = _FeedbackCapturingProvider()
    run_evolution_loop(
        provider,
        EvolutionLoopConfig(
            project_root=PROJECT_ROOT,
            generated_dir=tmp_path / "generated",
            output_dir=tmp_path / "outputs",
            round_count=2,
            repair_candidates_per_round=3,
            destroy_candidates_per_round=0,
            benchmark_instance_glob="data/R2_T6_0.txt",
            seeds=(0,),
            top_k_to_keep=1,
            operator_types_to_evolve=("repair",),
        ),
    )

    assert provider.revision_feedback is not None
    assert len(provider.revision_feedback["top_operators"]) == 1
    assert len(provider.revision_feedback["weak_operators"]) == 1


def test_frozen_operator_import_failure_is_recorded(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(
        json.dumps(
            {
                "repair": [
                    {
                        "name": "missing_repair",
                        "file_path": str(tmp_path / "missing.py"),
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
            iterations=0,
            frozen_operator_registry_path=str(registry_path),
            use_frozen_repair=True,
        ),
    )

    assert getattr(solver, "fallback_events", []) == [
        {
            "operator_type": "repair",
            "operator_name": "missing_repair",
            "stage": "import",
            "reason": "file_not_found",
            "fallback_used": True,
            "fallback_reason": "file_not_found",
        }
    ]


def test_frozen_operator_runtime_failure_is_recorded(tmp_path: Path) -> None:
    operator_path = tmp_path / "broken_repair.py"
    operator_path.write_text(ERROR_REPAIR_CODE, encoding="utf-8")
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(
        json.dumps(
            {
                "repair": [
                        {
                            "name": "broken_repair",
                            "file_path": str(operator_path),
                            "code_hash": hashlib.sha256(
                                ERROR_REPAIR_CODE.encode("utf-8")
                            ).hexdigest(),
                            "validation_status": "valid",
                            "execution_status": "success",
                            "failure_type": "success",
                            "safe_to_execute": True,
                            "requires_human_risk_ack": False,
                            "source_provider": "test",
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
                            **build_generated_artifact_metadata(
                                claimed_source_provider="test",
                                round_id=0,
                                code_hash=hashlib.sha256(
                                    ERROR_REPAIR_CODE.encode("utf-8")
                                ).hexdigest(),
                            ),
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
            iterations=0,
            frozen_operator_registry_path=str(registry_path),
            use_frozen_repair=True,
            use_dp_aware_insertion=True,
            allow_generated_frozen_deployment=True,
            explicit_runtime_deployment_ack=True,
            runtime_authorization_source="current_runtime_config",
        ),
    )
    partial = solver.initial_solution
    removed_task = partial.routes[0].pop()
    partial_eval = solver.solution_evaluator.evaluate(partial)

    solver.repair_ops["broken_repair"](partial, [removed_task], partial_eval)

    events = getattr(solver, "fallback_events", [])
    assert len(events) == 1
    assert events[0]["operator_type"] == "repair"
    assert events[0]["operator_name"] == "broken_repair"
    assert events[0]["stage"] == "runtime"
    assert "candidate runtime failure" in events[0]["reason"]
