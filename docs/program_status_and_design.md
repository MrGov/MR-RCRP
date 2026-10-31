# 项目现状总览：代码修改、算法设计思想、已验证内容

编写日期：2026-10-31　仓库：`mrta_rect_coverage`（HEAD `9020311` + 未提交工作树）　编制：本轮编码会话

> 本文档说明**本轮会话对代码做了什么、为什么这么做、哪些已经被实验证实或否证**。所有实验数字都标注了口径（预算、算子池、执行器、代码状态），不同口径的数字不可混排。分项实验的完整表格在 `docs/e16_*.md`…`docs/e25_*.md`，本文只做汇总与交叉引用。

---

## 0. 一页总结

| 项 | 状态 |
| --- | --- |
| 算法骨架 | 精确 8 状态 Route-DP 内层 + ALNS 外层 + LLM 离线生成/冻结算子（不变） |
| 本轮新增的三个精确内层组件 | `core/incremental_route.py`（O(1) 增量定价）、`heuristics/priced_local_search.py`（精确计价局部搜索）、`heuristics/decision_audit.py`（决策级最优性审计） |
| 真正改善性能的改动 | ① 常驻算子执行器（单次调用 225 ms → 8.5 ms）② 精确增量计价（repair 6.9–23.4×）③ 精确计价局部搜索（local_search 33.4 → 4.6 ms/迭代，同预算迭代 2.52×） |
| 按预注册规则被否证的机制 | 迭代成本折价奖励（E16）、花费感知算子选择（E22 两变体）、精确转移增益破坏算子（E23）、决策质量信用（E25） |
| 唯一正向的机制实验 | E24 精确计价局部搜索：配对中位 **+0.154%**，95% CI **[+0.16%, +1.80%]**，T40 子集 8 胜 2 负 |
| 与基线对比的当前水平 | 8 配对开发集上 Proposed 均值 **3223.731**，B1 3286.540（+1.63%）、CDABC 3254.271（+1.07%）、RNSGA 3241.839（+0.49%）；但 W5-T0-L3，领先主要由 2 个 BOTTLENECK 配对贡献，**统计上尚未确立** |
| 核心科学结论 | 瓶颈不在迭代次数、不在算子选择规则、不在邻域强度，而在**每次迭代能挤出多少不同的信息** |
| 测试状态 | 全量 `pytest` **412 passed / 0 failed**（约 53 s） |

---

## 1. 问题与既有方法链（不变量，本轮未改）

*n 个互不重叠矩形任务区、R 台同构机器人、depot=(0,0)，每矩形恰好覆盖一次，最小化 makespan。*

* 单任务 **8 状态** = 4 个进入角 × 2 种扫掠模式（H/V）；出口角由（进入角、模式、扫掠次数奇偶）唯一确定，不可独立指定。
* `processing_time = n_sweeps·traversal_length/sweep_speed + (n_sweeps−1)·turning_time`；`travel_time = manhattan/travel_speed`。
* 内层：给定访问序列，分层 DP 精确求解状态分配（每层 ≤8 状态，O(64)/任务）。
* 外层：ALNS，destroy/repair 为算子，SA 接受 + 分段自适应权重。
* LLM：离线生成/修订算子源码 → 静态校验 → 有界子进程执行 → 固定父解配对评价 → 冻结进池；部署后求解零 LLM 调用。

本轮所有工作都在**不改变这个骨架**的前提下进行。

---

## 2. 代码修改清单

### 2.1 新增源码（13 个）

