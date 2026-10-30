# P0′ 实施任务单：只读状态链 / 状态 regret 仪表

> 依据：`docs/dp_feedback_chain_design_v0.3.md` §2.2、§3、§10。
> 授权：本任务单只允许**新增文件**。**禁止修改** `core/dp_evaluator.py`、`core/solution_evaluator.py`、`core/cost_matrix.py`、`core/state_generator.py`、`core/models.py`、`heuristics/alns_solver.py`、`llm/operator_evolution/*`。
> 当前状态：**尚未创建任何文件，尚未运行任何测试**。下列各项均待执行。
> 项目根：`mrta_rect_coverage/`；源码在 `src/mrta_rect_coverage/`；Python 环环境 `G:\Anaconda\envs\mrta_env\python.exe`（已确认存在）；`pyproject.toml` 要求 `>=3.11`。

---

## 1. 交付物清单（4 个新文件，0 个改动）

| # | 路径 | 类型 | 作用 |
|---|---|---|---|
| 1 | `src/mrta_rect_coverage/core/state_chain_report.py` | 新增 | 仪表核心：I0 腿分解 / I2 状态链 / I3 regret 表 / 一致性断言 |
| 2 | `tests/test_state_chain_report.py` | 新增 | T1–T9 单元与对拍测试 |
| 3 | `src/mrta_rect_coverage/experiments/e14_state_regret_instrument.py` | 新增 | 薄运行器：`smoke` / `parents` / `verify` 三阶段 |
| 4 | `tests/test_e14_state_regret_instrument.py` | 新增 | 运行器冒烟测试（单实例） |

**分层约束**：文件 1 位于 `core/`，只允许 import `core.cost_matrix`、`core.models`、`utils.geometry`。**禁止** import `experiments/`、`heuristics/`、`llm/`（避免反向依赖）。

---

## 2. 文件 1：`core/state_chain_report.py`

### 2.1 模块头与常量

```python
"""Read-only state-chain and state-regret instrumentation for fixed routes.

This module never mutates RouteDPEvaluator, never re-enters its DP and never
changes its cache. It recomputes forward/backward DP tables locally from
CostMatrix + State, which is O(64k) per route - the same order as one route DP.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple

from .cost_matrix import CostMatrix
from .models import (
    Instance, MultiRobotSolution, RouteEvaluation, SolutionEvaluation, State,
)

REGRET_TOL = 1e-9          # 与 DP 内部 1e-8/1e-9 容差同量级
DEFAULT_NEAR_TIE_TOL = 0.0  # 严格并列；运行器可传具体秒数
```

### 2.2 数据结构

```python
@dataclass(frozen=True)
class StateOption:
    state_id: int
    entry_corner: str        # "LB"/"LT"/"RB"/"RT"
    sweep_mode: str          # "H"/"V"
    exit_corner: str
    n_sweeps: int
    processing_time: float
    prefix_cost: float       # F_j(s)，【含】P_j
    suffix_cost: float       # B_j(s)，【不含】P_j
    q_cost: float            # F_j(s) + B_j(s)
    regret: float            # q_cost - route_optimal_cost
    def to_dict(self) -> dict: ...

@dataclass(frozen=True)
class PositionRegret:
    position: int            # 0-based
    task_id: int
    chosen_state_id: int
    chosen_rank: int         # 1-based，在 options（已按 (q_cost, state_id) 升序）中的位次
    min_alternative_regret: float   # 非选中状态中的最小 regret；无替代时返回 inf
    near_tie_count: int      # 非选中状态中 regret <= near_tie_tol 的个数
    options: Tuple[StateOption, ...]
    def to_dict(self) -> dict: ...

@dataclass(frozen=True)
class RouteRegretReport:
    route_task_ids: Tuple[int, ...]
    route_optimal_cost: float          # 本模块独立算出的 C_r*
    evaluator_total_cost: float        # RouteEvaluation.total_cost，用于对拍
    positions: Tuple[PositionRegret, ...]
    def to_dict(self) -> dict: ...
```

### 2.3 核心函数

```python
def route_regret_report(
    route_evaluation: RouteEvaluation,
    *,
    states_by_task: Dict[int, Iterable[State]],
    cost_matrix: CostMatrix,
    near_tie_tol: float = DEFAULT_NEAR_TIE_TOL,
) -> RouteRegretReport:
```

**算法（必须严格按此实现，`P` 只计一次）**

