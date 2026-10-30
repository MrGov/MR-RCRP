# MR-RCRP：DP 证据驱动的 LLM 算子演化与成本感知 ALNS（设计修订稿 v0.2）

> 状态：**研究与实现设计稿，尚未冻结**。本文不授权修改已冻结的 B1、Route-DP、数学模型、测试数据或 Proposed-original/vNext。当前工作为设计审查；真正开发应按文末阶段逐项实施、逐项验证。
>
> 核心目标：把 Exact Route-DP 的真实状态链与路线成本转化为离线 LLM 算子修订证据；利用真实完整 ALNS 增量收益控制部署算子数量；在在线 ALNS 中考虑算子计算开销，而不是无限扩大算子池。

## 0. 研究定位与边界

- **LLM：离线**生成和修订 Destroy/Repair Python 算子；不在每次在线 ALNS 迭代调用 LLM。
- **Exact Route-DP：在线**对给定任务分配与访问序列优化覆盖状态、评价 makespan；**离线**作为诊断和反馈信息源。
- **ALNS：在线**执行冻结算子、接受和局部搜索，保留已有 SA 与自适应 roulette 主体。
- **算子池：**由候选的质量、耗时、可靠性与完整 ALNS 的边际贡献决定；不由 LLM 自行宣布“需要几个”。
- 对比算法的 Greedy/Exact 模式属于**独立基线设置**，不属于 Proposed 的 DP 反馈演化；正式实验需如实区分，不应通过削弱基线证明创新。
- 已有证据只表明当前 vNext 可行且速度优化有益，**不能**预先宣称新反馈/算子池/成本奖励组合具有性能优势或已验证新颖性。

## 1. MR-RCRP 的精确状态与代价定义

### 1.1 八种覆盖状态

对于每个轴对齐矩形任务 i，允许四个进入角点 `LB/LT/RB/RT`，覆盖方向为 `H/V`，因此为 `4 × 2 = 8` 个合法状态。每个状态的出口角点由进入角点、覆盖方向和扫描次数奇偶性**确定**，不可独立指定。状态机沿用 `core/state_generator.py` 的唯一实现；不另造出口规则。

令矩形宽、高为 `w_i,h_i`，扫描宽度为 `δ`，覆盖速度为 `v_s`，固定转弯时间为 `τ`：

\[
N_i^H=\lceil h_i/\delta\rceil,\quad N_i^V=\lceil w_i/\delta\rceil;
\]
\[
P_i(H)=N_i^H w_i/v_s+(N_i^H-1)\tau,\quad
P_i(V)=N_i^V h_i/v_s+(N_i^V-1)\tau.
\]

跨区域曼哈顿移动**时间**为 `d_1(a,b)/v_t`，其中 `v_t=instance.travel_speed`，不能混用覆盖速度 `v_s`。文档 v0.1 的 `v=1,δ=2,τ=0.5` 只属于其来源 PDF 示例，不能作为当前全部结构化算例的参数。

状态 `state_id` 在当前 `generate_all_states(instance)` 中按实例全局顺序分配。可靠身份应至少包括 `(instance_id, task_id, state_id)`；跨实例不得比较裸 `state_id`。

### 1.2 路线、目标与精确 DP

对路线 `r=(i_1,…,i_k)` 及覆盖状态链 `s_1,…,s_k`，有

\[
P_r=\sum_{j=1}^k P_{i_j}(s_j),\qquad
V_r=\frac{d_1(0,\mathrm{entry}(s_1))}{v_t}+
\sum_{j=1}^{k-1}\frac{d_1(\mathrm{exit}(s_j),\mathrm{entry}(s_{j+1}))}{v_t}+
\frac{d_1(\mathrm{exit}(s_k),0)}{v_t}.
\]
\[
C_r=P_r+V_r,\qquad M(S)=\max_{r=1}^{R} C_r.
\]

空路线成本为 0。固定任务序列时，状态依赖仅通过前后相邻状态发生，Route-DP 可精确求解给定序列的最小 `C_r`。`P_r` 内含扫描与转弯时间，需要诊断时可再拆为 `P_r^{sweep}`、`P_r^{turn}`。

**重要限定：** `P_i(H/V)` 与该任务在路线中的位置无关；但若重新排序后再次运行 DP，最优 H/V 模式可能改变，因此“顺序改变不影响覆盖时间”仅在**状态保持不变**时成立。不要把覆盖成本变化归因于绝对独立的动作类型。