| 文件 | 作用 | 关键接口 |
| --- | --- | --- |
| `src/mrta_rect_coverage/core/incremental_route.py` | 单路线前向/后向 DP 表（`RouteTables`），把「插入/移除/替换一个任务的最优代价」从 O(len·64) 降到 O(64)/O(192)，并带表缓存与价格缓存。**时序坑**：`backward[k]` 的定义是「任务 k 完成后」的代价，**不含** `P_k`，任何用到后向表的地方都必须单独加后继任务的处理时间 | `RouteIncrementalEvaluator(cost_matrix, states_by_task, *, cache_limit)`；`tables` / `route_cost` / `insertion_costs`（返回插入后总代价）/ `best_insertion` / `insertion_cost_at` / `removal_at` / `replacement_at` / `route_cost_without` / `route_cost_replaced` / `route_costs` / `statistics` / `clear_cache` |
| `src/mrta_rect_coverage/heuristics/priced_local_search.py` | 精确计价局部搜索：五个邻域族全部用定价代替整解重算，并加**精确支配剪枝**（不触碰当前 makespan 的 argmax 路线则不可能改进） | `run_priced_local_search(initial_solution, evaluator, pricer, max_iterations=1, initial_evaluation=None)`；内部 `_RouteCostView`、`_scan_relocates/_scan_intra_route_swaps/_scan_intra_route_two_opt/_scan_inter_route_swaps` |
| `src/mrta_rect_coverage/heuristics/decision_audit.py` | 决策级最优性审计：对每次 destroy/repair 复算「该时刻的精确最优决策」，输出 precision / capture / makespan 命中率 / 后悔 / 被支配落点比例 | `audit_destroy`、`audit_repair`、`DestroyDecision`、`RepairDecision`、`RepairDecisionAudit`、`DecisionAuditRecorder` |
| `src/mrta_rect_coverage/llm/operator_evolution/regime_labeler.py` | 从 e14 报告里打 regime 标签（`mode_sensitive` / `balance_dominated` / `turn_heavy` / `transfer_dominated` / `mixed` / `unknown`），纯 dict→dict、无副作用 | `label_regime`、`large_gap_share`、`route_cost_shares`、`informative_positions`、`REGIME_THRESHOLDS` |
| `experiments/e16_cost_penalty_ablation.py` | 迭代成本折价奖励的固定墙钟 A/B（已关闭） | `stage_run` / `stage_analyze` |
| `experiments/e17_evidence_arms.py` | LLM 算子生成的 F1（标量证据）vs F2（DP 证据）两臂对照 | `stage_run` / `stage_analyze` |
| `experiments/e18_freeze_dp_evidence.py` | 把 E17 胜出算子冻结成可部署包（哈希校验、与 E11 冻结格式对齐、AUX 槽位） | `stage_freeze` / `stage_verify` |
| `experiments/e19_deployment_freezes.py` | 两套冻结（E11 旧 / E18 新）的部署重放对比，读 E12 基线记录不重跑基线 | `stage_run` / `stage_analyze` |
| `experiments/e20_headroom_probe.py` | 杠杆探测：对历史最优解做精确 relocate/swap 下降，测「后处理还有多少空间」 | `descend` / `stage_probe` |
| `experiments/e22_cost_aware_selection.py` | 花费感知算子选择 A/B（两变体，均已关闭） | `stage_run(mode)` / `stage_analyze` |
| `experiments/e23_transfer_gain_ablation.py` | 「精确转移增益破坏算子」A/B（已关闭） | `stage_run` / `stage_analyze` |
| `experiments/e24_priced_local_search_ablation.py` | 精确计价局部搜索 A/B（唯一正向） | `stage_run` / `stage_analyze` |
| `experiments/e25_decision_audit_ablation.py` | 决策审计 `describe`（算子画像）+ `run`（H-Q 按决策给信用）+ `analyze` | `stage_describe` / `stage_run` / `stage_analyze` |

### 2.2 修改的源码（13 个）

| 文件 | 改动内容 |
| --- | --- |
| `heuristics/alns_solver.py` | 本轮改动最多：① `iteration_cost_penalty` + `iteration_cost_reference_seconds`（P1，默认关）② `cost_aware_selection` / `cost_aware_mode` / `cost_aware_exponent` / `cost_aware_clip` / `cost_aware_min_samples`（M2，默认关）③ `transfer_gain_destroy`（默认关）+ `_transfer_gain_destroy` + `_estimate_insert_position` + 模块级 `_manhattan` ④ `priced_local_search`（**默认 True**）+ `self.insertion_pricer` ⑤ `decision_audit` / `decision_driven_selection`（默认关）+ `_audit_iteration_decision` ⑥ `_best_insertion_for_task` / `_regret_k_insertion` 改用 pricing ⑦ history 增 `measured_stage_seconds`/`cost_penalty_factor`/`score_raw`/`score_effective`/`cost_factors`/`decision_quality`/`destroy_reward`/`repair_reward` ⑧ `ALNSResult` 增 `iteration_cost_reference_seconds`/`operator_time_stats`/`decision_audit` |
| `llm/operator_evolution/candidate_execution.py` | `CandidateProxy.import_timeout_s: float = 3.0`（导入预算与调用预算 `timeout_ms=1000` 分离），`execute()` 透传 |
| `llm/operator_evolution/persistent_candidate_execution.py` | `from_validated` 透传 `import_timeout_s`；两处握手 `poll(1.)` → `poll(self.import_timeout_s)` |
| `llm/operator_evolution/feedback_builder.py` | 新增 `build_state_regret_feedback`（F2_state_v2）、`build_paired_contrast`（F2_contrastive_v2）、`summarize_degeneracy`、`build_dataset_evidence`（F2 数据集级证据，含降级阶梯与字节预算）；`FORBIDDEN_FIELDS` 白名单校验 |
| `llm/operator_evolution/prompt_builder.py` | `build_initial_generation_prompt` / `build_revision_prompt` 增加 `evidence` 参数，渲染固定三段 `[STRUCTURE]/[CONTRAST]/[LIMITS]`；新增 dataset 模式的 `_render_dataset_structure` |
| `llm/operator_evolution/evolution_loop.py` | `benchmark_instance_list`（JSON 清单优先于 glob）、`evidence_report_glob`、`evidence_budget_bytes`；`_build_evidence` 聚合报告 → 证据 dict 并写 `evidence.json` |
| `experiments/e6_pair_selection.py` | `EXECUTORS=("original","warm")`、`_registered_proxy`、`close_extra_executors`、`make_solver(..., executor=, config_overrides=)` |
| `experiments/e8_repair_portfolio.py` | `portfolio_solver(..., executor=, config_overrides=)`；统计字典清理扩到 6 个（新增两个计时字典，否则出现陈旧行） |
| `experiments/e11_structural_benchmark.py` | `make_solver(..., executor=, config_overrides=)` 透传 |
| `experiments/e12_comparison.py` | `git_head()`（含绝对路径回退）、`entries(samples)`、`frozen_revisions(accept_note)`（E11 冻结哈希门 + 注记要求）、`--samples/--seeds/--accept-hash-change/--proposed-executor`、`solve_one(..., executor)` 用 `try/finally` 关闭常驻 worker |
| `experiments/e14_state_regret_instrument.py` | 新增 stages `dataset`（读 v1 manifest）、`alns`（跑 ALNS 后出报告）、`solutions`（对已有解出报告）；`_git_head()` 绝对路径回退；`stage_verify` 扩展扫描范围 |
| `experiments/e15_cost_penalty_calibration.py` | 标定单位从「一次 `evaluate_route` 探针」改为**一次真实 ALNS 迭代**（原因见 §3.4），输出 `calibration_unit="alns_iteration"` |
| `experiments/operator_evolution_runner.py` | 透传新增的三个证据配置项 |

