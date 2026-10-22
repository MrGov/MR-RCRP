# Research Hypotheses

## 1. 共同评价规则

以下均为待实验验证的可证伪假设，不是性能结论。所有主比较采用预先固定的 generation/train、selection/dev 和 held-out final test；final test 的任何结果都不得反馈给 LLM、prompt、operator/portfolio selection 或参数调优。

### 1.1 当前数据与建模 no-go

当前只有 `R2_T6_0.txt` 与 `R2_T10_0.txt` 两个 2-robot、单 replicate 实例，只能用于 smoke/demo，不能支持 train/dev/test、统计推断或泛化。正式实验前必须冻结新的 instance families、robot/task combinations、replicates、family-level splits、seeds、exclusion 与 leakage policy。正式建模已批准 `objective_v2_formal` 的 independent `travel_speed`，但代码迁移和测试尚未完成；迁移前的 makespan 仍只解释为 `objective_v1_prototype` metric。

### 1.2 Independent experimental unit

Generated-method 的独立重复单位是一个完整 **LLM evolution run**。每个 run 绑定 provider/model/prompt variant、evolution-run seed、全部 generation rounds、candidate pool、train/dev evaluation 以及 selection/freezing result。Candidate、round、benchmark seed 和 instance 都嵌套于 evolution run 内，不得作为独立重复。

Benchmark seed 与 solver seed 只用于估计一个 frozen operator/portfolio 在给定实例上的运行方差，不能替代 independent evolution-run repetition。所有论文结果必须报告每个 condition 的独立 evolution-run 数量。

### 1.3 Hierarchy 与 primary estimand

实验层级固定为：

`method condition → independent evolution-run repetition → frozen operator/portfolio set → instance family → instance replicate → solver seed → run-level result`。

Primary analysis population 是 **all scheduled independent evolution runs**。唯一 primary estimand 是：held-out final-test instance families 上，multi-round LLM-evolved frozen operator portfolio 相比 strongest non-LLM ALNS baseline 的平均相对 makespan improvement：

`(baseline_makespan - generated_method_makespan) / baseline_makespan`。

先在 evolution run × instance family 内聚合 replicates/seeds，再以 equal family/equal scheduled-run weight 聚合；不得直接对 candidate rows 或 raw trials 聚合为主结果。`no_valid_operator`、no deployable portfolio、freeze/deployment failure/blocked、all-invalid 或 not-evaluable scheduled runs 不得删除；按统计计划的唯一 primary rule 在每个 family 记 0 relative improvement。Complete-case conditional quality 只作 supplementary。

### 1.4 Confirmatory hierarchy 与统计分析

- H1a statistical superiority 是唯一 primary confirmatory hypothesis；双侧 95% CI lower bound 必须 `> 0`。
- H1b practical superiority 是同一 estimand 的 nested claim；双侧 95% CI lower bound 必须 `> delta_MCID=0.02`。H1a 通过但 H1b 未通过时不得声称达到实践意义。
- 只有 H1a 通过预注册门槛后，才按固定顺序检验 H6、再检验 H3，作为 gate-kept secondary confirmatory。
- H2、H4、H5 为 secondary/exploratory；H7 始终为 exploratory。
- Fixed-sequence gatekeeping 之外的比较使用预注册 Holm correction 或明确标为 exploratory，避免多重比较与 winner's curse。
- Candidate-level rows不得作为独立样本。分析需用 cluster-aware CI、hierarchical/mixed-effects model 或预注册两阶段 aggregation，保留 evolution-run 与 instance-family 相关性。
- 样本数小时，bootstrap 必须同时 over independent evolution runs and instance families，不能 over raw candidates/trials。
- 共同次要指标包括 validity、各轴 failure rates、fallback、ALNS runtime、time-to-target、solver-seed 方差和成本。ALNS budget、instances、seeds、LLM call/token budget、聚合函数、置信水平、缺失处理及最小实用差异必须在打开 final test 前冻结。

### 1.5 四轴 outcome taxonomy 与分母

每个 scheduled trial 分开记录四个轴：

