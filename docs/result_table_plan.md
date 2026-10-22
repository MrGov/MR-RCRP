# Result Table Plan

## 1. 状态与共同规则

- **状态：** Phase 5B table specification；没有任何正式结果。
- 所有正式表只接受 `objective_v2_formal`、未污染 final-test manifest 和冻结 analysis script 的输出。
- 每张表同时报告 independent evolution runs、distinct families、replicates、solver seeds 和 scheduled/valid denominators。
- Smoke/demo、dev-best case、fallback-as-success 和 raw candidate-row significance 不得进入主结论。

## 2. Table 0 — Scheduled Evolution-Run Accounting

- **支持：** 主分析总体审计；所有 generated-method conditions。
- **Rows：** method condition × provider/model/time block；必要时附 evolution-run-level appendix。
- **Columns：** scheduled runs、completed generation runs、`no_valid_operator`、`validation_failed`、`execution_blocked`、`freeze_failed`、`deployment_blocked`、no deployable portfolio、portfolio not evaluable、evaluable portfolios、final-test evaluated portfolios、included in failure-aware primary analysis、included only in supplementary complete-case analysis、deployment success rate、valid portfolio rate；另列 preregistered cells、attributed-success cells、failure cells、cell failure rate、fully-attributable-family rate、run-level deployable-portfolio rate、fallback rate 和 attributed generated success rate。
- **Primary status：** 每个 `scheduled_run_id` 必须有一个互斥 primary run status；更细 failures 可作为 subtype/multi-label，但不能改变 scheduled denominator。
- **原始字段：** scheduled-run/method/evolution-run IDs、完整 preregistered cell-grid key、cell primary status/analysis value、generation/freeze/deployment/evaluation statuses、failure type/subtype、fallback、attribution、runtime authorization、portfolio manifest/hash、cost 与 contamination evidence。
- **允许结论：** generation-to-deployment funnel、主分析总体完整性和 failure rate。
- **不允许结论：** 不把 final-test evaluated 或 complete-case runs 当成 scheduled population；不从较高 completion rate直接推出 solver quality。

对通过 batch-integrity gate 的 analysis batch，`included in failure-aware primary analysis` 必须等于 scheduled runs。Localized result-artifact failures 记 0 且不得删行。Objective/input/formal-manifest/split/lockbox integrity failure 或 baseline pairing missing 分别标 contaminated/inconclusive，不产生 effect value；仍完整出现在 scheduled accounting、原因、影响范围和预注册 rerun/abandonment columns 中。Complete-case inclusion 只能是 integrity-valid primary population 的子集。

Primary status 先经过独立 integrity gate：`batch_contaminated` / `batch_inconclusive` 不与 cell failure 混用；对 integrity-valid runs 再按 pipeline 最远终止阶段记录 `generation_incomplete` → `validation_failed` / `execution_blocked` / `no_valid_operator` → `freeze_failed` → `no_deployable_portfolio` → `deployment_blocked` → `portfolio_not_evaluable` → `evaluable_portfolio`。同一 run 只能取一个 primary status；候选级混合 failures 保留为 subtype breakdown，不重复增加 run denominator。

## 3. Table 1 — Failure-Aware Main Result

- **支持：** RQ1 / H1；附 RQ2 的 one-shot secondary contrast。
- **Rows：** strongest non-LLM ALNS、one-shot LLM、multi-round no-feedback、multi-round structured-feedback single best、multi-round frozen portfolio。
- **Columns：** scheduled-run failure-aware relative improvement、95% CI、H1a statistical-superiority status、H1b practical-superiority status、`delta_MCID`、win/tie/loss families、worst quantile、cell failure/fully-attributable-family/run-level deployable-portfolio/fallback/attributed-generated-success rates、batch contaminated/inconclusive accounting、two-part endpoint、dominated sensitivity、runtime、scheduled-run/family counts。
- **原始字段：** method/evolution_run/family/replicate/solver_seed IDs、cell schedule/status/value、baseline/generated makespan、execution/feasibility/fallback/attribution、runtime、manifest hashes。
- **允许结论：** all scheduled independent evolution runs 下 H1a 的预注册 primary contrast、H1b nested practical claim 及等预算 one-shot secondary contrast。
- **不允许结论：** 不用 complete-case estimate 替代 failure-aware primary；不从单一 scale、单个 run、dev performance 或未校正多比较声称总体优越/SOTA。

### 3.1 Supplementary Table S1 — Conditional Complete-Case Quality

- 只包含成功部署且有 valid paired results 的 portfolios，明确标记 conditional/supplementary；
- 只保留 attributable valid cells；同时显示相对于全部预注册 cells、run×family groups 和 scheduled runs 的 inclusion fractions，并链接 Table 0 failure breakdown；
- 如果 S1 与 Table 1 方向或判定不同，以 Table 1 为准；S1 不支持主结论。

## 4. Table 2 — Ablation Results

- **支持：** RQ2、RQ3、RQ7 / H1 mechanism、H2、H6。
- **Rows：** one-shot/multi-round；no/performance/structured feedback；elite/revision/cross-instance-dev on/off；H2 F00/F10/F01/F11。
- **Columns：** H2a scheduled-run failure-aware relative improvement（percentage-point effect）、H2b valid-deployable-portfolio rate/risk difference、secondary valid-candidate/optimization rates及各自分母、token/evaluation budget、95% CI、multiplicity label。
- **原始字段：** ablation ID、evolution run、feedback factors/payload hash、candidate budget、tokens、validity/outcome、solver metrics。
- **允许结论：** 受控机制的增量；H2a/H2b 主效应和 exploratory H2c。
- **不允许结论：** F11 最佳不等于两个 factor 分别有效；预算不同的 arms 不作因果归因。