```
route = list(route_evaluation.route_task_ids)
若 route 为空: 返回 RouteRegretReport((), 0.0, route_evaluation.total_cost, ())
若 route 中有重复 task_id 或 task 不在 states_by_task: raise ValueError(带 task_id)
layers = [list(states_by_task[t]) for t in route]；任一层为空 → raise ValueError

# 前向：F[j][s] 含 P_j
F = []
for j, states in enumerate(layers):
    cur = {}
    for s in states:
        if j == 0:
            cur[s.state_id] = cost_matrix.depot_to_state(s.state_id) + s.processing_time
        else:
            cur[s.state_id] = min(
                F[j-1][p.state_id] + cost_matrix.transition(p.state_id, s.state_id)
                for p in layers[j-1]
            ) + s.processing_time
    F.append(cur)

# 后向：B[j][s] 不含 P_j
B = [dict() for _ in layers]
for j in range(len(layers)-1, -1, -1):
    for s in layers[j]:
        if j == len(layers)-1:
            B[j][s.state_id] = cost_matrix.state_to_depot(s.state_id)
        else:
            B[j][s.state_id] = min(
                cost_matrix.transition(s.state_id, t.state_id)
                + t.processing_time + B[j+1][t.state_id]
                for t in layers[j+1]
            )

C_star = min(F[-1][sid] + cost_matrix.state_to_depot(sid) for sid in F[-1])

# Q_j(s) = F_j(s) + B_j(s)；排序键 (q_cost, state_id) 保证确定性
for j, states in enumerate(layers):
    options = sorted(
        (StateOption(..., q_cost=F[j][s.state_id] + B[j][s.state_id],
                     regret=q_cost - C_star) for s in states),
        key=lambda o: (o.q_cost, o.state_id),
    )
    chosen = route_evaluation.chosen_state_ids[j]
    chosen_rank = 1 + sum(1 for o in options if (o.q_cost, o.state_id) < (Q[chosen], chosen))
```

**必须实现的自检（在函数返回前执行，失败即 `raise ValueError`，不带容差宽松化）**

1. `abs(C_star - route_evaluation.total_cost) <= 1e-6`；
2. 每个位置 `min(o.q_cost for o in options) == 期望值`，且该最小值与 `C_star` 差 `<= REGRET_TOL`；
3. 每个位置中 `chosen_state_id` 对应的 `q_cost` 与 `C_star` 差 `<= REGRET_TOL`；
4. 所有 `regret >= -REGRET_TOL`。

> 恒等式 2、3 只在 `F` 含 `P_j` 且 `B` 不含 `P_j` 时同时成立。这是本模块最关键的防错闸门：若实现者把 `P_j` 在两端都算，条件 3 必然失败（`Q` 比 `C_star` 大一个 `P_j`）。

```python
def route_cost_split(
    route_evaluation: RouteEvaluation,
    *,
    instance: Instance,
    task_by_id: Dict[int, "TaskRegion"],
) -> dict:
    """I0：sweep / turn / transfer 三段分解，并内置恒等式断言。"""
```

实现要点（与 `experiments/e10b_structural_dp_analysis.py:60–80` 同构；公式见 v0.3 §2.3）：

- `coverage += s.n_sweeps * (task.width if s.sweep_mode.value == "H" else task.height) / instance.sweep_speed`
- `turning += max(0, s.n_sweeps - 1) * instance.turning_time`
- `transfer = sum(route_evaluation.transition_costs)`
- 断言 `abs(coverage + turning + transfer - route_evaluation.total_cost) <= 1e-6`，失败抛 `ValueError`（附 `route_task_ids` 与三项数值）。
- 返回 `dict(coverage=, turning=, transfer=, total=, transfer_share=, coverage_share=, turning_share=)`，`*_share` 在 `total == 0` 时取 `0.0`。

```python
def state_chain_rows(
    route_evaluation: RouteEvaluation, *, route_id: int,
) -> List[dict]:
    """I2：逐任务状态链行，键为 task_id/route_id/position/state_id/entry/mode/exit/n_sweeps/processing_time。"""
```

- 直接消费 `route_evaluation.chosen_states`（`core/models.py:97`，已由 DP 返回），**不得**重新调用 DP。
- `entry` / `exit` / `mode` 取枚举 `.value`；不得输出枚举对象（JSON 不可序列化）。