1. **Execution status（互斥）：** `execution_blocked`、`source_read_failed`、`validation_failed`、`runtime_error`、`timeout`、`execution_success`。
2. **Feasibility / contract validity（互斥）：** `valid_solution` 或 `invalid_solution`；后者必须有且只有一个 primary subtype：`contract_violation`、`missing_tasks`、`duplicate_tasks`、`malformed_return`。Subtype 属于 feasibility 轴，不跨轴重复计数。
3. **Optimization outcome（primary label 互斥）：** `improved_over_baseline`、`tied_baseline`、`worsened_vs_baseline`、`not_evaluable`。`no_improvement` 仅为派生指标：`tied OR worsened`。
4. **Structural diagnostics（可多标签）：** `excessive_complexity`、`degenerate_operator`、`ignores_context`、`always_fallback`、`duplicate_behavior`、`unsafe_pattern_blocked`。

Precedence 固定为 execution → feasibility → optimization：非 `execution_success` 的 trial 将 feasibility/optimization 记为 not evaluated；非 `valid_solution` 的 trial 将 optimization 记为 `not_evaluable`。`execution_success` 不等于 optimization success。

Execution rates 的分母是全部 scheduled trials；feasibility rates 的分母是 `execution_success` trials；optimization rates 的分母是 executed+valid trials；structural rates 的分母是完成相应静态/动态诊断的 candidates，并另报 eligible denominator。报告必须同时给出各分母计数，不能静默删除 invalid、timeout 或 blocked observations。

## H1a/H1b：Multi-Round Evolved Frozen Portfolio 优于最强非 LLM ALNS

**H1a primary confirmatory：** 在相同 solver budget 下，以 all scheduled independent evolution runs 为总体，多轮 LLM evolution 得到的 frozen operator portfolio 在 held-out instance families 上相对 strongest non-LLM ALNS 的 failure-aware mean relative improvement，其 95% CI lower bound `> 0`。

**H1b nested practical claim：** 同一 95% CI lower bound `> delta_MCID=0.02`。相对 one-shot LLM 的比较是机制性 secondary contrast，不替代 primary baseline contrast。

- **Independent variable：** method condition（strongest non-LLM ALNS；one-shot LLM；multi-round no-feedback；multi-round feedback/revision frozen portfolio）。
- **Dependent variables：** held-out makespan gap、成功改善实例比例、validity/fallback/timeout、跨 seed 方差、离线成本。
- **Baselines：** built-in human operators、problem-specific operators、random/template candidates、one-shot LLM、multi-round no-feedback。
- **Required ablations：** revision rounds、elite retention on/off、repair-only/destroy-only/both、等调用预算与等 token 预算、不同 candidate pool size。
- **Falsification condition：** CI lower bound `<= 0` 时 H1a 不支持；CI lower bound `<= 0.02` 时 H1b 不支持。若等预算 one-shot contrast 无优势，只能支持 frozen generated portfolio 的总体效果，不能支持 multi-round revision 机制。
- **所需数据和日志：** prompt/revision records、round/candidate IDs、code hash、elite lineage、instance/seed-level benchmark、failure breakdown、token/cost、frozen deployment/usage/reward 与污染标记。

## H2：DP-Aware 与 Feasibility Feedback 的 2×2 因子实验

H2 是 secondary/exploratory factorial analysis：Factor A 为 DP-aware performance feedback on/off；Factor B 为 feasibility/failure feedback on/off。四个 cell 固定 evaluator、candidate pool、generation/benchmark budget、rounds、model settings 及 token/information/prompt-length budget。

- **H2a：** Factor A 对 scheduled-run-level failure-aware held-out relative makespan improvement 的主效应；effect scale 为 relative-improvement percentage-point difference，population/denominator 为 all scheduled evolution runs，failure run 记 0。
- **H2b：** Factor B 对 valid deployable portfolio rate 的主效应；每个 scheduled evolution run 是一个 binary outcome，effect scale 为 absolute risk difference，denominator 为 all scheduled evolution runs。
- **H2c：** A×B 交互作用，仅作 exploratory，不因单个 cell 最优而事后宣称协同。

