# E25 — 决策级审计：部署算子的决策画像，与「按决策给信用」的 A/B

日期：2026-10-31　代码状态：HEAD `9020311` + 未提交工作树（`heuristics/decision_audit.py` 等）
产物：`outputs/e25_decision_audit_ablation/`（`describe_runs.json`、`runs.json`、`pairs.json`、`summary.json`、`REPORT.md`、`experiment_config.json`）

## 0. 一句话

精确 Route-DP 已经便宜到可以对**每一次算子调用**做最优性审计：`describe` 阶段首次定量给出「每个算子实际把任务放/摘得有多接近该时刻的精确最优」，结论是**只有 LLM 生成的 destroy 明显优于随机基线，两个手工 destroy 处在随机水平**；但把这个审计当作信用信号驱动权重（`run` 阶段，H-Q），在固定墙钟预算下**没有收益**（中位 0.00%，CI 跨 0）→ 预注册判定 **TURN_OFF**。

## 1. 机制

`heuristics/decision_audit.py` 在每次 destroy / repair 调用后用同一套精确前向/后向表（`core/incremental_route.py`）复算该决策的**事后最优值**，全部量都是给定状态的确定性函数，与接受准则、seed、makespan 噪声无关：

* destroy：`precision` = 被摘走的任务中，真正属于「精确边际节省前 k 名」的比例；`saving_capture` = 被摘集合的节省 / 最优前 k 集合的节省；`is_random_level` = `precision <= k/N`。
* repair：对每个被摘任务，枚举每条路线的最优插入位（O(64)/位），得到
  `price(t,r)`，再算两条基线：
  * 和代价最优路线 `argmin_r cost(r)+price(t,r)`；
  * makespan 最优路线 `argmin_r max(cost(r)+price(t,r), max_{r'≠r} cost(r))`（只有被选路线增长，其余保持当前代价——这是本轮修掉的一个真实 bug，早期版本把所有路线的插入价都加进去，makespan 虚高）。
  由此得到 `sum_hit_rate` / `makespan_hit_rate` / `neither_rate`（既不和最优也不 makespan 最优 = **被支配的落点**）与平均后悔（绝对量与占 makespan 比例）。
* `DecisionAuditRecorder` 按算子聚合，进 `ALNSResult.decision_audit`；`alns_solver._audit_iteration_decision` 用 `except (ValueError, KeyError)` 兜底（生成的算子可能返回不可归因的状态，仪表化绝不中断迭代）。
* 单元测试 12 个：与整条路线 DP 逐项对拍（含 3 个实例）、暴力枚举对拍 makespan 最优路线、空/单任务/丢任务边界、聚合正确、以及 `test_audit_does_not_change_the_search`（同 seed 6 次迭代决策轨迹逐行相同）。

规模：16 次部署运行共审计 **14,480 次迭代**（每次 1 destroy + 1 repair）。

## 2. `describe`：部署池（AUX）的决策画像

池 = 3 个手工 destroy + `e5_llm_destroy`，3 个手工 repair + `e8_aux_repair`；预算 = 每任务 1 秒；`structural_benchmark_v1/development` 的 8 实例 × seeds (0,1)。

### 2.1 destroy：谁真的摘到了「贵的任务」

随机破坏的理论基线是 `precision = k/N = 0.25`（`destroy_fraction = 0.25`）。

| destroy | precision | saving capture | random_level 占比 |
| --- | ---: | ---: | ---: |
| `random_destroy` | **0.2443** | 0.5688 | 0.557 |
| `bottleneck_route_destroy` | **0.2397** | 0.5666 | 0.655 |
| `geometry_aware_destroy` | 0.2744 | 0.5905 | 0.545 |
| `e5_llm_destroy`（LLM 生成，冻结） | **0.3225** | **0.7127** | **0.333** |

三条读法：

1. `random_destroy` 落在 0.2443，与理论值 0.25 吻合 → **仪器自校准通过**，这个数不是编出来的。
2. 手工的 `bottleneck_route_destroy`（整条瓶颈路线作为破坏单位）在「摘最贵的 k 个任务」这个判据下**与随机不可区分**（0.2397）。它不是没用，而是它的意图（搬整条瓶颈路线的负载）与「摘最贵的任务」不是同一个目标——审计第一次把这个区别量化出来。
3. 只有 LLM 生成的 `e5_llm_destroy` 明显高于随机（+29%），且 saving capture 0.71 vs 0.57，`random_level` 运行占比 33% vs 55–66%。→ E17 里 F2 算子候选评价胜出的那个 destroy，在决策层面确实是更强的。

