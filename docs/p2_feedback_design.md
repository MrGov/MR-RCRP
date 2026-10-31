# P2 反馈结构设计（v0.1，由 P0″ 实测数据定稿）

- 状态：§7 三项取舍已拍板（冻结 / 保留 / 是），阈值与 `kappa` 均已冻结并记录于 §7、§7b
- 取代关系：本文取代 `docs/dp_feedback_chain_design_v0.3.md` 的 §4（反馈档位）与
  §3（仪表优先级）中的「状态链为头条证据」表述；v0.3 的 §1 两口径、§5 四臂、
  §6 草稿与部署解耦、§7 成本奖励、§8 统计、§10 验收 不变。
- 数据来源：`mrta_rect_coverage/outputs/e14_state_regret_instrument/`
  （22 份报告 / 86 条路线 / 846 个位置，`verify_summary.json` failures = []）。

---

## §0 一句话结论

**状态层在这批实例上不是收益来源，而是结构判别器。** 反馈头条必须换成转移与
均衡；状态证据降级为「位置级注解 + regime 自动判定」，且必须屏蔽 71.3% 的并列区。

---

## §1 三条硬约束（全部由实测数据强制）

### D1 状态层是窄杠杆

| 指标 | 数值 | 含义 |
| --- | --- | --- |
| 有决策信息的位置 | **243 / 846 = 28.7%** | 最近替代严格更差 |
| 并列最优的位置 | **603 / 846 = 71.3%** | ≥2 个状态取得同一最优代价 |
| 8 个状态全等价 | 110（13.0%） | 该任务对状态完全不敏感 |
| 4 个状态并列 | 345（40.8%） | 同模式内 4 角等价（处理时间只依赖模式） |
| informative 位置 \|mode_gap\| 中位 | 24.0（makespan 的 **0.44%**） | 单点最大可动作量 |
| informative 位置 \|mode_gap\| 最大 | 140.0（**5.71%**） | 极端个案 |

阈值分布（占 makespan 比例，全体 846 位置）：

| 门槛 | 位置数 | 占比 |
| --- | --- | --- |
| ≥ 0.25% | 206 | 24.3% |
| ≥ 0.5% | 88 | 10.4% |
| ≥ 1.0% | **34** | **4.0%** |
| ≥ 2.0% | 11 | 1.3% |
| ≥ 5.0% | 1 | 0.1% |

→ 状态选择的最大可动作量集中在 **4% 的位置**上。把「状态后悔」当头条收益信号，
LLM 会被引向 96% 的无关位置。

### D2 并列区必须屏蔽

`chosen_rank` = 824 个 rank1 + 9 个 rank2 + 13 个 rank3：DP 在并列时按内部迭代顺序
选，不是 state_id 序。因此**任何跨运行的「状态链差异」「H/V 切换率」「状态编辑距离」
在并列位置都是 tie-break 假象**，不得进入判决口径，也不得进入反馈正文。

初版仪表（`near_tie_tol=0.0`）报出 583 个零后悔位置；改用数值容差
`effective_tol = max(near_tie_tol, 1e-9)` 后为 603——差出来的 20 个是浮点并列，
属同一类现象，必须归入并列区而不是信息区。

### D3 收益主导项是转移与均衡

86 条父解路线均值：**transfer 79.4%**（65.1%–90.6%）、coverage 16.2%、
turning 4.4%；`load_excess / makespan` 均值 **12.45%**。

### D4 状态证据是 regime 相关的（正面发现，应保留）

按实例族聚合 informative 位置：

| regime | 位置数 | informative | 中位 \|gap\| | 最大 \|gap\| | gap ≥ 1% 个数 |
| --- | --- | --- | --- | --- | --- |
| E10_BASE | 120 | 29.2% | 24.0 | 36.0 | 0 |
| E10_BOTTLENECK | 120 | 20.0% | 18.3 | 65.0 | 2 |
| **E10_HV-GEOM** | 120 | **32.5%** | **66.0** | **140.0** | **28** |
| E10_SPATIAL | 120 | 29.2% | 24.0 | 36.0 | 0 |
| E10_SWEEP-NARROW | 120 | 30.0% | 24.0 | 30.0 | 0 |
| E10_TRAVEL-HIGH | 120 | 29.2% | 48.0 | 72.0 | 0 |
| E10_TURN-HIGH | 120 | 29.2% | 24.0 | 36.0 | 0 |
| R2_T6_0（smoke，6 任务） | 6 | 66.7% | 9.0 | 14.0 | 4 |

