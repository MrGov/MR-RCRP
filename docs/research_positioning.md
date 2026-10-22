# Research Positioning: LLM Offline Operator Evolution for AI-for-Optimization

## 1. 研究定位

本文候选主线是：提出一种**可验证、可复用、fail-closed 的多轮 LLM offline operator evolution 框架**，将 LLM 生成的搜索算子转换为可离线评价、修订、筛选、冻结并复用的组合优化组件。

MR-RCRP（multi-robot rectangular coverage routing problem）是结构化验证载体；DP-aware ALNS 是执行和精确评价 generated operators 的宿主优化框架。论文不是以“为 MR-RCRP 构造更强 ALNS”为中心，也不把 LLM 当作直接任务分配求解器。

本阶段“可复用”具有严格范围：只指 frozen operators 在 **MR-RCRP problem family 内**跨独立实例、实例规模和重复运行复用。`AI-for-Optimization` 是论文面向的研究社区定位，不是已经获得的跨优化问题领域实证结论。除非后续加入第二个优化问题并采用独立实验协议，不得使用“cross-domain reusable operators”或等价表述。

本文使用以下事实标签：

- **[Implemented]**：当前代码已实现且有测试支撑。
- **[Planned]**：后续拟实现或形成实验协议，但当前代码不具备完整机制。
- **[Candidate contribution]**：只有在预注册实验支持后才可写入论文贡献。
- **[Unsupported claim]**：当前没有结果支持，不得写成结论。

“新颖性潜力”仅表示值得进一步查新和验证的候选定位；本阶段没有进行外部文献查新，不能声称无先例或已证明新颖。

## 2. MR-RCRP 问题定义

### 2.1 实体与输入

一个实例包含：

- 一个 depot，当前默认为 `(0, 0)`；
- `m` 个同质机器人；
- `n` 个轴对齐矩形覆盖任务；
- 机器人速度 `speed`、扫幅 `sweep_width` 与转弯时间 `turning_time`；
- 每个任务的左右、上下边界。

每个矩形任务生成 8 个覆盖状态：4 个入口角与 2 个 sweep mode（水平 H、垂直 V）的笛卡尔积。状态包含入口/出口角、入口/出口坐标、sweep 数和内部处理时间。

### 2.2 解、约束与输出

一个解由 `m` 条有序任务路线组成。完整可行解必须满足：

1. 每个任务恰好分配给一台机器人；
2. 每个任务在所有路线中恰好出现一次；
3. 机器人从 depot 出发并在完成路线后返回 depot；
4. 路线可为空，空路线成本为 0；
5. 每个矩形必须选择一个合法覆盖状态。

输出包括每台机器人的任务顺序、DP 选择的覆盖状态链、各路线成本与总体 makespan。

### 2.3 成本与目标

H-mode 与 V-mode 的内部覆盖时间分别使用：

`processing_time = n_sweeps * traversal_length / speed + (n_sweeps - 1) * turning_time`。

固定路线成本由 depot travel、任务间 travel、任务内部 processing time 和返回 depot travel 组成。多机器人目标为：

`minimize max_r route_cost(r)`。

**正式实验 blocking decision：** `CostMatrix` 对 depot/任务间移动直接使用 Manhattan distance，没有除以 `speed`；内部 processing time 则除以 `speed`。因此当前实现只有在 `speed = 1`，或 Manhattan distance 已被归一化解释为时间时单位一致。在明确固定 `speed = 1` 的建模假设或统一 travel/processing 单位之前，所有 makespan 只能称为**当前原型模型下的 prototype metric**，不能解释为最终物理完成时间，也不得用于论文级性能结论。本阶段只记录该阻断项，不修改生产代码。

## 3. DP Route Evaluator 的正式作用

### 3.1 已实现事实

给定固定任务序列 `(t1, ..., tk)`，route DP 以任务位置为层、任务的 8 个覆盖状态为节点，求取成本最小的状态链。它联合考虑：