- **Independent variable：** 2×2 feedback factors（DP-aware performance on/off × feasibility/failure on/off）；rank-only/aggregate feedback 可作为附加 controls。
- **Primary dependent variables：** H2a 使用 scheduled-run-level failure-aware held-out relative improvement；H2b 使用 valid-deployable-portfolio indicator。Candidate validity、invalid/contract rates、bottleneck-route improvement、repair improvement、fallback 和成本均为 secondary diagnostics，并使用各自显式分母。
- **Baselines：** no feedback、rank-only、aggregate makespan-only、人工 problem-specific operator。
- **Required ablations：** 四个 factorial cells、shuffled DP/failure evidence、去除 route-cost vector/bottleneck/insertion delta、相同 token/information budget 与必要的 padding/masking。
- **Falsification condition：** H2a/H2b 对应主效应不支持预注册方向，或 shuffled evidence 产生同等效应；prompt 长度或额外 benchmark 信息解释全部收益时，相应假设不成立。
- **所需数据和日志：** DP route costs、bottleneck IDs、固定 baseline repair outcomes、per-instance/per-seed deltas、feedback payload hash、token count、contract/feasibility states 和 final solver metrics。

## H3：Behavior-Complementary Portfolio 优于 Single Best

**假设：** LLM-generated behavior-complementary frozen operator portfolio 比 single best generated operator 更稳定，并在 held-out instances 上取得更好的总体表现。

- **Independent variable：** deployment set/selection（single dev-best；score top-k；random-k；human portfolio；behavior-complementary portfolio）。
- **Dependent variables：** held-out makespan gap、跨 seed/instance 方差、worst-quantile performance、operator usage entropy、runtime 和 fallback rate。
- **Baselines：** single best、同规模 score top-k、random-k eligible、built-in/human portfolio。
- **Required ablations：** fixed portfolio size `k`；去除 outcome-correlation descriptor、geometry/scale descriptor、failure/runtime descriptor 和 dedup；固定候选池及 ALNS selector。
- **Falsification condition：** behavior-complementary portfolio 不优于 single best 或同规模 score top-k，稳定性也无改善；若收益只来自更多 operators、更高在线预算、跨 test-run selector state 或 test-driven selection，则假设不成立。
- **所需数据和日志：** candidate×instance×seed outcome matrix、behavior descriptors、pairwise correlations、portfolio manifest、在线选择/usage/reward、fallback/failure 和成本日志。

当前代码尚未实现完整行为互补 portfolio；H3 是机制与实验目标，不能描述为既有结果。

Portfolio composition、operator set 和 selector policy 必须在 train/dev 后冻结。预注册 selector 可在单个 test run 内自适应，但每个 instance、solver seed、evolution run 和 test file 都必须重置 learned state；不得跨 run 持久化或回写设计。

## H4：Generated Operators 可跨实例规模迁移

**假设：** 在 generation/train 与 dev 上冻结的 LLM-generated operators，相比人工 problem-specific operators，在未参与生成和选择的 **MR-RCRP instance families/规模**上仍具有可迁移收益。该假设不涉及跨优化问题领域复用。

- **Independent variable：** operator source（built-in/general human；problem-specific human；one-shot LLM；evolved LLM）与 test scale/geometry shift。
- **Dependent variables：** unseen-scale makespan gap、transfer degradation、有效率、fallback、runtime 和尾部风险。
- **Baselines：** built-in operators、problem-specific operators、rule-based advisor、one-shot frozen operators、within-scale control。
- **Required ablations：** repair/destroy 分开；按机器人数量、任务数、长宽比与空间密度分层；严格排除同源实例；相同 ALNS budget。
- **Falsification condition：** evolved operators 在未见规模不优于人工 controls，或相对 within-scale 的性能退化超过预设阈值；若 test 信息参与 prompt/selection，结果作废而非支持假设。
- **所需数据和日志：** split manifest、实例生成 provenance、scale/geometry strata、operator lineage/hash、per-instance/per-seed metrics、usage/fallback/failure 与 contamination audit。

## H5：Frozen Reuse 的质量—成本权衡

**Secondary/exploratory hypothesis：** 在 MR-RCRP problem family 内重复部署 frozen operators，可在预注册的质量约束或成本约束下形成优于 regeneration controls 的质量—成本 tradeoff。Makespan 与货币成本不直接相减，也不声称二者自然“抵消”。

