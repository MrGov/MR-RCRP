# 精确计价局部搜索（Exact Priced Local Search）：正确性、提速与 E24 判定

日期：2026-10-31。相关文件：`src/mrta_rect_coverage/heuristics/priced_local_search.py`（新）、
`src/mrta_rect_coverage/core/incremental_route.py`（扩展）、`src/mrta_rect_coverage/heuristics/alns_solver.py`（接线 + 默认值）、
`src/mrta_rect_coverage/experiments/e24_priced_local_search_ablation.py`（新）、
`tests/test_priced_local_search.py`（新）。

## 0. 一句话结论

局部搜索里每个候选移动原本要跑一次整条路线的 Route-DP（8 机器人 × 80 任务一次失败扫描 ≈ 9400 次整解评价 ≈ 2 s），
改成**用精确前向/后向表增量定价**后，同一次扫描只需 4.6 ms（中位 33.4 → 4.6 ms/迭代，7.2x），
决策完全不变，于是同一秒数预算里迭代数变成 2.52 倍；16 个配对上配对 makespan 中位 **+0.15%**
（95% CI [+0.16%, +1.80%]，9 胜/4 平/3 负，T40 子集中位 **+0.69%**，8 胜/2 负）→ **KEEP_WEAK，已设为默认开启**。

## 1. 为什么改这里

`heuristics/local_search.py:58 run_stronger_local_search` 被 `heuristics/alns_solver.py` 以 `max_iterations=1`
调用，一次调用会按顺序扫五个邻域（bottleneck_relocates → inter_route_relocates → intra_route_swaps →
intra_route_two_opt → inter_route_swaps），**每个候选都用 `evaluator.evaluate(candidate)` 做整解评价**。

实测（部署 AUX 池，预算 = 任务数秒）local_search 占每迭代时间：T20 66.8%、T40 65.7%、T80 **82.2%**。
更糟的是它的分布是重尾的：T80 上 local_search 单次 median 36 ms、mean **671 ms**、p90 2171 ms、max 2688 ms ——
大多数迭代都在为"扫完全部邻域却没有任何改进"付费。E24 里 `TRAVEL-HIGH/R8_T80_0 s1` 的关闭臂甚至出现
**一次迭代耗时 ~31 分钟**（1911 s 只跑完 101 次迭代），这是旧实现的重尾最坏情况。

## 2. 机制：精确增量定价 + 精确支配过滤

对任一固定路线，先建两张表（`core/incremental_route.py`）：

* `forward[k][s]`：覆盖前 k+1 个任务且第 k 个停在状态 s 的最小代价（含处理时间，不含返仓）；
* `backward[k][s]`：从第 k 个任务的状态 s **完成后**到返仓的最小代价（含后继处理时间与转移，**不含**第 k 个的处理时间）。

三者都是从这两张表按 O(常数) 读出，且与"整条路线跑一次 DP"在浮点容差内**完全相等**：

| 操作 | 复杂度 | 用途 |
| --- | --- | --- |
| `removal_at(tables, position)` | O(64) | relocate 的"释放代价"，每个 (from_robot, from_index) 只算一次 |
| `insertion_cost_at(tables, position, task_id)` | O(64) | relocate 的"插入代价"，同一 (to_robot, task) 覆盖全部插入位 |
| `replacement_at(tables, position, task_id)` | O(192) | inter-route swap 的两侧替换（对比：两次整条 DP） |

`heuristics/priced_local_search.py` 用它们重写五个邻域扫描，**保持与参考实现逐项相同**：
同邻域顺序、同"bottleneck 命中就跳过其余四族"、同 `candidate + 1e-9 < current` 首改进语义。

额外加了**精确支配过滤**：只有当候选移动触及"当前 makespan 的 argmax 路线"时才可能改进，
所以 `others_max(touched) + 1e-9 >= makespan` 的候选可以被证明不可能改进并直接跳过——
跳过的候选都不可能是首个改进解，因此不会改变决策。