## 5. Table 3 — Portfolio Comparison

- **支持：** RQ4 / H3。
- **Rows：** single best、random-k、score top-k、human-k、behavior-diverse frozen portfolio；fixed vs run-local adaptive selector。
- **Columns：** `k`、makespan/relative improvement、seed/family variance、worst quantile、usage entropy、fallback、selector overhead、composition stability。
- **原始字段：** portfolio/member hashes、behavior descriptors、pairwise correlations、selector trajectory/reset evidence、usage/reward、solver results。
- **允许结论：** 在相同 pool、`k` 和 budget 下行为互补性/selector 的增量。
- **不允许结论：** 不把更多 operators、跨 run learned state 或额外 ALNS budget 的收益归于 portfolio quality。

## 6. Table 4 — Candidate Generation Quality

- **支持：** RQ2、RQ7 / H1 mechanism、H6。
- **Rows：** generation strategy/round/feedback regime；聚合单位仍为 evolution run。
- **Columns：** scheduled candidates、source-read/validation/execution rates、valid-solution rate、improved/tied/worsened rate、eligible/unique behavior count、runtime/tokens。
- **原始字段：** run/round/candidate/code/parent IDs、four-axis statuses、eligibility、behavior hash/descriptor、tokens/runtime。
- **允许结论：** 不同生成/反馈策略对候选漏斗和后续质量的影响。
- **不允许结论：** 不把 candidate rows 当独立样本；execution success 不等于 optimization success。

## 7. Table 5 — Failure Modes

- **支持：** RQ7 / H6；支撑 fail-closed validity analysis。
- **Rows：** method/feedback regime 与 evolution round。
- **Columns：** execution status breakdown、invalid subtype、optimization outcome、structural multi-label、fallback、attribution-ambiguous counts；每列附 denominator。
- **原始字段：** scheduled/executed/valid/evaluable flags、failure_type/subtype、structural labels、fallback reason、stderr/error summary。
- **允许结论：** 四轴 failure profile 与 structured revision 的局部机制效果。
- **不允许结论：** 不跨轴重复计数；validity 改善不能替代 held-out optimization evidence。

## 8. Table 6 — Cost–Quality

- **支持：** RQ6 / H5。
- **Rows：** human-only、one-shot regeneration、multi-round single best、frozen portfolio reuse；可按复用次数分层。
- **Columns：** quality floor attainment、calls/tokens/provider cost、candidate/benchmark compute、end-to-end wall time、cost-constrained quality、Pareto status、amortized cost。
- **原始字段：** provider call/token/latency/price、candidate/subprocess/benchmark/solver runtime、failure cost、deployment count、makespan。
- **允许结论：** quality-constrained cost、cost-constrained quality 和 Pareto tradeoff。
- **不允许结论：** 不直接相减 makespan 与货币；无预注册 utility 时不作主分析 break-even。

## 9. Table 7 — Generalization/Transfer within MR-RCRP

- **支持：** RQ5 / H4；H7 仅 exploratory conditioning rows。
- **Rows：** operator source/conditioning × ID small/medium、unseen large、stress distribution cells。
- **Columns：** relative improvement、transfer degradation、valid/fallback、runtime、95% CI、family/run counts。
- **原始字段：** family/size/distribution strata、split/manifest、operator lineage、conditioning features/version、solver metrics。
- **允许结论：** frozen operators 在 MR-RCRP family 内跨实例/预注册规模的复用与退化。
- **不允许结论：** 不声称跨优化问题领域迁移；不使用生成后挑选的“有利”scale。

## 10. Table 8 — Runtime Decomposition

- **支持：** RQ6 / H5；解释 performance overhead。
- **Rows：** method condition、candidate type、deployment mode、size stratum。
- **Columns：** provider latency、validation、subprocess startup/overhead、candidate runtime、DP/benchmark、ALNS/local search、end-to-end wall time、timeout counts。
- **原始字段：** timestamps/wall_time/candidate_runtime/subprocess_overhead、provider/benchmark/solver runtime、hardware/environment ID。
- **允许结论：** 成本瓶颈与 frozen reuse 的摊销结构。
- **不允许结论：** 不把 subprocess overhead 算成 candidate algorithm runtime；不同硬件结果不直接比较而无校正。

## 11. Table 9 — Lockbox Compliance Summary

- **支持：** 全部 RQ/H 的研究有效性审计。
- **Rows：** objective/data/code/prompt/operator/portfolio/statistics/runner/final-test opening controls。
- **Columns：** artifact ID/hash、freeze time、approval、preflight status、deviation、contamination status、evidence path。
- **原始字段：** all manifests/hashes、approval/audit events、exact input set、selector reset、retries/exclusions、contamination log。
- **Joint-preflight evidence：** train/dev/final-test manifest hashes、merged-record check statuses、file-identity capability、pre-registered exemption（如有）、receipt/hash、执行顺序与 downstream final-test isolation evidence。
- **允许结论：** 本次结果是否满足预注册 lockbox 和可复现合同。
- **不允许结论：** Compliance 不证明方法有效或代码是 capability-safe；缺 evidence 不得默认 pass。

## 12. Supplementary Outputs

- Per-family forest/interval plots；
- Evolution-run variability and portfolio-composition stability；
- Full four-axis transition matrices；
- Negative/null/inconclusive results；
- Budget sensitivity、provider/model/time-block diagnostics；
- Manifest deviation and contamination appendix。

Supplementary exploration 不得反向改变主表、hypothesis hierarchy 或 final-test methods。