### 2.3 新增配置（3 个）

* `configs/instances_v1_dev_14.json`（7 族 × {R2/T10, R4/T40}，供演化与审计用）
* `configs/instances_v1_dev_42.json`（7 族 × 6 尺度格 × replicate 0，论文表工作集）
* `configs/operator_evolution_dp_evidence.yaml`（真 LLM 演化：`langchain_openai_compatible`，2 轮 × 每类 2 候选，绑定 DP 证据目录）

### 2.4 新增测试（11 个文件，本轮累计新增约 90 个用例）

`tests/test_incremental_route.py`(10)、`test_priced_local_search.py`(22)、`test_decision_audit.py`(12)、`test_cost_aware_selection.py`(11)、`test_transfer_gain_destroy.py`(9)、`test_executor_equivalence.py`(7)、`test_regime_labeler.py`(9)、`test_state_feedback.py`(16)、`test_e17_evidence_arms.py`(6)、`test_e18_freeze_dp_evidence.py`(9)、`test_e20_headroom_probe.py`(9)。

其中四个是**等价性/对拍**测试（最有价值）：

* `test_incremental_route.py`：逐位与整条路线 DP 对拍（容差 1e-9）、断言定价过程**不调用** `RouteDPEvaluator`（`calls == 0`）。
* `test_priced_local_search.py`：与参考实现 `run_stronger_local_search` **决策完全一致**（多实例 × 多初始解 × 多迭代），并断言在 ALNS 里两个开关的 `best_makespan` 与 `(destroy, repair, best)` 轨迹逐行相同。
* `test_executor_equivalence.py`：`original` 与 `warm` 执行器在固定迭代数下**迭代数、makespan、routes、决策轨迹、调用计数全部相同**（证明常驻化是纯执行期优化）。
* `test_decision_audit.py`：审计不改变搜索（同 seed 轨迹逐行相同）。

### 2.5 新增文档（14 份，均在 `mrta_rect_coverage/docs/`）

`program_assessment_and_plan.md`、`operator_economics_and_plan.md`、`algorithm_design_v1_bottleneck_exact.md`、`dataset_unification_plan.md`、`e14_v1_development_instrument_result.md`、`e16_cost_penalty_ablation_result.md`、`e18_e19_deployment_freeze_result.md`、`e20_headroom_probe_result.md`、`implementation_revision_alns_solver.md`、`incremental_exact_pricing_result.md`、`priced_local_search_result.md`、`task_P2_state_feedback.md`、`e25_decision_audit_result.md`、本文。

### 2.6 数据目录整理

`data/` 原为 5 套数据混放。本轮确认了三套来源并做清理：删除 53 个只被历史脚本引用、当前无任何引用的根实例（保留 8 个 legacy smoke 实例）、删除 3 个空占位目录，重写 `data/README.md` 为权威数据地图，并在 `docs/data_directory_audit.md` 追加取证记录。**当前正式口径**：机制验证用 `data/structural_benchmark_v1/development`（84），冻结对比用 `validation`（84），`test`（168）锁死。

---

## 3. 算法设计思想：这一轮到底在优化什么

### 3.1 起点：先测清楚成本花在哪里

同实例、同 10 s 墙钟预算的迭代数与 DP 调用数（`BASE/R2_T10_0` seed 0）：

| 方法 | 迭代数 | Route-DP 调用 | 每迭代 |
| --- | ---: | ---: | ---: |
| B1（手工 ALNS） | 8054 | 235 万 | 1.2 ms |
| CDABC | 4179 | 108 万 | — |
| RNSGA | 321 | 209 万 | — |
| **Proposed** | **63** | 1.67 万 | **162 ms** |

每迭代 DP 调用数与 B1 同量级（265 vs 292）→ **搜索逻辑不是瓶颈，执行开销才是**。162 ms 里 DP 只占 1–2 ms，其余是：`_execute_external` → `execute_candidate_process` 每次调用都 `multiprocessing.get_context("spawn")` 新建进程并重新 import 整个包（约 0.6 s/次）。

这条发现改写了后续所有工作：**先修测量与执行，再谈机制**。

### 3.2 改动一：常驻算子执行器（纯工程，无行为变化）

`PersistentCandidateProxy` 本来已存在但只被 E13 使用，其余实验全部走冷 spawn。本轮把它接进 E6/E8/E11/E12。