- **Independent variable：** deployment strategy（human-only；one-shot per run；online/regenerated；offline-evolved frozen reused）与复用次数。
- **Dependent variables：** quality-constrained LLM calls/tokens/wall-time/benchmark compute；cost-constrained held-out makespan；quality–cost Pareto frontier；每实例摊销成本。
- **Baselines：** zero-LLM human operators、one-shot regeneration、允许时的 online generation control、frozen single best/portfolio。
- **Required ablations：** quality floor、fixed token/call/runtime budgets、是否计入失败候选成本、benchmark 深度、模型/价格敏感性、复用次数、single vs portfolio、缓存成本。
- **Falsification condition：** 在固定成本预算下 frozen reuse 不改善质量，且在固定质量 floor 下也不降低总成本；只排除失败/重试成本后才出现的优势不支持该假设。
- **所需数据和日志：** 每次 provider 调用的 token/latency/cost、所有候选执行/benchmark wall time、invalid/timeout 资源消耗、部署次数、solver quality/runtime 和价格假设版本。

Break-even 仅作 sensitivity analysis；必须在看 test 结果前定义共同效用函数或 willingness-to-pay、价格版本与复用次数范围，不作为 H5 主分析。

## H6：Structured Failure Feedback 优于 Rank-Only/Generic Feedback

**假设：** 将 execution、feasibility/contract、optimization outcome 和 structural diagnostics 四轴分开反馈，可比 rank-only 或 generic feedback 产生更有效的后续 candidates。

- **Independent variable：** feedback regime（none；rank-only；generic；correct structured；shuffled/wrong labels）。
- **Dependent variables：** 下一轮 execution-status rates、feasibility rates、optimization-outcome rates、structural-diagnostic rates、held-out performance、revision efficiency 和 token cost；每类 rate 使用预注册分母。
- **Baselines：** no feedback、rank-only、generic feedback、shuffled-label feedback。
- **Required ablations：** invalid-only、timeout-only、feasibility-only、performance-only、structural-only；去除 code/contract evidence；等 token/candidate/benchmark 预算。
- **Falsification condition：** correct structured feedback 不优于 generic/rank-only，或 shuffled labels 达到相同效果；若 validity 改善但 primary optimization metric 持续恶化超过预设阈值，则只能支持局部机制而非整体假设。
- **所需数据和日志：** round-to-round lineage、failure labels/evidence、prompt hash、revision diff、per-type transition matrix、validity/performance、token/cost 与结构标签规则版本。

## H7：Instance Conditioning 的探索性泛化假设

**假设：** 使用预先定义的实例与搜索状态特征进行条件化生成，可能在未见规模上优于 unconditional evolution；该假设只作为方向 B 的泛化消融。

- **Independent variable：** conditioning（none；真实 features；shuffled features；rule-based configuration）及 feature groups。
- **Dependent variables：** unseen-scale makespan、transfer degradation、validity、operator diversity、prompt/token cost。
- **Baselines：** unconditional A、rule-based conditioning、shuffled features、人工 scale-specific operators。
- **Required ablations：** robot/task count、geometry、load imbalance、stagnation feature groups逐项删除；seen/unseen scale；等 token budget。
- **Falsification condition：** 条件化在未见规模无稳定收益、只改善 seen-scale、shuffled features 同样有效，或收益被额外 token/人工调参解释。
- **所需数据和日志：** feature schema/version、feature values、split manifest、prompt/token records、operator lineage、scale-stratified metrics 与 contamination audit。

即使 H7 得到局部支持，方向 B 也只有在多规模、多 seed 和严格 held-out protocol 下稳定成立时，才可考虑从消融提升为贡献。

## 2. 假设判定与报告纪律

- 每个假设单独报告 supported、not supported、inconclusive 或 contaminated；
- invalid、timeout、fallback 和 blocked candidates 不从分母中静默删除；
- 多重比较、探索性分析和事后 subgroup 必须显式标注；
- 负结果不会被用于回写 final-test prompt 后重新宣称同一 lockbox；
- 每个结果表必须报告 independent evolution-run repetitions、instance families、replicates 和 solver seeds 的数量；
- execution success、valid solution 与 optimization improvement 分开报告，不能共用一个 success 分母；
- 新颖性判断需另行完成文献查新，实验支持不等于新颖性成立。
