# LLM Operator Evolution Research Plan

## 1. 研究目标与边界

本文研究对象是一种用于组合优化的、可验证且可复用的 **LLM 辅助离线算子演化框架**。LLM 不直接输出 MR-RCRP 的最终任务分配解，而是在离线阶段生成、批评和修订 ALNS destroy/repair operators。候选代码经过 fail-closed 的验证、评价、选择和冻结流程后，才可能成为在线搜索可复用的组件。

MR-RCRP 与 DP-aware ALNS 是严格验证载体：ALNS 负责组合搜索，route DP 对固定任务序列进行 problem-aware 精确评价。基础算子、problem-specific operators 与 rule-based advisor 是 baseline、control、ablation 和 scaffold，不是论文主创新。

本计划中的 reusable 仅指 frozen operators 在 MR-RCRP problem family 内跨实例、规模和运行复用。AI-for-Optimization 是研究社区定位；没有第二个优化问题实验时，不提出 cross-domain empirical reuse claim。

所有关于性能、泛化、稳定性和成本收益的表述均为待验证假设。本计划不主张已完成文献查新，也不主张真实 LLM 已经有效。

## 2. 核心研究问题

- **RQ1：** 在相同 LLM 调用、token 和 benchmark 预算下，多轮生成—反馈—修订是否优于 one-shot operator generation？
- **RQ2：** DP-aware、feasibility-aware 和 failure-type-aware 的反馈是否比总体 makespan 排名提供更有效的修订信号？
- **RQ3：** 基于行为互补性选择的 frozen portfolio 是否比 single best 或纯性能 top-k 更稳定、更易跨实例复用？
- **RQ4：** frozen operators 能否在未参与生成、反馈和选择的 held-out instances 与未见规模上保持收益？
- **RQ5：** 离线生成和评价成本能否通过重复部署得到摊销，且不被 invalid、timeout 或 fallback 污染？

## 3. 组件的正式角色

| 组件 | 正式角色 | 不承担的角色 |
|---|---|---|
| LLM | offline operator generator、reviser、critic | 不直接求解，不在 final test 在线调用 |
| ALNS | 执行 destroy/repair/local-search 组合搜索与在线低成本选择 | 不为 LLM 结论提供无控制的混合归因 |
| Route DP | 对固定任务序列精确选择覆盖状态链并计算路线代价 | 不决定任务分配或任务顺序 |
| Feasibility/contract gate | 验证任务恰好一次、repair/destroy 合同和结果结构 | 不替代性能评价 |
| Eligibility/benchmark/freeze gate | 将候选代码转化为可审计、可复用的搜索组件 | 不是完整 capability sandbox |

当前执行边界是 timeout-limited subprocess，不隔离 CPU、内存、文件系统、网络、环境变量或后代进程树。因此 fail-closed protocol 是可信实验的支撑机制，不应被表述为完整安全沙箱。

### 3.1 独立实验单位

Generated-method 的独立重复单位是一个**完整 LLM evolution run**，而不是 candidate、round、benchmark seed 或 instance。一个 evolution run 至少绑定：

- provider、model、prompt variant 与运行时配置；
- 独立 evolution-run seed；
- 全部 candidate-generation rounds 与 candidate pool；
- generation/train 和 selection/dev evaluations；
- 最终 selection/freezing result，包括 single operator 或 portfolio manifest。

同一 evolution run 内的 candidates、rounds、benchmark seeds、instances 和 solver runs 共享生成历史与选择压力，必须视为嵌套相关 observations。Benchmark seed 与 solver seed 只估计某个 frozen operator/set 在实例上的运行方差，不能替代独立 evolution-run repetitions。

### 3.2 实验层级

预注册分析按以下层级组织：

`method condition → independent evolution-run repetition → frozen operator/portfolio set → instance family → instance replicate → solver seed → run-level result`。

人工 baseline 没有 LLM evolution run 时，必须通过预先固定的 pseudo-block/run ID 与相同 instance-family/solver-seed blocks 配对，不能通过复制 candidate rows 人为增加样本量。

### 3.3 Primary estimand

唯一 primary estimand 是：在 held-out final-test instance families 上，**multi-round LLM-evolved frozen operator portfolio 相比 strongest non-LLM ALNS baseline 的平均相对 makespan improvement**。相对改善方向固定为：

`(baseline_makespan - generated_method_makespan) / baseline_makespan`。

先在每个 independent evolution run × held-out instance family 内按预注册 replicate/solver-seed 规则聚合，再跨 evolution runs 与 instance families 估计总体效应。不得按 candidate rows 或 raw trials 直接求总体均值。

