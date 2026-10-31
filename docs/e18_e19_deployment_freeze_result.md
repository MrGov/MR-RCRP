# E18/E19 — 冻结 E17 证据算子并重跑部署对比

日期：2026-10-30 · git head `9020311` · 仅 development 实例，未触碰 validation / test

## 结论先行

1. **冻结包已可复现**：E17 的 F2_dataset 胜出算子被打成独立的哈希冻结包 `outputs/e18_freeze_dp_evidence/`，与 E11/E8 的原产物完全隔离（E12/E11/E13 的历史记录仍逐字节可校验）。
2. **候选空间的机制收益成立**（E17：同模型、同预算下，DP 证据臂的 destroy 中位 +0.2070 vs 标量臂 +0.0990）。
3. **部署收益尚未证实**：8 个配对（4 实例 × 2 seeds）上，新冻结包相对 E11 冻结包的中位改善 **+0.077%**、均值 **+0.120%**，4 更好 / 3 更差 / 1 持平。同一实例跨 seed 的差值在 **−3.83% ~ +3.48%** 之间摆动，量级远大于均值。
4. 因此：**不要把「候选评价上的 +0.04~+0.11」当成部署结论**。部署主张需要 B3 规模的重复与区间，当前证据只够支撑「机制有效 + 冻结可复现」。

## E18 冻结包

| 槽位 | 来源 | operator_id | E17 rel | succ |
| --- | --- | --- | ---: | ---: |
| `destroy` | E17 `F2_dataset` rep1.round1 | `destroy_r001_001` | +0.2474 | 1.00 |
| `main` | 继承 E11（E5 frozen repair） | `repair_r001_001` | — | — |
| `aux`（= 部署 repair） | E17 `F2_dataset` rep0.round0 | `repair_r000_000` | +0.0283 | 0.36 |

- 选择规则：`execution_status == "success"` 内取 `avg_relative_improvement` 最高，同分取较小 repetition。不重评估、不调参、不读 validation/test。
- `main` 故意不动：E11 的 repair 池布局（4 槽）依赖它，换掉会同时改变池结构，混杂变量。
- 三种身份哈希 `digest()` 校验，`--stage verify` 逐项重算（含 E11/E8/E17 输入文件的 sha256 与候选池是否漂移）。
- `recommended_proposed` 保持 `AUX`，`deployed_destroy = operators.destroy`、`deployed_repair = operators.aux` —— 与 E11 的字段语义一致，E12 的校验条件仍然成立。

## E19 部署重放

同 4 个 development 实例、同 seeds (0,1)、同 `task_count` 秒预算、同构造器/池/参数/RNG；两臂按 `(实例序号 + seed)` 奇偶交替执行以摊平机器漂移。文献基线**不重跑**，统一读 `outputs/e12_literature_baselines/runs` 的不可变记录，保证两臂对着同一张基线表。

### 配对差（正 = E18 更好）

| 实例 | seed | Δ |
| --- | ---: | ---: |
| BASE/R2_T10_0 | 0 | +0.077% |
| BASE/R2_T10_0 | 1 | +0.000% |
| HV-GEOM/R2_T20_0 | 0 | +1.105% |
| HV-GEOM/R2_T20_0 | 1 | +1.954% |
| BOTTLENECK/R4_T40_0 | 0 | **+3.478%** |
| BOTTLENECK/R4_T40_0 | 1 | **−3.830%** |
| TRAVEL-HIGH/R8_T80_0 | 0 | −0.273% |
| TRAVEL-HIGH/R8_T80_0 | 1 | −1.551% |

均值 +0.120%，中位 +0.077%。`mean_makespan`：E11 = 3270.95，E18 = 3277.32。

BOTTLENECK 同实例两个 seed 符号相反、幅度 ~3.5% —— 这条比均值重要：**单 seed 的部署对比基本是在测运气**。

### 对文献基线的增益（8 配对均值，括号 W/T/L）

| 基线 | E11 冻结 | E18 冻结 |
| --- | --- | --- |
| B1 | +0.403% (3/0/5) | **+0.556%** (4/1/3) |
| CDABC | −0.478% (1/0/7) | **−0.335%** (1/2/5) |
| RNSGA | −0.718% (3/0/5) | **−0.579%** (3/1/4) |
| SGA-TS | +1.778% (4/2/2) | **+1.901%** (5/1/2) |
| MRHDABC | +0.088% (3/0/5) | **+0.219%** (2/2/4) |

五个基线上方向一致（都朝好的方向挪），但幅度全部在 ±0.35% 内 —— 与 E16 那次 8 s 预算下 ±0.85% 的置信半宽同量级。**方向一致 + 幅度小于噪声 = 还不能下结论。**

CDABC / RNSGA 仍为负增益：这与 E12 的原表一致，说明这不是新算子引入的退步，而是这两条基线在该实例子集上本来就强。论文里必须正面处理（不能只报对 SGA-TS 的 +1.9%）。

## 复现

```powershell
$env:PYTHONPATH='src'
G:\Anaconda\envs\mrta_env\python.exe -m mrta_rect_coverage.experiments.e18_freeze_dp_evidence --stage freeze
G:\Anaconda\envs\mrta_env\python.exe -m mrta_rect_coverage.experiments.e18_freeze_dp_evidence --stage verify
G:\Anaconda\envs\mrta_env\python.exe -m mrta_rect_coverage.experiments.e19_deployment_freezes --stage run
G:\Anaconda\envs\mrta_env\python.exe -m mrta_rect_coverage.experiments.e19_deployment_freezes --stage analyze
```

产物：`outputs/e18_freeze_dp_evidence/`（`algorithm_freeze.json`、`selection_decision.json`、`experiment_config.json`）、`outputs/e19_deployment_freezes/`（`runs/`、`pairs.json`、`summary.json`、`REPORT.md`）。

## 下一步（部署确认性实验的最小设计）

要把「部署收益」变成可主张的东西，样本量必须上来，但不需要 6 方法全跑：

- 臂：**Proposed(E18) vs B1**（B1 是最强的手工基线，也是机制对照的同宿主）。
- 尺度：v1 validation 84 实例或 development 42 单元表；seeds ≥ 3。
- 预算：`task_count` 秒不变。
- 成本估算：development 42 单元（7 场景 × 6 尺度）每臂每 seed Σtask = 7 × 310 = 2170 s ≈ 36 min；2 臂 × 3 seeds ≈ **3.6 h 串行**。
- 判据：配对中位差 + two-way cluster bootstrap 5000 的 95% CI，与 `statistical_analysis_plan.md` 的 MCID 0.02 对齐，事前写死。

在此之前，P2 论文口径应保持为：**候选空间机制对照（E17）+ 冻结可复现（E18）+ 部署效应待确认（E19 仅作 pilot）**。

## 局限

- 单算子对（每个槽位各一个候选），不是算子集合主张。
- 8 配对，无重复级区间，无法区分 +0.12% 与 0。
- 基线读历史记录，未与两臂在同一会话内交替测量；虽然预算口径相同，机器状态差异仍可能进入基线一侧。
- `repair_r000_000` 的 E17 success_rate 只有 0.36（其余候选 0.33–0.36），低成功率候选被选中是按「相对改善最高」规则的结果，需要在更大样本上复查是否会拖累 fallback 率 —— 本次两臂 `fallback=0`。
