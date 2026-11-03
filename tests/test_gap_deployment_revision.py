"""Current gap-lineage integration, not just historical E5/E7 executors."""
import copy
import json
import random
from pathlib import Path

import pytest

from mrta_rect_coverage.experiments import operator_gap_revision as gap
from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import RepairContext


@pytest.fixture(scope="module")
def actual():
    artifact = gap.ROOT / "outputs/operator_gap_revision/batch_001/results.json"
    if not artifact.exists():
        pytest.skip("current local batch artifacts are required")
    data = json.loads(artifact.read_text(encoding="utf-8"))
    paths = [Path(data["anchor"]["path"])] + [Path(r["evaluation"]["path"]) for r in data["rounds"]]
    manifest = json.loads((gap.ROOT / "data/structural_benchmark_v1/manifest.json").read_text())
    ids = {c["instance_id"] for c in data["cases"]}
    entries = [e for e in manifest["entries"] if e["instance_id"] in ids]
    return data, paths, entries


def arguments(case, entry):
    instance = load_instance(gap.ROOT / "data/structural_benchmark_v1" / entry["path"])
    costs = list(case["partial_costs"])
    return (MultiRobotSolution(copy.deepcopy(case["partial_routes"])), list(case["removed_tasks"]),
            RepairContext(instance, costs, max(costs), max(range(len(costs)), key=costs.__getitem__)),
            random.Random(case["seed"]))


def test_replacement_trial_does_not_require_new_post_ls_gain():
    assert callable(getattr(gap, "trial_compositions", None)), "replacement proposals are missing"
    candidate = Path("child.py")
    assert gap.trial_compositions([Path("parent.py")], candidate, allow_addition=False) == {"replacement": [candidate]}
    assert gap.trial_compositions([], candidate, allow_addition=True) == {"replacement": [candidate]}


def test_current_candidate_modes_and_repeated_input_isolation(actual):
    assert callable(getattr(gap, "managed_executor", None)), "managed warm executor is missing"
    data, paths, entries = actual
    for path in paths:
        expected_hash = gap.digest(path)
        with gap.managed_executor(path, "original") as original, gap.managed_executor(
                path, "warm", reviewed_hashes=[expected_hash]) as warm:
            for index in [0, 1, 0, 3, 4, 5, 0]:
                case = data["cases"][index]
                entry = next(e for e in entries if e["instance_id"] == case["instance_id"])
                args = arguments(case, entry)
                before = copy.deepcopy(args)
                left = original.execute(args, timeout_ms=2000)
                right = warm.execute(args, timeout_ms=2000)
                assert left.status == right.status == "success"
                assert left.result == right.result
                assert args[:3] == before[:3]
                assert args[3].getstate() == before[3].getstate()
                right.result.solution.routes[0].append(-999)  # returned objects cannot leak back
            assert warm.backend.process_starts == 1
        assert warm.backend._process is None


def test_warm_requires_explicit_source_review(actual):
    assert callable(getattr(gap, "managed_executor", None)), "review gate is missing"
    with pytest.raises(ValueError, match="review"):
        with gap.managed_executor(actual[1][0], "warm", reviewed_hashes=[]):
            pass


def test_each_actual_candidate_runtime_failure_and_source_change_close_worker(actual, tmp_path):
    data, paths, entries = actual
    args = arguments(data["cases"][0], entries[0])
    for index, source in enumerate(paths):
        path = tmp_path / f"candidate_{index}.py"
        path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        with gap.managed_executor(path, "warm", reviewed_hashes=[gap.digest(path)]) as proxy:
            assert proxy.execute(args, timeout_ms=2000).status == "success"
            broken = (args[0], [-999], args[2], args[3])
            assert proxy.execute(broken, timeout_ms=2000).status == "runtime_error"
            assert proxy.backend._process is None
            assert proxy.execute(args, timeout_ms=2000).status == "success"
            path.write_text(path.read_text(encoding="utf-8") + "\n# source drift\n", encoding="utf-8")
            assert proxy.execute(args, timeout_ms=2000).status == "source_hash_mismatch"
            assert proxy.backend._process is None


@pytest.mark.parametrize("failure", ["timeout", "invalid_solution"])
def test_derived_failure_fixture_does_not_leave_worker(actual, tmp_path, failure):
    # Derived test fixtures are never archived as generated algorithm candidates.
    data, paths, entries = actual
    source = paths[2].read_text(encoding="utf-8")
    lines = source.splitlines()
    index = next(i for i, line in enumerate(lines) if line.startswith("def repair(")) + 1
    body = ("    if unassigned_tasks:\n        while True:\n            pass" if failure == "timeout" else
            "    if unassigned_tasks:\n        return RepairResult(solution=MultiRobotSolution(routes=[]))")
    lines.insert(index, body)
    path = tmp_path / "derived_failure.py"
    path.write_text("\n".join(lines), encoding="utf-8")
    with gap.managed_executor(path, "warm", reviewed_hashes=[gap.digest(path)]) as proxy:
        result = proxy.execute(arguments(data["cases"][0], entries[0]), timeout_ms=20)
        assert result.status == failure
        assert proxy.backend._process is None


