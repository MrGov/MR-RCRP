# Ablation Plan

## 1. 状态与共同控制

- **状态：** Phase 5B documentation specification；全部消融尚待实现和实验验证。
- 所有 LLM ablations 以完整 independent evolution run 为重复单位。
- 同一比较内固定 provider/model/time block、candidate pool size、rounds、candidate evaluations、train/dev manifests、token/information budget、timeout、ALNS iterations、portfolio size 和 solver seeds。
- Final-test 只评价 train/dev 后冻结的 conditions；不得根据 test 结果删除或新增 ablation。
- Invalid、timeout、fallback、blocked 与 source-read/validation failures 是结果，不得从预算或分母中静默移除。

## 2. A：Multi-Round Offline Evolution 主线消融

| ID | 对照 | 干预 | 主要回答 | 固定项 |
|---|---|---|---|---|
| A1 | One-shot generation | Multi-round generation+revision | RQ2：多轮是否优于 one-shot | 总 calls/tokens、candidate evaluations、最终部署规模 |
| A2 | Multi-round no feedback | Performance/rank feedback | Feedback 是否超出“多采样”效果 | Rounds、候选数、信息长度、benchmark access |
| A3 | Performance feedback | Four-axis structured feedback | D 的结构化信息是否额外有效 | Token/information budget、feedback instances |
| A4 | Elite retention on | Without elite retention | 跨轮保留是否必要 | 每轮 parent/candidate budget、selection pressure |
| A5 | Revision on | Without revision（每轮独立重采样） | Revision lineage 是否必要 | 调用、温度、候选和评价预算 |
| A6 | Cross-instance dev evaluation | Without cross-instance dev evaluation | 多实例 dev 是否降低过拟合 | Train access、总评价数；该 arm 仍不得接触 final-test |
| A7 | Joint repair+destroy evolution | Repair-only / destroy-only | 两类算子贡献 | 固定 counterpart、trial attribution 与部署 budget |

`without cross-instance dev evaluation` 是过拟合诊断：只能使用预先指定的 train/dev 子集，不能用 final-test 替代被移除的 dev families。

## 3. C：Frozen Portfolio 消融

| ID | Conditions | 关键控制 | 主要 outcomes |
|---|---|---|---|
| C1 | Single dev-best vs score top-k | 相同 eligible pool；报告不同组件数带来的预算差异 | Makespan、variance、runtime |
| C2 | Score top-k vs behavior-diverse portfolio | 相同 `k`、quality floor、ALNS selector 和 candidate pool | Makespan、worst quantile、usage entropy |
| C3 | Random-k eligible vs behavior-diverse | 相同 `k` 和随机重复 | Diversity objective 的增量 |
| C4 | Human portfolio vs generated portfolio | 相同 `k`、operator interfaces 和 ALNS budget | Generated source 的增量 |
| C5 | Fixed/uniform portfolio vs run-local adaptive selector | 相同 frozen composition；selector 规则预注册 | Selector 贡献、runtime、stability |
| C6 | Full descriptors vs no correlation/no failure-runtime/no dedup | 每次只移除一组 descriptor | Portfolio composition 与 held-out quality |
| C7 | Mandatory state reset vs deliberately persistent diagnostic | Persistent arm 只可用于 train/dev contamination demonstration，不进入 final-test | 证明无跨 run state persistence 的必要性 |

正式 final-test portfolio 必须在每个 instance、solver seed、evolution run 和 test file 重置 selector state。任何跨 run persistence 结果都标 contaminated，不能成为性能对照。

## 4. D：Failure-Informed Revision 消融

| ID | Feedback regime | 内容 | 归因目标 |
|---|---|---|---|
| D0 | No feedback | 不提供结果信号 | 生成基线 |
| D1 | Execution-only | blocked/read/validation/runtime/timeout/execution success | 执行有效率 |
| D2 | Feasibility-only | valid/invalid + contract/missing/duplicate/malformed subtype | 可行性贡献 |
| D3 | Performance-only | fixed-baseline delta、rank、bottleneck/DP metrics | 优化质量贡献 |
| D4 | Structural-only | 冻结 rubric 下的 measurable diagnostics | 结构诊断贡献 |
| D5 | Generic/rank-only | 非结构化摘要 | 信息结构 control |
| D6 | Four-axis structured | execution + feasibility + optimization + structural | RQ7/H6 主方法 |
| D7 | Shuffled/wrong labels | 相同长度和 token 的错误映射 | 语义证据 control |