* 单次调用：**225.19 ms → 8.52 ms**（本地直接调用 5.71 ms），cold/local = **39.4×**。
* 同 10 s 预算 A/B（warm vs original）：BASE/T10 迭代 68 → 3699（**54×**），makespan 不变；HV-GEOM/T40 与 BOTTLENECK/T40 各两 seed：中位 **+1.68%**（3 胜 1 负 2 平）。
* 等价性：`test_executor_equivalence.py` 7 个用例，固定迭代数下决策轨迹逐行相同 → 这不是"换了启发式"，是**把同样的搜索在同样的墙钟里跑更多步**。

### 3.3 改动二：精确增量计价（把每个候选的精确评价变便宜）

**为什么**：修好执行器后，repair 成了唯一大头。`_greedy_insertion` / `_regret_k_insertion` 对**每个候选插入位**都跑一次完整 `route_dp.evaluate_route`：40 任务、25% 破坏 ≈10 个任务 × 4 条路线 × 11 个位置 ≈ **440 次 DP ≈ 44 ms**（每次迭代只调一次 repair，所以那就是全部成本）。

**怎么做**：为每条路线建前向表 F 与后向表 B，则插入代价 = `min_{s'}[F(p−1,s')] + min_{s_i}[travel(s',s_i) + P_i(s_i) + K(s_i)]`，其中 `K` 由后向表给出，**O(64)/位置，与路线长度无关**；移除与替换同理（O(64)/O(192)）。取值与逐候选跑 DP 完全一致（1e-9 内，有对拍测试）。

| 实例 | 候选数 | 逐候选 DP | 增量表 | 提速 |
| --- | ---: | ---: | ---: | ---: |
| R2_T10_0 | 40 | 0.1 ms | 0.08 ms | 0.9× |
| R4_T40_0 | 340 | 43.8 ms | 6.34 ms | 6.9× |
| R8_T80_0 | 740 | 231.8 ms | 18.22 ms | 12.7× |
| R8_T100_5 | 940 | 947.7 ms | 40.48 ms | **23.4×** |

固定 40 次迭代、12 实例上整迭代中位提速 **1.18×**（T40/T80 上 repair 从 42–76 ms 降到 18 ms，但"每插入一个任务要为每条路线各建一次表"限制了收益上限）。

**重要副作用（必须记住）**：后向表是反序累加，与 DP 正序累加在相对 1e-13 上不等价，而插入位选择的容差是 1e-9 绝对 → 恰好并列的候选位可能被打散。实测 12 个实例里 11 个决策轨迹与旧实现逐行相同，1 个（BOTTLENECK/R4_T40_0）在第 27 次迭代分叉。**结论：同一实现内确定性成立；跨实现不保证逐位复现，历史 B1 数字不能与新实现逐位对比。**

### 3.4 一次被自己否证的设计：迭代成本折价奖励（E16，已关闭）

原设想：奖励按迭代耗时折价 `r·min(1, sqrt(t_ref/t))`，让 AOS 偏爱"便宜"的算子。

* 标定单位先搞错了：用「一次 `evaluate_route`」做 `t_ref` 与真实迭代差 800 倍（6 任务实例 50 个 probe 单位/迭代，40 任务是 800 个）。改用「一次真实 ALNS 迭代」重新标定（`calibration_unit="alns_iteration"`，`t_iteration_median = 4.9774e-02 s`，`kappa=1.0`）。
* 结果：操纵检验成立（45.1% 的迭代被折价），但性能 **中位 +0.00248、95% CI [−0.00844, +0.00865] 跨 0 → TURN_OFF**。
* 复盘的教训：在分段权重框架里，折价只是把奖励乘一个与算子相关的常数——当算子间成本同质时它是空操作，差异大时它变成常数缩放，**同样不改变排序**。所以 E16 的失败不是参数问题，是机制形态问题。

### 3.5 被否证的"花钱感知选择"（E22，已关闭）

把折价从奖励搬到选择概率（按历史成本做概率折扣）与段权重的时间归一（throughput）：

| 变体 | 块 | 配对中位 Δ | 95% CI | 判定 |
| --- | --- | ---: | --- | --- |
| probability | AUX 异质池 | −1.50% | [−2.69%, +0.15%] | INCONCLUSIVE |
| probability | B1 同质池 | −1.43% | [−7.21%, +4.12%] | INCONCLUSIVE |
| throughput | AUX | −0.77% | [−1.81%, −0.04%] | **TURN_OFF_HURT** |
| throughput | B1 | +0.26% | [−1.35%, +2.41%] | TURN_OFF |

同质池对照同样偏负 → 该机制引入的墙钟抖动本身就污染搜索。加上 E16，**"成本/时间感知"这条线没有一条能兑现**（这也解释了为什么 `operator_economics_and_plan.md` §5 的 M1/M3 决定不投）。

### 3.6 被否证的"瓶颈定向破坏"（E23，已关闭）

设计：按"从瓶颈路线摘掉它能省多少、插到别处要花多少"的精确差值选任务（`transfer_gain_destroy`）。

* 结果：中位 **+0.48%**、CI [−1.23%, +0.85%]、**8 胜 4 负** → TURN_OFF。方向对但量级不足。
* 两个大亏：BOTTLENECK/T40 s0 −4.18%、SPATIAL/T40 s0 −3.39%；赢的最大 HV-GEOM s1 +1.92%。

### 3.7 杠杆探测（E20）：后处理没有空间

