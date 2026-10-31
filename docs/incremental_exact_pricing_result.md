# 精确增量计价（incremental exact pricing）落地结果

日期 2026-10-31。取代 `docs/operator_economics_and_plan.md` §7 里"待做"的第一项，回答的问题是：
**让每个插入候选都由精确 Route-DP 定价，能不能在墙钟预算内做到？** 结论：能，且幅度足够改变排名格局。

---

## 1 改了什么

| 文件 | 改动 |
| --- | --- |
| `src/mrta_rect_coverage/core/incremental_route.py` | **新增**（约 300 行）。`RouteTables` + `RouteIncrementalEvaluator`：对一条路线建前向表 `forward[k][s]`（覆盖 `t_0..t_k` 且 `t_k` 处于状态 `s` 的最小代价）与后向表 `backward[k][s]`（从 `t_k` 的 `s` 出发完成余下任务并返仓的最小代价），插入代价 `min_{s'} A(s') + min_{s_i}[travel + P_i + K(s_i)]`，`O(64)`/位置、与路线长度无关 |
| `src/mrta_rect_coverage/heuristics/alns_solver.py` | `__init__` 建 `self.insertion_pricer`；`solve()` 开头清缓存；`_best_insertion_for_task` 与 `_regret_k_insertion` 改用 `insertion_prices`，不再对每个候选位置跑一次 `route_dp.evaluate_route` |
| `src/mrta_rect_coverage/llm/operator_evolution/candidate_execution.py` | `CandidateProxy` 新增 `import_timeout_s: float = 3.0`（原硬编码 1.0 s），`execute()` 透传。**调用预算 `timeout_ms` 不变** |
| `src/mrta_rect_coverage/llm/operator_evolution/persistent_candidate_execution.py` | warm worker 的两次 import 轮询改用 `self.import_timeout_s`，`from_validated` 透传 |
| `tests/test_incremental_route.py` | **新增** 10 个测试 |
| `tests/test_e6_pair_selection.py` | 修一处与 M2 签名不一致的 monkeypatch（`_weighted_pick(weights, group=None)`） |

`import_timeout_s` 的动因是一次真实故障：E12 名单的最后一个配对（`TRAVEL-HIGH/R8_T80_0` seed 1）在加载冻结算子时抛
`ValueError: destroy failed candidate loader ... 'Candidate import timed out'`，`wall_time_ms=1192`。机器有负载时新进程 import 整个包会超 1 s，
这是**加载期**预算，与搜索期每次调用的 1 s 超时不应共用。改成加载期 3 s。

## 2 正确性

- 判据是"与精确 Route-DP 给出同一个数"，不是手算期望值。`tests/test_incremental_route.py`：
  T1 固定路线代价、**T2 每个插入位与整条路线 DP 逐位对拍**、T3 argmin、T4 空路线、T5 建表一次且稳定、T6 未知任务报错、
  T7 确定性、T8 完全不触碰 `route_dp`（`calls` 恒为 0）、T9 缓存容量不影响数值、T10 长路线每一位仍精确。
- 容差 1e-9 绝对；实测偏差量级为 1e-13 相对。
- 全量 `pytest -q` **378 passed / 0 failed**（55.25 s），其中 `tests/test_executor_equivalence.py` 仍断言两个执行器的决策轨迹逐行相同。

### 2.1 一个有代价的事实：轨迹不再逐位可复现

后向表是**反序累加**，与 DP 的正序累加在浮点上不等价（相对误差 ~1e-13）。当两个候选插入位在 DP 里恰好并列时，
这个量级足以改变 argmin（`_best_insertion_for_task` 的容差是 1e-9 绝对）。实测 12 个实例、固定 40 次迭代、同 seed：

- **11/12 决策轨迹与 HEAD（P1 版）逐行相同**；
- `BOTTLENECK/R4_T40_0` 在第 27 次迭代分叉（`geometry_aware_destroy + regret_k_insertion` 之后 best makespan 3812.55 vs 3842.86），
  终点 old 3663.540 / new 3601.156 —— 属平局打散后的路径差异，不是精度损失。

