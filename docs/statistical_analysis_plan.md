# Statistical Analysis Plan

## 1. 状态与分析原则

- **状态：** Phase 5B pre-registration draft；在任何 formal/final-test execution 前必须经独立 review 冻结。
- Candidate、round、instance replicate、benchmark seed 和 solver seed 不得被当作 generated-method 的独立重复。
- 所有 estimands、方向、failure denominators、multiplicity、missingness 和 contamination 规则在打开 final-test 前冻结。
- `objective_v1_prototype`、smoke/demo 和 contaminated results 不进入正式分析。

## 2. Independent Experimental Unit

Generated-method 的独立实验单位是一个完整 **LLM evolution run**，包括 provider/model/prompt variant、evolution-run seed、全部 generation/revision rounds、candidate pool、train/dev evaluations、selection 和 frozen operator/portfolio result。

同一 evolution run 内的 candidates、rounds、instance accesses 和 seeds 共享生成历史与选择压力，只能作为嵌套 observations。每个 method condition 必须报告 independent evolution-run repetitions 数量。

非 LLM baseline 没有 evolution process；通过预注册的 pseudo-run/block ID 与同一 family/replicate/solver-seed blocks 配对，不复制 baseline rows 伪造样本量。

## 3. Analysis Hierarchy

设计层级为：

`method condition → independent evolution-run repetition → frozen operator set/portfolio → instance family → instance replicate → solver seed → run-level result`。

在评估阶段，多个 evolution-run portfolios 会在相同 held-out families 上形成 crossed run×family observations。分析和 bootstrap 必须同时保留 evolution-run 与 family clustering；replicate/seed 只估计 cell 内运行方差。

## 4. Analysis Population、Failure-Aware Primary Estimand 与 H1

### 4.1 Analysis population

主分析总体是某 method condition 下 **all scheduled independent evolution runs**。每个 run 在排程时取得不可复用的 `scheduled_run_id`，无论最终是否生成、冻结、部署或评价成功，都必须进入 scheduled-run accounting 和主分析状态表。以下记录不能作为删行条件：

- `no_valid_operator`、all candidates invalid；
- no deployable portfolio、freeze failed；
- deployment blocked、runtime authorization missing；
- localized generated-result/artifact failure；
- batch-level input/manifest/lockbox contamination or inconclusive status（仍进入 scheduled accounting，但按 4.2.1 不产生 effect value）；
- portfolio not evaluable；
- 只有 fallback 可以运行，或没有 complete-case candidate/benchmark rows。

Successfully frozen portfolios、deployable operators、successful benchmark rows、valid paired results 和 complete-case candidate rows 都不是主分析 inclusion criterion。

### 4.2 Evaluation cell 与唯一 primary failure mapping

主分析的最小预注册 evaluation cell 固定为：

`cell(r,c,f,i,s) = evolution_run r × method_condition c × final_test_family f × instance_replicate i × solver_seed s`。

在打开 final-test 前，manifest 必须为每个 condition 冻结完整 cell grid。每个预注册 generated-method cell 都必须产生一个 analysis value，禁止因生成、部署或评价失败而删 cell。若该 cell 成功完成、solution 有效、未使用 fallback，且结果可明确归因于 generated operator/portfolio，则：

`delta_rcfis = (M_baseline,fis - M_generated,rcfis) / M_baseline,fis`。

正值表示 generated method 的 makespan 更低。若 generated-method cell 出现以下任一状态，其主分析值唯一映射为 `delta_rcfis = 0`：

- `timeout`；
- `invalid_solution` 或 contract/feasibility violation；
- `fallback_used`；
- `execution_blocked` 或 `deployment_blocked`；
- generated result missing；
- `localized_result_artifact_failure`：仅损坏该 cell 的 generated result/artifact，且已证明不影响 objective、输入数据、split、lockbox 或 baseline pairing；
- evaluator/runtime error；
- 没有可归因的 generated operator result，包括 `attribution_ambiguous`。

为使 localized failure accounting 互斥，同一 cell 的 primary status 使用以下 precedence：`localized_result_artifact_failure` → `deployment_blocked` → `execution_blocked` → `timeout` → `evaluator_or_runtime_error` → `invalid_solution` → `fallback_used` → `missing_result` → `no_attributed_generated_result` → `attributed_generated_success`。额外 failure evidence 可作 multi-label diagnostics，但不得重复增加分母。`execution_success`、得到 fallback makespan 或 solver 进程退出为 0 均不自动构成 `attributed_generated_success`。