对 E12（48 条）与 E19（16 条）的历史最优解施加**精确**的 relocate + swap 下降（每个候选由完整 Route-DP 计价）：

* **中位下降 0.00%**，62.5%（40/64）记录零改进；预注册 H-A（≥0.5%）**被否证**。
* 仅有的两处真实改进全部来自**交换**（BOTTLENECK/T40 +2.16%、TRAVEL-HIGH/T80 +1.06%），搬运被 ALNS 的 destroy+repair+local_search 完全覆盖。
* 更不利的副产品：把同一把精确下降公平施加给所有方法后，我们在这支 4×2 开发集上**排第三/四**（RNSGA 0.315% < CDABC 0.533% < Proposed 1.179%），且打磨后名次不改善 → **差距在搜索结构，不在打磨**。
* 我要收回的一个推理错误：此前把"别人的 1.3% 到最优解的差距"当成"我们自己的机会"，这是错的。

### 3.8 唯一正向的机制改动：精确计价局部搜索（E24，已默认开启）

诊断发现：在部署池下 local_search 占每迭代 **66.8%（T20）/ 65.7%（T40）/ 82.2%（T80）**，因为参考实现每个候选都做一次整解评价，而 T80 一次失败的全邻域扫描是 ≈9400 个候选 × 0.2 ms ≈ **1.9 s**，且绝大多数迭代都在付这笔钱（改进很稀疏）。

做成三件事：① 五个邻域族全部用定价（relocate 用 `removal_at` + `insertion_costs`，inter-swap 用两次 `replacement_at`，intra 用 `route_cost`）；② **精确支配剪枝**——不触碰当前 makespan argmax 路线的候选可证明不可能改进，直接跳过；③ 与参考实现**逐决策等价**（22 个测试，含 ALNS 内的轨迹逐行相同）。

| 结果 | 数值 |
| --- | --- |
| local_search 每迭代中位 | **33.448 ms → 4.624 ms** |
| 同预算迭代数 | **2.52×** |
| 配对 Δ 中位 / 均值 | **+0.1543% / +0.8049%**，95% CI **[+0.1625%, +1.8008%]** |
| W/T/L | **9/4/3** |
| 按规模 | T40 **+0.6945%（10 对，8 胜 2 负）**；T20 −0.1729%；T10/T80 持平 |
| 判定 | **KEEP_WEAK**（预注册规则） |
| 尾部病态证据 | 关闭臂 `TRAVEL-HIGH/R8_T80_0 s1` 用 1911 s 只跑完 101 次迭代（**18924 ms/迭代**） |

一个必须写进论文的教训：**纯惰性化（materialize 全部 slot）反而更慢**。`cProfile` 显示参考实现只有 322 次 route_dp 调用，而我的路径 4115 次 `_insertion_at`、64 万次 `transition` —— 参考实现靠 `RouteDPEvaluator` 的 **89% 缓存命中率**。所以必须在 pricer 里加价格记忆缓存（`DEFAULT_PRICE_CACHE_LIMIT = 50000`），否则把一个"便宜操作重复做 1000 次"比一个"昂贵操作做 1 次"更慢。

### 3.9 决策级审计（E25）：仪器成立，作为信用不成立

**动机**：既然精确量已经便宜，就可以不只测"结果好不好"（8/3/1 只看到是否刷新最好解，被 SA 接受、destroy/repair 耦合、seed 三重过滤后近似噪声），而是测"决策本身对不对"。

**两个关键设计决定**（都是先测再定）：

1. **双目标基线**：makespan 是 `max_r cost_r`，而"和代价"是另一个目标。只按最便宜路线插入，在"便宜路线恰是瓶颈"时恰恰是错的。所以每个决策同时对照 `argmin_r cost(r)+price(t,r)` 与 `argmin_r max(cost(r)+price(t,r), max_{r'≠r}cost(r))`。
2. **repair 质量取 makespan 命中率，不取 1−归一化后悔**：实测后悔只占 makespan 的 0.35–0.99%，用 1−ratio 会饱和在 0.99、算子间差 0.005，等于没有信号。

`describe`（14,480 次被审计迭代）给出的画像——这是本轮**最有价值的诊断产出**：

| destroy | precision | saving capture | random-level 占比 |
| --- | ---: | ---: | ---: |
| `random_destroy` | 0.2443（理论 0.25） | 0.5688 | 0.557 |
| `bottleneck_route_destroy` | **0.2397** | 0.5666 | 0.655 |
| `geometry_aware_destroy` | 0.2744 | 0.5905 | 0.545 |
| `e5_llm_destroy`（LLM 生成） | **0.3225** | **0.7127** | **0.333** |

| repair | makespan 命中 | 被支配落点 | 平均 makespan 后悔 |
| --- | ---: | ---: | ---: |
| `e8_aux_repair`（LLM 生成） | **0.8643** | **3.57%** | **0.35%** |
| `greedy_insertion` | 0.8461 | 6.18% | 0.55% |
| `regret_k_insertion` | 0.8055 | 5.73% | 0.60% |
| `bottleneck_balancing_insertion` | 0.7542 | **9.78%** | 0.99% |

