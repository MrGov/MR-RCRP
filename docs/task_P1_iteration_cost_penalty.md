# P1 实施任务单：`iteration_cost_penalty` + 运行时 `t_ref` 标定

- 依据：`docs/dp_feedback_chain_design_v0.3.md` §7（口径 (b)：四项耗时总和，不归因到单个算子）
- 前置：P0′/P0″ 已通过（19 个测试全绿，22 份报告 failures = []）
- 本轮改动范围：**1 个新实验脚本 + 1 个新测试文件 + `heuristics/alns_solver.py` 的受控小改**
- 禁止：改 `core/`（dp_evaluator / solution_evaluator / cost_matrix / state_generator）、改算子实现、改 B1 预设默认值

---

## §1 目标与判据

**目标**：在**固定墙钟预算**下，让 ALNS 的自适应权重感知「一次迭代的耗时」，
从而让「快而略差」的算子有机会与「慢而略好」的算子公平竞争。

**判据（预注册）**：

1. 只有 `max_runtime_seconds` 固定、`iterations=None` 时才允许开启本机制。
   若按固定迭代数比较，机制**按构造无效**，不得据此判断「机制无效」。
2. 竞争臂：`S`（现状 B1）vs `S + cost_penalty`，同实例、同 seed、同墙钟预算。
3. 若在 development 划分上 `Δmakespan` 的中位数与 95% CI 覆盖 0 → **关闭该机制并如实记录**
   （这是允许的结论，不得沿用 vNext 的「有改善」表述）。

---

## §2 设计要点

- 惩罚乘子作用在**每次迭代的奖励**上，不改接受准则、不改算子实现、不改候选解评价。
- 保留**原始分数**用于「是否刷新全局最优」的判断（`score_raw >= 8.0`），
  **仅**对进入算子权重与使用的奖励乘惩罚因子。
- 惩罚因子：`factor = min(1.0, sqrt(t_ref / max(t_t, eps)))`，`t_t = measured_stage_seconds`。
- `t_ref` 必须**运行时标定**（绑机器的绝对常数不可复现）：
  `t_ref = kappa * t_probe`，`t_probe` = 清缓存后重复 `evaluate_route` 固定路线的耗时中位数，
  `kappa = 8.0`（预注册，标定后冻结；若实测 `kappa` 导致 factor 恒等于 1，则机制自动失效，
  需在报告中显式说明而不是调 kappa）。

---

## §3 代码改动（文件级）

### 3.1 `src/mrta_rect_coverage/heuristics/alns_solver.py`（唯一被改的既有文件）

**3.1.1 `ALNSConfig`（42–97 行）新增两个字段**

```python
iteration_cost_penalty: bool = False
iteration_cost_reference_seconds: float | None = None
```

**3.1.2 `ALNSConfig.__post_init__`（79–97 行）新增校验**

```python
if self.iteration_cost_penalty:
    if self.max_runtime_seconds is None:
        raise ValueError(
            "iteration_cost_penalty requires max_runtime_seconds "
            "(a fixed iteration count makes the penalty meaningless)"
        )
    if (self.iterations is not None and self.max_runtime_seconds is None):
        raise ValueError("unreachable")
    ref = self.iteration_cost_reference_seconds
    if ref is None or not math.isfinite(ref) or ref <= 0:
        raise ValueError(
            "iteration_cost_penalty requires a positive calibrated "
            "iteration_cost_reference_seconds"
        )
```

（第二条 `unreachable` 分支是多余防御，实现时**删除**，只保留前两条。）

**3.1.3 主循环：把 `measured_stage_seconds` 提前到奖励计算之前**（现在在 421 行）

在 `local_search_seconds` 赋值之后（327–328 行之后）插入：

```python
measured_stage_seconds = (
    destroy_seconds + partial_evaluation_seconds
    + repair_seconds + local_search_seconds
)
```

421 行的同名赋值改为复用该变量（不重复计算）。

**3.1.4 奖励处（336–344 行）拆成 raw / effective**

```python
score_raw = 0.0
...
score_raw = 8.0 / 3.0 / 1.0            # 语义不变
score = score_raw
cost_penalty_factor = 1.0
if self.config.iteration_cost_penalty:
    reference = float(self.config.iteration_cost_reference_seconds)
    cost_penalty_factor = min(
        1.0, math.sqrt(reference / max(measured_stage_seconds, 1e-12))
    )
    score = score_raw * cost_penalty_factor
```

