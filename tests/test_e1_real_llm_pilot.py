from __future__ import annotations

import json
import sys
import types
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.experiments.e1_real_llm_pilot import (
    E1PilotConfig,
    build_f1_feedback,
    build_f2_feedback,
    compute_exact_dp_behavior,
    load_development_instance_paths,
    run_e1_pilot,
    classify_provider_error,
)
from mrta_rect_coverage.llm.operator_evolution.schemas import GeneratedOperatorDraft
from mrta_rect_coverage.llm.operator_evolution.langchain_provider import LangChainOperatorEvolutionProvider


class _FakeProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int, str]] = []
        self.last_call_metadata = {
            "prompt_tokens": 11,
            "completion_tokens": 17,
            "total_tokens": 28,
            "latency_ms": 3.5,
            "estimated_cost": 0.001,
        }

    def generate_operator_candidates(self, prompt, n, operator_type, round_id):
        self.calls.append(("generate", round_id, prompt))
        return [self._draft(round_id, 0)]

    def revise_operator_candidates(self, prompt, previous_results, n, operator_type, round_id):
        self.calls.append(("revise", round_id, prompt))
        return [self._draft(round_id, 0)]

    @staticmethod
    def _draft(round_id: int, index: int) -> GeneratedOperatorDraft:
        code = (
            "from mrta_rect_coverage.llm.operator_evolution.protocols import RepairResult\n"
            "from mrta_rect_coverage.core.models import MultiRobotSolution\n"
            "def repair(partial_solution, unassigned_tasks, context, rng):\n"
            "    routes = [list(route) for route in partial_solution.routes]\n"
            "    for task_id in unassigned_tasks:\n"
            "        routes[0].append(task_id)\n"
            "    return RepairResult(solution=MultiRobotSolution(routes=routes), note='fake')\n"
        )
        return GeneratedOperatorDraft(
            operator_id=f"repair_r{round_id:03d}_{index:03d}",
            operator_type="repair",
            round_id=round_id,
            name="fake_repair",
            description="test fixture",
            source="fake",
            code=code,
            module_filename=f"repair_r{round_id:03d}_{index:03d}.py",
        )


def test_development_paths_are_manifest_scoped() -> None:
    root = Path(__file__).resolve().parents[1]
    paths = load_development_instance_paths(root / "manifests" / "r2-sanity-v1_development.json")
    assert len(paths) == 2
    assert all("r2_sanity" in path.as_posix() for path in paths)
    with pytest.raises(ValueError, match="development"):
        load_development_instance_paths(root / "manifests" / "r2-sanity-v1_held-out.json")


def test_exact_dp_behavior_uses_canonical_state_chain_diff() -> None:
    before = MultiRobotSolution(routes=[[1, 2], [3]])
    after = MultiRobotSolution(routes=[[2, 1], [3]])
    before_eval = type("Eval", (), {})()
    after_eval = type("Eval", (), {})()
    before_eval.route_evaluations = [
        type("Route", (), {"chosen_states": [type("State", (), {"task_id": 1, "sweep_mode": type("Mode", (), {"value": "H"})(), "entry_corner": type("Corner", (), {"value": "LB"})(), "exit_corner": type("Corner", (), {"value": "RT"})()})(), type("State", (), {"task_id": 2, "sweep_mode": type("Mode", (), {"value": "V"})(), "entry_corner": type("Corner", (), {"value": "LT"})(), "exit_corner": type("Corner", (), {"value": "RB"})()})()]},)(),
        type("Route", (), {"chosen_states": [type("State", (), {"task_id": 3, "sweep_mode": type("Mode", (), {"value": "H"})(), "entry_corner": type("Corner", (), {"value": "LB"})(), "exit_corner": type("Corner", (), {"value": "RT"})()})()]},)(),
    ]
    after_eval.route_evaluations = [
        type("Route", (), {"chosen_states": [type("State", (), {"task_id": 2, "sweep_mode": type("Mode", (), {"value": "V"})(), "entry_corner": type("Corner", (), {"value": "LT"})(), "exit_corner": type("Corner", (), {"value": "RB"})()})(), type("State", (), {"task_id": 1, "sweep_mode": type("Mode", (), {"value": "V"})(), "entry_corner": type("Corner", (), {"value": "LT"})(), "exit_corner": type("Corner", (), {"value": "RB"})()})()]},)(),
        type("Route", (), {"chosen_states": [type("State", (), {"task_id": 3, "sweep_mode": type("Mode", (), {"value": "H"})(), "entry_corner": type("Corner", (), {"value": "LB"})(), "exit_corner": type("Corner", (), {"value": "RT"})()})()]},)(),
    ]
    profile = compute_exact_dp_behavior(before, after, before_eval, after_eval)
    assert profile["dp_state_switch_fraction"] == pytest.approx(1 / 3)
    assert profile["hv_mode_switch_fraction"] == pytest.approx(1 / 3)
    assert profile["dp_cascade_count"] == 1