三条结论：① 仪器自校准通过（随机破坏实测 0.2443 ≈ 理论 0.25）；② 两个手工 destroy 在"摘最贵的 k 个"判据下与随机不可区分，只有 LLM 生成的 destroy 明显更强（+29%）；③ LLM 生成的 repair 在命中率、后悔、被支配落点三项都最好——**这与用昂贵候选评价得到的 E17/E18/E19/E24 排序一致**，即审计能用一次确定性计算复现那个结论。

但把它当信用（H-Q，段奖励 = 8 × 决策质量）：

* 中位 **+0.0000%**、CI [−0.5172%, +0.9256%]、W/T/L 5/4/7 → **TURN_OFF**。
* 机制解释：destroy 权重被拉向最贵的 `e5_llm_destroy`（precision 最高但单次 10–20 ms vs 其余 0.01–0.16 ms），repair 四者质量都接近上限导致权重趋同，**迭代数下降**（SPATIAL 1446→655、TURN-HIGH 1033→563，最坏 −61%）。
* 科学结论：**决策质量度量的是"单步最优性"，不是"整条搜索轨迹的价值"**。总做单步最优决策的算子会退化成贪心，而 ALNS 的收益恰恰来自"暂时不最优"的多样性。

**处置**：`decision_driven_selection` 默认关、不进任何实验臂；`decision_audit` 保留（默认关、零决策影响、<1 ms/迭代），作为"不跑对照实验就能判断算子是否在做有意义的事"的仪器。

### 3.10 LLM 侧：证据档位的机制对照（E17 → E18 → E19）

* **E14 仪器**先把"状态层还剩多少可动"量化清楚：v1 development 4,340 个位置里，有信息（最近替代状态严格更差）的 **32.40%**，并列最优 **67.6%**；`|mode_gap| ≥ 1%·makespan` 的只占 **2.90%**；成本构成 transfer **81.8%** / coverage 14.4% / turning 3.8%；负载超出 `B = M − mean` 占 makespan **11.7%**。→ **状态选择是小杠杆（≤3%），大杠杆在顺序与均衡（~12%）**。
* **E17**（真 LLM，6 次演化，14 实例）：给 LLM 的反馈从"标量/scalar+top/weak"（F1）升级为"数据集级精确 DP 证据"（F2，2358 字节 / 2500 预算）后，最优 destroy 的候选评价中位 **+0.0990 → +0.2070**（配对差 +0.0365，3/3 正），最优 repair 中位 **+0.0055 → +0.0275**（2/3 正）。n=3、非 seed 配对，只能作描述性证据；但 F1 曾单次冲到 +0.2256 而中位仅 +0.0990，说明**单次运行会被运气支配，这个对照是必要的**。
* **E18** 把 F2 胜出算子冻结成带哈希的部署包（destroy `destroy_r001_001`，rel +0.2474/succ 1.00；aux repair `repair_r000_000`，rel +0.0283/succ 0.36；main repair 继承 E5），`--stage verify` 零问题。
* **E19** 两套冻结的部署重放（8 配对）：配对差均值 +0.120%、中位 +0.077%，4 好 3 差 1 平；对基线的增益五条全部朝好方向但幅度 < ±0.35%，与 E16 的置信半宽同量级 → **部署层面的收益未证实**（同实例跨 seed 符号相反、幅度 ~3.5%，单 seed 部署对比测的是运气）。

### 3.11 一条贯穿的负面证据链

| 实验 | 机制 | 判定 |
| --- | --- | --- |
| E16 | 迭代成本折价奖励 | TURN_OFF |
| E20 | 精确后处理（relocate+swap 下降） | 中位 0.00%，H-A 否证 |
| E22 | 花费感知选择（2 变体） | INCONCLUSIVE / TURN_OFF_HURT |
| E23 | 精确转移增益破坏算子 | TURN_OFF（+0.48%，8 胜 4 负） |
| E25 | 决策质量信用（H-Q） | TURN_OFF（0.00%） |
| **E24** | **精确计价局部搜索** | **KEEP_WEAK（+0.154%，CI 下界 > 0）** |

唯一正向的 E24，其机理是**改变预算**（同墙钟内迭代翻倍），不是改变启发式。与 E20（连别人的解做精确下降都几乎没有空间）合起来指向同一个结论：**当前瓶颈是"每次迭代能挤出多少不同的信息"，不是迭代次数、不是信用规则、不是邻域强度。**

---

## 4. 已验证内容（按主题，含口径）

**口径声明**：除特别标注外，预算 = 每任务 1 秒墙钟（E12 口径）；算子池 = AUX 部署池（E18 冻结 destroy + E5 main repair + E17 aux repair）；执行器 = warm 常驻；代码状态 = HEAD `9020311` + 未提交工作树。

### 4.1 精确性（对拍类，最硬）

| 断言 | 证据 |
| --- | --- |
| 增量定价的插入/移除/替换价 = 逐候选跑 Route-DP | `test_incremental_route.py` T2 逐位对拍，容差 1e-9 |
| 定价过程不调 RouteDPEvaluator | 同上 T8：`statistics()["calls"] == 0` |
| 计价局部搜索与参考实现决策逐行相同 | `test_priced_local_search.py`（3 实例 × 3 解 × 1/4 迭代 + ALNS 内轨迹） |
| 常驻执行器不改变任何决策 | `test_executor_equivalence.py`（迭代数/makespan/routes/轨迹/调用计数全同） |
| 决策审计不改变搜索 | `test_decision_audit.py::test_audit_does_not_change_the_search` |
| 审计的 makespan 最优路线判定正确 | 暴力枚举 route×position 对拍 |
| 全量回归 | **412 passed / 0 failed**（53 s） |

