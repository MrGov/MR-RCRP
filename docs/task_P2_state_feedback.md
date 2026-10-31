# P2 实施任务单：状态证据反馈（regime 标签 + 三档 payload + prompt 注入）

- 依据：`docs/p2_feedback_design.md`（v0.1，§7 三项取舍已拍板）与
  `docs/e16_cost_penalty_ablation_result.md`（成本惩罚已关闭，不进 P2）
- 适用范围：**只读反馈层**。禁止修改 `core/dp_evaluator.py`、
  `core/solution_evaluator.py`、`heuristics/alns_solver.py`
- 既有函数签名只能**追加可选关键字参数**，不得改变既有调用方的行为
- 新增 3 文件、修改 3 文件、新增 2 个测试文件、扩充 1 个测试文件

---

## §0 一句话目标

把 P0″ 已经算出来的**位置级精确证据**转成 LLM 可用的结构化反馈：
regime 自动标签（E3）+ 路线成本结构（E1）+ 配对差分（E2）+ 限流的
位置注解（E4），并在 `F1_scalar` 之上形成 `F2_state_v2` / `F2_contrastive_v2`
两档 payload。**不新增任何 DP 计算**，全部复用已有 report 字段。

---

## §1 新增文件 1：`src/mrta_rect_coverage/llm/operator_evolution/regime_labeler.py`

### 1.1 分层约束

- 只 import stdlib。**禁止** import `..core`、`..experiments`、`..heuristics`
  （它是纯 dict → dict 的函数，输入就是 e14 的 report JSON）。
- 无副作用、无 I/O、无随机、无 LLM。

### 1.2 公开常量

```python
REGIME_THRESHOLDS = {
    "mode_sensitive_gap_ratio": 0.01,      # |mode_gap| >= 1% makespan 才算大
    "mode_sensitive_position_share": 0.25, # informative 中这类位置的占比阈值
    "balance_dominated_load_excess_ratio": 0.15,
    "turn_heavy_turning_share": 0.06,
    "transfer_dominated_transfer_share": 0.75,
}
```

四项阈值**已冻结**（`p2_feedback_design.md` §7 拍板），不得在实现里调参。

### 1.3 函数

```python
def label_regime(report: dict) -> dict:
    """Return {"regime": str, "evidence": {...}} for one e14 report."""
```

判定顺序（**首个命中即返回**，保证互斥）：

| 序 | regime | 条件 | evidence 必含 |
| --- | --- | --- | --- |
| 1 | `mode_sensitive` | informative 位置中 `|mode_gap| >= 0.01*makespan` 的占比 `>= 0.25` | `share`, `threshold`, `large_gap_position_count`, `informative_count` |
| 2 | `balance_dominated` | `route_load_excess / makespan >= 0.15` | `load_excess`, `makespan`, `ratio` |
| 3 | `turn_heavy` | `mean(turning / cost_split.total) >= 0.06` | `mean_turning_share` |
| 4 | `transfer_dominated` | `mean(transfer / cost_split.total) >= 0.75` | `mean_transfer_share` |
| 5 | `mixed` | 以上皆不中 | 四个候选的实测值全部给出 |

补充函数（供 §2 复用，避免重复遍历）：

```python
def informative_positions(report: dict) -> list[dict]
def route_cost_shares(report: dict) -> dict   # {"mean_transfer_share":..., "mean_turning_share":..., "mean_coverage_share":...}
```

### 1.4 缺失证据的处理（关键）

- report 缺 `state_degeneracy` 或 `routes[].regret_table`（即 `include_regret=False`）→
  规则 1 **不可判定**：跳过它，并在 `evidence["mode_sensitive"] = {"availability": "unavailable"}`，
  不得把 share 当 0 参与判定。
- `routes` 为空、`makespan == 0` → 直接返回 `regime="unknown"`、`evidence["availability"]="unavailable"`。
- 任何除法前必须挡 0；`mean(...)` 空序列返回 `None`，不得返回 0。

### 1.5 验收自检（写进 docstring）

21 份真实 report 上 `label_regime` 与实例名前缀的一致性率应为 100%
（`E10_HV-GEOM` → `mode_sensitive`；其余 6 族 → 非 `mode_sensitive`）。
这**只是 sanity**，不是研究结论（A4）。

---

## §2 修改文件 1：`src/mrta_rect_coverage/llm/operator_evolution/feedback_builder.py`

