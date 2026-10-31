# 数据集统一与重跑计划（2026-10-30）

状态：**待确认**。本文件只做盘点与列单，未执行任何重跑。已完成的只有：删除 53 个无引用根实例 + 3 个空占位目录，重写 `data/README.md`，在 `docs/data_directory_audit.md` 追加更新段。

## §0 结论先行

三套数据各绑一条实验线，其中**创新点主线（LLM 演化算子）被绑在最老的自生成数据集上**，而最正式的 `structural_benchmark_v1` 只服务了对比算法线。要统一，真正的代价不在"换数据集"本身，而在**算子是在 A 集上演化、在 B 集上评估**这个错位——它使"演化集 = benchmark 的 development split"这一标准叙事目前不成立。

## §1 现状：谁在用哪套数据（有据可查）

| 实验线 | 数据集 | 证据 |
| --- | --- | --- |
| 对比算法线 E11 / E12 / E13 | **`structural_benchmark_v1` development（+ E11 用 validation）** | `e11:25` DATA=v1；`e12:22-23` SAMPLES=4 个 `development/...`；`e13` 复用 e12 的实例集 |
| 机制线 E10-B / E14 / E15 / E16 | `e10_structural_development`（21 个，全 R4/T40） | `e10b:32`、`e14:23`、`e15:46`、`e16:48` 均 `ROOT/'data/e10_structural_development'` |
| 演化线 E5 / E7（产出被 E11 的 AUX 引用） | **legacy 根实例**：E5 = `R2_T10_0/R2_T20_0/R4_T40_0/R8_T80_0`；E7 选择集 = `R2_T20_3/R4_T60_8/R8_T100_5` | `outputs/e5.../experiment_config.json: instances`；`outputs/e7.../experiment_config.json: selection_instances/comparison_instances` |
| 部署链 | E11 的 `algorithm_freeze.json` 的 `operators.destroy/main/aux.source_path` **指向 `outputs/e5_llm_destroy_repair/...` 与 `outputs/e7_cooperative_evolution/generated/...`** | `outputs/e11_structural_benchmark/algorithm_freeze.json` |

由此产生的一致性缺口，按严重程度排：

1. **演化/评估错位（高）**：AUX 算子在 legacy 4~7 个实例上演化，却在 v1 dev+val 上评估并得出 `gain_vs_V1 = +1.08% (dev) / +1.69% (val)`。这不是数据泄漏（v1 从未参与演化），但**论文不能写"在 benchmark 的 development split 上演化"**。要么改成真在 v1 dev 上演化，要么明确写成"跨数据集迁移"。
2. **对比样本过小（中）**：E12/E13 只用 4 个 dev 实例（R2/T10、R2/T20、R4/T40、R8/T80 各一），族与尺度**完全混淆**。E12 自己的 REPORT 已写 "Small sample confounds scale and scenario; no significance or generalization claims"。这不属于"算例不一致"，但不足以支撑对比表。
3. **机制线单尺度（中）**：E14/E15/E16 的 regime 阈值在 `e10`（全 R4/T40）上冻结，未在跨尺度实例上验证过；e10 与 v1 dev 的 R4/T40 格子是**不同实例**（e10 每族 3 重复，v1 dev 每族每尺度 2 个），不能互换。

## §2 统一口径（已确认）

| 用途 | 数据集 | 说明 |
| --- | --- | --- |
| 阈值/机制开发 | `e10_structural_development`（冻结现状） | 只作为阈值来源与历史记录，**不再新增运行** |
| 机制外部效度检验 | `structural_benchmark_v1/development`（84） | 阈值冻结后在此验证泛化 |
| 冻结对比（与文献算法） | `structural_benchmark_v1/validation`（84） | 最终对比口径 |
| 最终确认 | `structural_benchmark_v1/test`（168） | **保持锁死**，需单独授权 |
| smoke / 单点调试 | legacy 8 个根实例（`R2_T6_0` 等） | 仅作冒烟，不得作为证据 |

`r2_sanity` 保持现状（协议/溯源产物，其 held-out 已被 R3 永久消费，不得复用）。

## §3 需要重跑/重测的清单（待你确认）

**成本标度律（实测，不是估计）**：E12 的 48 个 run 里 `runtime_seconds == budget_seconds == task_count`（误差 <3%，如 40 任务实例 40.0~40.3 s）。故一次实验墙钟成本
`= 种子数 × 方法数 × Σ(所选实例的 task_count)`。
v1 development 全量 Σtask = 4340 s（84 个实例：14×10+14×20+14×40+14×60+14×80+14×100）。

### B1 · 机制仪表在 v1 dev 上重跑（建议先做，最便宜）

- **做什么**：给 `e14` 加数据集/划分参数，对 v1 dev 84 个实例跑状态后悔 + regime 标注；对其中 R4/T40 子集（14 个）与 e10（21 个）做同设计格对照。
- **成本**：纯 DP 计算，84 实例 × ≤100 任务，分钟级。无 ALNS、无 LLM。
- **会改变什么**：e10 上得到的分布（informative 28.7%、HV-GEOM 独占 28 个 |gap|≥1% 位置）可能不成立。**这是检验，不是确认**——如果跨尺度后 regime 阈值区分不出来，`p2_feedback_design.md` §3 的阈值就要重冻结，连带影响 P2 的 F2 档位设计。
- **产出**：`outputs/e14_structural_v1_development/`。

### B2 · 算子演化从 legacy 迁到 v1 dev（核心决策）

