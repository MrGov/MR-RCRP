# archive/ — 已被取代的历史文档

这里存放**仍有史料价值但不再是当前实施依据**的文档。当前唯一实施基线见 `../` 下的：

- `dp_feedback_chain_design_v0.3.md`（设计定稿）
- `p2_feedback_design.md`（P2 反馈结构，取代 v0.3 §3/§4）
- `task_P0prime_state_regret_instrument.md` / `task_P1_iteration_cost_penalty.md`（任务单）

| 文件 | 归档原因 |
| --- | --- |
| `dp_feedback_chain_design.md` | v0.1/v0.2 之前的初稿，被 v0.3 取代 |
| `dp_feedback_chain_design_v0.2_revised.md` | v0.2 修订稿，被 v0.3 取代 |
| `manifest_spec.md` | pilot 阶段 manifest schema 契约，pilot 体系已退出主流程 |
| `r3_diagnostics_report.md` | R3 诊断报告；`r3_diagnostics.py` 模块仍在用（e10b/e1），报告本身是历史快照 |
| `r3_heldout_hypotheses.md` | R3 期假设，已被 `research_hypotheses.md` 取代 |
| `closed_loop_observability_plan.md` | 闭环节观测计划，已被 e14 仪表取代 |
| `experiment_no_go_checklist.md` | 早期实验 No-Go 清单，已被 `../statistical_analysis_plan.md` 与 `../final_test_lockbox_protocol.md` 吸收 |
| `result_table_plan.md` | 早期结果表规划，已由 `../paper_contribution_plan.md` 与 e12/e13 产物取代 |
| `final_test_protocol.md` | 已被 `../final_test_lockbox_protocol.md` 取代 |
| `final_test_protocol_rootcopy.md` | 原工作区根 `docs/` 下的同名副本，去重归档 |

恢复某一文件：`git checkout HEAD -- docs/<原路径>`（已归档文件同理，路径改为 `docs/archive/<名>`）。

删除历史（2026-10-30 清理，均已 git 跟踪，可用 `git checkout HEAD -- docs/<名>` 恢复）：
`pilot_plan.md`、`pilot_execution_gate_plan.md`、`pilot_infrastructure_task_breakdown.md`、`pilot_manifest_plan.md`、`pilot_manifest_validator_spec.md`、`pilot_observability_schema.md`、`pilot_runner_receipt_spec.md`、`mock_file_pilot_test_plan.md`、`mock_file_validation_plan.md`、`phase6a_mock_file_closed_loop_plan.md`、`phase6b_implementation_plan.md`、`r5_contract_to_code_mapping.md`、`r5_mock_pipeline.md`、`r6_independent_readiness_review.md`。