### 2.2 repair：落点离「精确 makespan 最优」有多远

| repair | makespan hit | sum hit | neither（被支配） | 平均 makespan 后悔 | 平均和代价后悔 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `e8_aux_repair`（LLM 生成，冻结） | **0.8643** | 0.5083 | **0.0357** | **0.3518%** | 16.78% |
| `greedy_insertion` | 0.8461 | 0.4688 | 0.0618 | 0.5506% | 17.65% |
| `regret_k_insertion` | 0.8055 | 0.5284 | 0.0573 | 0.5967% | 14.60% |
| `bottleneck_balancing_insertion` | 0.7542 | 0.5299 | **0.0978** | 0.9906% | **12.31%** |

三条读法：

1. `e8_aux_repair` 在 makespan 命中率与后悔两项都最好，被支配落点最少（3.6%）；这与 E17/E18/E19/E24 通过昂贵候选评价得到的排序**一致**——审计用确定性单次计算复现了那个结论。
2. `bottleneck_balancing_insertion` 有 **9.8% 的落点是被支配的**（既不最优和代价也不最优 makespan），这是它相对其他 repair 最差的一项。它是唯一「按目标负载分配」而非「按精确代价分配」的算子，这个缺陷可以直接改。
3. 「和代价后悔」与「makespan 命中率」的排序几乎相反（bottleneck balancing 和代价后悔最小 12.3%、makespan 命中率最差 0.754）。这说明两个目标在这批实例上**确实冲突**，任何单目标信用都会奖励一套行为、惩罚另一套——这正是决策审计应当显式呈现的东西。

## 3. `run`：H-Q（按决策给信用 vs 按结果给信用）

* 两臂**都开启审计**（`decision_audit=True`），所以观测成本相同；唯一差异是 `decision_driven_selection`：开 = 段奖励取 `8 × 决策质量`（destroy 用 precision，repair 用 makespan hit rate），关 = 原来的 8/3/1 结果信用。
* repair 的质量取 **makespan 命中率**而非「1 − 归一化后悔」：实测后悔占 makespan 只有 0.35–0.99%，用 1−ratio 会饱和在 0.99 上，算子之间差 0.005，等于没有信号（这是设计时先测再定的一次修正）。

结果（16 配对，预算 = 每任务 1 秒）：

| 配对 | 中位 Δ | 均值 Δ | 95% CI | W/T/L | 判定 |
| ---: | ---: | ---: | --- | --- | --- |
| 16 | **+0.0000%** | +0.1182% | [−0.5172%, +0.9256%] | 5/4/7 | **TURN_OFF** |

按规模：T10 0.00%（2 对全平）、T20 −0.257%（1/1）、T40 −0.349%（10 对，4 胜 6 负）、T80 0.00%（2 对全平）。

逐配对（正 = 决策信用更好）：