- depot 到首任务入口；
- 每个状态的内部 processing time；
- 前一任务出口到下一任务入口的 Manhattan transition；
- 最后任务出口到 depot。

DP 返回精确状态链、累计成本、transition cost、入口/出口点和 predecessor trace，并按 task sequence 缓存。

### 3.2 不承担的角色

DP 不决定：

- 任务属于哪台机器人；
- 每台机器人的任务顺序；
- destroy/repair 的搜索策略；
- LLM 候选的生成或选择。

因此，DP 是**固定任务序列上的 problem-aware 精确内层评价器**。ALNS 和 generated operators 搜索外层的分配与排序；DP 为每个外层候选提供一致评价。

## 4. 当前搜索组件的角色

### 4.1 ALNS

**[Implemented]** ALNS 负责组合搜索。每轮执行：operator selection → destroy → partial evaluation → repair → stronger local search → acceptance → reward/weight update。Acceptance 支持 improvement-only 与 simulated annealing。

### 4.2 Destroy operators

**[Implemented]** Destroy 将完整解分解为 partial solution 与 removed tasks。当前内置 random、bottleneck-route 和 geometry-aware destroy。Generated destroy 的公平评价必须与固定 repair 配对。

### 4.3 Repair operators

**[Implemented]** Repair 将 removed tasks 插回 partial solution。Greedy、regret、bottleneck-balancing insertion 都调用 route DP 评价插入候选。`dp_aware_insertion` 只保留为私有兼容别名，不再注册为 selectable operator；`alns_dp_aware` 也不是合法 benchmark mode。

### 4.4 Local search

**[Implemented]** Local search 对 repaired solution 做 relocate、swap、2-opt 等确定性邻域改进。它是所有比较方法需要控制的后处理因素，不属于 LLM 贡献。

### 4.5 Advisor

**[Implemented]** Advisor interface 可根据当前 makespan、路线失衡、停滞和 operator stats 推荐 destroy/repair。当前只有 mock 和 rule-based advisor，没有在线真实 LLM advisor。论文中 advisor 应作为 control/ablation，不与 offline operator evolution 混为同一机制。

## 5. LLM 子系统：已有能力与缺口

### 5.1 已实现事实

当前 offline operator evolution 已具备：

- mock、file 与 LangChain-compatible provider abstraction；
- repair/destroy candidate generation 与多轮 revision 接口；
- 候选源码落盘、AST denylist、code hash、subprocess hard timeout；
- smoke test、contract/feasibility validation 和结构化 failure status；
- repair 与固定 baseline repair 比较；
- destroy 与固定 repair 组合评价；
- 多实例/seed 参数接口、makespan delta、relative improvement、validity/error/timeout metrics；
- eligible top/weak feedback、全局单个 best-per-type selection；
- freeze registry、hash/AST/metadata/runtime authorization gate；
- fallback、invalid、timeout 与 reward/success 隔离。

当前边界只是 `timeout_only` subprocess，不是 capability sandbox。CPU、内存、文件系统、网络、环境变量和后代进程树隔离尚未实现。

### 5.2 计划实现机制

以下机制当前不完整：

- 真正的 top-k elite code retention 与父代 lineage；
- 基于行为互补性的 operator portfolio；
- portfolio 在线低成本选择与独立 reward attribution；
- failure-specific feedback payload 与定向 revision；
- instance-feature conditioning schema；
- generation/dev/final-test 隔离；
- 跨实例规模泛化、统计检验和成本核算；
- versioned/signed provenance receipt 与 capability sandbox。

### 5.3 当前不能声称的结果

不得声称：

- 真实 LLM generated operators 已优于人工算子；
- 多轮 revision 已优于 one-shot；
- portfolio 已完整实现或优于 single best；
- operators 已在 held-out instances 上泛化；
- 性能收益已抵消 LLM 成本；
- fail-closed gate 等价于完整安全沙箱；
- DP-aware ALNS 已被现有消融证明优于普通 ALNS。

## 6. LLM 的正式方法角色

