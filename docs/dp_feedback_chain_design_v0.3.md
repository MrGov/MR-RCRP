# MR-RCRP：DP 证据驱动的 LLM 算子设计（设计定稿 v0.3）

> 状态：**定稿，作为实施基线**。口径已锁定（A + b），公式已收敛，验收条件可执行。
> 授权边界：本文**不授权修改**已冻结的 B1、Route-DP、数学模型、测试数据与 `Proposed-original/vNext`。当前阶段只允许新增**只读**模块与测试（见 `task_P0prime_state_regret_instrument.md`）。
> 未执行声明：文中引用的所有代码位置只经静态阅读确认，**尚未运行任何新增代码或测试**；凡标「待执行」的均为待验证项。
> **部分取代（2026-10-30）**：P0″ 实测数据显示状态层是窄杠杆（846 个位置中 71.3% 并列、仅 28.7% 有信息），故本文 §3 的仪表优先级与 §4 的三档反馈内容已由 `docs/p2_feedback_design.md` 取代；§1 两口径、§5 四臂、§6 草稿/部署解耦、§7 成本奖励、§8 统计、§10 验收仍然有效。

---

## 0. 与 v0.2 的关系

| 项 | v0.2 | v0.3 |
|---|---|---|
| 研究口径 | 未定（演化 vs 一次性暧昧） | **口径 A：一次性设计**（§1.1） |
| 成本奖励 | `cost_aware_reward`，四项耗时，未定预算前提 | **`iteration_cost_penalty`**，绑定固定墙钟预算（§1.2, §7） |
| `Q_j(s)=F_j(s)+B_j(s)` | 只给了公式，未钉死 `P_j` 计次 | 钉死定义 + **自检恒等式**（§2.2） |
| 状态替代代价 | 「可选、只用于少量案例」 | **升格为必需字段**（§3 I3） |
| `F2_probe` | 后置 | **删除** |
| I4 / MST / 三通道上界 | 降级但保留 | **删除**，仅保留 `route_load_excess` 描述量 |
| 候选数量 | 每类最多 1 个（与 F2_contrastive 矛盾） | **草稿 3 个 / 部署 ≤1 个**（§6） |
| `t_ref` | development 固定常数 | **运行时标定**（§7.3） |

---

## 1. 两个已确定的口径

### 1.1 口径 A：一次性设计，不是多轮演化

**一句话主张：**

> 在相同的 LLM 调用预算与相同的候选评价预算下，以精确 Route-DP 导出的**状态链证据**与**同输入 A/B 对照证据**作为反馈，能让 LLM **一次**设计出更强的 Destroy/Repair 算子；这些算子在固定时间预算的完整 ALNS 中带来可测量的边际收益。

由此派生三条硬约束：

1. **不主张**演化、种群、交叉、代数累积、行为互补集合。vNext 中 `evolution_loop` 的多轮语义保留为实现细节，但**不作为论文主张**；对外表述统一为 `candidate → evaluate → select → freeze` 单轮流水线。
2. **不主张**算子集合的互补性（原 C2 / EoH-S 对照）。原因：roulette 概率会随成员变化，集合收益不单调，单凭增量无法证明互补。集合只作为「部署 ≤1 个新算子」的最小扩充。
3. **不主张**迭代生成更好的算子（例如「第 k 代优于第 k−1 代」）。凡此类表述一律从论文与代码注释中撤除。

### 1.2 口径 b：迭代成本惩罚

- 正式名称：`iteration_cost_penalty`（**不再**叫 `cost_aware_reward`，避免暗示「奖励更快的算子」）。
- 语义：对**本次迭代整体**偏贵这一事实做奖励折减，作用是让固定墙钟预算花在更多迭代上；**不归因到具体某一个算子**。
- 前提：只有在 `max_runtime_seconds` 生效（固定墙钟预算）时才可能有非零效果。若对比实验按固定迭代数运行，该机制**按构造无效**，不得据此声称"机制无效"。

---

## 2. 定稿的状态与代价定义

### 2.1 唯一实现与唯一公式