| 实例 | s | off | on | Δ | 迭代 off→on |
| --- | ---: | ---: | ---: | ---: | --- |
| BASE/R2_T10_0 | 0 | 1293.000 | 1293.000 | +0.0000% | 2037→2059 |
| BASE/R2_T10_0 | 1 | 1293.000 | 1293.000 | +0.0000% | 1945→2040 |
| HV-GEOM/R2_T20_0 | 0 | 2332.000 | 2317.000 | +0.6432% | 771→806 |
| HV-GEOM/R2_T20_0 | 1 | 2332.000 | 2359.000 | −1.1578% | 719→678 |
| BASE/R4_T40_0 | 0 | 2697.000 | 2706.000 | −0.3337% | 780→669 |
| BASE/R4_T40_0 | 1 | 2711.000 | 2745.000 | −1.2541% | 835→674 |
| HV-GEOM/R4_T40_0 | 0 | 2717.000 | 2743.000 | −0.9569% | 756→649 |
| HV-GEOM/R4_T40_0 | 1 | 2742.000 | 2752.000 | −0.3647% | 811→630 |
| BOTTLENECK/R4_T40_0 | 0 | 2746.473 | 2631.784 | **+4.1759%** | 1026→604 |
| BOTTLENECK/R4_T40_0 | 1 | 2675.697 | 2715.640 | −1.4928% | 645→692 |
| SPATIAL/R4_T40_0 | 0 | 3675.000 | 3673.000 | +0.0544% | 1446→655 |
| SPATIAL/R4_T40_0 | 1 | 3662.000 | 3688.000 | −0.7100% | 1551→743 |
| TURN-HIGH/R4_T40_0 | 0 | 2931.000 | 2929.000 | +0.0682% | 1033→563 |
| TURN-HIGH/R4_T40_0 | 1 | 2982.000 | 2886.000 | **+3.2193%** | 625→635 |
| TRAVEL-HIGH/R8_T80_0 | 0 | 6551.000 | 6551.000 | +0.0000% | 390→333 |
| TRAVEL-HIGH/R8_T80_0 | 1 | 6551.000 | 6551.000 | +0.0000% | 273→291 |

### 3.1 为什么没有收益：机制审计

不是「没生效」，而是**生效方向与预算约束相反**：

* destroy 权重被拉向 `e5_llm_destroy`（precision 最高）——它恰好是最贵的 destroy（单次 10–20 ms，其余 0.01–0.16 ms）；
* repair 权重被拉到 5–7.4（质量 0.70–0.95 都接近上限），四者差异变小，选择近均匀；
* 结果是**迭代数下降**：SPATIAL 1446→655、TURN-HIGH 1033→563、BASE/T40 835→674，最坏 −61%。
* 8 个 T40 配对里 6 个变差，能赢的两个（BOTTLENECK s0 +4.18%、TURN-HIGH s1 +3.22%）属于「随机轨迹恰好找到更好盆地」的量级，不是机制稳定收益。

即：**决策质量是「单步最优性」的度量，不是「整条搜索轨迹价值」的度量**。一个始终做单步最优决策的算子会退化成贪心，而 ALNS 的收益恰恰来自「暂时不最优」的多样性。把单步最优性当信用，等于把搜索推向贪心。

## 4. 决定与保留价值

* **不投 H-Q**：`decision_driven_selection` 保持默认 `False`，不进任何实验臂（与 M2、`transfer_gain_destroy`、`iteration_cost_penalty` 同一处置）。
* **保留 `decision_audit`**（默认 `False`，零决策影响，开销 < 1 ms/迭代）：它是唯一能在**不跑对照实验**的前提下判断「一个算子是不是在做有意义的事」的仪器，对 LLM 算子生成的反馈环节有直接价值（下一步用它做 F2 档反馈的证据，替代「makespan 变好/变坏」）。
* 已暴露两个可直接改的具体缺陷：`bottleneck_balancing_insertion` 的 9.8% 被支配落点；`bottleneck_route_destroy` 在「摘贵任务」这一判据下与随机无异（提示它和 repair 的分工需要重新设计，而不是调参）。

## 5. 与前面实验的合流结论

本会话已经用预注册规则关闭了四个「信用/选择」类机制：

| 实验 | 机制 | 判定 |
| --- | --- | --- |
| E16 | 迭代成本折价奖励 | TURN_OFF（中位 +0.25%，CI 含 0） |
| E22 | 花费感知选择（probability / throughput） | INCONCLUSIVE / **TURN_OFF_HURT** |
| E23 | 精确转移增益破坏算子 | TURN_OFF（中位 +0.48%，CI 含 0，8 胜 4 负） |
| E24 | 精确计价局部搜索 | **KEEP_WEAK**（中位 +0.15%，CI [+0.16%, +1.80%]，迭代 2.52×） |
| E25 | 决策质量信用（H-Q） | TURN_OFF（中位 0.00%，CI 含 0） |

唯一正向的是 E24，而它的作用机理是**改变预算**（同样墙钟内迭代数翻倍），不是改变启发式。这与 E20（对最优解做精确下降也几乎没有空间，64 条里 40 条零改进）一起说明：**当前瓶颈既不在算子选择规则，也不在邻域强度，而在「每次迭代能挤出多少不同的信息」**。