def test_context_cleanup_on_early_return_and_exception(actual):
    data, paths, entries = actual
    created = []
    def early_return():
        with gap.managed_executor(paths[2], "warm", reviewed_hashes=[gap.digest(paths[2])]) as proxy:
            created.append(proxy)
            proxy.execute(arguments(data["cases"][0], entries[0]), timeout_ms=2000)
            return
    early_return()
    assert created[0].backend._process is None
    with pytest.raises(KeyboardInterrupt):
        with gap.managed_executor(paths[2], "warm", reviewed_hashes=[gap.digest(paths[2])]) as proxy:
            proxy.execute(arguments(data["cases"][0], entries[0]), timeout_ms=2000)
            raise KeyboardInterrupt
    assert proxy.backend._process is None


def test_actual_children_fixed_iteration_solver_paths_equal(actual):
    _, paths, entries = actual
    for composition in ([paths[0]], [paths[1]], [paths[2]], [paths[0], paths[2]]):
        config = {"deployment_iterations": 8, "seeds": [23],
                  "reviewed_warm_hashes": [gap.digest(p) for p in paths]}
        original = gap.deploy(composition, entries[:1], {**config, "executor": "original"})[0]
        warm = gap.deploy(composition, entries[:1], {**config, "executor": "warm"})[0]
        assert original["best_routes"] == warm["best_routes"]
        assert original["makespan"] == warm["makespan"]
        # Exact operation counts must match; measured wall times are
        # observational and cannot be bit-identical across executions.
        original_work = original["insertion_pricing_work"]
        warm_work = warm["insertion_pricing_work"]
        timed = {"table_build_seconds", "insertion_compute_seconds"}
        assert {k: v for k, v in original_work.items() if k not in timed} == {
            k: v for k, v in warm_work.items() if k not in timed
        }
        assert all(original_work[k] >= 0 and warm_work[k] >= 0 for k in timed)
        keys = ["destroy", "repair", "accepted", "accept_reason", "temperature", "best_makespan",
                "current_makespan", "repaired_routes", "refined_routes", "fallback_used", "route_dp_calls"]
        assert [[r[k] for k in keys] for r in original["history"]] == [[r[k] for k in keys] for r in warm["history"]]
        assert all(s["closed"] for s in warm["executor_statistics"].values())


def test_feedback_separates_deployed_members_from_evolution_parent(actual):
    from mrta_rect_coverage.llm.prompts.operator_revision import build_compact_gap_revision_prompt
    data, paths, _ = actual
    parent = data["rounds"][1]["evaluation"]
    lineage_parent = data["rounds"][0]["evaluation"]
    feedback = gap.compact_gap_feedback(parent, lineage_parent, [parent, lineage_parent], [], data["cases"],
                                        evidence_file="local.json", deployment_summary={"manual": 1300})
    assert feedback["current_composition"]["generated_members"] == []
    assert feedback["evolution_parent_hash"] == gap.digest(paths[2])
    assert feedback["lineage_parent_hash"] == gap.digest(paths[1])
    assert len(feedback["selected_cases"]) == 3
    assert feedback["selected_cases"][0]["rule"] == "worst_post_ls"
    assert feedback["selected_cases"][0]["instance"] == "development/BASE/R2_T10_0"
    prompt = build_compact_gap_revision_prompt(parent={"source_path": str(paths[2]), "source_hash": gap.digest(paths[2])},
                                                feedback=feedback, target="test target")
    assert prompt.count(paths[2].read_text(encoding="utf-8")) == 1
    assert "manual_paired_outcomes" not in prompt
    assert "parent_paired_outcomes" not in prompt
    assert len(prompt) < 30000


def test_deployment_exception_closes_started_workers(actual, monkeypatch):
    from contextlib import contextmanager
    _, paths, entries = actual
    created = []
    manager = gap.managed_executor
    solve = gap.ALNSSolver.solve
    @contextmanager
    def capture(*args, **kwargs):
        with manager(*args, **kwargs) as proxy:
            created.append(proxy)
            yield proxy
    def failed_solve(solver):
        name = next(n for n in solver.repair_ops if n.startswith("generated_"))
        solver._select_operators = lambda context: ("random_destroy", name, "cleanup_test")
        solve(solver)
        raise RuntimeError("injected after worker started")
    monkeypatch.setattr(gap, "managed_executor", capture)
    monkeypatch.setattr(gap.ALNSSolver, "solve", failed_solve)
    with pytest.raises(RuntimeError, match="injected"):
        gap.deploy([paths[2]], entries[:1], {"deployment_iterations": 1, "seeds": [23],
                   "executor": "warm", "reviewed_warm_hashes": [gap.digest(paths[2])]})
    assert created[0].backend.process_starts == 1
    assert created[0].closed and created[0].backend._process is None


def test_recheck_rejects_mislabeled_lineage_before_evaluation(actual, tmp_path, monkeypatch):
    from mrta_rect_coverage.experiments import operator_gap_recheck as recheck
    config = json.loads((gap.ROOT / "configs/operator_gap_recheck.json").read_text())
    config["output_dir"] = str(tmp_path / "mislabeled_run")
    config["reviewed_warm_hashes"] = list(reversed(config["reviewed_warm_hashes"]))
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config))
    def forbidden(*args, **kwargs):
        pytest.fail("mislabeled lineage reached evaluation")
    monkeypatch.setattr(recheck, "evaluate", forbidden)
    with pytest.raises(ValueError, match="frozen lineage"):
        recheck.run(path)