因此：**同一实现内确定性成立（有测试）；跨实现不保证逐位复现，历史 E11/E12/E16 的 B1 数字不能与新实现逐位对比。**
最终论文表会在同一实现下重跑全部方法，不受影响；若要复现旧数字，须 `git checkout` 掉 pricer。

## 3 速度

### 3.1 计价微基准（插入 10 个任务 × 4 条路线 × 全部位置）

| 实例 | 候选数 | 逐候选 DP | 增量表 | 提速 |
| --- | ---: | ---: | ---: | ---: |
| `R2_T10_0` | 40 | 0.1 ms | 0.08 ms | 0.9x |
| `R4_T40_0` | 340 | 43.8 ms | 6.34 ms | **6.9x** |
| `R8_T80_0` | 740 | 231.8 ms | 18.22 ms | **12.7x** |
| `R8_T100_5` | 940 | 947.7 ms | 40.48 ms | **23.4x** |

小实例没有收益（建表开销 ≥ 一次 DP），这正是 T10 上迭代数没变化的解释。

### 3.2 求解器内每迭代耗时（B1 配置，40 次迭代中位数）

| 实例 | repair 旧 | repair 新 | 整迭代提速 |
| --- | ---: | ---: | ---: |
| `BASE/R4_T40_0` | 42.1 ms | 18.3 ms | 1.28x |
| `HV-GEOM/R4_T40_0` | 76.2 ms | 17.7 ms | 1.26x |
| `BOTTLENECK/R4_T40_0` | 76.0 ms | 18.9 ms | 1.06x |

修完插入后剩下的 18 ms 是"每插入一个任务就要为 4 条路线各建一次表"（路线在每次插入后都变了），以及 `~0.1 ms` 的逐机器人 DP 复核。
固定 40 次迭代的 12 实例中位提速 **1.18x**；固定墙钟预算下则表现为**迭代数增加**，见 §4。

## 4 同预算迭代数（E12 四实例 × seeds 0/1，预算 = task_count 秒）

| 实例/seed | B1 | Proposed | CDABC | RNSGA |
| --- | ---: | ---: | ---: | ---: |
| BASE/T10 s0 | 5498 | 1694 | 4496 | 335 |
| BASE/T10 s1 | 4058 | 1714 | 4397 | 318 |
| HV-GEOM/T20 s0 | 542 | 563 | 4133 | 194 |
| HV-GEOM/T20 s1 | 540 | 603 | 3830 | 187 |
| BOTTLENECK/T40 s0 | 420 | 356 | 8486 | 245 |
| BOTTLENECK/T40 s1 | 317 | 401 | 7869 | 204 |
| TRAVEL-HIGH/T80 s0 | 168 | 90 | 27437 | 332 |
| TRAVEL-HIGH/T80 s1 | 129 | 66 | 13092 | 195 |

对比历史：Proposed 在 `BASE/R2_T10_0` 从 **63 → 1694**（27x，E13 记录的冷 spawn/vNext 分别为 63/—），
`BOTTLENECK/R4_T40_0` 从 E13 vNext 的 **302 → 356**，`TRAVEL-HIGH/R8_T80_0` 90（E13 未记录该实例 vNext）。

T10 上仍差 B1 三倍：那里一整个迭代只要 ~2 ms，而冻结算子的一次进程调用是 3–8 ms，占比由**算子边界**而非 DP 决定。
T80 上只有 66–90 次迭代，B1 129–168：瓶颈变成 `regret_k_insertion` 在大路线上的建表与 `local_search`。

## 5 排名快照（同 E12 四实例 × 2 seeds = 8 配对，预算 = task_count 秒）