这里的 `0` 是预注册的 **policy estimand**：表示 scheduled method attempt 没有交付可归因的 generated improvement；它不是物理 makespan penalty，也不声称失败 operator 与 baseline 实际等价。内置 fallback 可以保证流程健壮，但 fallback baseline 的 makespan 不得记入 generated method quality、success 或 reward。

Strongest non-LLM baseline 的同一 `(f,i,s)` pairing 必须先按预注册 budget 成功完成并形成正且有限的 denominator。若 baseline cell 在固定 infrastructure retry 后仍缺失，则该 formal batch 标为 `inconclusive`，不得选择性删 pair、以 generated failure `0` 掩盖缺失 denominator 或临时更换 baseline。

Whole-run method failure 是上述 cell rule 的退化情形：若某 scheduled run 没有 deployable/evaluable portfolio，但 objective、输入、split、lockbox 与 baseline pairing 完整，则它在全部预注册 `(c,f,i,s)` cells 上均取 `0`，而不是另设第二套规则。预注册 infrastructure retry 必须保留原事件并沿用同一 `scheduled_run_id`。

#### 4.2.1 Localized failure 与 batch integrity failure 的唯一分类

以下两类互斥；`manifest_violation` 不再作为未限定范围的分析标签：

| Class | 判定范围与示例 | 主分析动作 |
|---|---|---|
| `localized_result_artifact_failure` | 故障可证明只影响某个 generated result/operator cell：generated result/attribution missing、fallback、timeout、invalid/contract result、cell-local runtime/evaluator error、cell-local deployable-portfolio failure，或 malformed result row 且不影响输入集、objective、split、lockbox、baseline pairing | 该预注册 cell 保留并令 `delta_rcfis=0`；进入 cell failure、deployment、fallback 与 attribution denominators；不得删除 |
| `batch_integrity_contaminated` / `batch_integrity_inconclusive` | objective-version mismatch、input file/hash mismatch、manifest hash/schema failure、lockbox breach、split contamination、final-test record 出现在 train/dev、uncontrolled glob/non-manifest input、family assignment mismatch、跨 split exact-file duplicate、baseline pairing missing/unverifiable，或任何可能改变共同输入/denominator/lockbox 的故障 | 受影响的预注册 integrity unit 不赋 `delta`、不进入 primary effect estimate；保留全部 scheduled accounting 和 lockbox/integrity report，并按预注册规则 rerun 或 abandon |

唯一判定顺序是：

1. 先检查事件是否破坏或无法证明 objective、baseline denominator/pairing、input bytes/hash、manifest schema/hash、family/split assignment、allowed-input set 或 lockbox integrity；若是，按冻结的 dependency map 标记受影响的 `scheduled_run_id`、`analysis_batch_id` 或整个 formal batch 为 `contaminated`（完整性破坏/泄漏）或 `inconclusive`（例如 baseline pairing 在固定 infrastructure retry 后仍不可建立）。
2. 只有在审计证据证明故障局限于 generated result/operator cell 时，才使用 localized failure-zero mapping。
3. 无法可靠分类或无法界定影响范围时 fail closed 为 batch-level `inconclusive`/`contaminated`，不得降级为 cell failure。受影响范围必须由预先冻结的 dependency map 决定，禁止看结果后缩小污染范围。

任何 final-test integrity、反馈泄漏、split/lockbox mismatch 都是 batch contamination；baseline pairing missing/unverifiable 是 batch inconclusive。二者都不允许以 `0` 伪造可比较 effect。Failure-zero 是 scheduled generated-method delivery 的 policy estimand；batch contamination/inconclusive 是实验完整性失败，二者不得混合。Rerun 只允许遵循预注册 infrastructure rule 并保留原 scheduled/accounting record；lockbox 已污染时必须 abandon 当前 confirmatory batch 或启用未见的新 lockbox/version，不能用重跑修复。

Primary estimand `theta` 是 held-out final-test families 上、以 all scheduled independent evolution runs 为总体，multi-round LLM-evolved frozen portfolio 相比 strongest non-LLM ALNS 的平均 relative makespan improvement。