- 状态机、扫描次数、出口奇偶映射：**唯一实现** `core/state_generator.py`（`_compute_n_sweeps` 66–71 行、`_compute_processing_time` 74–86 行、`_determine_exit_corner` 89–121 行）。本文不另造规则。
- 每个任务 8 个状态 = 4 个进入角 `{LB,LT,RB,RT}` × 2 种模式 `{H,V}`；出口角由 `(进入角, 模式, n_sweeps 奇偶)` 唯一确定。
- 参数一律取实例自身字段：`instance.sweep_width / sweep_speed / travel_speed / turning_time`（`core/instance_loader.py:69` 解析）。**禁止**沿用来源 PDF 示例的 `v=1, δ=2, τ=0.5`。

对任务 $i$、模式 $m$：

$$N_i^H=\max(1,\lceil h_i/\delta\rceil),\quad N_i^V=\max(1,\lceil w_i/\delta\rceil)$$

$$P_i(H)=\frac{N_i^H w_i}{v_s}+(N_i^H-1)\tau,\qquad P_i(V)=\frac{N_i^V h_i}{v_s}+(N_i^V-1)\tau$$

路线 $r=(i_1,\dots,i_k)$ 与状态链 $s_1,\dots,s_k$：

$$C_r=\underbrace{\sum_j P_{i_j}(s_j)}_{\text{processing}}+\underbrace{\frac{d_1(0,\mathrm{entry}(s_1))}{v_t}+\sum_{j<k}\frac{d_1(\mathrm{exit}(s_j),\mathrm{entry}(s_{j+1}))}{v_t}+\frac{d_1(\mathrm{exit}(s_k),0)}{v_t}}_{\text{transfer}}$$

$$M(S)=\max_{r=1}^{R} C_r,\qquad \text{空路线 } C_r=0$$

其中 $v_t=\texttt{instance.travel\_speed}$，$d_1$ 为曼哈顿距离（`utils/geometry.py`，`core/cost_matrix.py` 以 $/v_t$ 预计算）。

**限定（v0.1 错、v0.2 已修，此处定稿）**：$P_{i_j}(s_j)$ 与该任务在路线中的位置无关；但**重新排序后重跑 DP，最优 H/V 可能改变**，故「顺序不影响覆盖时间」仅在**状态链不变**时成立。

### 2.2 状态替代代价与 regret 向量（本稿最关键的定义）

对**固定任务序列** $r=(i_1,\dots,i_k)$，定义

$$
F_1(s)=\frac{d_1(0,\mathrm{entry}(s))}{v_t}+P_{i_1}(s)
$$
$$
F_j(s)=\min_{s'\in\mathcal S_{i_{j-1}}}\big[F_{j-1}(s')+t(s',s)\big]+P_{i_j}(s),\quad j\ge 2
$$
$$
B_k(s)=\frac{d_1(\mathrm{exit}(s),0)}{v_t}
$$
$$
B_j(s)=\min_{s'\in\mathcal S_{i_{j+1}}}\big[t(s,s')+P_{i_{j+1}}(s')+B_{j+1}(s')\big],\quad j\le k-1
$$
$$
\boxed{Q_j(s)=F_j(s)+B_j(s)},\qquad \Delta_j(s)=Q_j(s)-C_r^{*}
$$

**计次约定（必须写死在实现里，这是最容易错的一步）：**
- $F_j(s)$ = 到达并**完成**任务 $i_j$ 于状态 $s$ 的最小前缀成本，**含** $P_{i_j}(s)$；
- $B_j(s)$ = 从任务 $i_j$ **完成后**状态 $s$ 出发、经剩余任务返回 depot 的最小后缀成本，**不含** $P_{i_j}(s)$；
- 故 $P_{i_j}$ 在 $Q_j$ 中**恰好计一次**。若两端都含，$\Delta_j$ 系统性偏高约 $P_{i_j}$（几十秒量级），会把所有任务误标为「状态刚性」。

**三条自检恒等式（可执行为断言）：**

1. 对所有 $j$：$\min_{s\in\mathcal S_{i_j}} Q_j(s)=\min_s Q_j(s)=C_r^{*}$；
2. 对所有 $j$：$Q_j(s_j^{*})=C_r^{*}$，其中 $s_j^{*}$ 是实际最优链在位置 $j$ 的状态；
3. 对所有 $j,s$：$\Delta_j(s)\ge -\varepsilon$（$\varepsilon=10^{-9}$）。

