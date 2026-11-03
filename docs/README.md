# Documentation Index

Read the current normative documents first. Historical plans and experiment reports remain available for provenance but do not define today's research objective or authorize work.

## Current Normative Documents

| Document | Authority |
|---|---|
| [`../README.md`](../README.md) | Project summary, runnable entry point, and reading order. |
| [`../AGENTS.md`](../AGENTS.md) | Research objective, model guardrails, engineering and data-handling expectations. |
| [`research_positioning.md`](research_positioning.md) | **Single authority for current research objective, implemented-method description, candidate contributions, and claim limits.** |
| [`program_status_and_design.md`](program_status_and_design.md) | Current code/evidence map and checked unresolved issues. Does not replace source code or raw records. |
| [`modeling_decisions.md`](modeling_decisions.md) | Current MR-RCRP mathematical model, units, and feasibility. |
| [`experiment_protocol.md`](experiment_protocol.md) | Compact current principles for fair comparisons, evidence levels, splits, and claims. |
| [`../data/README.md`](../data/README.md) | Authoritative local dataset inventory, access scope, and identity rules. |

Recommended order: README → research positioning → program status → modeling decisions → experiment protocol → data README. Consult AGENTS before code changes.

## Technical References

These documents describe a specific technical contract, model decision, or implementation and are not independent research-positioning authorities:

- [`instance_protocol.md`](instance_protocol.md), [`dataset_protocol.md`](dataset_protocol.md), [`instance_families.md`](instance_families.md): instance schema, generation protocol, and intrinsic family definitions. Read together with the current data README; their planned matrices are not all executed datasets.
- [`llm_operator_evolution_spec.md`](llm_operator_evolution_spec.md): historical operator interface specification; separate specified behavior from implementation evidence.
- [`operator_evolution.md`](operator_evolution.md): current structural population method, original-paper check, run_001 results, and legacy interfaces.
- [`RUNBOOK.md`](RUNBOOK.md): runtime commands and environment notes; historical machine paths are examples only.
- [`implementation_revision_alns_solver.md`](implementation_revision_alns_solver.md): scoped historical hash/equivalence record, not a general proof for later source revisions.
- [`statistical_analysis_plan.md`](statistical_analysis_plan.md), [`reproducibility_checklist.md`](reproducibility_checklist.md), [`final_test_lockbox_protocol.md`](final_test_lockbox_protocol.md): statistical and lockbox technical references. Proposed hypotheses/conditions require a current study-specific protocol before use.

## Experiment Records

These are immutable historical result narratives; consult each report's own code revision, configuration, inputs, seeds, and limitations. A report title or method label is not proof that its source hashes match a later experiment.

- E14: [`e14_v1_development_instrument_result.md`](e14_v1_development_instrument_result.md) — descriptive state-chain observations; informative positions are not an algorithm-gain ceiling.
- E16: [`e16_cost_penalty_ablation_result.md`](e16_cost_penalty_ablation_result.md) — negative result for the tested iteration cost penalty.
- E17: [`../outputs/e17_evidence_arms/REPORT.md`](../outputs/e17_evidence_arms/REPORT.md) — small-sample candidate-quality comparison of `F1_scalar` and `F2_dataset`; not a deployment result.
- E18/E19: [`e18_e19_deployment_freeze_result.md`](e18_e19_deployment_freeze_result.md) — frozen-source identities and small mixed deployment comparison.
- E20: [`e20_headroom_probe_result.md`](e20_headroom_probe_result.md) — tested solutions and neighborhoods only.
- E22: [`../outputs/e22_cost_aware_selection/REPORT.md`](../outputs/e22_cost_aware_selection/REPORT.md) and [`../outputs/e22_cost_aware_throughput/REPORT.md`](../outputs/e22_cost_aware_throughput/REPORT.md) — negative/inconclusive cost-aware selection and throughput evidence for their tested settings.
- E23: [`../outputs/e23_transfer_gain_ablation/REPORT.md`](../outputs/e23_transfer_gain_ablation/REPORT.md) — negative/inconclusive transfer-gain destroy result under its tested setup.
- E24: [`priced_local_search_result.md`](priced_local_search_result.md) — timing and historical A/B; current status page records an arm-configuration issue requiring qualification.
- E25: [`e25_decision_audit_result.md`](e25_decision_audit_result.md) — audit profiles and decision-credit comparison; metrics have limited operational scope.
- [`incremental_exact_pricing_result.md`](incremental_exact_pricing_result.md): exact incremental-pricing correctness/performance record.

Raw outputs under `outputs/` are not rewritten by this index. E17 candidate evidence, E18 freeze records, E19 deployment, E24/E25 outputs, and failed/negative conditions retain their original experiment identities.

## Historical Designs and Task Plans

The documents below preserve prior hypotheses, draft designs, or phase-specific instructions. They are not current defaults and do not override the current normative documents. F2 labels are stage-specific; see `research_positioning.md` for the mapping.

- Research formulations: `research_questions.md`, `research_hypotheses.md`, `paper_contribution_plan.md`, `innovation_review.md`, `llm_operator_evolution_research_plan.md`, `research_method_vNext.md`, `research_synthesis.md`.
- Superseded plans: [`archive/superseded_plans/`](archive/superseded_plans/), `operator_economics_and_plan.md`, `dp_feedback_chain_design_v0.3.md`, `task_P0prime_state_regret_instrument.md`, `task_P1_iteration_cost_penalty.md`, `task_P2_state_feedback.md`, `p2_feedback_design.md`, `ablation_plan.md`, `r4_experiment_comparison_protocol.md`.
- Dataset planning/audit history: `dataset_unification_plan.md`, `data_directory_audit.md`.
- Root logs moved intact: [`archive/root_logs/`](archive/root_logs/) contains the former `task_plan.md`, `progress.md`, and `findings.md`.
- Earlier archive history: [`archive/README.md`](archive/README.md).

## Known-Issue Register

The checked code concerns and their scope are recorded in [`program_status_and_design.md`](program_status_and_design.md). Historical explanatory material that remains useful but is not implementation evidence includes [`literature_gap_matrix.md`](literature_gap_matrix.md). `legacy_specs/` remains intact; its old interface test is a cleanup candidate only and was not changed in this documentation pass.