- 全部 34 个「gap ≥ 1% makespan」的位置里，**28 个落在 HV-GEOM**（39 个 informative
  位置中的 72%），其余 6 个在 BOTTLENECK（2）与 smoke（4）。
- 模式偏好近均衡（H 109 : V 134），**没有可被学成全局规则的偏置**——证据必须逐位置给。
- 最大 gap 出现在位置 0/1/3/5/7/9 各处 → 状态价值是**顺序中介**的，不是任务固有属性。

→ 结论：状态证据的真正用途是**判定「这个实例/路线上状态层有没有决策空间」**，
并把它变成反馈里的 regime 标签；不是直接报收益。

---

## §2 反馈的证据分级（E1–E5）

每条证据必须带 `source`（文件/字段路径）与 `availability`（`ok` / `unavailable`）；
不 available 时留空并标注，**不得填 0**。

| 级别 | 名称 | 角色 | 数据来源 |
| --- | --- | --- | --- |
| **E1** | 路线成本结构 | 头条 | e14 report：`cost_split`、`route_load_excess`、`bottleneck_routes` |
| **E2** | 配对差分 | 头条 | `evaluate_paired_repair_candidates`（同 `input_id` + 同 seed + 同 `fixed_destroy_hash`） |
| **E3** | regime 自动标签 | 结构 | §3 规则，输入 e14 report |
| **E4** | 位置级状态注解 | 结构（限流） | e14 report：仅 `informative == True` 的位置 |
| **E5** | 禁用指标 | — | switch 计数、cascade 计数、状态编辑距离、平均 regret |

各档位内容下限：

- **E1 必给**：`transfer_share`、每条路线 `cost_split.total` 与 `transfer`、
  `load_excess` 及占比、bottleneck 路线 id 列表、near-bottleneck（cost ≥ 0.95×makespan）。
- **E2 必给**：`Δmakespan`、`Δmean_transfer`、`Δmean_processing`、`Δload_excess`、
  `verdict`（按 makespan + 容差），以及**归因标签降级为观察**：
  `transfer_down` / `balance_improved` / `processing_down` / `mixed`。
- **E3 必给**：regime 名 + 判定用量（例如 `mode_sensitive because 72% of informative
  positions have |mode_gap| ≥ 1% makespan`）。
- **E4 必给**：`(task_id, position, chosen_state_id, mode_preference, mode_gap,
  tied_state_count)`，且 `tied_state_count == 1`；并列位置只以聚合计数出现
  （`tied_position_fraction`）。

---

## §3 regime 自动判定规则（可直接实现）

输入：一份 e14 report（含 `state_degeneracy`、`objective`、`routes[].cost_split`）。
输出：`{regime, evidence}`，`evidence` 记录触发阈值与实测值。

判定顺序（首个命中即返回，保证互斥）：

1. `mode_sensitive`：`share(|mode_gap| ≥ 0.01 × makespan among informative) ≥ 0.25`
   - 数据依据：HV-GEOM = 72%，其余全部 0%（BOTTLENECK 2/24 ≈ 8%，smoke 4/4）。
   - 阈值 0.25 留了 3 倍裕度，且在 7 类真实数据上无假阳性。
2. `balance_dominated`：`load_excess / makespan ≥ 0.15`
3. `turn_heavy`：`mean(turning_share) ≥ 0.06`
4. `transfer_dominated`：`mean(transfer_share) ≥ 0.75`
5. 否则 `mixed`。

实现位置：新增 `llm/operator_evolution/regime_labeler.py`（纯函数、无副作用、
不 import experiments）；单测用 21 份真实 report 做快照对拍。

---

## §4 反馈档位（替换 v0.3 §4）