## 4. 数据分区与信息流

### 4.1 当前数据限制

当前仓库只有 `R2_T6_0.txt` 与 `R2_T10_0.txt` 两个 2-robot、单 replicate 实例。它们只允许用于 smoke/demo、接口与确定性检查；不能支持 train/dev/test、统计显著性、跨规模泛化、真实 LLM 有效性或优于 baseline 的论文结论。不得把两个文件硬拆成三组。

此外，travel cost 未除以 speed、processing time 除以 speed 的单位问题是正式实验的 blocking modeling decision。在固定 `speed=1` 或统一单位前，makespan 仅为当前模型下的 prototype metric。

### 4.2 实例协议冻结

任何实验开始前，必须先冻结并版本化：instance generation rules、included instance families、robot/task combinations、每 family replicate 数、random seeds、exclusion criteria、data-leakage policy 以及 train/dev/final-test manifests。拆分必须按 instance family、规模或生成族分组，不能随机拆 raw files。

在任何真实 LLM 运行前，实例必须按清单固定为三个互斥集合：

1. **Generation/train：** 可用于候选生成、失败反馈和多轮修订。
2. **Selection/dev：** 可用于候选排名、portfolio 构造、停止规则和预先声明的超参数选择，不回写为逐实例 prompt answer。
3. **Final test lockbox：** 只在方法、prompt、预算、选择规则和统计方案冻结后进行一次性评价。

final test 的 makespan、失败案例、实例特征、算子选择轨迹和成本不得反馈给 LLM、prompt、elite selection、portfolio selection 或参数调优。任何发生此类回流的运行必须标为 contaminated，不进入主结果。最终测试实例也不得用于设计 feature schema 或 failure taxonomy。

当前默认 glob 会覆盖 `data/R*_T*_*.txt`，尚未实现上述物理/清单隔离。正式实验必须显式覆盖默认 glob，只从冻结 split manifest 读取对应集合，并在运行前验证 final-test IDs 不在 generation/dev 输入中。本阶段不修改 config 或 data。

### 4.3 Final-test selector state

Portfolio composition、operator set、selector algorithm 和初始参数必须在 train/dev 后冻结。允许预注册 adaptive selector 在单个 test run 内使用该 run 的 search history 更新 weights；每个 instance、solver seed、independent evolution run 和 test file 开始时必须重置 learned state。禁止跨这些边界持久化 selector state，也禁止把 final-test performance/trajectory 回写 prompt、portfolio、operator set、hyperparameters 或 future test runs。Final test 完成后只允许报告。

## 5. 主线 A：多轮 Offline Operator Evolution

### 5.1 计划生命周期

1. generation：按固定接口生成 repair/destroy source；
2. source read 与静态 validation；
3. timeout-only 隔离 smoke execution；
4. benchmark evaluation；
5. eligibility gating；
6. ranking 与 explicit elite retention；
7. failure/performance feedback；
8. revision；
9. 多轮重复并冻结候选；
10. 在 ALNS 中部署 frozen single operator 或 portfolio。

当前代码已经具备 generation/revision、基本 benchmark、failure metrics、best selection 和 freezing/deployment gate；尚缺真正的跨轮 top-k code retention、behavioral diversity、完整 portfolio 和锁定的数据分区。论文不得把这些计划机制写成已实现事实。

### 5.2 公平预算

one-shot 与 multi-round 必须控制：

- 每类算子的 LLM 调用数与总 token；
- generation/train 和 selection/dev benchmark 次数；
- 候选最大执行时间；
- ALNS iteration/time budget；
- 候选数量、最终部署组件数和随机 seeds。

若多轮方法因反馈文本更长而使用更多 token，应同时报告等调用预算与等 token 预算结果。

### 5.3 必需 baselines

- built-in human-designed ALNS operators；
- problem-specific operators；
- rule-based advisor；
- random/template-generated operators；
- one-shot LLM operators；
- multi-round without feedback；
- rank-only feedback；
- equal-budget parameter/search control；
- oracle-free single best selected only on dev。

## 6. 辅助创新 C：Behavior-Complementary Frozen Portfolio

### 6.1 计划机制

portfolio 不只保留 dev makespan 排名前 k 的候选。计划先施加统一 quality/eligibility floor，再根据行为描述选择互补算子。候选描述可包括：

- 改善实例与失败实例的覆盖集合；
- 对机器人/任务规模、矩形长宽比和负载失衡的响应；
- destroy 的 removal pattern 与 repair 的 insertion pattern；
- pairwise outcome correlation；
- runtime、invalid、timeout 和 fallback profile；
- 代码或结构特征仅作为辅助，不替代实际行为。