恒等式 1、2 同时成立的唯一解释是 `F`、`B` 都按上式定义且 `P` 只计一次——这是本模块的主验收条件（见任务单 T5）。

**tie-break（必须固定）**：$\Delta_j$ 的排序键取 `(Q_j(s), state_id)` 升序。禁止依赖字典/集合迭代顺序，否则同一实例两次运行会给出不同的「刚性」标签，反馈不可复现。

**成本**：一次前向 + 一次后向 = $O(k\cdot 8^2)=O(64k)$，与一次路线 DP 同阶（`core/dp_evaluator.py` 的 DP 亦为 $O(64k)$）。因此「全任务全状态 regret 表」不是奢侈品，**每路线额外一次 DP 的量级**即可获得，故 v0.3 将其升格为必需字段。

**边界**：该表只在「固定序列 + 固定实例参数 + 固定状态图」下有定义。任务集合或序列改变后必须重算，**禁止跨解复用**。

### 2.3 腿分解（I0）

每条路线 $r$：

$$C_r=\underbrace{\sum_j \frac{N_{i_j}(s_j)\,L_{i_j}(s_j)}{v_s}}_{\text{sweep}}+\underbrace{\sum_j \max(0,N_{i_j}(s_j)-1)\,\tau}_{\text{turn}}+\underbrace{\sum_{m=0}^{k} d^{(m)}/v_t}_{\text{transfer}}$$

其中 $L_i(H)=w_i$、$L_i(V)=h_i$；transfer 项即 `RouteEvaluation.transition_costs` 之和（首项 depot→首状态、末项末状态→depot，`core/dp_evaluator.py:124–130`）。

> 注：该分解**已存在**于 `experiments/e10b_structural_dp_analysis.py:60–80` 的 `snapshot()`（且第 73 行有 `travel+coverage+turning==total_cost` 断言）。P0′ 只需在 `core/` 层提供一个不依赖 `experiments/` 的同构实现，供后续反馈构造直接调用。

### 2.4 全局目标的代数分解（仅用于描述）

$$\bar P=\tfrac1R\textstyle\sum P_r,\quad \bar V=\tfrac1R\sum V_r,\quad B=\max_r C_r-\tfrac1R\sum C_r\ \Rightarrow\ M=\bar P+\bar V+B$$

空路线计入 mean（$C_r=0$），否则恒等式不成立。$B$ 是**最大负载超额量**，是与覆盖、移动并列的**均衡描述量**，不是第三种物理成本。父子解差异同时记录 $(\Delta M,\Delta\bar P,\Delta\bar V,\Delta B)$，**不做因果归因**。

---

## 3. 仪表清单（定稿）

| 编号 | 名称 | 状态 | 内容 |
|---|---|---|---|
| **I0** | 腿分解 | 必需 | 每路线 `sweep / turn / transfer / total`，回算后与 `total_cost` 对拍 |
| **I1** | 瓶颈画像 | 必需 | 每路线 `cov_share / transfer_share`、旧/新瓶颈路线、`route_load_excess` |
| **I2** | 状态链 | 必需 | 每任务 `(task_id, route_id, position, state_id, entry, mode, exit, n_sweeps)` |
| **I3** | **状态 regret 向量** | **必需（v0.2 为可选）** | 每任务 8 个状态的 $Q_j(s)$、$\Delta_j(s)$、选中状态排名、近似并列集合 |
| I4 | 作用域上界 | **删除** | MST 界、`mode_processing_gap` 一律不进反馈；`transfer_share` 仅作描述 |

**删除 I4 的理由**：这些量要么理论不严谨（MST 需在角点最小距离图上重建，且只是 transfer 下界而非 makespan 上界），要么存在误读风险（把 `mode_processing_gap` 当成可获得的改善）。v0.3 只保留能**精确回算并断言**的量。

**I3 升格的理由（对审稿人的核心回答）**：它是整套设计里**唯一任何标量反馈、排名反馈或失败日志基线都无法伪造的信号**——「同一固定序列下，其余 7 个状态的精确最优代价」。审稿人必然追问「你的状态链比 RouteRepair 类失败日志到底多给了什么」，答案就是这一张表。且其成本仅一次前向+一次后向（§2.2）。

---

## 4. 反馈等级（三档）