## 2. 代价分解与可支持的诊断结论

### 2.1 精确的路线物理成本分解

每台机器人 `C_r=P_r+V_r`，其中 `P_r=P_r^{sweep}+P_r^{turn}`。均衡并非第三种物理成本。

### 2.2 全局目标的代数分解（可精确，但不是因果归因）

定义 `\bar P=(1/R)ΣP_r`、`\bar V=(1/R)ΣV_r`、`B=max_r(C_r)-(1/R)ΣC_r`，则

\[
\boxed{M=\bar P+\bar V+B}.
\]

对于两个完整解，可精确计算

\[
\Delta M=\Delta\bar P+\Delta\bar V+\Delta B.
\]

这里的 `B` 为**路线最大负载超额量**，不是与覆盖、移动并列的物理代价；分解是代数恒等式，不代表三项的变化具有独立因果作用。父子解差异中同时记录 `(\Delta M,\Delta\bar P,\Delta\bar V,\Delta B)` 以及旧/新瓶颈路线。

### 2.3 三条使用原则

1. `state_switch`、`hv_mode_switch`、`cascade` 是变化描述，**不是损失或越小越好的指标**；当前模型没有相邻任务 H/V 模式切换罚项。
2. `transfer_share` 高只能提示移动成本重要，不能保证顺序优化可获得较大改善；仍可能受到机器人分配和状态约束影响。
3. 反馈中的“造成”“由于”只在有控制变量的对应试验支持时使用；否则表述为“伴随”“可能与……有关”，避免把完整解的关联误写为单次插入的因果证据。

## 3. 反馈仪表：分为必需与可选

### I1：真实成本与瓶颈画像（必需）

对每条路线记录 `total / sweep / turn / transfer`、`cov_share / transfer_share`、旧/新瓶颈、最大负载超额量 `B`；所有量直接由 `RouteEvaluation.chosen_states` 与 `transition_costs` 回算并做数值一致性检查。

### I2：实际覆盖状态链（必需）

记录每任务 `(task_id, route_id, position, state_id, entry, mode, exit)`。对父子不同任务序列，先按 `task_id` 对齐；仅相同路线且顺序一致时才定义位置意义上的首个状态分叉点。对于不同顺序/分配，使用 `changed_tasks`、`affected_routes` 和 `state_change_count`，不能把两条长度不同的状态链按数组下标硬比较。

### I3：状态替代代价 `state_substitution_penalty`（可选、只用于少量案例）

对固定任务序列第 j 个任务，将最优链的状态 `s_j^*` 强制替换为**任意其他**合法状态，并允许其余任务状态全局重新优化：

\[
Q_j(s)=F_j(s)+B_j(s),\qquad
\Delta_j=\min_{s\ne s_j^*}Q_j(s)-C_r^*\ge 0.
\]

`F_j(s)` 为到达并完成状态 s 的最优前缀成本，`B_j(s)` 为固定 s 后的最优后缀成本（含返仓），`C_r^*` 为原路线 DP 最优成本。`Q_j` 可以通过一次前向和一次后向 DP 算出；**不必对每个候选做重复后缀重算**。

- `Δ_j≈0`：存在接近等价的替代状态，**状态选择灵活**。
- `Δ_j` 大：在当前固定任务序列下，该状态不容易替换，**状态选择刚性更强**。
- 不等同于任务可移动性或路线负载 slack，不能据此断言“这个任务不要搬”。

### I4：可改进空间提示（可选，当前优先用可靠代理而非不严谨的理论界）

- `mode_processing_gap = P_r-Σ_{i∈r}min(P_i(H),P_i(V))`，仅为**覆盖处理部分**的理想化改善上限；切换模式可能增加转移成本，不能视为 makespan 改善上限。
- `route_load_excess = max_r C_r-mean_r C_r`，是均衡程度描述，不叫 `balance_gain_bound`。
- `transfer_share` 和瓶颈路段的曼哈顿腿分布可作为顺序/重分配的启发式提示。
- 若确需 `order_transfer_bound`：在任务与 depot 的图上，以**两个矩形允许角点之间的最小 Manhattan 移动时间**（depot 至角点取最小）作为无向边权建立 MST。该 MST 权值是该路线区域间转移成本的下界；不能直接用矩形中心点距离构建后宣称合法下界。此项仅用于**转移成本**，不是完整 makespan 的上界。建议推迟到后续确有必要时实现。
- 全局 makespan 的保守下界可先用 `max(Σ_i min_m P_i(m)/R, max_i min_m P_i(m))`。`core/lower_bounds.py` 中已有 `simple_average_processing_lb()`；其他名字带 LB 的方法不能未经数学核查就用于最优性结论，尤其不可直接把每任务 depot 往返成本求和作为总路线下界。