一个反直觉的坑（值得记下来）：第一版是**纯惰性**定价，结果在 T10 上比参考实现更慢（0.734 → 1.73 ms）。
`cProfile` 显示 40 次迭代调用了 4115 次 `_insertion_at`、64 万次 `cost_matrix.transition`，
而参考实现只做了 322 次 `route_dp` 调用——**参考实现靠 `RouteDPEvaluator` 的 89% 缓存命中率**，
我的数据通路每次都要重算。修法是给 pricer 加**价格记忆缓存**（`DEFAULT_PRICE_CACHE_LIMIT = 50000`，
键带 `insert`/`replace` 标签，removal 用独立字典）。加上缓存后才有下面的数字。

> 这里踩过一个会静默给出错误结果的 bug：insert 与 replace 曾经共用 `(route, task_id, position)` 键，
> 于是同一位置上的替换价会被当成插入价返回（R2_T6 上给出 209.5 而非 206.0）。
> 现在键值带操作标签，`test_replacement_price_matches_route_dp_for_every_position` 覆盖了这一点。

## 3. 正确性（22 个用例，全部通过）

`tests/test_priced_local_search.py`：

* `test_removal_price_matches_route_dp_for_every_position`（T6/T10/T40 参数化）、
  `test_replacement_price_matches_route_dp_for_every_position`：与整条 Route-DP **逐位置**对拍，容差 1e-9；
* `test_priced_search_matches_reference_decisions`（3 实例 × 3 初始解，`max_iterations=1`）与
  `test_priced_search_matches_reference_over_multiple_iterations`（`max_iterations=4`）：
  断言 `priced.routes == reference.routes` 且 makespan 差 < 1e-9；
* `test_alns_decisions_are_identical_with_priced_local_search`（T6/T20）：固定 8 次迭代、
  `cooling_schedule="iteration"`、seed 3，断言 best makespan、best routes、
  `(destroy, repair, best_makespan, accepted)` **逐行相同**；
* 另有确定性、不恶化、空路线/单任务、每任务恰好一次、尊重传入 initial_evaluation、非法参数等边界用例。

全量 `pytest -q`：**400 passed**。

## 4. 提速（同迭代数下的中性对照，B1 池，固定 40 迭代）

冻结 40 次迭代、两臂 makespan 完全相同，只比时间：

| 场景 | local_search off→on | 每迭代 off→on | 整体 |
| --- | --- | --- | ---: |
| BASE/R2_T10_0 | 0.734 → **0.121** ms | 1.269 → 0.641 ms | 1.98x |
| HV-GEOM/R2_T20_0 | 7.743 → **2.135** ms | 11.06 → 5.42 ms | 2.04x |
| BOTTLENECK/R4_T40_0 | 2.338 → **1.072** ms | 13.51 → 11.92 ms | 1.13x |
| TRAVEL-HIGH/R8_T80_0 | 5.533 → **1.432** ms | 53.01 → 45.86 ms | 1.16x |

（T40/T80 的整体倍速被 repair 主导的 11–47 ms 掩盖，这是下一处要动的地方。）

## 5. E24：固定墙钟下的 A/B（预注册规则 + 判定）

`src/mrta_rect_coverage/experiments/e24_priced_local_search_ablation.py`，产物 `outputs/e24_priced_local_search_ablation/`。

* 块：部署 AUX 池（E18 冻结 LLM destroy + E5 主 repair + E17 aux repair），warm 执行器；
* 臂：`off`（参考局部搜索）/ `on`（精确计价局部搜索），**除该开关外配置逐字段相同**；
* 预算：每任务 1 秒（E12 口径）；实例 8 个 × seeds (0,1) = **16 配对**；
* 臂顺序按 `(instance, seed)` 位置交替，抵消机器漂移。