def test_f1_excludes_exact_dp_and_f2_includes_it() -> None:
    row = {"operator_id": "x", "avg_relative_improvement": 0.1, "success_rate": 1.0, "exact_dp_behavior": {"dp_cascade_ratio": 0.4}}
    assert "dp_cascade_ratio" not in json.dumps(build_f1_feedback([row]))
    assert "Exact-DP behavior unavailable" in build_f2_feedback([row])["behavior_diagnosis"]


def test_single_candidate_feedback_does_not_label_same_operator_weak() -> None:
    row = {"operator_id": "only", "avg_relative_improvement": 0.1, "success_rate": 1.0}
    payload = build_f1_feedback([row])
    assert [item["operator_id"] for item in payload["top_candidates"]] == ["only"]
    assert payload["weak_candidates"] == []


def test_two_candidate_feedback_has_distinct_top_and_weak() -> None:
    rows = [
        {"operator_id": "better", "avg_relative_improvement": 0.1, "success_rate": 1.0},
        {"operator_id": "worse", "avg_relative_improvement": -0.1, "success_rate": 1.0},
    ]
    payload = build_f1_feedback(rows)
    assert [item["operator_id"] for item in payload["top_candidates"]] == ["better"]
    assert [item["operator_id"] for item in payload["weak_candidates"]] == ["worse"]


def test_f2_diagnosis_selects_real_trial_and_is_noncausal() -> None:
    row = {
        "operator_id": "candidate",
        "avg_relative_improvement": 0.1,
        "success_rate": 1.0,
        "exact_dp_behavior": {"dp_state_switch_fraction": 0.25},
        "trials": [{
            "instance_id": "dev-A", "solver_seed": 0, "feasible": True,
            "baseline_makespan": 100.0, "candidate_makespan": 90.0,
            "relative_improvement": 0.1,
            "exact_dp_behavior": {
                "dp_state_switch_fraction": 0.25,
                "hv_mode_switch_fraction": 0.125,
                "dp_cascade_ratio": 0.2,
                "bottleneck_relief": 10.0,
                "travel_change": -12.0,
                "coverage_change": 2.0,
                "turning_change": 0.0,
            },
        }],
    }
    payload = build_f2_feedback([row])
    diagnosis = payload["behavior_diagnosis"]
    assert "dev-A" in diagnosis
    assert "10.000" in diagnosis
    assert "0.250" in diagnosis
    assert "may" in diagnosis.lower() or "可能" in diagnosis
    assert "caused" not in diagnosis.lower()