固定 portfolio size `k`，使用预先声明的低成本 ALNS 选择策略；final test 不在线调用 LLM。Selector 只允许上述 run-local adaptation，不能跨 test runs 学习。当前代码只冻结每类 single best，完整行为互补 portfolio 尚未实现。

### 6.2 Controls 与 ablations

- single dev-best；
- score top-k；
- random-k eligible operators；
- human-designed portfolio；
- behavior-diverse portfolio；
- 去除 dedup、去除 correlation、去除 failure/runtime descriptors；
- 相同 `k`、相同 ALNS budget 和相同候选池。

## 7. 辅助创新 D：Failure-Informed Revision

### 7.1 四轴 taxonomy

每个 trial 必须在四个轴上分别记录，轴之间不互相覆盖：

1. **Execution status（互斥）：** `execution_blocked`、`source_read_failed`、`validation_failed`、`runtime_error`、`timeout`、`execution_success`。
2. **Feasibility / contract validity（互斥）：** `valid_solution`、`invalid_solution`；`invalid_solution` 必须进一步给出一个 primary subtype：`contract_violation`、`missing_tasks`、`duplicate_tasks` 或 `malformed_return`。这些 subtype 属于同一 feasibility 轴，不得在其它轴重复计数。
3. **Optimization outcome（primary label 互斥）：** `improved_over_baseline`、`tied_baseline`、`worsened_vs_baseline`、`not_evaluable`。`no_improvement` 是派生 binary summary，定义为 `tied_baseline OR worsened_vs_baseline`，不得作为第五个 primary label 重复计数。
4. **Structural diagnostics（可多标签）：** `excessive_complexity`、`degenerate_operator`、`ignores_context`、`always_fallback`、`duplicate_behavior`、`unsafe_pattern_blocked`。

Primary label precedence 固定为：先记录 execution；只有 `execution_success` 才评价 feasibility；只有 `valid_solution` 才评价 optimization，否则 optimization=`not_evaluable`。Structural diagnostics 是辅助多标签，不覆盖前三轴的 primary labels。`execution_success` 只表示代码完成执行，绝不等于 feasibility success 或 optimization success。

Rate 分母必须显式固定：

- execution-status rates：全部 scheduled trials；
- feasibility rates：`execution_success` trials；
- optimization-outcome rates：`execution_success + valid_solution` trials；
- structural-diagnostic rates：全部已完成静态或动态诊断的 candidates，并另报 eligible denominator。

同一 trial 在每个互斥轴只计一次。聚合输出同时报告 scheduled、executed、valid、evaluable counts，禁止因 invalid/timeout 被过滤而改变未声明的质量分母。

Structural diagnostics 优先来自可测行为、复杂度阈值与退化测试；“未使用某个人工指定机制”不能单独成为 failure oracle。若使用人工或 LLM critic，必须冻结 rubric 并报告标签一致性与 sensitivity。

反馈 payload 计划包含 candidate/code hash、failure type、错误摘要或 violated contract、按实例/seed 聚合表现、runtime/fallback 信息以及 problem-specific hints。不得包含 final-test 信息。

### 7.2 Controls 与 ablations

- no feedback；
- rank-only；
- generic feedback；
- correct structured feedback；
- shuffled/wrong failure labels；
- feasibility-only、performance-only、structural-only；
- 相同候选、调用、token 与 benchmark 预算。

### 7.3 H2 的 2×2 反馈实验

H2 使用 factorial design，而不是把两类反馈合并成单一干预：

- Factor A：DP-aware performance feedback on/off；
- Factor B：feasibility/failure feedback on/off。

四个 cell 必须固定 evaluator、初始 candidate-generation budget、candidate count、rounds、benchmark budget、模型设置和 prompt-length/token-information budget。H2a 检验 Factor A 主效应；H2b 检验 Factor B 主效应；H2c 仅探索二者交互。若必须 padding/masking 以保持 prompt 长度，应预先固定并记录。

## 8. 方向 B：条件化生成作为泛化消融

B 不列为核心贡献。条件化输入可使用机器人数量、任务规模、矩形几何统计、路线失衡和搜索停滞特征，但 feature schema 必须只由 generation/train 与 dev 确定。

主要比较 unconditional A、feature-conditioned generation、rule-based configuration、shuffled features 和逐特征组删除。只有当 B 在未见规模和多 seed 上显示稳定、可复现收益，且不只是增加 prompt token 或人工特征工程，才考虑提升其贡献地位。

## 9. 评价协议与指标