两个选项，需你选：

- **B2-a（推荐）真在 v1 development 上演化**：在 dev 里挑演化子集（建议 7 族 × 2 尺度 = 14 个实例），跑 E5/E7 式演化 → 冻结 → 在 dev 剩余与 validation 上评估。
  - 成本：LLM 请求 ≈ 3~10 次（历史实测：E5 两轮 2 次请求 20,179 tokens / 189 s；E7 一次请求 14,068 tokens / 105 s）；候选评估 ALNS ≈ 30~60 min（候选数 × 实例 × 种子 × 短预算）；部署对比 3 配置 × 4 实例 × 2 种子 × 40 s ≈ 16 min。
  - 收益："演化在 dev、评估在 val/test"链条闭合，`gain_vs_V1` 才有标准含义。
- **B2-b 保留 legacy 演化，v1 定位为外部泛化集**：成本 0，但必须在论文里明写"算子在另一个数据集上演化，v1 仅作迁移评估"，并解释为什么不用 benchmark 的 dev split。

### B3 · 对比表扩样本（与 B2 强绑定）

- **为什么绑定**：E12/E13 的 `Proposed` 臂 = E11 冻结的 AUX 算子（同一批文件）。**换算子 ⇒ `algorithm_freeze.json` 必须重生成 ⇒ E12、E13 必须重跑**。
- **规模选项**（都在 dev 上，不碰 validation/test）：

| 方案 | 实例数 | Σtask (s) | 6 方法 × 2 种子总墙钟 |
| --- | --- | --- | --- |
| S（现状） | 4 | 150 | 0.5 h（已跑完） |
| M | 14（7 族 × R2/T20 + R4/T40 各一） | 420 | **1.4 h** |
| L | 42（每格 1 个重复，7 族 × 6 尺度） | 2170 | **7.2 h** |
| XL | 84（dev 全量） | 4340 | **14.5 h** |

- **建议 M 或 L**：M 能拆开"族"与"尺度"的部分混淆（每族覆盖两个尺度），L 才能每格无混淆但耗时翻 5 倍。
- 若选 B2-a，这一轮同时产出新的 AUX 对比；若选 B2-b，至少要把样本从 4 扩到 M/L，否则对比表本身站不住。

### B4 · P3 配对（P2 反馈的下一步，依赖 B1/B2 的数据集决定）

- **做什么**：在选定数据集上跑真实 ALNS 产出父/子解配对 JSON，喂 `e14 --stage solutions`，得到真实 report 与配对差分。
- **成本**：14 实例 × 3 种子 × 2 臂 × 40 s ≈ **56 min**（R4/T40 格）；若用 M 方案 ≈ 14×3×2×(20|40)/... ≈ 1.5 h。
- **依赖**：B1 的 regime 结论决定 F2 档位的证据头条是否还成立；若无 B1 就跑 P3，可能把"状态后悔"当头条而它其实无信息量。

### B5 · E15 标定 / E16 成本惩罚：**不重跑**

- E16 已判 `TURN_OFF`（24 配对，CI [−0.00844, +0.00865]）。它是"机制无效"的证据，不依赖数据集选择；换数据集重跑只会把负结果再做一遍。
- E15 的 `t_iteration` 只服务成本惩罚；惩罚关闭后无需重标定。若 B2 后重新评估成本奖励再考虑。

### B6 · E1–E9 历史输出：**不重跑，标注 legacy**

- 它们全部跑在 legacy 根实例上。保留为历史/诊断记录，在文档中标注 "legacy dataset（演化来源），不作为论文主证据"。
- 若选 B2-a，E5/E7 的产物被新演化取代，但旧记录不删（它们是方法演进的证据链）。

## §4 依赖关系（执行顺序不能乱）

```
B1 (机制仪表, 分钟级) ──► 确定 regime 阈值是否要重冻结
                             │
B2 决策 (a/b) ───────────────┤
                             ▼
                    B3 (对比表, 与 B2 绑定)
                             │
                             ▼
                    B4 (P3 配对, 依赖 B1 结论)
```

B3 必须在 B2 之后再跑（否则算子一换又白跑）。B1 独立，可以立刻跑。

## §5 代码改动（随 B1/B3 一起做，不单独占用运行时间）

1. `experiments/e14_state_regret_instrument.py`：新增 `--dataset {e10,v1} --split`，v1 走 manifest 取实例（保留 e10 路径可复现）。
2. `experiments/e15/e16`：数据集常量参数化（不改变默认行为）。
3. `experiments/e11/e12`：把硬编码 `SAMPLES` 换成可配置的 sample-plan JSON，为 B3 的 M/L 规模服务；sample-plan 先冻结再跑。
4. `llm/operator_evolution/evolution_loop.py`：`benchmark_instance_glob` 默认值改为**显式必填**（缺失即报错），避免下次静默在 8 个 legacy 实例上跑。
5. 文档：`data/README.md`（已改）、`docs/data_directory_audit.md`（已追加）、本文件。

## §6 待你确认（4 项）

1. **B1 现在就跑吗？**（分钟级，无风险，信息量最大）
2. **B2 选 a 还是 b？**（a = 真在 v1 dev 上演化，推荐；b = 保留 legacy，论文写成迁移评估）
3. **B3 规模选 S/M/L/XL？**（建议 M=1.4 h 或 L=7.2 h）
4. **B4 是否并入 B3 那一轮**（共用同一批 ALNS 运行，省一半墙钟）？

在你勾选之前，我不会启动任何重跑。
