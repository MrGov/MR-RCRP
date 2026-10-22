# Innovation Review

## 1. 评价边界

本文件比较四条 LLM 创新方向。新颖性评分是**候选潜力判断**，不是文献查新结论；所有性能判断均待真实 LLM、严格数据隔离和统计实验验证。

本文的复用范围限于 frozen operators 在 MR-RCRP problem family 内跨实例/规模复用。`AI-for-Optimization` 是研究社区定位；在没有第二个优化问题实验时，不把任何方向表述为已证明 cross-domain reusable。

评分采用 1–5：5 表示更高的新颖性潜力/匹配度/可证伪性/依赖度，或更高成本/风险。高“真实 LLM 依赖”表示仅靠 mock/file 不能验证核心主张。

## 2. 总体比较

| 方向 | 新颖性潜力 | 当前代码匹配 | 实现成本 | 可证伪性 | 真实 LLM 依赖 | 主要风险 |
|---|---:|---:|---:|---:|---:|---|
| A. Offline operator evolution | 4 | 5 | 3 | 5 | 5 | 被批评为 prompt search 或昂贵自动调参 |
| B. Instance-conditioned generation | 4 | 2 | 5 | 4 | 5 | 特征工程/数据泄漏掩盖 LLM 贡献 |
| C. Generated operator portfolio | 4 | 3 | 4 | 5 | 4 | top-k 冒充 diversity，在线选择产生混杂 |
| D. Failure-informed revision | 4 | 4 | 3 | 5 | 5 | 失败反馈只换 prompt 文案，机制不够实质 |

推荐：**A 为主线，C 与 D 为辅助创新；B 只作泛化和条件化消融。**

## 3. 方向 A：LLM-guided Offline Operator Evolution

### 方法定义

LLM 离线生成 repair/destroy code，候选经 validation、isolated execution、benchmark 和 eligibility gate 后排名；下一轮根据结构化反馈修订，最终冻结并部署到 ALNS。部署后求解阶段不调用 LLM。

### 评价

- **新颖性潜力：** 高于 one-shot code generation，因为研究对象是可重复的 operator lifecycle、selection pressure 和跨轮 adaptation；仍需正式查新。
- **与当前代码匹配：** 最高。Generation/revision/evaluation/feedback/best/freeze/deployment 骨架均存在。
- **实现成本：** 中等。核心缺口是严格 split、真实 elite retention、实验矩阵与真实 LLM logging。
- **实验可证伪性：** 强。可直接比较 one-shot、multi-round、无反馈、随机反馈和人工算子。
- **真实 LLM 依赖：** 高。Mock 只能验证流程，不能支持 LLM 有效性主张。

所有 A 的推断必须以完整 independent evolution run 为独立重复。Candidates、rounds、benchmark seeds 和 instances 是 run 内嵌套 observations，不能增加名义样本量。当前两个 R2 单-replicate 实例只可 smoke/demo，不能用于 A 的 train/dev/test 结论。

### 审稿风险

1. 只是让 LLM 写 heuristic code，没有方法创新；
2. 性能来自更多 benchmark evaluations，而不是反馈质量；
3. 选择同一 dev set 导致过拟合；
4. 与 genetic programming、program synthesis、automated heuristic design 的关系未澄清；
5. 只在一个问题族上有效。

### 必需 baselines

- 人工内置 ALNS operators；
- 人工 problem-specific operators；
- random/template code mutation；
- one-shot LLM operators；
- multi-round LLM without feedback；
- multi-round with rank-only feedback；
- equal evaluation-budget search/control；
- oracle dev selection（只作上界，不接触 final test）。

### 必需 ablations

- revision rounds；
- elite retention on/off；
- DP-aware feedback on/off；
- feasibility/failure feedback on/off；
- LLM model/temperature（资源允许时）；
- repair-only、destroy-only、joint evolution；
- freeze/reuse 与重新生成。

## 4. 方向 B：Instance-Feature-Conditioned Operator Generation

### 方法定义

向 LLM 提供实例族或搜索状态特征，例如机器人数量、任务规模、矩形 aspect-ratio distribution、H/V processing gap、路线失衡和停滞，生成条件化算子。

### 评价

- **新颖性潜力：** 中高，但容易与 feature-based algorithm configuration 重叠。
- **当前代码匹配：** 低。Prompt 只有 problem hints，没有正式 feature schema；离线 evolution 也没有 search-state-conditioned generation。
- **实现成本：** 高。需要特征定义、归一化、分桶、训练/测试 extrapolation 和 leakage audit。
- **实验可证伪性：** 较强。可比较 no-feature、wrong/shuffled feature、coarse family feature 和完整 feature。
- **真实 LLM 依赖：** 高。

### 审稿风险

- 收益来自人工挑选 problem-specific features；
- conditioning 只是把实例标签写进 prompt；
- 对 dev family 过拟合，跨规模失效；
- final test 特征虽不含标签，但被用于设计 prompt schema，造成间接泄漏。

### 必需 baselines/ablations

- unconditional A；
- shuffled/mismatched features；
- rule-based feature-to-operator mapping；
- conventional algorithm selection/configuration；
- seen-size interpolation 与 unseen-size extrapolation；
- geometry-only、load-only、stagnation-only feature groups。

### 定位决策

方向 B 只作为泛化实验和条件化消融。只有在 held-out 规模上持续、显著且跨 seed 稳定，且胜过 rule-based conditioning 时，才考虑提升为贡献。

## 5. 方向 C：LLM-Generated Operator Portfolio