| 档位 | 内容 | 用途 |
| --- | --- | --- |
| `F1_scalar` | 现状：top/weak operators + makespan 排名 + 失败类型分布 | 基线（对照组） |
| `F2_state_v2` | E1 + E2 + E3 + E4 聚合 | 机制臂第一版 |
| `F2_contrastive_v2` | F2_state_v2 + ≤3 组 E2 配对案例（每组点名 regime 与 bottleneck 路线）+ ≤5 条 E4 位置注解 | **主臂** |

强制规则（在 v0.3 §4 六条基础上新增三条）：

7. **并列屏蔽**：payload 中任何状态相关字段必须能被 `tied_state_count == 1` 过滤；
   并列位置只允许出现在 `tied_position_fraction` 这一个聚合字段里。
8. **量级披露**：每个状态类证据必须同时给出「占 makespan 比例」，避免 LLM 把
   24.0 秒当成大信号（它只是 0.44%）。
9. **limitations 必填**：模板句固定为
   `state evidence is degenerate at {tied_fraction} of positions in this parent set;
   only {informative_fraction} carry a decision signal`。

预算：`F2_state_v2` ≤ 2.5 KB；`F2_contrastive_v2` ≤ 4 KB，其中单案例 ≤ 800 B。

---

## §5 与现有代码的接口（扩展，不重写）

| 目标 | 位置 | 说明 |
| --- | --- | --- |
| 反馈构造 | `llm/operator_evolution/feedback_builder.py` | 新增 `build_state_regret_feedback(report, *, budget)`、`build_paired_contrast(parent_report, child_report, *, budget)`、`summarize_degeneracy(report)`；现有 `build_pair_feedback` / `coverage_mode_knowledge` / `select_decision_knowledge` / `build_feedback_payload` 保留不动 |
| prompt 注入 | `llm/operator_evolution/prompt_builder.py` | `build_revision_prompt` 增加可选 `evidence: dict`，compact 版渲染三段：`STRUCTURE` / `CONTRAST` / `LIMITS` |
| regime 判定 | `llm/operator_evolution/regime_labeler.py`（新） | §3 五条规则 |
| 子代证据 | `experiments/e14_state_regret_instrument.py` | 新增 stage `solutions`：输入 ALNS result JSON 的 `routes`，产同结构 report（这是 P2 唯一需要新增的运行器能力） |
| 配对评价 | `experiments/e7_cooperative_evolution.py:110,120` | 直接复用 `prepare_paired_repair_cases` / `evaluate_paired_repair_candidates`，不新建重放引擎 |

数据流：父代证据 = 现有 22 份 `outputs/e14_state_regret_instrument/parents/*.json`；
子代证据 = e14 stage `solutions` 新产出；配对差分 = e7 的 paired 评价结果。

---

## §6 验收（P2 代码层）

| 编号 | 验收项 |
| --- | --- |
| A1 | 反馈 payload 的字段名白名单断言：出现 E5 任一字段即失败 |
| A2 | 每条 E4 条目满足 `informative is True and tied_state_count == 1` |
| A3 | `F2_state_v2` ≤ 2.5 KB、`F2_contrastive_v2` ≤ 4 KB（序列化后字节数） |
| A4 | regime 判定在 21 份真实 report 上与实例名前缀一致率 100%（sanity，不作结论） |
| A5 | 同输入两次构造 payload 字节完全相同（确定性） |
| A6 | 反馈构造过程零 LLM 调用（mock provider 计数断言） |
| A7 | 缺少某证据源时 payload 保留键并标 `unavailable`，不出现 0 |

---

## §7 三项取舍：已拍板（用户 2026-10-30 决定：冻结、保留、是）

1. **regime 阈值现在冻结**（已采纳）。
   冻结值：`mode_sensitive` = informative 位置中 `|mode_gap| ≥ 1% makespan` 的占比 `≥ 0.25`；
   `balance_dominated` = `load_excess / makespan ≥ 0.15`；
   `turn_heavy` = `mean(turning_share) ≥ 0.06`；
   `transfer_dominated` = `mean(transfer_share) ≥ 0.75`；否则 `mixed`。
   这些数字在 P2/P3 的任何结果产生之前写死，不得在看到 H6′ 结果后调整；
   调参即等于事后选择，直接毁掉机制对照的可信度。