### 9.1 Operator-level

- 四轴 taxonomy 的 status/rate 与各自明确分母；
- execution blocked/source-read/validation/runtime/timeout、feasibility subtype、optimization outcome、structural diagnostics 和 fallback 分解；
- repair 相对固定 baseline repair 的 makespan delta 与 relative improvement；
- destroy 与固定 repair 配对后的增量；
- runtime、代码 hash、调用/token/货币成本；
- diversity 和 behavior correlation。

fallback 不得记作 generated operator success，也不得获得 generated reward。destroy/repair 联合 trial 若无法清楚归因，应标记 attribution ambiguous 并从 generated reward 中排除。

### 9.2 Solver-level

- final makespan、相对 baseline gap；
- time/iteration-to-target；
- 跨实例和跨 seed 的均值、中位数、方差与尾部表现；
- operator usage/reward、fallback、invalid 与 timeout；
- 按实例规模和几何类别的 held-out generalization；
- offline generation/evaluation cost 与 repeated-deployment amortization。

### 9.3 统计分析

- Candidate-level rows、rounds 或同一 evolution run 内的 raw trials不得作为独立样本。
- 所有主结果必须报告每个 method condition 的 independent evolution-run repetition 数量。
- 分析必须保留 evolution run、instance family、instance replicate 与 solver seed 的层级相关性，使用 cluster-aware CI、hierarchical/mixed-effects analysis 或预注册的两阶段 aggregation。
- 样本量较小时，使用同时 over independent evolution runs 与 instance families 的 cluster/bootstrap，而不是 over raw candidate rows。
- H1 是唯一 primary confirmatory hypothesis；H6 与 H3 采用预注册 fixed-sequence gatekeeping 作为 secondary confirmatory；H2、H4、H5 是 secondary/exploratory，H7 是 exploratory。若越过该层级作额外检验，使用 Holm 等预注册多重比较控制并明确标注 exploratory。
- Dev ranking 只用于冻结 operator/portfolio；final-test effect 不允许反向选择候选，以隔离 winner's curse。
- 效应方向、最小实用差异、聚合函数、缺失/失败处理和 confidence level 必须在打开 final test 前冻结。

### 9.4 成本 estimands

成本与 makespan 不直接相减或互相“抵消”。主成本分析同时报告：

1. **quality-constrained cost：** 达到预注册 baseline-quality floor 时比较 LLM calls、tokens、wall time 与 benchmark compute；
2. **cost-constrained quality：** 在固定 LLM-call/token/runtime budget 下比较 held-out makespan；
3. **quality–cost Pareto frontier。**

Break-even 只可作为敏感性分析；必须提前定义共同效用函数或 willingness-to-pay、价格版本和复用次数范围，不作为主分析。

## 10. 每轮输入输出文件合同

建议每个 evolution run 采用不可变目录：

```text
run_manifest.json
split_manifest.json
round_000/
  prompt.json
  candidates/<candidate_id>.py
  validation.jsonl
  execution.jsonl
  benchmark.jsonl
  leaderboard.json
  elite_manifest.json
  failure_feedback.json
round_001/...
portfolio_manifest.json
frozen_registry.json
cost_report.json
```

manifest 至少记录配置 hash、代码版本标识、instance IDs、seeds、provider/model claimed metadata、runtime authorization evidence、prompt hash、candidate code hash、预算和污染标记。普通字符串证据不应被描述为不可伪造的 provenance receipt。

真实 provider 的计划性补充记录包括 endpoint、精确 model identifier/version、temperature、重试、调用时间块和 token；方法执行顺序应按预注册时间块随机化。Portfolio 还应在 dev folds 或 bootstrap 上报告 composition stability。这些是后续协议计划，不是本阶段实现。

## 11. 分阶段执行顺序

1. 文档冻结：研究问题、数据划分、主指标、预算与污染规则；
2. 基线稳定化：先解决成本单位 blocking decision，再核对可行性、determinism 和现有手工算子；
3. 冻结实例生成规则、family-level splits、independent evolution-run repetitions 与统计分析计划；
4. 完成 A 的显式 elite retention 与可复现实验输出；
5. 完成 D 的四轴 failure payload 与受控 ablations；
6. 完成 C 的 behavior descriptors、dedup 与 portfolio selection；
7. 只在隔离/授权条件满足后运行 generation/train 与 dev；
8. 冻结所有决策后运行 final-test batch；
9. 报告正结果、负结果、失败分解、成本和污染审计。

本文件只定义研究计划，不授权进入 Phase 5B、调用真实 LLM 或运行实验。