现有 4 个函数（`build_pair_feedback` / `coverage_mode_knowledge` /
`select_decision_knowledge` / `build_feedback_payload`）**一行都不改**。
在文件末尾追加以下内容（`_failure_type_breakdown` 之后）。

### 2.1 E5 禁用字段黑名单

```python
FORBIDDEN_FIELDS = (
    "state_switch_fraction", "hv_mode_switch_fraction",
    "entry_corner_switch_fraction", "exit_corner_switch_fraction",
    "dp_cascade_count", "dp_cascade_ratio", "state_edit_distance",
    "mean_regret", "avg_regret",
)

def assert_no_forbidden_fields(payload) -> None:
    """Raise ValueError if any E5 field name appears anywhere in payload."""
```

递归遍历所有 dict/list，命中键名（大小写不敏感、子串匹配）即 `raise ValueError`。
**注意**：现有 `build_pair_feedback` 输出里合法包含这些字段（E7 语义），
所以本断言**只用于 §2.2/§2.3 的新 payload**，不得套到旧函数输出上。

### 2.2 `summarize_degeneracy(report) -> dict`

```python
def summarize_degeneracy(report: dict) -> dict:
```

输出（全部来自 `report["state_degeneracy"]`，不重算）：

```python
{
  "position_count": int,
  "tied_position_count": int,
  "all_equal_position_count": int,
  "informative_position_count": int,
  "tied_position_fraction": float | None,
  "all_equal_position_fraction": float | None,
  "informative_position_fraction": float | None,
  "mode_gap_abs_median": float | None,
  "mode_gap_abs_max": float | None,
  "mode_preference_counts": {"H":int,"V":int,"equivalent":int,"unknown":int},
  "limitation_line": str,   # §4 规则 9 的固定句，若 fraction 为 None 则 unavailable
  "source": "<report 路径占位>#/state_degeneracy",
  "availability": "ok" | "unavailable",
}
```

`limitation_line` 固定模板（英文原样，逐字）：

```
state evidence is degenerate at {tied_fraction:.1%} of positions in this parent set;
only {informative_fraction:.1%} carry a decision signal
```

`state_degeneracy` 为 `None` → 所有计数为 `None`、`availability="unavailable"`，
**不得填 0**。

### 2.3 `build_state_regret_feedback(report, *, budget_bytes=2500) -> dict`

```python
def build_state_regret_feedback(report: dict, *, budget_bytes: int = 2500) -> dict:
```

输出结构（字段名即白名单，**不得新增状态类字段**）：

```python
{
  "feedback_mode": "F2_state_v2",
  "byte_size": int,          # len(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode())
  "budget_bytes": int,
  "regime": {"regime": str, "evidence": dict},          # §1
  "cost_structure": {         # E1
     "makespan": float,
     "per_robot_costs": [float],
     "load_excess": float,
     "load_excess_ratio": float,
     "bottleneck_routes": [int],
     "near_bottleneck_routes": [int],   # cost >= 0.95 * makespan
     "transfer_share": float,
     "coverage_share": float,
     "turning_share": float,
     "source": "<report>#/objective"
  },
  "degeneracy": dict,         # §2.2 原样
  "position_notes": [         # E4，限流 ≤5 条
     {"task_id": int, "position": int, "route_id": int,
      "chosen_state_id": int, "mode_preference": str,
      "mode_gap": float, "tied_state_count": 1,
      "gap_ratio_of_makespan": float,
      "source": "<report>#/routes/<r>/regret_table/<p>"}
  ],
  "contrast": dict | {"availability": "unavailable", "reason": str},   # E2，可选
  "limitations": [str, ...],
  "unavailable_evidence": [str, ...],
}
```

硬性规则：

1. **E4 只收 `informative is True and tied_state_count == 1`** 的位置（A2）。
   并列位置只能以 `degeneracy.tied_position_fraction` 出现（规则 7）。
2. E4 排序：按 `gap_ratio_of_makespan` 降序，再按 `(route_id, position)` 升序；
   取前 5 条。**排序键必须是确定性的**，不得用 dict 迭代顺序（A5）。
3. E4 每条必须带 `gap_ratio_of_makespan`（规则 8 量级披露）。
4. 超预算时的降级顺序（必须实现，且只在超预算时触发）：
   `position_notes` 逐条截断 → `degeneracy.mode_preference_counts` 省略 →
   `regime.evidence` 只留命中的那条。**`cost_structure`、`limitations`、
   `degeneracy.limitation_line` 永不截断**；截断后重算 `byte_size` 必须 ≤ 预算。