```python
def solution_state_report(
    instance: Instance,
    solution: MultiRobotSolution,
    evaluation: SolutionEvaluation,
    *,
    states_by_task: Dict[int, Iterable[State]],
    cost_matrix: CostMatrix,
    solution_hash: str | None = None,
    near_tie_tol: float = DEFAULT_NEAR_TIE_TOL,
    include_regret: bool = True,
) -> dict:
```

返回结构（可直接 `json.dump`）：

```json
{
  "instance": {"name": ..., "task_count": ..., "robot_count": ...,
               "sweep_width": ..., "sweep_speed": ..., "travel_speed": ..., "turning_time": ...,
               "depot": [x, y]},
  "solution_hash": "...",
  "makespan": ...,
  "per_robot_costs": [...],
  "route_load_excess": <max(per_robot_costs) - mean(per_robot_costs)>,
  "bottleneck_routes": [i, ...],
  "objective": {"mean_processing": ..., "mean_transfer": ..., "load_excess": ..., "makespan": ...},
  "routes": [{"route_id":i,"task_order":[...],
              "cost_split":{...},            // I0
              "state_chain":[...],           // I2
              "regret_table":[PositionRegret.to_dict(), ...]   // I3
             }, ...]
}
```

- `objective` 中的三个量必须满足 `mean_processing + mean_transfer + load_excess == makespan`（容差 1e-6），空路线计入 mean——此断言写在函数内。
- `mean_processing` 取各路线 `coverage + turning` 的均值；`mean_transfer` 取 `transfer` 的均值。
- `include_regret=False` 时跳过 I3（用于只想要 I0/I2 的快速通道）。

```python
def assert_report_consistent(report: dict, *, tol: float = 1e-6) -> None:
    """对 solution_state_report 的产物做独立复核，供 verify 阶段与测试调用。"""
```

校验项：`objective` 恒等式、每条路线 `cost_split` 恒等式、每个位置 `regret` 最小值 `== 0`（容差 `REGRET_TOL`）、`chosen_rank >= 1`、`min_alternative_regret >= -REGRET_TOL`。任何一项不符抛 `ValueError` 并指明 `route_id` / `position`。

---

## 3. 文件 2：`tests/test_state_chain_report.py`

风格对齐现有测试：`from __future__ import annotations`、纯函数式 `assert`、无 fixture（参考 `tests/test_dp_evaluator.py`）、路径用 `Path(__file__).resolve().parents[1]`。

公共辅助：

```python
def _build(instance_name: str = "R2_T6_0.txt"):
    instance = load_instance(PROJECT_ROOT / "data" / instance_name)
    states_by_task = generate_all_states(instance)
    cost_matrix = CostMatrix(instance.depot, states_by_task, travel_speed=instance.travel_speed)
    route_dp = RouteDPEvaluator(cost_matrix, states_by_task)
    return instance, states_by_task, cost_matrix, route_dp

def _brute_force_chain_cost(chain, cost_matrix):
    total = cost_matrix.depot_to_state(chain[0].state_id)
    for a, b in zip(chain, chain[1:]):
        total += cost_matrix.transition(a.state_id, b.state_id)
    total += sum(s.processing_time for s in chain)
    total += cost_matrix.state_to_depot(chain[-1].state_id)
    return total
```

| 编号 | 用例 | 断言 |
|---|---|---|
| **T1** | 空路线 | `route_regret_report(route_dp.evaluate_route([]), ...).positions == ()`，`route_optimal_cost == 0` |
| **T2** | 单任务路线 `[1]` | 8 个 option；`min(q_cost) == total_cost`；选中项 `regret == 0`；`chosen_rank` 为选中状态按 `(q, state_id)` 的位次 |
| **T3** | 两任务路线 `[1,2]` | 每个位置 `min_s Q_j(s) == C_r*` 且 `Q_j(chosen) == C_r*`（容差 1e-9） |
| **T4** | 三任务路线 `[1,2,3]` 暴力对拍 | 枚举全部 `8**3 = 512` 条状态链，`min(_brute_force_chain_cost) == C_r*`；对每个 `(j, s)`，把「第 j 位固定为 s」的链子集取最小，逐项等于 `Q_j(s)`（容差 1e-9） |
| **T5** | 篡改检测 | 把某 option 的 `regret` 改为负值 / 把 `route_optimal_cost` 加 1，`assert_report_consistent` 必须抛 `ValueError` |
| **T6** | 只读性 | 生成报告前后 `route_dp.statistics()["calls"]` 不变；`cache_misses` 不变 |
| **T7** | 确定性 | 连续两次 `to_dict()` 完全相等（`==`，非近似） |
| **T8** | 腿分解恒等式 | 每条路线 `abs(coverage + turning + transfer - total) <= 1e-6`；`sum(transfer)` 与 `sum(transition_costs)` 一致 |
| **T9** | 排序与 tie-break | 每个位置 `options` 严格按 `(q_cost, state_id)` 升序；`state_id` 唯一 |

