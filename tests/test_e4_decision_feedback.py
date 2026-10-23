from pathlib import Path
import hashlib
import json

from mrta_rect_coverage.llm.operator_evolution.feedback_builder import select_decision_knowledge
from mrta_rect_coverage.experiments.e1_real_llm_pilot import build_f1_feedback, build_f2d_feedback, revision_prompt
from mrta_rect_coverage.llm.operator_evolution import prompt_builder


def trial(name, before, after, **dp):
    return dict(instance_id=name, solver_seed=0, feasible=True,
                baseline_makespan=max(before), candidate_makespan=max(after),
                relative_improvement=1-max(after)/max(before),
                baseline_route_costs=before, candidate_route_costs=after,
                reassigned_task_count=1, exact_dp_behavior=dp)


def test_knowledge_uses_parent_failure_support_not_largest_metric():
    rows = [dict(operator_id="parent", trials=[
        trial("new_bottleneck_a", [10, 9], [8, 12], travel_change=-1000, dp_cascade_ratio=0),
        trial("new_bottleneck_b", [10, 9], [8, 11], travel_change=-10),
        trial("large_cascade", [10, 9], [11, 9], travel_change=1, dp_cascade_ratio=0.99),
        trial("improved", [10, 9], [8, 9], dp_cascade_ratio=0.9),
    ]), dict(operator_id="weak", trials=[trial("irrelevant", [10, 9], [1000, 9], travel_change=999, dp_cascade_ratio=1)])]
    result = select_decision_knowledge(rows, parent_id="parent", parent_source="", source_reference="saved.jsonl")
    assert result["primary_issue"] == "bottleneck_transfer"
    assert result["evidence"][0]["observation"]["instance_id"] == "new_bottleneck_a"
    assert "irrelevant" not in json.dumps(result)
    assert result["contrasting_improvement"]["exact_dp_behavior"]["dp_cascade_ratio"] == 0.9
    assert "not a penalty" in result["contrasting_improvement"]["interpretation"]


def test_no_failure_means_no_invented_defect():
    result = select_decision_knowledge([dict(operator_id="p", trials=[trial("good", [10], [9])])],
                                      parent_id="p", parent_source="", source_reference="record")
    assert result["primary_issue"] == "insufficient_evidence"
    assert result["evidence"] == []


def test_geometry_evidence_is_distinct_from_mode_changes_alone():
    bad = trial("turning_loss", [10, 9], [11, 9], hv_mode_switch_fraction=0.2,
                coverage_change=-1, turning_change=2)
    harmless = trial("mode_change_only", [10, 9], [11, 9], hv_mode_switch_fraction=0.9,
                     coverage_change=-3, turning_change=0)
    result = select_decision_knowledge([dict(operator_id="p", trials=[bad, dict(bad, solver_seed=1), harmless])],
                                      parent_id="p", parent_source="", source_reference="saved")
    assert result["primary_issue"] == "coverage_geometry"
    assert result["supporting_unique_failure_instances"]["coverage_geometry"] == 1
    direction = result["primary_revision_direction"]
    assert "turning_time" in direction and "external Exact-DP" in direction
    assert "no evaluator" in select_decision_knowledge(
        [dict(operator_id="p", trials=[trial("transfer", [10, 9], [8, 12])])],
        parent_id="p", parent_source="", source_reference="saved")["primary_revision_direction"]


def test_directed_prompt_contains_real_source_scalar_and_evidence(tmp_path):
    source = "def repair(partial_solution, unassigned_tasks, context, rng):\n    pass\n"
    path = tmp_path / "parent.py"
    path.write_text(source, encoding="utf-8")
    parent = dict(operator_id="p", source_path=str(path), source_hash=hashlib.sha256(source.encode()).hexdigest(),
                  avg_relative_improvement=-0.2, success_rate=1,
                  trials=[trial("measured", [10, 9], [8, 12], travel_change=1, dp_cascade_ratio=0.5)])
    feedback = build_f2d_feedback([parent], parent=parent, source_reference="real_trials.jsonl")
    scalar = build_f1_feedback([parent])
    assert all(feedback[k] == scalar[k] for k in ("summary", "top_candidates", "weak_candidates"))
    old = prompt_builder.use_rich_prompts
    try:
        prompt_builder.use_rich_prompts = True
        prompt = revision_prompt(parent, feedback, n=2)
    finally:
        prompt_builder.use_rich_prompts = old
    assert source in prompt and parent["source_hash"] in prompt
    assert '"candidate_makespan": 12' in prompt and "real_trials.jsonl" in prompt
    assert "Requested candidates: 2" in prompt
    assert "F2-D" in prompt and "not causal proof" in prompt
