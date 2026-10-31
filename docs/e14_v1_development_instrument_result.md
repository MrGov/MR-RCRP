# B1 结果：状态后悔仪表在 v1 development 上的跨尺度检验（2026-10-30）

运行：`PYTHONPATH=src python -m mrta_rect_coverage.experiments.e14_state_regret_instrument --stage dataset --dataset v1 --split development`
产出：`outputs/e14_state_regret_instrument/v1/development/`（84 份实例报告 + `dataset_summary.json`）。纯 DP、无 ALNS、无 LLM，运行时间分钟级。

## §0 结论

**e10 上冻结的四条主要结论在 v1 development 上全部复现**，但暴露两件 e10 单尺度集看不见的事：状态层价值强烈依赖**规模**，且现行「并列屏蔽」规则丢掉了**一半以上**真正由模式决定的信号。

| 指标 | e10（21 个，全 R4/T40） | v1 development（84 个，6 尺度 × 7 族） | 判定 |
| --- | --- | --- | --- |
| 有信息位置占比 | 28.45% | 32.40% | 同量级 ✓ |
| 并列位置占比 | ~71% | 67.6% | 同量级 ✓ |
| 转移占比（mean transfer share） | 0.794 | 0.818 | 一致偏主导 ✓ |
| 覆盖占比 | 0.162 | 0.144 | 同量级 ✓ |
| 转向占比 | 0.044 | 0.038 | 同量级 ✓ |
| load_excess / makespan | 0.1245 | 0.1171 | 一致 ✓ |
| \|mode_gap\| ≥ 1% makespan（有信息位置） | 30/840 = 3.57% | 126/4340 = 2.90% | 同量级 ✓ |
| HV-GEOM 占大 gap 位置的比例 | **28/34 = 82%** | **86/126 = 68%** | 复现 ✓（见下） |

结论：**阈值不需要重新冻结。** `p2_feedback_design.md` §3 的五条 regime 规则与 0.25/0.15/0.06/0.75 阈值在跨尺度数据上仍然落在设计位置。

## §1 复现的强信号：HV-GEOM 是唯一"状态值得优化"的场景

大 gap（≥1% makespan）位置数 / 每实例平均：

| 场景 | 实例数 | 有信息占比 | 大 gap 总数 | 每实例 | regime 分布 |
| --- | --- | --- | --- | --- | --- |
| **HV-GEOM** | 12 | 0.332 | **86** | **7.17** | mode_sensitive **9**、balance 2、transfer 1 |
| TRAVEL-HIGH | 12 | 0.347 | 9 | 0.75 | transfer 6、balance 4、mode_sensitive 2 |
| BASE | 12 | 0.347 | 8 | 0.67 | transfer 7、balance 3、mode_sensitive 2 |
| TURN-HIGH | 12 | 0.347 | 8 | 0.67 | turn_heavy 5、balance 3、transfer 2、mode_sensitive 2 |
| BOTTLENECK | 12 | 0.288 | 5 | 0.42 | transfer 7、balance 3、mode_sensitive 2 |
| SPATIAL | 12 | 0.331 | 5 | 0.42 | transfer 7、balance 3、mode_sensitive 2 |
| SWEEP-NARROW | 12 | 0.275 | 5 | 0.42 | transfer 6、balance 1、turn_heavy 2、mode_sensitive 2、mixed 1 |

HV-GEOM 每实例的大 gap 位置数是其他场景的 **10~17 倍**。e10（全 R4/T40）在大 gap 位置的场景归属上给出 82% 集中度，v1（跨 6 尺度）给出 68% —— 集中度被打散的部分正是下面这条新发现的规模效应。

## §2 新发现一：状态层价值随规模急剧衰减

| 任务数 | 实例数 | 有信息占比 | 大 gap 位置 | regime 分布 |
| --- | --- | --- | --- | --- |
| **10** | 14 | 0.407 | **47** | **mode_sensitive 14（全部）** |
| 20 | 14 | 0.286 | 15 | transfer 8、turn_heavy 4、mode_sensitive 2 |
| 40 | 14 | 0.354 | 19 | transfer 9、turn_heavy 2、mode_sensitive 2、mixed 1 |
| 60 | 14 | 0.281 | 5 | transfer 8、balance 5、turn_heavy 1 |
| 80 | 14 | 0.294 | 22 | transfer 8、balance 4、mode_sensitive 2 |
| **100** | 14 | 0.323 | 18 | **balance_dominated 10**、transfer 3、mode_sensitive 1 |