| 档位 | 内容 | 角色 |
|---|---|---|
| `F1_scalar` | makespan、相对改善、可行性、top/weak 汇总 | 基线臂（等价现有 `build_feedback_payload`） |
| `F2_state` | F1 + I0 腿分解 + I1 瓶颈画像 + I2 状态链高亮 | 中间臂（信息量阶梯） |
| `F2_contrastive` | F2_state + **同一 `input_id` 上的双 Repair A/B 对照**（获益一例、失败一例）+ **I3 regret 向量**（限于 `changed_tasks`） | 主臂 |

**规则**

1. `F2_contrastive` 的对照必须来自**同一 `partial_solution` + 同一 `removed_tasks` + 同一 `solver_seed` + 同一 `fixed_destroy_hash`** 的两次适用真实 Repair，判决按 makespan 与统一数值容差。
2. 每份 prompt 最多 3 条主要案例、5 条 highlights（沿用 v0.2 §5）。
3. `revision_directions` 用**确定性规则模板**生成，1–2 条，**不新增 LLM 调用**；同一次修订请求内由 LLM 自行选择是否采纳。
4. 每条证据必须带 `source`（可回指到 `trials/{i}` 或 `inputs/{instance_id}.json`）与 `limitations`；`unavailable` 必须显式写出，**不得填 0**。
5. 禁用词：`造成 / 由于 / 导致`（除有控制变量的受控试验支持）；统一用 `伴随 / 与…可能有关`。
6. 反馈中**不得**把 `state_switch / hv_mode_switch / cascade` 表述为损失、罚项或越小越好。模型中没有相邻任务模式切换罚项，此点已由现有 `feedback_builder.py:53,96` 的正确表述确认，须继续沿用。

---

## 5. 实验臂与假设

### 5.1 四臂

| 臂 | 内容 | LLM 调用 | 用途 |
|---|---|---|---|
| `A0` | B1 手工 4×4 算子池，无 LLM | 0 | 非 LLM 基线 |
| `A1` | 一次性设计，反馈 = `F1_scalar` | 2 类 × 3 草稿 | 反馈基线 |
| `A2` | 一次性设计，反馈 = `F2_state` | 同上 | 机制分解 |
| `A3` | 一次性设计，反馈 = `F2_contrastive` | 同上 | **主臂** |

### 5.2 等预算协议（必须逐项记录并在论文中披露）

| 维度 | 约束 |
|---|---|
| 模型 / 温度 / max_tokens | 四臂完全相同，运行前冻结 |
| 调用次数 | 每臂每类 3 次（3 个草稿），**总调用次数完全相同** |
| 提示词模板 | 同一模板，仅 `feedback` 段的**内容字段**不同 |
| 候选评价 | 每候选在同一批 development `input_id` 上评价，预算相同 |
| 采样随机性 | provider seed 固定并记录；无 stateful 重试 |
| 记账 | `llm_calls / prompt_tokens / completion_tokens / candidate_count / valid_count / fallback_count / dp_calls / wall_seconds` |

### 5.3 假设

- **H6′（机制，主检验）**：同预算下，`A3` 产出的算子集合的边际收益 $_\Delta(h\mid S)$ 优于 `A1`；双侧 95% CI 下界 $>0$。
- **H6″（信息阶梯，探索性）**：`A2 > A1` 且 `A3 > A2`。此条只作机制描述，**不进入确认性层级**（阶梯非单调时不得反推「DP 证据无效」）。
- **H1a′（部署，确认性）**：`A3` 冻结算子池在 fixed wall-clock 预算下的 makespan 优于最强非 LLM 对比算法；沿用 `docs/statistical_analysis_plan.md` 的 MCID = 0.02 相对改善与 H1a/H1b 嵌套判定。
- **H-iter（成本惩罚）**：`A0 + iteration_cost_penalty` 在**固定墙钟预算**下不劣于 `A0`，且单位时间有效迭代数上升。若 CI 跨 0 则关闭该机制（文档已允许）。

> **需要你确认的连带修改（本文不自行改动这些文件）**：`docs/research_hypotheses.md` 的 H1 标题含 "Multi-Round Evolved"，与口径 A 冲突，需改为单轮口径；`docs/ablation_plan.md`、`docs/innovation_review.md` 中凡「演化 / 互补集合」的表述需相应下调。

---

## 6. 候选池：草稿冗余，部署精简