- `score_raw >= 8.0` 处（404 行 `new_global_best`）**改用 `score_raw`**。
- `destroy_reward` / `repair_reward`（376–385）用 `score`（已含惩罚）；fallback 仍为 0，
  且必须是**先乘惩罚、后应用 fallback 置零**，保证 fallback 永不为正。
- `pair_action_stats["reward"]`（406）用 `score`。

**3.1.5 迭代历史（424–439 行起）新增四个只读字段**

```python
"measured_stage_seconds": measured_stage_seconds,
"cost_penalty_factor": cost_penalty_factor,
"score_raw": score_raw,
"score_effective": score,
```

**3.1.6 `ALNSResult`（106–122 行）新增**

```python
iteration_cost_reference_seconds: float | None = None
```

在 `solve()` 返回处填 `self.config.iteration_cost_reference_seconds`。

**兼容性要求**：默认 `iteration_cost_penalty=False` 时，所有既有行为的数值结果必须**逐位不变**
（`score`、`operator_usage_stats`、`best_evaluation`、`iteration_history` 除新增字段外不变）。

### 3.2 `src/mrta_rect_coverage/experiments/e15_cost_penalty_calibration.py`（新文件）

职责：运行时标定 `t_ref`，产出可冻结的标定记录。

```
ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = ROOT / "outputs/e15_cost_penalty_calibration"
```

- `--stage calibrate --instance data/R2_T6_0.txt --repeats 20 --kappa 8.0`
- 标定流程：构造 states/CostMatrix/RouteDP → 固定路线 `list(range(1, task_count+1))`
  → 预热一次 → 循环 `repeats` 次：`route_dp._cache.clear()` 后 `perf_counter()` 包 `evaluate_route`
  → 取**中位数** `t_probe`。
- 输出 `calibration.json`：

```json
{
  "git_head": "...",
  "python": "...",
  "instance": "R2_T6_0",
  "route": [1, 2, 3, 4, 5, 6],
  "repeats": 20,
  "t_probe_seconds": 0.000412,
  "kappa": 8.0,
  "t_ref_seconds": 0.003296,
  "samples_seconds": [...],
  "machine_fingerprint": {"platform": "...", "processor": "...", "python": "..."},
  "created_at": "..."   // UTC ISO8601，仅记录，不参与判定
}
```

- `--stage verify`：读 `calibration.json`，断言 `t_ref == kappa * t_probe`（1e-12）
  且 `samples` 中位数等于 `t_probe`（1e-12），打印并返回退出码。
- 禁止：不 import `e10b` / `e14` 的函数，不写 `experiment_config.json`。

### 3.3 `tests/test_iteration_cost_penalty.py`（新文件）

| 编号 | 用例 | 断言 |
| --- | --- | --- |
| P1-T1 | 默认关闭等价性 | 同实例同 seed 同迭代数，`iteration_cost_penalty=False` 时 `best_evaluation.makespan`、`operator_usage_stats` 与改动前基线一致（用仓库内固定基线 fixture 或 golden 值）；`history` 的 `score_effective == score_raw` |
| P1-T2 | 缺墙钟预算即报错 | `iteration_cost_penalty=True, max_runtime_seconds=None` → `ValueError` 含 `max_runtime_seconds` |
| P1-T3 | 缺参考耗时即报错 | 有墙钟但 `iteration_cost_reference_seconds=None` → `ValueError` 含 `reference_seconds` |
| P1-T4 | 因子上下界 | 构造 `measured_stage_seconds` 已知的假迭代：`t_ref` 极小 → `factor < 1`；`t_ref` 极大 → `factor == 1.0`；`factor` 恒在 `(0, 1]` |
| P1-T5 | fallback 不为正 | 令 destroy 抛错触发 fallback，`destroy_reward == 0.0`，且 `reward_attribution == "fallback_excluded"` |
| P1-T6 | 原始分数语义不变 | `score_raw == 8.0` 的迭代仍刷新 `new_global_best`，即使 `factor < 1` |
| P1-T7 | 确定性 | 同配置两次 `solve()`，`history` 的 `score_effective` 序列完全一致 |
| P1-T8 | 权重受影响 | 两个算子耗时差 4 倍时，慢者 `score` 严格小于快者的 `score_raw` 加权和（构造最小实例直接验证 segment 权重的分子） |