- R2/T10：**14/14 全部判为 mode_sensitive**，大 gap 位置 47 个（每实例 3.4）。
- R4/T60 降到每实例 0.36 个；R8/T100 有 10/14 判为 balance_dominated。

含义：**状态层是"小规模 + HV-GEOM 几何"的局部杠杆**。规模一大，makespan 由负载均衡与转移主导，状态选择边际为零——这正是 e10（全 R4/T40）看不到的。对 P2 的直接后果：F2 档位必须**带上规模条件**（把 `n_tasks` 写进 evidence，而不是只写 regime 标签），否则 LLM 会在 100 任务的实例上被鼓励去优化一个零收益的维度。

## §3 新发现二：现行并列屏蔽规则丢掉了 55% 的模式信号

v1 dev 全体 4340 个位置中，`|mode_gap| ≥ 1% makespan` 的有 **279** 个，但其中只有 **126（45%）** 是 `informative ∧ tied_state_count == 1`；另外 **153（55%）** 被现行规则屏蔽掉，它们的 `tied_state_count` 分布是 `{2: 152, 4: 1}`。

原因不是 bug，而是两种并列被混为一谈：

- **跨模式并列**（H 与 V 的最优代价相等）：模式确实无差别 → 应该屏蔽。此时 `mode_gap ≈ 0`，本来也不会进大 gap 名单。
- **模式内并列**（同模式里 2 个或 4 个进入角代价相等，但另一模式明显更差）：进入角是自由的，**模式仍然是决定性的** —— 这正是 `tied_state_count ∈ {2,4}` 且 `mode_gap` 很大的那 153 个位置。

`near_tie_tol` 只回答"状态选择是否唯一"，回答不了"模式是否还有压力"。对 F2 反馈，后者的 153 个位置被白白丢弃，而对 LLM 来说它们是有效信息（"此处 H 比 V 便宜 2.1%，但 4 个角都等价"）。

**建议（需你决定）**：把一个掩码拆成两个，不动已冻结的五条 regime 阈值：

- `chain_comparable = informative ∧ tied_state_count == 1` —— 只用于"状态链/切换"类主张（跨运行比较状态链时必须如此，因为并列时 DP 的角选择是迭代顺序决定的）。
- `mode_decisive = mode_gap is not None ∧ |mode_gap|/makespan ≥ 0.01` —— 用于模式压力类主张与 E4 注解，**包含模式内并列**。

若采纳，`large_gap_share` 的口径会从 126 → 279（占全部位置 6.4%），HV-GEOM 与 R2/T10 的信号会更强；但 `mode_sensitive` regime 标签（依赖 informative 掩码）是否跟着改，是第二个独立决定——我倾向**不跟着改**（regime 是实例级粗标签，已冻结；位置级证据用新掩码即可）。

## §4 对 B2/B3/B4 的影响

- **B2（演化迁到 v1 dev）**：HV-GEOM + 小尺度是唯一有信号的区域，演化子集必须**包含 HV-GEOM 与 R2 尺度**，否则算子在零信号区域上演化，学不到东西。建议演化子集 = 7 族 × {R2/T10, R4/T40} = 14 个实例（含全部 HV-GEOM 两尺度）。
- **B3（对比表）**：规模效应显著 ⇒ 对比必须覆盖全部 6 个尺度，否则"我们的方法在大规模上更好"无从检验。这直接指向 L 方案（42 单元）。
- **B4（P3 配对）**：配对实例应集中在 HV-GEOM（信号密度 7.17/实例），而不是均匀抽样；否则 56 分钟的配对运行大部分会落在零信号实例上。

## §5 复现命令

```powershell
cd mrta_rect_coverage
$env:PYTHONPATH='src'
& G:\Anaconda\envs\mrta_env\python.exe -m mrta_rect_coverage.experiments.e14_state_regret_instrument --stage dataset --dataset v1 --split development
& G:\Anaconda\envs\mrta_env\python.exe -m mrta_rect_coverage.experiments.e14_state_regret_instrument --stage verify
```