**生成与部署解耦**（这是 v0.2 的逻辑缺口，必须修）：

1. **草稿阶段**：每类生成 $N_{\text{draft}}=3$ 个策略不同的候选，**不部署、不进 ALNS 池**。
2. **对照阶段**：3 个草稿 + 现有手工算子，在同一批 `input_id` 上互相 A/B（`evaluate_paired_repair_candidates` 接受算子列表，见 `experiments/e7_cooperative_evolution.py:120`），产生 `F2_contrastive` 的获益/失败案例。
3. **部署阶段**：按边际贡献只保留 $\le 1$ 个新 Destroy 与 $\le 1$ 个新 Repair。

**边际贡献**（同实例、同 seed、同一固定墙钟预算、配对）：

$$\Delta(h\mid S)=\frac1N\sum_{j=1}^{N}\frac{M_j(S)-M_j(S\cup\{h\})}{M_j(S)}$$

**门槛必须在看到结果前预注册**，且设在噪声之上：

1. 先在 development 上跑 **$S$ 对 $S$（自身重跑、不同 seed）的 null 分布**；
2. 部署门槛 = null 分布 95 分位（或 MCID，取较大者）；
3. `seeds ≥ 5`，报告配对差中位数 + bootstrap CI，不只报均值；
4. **允许全部候选被拒**，失败结果照常记录。

> 注意：加入成员会改变 roulette 选择概率，故 $M_j(S\cup\{h\})$ 允许更差；本问题**不援引** EoH-S 的超模性结论。

---

## 7. 迭代成本惩罚（口径 b）

### 7.1 公式

$$r_t^{\text{cost}} = r_t\cdot \min\!\Big(1,\ \sqrt{t_{\text{ref}}/\max(t_t,\epsilon)}\Big),\qquad t_t = t^{\text{destroy}}+t^{\text{partial\_eval}}+t^{\text{repair}}+t^{\text{local\_search}}$$

- $r_t\in\{0,8,3,1\}$ 沿用现有奖励（`heuristics/alns_solver.py:336–344`）。
- $t_t$ 复用 `measured_stage_seconds`（`alns_solver.py:421`），四段计时字段均已存在（304 / 309 / 314 / 327 行）——**不新增计时探针**。
- 同一乘子同时作用于所选 Destroy 与 Repair。这是**已知的归因缺陷**，因此该机制不得用于证明「某算子更好」，只用于 anytime 效率。
- 保持 `segment_length=20`、`reaction_factor=0.2` 与 SA 接受准则不变；不改接受准则、不引入 E6 的耦合选择。
- 回退不得获得正向奖励：现有 `reward_attribution` 已实现 `ambiguous_excluded` / `fallback_excluded`（`alns_solver.py:365–393`），乘子在**其后**施加，不得覆盖该逻辑。

### 7.2 开关

新增 `ALNSConfig.iteration_cost_penalty: bool = False`（`alns_solver.py:43–69` 的 dataclass 内），默认关闭 = 与原版**逐位一致**。开启时额外要求 `max_runtime_seconds is not None`，否则在 `__post_init__` 抛错——这是把 §1.2 的前提写成代码约束。

### 7.3 `t_ref` 运行时标定（替代 v0.2 的固定常数）

1. 求解开始前，对该实例清空缓存后连续跑 $K=20$ 次固定路线的 `evaluate_route`，取中位数 $t_{\text{probe}}$；
2. $t_{\text{ref}}=\kappa\cdot t_{\text{probe}}$，$\kappa$ **预先固定**（建议 8.0，需在 development 上校准一次后冻结）；
3. 冻结记录与结果元数据写入：`K`、`t_probe`、`kappa`、`t_ref`、CPU 型号/核数、Python 版本；
4. 目的：使 $t_{\text{ref}}$ 成为**相对量**，跨机器可比，满足可复现验收。

### 7.4 边界

- 只在固定墙钟预算下有物理意义（§1.2）。
- `min(1,·)` 意味着**只能折减、不能加成**：$t_t<t_{\text{ref}}$ 时乘子恒为 1。$\kappa$ 的选择因此极敏感，必须预注册。
- 若 development 上 `A0 + penalty` 未显示单位时间有效迭代数上升，直接关闭，**不阻断后续阶段**。

---

## 8. 统计与数据切分