5. `limitations` 固定三条 + `summarize_degeneracy` 的 `limitation_line`。
6. 全函数**零 LLM 调用**（A6）、对同一 report 两次输出字节完全相同（A5）。

### 2.4 `build_paired_contrast(parent_report, child_report, *, budget_bytes=4000) -> dict`

```python
def build_paired_contrast(parent_report: dict, child_report: dict,
                          *, budget_bytes: int = 4000) -> dict:
```

配对身份：`(input_id, fixed_destroy_hash)` 必须相同，`solver_seed` 必须相同，
否则 `raise ValueError`（同输入同 seed 才是可比的）。

输出：

```python
{
  "feedback_mode": "F2_contrastive_v2",
  "byte_size": int, "budget_bytes": int,
  "input_id": str, "fixed_destroy_hash": str, "solver_seed": int | None,
  "delta_makespan": float,
  "delta_makespan_ratio": float,        # / parent_makespan
  "delta_mean_transfer": float,
  "delta_mean_processing": float,
  "delta_load_excess": float,
  "verdict": "improved" | "degraded" | "tie",     # 按 makespan + 1e-9 容差
  "observations": [str, ...],           # 归因降级为观察标签，≤4 条
  "parent_regime": str, "child_regime": str,
  "bottleneck_shift": {"parent": [int], "child": [int]},
  "limitations": [str, ...]
}
```

`observations` 的标签只允许四类：`transfer_down` / `balance_improved` /
`processing_down` / `mixed`，且必须由实测 Δ 触发（例如
`delta_mean_transfer < -1e-9` 才可写 `transfer_down`）。
**禁止**「caused by / due to / because of」类措辞（写进断言）。

单案例序列化后 ≤ 800 B，超了先删 `observations`。

### 2.5 一个 review 提醒

`build_paired_contrast` 只接受**两份已生成的 report**。它**不**调用
`prepare_paired_repair_cases` / `evaluate_paired_repair_candidates`——
那一步在 `docs/p2_feedback_design.md` §5 里是「配对评价」的复用项，
发生在**产出子代 solution 之前**；本函数只消费其结果生成的 report。
两条链路不要混在同一个函数里。

---

## §3 修改文件 2：`src/mrta_rect_coverage/llm/operator_evolution/prompt_builder.py`

### 3.1 签名（只加可选参数）

```python
def build_revision_prompt(
    *, operator_type: str, round_id: int,
    previous_summary: Dict[str, object],
    top_operators: List[Dict[str, object]],
    weak_operators: List[Dict[str, object]],
    n: int = 3,
    evidence: Dict[str, object] | None = None,     # 新增
) -> str:
```

### 3.2 实现策略（不改 rich 模板）

1. `base = _rich_rev(...)` 或 `_compact_revision_prompt(...)`，**保持现有分支不动**。
2. `evidence is None` → 直接 `return base`（**既有调用方零行为变化**，这是回归底线）。
3. 否则 `return base + "\n" + _render_evidence_sections(evidence)`。

```python
def _render_evidence_sections(evidence: Dict[str, object]) -> str:
    """Render STRUCTURE / CONTRAST / LIMITS blocks. Deterministic, no reordering."""
```

固定三段、固定顺序、固定标题行：

```
[STRUCTURE]
regime: <regime> (<one-line why, e.g. "72% of informative positions have |mode_gap| >= 1% makespan")>
cost: makespan=<x> transfer=<pct> coverage=<pct> turning=<pct> load_excess=<x> (<pct>)
bottleneck_routes: [..] near_bottleneck: [..]
position_notes (only informative, non-tied):
  - task 17 pos 3 mode H gap 24.0 (0.44% of makespan)
[CONTRAST]
input <input_id>: makespan -8.0 (-1.2%) transfer -12.0 processing +1.0 load_excess -14.0 verdict improved
observations: balance_improved
[LIMITS]
<limitation_line>
- <each limitations entry>
```

规则：

- 任一段证据 `unavailable` → 该段保留标题，正文写 `unavailable: <reason>`，
  **不得留空、不得填 0**（A7）。
- 数字格式固定（`:.1f` / `:.2%`），避免浮点尾数造成字节不稳定。
- 全函数不得访问网络、不得调用 provider；`_render_evidence_sections` 是纯函数。

### 3.3 禁止做