四轴分别记录且遵守 execution→feasibility→optimization precedence；execution success 不得被重命名为 generated/operator success。Structural labels 必须来自冻结、可重放的规则；人工/critic label 需报告一致性和 sensitivity。

## 5. H2：DP-Aware × Feasibility/Failure 2×2 Factorial

| Cell | DP-aware performance feedback | Feasibility/failure feedback | 解释 |
|---|---|---|---|
| F00 | Off | Off | No-factor control；可含等长度 neutral payload |
| F10 | On | Off | DP factor only |
| F01 | Off | On | Feasibility/failure factor only |
| F11 | On | On | 两因素联合 |

### 5.1 固定条件

- 相同 evaluator implementation 与调用次数；关闭的 factor 使用 masking/padding，不减少总访问或 token budget；
- 相同初始 candidate-generation budget、candidate pool、rounds 和 benchmark instances/seeds；
- 相同 provider/model/temperature/time block；
- 相同 prompt-length/token/information budget；
- 相同 selection/freezing、portfolio/ALNS deployment 和 solver budget；
- 相同 invalid/timeout/fallback 计数规则。

### 5.2 预注册 contrasts

- **H2a primary response（quality）：** 每个 scheduled evolution run 的 failure-aware held-out relative makespan improvement；按 `statistical_analysis_plan.md` 聚合，failure run 记 0。Effect scale 是 relative-improvement percentage-point difference，denominator/population 是四个 cells 的 all scheduled independent evolution runs。主效应为 `0.5*(mu_F10+mu_F11) - 0.5*(mu_F00+mu_F01)`；
- **H2b primary response（deployability）：** 每个 scheduled evolution run 是否交付 `valid deployable portfolio` 的 binary indicator。Effect scale 是 absolute risk difference（percentage points），denominator 是各 cell 的 all scheduled independent evolution runs；不得以 candidate attempts 或 successful freezes 作分母。主效应为 `0.5*(p_F01+p_F11) - 0.5*(p_F00+p_F10)`；
- **H2c interaction：** 对 H2a quality response 的 difference-in-differences `(mu_F11-mu_F10) - (mu_F01-mu_F00)`，仅 exploratory；deployability interaction 只作补充并明确标注；
- Candidate-level valid rate、invalid-solution/contract-violation rate 和 conditional complete-case quality 均为 secondary diagnostics；必须分别使用 scheduled candidate attempts、execution-success trials 或 valid portfolios 的显式分母，不能替代 H2a/H2b primary responses；
- shuffled DP/failure evidence 作为附加语义 control，不与主 factorial cells 混为第五个 factor level。

### 5.3 固定预算合同

F00/F10/F01/F11 必须具有相同 scheduled candidate budget、generation/revision rounds、train/dev family access、token/information budget、evaluator access/call count、prompt-length constraints、benchmark/solver seeds 和 timeout/retry policy。关闭 factor 只能通过预注册 masking/padding，不能减少信息载体长度或把节省的 budget 转给其他操作。

## 6. Ablation Execution Matrix

为了避免不可承受的全笛卡尔积，按预注册优先级执行：

1. H1/RQ1 主方法与 strongest non-LLM；
2. RQ2 的 one-shot/multi-round/no-feedback；
3. H6/RQ7 的 D0/D5/D6/D7；
4. H3/RQ4 的 single/top-k/behavior-diverse；
5. H2 的完整 2×2；
6. 其余 descriptor、repair/destroy 和 conditioning ablations 标 secondary/exploratory。

任何因预算删除的 arm 必须在 final-test 前整组删除并记录；不得根据 dev 上某 arm 表现差而只保留有利 comparisons。

## 7. 结果判定边界

- A 只有在等预算 multi-round 优于 one-shot/no-feedback 时才支持 revision 机制；
- C 只有在相同 `k` 下 behavior-diverse 优于 score top-k/single/random-k 时才支持 portfolio 互补性；
- D 只有在 D6 优于 generic/rank-only 且 shuffled labels 不复现收益时才支持 structured semantics；
- H2a/H2b 分别报告；F11 最优本身不证明两个主效应或交互；
- 任一结果若依赖 final-test feedback、额外 budget 或 fallback attribution 污染，标 contaminated/inconclusive。
