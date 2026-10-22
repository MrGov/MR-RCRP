# Paper Contribution Plan

## 1. 中心论点

论文面向跨领域 AI-for-Optimization，研究如何把 LLM 生成的搜索算子经由多轮、可证伪、fail-closed 的离线演化流程，转化为可冻结并重复部署的组合优化组件。MR-RCRP + DP-aware ALNS 提供结构化验证载体，而不是论文主创新本身。

这里“跨领域”只描述论文面向 AI-for-Optimization 研究社区，不是跨优化问题领域的实证主张。当前“可复用”仅指 frozen operators 在 MR-RCRP problem family 内跨实例、规模和运行复用；没有第二个优化问题实验时，不得写成 cross-domain reusable operators。

中心论点在实验完成前只能作为研究目标：**多轮、问题感知且失败类型感知的离线算子演化，可能比 one-shot generation 产生更有效、更稳定、更可复用的 operators；行为互补 portfolio 可能进一步改善稳健性。**

## 2. 候选贡献层级

### 2.1 核心方法贡献

**A：可验证、可复用、fail-closed 的多轮 LLM offline operator evolution。**

候选贡献内容包括 generation、validation、isolated timeout execution、baseline-controlled benchmark、ranking、elite retention、feedback、revision、freeze 和 ALNS deployment 的闭环。强贡献成立的前提是：以完整 independent evolution run 为独立重复，在等预算、family-held-out final test 和人工/one-shot controls 下显示可复现收益；candidate rows、rounds 或 benchmark seeds 不得充当独立样本。

“LLM 生成代码”本身不是贡献；闭环机制及其严格归因、复用和可证伪评价才是候选创新所在。

### 2.2 辅助方法贡献

**C：基于行为互补性的 frozen operator portfolio。**

只有当行为多样性选择在相同候选池和 portfolio size 下优于 single best、score top-k、random-k 和 human portfolio，才能作为辅助贡献。当前完整 portfolio 尚未实现，不能写成既成事实。

**D：failure-informed operator revision。**

只有当四轴反馈——execution status、feasibility/contract validity、optimization outcome 与 structural diagnostics——在等 token/benchmark 预算下优于 rank-only、generic 与 shuffled feedback，才能作为辅助贡献。

### 2.3 支撑性工程贡献

Generated operators 的 fail-closed evaluation and deployment protocol 可作为可信实验和可复现部署的支撑贡献，包括：

- AST denylist、source hash、timeout-limited subprocess；
- contract/feasibility validation；
- invalid/timeout/fallback 与 success/reward 的隔离；
- fail-closed selection/freezing；
- runtime authorization 与 claimed metadata 分离。

该协议不是 capability sandbox。除非研究问题和实验专门转向系统安全，否则不应把论文主线包装为软件安全论文。

### 2.4 实验贡献

候选实验贡献是对 LLM operator generation 的性能、有效率、四轴失败模式、fallback、MR-RCRP 内跨实例/跨规模泛化和质量—成本 tradeoff 进行系统分析。它必须包括负结果、独立 evolution-run 数量、instance-family 层级统计和失败分解，而非只报告最佳 makespan。

## 3. 六个候选表述的裁决

| 候选表述 | 论文位置 | 使用条件 |
|---|---|---|
| 1. 面向 MR-RCRP 的 DP-aware ALNS | 验证框架/问题方法背景 | 如实说明 route DP 对固定序列的作用；不盖过 LLM 主线 |
| 2. LLM 辅助离线算子演化 | 核心方法贡献 | 等预算 multi-round、one-shot 和人工 controls 支持 |
| 3. 四轴 execution/feasibility/optimization/structural 反馈的多轮修订 | 辅助方法贡献 D | structured feedback 与 shuffled/generic 消融支持 |
| 4. LLM-generated operator portfolio 与复用 | 辅助方法贡献 C | 完整机制实现且优于 top-k/random-k/single best |
| 5. fail-closed evaluation/deployment protocol | 支撑性工程贡献 | 明确不是 capability sandbox，不夸大安全性 |
| 6. 性能、泛化、成本和失败模式系统实验 | 实验贡献 | family-level final-test lockbox、independent evolution-run statistics、四轴 taxonomy 与约束式成本 estimands 完整 |

方向 B 的 instance-feature conditioning 只作为泛化与条件化消融；除非在未见规模上稳定优于 unconditional A 和 rule-based controls，否则不进入核心贡献列表。

## 4. MR-RCRP 与 DP-aware ALNS 的叙事位置

