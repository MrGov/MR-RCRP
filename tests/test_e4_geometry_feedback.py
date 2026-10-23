import hashlib
import json
from pathlib import Path

from mrta_rect_coverage.experiments.e1_real_llm_pilot import build_f1_feedback, build_f2g_feedback, revision_prompt
from mrta_rect_coverage.llm.operator_evolution import prompt_builder
from mrta_rect_coverage.llm.operator_evolution.feedback_builder import coverage_mode_knowledge


def example_row():
    return dict(operator_id="p", source_hash="h", avg_relative_improvement=-0.1, success_rate=1,
                trials=[dict(instance_id="R2_T10_0", solver_seed=0, feasible=True,
                    baseline_makespan=985., candidate_makespan=1071., relative_improvement=-86/985,
                    baseline_route_costs=[947.,985.], candidate_route_costs=[1071.,773.],
                    reassigned_task_count=1, exact_dp_behavior=dict(travel_change=-88., turning_change=0.,
                        coverage_change=0., dp_cascade_ratio=0.2222222222222222))])


def test_geometry_knowledge_formulas_parity_contract_and_measured_evidence():
    row=example_row()
    payload=coverage_mode_knowledge(parent=row,diagnosed_operator=row,source_reference="saved.json")
    f=payload['formulas']
    assert "ceil(task.height / context.instance.sweep_width)" in f['H']
    assert "ceil(task.width / context.instance.sweep_width)" in f['V']
    assert "(n_H - 1) * context.instance.turning_time" in f['H']
    assert "(n_V - 1) * context.instance.turning_time" in f['V']
    assert "Even H: LB->LT" in f['parity'] and "Even V: LB->RB" in f['parity']
    assert "/context.instance.travel_speed" in f['travel'] and "return travel" in f['travel']
    assert "sweep_speed" in payload['available_attributes']['instance']
    assert payload['evidence'][1]['observation']['candidate_route_costs']==[1071.,773.]
    assert payload['evidence'][1]['observation']['exact_dp_behavior']['travel_change']==-88.
    assert "saved.json" in payload['evidence'][1]['source']
    assert "Do not implement the DP recurrence" in json.dumps(payload)


def test_f2g_prompt_preserves_scalar_parent_and_actual_request_count(tmp_path):
    row=example_row()
    source="def repair(partial_solution, unassigned_tasks, context, rng):\n    pass\n"
    path=tmp_path/'parent.py'; path.write_text(source)
    row.update(source_path=str(path),source_hash=hashlib.sha256(source.encode()).hexdigest())
    payload=build_f2g_feedback([row],parent=row,diagnosed_operator=row,source_reference="record")
    scalar=build_f1_feedback([row])
    assert all(payload[k]==scalar[k] for k in ('summary','top_candidates','weak_candidates'))
    old=prompt_builder.use_rich_prompts
    try:
        prompt_builder.use_rich_prompts=True
        prompt=revision_prompt(row,payload,n=2)
    finally:
        prompt_builder.use_rich_prompts=old
    assert source in prompt and row['source_hash'] in prompt
    assert "Requested candidates: 2" in prompt and "F2-G" in prompt
    assert "No evaluator is exposed" in prompt
    assert "workload and bottleneck hints" in prompt