## 4. 数据结构：保留最小字段

### 4.1 `StateChainRecord`（一条完整解中的一条路线）

必需：`instance_id, solution_hash, route_id, task_order, chosen_state_ids, states[{task_id,position,entry,mode,exit}], sweep_total, turn_total, transfer_total, route_cost`。

可选：`state_substitution_penalties`、关键移动腿和 canonical R3 `state/cascade` 指标。`chosen_state_ids` 和 `chosen_states` 在现有 `RouteEvaluation` 中已存在，优先消费返回对象，不能反复计算整个 DP 以获得相同信息。

### 4.2 `CounterfactualPair`（固定输入下的两个 Repair）

必需：
- `instance_id, input_id, evaluator_config_hash, parent_candidate_hash, child_candidate_hash`；
- `full_parent_routes, partial_routes, removed_tasks, solver_seed, fixed_destroy_hash`；
- 两个完整候选各自的 `routes, makespan, route_costs, actual_state_chains`；
- `changed_tasks, affected_routes, old_bottlenecks, new_bottlenecks`；
- `delta_makespan, delta_mean_processing, delta_mean_transfer, delta_load_excess`；
- `verdict=better/worse/tie` **按 makespan**，近似相等采用统一数值容差。

`input_id` 必须能唯一指向已持久化的完整父解、partial、移除任务与 D* 运行记录；不能单用 `{partial_hash, removed_set, seed}` 跨实例比较。两算子都从同一输入启动，需使用相同 `solver_seed`，且记录两套候选身份。

`attribution` 不再自动宣称“精确因果”。可将规则支持的**观察标签**设为 `bottleneck_shift / bottleneck_relief / transfer_increase / processing_increase / cost_tradeoff / no_effect`。只有实际触发不可行结果时才用 `invalid_solution`；合法状态由 DP 生成，一般不存在 `parity_violation`。

### 4.3 `PerturbationProbe`（可选，非第一阶段交付）

只保留可行的固定序列 state substitution、跨机器人 move 与相邻 swap。`drop_task` 产生不完整解，只能作为 partial-route 诊断，不能用其 makespan 与完整解比较。每条探针都需标注是否使用 Exact-DP、额外评价次数与耗时；不进入正式在线 ALNS 的候选选择。

## 5. LLM 反馈级别：先简化，后扩展

| 反馈模式 | 内容 | 作用 |
|---|---|---|
| `F1_scalar` | 真实 makespan / top-weak / 可行性 | 保留基准 |
| `F2_state` | F1 + 路线成本、瓶颈与 DP 状态链高亮 | 推荐第一步 |
| `F2_contrastive` | F2 + 同一部分解的双 Repair 行为对比 + 规则化可选建议 | 研究核心候选 |
| `F2_probe`（后置） | 上述 + 受控扰动/替代状态代价 | 只有前两者不足时实施 |

原 v0.1 中 F0、F1、F2、F2′ 可作为历史对照名称，但不要为实现最小原型而强制创建全部反馈臂。`F2_contrastive` 的对照应优先选择**真实获益和失败各一例**，每份 prompt 不超过 3 条主要案例和 5 条 highlights。

`hypotheses` 采用**确定性规则模板**，只根据实际可重复计算的 `changed_tasks`、makespan、瓶颈转移和成本分解生成 1–2 条**可选思路**；同一次现有 LLM 修订请求可自主选择策略，不新增单独的假设生成 LLM 调用。

若未来比较 F2 与 F2_contrastive，要记录 prompt tokens 与 DP 评价成本。若包含额外探针，就不能声称仅改变“信息表述形式”；应作为证据预算也变化的扩展实验。

### 修订后的反例反馈示意

> 同一 partial solution 上，Repair A 与 Repair B 的完整 makespan 分别为 152、141。B 将任务 37 从机器人 2 插至机器人 4；各路线真实 DP 评价显示，`Δmean_processing=-2, Δmean_transfer=+5, Δload_excess=-14`，因此 `Δmakespan=-11`。这反映“移动成本上升但瓶颈负载降低”的折中。**可选修订方向**：插入评估同时比较目标路线的预估负载和全局最大路线，不只贪婪降低总移动成本。该指令基于完整 Repair 后对照，不声称任务 37 的单次移动独立导致全部收益。