---

## §4 运行命令

```powershell
cd mrta_rect_coverage
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
$py = 'G:\Anaconda\envs\mrta_env\python.exe'

& $py -m pytest tests/test_iteration_cost_penalty.py -q -p no:cacheprovider
& $py -m mrta_rect_coverage.experiments.e15_cost_penalty_calibration --stage calibrate
& $py -m mrta_rect_coverage.experiments.e15_cost_penalty_calibration --stage verify
& $py -m pytest tests/ -q -p no:cacheprovider      # 全量回归，必须全绿
```

---

## §5 DoD

1. `tests/test_iteration_cost_penalty.py` 8/8 通过；全量 `tests/` 无新增失败。
2. `git status --porcelain` 只出现 `M heuristics/alns_solver.py` + 2 个 `??` 新文件。
3. `outputs/e15_cost_penalty_calibration/calibration.json` 存在，`verify` 退出码 0。
4. 关闭开关时 `iteration_history` 的 `score_effective` 与 `score_raw` 完全相等（可用 e3 类既有运行抽查一份结果 JSON）。
5. 报告中必须写明：`t_ref` 是**本机标定值**，跨机器需重跑 `calibrate`。

## §6 回滚

`git checkout -- src/mrta_rect_coverage/heuristics/alns_solver.py` 并删除两个新文件；
`outputs/e15_cost_penalty_calibration/` 可保留（纯数据）。

---

## §7 实施记录（已完成，2026-10-30）

DoD 全部满足：

| 项 | 结果 |
| --- | --- |
| `tests/test_iteration_cost_penalty.py` | **10 passed**（任务单 8 个 + 2 个 e15 往返；T4 拆成因子下界/上界两条断言） |
| 全量 `pytest`（bare，靠 testpaths） | **281 passed / 0 failed**（P1 前为 271） |
| `git status --porcelain` | `M heuristics/alns_solver.py`、`?? experiments/e15_cost_penalty_calibration.py`、`?? tests/test_iteration_cost_penalty.py`（+ 上一轮的 docs/清理改动） |
| `e15 --stage calibrate` / `verify` | 退出码 0，`outputs/e15_cost_penalty_calibration/calibration.json` 已生成 |
| 开关关闭时 `score_effective == score_raw` | 见 P1-T1 |

**两处与任务单的偏差（必须记住，否则会误判测试失败）：**

1. **P1-T7「`score_effective` 序列完全一致」按设计不可满足。**
   因子由 `measured_stage_seconds`（墙钟实测）算出，因此 `score_effective` 天然不可复现。
   断言已改为：决策轨迹（destroy/repair 选择、`score_raw`、current/best makespan）逐行一致，
   且每行满足 `score_effective == score_raw * cost_penalty_factor`（精确到 1e-12）、`0 < factor < 1`。
   这条要在论文/文档里写明：**成本惩罚的有效奖励是墙钟相关量，不是可复现统计量**；
   可复现的是 `score_raw` 轨迹。
2. **单元测试统一用 `cooling_schedule="iteration"`。**
   B1 预设的 `cooling_schedule="progress"` 按已用墙钟时间降温，两次运行温度不同，
   会让「关闭等价」「确定性」这类逐行对比必然失败；测试里固定为 `"iteration"`，
   真实实验仍用 B1 的 `"progress"`。
3. **开启惩罚时测试必须显式给 `max_runtime_seconds`**（例如永不触发的 `3600.0`），
   因为 `__post_init__` 拒绝「固定迭代数 + 成本奖励」这种无意义组合；终止仍按迭代数发生，
   所以两次运行可比。

**`kappa=8.0` 的依据**见 `docs/p2_feedback_design.md` §7b：实测一次典型 ALNS 迭代 ≈ 4.3 个
probe 单位，`kappa=8` 使**典型迭代因子恒为 1.0**、只有明显贵的迭代被折价（最贵约 0.54）。
这是刻意的软惩罚 —— 若把全部奖励压成同一常数比例，只会缩放权重质量而不改变算子排序，
机制就测不出差异。