补充用例（防回归）：

| 编号 | 用例 | 断言 |
|---|---|---|
| **T10** | 非法输入 | 路线含重复 task_id、含未知 task_id、`states_by_task` 缺层 → 均抛 `ValueError` 且消息含 task_id |
| **T11** | `near_tie_tol` 生效 | 用 `near_tie_tol=0.0` 与 `near_tie_tol=1e9` 各跑一次，后者 `near_tie_count == 7`（全部并列） |

**T4 是本任务单的核心**：它是唯一能独立证明「`P` 只计一次、`Q` 表定义正确」的证据。若 T4 通过而 T3 失败，说明实现与 DP 的最优链选择不一致；若 T3 通过而 T4 失败，说明 `F/B` 递归边界写错。

---

## 4. 文件 3：`experiments/e14_state_regret_instrument.py`

### 4.1 骨架

```python
"""E14: read-only state-chain / state-regret instrumentation (no DP changes)."""
ROOT = Path(__file__).resolve().parents[3]        # = mrta_rect_coverage/
SRC  = ROOT / "src"                               # 与 e10b 的 ROOT 约定一致
DEFAULT_OUTPUT = ROOT / "outputs/e14_state_regret_instrument"
E10B_OUTPUT    = ROOT / "outputs/e10b_structural_dp_analysis"

def evaluator_for(instance):
    states = generate_all_states(instance)
    cm = CostMatrix(instance.depot, states, travel_speed=instance.travel_speed)
    return states, cm, MultiRobotSolutionEvaluator(RouteDPEvaluator(cm, states), instance=instance)

def round_robin_solution(instance):        # smoke 用：把任务按 id 轮转分给 R 条路线
def stage_smoke(output):                   # 单实例 R2_T6_0
def stage_parents(output):                 # 读 E10-B inputs/*.json 的 parent_routes，21 个实例
def stage_verify(output):                  # 重跑 assert_report_consistent + 比对 evaluator 统计
def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--stage", choices=("smoke", "parents", "verify"), required=True)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--near-tie-tol", type=float, default=0.0)
```

### 4.2 三阶段行为

**`smoke`**
- 输入：`data/R2_T6_0.txt`；解：`round_robin_solution`。
- 输出：`outputs/e14_state_regret_instrument/smoke/R2_T6_0.json`。
- 同时写 `meta.json`：`{"git_head": ..., "python": sys.version, "near_tie_tol": ..., "dp_statistics_before": ..., "dp_statistics_after": ...}`。
- **不检查** `E10B_OUTPUT` 是否存在。

**`parents`**
- 前置：`E10B_OUTPUT/inputs/*.json` 已存在（**已确认存在 21 个文件**，如 `E10_BASE_r0.json`）。若缺失，直接 `raise SystemExit("run e10b --stage prepare first")`。
- 对每个 input 文件：读 `instance_id` / `entry` / `parent_routes` / `input_id` / `fixed_destroy_hash`，`load_instance` 后生成完整 `solution_state_report`。
- 输出：`outputs/e14_state_regret_instrument/parents/{instance_id}.json`，顶层附 `input_id`、`fixed_destroy_hash`、`parent_routes`、`parent_label`。
- 每个实例记录 `dp_statistics_before/after`，断言 `calls` 未增加。
- **不重跑 destroy、不重跑 repair、不调用 LLM**（纯只读）。

**`verify`**
- 遍历 `smoke/` 与 `parents/` 下所有 JSON，逐个 `assert_report_consistent`。
- 汇总并打印：实例数、路线总数、位置总数、最小/最大 `min_alternative_regret`、`near_tie_count>0` 的位置占比、失败项列表。
- 写 `outputs/e14_state_regret_instrument/verify_summary.json`；有失败项则非零退出码。

### 4.3 文件级不可妥协项

1. **不得** import `experiments.e10b_structural_dp_analysis` 的任何**函数**（避免哈希冻结冲突）；只读它的**输出 JSON 文件**。
2. **不得**写任何 `experiment_config.json` 冻结清单（本阶段不冻结，也就不必改 `e10b` 的 frozen hashes）。
3. `near_tie_tol` 必须写进 `meta.json` 与每个结果文件，避免口径漂移。