### 4.3 Complete-case 与 sensitivity 边界

- 只包含成功部署且具有 attributable valid cells 的 conditional-quality/complete-case analysis 是 supplementary，且必须报告所保留 cells、run×family groups 和 runs 占全部预注册分母的比例；
- deployment success + conditional quality 的 two-part endpoint 是 supplementary；
- 将 failure cells/runs 记为 dominated/worst-rank 是 sensitivity；
- 主分析与 complete-case/sensitivity 结论不一致时，以 failure-aware scheduled-run primary analysis 为准。

Cell-level complete-case 删除不得出现在主分析。论文必须把 deployment/failure rates 与主质量估计并列，并同时给出预注册 two-part 或 dominated sensitivity；这些 supplementary analyses 不能支持或挽救 H1 主结论。

### 4.4 H1a/H1b 与 MCID

`delta_MCID=0.02` relative improvement 是 Phase 5B 预注册的最小实践改善；只能在不接触 final-test 的 train/dev-only pilot 中经新 protocol version 预注册修改。

- **H1a statistical superiority（primary confirmatory）：** `theta` 的双侧 95% CI lower bound `> 0`；
- **H1b practical superiority（nested practical claim）：** 同一 CI lower bound `> delta_MCID=0.02`。

H1a 通过而 H1b 未通过时，只能声称 statistical superiority，不能声称提升达到预注册的实践意义。禁止使用“point estimate >= 0.02 且 CI lower > 0”替代 H1b。

## 5. Confirmatory Hierarchy 与 Multiplicity

固定顺序：

1. H1a：唯一 primary confirmatory；H1b 是同一 estimand 上的 nested practical-superiority claim；
2. 若 H1a 通过，检验 H6（structured failure feedback）；
3. 若 H6 通过，检验 H3（behavior-complementary portfolio）。

H6/H3 使用 fixed-sequence gatekeeping，不额外拆分 alpha。H2、H4、H5 是 secondary/exploratory；H7 始终 exploratory。Gatekeeping 之外的成组 hypothesis tests 使用预注册 Holm correction；未预注册 subgroup/metric 只报告 effect size/CI 并标 exploratory。

禁止从多个 providers、budgets、families 或 metrics 中选择最显著者作为主结论。Dev 用于冻结方法，不用于估计 confirmatory effect。

## 6. Estimation 与 Confidence Intervals

### 6.1 唯一 primary two-stage aggregation

1. 对通过 4.2.1 batch-integrity gate 的 analysis batch，先按 4.2 为完整预注册 cell grid 中的每个 `delta_rcfis` 赋 attributable relative improvement 或 localized policy value `0`；不存在空 cell 或 complete-case deletion。Batch-level contaminated/inconclusive integrity units 没有 `delta`，不由本聚合链补零。
2. 在每个 `run × condition × family × replicate` 内，对 **全部预注册 solver seeds** 的 cell values 取 arithmetic mean；失败记 0 的 seed 保留，seed 不增加 replicate 权重。
3. 在同一 `run × condition × family` 内，对 **全部预注册 replicates** 的 seed means 取 arithmetic mean，得到 `delta_rcf`；即使整个 family 的 cells 全部失败，其值仍为 `0`。Replicate 不增加 family 权重。
4. 对每个 scheduled `run × condition`，对 **全部预注册 final-test families** 的 `delta_rcf` 取 equal-weight arithmetic mean；每个 distinct family 权重相等，size/distribution cell 不因更多 replicates/seeds 获得额外权重。
5. 对同一 condition 的全部 scheduled independent evolution runs 取 equal-weight arithmetic mean，得到 `theta`；每个 scheduled run 权重相等。Whole-run failure 因其全部 cells 为 0 而自然得到 run mean `0`。

这条 cell mapping → seed → replicate → family → evolution-run arithmetic-mean 链是唯一 primary aggregation。Median、trimmed mean、inverse-variance weighting、只聚合 valid cells/runs 或按 raw trial 数加权只能作为 sensitivity。

Primary model/estimator 明确定义为上述 design-based two-stage equal-weight arithmetic-mean estimator；不是 mixed-effects model，也不按 candidate/trial 数或估计方差改变权重。

### 6.2 Primary CI：two-way cluster bootstrap