def test_revision_prompt_contains_evaluator_diagnosis_and_parent_performance(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    result = run_e1_pilot(
        E1PilotConfig(
            project_root=root,
            manifest_path=root / "manifests" / "r2-sanity-v1_development.json",
            output_dir=tmp_path / "e1",
            provider_name="fake",
            candidates_per_generation=1,
            solver_seeds=(0,),
        ),
        provider=_FakeProvider(),
    )
    assert result["branches"]["F2"]["feasible_count"] > 0
    prompt = (tmp_path / "e1" / "F2" / "prompts" / "round_001.txt").read_text(encoding="utf-8")
    assert "Evaluator-derived representative cases" in prompt
    assert "Parent evaluated performance:" in prompt


def test_e1_fake_provider_runs_two_round_parent_child_branches(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    result = run_e1_pilot(
        E1PilotConfig(
            project_root=root,
            manifest_path=root / "manifests" / "r2-sanity-v1_development.json",
            output_dir=tmp_path / "e1",
            provider_name="fake",
            candidates_per_generation=1,
            solver_seeds=(0,),
        ),
        provider=_FakeProvider(),
    )
    assert result["development_instance_count"] == 2
    assert (tmp_path / "e1" / "provider_config_redacted.json").exists()
    assert (tmp_path / "e1" / "budget_ledger.csv").exists()
    for mode in ("F1", "F2"):
        branch = tmp_path / "e1" / mode
        assert (branch / "lineage.jsonl").exists()
        assert (branch / "feedback_round_000.json").exists()
        assert (branch / "feedback_round_001.json").exists()
        assert "Constraints:" in (branch / "prompts" / "round_000.txt").read_text(encoding="utf-8")
        revision_prompt = (branch / "prompts" / "round_001.txt").read_text(encoding="utf-8")
        assert "def repair(partial_solution, unassigned_tasks, context, rng):" in revision_prompt
        assert "Parent source SHA-256:" in revision_prompt
        lineage = [json.loads(line) for line in (branch / "lineage.jsonl").read_text().splitlines()]
        assert any(item["generation"] == 1 and item["parent_candidate_id"] for item in lineage)
    assert result["provider_calls"] == 4
    for mode in ("F1", "F2"):
        usage = result["branches"][mode]["provider_usage"]
        assert usage["provider_call_count"] == 2
        assert usage["total_tokens"] == 56
        assert result["branches"][mode]["requested_candidate_count"] == 2
        assert "raw_response_candidate_count" in result["branches"][mode]
        trials = [json.loads(line) for line in (tmp_path / "e1" / mode / "trial_metrics.jsonl").read_text().splitlines()]
        assert trials
        assert all(
            trial["absolute_improvement"] == pytest.approx(
                trial["baseline_makespan"] - trial["candidate_makespan"]
            )
            for trial in trials if trial["feasible"]
        )


def test_e1_does_not_revise_without_evaluated_parent(tmp_path: Path) -> None:
    class InvalidProvider(_FakeProvider):
        @staticmethod
        def _draft(round_id: int, index: int) -> GeneratedOperatorDraft:
            draft = _FakeProvider._draft(round_id, index)
            draft.code = draft.code.replace("    routes =", "    getattr(context, 'missing')\n    routes =")
            return draft

    root = Path(__file__).resolve().parents[1]
    provider = InvalidProvider()
    result = run_e1_pilot(
        E1PilotConfig(
            project_root=root,
            manifest_path=root / "manifests" / "r2-sanity-v1_development.json",
            output_dir=tmp_path / "e1",
            provider_name="fake",
            candidates_per_generation=1,
            solver_seeds=(0,),
        ),
        provider=provider,
    )
    assert [call[0] for call in provider.calls] == ["generate", "generate"]
    assert result["branches"]["F1"]["provider_calls"] == 1
    assert result["branches"]["F2"]["provider_calls"] == 1
    assert not (tmp_path / "e1" / "F1" / "feedback_round_001.json").exists()


def test_resume_after_revision_disconnect_reuses_completed_generation(tmp_path: Path) -> None:
    class DisconnectProvider(_FakeProvider):
        def revise_operator_candidates(self, *args, **kwargs):
            raise ConnectionError("server disconnected")

    root = Path(__file__).resolve().parents[1]
    config = E1PilotConfig(
        project_root=root, manifest_path=root / "manifests" / "r2-sanity-v1_development.json",
        output_dir=tmp_path / "resume", provider_name="fake", candidates_per_generation=1,
        solver_seeds=(0,), modes=("F1",), max_provider_calls=2, resume=True,
    )
    with pytest.raises(ConnectionError):
        run_e1_pilot(config, provider=DisconnectProvider())
    branch = tmp_path / "resume" / "F1"
    original = (branch / "candidate_metrics.jsonl").read_text()
    provider = _FakeProvider()
    run_e1_pilot(config, provider=provider)
    assert [(call[0], call[1]) for call in provider.calls] == [("revise", 1)]
    rows = (branch / "candidate_metrics.jsonl").read_text().splitlines()
    assert rows[0] == original.strip()
    assert len(json.loads((branch / "elite_archive.json").read_text())) == 2
    provider.calls.clear()
    run_e1_pilot(config, provider=provider)
    assert provider.calls == []


def test_shared_initial_pool_reuses_exact_evaluator_evidence(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    provider = _FakeProvider()
    output = tmp_path / "shared"
    result = run_e1_pilot(E1PilotConfig(
        project_root=root, manifest_path=root / "manifests" / "r2-sanity-v1_development.json",
        output_dir=output, provider_name="fake", candidates_per_generation=1, solver_seeds=(0,),
        resume=True, shared_f1_initial_pool=True,
    ), provider=provider)
    assert len(provider.calls) == 3
    f1 = json.loads((output / "F1" / "candidate_metrics.jsonl").read_text().splitlines()[0])
    f2 = json.loads((output / "F2" / "candidate_metrics.jsonl").read_text().splitlines()[0])
    assert f1["source_hash"] == f2["source_hash"]
    assert f1["trials"] == f2["trials"]
    assert result["branches"]["F2"]["provider_usage"]["actual_successful_provider_calls"] == 1
    prompt = (output / "F2" / "prompts" / "round_001.txt").read_text(encoding="utf-8")
    assert "Evaluator-derived representative cases" in prompt


def test_e2_explicit_development_paths_and_candidate_archive(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    development = (root / "data" / "R2_T10_0.txt", root / "data" / "R2_T20_0.txt")
    result = run_e1_pilot(
        E1PilotConfig(
            project_root=root,
            manifest_path=None,
            development_instance_paths=development,
            output_dir=tmp_path / "e2",
            provider_name="fake",
            candidates_per_generation=1,
            solver_seeds=(0,),
        ),
        provider=_FakeProvider(),
    )
    assert result["development_instance_count"] == 2
    for mode in ("F1", "F2"):
        branch = tmp_path / "e2" / mode
        rows = [json.loads(line) for line in (branch / "candidate_metrics.jsonl").read_text().splitlines()]
        assert len(rows) == 2
        assert all(row["source_hash"] and row["source_path"] for row in rows)
        trials = [json.loads(line) for line in (branch / "trial_metrics.jsonl").read_text().splitlines()]
        assert all(trial["operator_id"] and trial["generation"] in (0, 1) for trial in trials)


def test_langchain_provider_records_usage_and_latency_metadata() -> None:
    class Response:
        content = "[]"
        usage_metadata = {"input_tokens": 3, "output_tokens": 5, "total_tokens": 8}
        response_metadata = {}

    class Chat:
        def invoke(self, messages):
            return Response()

    messages = types.ModuleType("langchain_core.messages")
    messages.HumanMessage = lambda content: content
    core = types.ModuleType("langchain_core")
    with patch.dict(sys.modules, {"langchain_core": core, "langchain_core.messages": messages}):
        provider = LangChainOperatorEvolutionProvider(Chat())
        provider.generate_operator_candidates("prompt", 1, "repair", 0)
    assert provider.last_call_metadata["total_tokens"] == 8
    assert provider.last_call_metadata["prompt_tokens"] == 3
    assert provider.last_call_metadata["completion_tokens"] == 5
    assert provider.last_call_metadata["latency_ms"] >= 0


def test_langchain_provider_extracts_text_blocks_and_yield_counts() -> None:
    class Response:
        content = [
            {"type": "text", "text": "[{\"name\": \"x\", \"code\": \"def repair(partial_solution, unassigned_tasks, context, rng):\\n    return None\"}]"},
            {"type": "reasoning", "text": "ignored"},
        ]
        usage_metadata = {"input_tokens": 2, "output_tokens": 4, "total_tokens": 6}
        response_metadata = {}

    class Chat:
        def invoke(self, messages):
            return Response()

    messages = types.ModuleType("langchain_core.messages")
    messages.HumanMessage = lambda content: content
    core = types.ModuleType("langchain_core")
    with patch.dict(sys.modules, {"langchain_core": core, "langchain_core.messages": messages}):
        provider = LangChainOperatorEvolutionProvider(Chat())
        drafts = provider.generate_operator_candidates("prompt", 1, "repair", 0)
    assert len(drafts) == 1
    assert provider.last_call_metadata["raw_response_candidate_count"] == 1
    assert provider.last_call_metadata["parsed_candidate_count"] == 1
    assert provider.last_call_metadata["parse_failure_count"] == 0


def test_runtime_config_reads_local_dotenv_without_python_dotenv(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".env").write_text(
        "OPERATOR_LLM_PROVIDER=langchain_openai_compatible\n"
        "OPERATOR_LLM_API_KEY=local-test-key\n"
        "OPERATOR_LLM_BASE_URL=https://example.invalid/v1\n"
        "OPERATOR_LLM_MODEL=test-model\n",
        encoding="utf-8",
    )
    clean_env = os.environ.copy()
    for name in ("OPERATOR_LLM_PROVIDER", "OPERATOR_LLM_API_KEY", "OPERATOR_LLM_BASE_URL", "OPERATOR_LLM_MODEL"):
        clean_env.pop(name, None)
    clean_env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    probe = subprocess.run(
        [sys.executable, "-c", "from mrta_rect_coverage.llm.runtime.config import load_from_env; c=load_from_env(); print(c.provider, c.model, bool(c.api_key))"],
        cwd=tmp_path,
        env=clean_env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert probe.stdout.strip() == "langchain_openai_compatible test-model True"


def test_provider_error_classification_is_specific() -> None:
    assert classify_provider_error("401 Unauthorized") == "PROVIDER_AUTH_BLOCKER"
    assert classify_provider_error("unsupported_parameter: temperature") == "PROVIDER_REQUEST_COMPATIBILITY_BLOCKER"
    assert classify_provider_error("ReadTimeout") == "PROVIDER_NETWORK_BLOCKER"
