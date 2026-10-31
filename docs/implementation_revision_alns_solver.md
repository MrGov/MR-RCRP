# 实现修订记录：`heuristics/alns_solver.py`（供 E12 重新运行使用）

日期：2026-10-30
用途：`e12_comparison --accept-hash-change docs/implementation_revision_alns_solver.md` 的验收凭据。

## 1. 为什么需要这份记录

E11 在 `outputs/e11_structural_benchmark/experiment_config.json` 的 `frozen_hashes` 里冻结了它当时实测的实现字节哈希。当前 `heuristics/alns_solver.py` 的字节已与该记录不同，因此 E12 的完整性门会拒绝启动（这是它应有的行为，不是 bug）。

不一致的文件只有一个：

| 文件 | E11 记录哈希 | 当前哈希 |
| --- | --- | --- |
| `src/mrta_rect_coverage/heuristics/alns_solver.py` | `0ca398a598d522b7367ea0eecda8930ea16f52df10c64b0952565345e5b64572` | `df767986d80b6f1ae1f2653919e9b2bb97a42ed0316d7b3b4cc22ab1adb14cc9` |

## 2. 差异到底是什么（已逐行核对）

`git diff 0949e078c1 HEAD -- src/mrta_rect_coverage/heuristics/alns_solver.py` 的内容**只是 P1 成本惩罚这一个特性**，共 43 增 6 删：

1. `ALNSConfig` 新增 `iteration_cost_penalty: bool = False` 与 `iteration_cost_reference_seconds: float | None = None`（默认关闭）；
2. `__post_init__` 只在 `iteration_cost_penalty` 为真时做两条校验（关闭时是空分支）；
3. `measured_stage_seconds` 的赋值位置从「计算 `iteration_elapsed` 之后」提前到「`local_search_seconds` 之后」——**表达式完全相同**，只是提前算，以便奖励阶段可用；
4. 奖励拆成 `score_raw`（8/3/1 语义不变）与 `score = score_raw * cost_penalty_factor`，因子在关闭时恒为 `1.0`；
5. `new_global_best` 改为用 `score_raw >= 8.0`（关闭时 `score_raw == score`，判据等价）；
6. `history` 增加 4 个字段（`measured_stage_seconds`、`cost_penalty_factor`、`score_raw`、`score_effective`），`ALNSResult` 增加 `iteration_cost_reference_seconds` 字段。这些字段**不参与任何决策**。

## 3. 默认路径等价性证据（已实测，不是推断）

对 `0949e078c1` 的旧模块与当前模块做**确定性**对比：固定迭代数 40、`cooling_schedule="iteration"`、`random_seed=7`，逐迭代比较 `(best_makespan, destroy, repair, accepted)` 决策轨迹。

| 实例 | 旧实现 makespan | 当前 makespan | 决策轨迹 |
| --- | ---: | ---: | --- |
| `R2_T6_0` | 206.000000 | 206.000000 | 完全相同 |
| `R2_T10_0` | 894.000000 | 894.000000 | 完全相同 |
| `R2_T20_0` | 1642.000000 | 1642.000000 | 完全相同 |

配合 `tests/test_iteration_cost_penalty.py` 的「关闭 ≡ 因子恒 1」用例，可以认定：**在默认配置（未开启 `iteration_cost_penalty`）下，当前实现与 E11 实测实现的行为一致**。

## 4. 附注：E11 记录哈希的来源

`0ca398…` 不对应任何已提交修订（对 `alns_solver.py` 的 5 个历史提交逐一比对均不匹配），说明 E11 冻结时的工作树含有未提交字节。这是仓库自身记录方式的历史问题，本记录不试图修复它，只把它显式标注出来。

## 5. 本记录不改变什么

- 不改 E11 的 `algorithm_freeze.json` / `experiment_config.json`；
- 不改 E12 默认输出目录的历史记录（新对比必须写到全新的 `--output`）；
- 不开启 `iteration_cost_penalty`（E16 已判定 TURN_OFF，见 `docs/e16_cost_penalty_ablation_result.md`）。