论文仍应完整交代：

- 矩形覆盖任务、同质机器人、depot、任务恰好一次和 makespan 目标；
- 每任务 8 个覆盖状态与固定任务序列上的 route DP；
- ALNS destroy/repair/local search/advisor 的接口；
- repair 与固定 repair baseline 的公平评价，destroy 与固定 repair 的配对评价。

但这些内容服务于三个验证需要：精确 problem-aware feedback、严格 feasibility 判断和可复用 operator deployment。基础算子、problem-specific operators 与 rule-based advisor 主要作为 controls/scaffolds。

当前跨矩形移动使用 Manhattan distance 而未除以 speed，内部 processing time 则使用 `/speed`。论文必须明确当前 speed=1 假设或在实验前统一单位；不能在一般 speed 上声称成本已一致。

当前仓库仅有两个 2-robot、单 replicate 实例，只能 smoke/demo。在新的 instance-generation protocol、family-level split 与 final-test manifest 冻结前，任何 train/dev/test、显著性或泛化主张均不成立。

## 5. Claim Ladder 与证据门槛

### Level 0：事实性描述

可立即陈述已实现接口、gate、DP、ALNS 和现有 benchmark 流程，但要区分当前能力与计划机制。

### Level 1：可行性主张

需要证明候选能通过验证、生成可行解、冻结部署且 fallback 不被计为成功。只支持“框架可运行”，不支持“方法优越”。

### Level 2：方法有效性主张

需要 A/D/C 各自的预注册 baselines、ablations、多 instance families、independent evolution-run repetitions、solver seeds 和等预算结果。H1 为唯一 primary confirmatory；H6、H3 仅在 fixed-sequence gatekeeping 下作为 secondary confirmatory。

### Level 3：泛化与复用主张

需要完全 family-held-out MR-RCRP instances、未见规模、冻结后零 LLM test-time calls，以及跨 independent evolution runs/模型/预算的稳定性证据。该层不支持跨优化问题领域泛化。

### Level 4：成本效益主张

需要端到端 token、货币、wall time、benchmark compute 与部署次数日志，并与人工、one-shot、在线生成等 controls 比较。主分析采用 quality-constrained cost、cost-constrained quality 和 Pareto frontier；没有预注册共同效用时不使用“质量抵消货币成本”的表述。

任何层级未满足时，应降级措辞而不是借用较低层证据支持较强结论。

## 6. 推荐与禁止措辞

### 实验前可用

- “我们研究/提出一个候选框架……”
- “该设计旨在检验……”
- “新颖性潜力有待系统文献查新与实验确认。”
- “当前实现提供 timeout-only execution boundary，而非 capability sandbox。”

### 仅有证据后可用

- “在预注册 held-out protocol 下优于……”
- “behavior-diverse portfolio 在相同 `k` 和预算下……”
- “structured failure feedback 对 validity/performance 的影响为……”

### 当前禁止

- “首次”“state of the art”“显著提升”“证明有效”；
- “安全执行任意 LLM 代码”或“完整 sandbox”；
- “portfolio 已完整实现”；
- “真实 LLM 已经改善 MR-RCRP”；
- “已证明跨优化问题领域复用”或“cross-domain reusable operators”；
- 使用 final test 反馈修订 prompt、算子、selection 或参数后的无污染测试主张。

## 7. 不能作为强贡献的内容

- 仅仅调用 LLM 或使用 prompt templates；
- 标准 ALNS、标准 route DP 或基础 operators 的直接组合；
- AST denylist、hash 或 timeout 单项机制；
- mock/file provider 支持；
- rule-based advisor 本身；
- 人工 problem-specific hints 或参数调优；
- 只在 generation/dev instances 上选择的最佳个例；
- 没有等预算 control 的成本或性能提升。

## 8. 建议论文结构

1. Introduction：AI-for-Optimization 中 generated operator 的验证、归因和复用问题；
2. Related Work：LLM for optimization、hyper-heuristics/operator generation、ALNS/portfolio；
3. Validation Vehicle：MR-RCRP、route DP、ALNS interfaces；
4. Method：A lifecycle、D feedback、C portfolio、fail-closed gates；
5. Experimental Protocol：splits、controls、ablations、cost/validity/generalization；
6. Results：主假设、负结果、失败模式与成本；
7. Limitations：非 capability sandbox、单领域验证、provider/provenance 和模型依赖；
8. Conclusion。

相关工作与新颖性需要后续独立文献查新。本文件不构成新颖性结论，也不授权实验。