---

## 5. 文件 4：`tests/test_e14_state_regret_instrument.py`

- `test_smoke_stage_creates_report(tmp_path)`：以 `tmp_path` 为 output 跑 `stage_smoke`，断言文件存在、`assert_report_consistent` 通过、`meta.json` 中 `dp_statistics_before["calls"] == dp_statistics_after["calls"]`。
- `test_round_robin_solution_is_partition`：任务恰好覆盖一次、路线数 == `robot_count`、`MultiRobotSolutionEvaluator.evaluate` 不抛异常。
- `test_parents_stage_requires_e10b`：把 `E10B_OUTPUT` 指向不存在目录时 `SystemExit`。

---

## 6. 执行命令（待执行）

```powershell
cd D:\VScode\20251217-yang\R_MRTA_01-copy\mrta_rect_coverage
$env:PYTHONPATH='src'

# 1) 单元 + 对拍测试
& 'G:\Anaconda\envs\mrta_env\python.exe' -m pytest tests/test_state_chain_report.py tests/test_e14_state_regret_instrument.py -q

# 2) 冒烟
& 'G:\Anaconda\envs\mrta_env\python.exe' -m mrta_rect_coverage.experiments.e14_state_regret_instrument --stage smoke

# 3) 21 个 development 父解
& 'G:\Anaconda\envs\mrta_env\python.exe' -m mrta_rect_coverage.experiments.e14_state_regret_instrument --stage parents

# 4) 独立复核
& 'G:\Anaconda\envs\mrta_env\python.exe' -m mrta_rect_coverage.experiments.e14_state_regret_instrument --stage verify
```

若 `mrta_env` 不可用，备选：`C:\Users\15628\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe`（需自行确认是否装了 pytest；否则用 `python -m unittest` 或将测试改写为可 `python -c` 调用）。

---

## 7. 完成定义（DoD）

1. 4 个新文件创建；`git status --porcelain` 只出现 `??` 未跟踪项，**无任何 `M` 修改项**。
2. T1–T11 全部通过；其中 **T4（暴力对拍）与 T6（只读性）必须通过**，否则视为未完成。
3. `--stage smoke` 产出 1 个 JSON + `meta.json`，`assert_report_consistent` 通过。
4. `--stage parents` 产出 21 个 JSON，全部 `dp_statistics_before["calls"] == after["calls"]`。
5. `--stage verify` 退出码 0，`verify_summary.json` 中失败项为空。
6. 报告中每条路线的 `cost_split` 恒等式与 `objective` 恒等式全部成立。

---

## 8. 风险与回滚

| 风险 | 症状 | 处置 |
|---|---|---|
| `P_j` 在 `F`、`B` 双计 | T3 恒等式 3 失败，`Q` 比 `C*` 大一个 `P_j` | 按 §2.3 注释修正 `B` 递归（`B` 不含当前任务 `P`） |
| `cost_matrix.transition` 同任务对缺键 | `KeyError`（`core/cost_matrix.py:72` 跳过同任务对） | 前置校验：相邻位置 task_id 相同即 `ValueError`（非法解） |
| `sweep_width` 语义在代码中是「扫描线数」而非「带宽」 | T8 恒等式不成立 | 以 `state_generator._compute_processing_time` 为准；`route_cost_split` 只复制其口径，不改动 |
| `state_id` 跨实例复用 | 21 个实例结果串味 | 报告中始终带 `instance.name`；禁止跨实例比较裸 `state_id`（v0.3 §2.1） |
| 报告写入 `e10b` 输出目录 | 冻结哈希校验报错 | 输出**只写** `outputs/e14_state_regret_instrument/` |

**回滚**：删除上述 4 个新文件即可，无其他副作用（未改动任何既有文件、未写入既有输出目录）。

---

## 9. 与后续阶段的接口（不在本单实现）

P2 阶段构造 `F2_contrastive` 时，直接消费本单产物：

- `parents/{id}.json → routes[].regret_table` 提供 I3 高亮（限于 `changed_tasks`）；
- `routes[].cost_split` 提供 I0；
- `routes[].state_chain` 提供 I2；
- A/B 对照的父子两侧各需一份本报告，按 `task_id` 对齐（不按下标硬比，v0.3 §3）。

本单**不**实现：反馈模板、prompt 组装、`Δ(h|S)`、null 分布、`iteration_cost_penalty`。这些分别在 P2 / P3 / P1 下发。