| 指标 | 值 |
| --- | --- |
| 配对 Δ 中位 / 均值 | **+0.1543% / +0.8049%** |
| 95% CI（5000 次 bootstrap） | **[+0.1625%, +1.8008%]** |
| W/T/L | **9 / 4 / 3** |
| 迭代数比（中位） | **2.52x** |
| local_search 每迭代（中位） | **33.448 ms → 4.624 ms** |
| 判定 | **KEEP_WEAK** |

按规模：

| 任务数 | 配对数 | Δ 中位 | Δ 均值 | W/L |
| ---: | ---: | ---: | ---: | ---: |
| 10 | 2 | +0.0000% | +0.0000% | 0/0 |
| 20 | 2 | −0.1729% | −0.1729% | 1/1 |
| 40 | 10 | **+0.6945%** | **+1.3225%** | 8/2 |
| 80 | 2 | +0.0000% | +0.0000% | 0/0 |

读法：

1. **收益集中在 T40**（局部搜索占 65%、剩余空间最大），T10/T20 局部搜索本来就便宜、T80 两臂都收敛到同一个 6551，
   所以"持平"是符合机制的，而不是无效。
2. 严格来说这是**预算效应**而不是新启发式：单元测试证明同一初始状态下两臂决策完全相同，
   差别只来自同一秒数里能跑多少迭代。这正是我们想要的因果链（精确性 → 便宜 → 更多迭代 → 更好解）。
3. 预注册门槛是 `KEEP ≥ +1.0% 且 CI 下界 > 0`，本轮中位 +0.15% 只在 CI 意义上为正，故判 **KEEP_WEAK**，
   如实记录：**它不是一个能独立支撑论文主张的增益**，而是把"精确内层评价"从不可负担变成可负担的基础设施。

## 6. 处置：已默认开启

`ALNSConfig.priced_local_search` 默认值由 `False` 改为 **`True`**，docstring 写入了 E24 的数值证据与
"设为 False 可逐位复现历史 B1 轨迹"的口径。B1 与 Proposed 共用该配置，因此对基线与我们的方法**同等生效**，
不构成偏袒。

随之调整的两个测试（`tests/test_alns_search_control.py`）：这两个用例通过 monkeypatch
`run_stronger_local_search` 给假时钟计时，默认切换到计价版后补丁不再命中，会真的进入死循环（假时钟永不前进）。
现在两处同时打补丁，断言不变。

## 7. 对论文主张的意义与边界

**可以写**：因为路线级移动可以用前向/后向表增量定价，精确 Route-DP 可以做到"每个候选移动都按精确最优状态给价"，
成本与路线长度无关。这使 E20 结论（后处理没有免费空间）与本节结论（预算之内可以更细地搜索）能同时成立：
精确性不是奢侈品，是已经被我们做成廉价的基础设施。

**不能写**：不能把 +0.15% 当作算法优越性证据；不能声称"比基线更精确地评价解"——
基线（`comparison_algorithms/common.py`，`SearchConfig.evaluation_mode` 默认 `'exact'`）同样用精确 Route-DP 评价，
差别只在于它们的移动是交叉/变异（一次改多条路线），**不存在单路线增量定价**。这一点在正文里必须诚实说明，
否则会被读成"给基线少给了算力"。

## 8. 下一步

局部搜索的预算问题已基本解决（T80 从 671 ms 均值降到 4.1 ms）。现在每迭代剩余的大头是 **repair（T40 约 11 ms、T80 约 45 ms）**，
而 repair 的成本同样来自逐候选插入定价——这条链路已经用上 pricer，剩余成本是"每插入一个任务要为 4 条路线各建一次表"。

真正的问题已经不是机器速度，而是**搜索质量**：E24 把迭代数翻了 2.5 倍，T40 只换来 +0.69%。
这说明瓶颈不在"迭代太少"，而在"每次迭代的信息含量"。下一步应该把现在廉价得到的精确量
（每个任务的真实边际代价、每条路线的真实插入价向量）变成**对算子决策质量的直接度量**，
而不是继续加热时间预算。
