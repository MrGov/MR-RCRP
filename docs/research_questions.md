# Paper-Grade Research Questions

## 1. 状态与共同边界

- **状态：** Phase 5B documentation specification；尚无正式实验结果。
- **论文主线：** 可验证、可复用、fail-closed 的多轮 LLM offline operator evolution；MR-RCRP + DP-aware ALNS 是验证载体。
- **独立重复单位：** generated-method 的完整 evolution run，而不是 candidate、round、instance 或 seed。
- **复用范围：** 只讨论 MR-RCRP problem family 内跨实例、规模和运行复用，不推出跨优化问题领域复用。
- **数据边界：** 当前两个 R2 文件只限 smoke/demo；所有 RQ 都需要未来冻结的 train/dev/final-test family manifests。
- **主张边界：** 以下都是可证伪问题，不是已验证结论；final-test 结果不得反馈到 prompt、generation、selection、portfolio 或 tuning。

## 2. RQ1：Multi-Round Offline Evolution 是否优于最强非 LLM ALNS？

- **对应 hypothesis：** H1。
- **地位：** 唯一 primary confirmatory question。
- **必要数据：** 多个 independent evolution runs；冻结的 generated portfolios；held-out final-test families、replicates 和 solver seeds；strongest non-LLM ALNS 的配对结果；validity/fallback/cost 日志。
- **Baseline：** 预注册后在 dev 上确定、但不看 final-test 的 strongest non-LLM ALNS，包括 problem-specific operators/local search/advisor 的公平候选配置。
- **Ablation/control：** one-shot、multi-round no-feedback、elite retention on/off、revision on/off、repair-only/destroy-only/both、等 candidate/token/evaluation budget。
- **允许检验：** frozen portfolio 相对 strongest non-LLM baseline 的 held-out 平均相对 makespan improvement 是否超过预注册实用阈值。
- **不允许结论：** 不得由单个 best candidate、dev performance、两个 R2 smoke 实例或 raw trial rows推出 LLM 优越；也不得因此声称跨优化领域泛化。

## 3. RQ2：Multi-Round Feedback 是否优于 One-Shot Generation？

- **对应 hypothesis：** H1 的机制性 secondary contrast。
- **地位：** Secondary；不替代 RQ1/H1 的 primary baseline contrast。
- **必要数据：** 配对的 one-shot 与 multi-round evolution runs；相同 provider/model/time block；相同 candidate、token、train/dev access 和 benchmark budget；冻结后的 held-out solver results。
- **Baseline：** one-shot LLM operators、multi-round no-feedback、random/template generation。
- **Ablation/control：** rounds、revision、elite retention、feedback payload、相同最终部署 operator/portfolio size。
- **允许检验：** 在等预算条件下，多轮 feedback/revision 是否改善 frozen operator/portfolio 的 held-out quality、validity 或稳定性。
- **不允许结论：** 若 multi-round 使用更多 token、候选评价或 dev access，不得把差异归因于 feedback；优于 one-shot 也不能单独证明优于非 LLM ALNS。

## 4. RQ3：DP-Aware 与 Feasibility/Failure Feedback 是否分别有贡献？

- **对应 hypothesis：** H2a、H2b；H2c 为交互作用。
- **地位：** H2a/H2b secondary/exploratory；H2c exploratory。
- **必要数据：** 2×2 factorial 四个 cells 的独立 evolution runs、feedback payload hashes、DP route/bottleneck evidence、feasibility labels、validity 与 held-out solver outcomes。
- **Baseline：** no feedback、rank-only/aggregate makespan feedback、shuffled evidence、人工 problem-specific operators。
- **Ablation/control：** DP-aware feedback on/off × feasibility/failure feedback on/off；固定 evaluator access、candidate pool、rounds、token/information budget 和 prompt-length policy。
- **允许检验：** 两个 factor 的主效应，以及明确标为 exploratory 的交互作用。
- **不允许结论：** 不得把两个 factor 合并为一个干预后声称分别有效；也不得把更长 prompt 或更多 evaluator information 的收益归因于语义反馈。

## 5. RQ4：Frozen Operator Portfolio 是否优于 Single Best？