| 实例 | Proposed | B1 | CDABC | RNSGA | 本行最优 |
| --- | ---: | ---: | ---: | ---: | --- |
| BASE/T10 s0 | 1293 | 1292 | 1292 | 1292 | 三者并列 |
| BASE/T10 s1 | 1293 | 1292 | 1292 | 1292 | 三者并列 |
| HV-GEOM/T20 s0 | 2332 | 2343 | 2328 | 2355 | CDABC |
| HV-GEOM/T20 s1 | 2343 | 2320 | 2351 | 2328 | B1 |
| BOTTLENECK/T40 s0 | **2688.290** | 2846.548 | 2851.086 | 2790.761 | **Proposed** |
| BOTTLENECK/T40 s1 | 2738.562 | 2877.771 | 2818.084 | **2715.949** | RNSGA |
| TRAVEL-HIGH/T80 s0 | **6551** | 6621 | 6551 | 6551 | 并列 |
| TRAVEL-HIGH/T80 s1 | **6551** | 6700 | 6551 | 6610 | 并列 |
| **均值** | **3223.731** | 3286.540 | 3254.271 | 3241.839 | |
| 均值迭代 | 686 | 1459 | 9218 | 251 | |

配对相对增益（正 = Proposed 更好）：

| 对比 | 均值 | 中位 | 最小 | 最大 | W/T/L |
| --- | ---: | ---: | ---: | ---: | --- |
| vs B1 | **+1.625%** | +0.763% | −0.991% | +5.560% | 5/0/3 |
| vs CDABC | **+1.068%** | 0.000% | −0.172% | +5.710% | 3/2/3 |
| vs RNSGA | **+0.489%** | −0.039% | −0.833% | +3.672% | 3/1/4 |

### 5.1 三条读法（必须写在正文里，避免过度声称）

1. **均值第一，但不是稳定第一。** 8 配对里 Proposed 对 B1 赢 5 输 3，对 RNSGA 输 4；均值领先主要来自两个 BOTTLENECK/T40 配对（+5.56% / +4.84%）。
   BOTTLENECK 正是"负载均衡是唯一瓶颈"的场景，说明当前收益来自**组合（均衡型修复算子 + 足够迭代数）**，而不是普适优势。
2. **T10 差 1 个单位。** 1293 vs 1292 是离散差异（makespan 为整数实例），不构成"更差"的机制证据，但也说明小实例上没有优势。
3. **跨实验一致性自查。** CDABC 的 8 配对均值 3254.271 与 E12 历史记录完全一致（该基线不经过我们改动的代码路径）；
   RNSGA 均值 3241.839 与 E12 的 3266.089 相差 0.7%，因为它按自身 RNG 与 deadline 停止，跨运行本就抖动。
   这条自查同时确认：本轮的 B1/Proposed 数字与 E12/E19 处于同一测量口径。

### 5.2 与 E19 的同口径对照

E19（冷 spawn，E11/E18 两臂，同样 4 实例 × 2 seeds）：E18 臂均值 **3277.32**。本轮 Proposed（E18 冻结 + warm 执行器 + 增量计价）**3223.731**：
同一批实例、同一预算，**−1.63%**。B1 同期从 E12 的 3303.588 变为 3286.540（−0.52%，来自更多迭代）。
即：执行器 + 计价这两个"纯工程"改动合计把我们的臂推进了 1.6 个百分点，其中约 1.1 个点来自我们独有的路径（B1 只吃到计价那部分）。

## 6 结论与下一步

- **"每个候选都由精确内层最优化定价，并在墙钟预算内可行"现在成立**：T40 6.9x、T80 12.7x、T100 23.4x，数值与 DP 一致（1e-9）。
  这是可以写进方法章节的一条可复现工程主张，但它**不是科学贡献本身**——它只是让上一层的搜索机制有可能在预算内跑起来。
- 排名快照首次出现 Proposed 均值第一（+1.63% vs B1、+1.07% vs CDABC、+0.49% vs RNSGA），但**只有 8 配对、单份 development 数据、且由单场景驱动**，属探索性。
- 未做的事：没有 42 单元 × 3 seeds 的论文表；`local_search` 与 `regret_k` 在大路线上的建表开销未优化；T10 的算子边界开销未处理。

**下一步（需要用户确认预算）**：用当前实现跑论文正式表 —— 42 单元（v1 development × replicate 0，7 族 × 6 尺度）× 3 seeds × 6 方法，
预算 = task_count 秒，串行 ≈ **21.7 h**。跑之前应确认算法配置已冻结（否则表作废）。