2. **E4 位置级注解保留**（已采纳），并限流：每案例 ≤5 条、仅 informative 位置、
   必须同时给出占 makespan 的比例。数据说 71.3% 位置无信息，但它仍是唯一
   任何标量/失败日志基线都无法伪造的信号。
3. **「状态价值是顺序中介的」写入 hypotheses 模板**（已采纳）。
   固定句（英文原样进模板）：
   `a mode_gap is only realisable if the operator also changes the neighbouring
   legs; state evidence alone cannot raise makespan gains`.
   它是 D4 的直接推论，也是防止 LLM 追求「状态优化」假收益的护栏。

---

## §7b P1 标定结果（已冻结，但开关在 E16 后**关闭**）

> 除非另有说明，本节所有数值都是 2026-10-30 在本机测得的历史记录。最终决定见 §7c。

`e15 --stage calibrate` 最终版本（标定单位 = 一次真实 ALNS 迭代）：

| 字段 | 值 |
| --- | --- |
| 标定单位 | `alns_iteration` |
| pilot | 7 个结构族各 `40` 步确定性运行（`cooling_schedule="iteration"`，seed 0） |
| `t_iteration_median_seconds` | `4.977e-02`（池化 280 个 `measured_stage_seconds` 的中位数） |
| `kappa` | `1.0` |
| `t_ref_seconds` | `4.977e-02` |
| 诊断 `probe_units_per_iteration` | `800.2` |

**为什么把标定单位从「一次 probe」改成「一次迭代」**：第一版用「单次冷缓存
`evaluate_route` × κ=8」，在 `R2_T6_0`（6 任务）上得 `t_ref = 4.92e-04 s`；
但一次完整迭代在 40 任务实例上要 `4.98e-02 s`，**相差约 100 倍**（6 任务 ≈ 50 probe 单位，
40 任务 ≈ 800 probe 单位）。迭代成本由 repair（贪心插入 × 大量 DP 调用）与 local search
主导，不由一张 DP 表主导。以 probe 标定会让因子对所有算子一律乘 `~0.1`；
公共缩放不改变算子排序，机制按构造成为空操作。

`kappa=1.0` 的含义：**中位迭代拿满分，只有明显更贵的迭代被折价**。

`score_effective` 是墙钟相关量，**不可复现**（因子按实测耗时算）；可复现的是
决策轨迹与 `score_raw` 序列 —— 已在 `tests/test_iteration_cost_penalty.py::test_penalised_run_is_deterministic`
中按此口径断言。

---

## §7c P1 开关结论：E16 实测无差异，**不进入 P2/P3**

`e16`（`docs/e16_cost_penalty_ablation_result.md`）在**固定 8 s 墙钟预算**下的
24 个配对运行（8 实例 × 3 seeds）：

| 指标 | 值 |
| --- | --- |
| 开启臂被折价迭代占比（中位） | `45.1%`（机制确实生效） |
| 配对 `delta_rel` 中位数 | `+0.00248`（开启臂略差 0.25%） |
| bootstrap 95% CI | `[-0.00844, +0.00865]`（跨 0） |
| on 更好 / 更差 / 持平 | 10 / 12 / 2 |
| 判定（预注册规则） | **`TURN_OFF`** |

结论与执行要求：

1. `iteration_cost_penalty` 保持默认 `False`，代码与测试保留（这是可复现的负结果）。
2. **不纳入任何实验臂，不作为创新点**；论文里只能作为「试过、无收益」的一句话交代。
3. P2 的反馈注入与本开关正交，不受影响。
4. 与 §7b 一并理解：更硬的惩罚会退化成常数缩放（同样无效），更软则等于没开 ——
   **在分段权重框架里，迭代成本不是能改变算子排序的信号**。



---

## §8 不做的事

- 不把「状态链匹配率」「H/V 切换率」做成指标（D2 已证伪其含义）。
- 不用状态后悔做算子排名的主键（D1 已证量级不成立）。
- 不引入人工 regime 分类（E3 必须自动判定，否则失去可复现性）。
- 不在 P2 阶段改动 `core/dp_evaluator.py`、`core/solution_evaluator.py`、
  `heuristics/alns_solver.py`（P1 才动 alns_solver，且只加开关）。