- **对应 hypothesis：** H3。
- **地位：** H1、H6 依次通过后才检验的 gate-kept secondary confirmatory question。
- **必要数据：** 相同 eligible candidate pool、固定 portfolio size `k`、dev behavior descriptors、portfolio manifest、operator usage/selection trajectories、held-out performance 与 seed variance。
- **Baseline：** single dev-best、同规模 score top-k、random-k eligible、human-designed portfolio。
- **Ablation/control：** performance top-k vs behavior-diverse；去除 correlation/dedup/failure-runtime descriptors；fixed selector vs 预注册 run-local adaptive selector。
- **允许检验：** behavior-complementary portfolio 在相同 `k` 和 ALNS budget 下是否改善质量、尾部风险或稳定性。
- **不允许结论：** 不得把“更多 operators”或跨 test-run 持久化 selector state 的收益写成行为互补性贡献；当前机制未实现前不得写成既有成果。

## 6. RQ5：Generated Operators 能否在 MR-RCRP 内跨实例/规模复用？

- **对应 hypothesis：** H4；方向 B/H7 只提供探索性条件化对照。
- **地位：** Secondary/exploratory。
- **必要数据：** family-level split、未参与 generation/selection 的 held-out in-distribution 与 unseen-scale families、operator lineage/hash、scale/distribution strata、配对 solver seeds。
- **Baseline：** built-in/general human、problem-specific human、rule-based advisor、one-shot frozen、within-scale control。
- **Ablation/control：** repair/destroy 分开、seen vs unseen scale、geometry/load strata、unconditional vs conditioned/shuffled features、相同 ALNS budget。
- **允许检验：** 在 MR-RCRP family 内，冻结算子跨实例或预注册未见规模的 transfer degradation 与相对收益。
- **不允许结论：** 不得声称跨优化问题领域复用；final-test features/performance 一旦参与设计，相关 transfer 结果作废而非变成支持证据。

## 7. RQ6：质量—成本权衡是否优于替代生成策略？

- **对应 hypothesis：** H5。
- **地位：** Secondary/exploratory。
- **必要数据：** provider calls/tokens/latency/cost、candidate validation/benchmark compute、invalid/timeout 成本、solver quality/runtime、部署与复用次数、价格/硬件版本。
- **Baseline：** zero-LLM human operators、one-shot regeneration、允许时的 online/regenerated control、frozen single best 与 portfolio。
- **Ablation/control：** fixed quality floor、fixed call/token/runtime budget、计入/排除失败成本的 sensitivity、复用次数、benchmark depth、价格版本。
- **允许检验：** quality-constrained cost、cost-constrained quality 与质量—成本 Pareto frontier。
- **不允许结论：** 不得直接用 makespan 抵消货币成本；未预注册共同效用或 willingness-to-pay 时不得作主分析 break-even 声明。

## 8. RQ7：Failure-Informed Revision 是否改善候选与 Portfolio？

- **对应 hypothesis：** H6。
- **地位：** H1 通过后首个 gate-kept secondary confirmatory question。
- **必要数据：** round-to-round lineage、四轴 failure records、feedback payload/hash、revision diff、下一轮 validity/optimization outcomes、portfolio eligibility 与 token cost。
- **Baseline：** no feedback、rank-only、generic feedback、shuffled/wrong labels。
- **Ablation/control：** execution-only、feasibility-only、performance-only、structural-only、four-axis structured feedback；相同 token/candidate/evaluation budget。
- **允许检验：** structured feedback 是否提高下一轮 valid candidate rate、有效 optimization outcome、revision efficiency 或最终 portfolio quality。
- **不允许结论：** execution success 不等于 feasibility 或 optimization success；validity 上升但 held-out quality 下降时，只能报告局部机制效果。

## 9. RQ—Hypothesis 层级摘要

| RQ | Hypothesis | 预注册地位 | 进入结论的最低证据 |
|---|---|---|---|
| RQ1 | H1 | Primary confirmatory | Independent evolution runs × held-out families；最强非 LLM baseline；等 solver budget |
| RQ2 | H1 secondary contrast | Secondary | One-shot/multi-round 等 token、candidate、evaluation budget |
| RQ3 | H2a/H2b/H2c | Secondary/exploratory | 完整 2×2；主效应与交互分开 |
| RQ4 | H3 | Gate-kept secondary confirmatory | H1→H6 已通过；相同 candidate pool 与 `k` |
| RQ5 | H4（H7 exploratory control） | Secondary/exploratory | Family-held-out MR-RCRP scales；无 test leakage |
| RQ6 | H5 | Secondary/exploratory | 完整成本日志；约束式 estimands/Pareto |
| RQ7 | H6 | Gate-kept secondary confirmatory | H1 已通过；正确/generic/shuffled feedback controls |