### 方法定义

不只冻结单个 dev-best operator，而是选择一个质量合格且行为互补的 operator set。ALNS 在线只在 frozen portfolio 中做低成本选择，不在线调用 LLM。

### 行为互补性候选描述

Portfolio 不能等同 top-k。计划使用不依赖 final test 的行为描述：

- 改善实例/seed 的覆盖集合；
- 对任务规模、机器人数量和几何族的相对优势；
- destroy removal pattern；
- repair insertion/load-balancing pattern；
- 与人工算子的 outcome correlation；
- runtime、failure 和 fallback profile。

### 评价

- **新颖性潜力：** 中高，尤其当 portfolio construction 明确优化 quality-diversity，而不是保存多个高分代码。
- **当前代码匹配：** 中等。ALNS 已支持多算子和自适应权重，但 freezing 当前每类只有一个 best。
- **实现成本：** 中高。需要行为日志、去重、portfolio objective 和固定在线 selector。
- **实验可证伪性：** 强。可对比 single best、score top-k、random-k、人工 portfolio 和 quality-diversity portfolio。
- **真实 LLM 依赖：** 中高；portfolio 机制可先用 mock/file 验证，但 LLM portfolio 贡献必须用真实模型。

### 审稿风险

- Portfolio 收益只来自更多算子或更多计算；
- 多个算子实际上语义/行为重复；
- 在线 selector 比 single-best 获得额外调参；
- 与标准 ALNS operator portfolio 没有方法差异。

### 必需 controls

- 固定相同 portfolio size `k`；
- 固定候选生成与 benchmark budget；
- single best、score top-k、random-k、人工-k；
- 无 diversity objective；
- frozen uniform/random selector 与同一 adaptive selector；
- AST duplicate、code-hash duplicate 和 behavioral duplicate removal。

Portfolio composition 必须在 train/dev 后冻结。Adaptive selector 只允许在单个 final-test run 内按预注册规则更新并在每个 instance/seed/evolution run/test file 重置；禁止跨 test runs 持久化。作为稳健性分析，计划报告 portfolio 在 dev folds/bootstrap 下的 composition stability。

## 6. 方向 D：Failure-Informed Operator Revision

### 方法定义

把候选结果拆成四个互不覆盖的证据轴，再将轴特定证据反馈给下一轮：

- execution：blocked/source-read/validation/runtime/timeout/execution success；
- feasibility/contract：valid 或 invalid，并用 contract/missing/duplicate/malformed primary subtype；
- optimization：improved/tied/worsened/no-improvement/not-evaluable；
- structural diagnostics：complexity、degeneracy、context use、fallback、duplicate behavior 与 blocked unsafe pattern。

Execution success 不等于 optimization success。Structural diagnostics 优先基于可测行为、复杂度和退化测试，不把“必须使用几何”等人工偏好作为隐含 oracle。

### 评价

- **新颖性潜力：** 中高，关键在于结构化 failure-to-revision mapping，而不是附加错误字符串。
- **当前代码匹配：** 高。已有 failure status/breakdown 和 fail-closed gate，但 feedback payload 只有聚合计数。
- **实现成本：** 中等。需要 canonical failure record、可控信息量和 failure-specific prompt arms。
- **实验可证伪性：** 强。可与 rank-only、generic error text、no feedback 和 shuffled failure feedback 比较。
- **真实 LLM 依赖：** 高。

### 审稿风险

- 反馈包含更多 token，公平预算不一致；
- 失败案例泄露 dev answers 或促成实例记忆；
- structural critic 依赖主观规则；
- validity 提升但 optimization performance 不提升。

### 必需 controls

- 相同 token/evaluation budget；
- no feedback；
- rank-only feedback；
- generic failure feedback；
- structured correct failure feedback；
- shuffled/wrong failure labels；
- feasibility-only、performance-only、structural-only feedback；
- 报告 validity、timeout、feasibility、performance 和 code-diversity 分项。

DP-aware performance feedback 与 feasibility/failure feedback 必须采用 2×2 factorial：分别估计两项主效应，交互只作 exploratory；四个 cells 保持 evaluator、candidate pool、rounds 和 token/information budget 相同。

## 7. 推荐论文主线

主叙事：

1. A 定义完整 offline evolution lifecycle；
2. D 提供可解释、可消融的 revision signal；
3. C 将单一 dev-best 扩展为 frozen reusable portfolio；
4. MR-RCRP + route DP + ALNS 提供结构化、精确、可行性敏感的验证环境；
5. B 只检验条件化是否改善跨规模泛化。

安全 gate 是可信实验基础设施和支撑性工程贡献，不应把论文改写成软件安全论文。当前 timeout-only boundary 必须如实披露。

统计上，H1/A 使用完整 evolution-run repetitions 与 held-out instance-family aggregation；不能从同一 candidate pool 的 candidate rows 构造置信区间。当前仅有两个 R2 实例、且 travel/processing speed 单位未决，因此所有方向仍处于协议设计状态。

## 8. 进入强贡献表述的证据门槛

- A：multi-round 在 held-out final test 上优于 one-shot，并控制总生成/评价预算；
- C：behavior-diverse portfolio 优于同规模 score top-k、random-k 和 single best；
- D：structured failure feedback 优于 rank-only/generic/shuffled feedback；
- B：在未参与设计的实例规模上稳定优于 unconditional A 与 rule-based conditioning；
- 所有方向：报告 validity、fallback、runtime、LLM token/cost、跨 seed 方差和负结果。