### 4.2 速度（同迭代数、中位）

| 环节 | 改前 | 改后 | 倍数 |
| --- | ---: | ---: | ---: |
| 单次生成算子调用 | 225.19 ms | 8.52 ms | **39.4×**（含进程边界 + 每调用 re-validate） |
| repair 候选评价（T40 / T80 / T100） | 43.8 / 231.8 / 947.7 ms | 6.34 / 18.22 / 40.48 ms | 6.9× / 12.7× / **23.4×** |
| local_search（部署池，每迭代中位） | 33.448 ms | 4.624 ms | **7.2×** |
| 整迭代（12 实例中位） | — | — | 1.18×（增量计价） + 局部搜索后 1.13–2.04×（B1 池实测） |

### 4.3 同预算效果（预注册判定）

| 实验 | 对比 | 中位 Δ | 95% CI | W/T/L | 判定 |
| --- | --- | ---: | --- | --- | --- |
| E24 | 精确计价局部搜索 on/off | **+0.1543%** | **[+0.1625%, +1.8008%]** | 9/4/3 | **KEEP**（弱） |
| E23 | 转移增益破坏 on/off | +0.48% | [−1.23%, +0.85%] | 8/0/4 | TURN_OFF |
| E25 | 决策信用 on/off | +0.0000% | [−0.52%, +0.93%] | 5/4/7 | TURN_OFF |
| E16 | 迭代成本折价 on/off | +0.248% | [−0.84%, +0.87%] | 10/2/12 | TURN_OFF |
| E22 | 花费感知（prob/through） | −1.50% / −0.77% | 跨 0 / 全负 | — | 否 |

### 4.4 与基线对比（8 配对开发集 = 4 实例 × 2 seeds，当前实现）

| 方法 | 均值 makespan | 相对 Proposed |
| --- | ---: | --- |
| **Proposed（warm + 增量计价）** | **3223.731** | — |
| B1（手工 ALNS） | 3286.540 | +1.625% |
| CDABC | 3254.271 | +1.068% |
| RNSGA | 3241.839 | +0.489% |

配对：vs B1 **W5-T0-L3**、vs CDABC 3-2-3、vs RNSGA 3-1-4。**领先主要由两个 BOTTLENECK/T40 配对（+5.56% / +4.84%）驱动**，T10 上差 1 个单位。

交叉验证：CDABC 均值与 E12 历史记录**完全一致**（该基线不经我们改动代码路径）；RNSGA 与 E12 差 0.7%（自身 RNG + deadline 抖动）→ 本轮与 E12/E19 同口径。

同口径历史对照：E19（冷 spawn）Proposed 均值 3277.32 → 本轮 3223.731 = **−1.63%**；同期 B1 从 3303.588 → 3286.540（−0.52%）。即两个工程改动合计推进 1.6 个点，其中约 1.1 个点是我们独有路径（B1 只吃到计价部分）。

### 4.5 结构性事实（可作为论文的问题分析章节）

| 事实 | 数值 | 来源 |
| --- | --- | --- |
| 成本构成（占 makespan） | transfer **81.8%**、coverage 14.4%、turning 3.8% | E14 v1 dev 84 实例 |
| 负载超出 `B = M − mean` | makespan 的 **11.7%** | 同上 |
| 有信息状态位置 | **32.40%**（并列最优 67.6%） | 同上 |
| `|mode_gap| ≥ 1%·makespan` 的位置 | **2.90%** | 同上 |
| 零后悔位置的集中处 | HV-GEOM 占全部大 gap 位置的 **68%** | 同上 |
| 规模效应 | 大 gap 位置按 n_tasks：T10 47 / T20 15 / T40 19 / T60 5 / T80 22 / T100 18 | 同上 |
| ALNS 对瓶颈无偏置 | destroy 不看瓶颈路线、repair 按总增量选目标、邻域无偏置 | 代码审读 |
| 后处理无空间 | 40/64 记录零改进，其余全来自交换 | E20 |

---

## 5. 当前算法处于什么水平（诚实评估）

**已经站得住的**：

1. 内层是目前这套建模下能做到的**精确最优**（给定序列，状态分配 DP；给定路线，插入/移除/替换价 O(64) 精确）。这一点有对拍测试，不是近似。
2. 执行效率已从"每迭代 162 ms"降到"小实例 0.6–5 ms、T80 45 ms"，与基线在同一量级。
3. LLM 生成的算子确实比手工算子强，而且**有两套独立证据**：候选评价（E17）与决策审计（E25 的 precision / makespan 命中率排序）。

**尚未站住的**：

1. **对基线的优势没有统计显著性**（W5-L3，靠 2 个 BOTTLENECK 配对）。
2. **LLM 环节对最终性能的贡献未确立**：E19 部署对比中位 +0.077%、CI 与噪声同宽。目前能说的是"F2 证据让 LLM 生成更好的候选"，不能说"让最终 makespan 更好"。
3. 迭代数虽然回到了与基线同量级，但**质量没有随之线性提升**（E24：迭代 2.52× 只换来 +0.15%），说明搜索的"边际信息产出"很低。