- 不要动 `llm/prompts/operator_revision.py`（rich 模板在 P2 不扩参数）。
- 不要把 `evidence` 塞进 `previous_summary` 再走旧路径（会污染 `F1_scalar` 基线）。

---

## §4 修改文件 3：`src/mrta_rect_coverage/experiments/e14_state_regret_instrument.py`

新增 stage `solutions`——这是 P2 唯一的新运行器能力。

### 4.1 输入契约（先核对真实文件再实现）

`--solutions <path>`：JSON，**列表**，每条：

```python
{
  "label": str,                 # 算子名，如 "R_dp_aware_v2"
  "instance_id": str,           # 如 "E10_HV-GEOM_r0"
  "routes": [[int, ...], ...],  # 长度必须 == instance.robot_count
  "input_id": str | None,       # 有则是配对案例
  "fixed_destroy_hash": str | None,
  "solver_seed": int | None,
}
```

`--instance-root`：默认 `STRUCTURAL_DATA`。通过 `outputs/e10b_structural_dp_analysis/inputs/*.json`
的 `instance_id → entry.file_path` 映射解析实例文件（**不要**猜文件名规则）；
映射缺失时 `raise SystemExit` 并列出缺失的 `instance_id`。

> 实现前先打开一个真实 ALNS/演化结果 JSON 确认字段名；若字段不同，
> **只改适配器**（一个 `_record_to_solution(record)` 函数），不改 report 结构。

### 4.2 函数

```python
def stage_solutions(output: Path, *, solutions_path: Path,
                    instance_root: Path = STRUCTURAL_DATA,
                    near_tie_tol: float = 0.0) -> None:
```

逐条执行（与 `stage_parents` 完全同构的 DP 记账断言）：

1. `instance = load_instance(instance_path)`；`instance.name = record["instance_id"]`。
2. `evaluator_for(instance)`；`solution = MultiRobotSolution(routes=...)`。
3. `before = route_dp.statistics()` → `evaluate` → `after_evaluation` →
   `solution_state_report(...)` → `after_report`。
4. 断言：`before["calls"] < after_evaluation["calls"]`、
   `after_evaluation["calls"] == after_report["calls"]`、
   `after_evaluation["cache_misses"] == after_report["cache_misses"]`。
5. `assert_report_consistent(report)`。
6. `report.update({"input_id", "fixed_destroy_hash", "solver_seed", "label", "solution_routes"})`。
7. 写 `output / "solutions" / f"{instance_id}__{label}.json"`（文件名必须含 label，
   否则同实例多算子会互相覆盖）。

`stage_verify` 扩展：把 `solutions/*.json` 一并纳入扫描（一行 `report_paths +=`），
其余不变。

CLI：`--solutions`（`type=Path`，默认 `None`，仅 `solutions` stage 必需）、
`--instance-root`（默认 `STRUCTURAL_DATA`）。

---

## §5 新增测试

### 5.1 `tests/test_regime_labeler.py`（8 例）

| 编号 | 内容 |
| --- | --- |
| REG-1 | 构造 HV-GEOM 式 report（informative 中 8/10 的 gap ≥ 1%）→ `mode_sensitive` |
| REG-2 | `load_excess/makespan = 0.20` → `balance_dominated` |
| REG-3 | `mean_turning_share = 0.08` → `turn_heavy` |
| REG-4 | `mean_transfer_share = 0.80` → `transfer_dominated` |
| REG-5 | 都不满足 → `mixed`；evidence 含四个实测值 |
| REG-6 | 规则互斥：同时满足 1 和 2 时返回 `mode_sensitive`（顺序优先） |
| REG-7 | 缺 `regret_table` → 跳过规则 1，`evidence["mode_sensitive"]["availability"] == "unavailable"` |
| REG-8 | 真实快照：对 `outputs/e14_state_regret_instrument/parents/*.json` 逐份跑，断言 7 族一致性 100%（文件缺失则 `pytest.skip`） |

### 5.2 `tests/test_state_feedback.py`（12 例）