Primary uncertainty method 固定为 two-way cluster bootstrap：独立、等概率、有放回地重采样 scheduled evolution runs 和 distinct final-test families，使用被抽中 run×family cells 的完整预聚合值，执行 **5,000** 次 resamples，并报告 percentile two-sided 95% CI。Bootstrap RNG seed、实现版本和 analysis-script hash 必须在 final-test opening 前冻结。

不得 bootstrap raw candidates、candidate evaluations、replicates、trial rows 或 solver seeds作为独立单位。若 scheduled runs 或 distinct families 少到无法执行预注册 two-way bootstrap，或有效 bootstrap replicates 不足，H1 标为 `inconclusive`；不得查看结果后替换 CI 方法。

### 6.3 Model 与 sensitivity fallback

包含 method fixed effect、evolution-run 与 family effects 的 hierarchical/mixed-effects model 仅为预注册 sensitivity analysis。若其不收敛、奇异或诊断失败，记录 model failure 并省略该 sensitivity estimate；primary two-stage estimate 与 cluster-bootstrap CI 不受影响。若 primary bootstrap 本身失败，按 6.2 标 `inconclusive`，不临时改用 mixed model、naive CI 或 raw-row bootstrap。

### 6.4 Paired comparisons

仅当 methods 使用同一 objective、family、instance replicate、solver seed、ALNS budget 和预注册 block 时作 paired comparison。One-shot 与 multi-round 的 provider/time block 也必须可配对。缺少有效 pairing 时使用独立/clustered comparison 并明确降低精度，不强行配对。

若 H2 factorial arms 共用 evolution seed 或 provider time block，必须在 Phase 6/7 前预注册 paired-block resampling unit、block ID、缺 block 处理和 paired-block bootstrap 实现；不得在查看结果后决定是否利用配对。

## 7. Secondary Estimands

- one-shot vs multi-round 的 held-out relative improvement；
- H2a scheduled-run-level quality main effect、H2b valid-deployable-portfolio risk difference 与 exploratory H2c interaction；
- H3 single-best/score-top-k/behavior-diverse 的质量、variance 和 worst quantile；
- H4 seen/unseen-scale transfer degradation；
- H5 quality-constrained cost、cost-constrained quality 与 Pareto frontier；
- H6 下一轮 valid/evaluable rate、optimization outcome 与 revision efficiency；
- time/iteration-to-target、fallback、runtime decomposition 和 usage entropy。

每个 secondary estimand 必须指定 family/run 聚合和 multiplicity family；不能用 operator-level trial 数扩大 solver-level样本量。

### 7.1 H2 2×2 estimands

令 `mu_ab` 为 factorial cell `Fab` 按第 4/6 节计算的 all-scheduled-run failure-aware held-out relative-improvement mean，令 `p_ab` 为该 cell 中 `valid_deployable_portfolio` binary indicator 的 scheduled-run mean。

- **H2a primary response：** quality；estimand `0.5*(mu_10+mu_11)-0.5*(mu_00+mu_01)`，effect scale 为 relative-improvement percentage points。Population/denominator 是四个 cells 中全部 scheduled independent evolution runs；failure run 记 0。CI 使用与 primary quality analysis 相同的 run×family two-way cluster bootstrap。
- **H2b primary response：** deployability；estimand `0.5*(p_01+p_11)-0.5*(p_00+p_10)`，effect scale 为 absolute risk difference percentage points。Denominator 是每个 cell 的全部 scheduled independent evolution runs；不使用 candidate attempts、successful freeze 或 execution-success rows作分母。CI 对各 cell 的 scheduled runs 分层重采样。
- **H2c：** quality response 上的 interaction `(mu_11-mu_10)-(mu_01-mu_00)`，始终 exploratory；deployability interaction 只作 supplementary。
- H2a 与 H2b 构成一个预注册 secondary multiplicity family并使用 Holm correction；candidate-valid rate、invalid/contract rate、conditional quality 和 route diagnostics 是 secondary diagnostics，不替代两个 primary responses。

## 8. Four-Axis Failure Analysis