**因此当前最诚实的定位是**：一个**精确内层 + 廉价执行的 ALNS 框架**，外加一套**能用确定性计算解释算子行为的仪器**。创新点若要在论文里成立，最可能落在"精确 Route-DP 作为在线定价与决策审计的基座"，而不是"又一个 ALNS 变体"，也不是"LLM 生成算子"本身（EoH/ReEvo/ReVEL 已占）。

---

## 6. 未验证与风险清单

| # | 项 | 状态 |
| --- | --- | --- |
| R1 | 对 CDABC / RNSGA 的优势 | 开发集上**未确立**（3-2-3 / 3-1-4），需 validation 集与更多 seed |
| R2 | LLM 环节的端到端贡献 | E19 中位 +0.077%，**未证实** |
| R3 | "成本/时间感知"整条线 | 四次否证（E16/E22×2），**建议放弃** |
| R4 | 决策审计作为 LLM 反馈（H-F） | **未测**（仪器已就绪，是下一步最自然的用法） |
| R5 | 精确支配剪枝的理论表述 | 已实现并测过等价性，但"该邻域类下局部最优"的证明未写成文字 |
| R6 | 跨实现可复现性 | 后向表反序累加 vs DP 正序累加在 1e-13 上不等价 → 历史数字不可逐位对比，需在论文口径里声明 |
| R7 | 文献新颖性 | 本会话 `web_search` 认证失败（HTTP 401），"精确内层定价 + 决策审计"的新颖性标 **UNVERIFIED**，必须自行核查（关键词：incremental DP evaluation for ALNS、exact insertion cost、operator credit assignment with exact subproblem） |
| R8 | test 集 | `structural_benchmark_v1/test`（168）**从未打开**，符合协议 |
| R9 | `generated_operators/round_000/*.py` 被 E17 运行覆写 | 溯源问题，未处理（不影响测试与实验） |

---

## 7. 建议的下一步（按优先级）

1. **把决策审计接到 LLM 反馈上（H-F）**：这是唯一同时具备"新机制"与"已有仪器"的路径——LLM 改算子时不再看"makespan 好/坏"，而看"你这个 destroy 有 66% 的调用处在随机水平，且漏掉了 X 类任务"。E17 的 F2（数据集级 DP 证据）已证明这类证据能提升候选质量，决策审计是它的**更强版本**（算子自己的行为画像）。成本约 25 min/轮（E17 口径）。
2. **修掉两个已被审计证明的缺陷**：`bottleneck_balancing_insertion` 的 9.78% 被支配落点、`bottleneck_route_destroy` 与随机无异。这是"改一个算子 → 立刻可测"的闭环，也是 H-F 的天然试验田。
3. **算法锁定后跑论文表**：42 单元（v1 dev）× 3 seeds × 6 方法 ≈ 21.7 h；正式表应跑 validation 84（≈ 14.5 h/seed）。跑前必须冻结配置并写 `implementation_revisions`。
4. **不要再投入的方向**：成本/时间感知选择（已四次否证）、纯邻域加强（E20）、加演化轮次（会从"一次性设计"滑向 EoH/ReEvo 主场，且当前瓶颈不在轮次）。

---

## 8. 复现命令（本轮新增实验）

```powershell
$env:PYTHONPATH = 'src'
$py = 'G:\Anaconda\envs\mrta_env\python.exe'

# 精确性/回归
& $py -m pytest -q -p no:cacheprovider

# E24 精确计价局部搜索（唯一正向机制）
& $py -m mrta_rect_coverage.experiments.e24_priced_local_search_ablation --stage run
& $py -m mrta_rect_coverage.experiments.e24_priced_local_search_ablation --stage analyze

# E25 决策审计：先看算子画像，再看 H-Q
& $py -m mrta_rect_coverage.experiments.e25_decision_audit_ablation --stage describe
& $py -m mrta_rect_coverage.experiments.e25_decision_audit_ablation --stage run
& $py -m mrta_rect_coverage.experiments.e25_decision_audit_ablation --stage analyze

# E20 杠杆探测（对历史最优解做精确下降）
& $py -m mrta_rect_coverage.experiments.e20_headroom_probe --stage probe

# 排名对比（4 实例 × 2 seeds × 6 方法，warm）
& $py -m mrta_rect_coverage.experiments.e12_comparison --stage run `
    --samples configs/instances_v1_dev_14.json --seeds 0,1 `
    --proposed-executor warm --accept-hash-change docs/implementation_revision_alns_solver.md
```

---

## 附：本轮关闭/保留的开关一览

| 开关 | 默认 | 状态 | 依据 |
| --- | --- | --- | --- |
| `priced_local_search` | **True** | 保留并默认开启 | E24 KEEP_WEAK |
| `decision_audit` | False | 保留（仪器，零决策影响） | E25 describe 有效 |
| `decision_driven_selection` | False | **关闭，不进实验臂** | E25 TURN_OFF |
| `cost_aware_selection` | False | **关闭** | E22 INCONCLUSIVE / TURN_OFF_HURT |
| `transfer_gain_destroy` | False | **关闭** | E23 TURN_OFF |
| `iteration_cost_penalty` | False | **关闭** | E16 TURN_OFF |