| 编号 | 内容 |
| --- | --- |
| FB-1 | `assert_no_forbidden_fields`：注入 `hv_mode_switch_fraction` → `ValueError` |
| FB-2 | `build_state_regret_feedback` 输出的 E5 字段全无（A1） |
| FB-3 | 所有 `position_notes` 满足 `informative is True and tied_state_count == 1`（A2） |
| FB-4 | 每条 note 含 `gap_ratio_of_makespan`（规则 8） |
| FB-5 | `byte_size <= budget_bytes`，且 `byte_size` 与重算一致（A3） |
| FB-6 | 紧凑预算（`budget_bytes=600`）触发降级：`position_notes` 变短但 `cost_structure`/`limitations` 仍在 |
| FB-7 | 确定性：同一 report 两次构造 → 字节完全相同（A5） |
| FB-8 | 缺 `state_degeneracy` → `degeneracy.availability == "unavailable"`，无 0 值（A7） |
| FB-9 | `build_paired_contrast` 配对身份不一致（不同 `fixed_destroy_hash`）→ `ValueError` |
| FB-10 | `verdict` 按容差：Δ=+1e-12 → `tie`；Δ=-1.0 → `degraded` |
| FB-11 | `observations` 只由实测触发：`delta_mean_transfer > 0` 时不得出现 `transfer_down` |
| FB-12 | 单案例 ≤ 800 B；`build_paired_contrast` 全文含 `"caused by"`/`"due to"`/`"because"` 即失败 |

### 5.3 `tests/test_e14_state_regret_instrument.py` 追加 3 例

| 编号 | 内容 |
| --- | --- |
| E14-S1 | `stage_solutions` 用 2 条合成的 `routes`（round-robin + 逆序）产 2 个报告，`assert_report_consistent` 通过 |
| E14-S2 | `stage_solutions` 前后 `calls`/`cache_misses` 记账断言生效（篡改统计即抛错） |
| E14-S3 | 同实例不同 `label` 不覆盖（文件名含 label）；`verify` 能扫到 `solutions/` |

### 5.4 prompt 注入测试（放进 `test_state_feedback.py` 或新文件）

| 编号 | 内容 |
| --- | --- |
| PB-1 | `evidence=None` 时输出与旧实现**字节完全相同**（回归底线，用 `use_rich_prompts=False` 与 `True` 各测一次） |
| PB-2 | 带 evidence 时含 `[STRUCTURE]`/`[CONTRAST]`/`[LIMITS]` 三段且顺序固定 |
| PB-3 | 某段 unavailable → 该段标题仍在 + 正文 `unavailable:` |
| PB-4 | 构造过程零 provider 调用（mock provider 计数为 0，A6） |

---

## §6 执行命令

```powershell
Set-Location 'D:\VScode\20251217-yang\R_MRTA_01-copy\mrta_rect_coverage'
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'

# 单文件
G:\Anaconda\envs\mrta_env\python.exe -m pytest tests/test_regime_labeler.py tests/test_state_feedback.py -q

# 全量（必须全绿；当前基线 281 passed）
G:\Anaconda\envs\mrta_env\python.exe -m pytest -q

# 真实 report 上跑一次（只读，不改输出）
G:\Anaconda\envs\mrta_env\python.exe -m mrta_rect_coverage.experiments.e14_state_regret_instrument --stage solutions --solutions <你的结果.json>
```

---

## §7 DoD

1. `pytest -q` 全绿，且总数 = 281 + 新增（约 25）− 0。
2. `git status --porcelain` 只出现预期的 3 新 + 3 改 + 3 测试文件；
   **`heuristics/alns_solver.py`、`core/*` 不得出现 `M`**。
3. `evidence=None` 路径与改动前字节完全相同（PB-1 通过）。
4. 21 份真实 report 的 regime 一致性 100%（REG-8）。
5. `git diff` 中 `feedback_builder.py` 的既有 4 个函数**零改动**。

## §8 回滚

```powershell
& 'C:\Program Files\Git\cmd\git.exe' checkout -- `
  src/mrta_rect_coverage/llm/operator_evolution/feedback_builder.py `
  src/mrta_rect_coverage/llm/operator_evolution/prompt_builder.py `
  src/mrta_rect_coverage/experiments/e14_state_regret_instrument.py `
  tests/test_e14_state_regret_instrument.py
Remove-Item src/mrta_rect_coverage/llm/operator_evolution/regime_labeler.py, `
  tests/test_regime_labeler.py, tests/test_state_feedback.py
```

## §9 不做的事

- 不新增任何 DP 计算、不改 report 结构、不改 `state_chain_report.py`。
- 不把 `F1_scalar` 基线改掉（它是对照组）。
- 不让 LLM 决定可行性或 makespan；regime 与 payload 全部确定性生成。
- 不在本阶段接入真实 LLM provider（P2 只做反馈构造与注入）。
- 不实现 `F2_probe`（探针档位仍后置）。