## 6. 四个未决技术问题的决定

**Q1：MST 下界**：`core/lower_bounds.py` 当前没有区域间 MST 实现。**决定：第一阶段不实现 MST。** 先使用真实成本画像、瓶颈与保守 `simple_average_processing_lb`；若后续确需 MST，再基于矩形角点最小距离实现独立、经过小例证明的路线转移下界。

**Q2：状态替代代价与缓存**：当前 `RouteDPEvaluator._cache` 以 `tuple(route_task_ids)` 为键，不包含强制状态约束，不能将“强制某状态的求值”用同一个 `evaluate_route(route)` 缓存键处理。**决定：不要修改原 DP/缓存。** 在只读分析模块上，从 `states_by_task` 与 `CostMatrix` 构造局部前/后向 DP 表，计算 `Q_j(s)`。只有固定路线、固定实例参数和状态图时该数值才有意义。

**Q3：hypotheses 来源**：第一阶段仅用确定性模板生成；LLM 仍在已经预算内的修订调用中自由设计代码。若尝试额外 LLM 总结，应独立计费和单列消融，不破坏等预算比较。

**Q4：Counterfactual 重放**：当前 `prepare_paired_repair_cases()`、`evaluate_paired_repair_candidates()` 及 E7 的 `pair_inputs.json` 重放已经能够冻结并共享 `full_solution / partial_solution / removed_tasks / seed / fixed_destroy_hash`。E10-B 也已有真实配对案例和状态快照。**决定：直接复用，不再开发新的重放引擎。**

## 7. 算子集合：离线确定成员与数量，不让 LLM 直接决策

### 7.1 起点与候选预算

以现有 vNext 的 `3 个人工 Destroy + D*` 和 `3 个人工 Repair + R_aux` 为基线。第一轮最多增加 1 个新 LLM Destroy、1 个新 LLM Repair；允许最后仍保留原池。先在 development 生成少量合法多样化候选，不直接部署所有候选。

LLM 的职责：读取少量 DP 反例与算子源码，提出不同策略的候选；实验的职责：决定是否加入。避免仅以源码编辑距离判断互补，也不预设“瓶颈/空间/HV”类别必然有效。

### 7.2 质量、可靠性与成本初筛

检查可调用性、合法性、fallback、运行耗时、在固定输入上的真实 makespan。固定输入评价用于快速淘汰，不直接决定正式算子池。候选必须再通过少量短预算完整 ALNS 实验。

### 7.3 边际贡献选择

对当前算子池 S 与候选 h，在相同 development 实例、seed、统一时间预算下，定义

\[
\Delta(h\mid S)=\frac1N\sum_{j=1}^{N}\frac{M_j(S)-M_j(S\cup\{h\})}{M_j(S)}.
\]

候选只有满足可行性/可靠性要求且增量收益超过预先设定的开发集门槛、并获得独立 validation 支持时才考虑加入。平局优先更小、更快的集合。所有失利结果保留。

**重要：** ALNS 的 roulette 会因为加入成员改变选择概率，因此 `M_j(S∪{h})` **可能更差**；本问题的集合收益不天然单调、也不能直接援引 EoH-S 的超模性结论。最终验证的是**给定在线选择策略与固定时间预算下的实际收益**。

## 8. 成本感知的 ALNS 自适应奖励（轻量、可关闭）

保留 vNext 的 SA、独立 Destroy/Repair roulette 与基础 `8/3/1/0` 奖励。增加可配置开关 `cost_aware_reward`，关闭时与原版行为一致。

初始建议：

\[
r_t^{cost}=r_t\cdot \min\left(1,\sqrt{\frac{t_{ref}}{\max(t_t,\varepsilon)}}\right)
\]

`r_t` 为原有阶段奖励，`t_t` 是本次完整 Destroy–Repair 及必要评价/局部搜索的实际耗时，`t_ref` 是 development 预先固定的**同规模参考周期耗时**。相同奖励修正用于所选 Destroy 与 Repair，作为第一版低侵入式方案；它**不能**证明收益应归因于哪一个算子。