**完全沿用现有 SOP，不另立标准**：`mrta_rect_coverage/docs/statistical_analysis_plan.md`

- 独立实验单元、两阶段聚合、two-way cluster bootstrap（5000 resamples）——照用；
- MCID = 0.02（预注册，仅可在 train/dev-only pilot 中经新 protocol version 修改）；
- 四轴 outcome taxonomy（`statistical_analysis_plan.md` §8）——照用；
- 数据切分：`evolution-development` → `selection-validation` → `confirmatory-heldout` → `final-test` lockbox；
- **反馈所引用的 `input_id` 只能来自 development**；validation / heldout / final-test 的实例**永不进入任何 prompt**。此条是口径 A 的成立前提，须写入 manifest 校验。

---

## 9. 实施阶段

| 阶段 | 内容 | 触碰冻结代码 | 前置 |
|---|---|---|---|
| **P0** | 本文档 + 定义定稿（已完成） | 否 | — |
| **P0′** | 只读仪表：I0 / I2 / I3 + 一致性断言 + 测试 | **否**（仅新增文件） | P0 |
| **P1** | `iteration_cost_penalty` 开关 + `t_ref` 标定 + `A0 vs A0+penalty` | 是（`alns_solver.py`，受开关保护） | P0′ |
| **P2** | `F2_state` / `F2_contrastive` 反馈构造 + 3 草稿生成 + A/B 对照 | 是（`feedback_builder.py` / `prompt_builder.py`） | P0′, P1 |
| **P3** | null 分布 + 门槛 + 部署筛选 | 是（新增 runner） | P2 |
| **P4** | 冻结 + 文献对比（Greedy 与必要 Exact 强基线） | 否 | P3 |

**执行力纪律**：每阶段独立下发最小改动，保留旧版算法与结果；不得一次性改动多模块导致无法归因。

---

## 10. 验收条件

1. **状态机一致**：对全部任务枚举 8 状态，出口角 == `_determine_exit_corner` 结果；`n_sweeps` 与 `N_H/N_V` 公式一致（含 `max(1,·)`）。
2. **代价一致**：每路线 `sweep + turn + transfer == total_cost`（容差 1e-6）；`max_r(total_cost) == makespan`；全局 `P̄ + V̄ + B == makespan`（空路线计入 mean）。
3. **regret 表一致**：§2.2 三条恒等式全部成立；且与「暴力枚举全部 8^k 状态链」的独立计算结果一致（小例，k ≤ 3）。
4. **只读性**：生成报告前后的 `RouteDPEvaluator.statistics()["calls"]` 不变（证明未触发 DP 重算）；连续两次生成结果逐字节一致（证明 tie-break 固定）。
5. **重放一致**：相同 `input_id` / 父解 / 移除集 / seed / 实例参数，重放得到一致的真实 Repair 输出；父子判决基于 makespan。
6. **预算可控**：`llm_calls / tokens / candidate_count / dp_calls / wall_seconds` 全部记录；记录与反馈不得污染在线 ALNS 的随机数或优化状态。
7. **pool 增益真实**：以完整 ALNS 在同实例、同 seed、同墙钟预算下的配对改善为唯一依据；允许新算子全部被拒。
8. **可复现**：冻结版本可复现；`t_ref` 标定记录（`K / t_probe / kappa / 机器指纹`）随结果保存；Proposed 与对比算法各守其身份，不通过削弱基线证明创新。

---

## 11. 明确不做的事

1. 不做多轮演化、种群、交叉、代数对比（口径 A）。
2. 不实现 MST 下界、`mode_processing_gap`、三通道上界（I4 已删）。
3. 不修改 `RouteDPEvaluator` 的缓存键，不在其中容纳「强制状态」约束（核验：`core/dp_evaluator.py:27,42–45` 的键为 `tuple(route_task_ids)`）。
4. 不新建配对重放引擎（复用 `prepare_paired_repair_cases` / `evaluate_paired_repair_candidates`）。
5. 不新增「假设生成」LLM 调用（用确定性规则模板）。
6. 不使用弹窗、不自动宣称因果关系、不在反馈中编造 DP 指标。
7. 不把 `state_switch / hv_mode_switch / cascade` 当损失或罚项。
8. 不在本轮修改 `Proposed-original/vNext` 与对比算法的评估模式。