LLM 是离线的：

- operator generator；
- operator reviser；
- 可选的结构 critic。

LLM 不直接输出最终任务分配解，不在最终 ALNS search loop 中在线决策，也不接收 final test 结果。

正式数据流为：

`LLM draft → static validation → isolated execution → feasibility gate → benchmark → eligible ranking/portfolio construction → structured feedback → revision → freeze → ALNS deployment`。

ALNS 执行组合搜索；route DP 提供 problem-aware 精确评价；eligibility、feasibility、benchmark 与 freezing gate 将不受信代码候选转换成可复用组件。

## 7. 数据隔离与 final-test lockbox

**[Planned, mandatory]** 实例必须在任何真实 LLM generation 前划分为：

- generation/train：可用于 prompt context、候选生成和 failure revision；
- selection/dev：只用于候选排名、portfolio 选择和预先规定的超参数选择；
- final test：设计冻结后只运行一次或按预注册次数运行。

Final test 的 makespan、failure、代码行为或实例特征不得反馈给 LLM，不得修改 prompt、operator code、selection rule、portfolio、ALNS 参数或 baseline。任何违反都必须标记为 contaminated run，不能作为主要泛化证据。

### 7.1 当前数据 no-go

当前仓库只有 `R2_T6_0.txt` 与 `R2_T10_0.txt` 两个 2-robot、单 replicate 实例。它们只能用于 smoke test、demo 和确定性接口检查，不能被拆成 generation/train、selection/dev 与 final test，也不能支持统计显著性、跨规模泛化、LLM 有效性或优于 baseline 的论文结论。

当前默认 operator-evolution glob 会自动纳入所有匹配的 `data/R*_T*_*.txt`。正式实验前必须通过独立、冻结的 split manifest 覆盖该行为，禁止 final-test 文件被 generation、feedback、ranking、portfolio construction 或 tuning 自动读取。本阶段不修改 config 或 data。

### 7.2 实例协议的冻结条件

进入任何实验前必须先冻结并版本化：

- instance generation rules 与 exclusion criteria；
- included instance families；
- robot/task combinations 与每个 family 的 replicate 数；
- generation/train、selection/dev、final-test 分组清单；
- final-test manifest、所有随机 seeds 与数据泄漏政策。

拆分必须按 instance family、规模或生成族分组，不能随机拆 raw files 后把高度相关的同族实例分散到不同集合。Final test 是一次锁定的 evaluation batch，不是可反复调参的数据源。

### 7.3 Final-test 内部状态边界

Portfolio composition、operator set、selector algorithm 和初始参数必须在 train/dev 后冻结。允许预注册的 adaptive selector 在**单个 test run 内**根据该 run 的搜索状态更新 operator weights；该 learned state 必须在每个 instance、solver seed、evolution run 和 test file 开始时重置，不得跨 run 持久化。Final-test performance、selection trajectory 或 failure 只能用于最终报告，不得回写 prompt、portfolio composition、operator code、超参数或未来 test runs。

## 8. 论文主张层级

- **主创新候选：** 多轮、可验证、在 MR-RCRP 问题族内可冻结复用、fail-closed 的 LLM offline operator evolution。
- **辅助创新候选 C：** 基于行为互补性的 frozen operator portfolio，而非只保留单一 best。
- **辅助创新候选 D：** 将 execution status、feasibility/contract validity、optimization outcome 与 structural diagnostics 四轴分开记录并用于定向 revision。
- **方向 B：** instance-feature conditioning 仅作泛化消融；除非 held-out 跨规模结果稳定，否则不列核心贡献。
- **验证载体：** MR-RCRP + DP-aware ALNS。
- **Baseline/scaffold：** 内置算子、problem-specific operators、rule-based advisor、local search 和单-best freezing。

具体比较、实验路线、贡献门槛与假设分别见 `innovation_review.md`、`llm_operator_evolution_research_plan.md`、`paper_contribution_plan.md` 和 `research_hypotheses.md`。