已存在 `destroy_seconds`、`repair_seconds`、`partial_evaluation_seconds`、`local_search_seconds` 和迭代耗时记录，可直接复用。保持权重更新 `segment_length=20`、`reaction_factor=0.2`，仅小幅修改奖励传入值，不改接受准则或模仿 E6 耦合选择。记录 `selection/accept/global-best/fallback/runtime`；候选回退不得获取虚假的正向奖励。

先独立验证成本感知奖励是否增加固定时间内的有效搜索与完整 makespan 改善，再把它与候选池增量筛选组合。不要一次改动所有模块而无法判断效果。

## 9. 推荐实施路线（与主线性能目标对齐）

**P0 — DP 反馈数据正确性（设计与最小只读实现）**：首先修正三通道、slack、verdict 等定义。复用 `RouteEvaluation` 和 E10-B snapshots，在既有案例验证 `P+V=C_r` 与 `max C_r=M`。只为当前输出缺少的字段加少量适配，不重写 Route-DP。

**P1 — 成本感知奖励（优先落地）**：保持原算子池，新增开关并用少量 development 实例比较 vNext vs vNext+cost。无可靠收益就关闭，不阻断研究。

**P2 — DP 对照反馈的有限 LLM 生成**：基于真实同一 partial solution 的获益/失败案例，生成少量新 Destroy/Repair；复用当前 candidate loader、bounded worker、反馈模板，不重新建立完整演化平台。

**P3 — 算子池增量构建**：每类最多纳入 1 个新成员，固定短预算完整 ALNS 比较；达不到增量门槛就维持原 4×4。优先选择跨结构场景稳健、耗时和 fallback 可控的成员。

**P4 — 冻结与论文对比**：一旦验证集支持，冻结 Proposed-final、算子源 hash、配置、生成预算和数据身份。之后才在未用于开发的 test 数据上比较 B1、四篇文献适配方法（Greedy 与必要的 Exact 强基线）。如实记录离线 LLM tokens/调用、在线求解时间、失败与负面结果。

建议不要先开发完整的 F0/F1/F2/F2′ 四臂和全量敏感性探针。真正对论文必要的最小机制对照是 `原 vNext / +成本奖励 / +DP 对照生成算子 / +组合`，且只在开发与验证完成后选定有限消融。

## 10. 验收条件

1. **模型正确**：出口奇偶映射与当前 `state_generator.py` 一致；使用每个实例自己的 `sweep_speed/travel_speed/sweep_width/turning_time`。
2. **代价一致**：各路线 `sweep+turn+transfer=route.total_cost`；`max_r(route.total_cost)=makespan`；全局 `mean_processing+mean_transfer+load_excess=makespan`。
3. **状态替代代价一致**：只读前/后向最小边际结果与若干独立、无缓存污染的受约束小例枚举一致；`Δ>=-数值容差`；近似 0 表示可替代而非刚性。
4. **重放一致**：相同完整父解、部分解、移除任务、seed、实例参数和 hash，重放得到一致的真实 Repair 输出；父子判决基于 makespan。
5. **预算可控**：LLM 请求/有效候选/DP 评价/真实耗时/tokens 均记录；记录和反馈不能污染在线 ALNS 随机数或优化状态。
6. **算子池真实增益**：以完整 ALNS 在相同实例、seed、时间预算下的配对改善为选择依据；允许新算子全部被拒绝。
7. **性能与研究底线**：冻结版本可复现、解完整可行，Proposed 与对比算法均遵守相应统一预算和独立算法身份；不借缩减文献算法能力宣称更优。

## 11. 文献与新颖性边界

- **EoH-S（AAAI 2026）**已研究 LLM 设计互补启发式集合，不能将“保留多个候选”单独称为首创。
- **ReVEL/RouteRepair 类**研究已涉及行为反馈、失败反例修订，不能单独将“提供反例”称为首创。
- 当前拟研究的特定组合是：**MR-RCRP 合法状态链和精确路线成本形成的对照证据、在相同 partial-solution 上的 LLM 算子修订、有限预算下的成本感知增量部署**。组合的新颖性仍需后续严谨文献核查和消融证明。

## 12. 当前实施授权边界

本 v0.2 文档是**修订后的方法设计**，不是代码变更命令。原文的“本轮不修改 `src/`”约束在审阅阶段继续成立。若进入实施，应分 P0/P1/P2/P3 独立给 Codex 下发最小改动任务，并保存旧版算法与结果。