| Axis | Primary labels | Rate denominator |
|---|---|---|
| Execution | execution_blocked, source_read_failed, validation_failed, runtime_error, timeout, execution_success | 全部 scheduled trials |
| Feasibility/contract | valid_solution；invalid_solution 的 contract/missing/duplicate/malformed primary subtype | execution_success trials |
| Optimization | improved, tied, worsened, not_evaluable | executed + valid trials；not_evaluable 另报 count |
| Structural | complexity, degenerate, ignores_context, always_fallback, duplicate_behavior, unsafe_pattern_blocked | 完成对应诊断的 candidates；另报 eligible denominator |

Precedence 为 execution→feasibility→optimization。Execution success 不等于 valid solution，valid solution 不等于 improved。Fallback、blocked、invalid 和 timeout 不得从 scheduled cost/validity summaries 中删除。

## 9. Missingness、Timeout、Fallback 与 Contamination

- 算法 timeout/invalid/fallback 是 method outcome，不做“重试直到成功”；
- 只有预注册 infrastructure failure 可重试，原记录保留并用固定 replacement rule；
- 所有预注册 cells 按 4.2 进入主分析；method failure 使用 `delta_rcfis=0`，不得在 cell、family 或 run 层 complete-case 删除；
- fallback trial 不归因于 generated operator success/reward；joint repair/destroy 无法归因时标 `attribution_ambiguous`；
- localized result-artifact failure 按 4.2 记 `0`；objective/input/hash/formal-manifest/split/lockbox mismatch、non-manifest input 或 final-test feedback leakage 按 4.2.1 标 batch contaminated，baseline pairing missing/unverifiable 标 batch inconclusive，均不能进入 confirmatory effect analysis；
- Negative/null/high-variance result 不是修改 lockbox 或重新调参的理由。

## 10. Precision/Power 与 Downgrade Rule

Train/dev-only pilot 可以估计 runtime、run/family/seed variance 和 projected CI width，但不能读取、生成或推断 final-test performance。初始 planning values 是：每纳入 cell 的 distinct families 为 train/dev/final-test 4/4/8；每 family replicates 10/10/20；generated confirmatory conditions 目标 20 independent evolution runs。

在 final-test generation/lockbox 前，使用 pilot variance 或保守先验模拟 primary two-way clustered analysis。若 projected 95% CI half-width 大于 `0.02`，优先增加 distinct families 和 independent evolution runs；replicates 只用于降低 family 内噪声，不能替代 families/runs。若资源无法满足预注册 precision，研究必须降级为 pilot/exploratory，不写 confirmatory claim。

任何 sample-size 调整只能使用 train/dev pilot 或先验模拟，并按预先固定规则整组执行；不得依据 final-test geometry、effect direction 或 significance 调整。

## 11. Mandatory Reporting

每个 condition 报告：

- scheduled evolution runs 与每个 `scheduled_run_id` 的 primary status；
- independent evolution-run repetitions；
- distinct families、每 family replicates、solver seeds；
- 预注册 cell count、cell primary-status breakdown，以及 scheduled/executed/valid/evaluable counts；
- **cell failure rate** = primary status 非 `attributed_generated_success` 的 generated-method cells / 全部预注册 generated-method cells；
- **fully attributable family rate**（旧说明性名称 `family-level evaluable rate`）= 全部预注册 cells 均为 `attributed_generated_success` 的 `run × condition × family` groups / 全部预注册 `run × condition × family` groups；另报“至少一个 attributable cell”的宽松诊断，不能替代该 rate；
- **run-level deployable portfolio rate** = 有效部署预注册 generated portfolio 的 scheduled runs / 全部 scheduled runs；
- **fallback rate** = `fallback_used=True` cells / 全部预注册 generated-method cells；
- **attributed generated success rate** = `attributed_generated_success` cells / 全部预注册 generated-method cells；
- failure-aware primary effect、H1a/H1b status、95% CI、multiplicity status 与 hypothesis status；
- deployment success、valid portfolio、primary-analysis inclusion 和 supplementary complete-case inclusion counts；
- localized invalid/timeout/fallback/blocked counts，以及 batch-level contaminated/inconclusive counts、受影响的冻结 integrity unit、原因、预注册 rerun/abandonment action；
- 主结果旁并列 deployment/failure rates、two-part endpoint 和 dominated/worst-rank sensitivity；
- provider/model/time block、calls/tokens/cost 与完整 runtime；
- all exclusions/retries 和 manifest/code/config/prompt hashes。

每个 hypothesis 最终只标 `supported`、`not_supported`、`inconclusive` 或 `contaminated`。
