# Paper-Grade Experiment Protocol

## 1. 状态、范围与执行禁令

- **状态：** Phase 5B documentation specification；不是 experiment authorization。
- **研究目标：** 用 MR-RCRP + DP-aware ALNS 严格验证多轮 LLM offline operator evolution、failure-informed revision 和 frozen portfolio。
- **当前禁令：** Gate B 未通过；不得运行真实 LLM/provider、正式/final-test/大规模实验，不得用两个 R2 smoke 文件形成论文证据。
- **Phase 6A：** 当前未获授权进入。Phase 5B-R 文档修订不授权 mock/file closed-loop planning 或 execution；须先通过新的 independent protocol review。
- **实现事实边界：** 本文档定义 planned conditions；portfolio、完整 elite retention 和 failure-specific revision 未全部实现。
- **Manifest 实现边界：** `archive/manifest_spec.md` 只是 strict schema contract；parser、canonical hash、duplicate/path safety、manifest-only runner 与 tests 尚未实现，均为 Phase 6/formal execution 前的 EXEC-BLOCKING。

## 2. Objective Version

### 2.1 `objective_v1_prototype`

- coverage processing 使用当前 `length / speed + turning cost`；
- depot/任务间 travel 使用 raw Manhattan distance；
- 只允许现有 `R2_T6_0.txt`、`R2_T10_0.txt` 的 smoke/demo、mock/file 接口检查；
- 不进入正式 ranking、operator freeze、论文表格、统计推断或 final-test。

### 2.2 `objective_v2_formal`

正式论文实验唯一允许的目标版本：

`travel_time(p,q) = ManhattanDistance(p,q) / travel_speed`

`processing_time = coverage_length / sweep_speed + turn_count * turning_time`

`travel_speed` 是独立有限正参数，不默认等于 `sweep_speed`。目标解释为 Manhattan travel、constant speed、无 collision/congestion、无 acceleration/deceleration、无 charging/refueling 假设下的 estimated completion time，而不是完整真实机器人执行时间。

`travel_speed = sweep_speed` 只作为预注册 sensitivity。`objective_v2_formal` 的 schema、loader、CostMatrix、DP/evaluator/lower bounds、tests、README/AGENTS/configs 和结果隔离完成前，正式实验保持 NO-GO。

## 3. Phase 5B Minimum Instance-Family Matrix

### 3.1 Strata 定义

| Size stratum | 预注册 robots/tasks combinations | 角色 |
|---|---|---|
| small | `(2,20)`, `(4,40)` | generation/train、近分布 dev 与 held-out ID test |
| medium | `(4,80)`, `(8,160)` | 主体 train/dev 与 held-out ID test |
| large | `(8,320)`, `(16,640)` | final-test unseen-scale generalization |
| stress/generalization | `(12,480)`, `(16,800)` | exploratory distribution/scale shift |

主 distribution strata 至少为：

- `D1_balanced_uniform`：balanced rectangle sizes、uniform spatial layout；
- `D2_mixed_clustered`：mixed aspect ratios、multi-cluster spatial layout；
- `D3_high_aspect_corridor`：high-aspect rectangles、corridor/anisotropic layout，只用于预注册 stress/generalization cell。

每个 distinct family 是 robots/tasks、rectangle/spatial distribution 全参数、sweep width、sweep/travel speeds、turning time、depot/overlap rule、objective/generator version 的固定 canonical combination；replicate seed 不属于 family 定义。

### 3.2 Minimum planning matrix

| Split | Size cells | Distribution cells | 每 cell robots/tasks | Distinct families / cell | Planning minimum replicates / family |
|---|---|---|---|---:|---:|
| train | small, medium | D1, D2 | 使用对应 size 的两个预注册 combinations | 4 | 10 |
| dev | small, medium | D1, D2；参数组合与 train family 不同 | 使用对应 size 的两个 combinations | 4 | 10 |
| final-test ID | small, medium | D1, D2；family IDs 全部 held out | 使用对应 size 的两个 combinations | 8 | 20 |
| final-test scale | large | D1, D2 | `(8,320)`, `(16,640)` | 8 | 20 |
| final-test stress | stress/generalization | D3 | `(12,480)`, `(16,800)` | 8 | 20 |

`4/4/8` 是每个实际纳入的 split×size×distribution cell 的最低 distinct-family planning value，不是统计功效已经证明。Train/dev-only pilot 或不使用 final-test 的先验 precision analysis 可以要求**增加** families 或 evolution runs；不得在查看 final-test geometry/performance 后调整。Planning minimum replicates 10/10/20 同样必须在生成前冻结；若资源不足，研究降级为 pilot/exploratory，而不是用更多 raw trials替代 distinct families。

同一 family 不得跨 split，但 pilot 与 formal 使用两个不可互换的身份域。任何 **pilot instance** 生成前，只冻结 pilot-only family matrix、pilot-only split rule、seeds 与 exclusions，并记录 `pilot_family_matrix_hash`、`pilot_split_assignment_rule_hash`；pilot manifests 标记 `manifest_scope=pilot_nonformal`、`matrix_scope=pilot`。Pilot 完成后、任何 **formal instance** 生成前，才冻结 complete formal family matrix、formal family→split assignment/deterministic rule、variant table、seeds 与 exclusion/replacement rule，并记录 scope 为 formal 的 `family_matrix_hash` 与 `split_assignment_rule_hash`。Pilot family/instance IDs、files、hashes、paths 与 file identities 不得提升、重标、复制或链接为 formal artifacts。本阶段不生成任何实例或 final-test manifest。

## 4. Method Conditions

### 4.1 Non-LLM baselines

| ID | Condition | 公平性要求 |
|---|---|---|
| N0 | Round-robin baseline | 固定 deterministic tie-breaking；作为弱参考，不竞争 strongest baseline |
| N1 | Baseline + current local search | 固定 local-search budget |
| N2 | Stronger local search | 邻域、停止规则和 budget 预注册 |
| N3 | Vanilla ALNS | 标准人工 operators；无 problem-specific advisor |
| N4 | Problem-specific ALNS | 人工 geometry/load-aware operators；候选 strongest non-LLM baseline |
| N5 | ALNS + rule-based advisor | Advisor 规则和访问特征冻结 |
| N6 | Human-designed operator portfolio | 仅在可实现且与 generated portfolio 使用相同 `k`/selector/budget 时纳入 |

Strongest non-LLM ALNS 必须从 N3–N6 的预注册候选中只用 train/dev 证据确定；不能看 final-test 后改名或重选。

### 4.2 Generated/operator controls

| ID | Condition | 角色 |
|---|---|---|
| G0 | Random syntactically valid operators | 控制随机 program search 与 evaluation budget |
| G1 | Mock/template operators | Pipeline/control，不支持 LLM 效果主张 |
| G2 | File-provider manually supplied operators | 人工 code control，不视为 LLM generation |
| G3 | One-shot LLM operators | RQ2/H1 mechanism baseline |
| G4 | Multi-round LLM without feedback | 控制多轮/候选预算本身 |
| G5 | Multi-round performance/rank feedback | 非结构化反馈 control |
| G6 | Multi-round structured feedback operators | A+D 主方法候选 |
| G7 | LLM single best frozen operator | Portfolio 对照 |
| G8 | LLM score top-k frozen operators | Diversity 对照 |
| G9 | LLM behavior-complementary frozen portfolio | A+C+D 完整主方法候选 |

G3–G9 需要真实 provider 的条件只是未来实验定义；在 Phase 7 preflight、runtime authorization 和风险确认前不得执行。

## 5. Budget Fairness Contract

所有可归因比较必须冻结并报告：

- scheduled candidate 数与实际 candidate evaluations；
- train/dev instance/family access 次数与 exact manifests；
- generation/revision rounds；
- LLM call、token 和可见 information budget；
- prompt length/padding/masking policy；
- wall-clock、candidate execution 与 benchmark evaluation budget；
- ALNS iterations、time limit、local-search budget 和 portfolio size `k`；
- benchmark seeds、solver seeds 与 independent evolution-run seeds；
- smoke/benchmark/operator/solver timeout 和基础设施 retry policy；
- invalid、timeout、fallback、blocked candidates 的成本是否计入（主分析必须计入）。

RQ2/RQ3/RQ7 至少报告等 candidate-evaluation budget 与等 token/information budget两种公平视角；不能让 multi-round/structured condition 同时获得更多 candidates、dev access 和 tokens。Solver-level comparison 使用相同 instance×solver-seed blocks 和相同 ALNS budget。

## 6. Experimental Flow

本协议冻结两个独立、不可互换的 preflight 生命周期：

### 6.1 Phase 6A / train-dev pilot lifecycle

1. 在任何 pilot instance 生成前，冻结独立的 pilot-only family matrix 与 pilot-only split rule，计算 `pilot_family_matrix_hash` 和 `pilot_split_assignment_rule_hash`；不得创建、读取或推断 final-test family matrix/assignment、manifest、files、hashes 或 performance；
2. 生成仅用于 pilot 的 instances/manifests；全部标记 `manifest_scope=pilot_nonformal`、`matrix_scope=pilot`、`artifact_promotion_allowed=false`，family/instance identity 与 formal identity domain 隔离；
3. 完成 pilot 所需的 objective-v2、manifest-only runner 和 pilot-scoped preflight implementation；pilot runner 只能接受 pilot manifests，不能接受 `formal_final_test`；
4. 运行 pilot preflight：只联合检查 supplied smoke/train/dev pilot manifests 的 schema/scoped hashes/path、内部及 train↔dev duplicate/family overlap、actual allowlist；生成 pilot-only receipt 和 pilot-artifact exclusion receipt；
5. 在另行通过 pilot-execution gate 后，pilot 只可验证 runtime、variance、pipeline closure、manifest-only execution、mock/file closed-loop、failure accounting 与 precision/power planning；结果不得支持 formal/final-test claim，也不能冻结或推断 final-test composition；
6. Pilot instances/manifests/IDs/hashes/paths/file identities 永久为 non-formal artifacts，不得提升、重标、复制或链接为 formal evidence。

### 6.2 Formal lockbox lifecycle

1. Pilot 结束后，其输出只能用于 precision/power planning 与协议调整；不得把任何 pilot artifact 提升或复用为 formal artifact；
2. 在不使用 final-test geometry/performance 的条件下、且在任何 formal instance 生成前，冻结 complete formal family matrix、formal split rule、replicates/evolution runs、method conditions、budgets、prompts 与 analysis plan；
3. 按冻结 formal matrix/rule 重新生成具有新 formal identity 的 train/dev/final-test instances，再生成 `formal_train`、`formal_dev`、`formal_final_test` 三份 manifests；formal IDs、hashes、paths、file identities 与 generation identities 不得命中 pilot-artifact exclusion receipt；
4. 在任何 formal prompt/operator generation、formal train/dev evaluation、formal portfolio selection 或 final-test run 前，由隔离 lockbox preflight 联合加载三份 formal manifests，执行跨 split 与 pilot-artifact exclusion checks，并生成绑定三份 manifest hashes、formal matrix/rule hashes 和 exclusion-receipt hash 的 immutable receipt；下游只接收 receipt，不接收 final-test records；
5. 仅在 Phase 7 另行批准后执行真实 provider generation/train 与 dev selection；冻结每个 evolution run 的 operator/portfolio、selector、code/config/prompts 和成本计划；
6. 仅在 Gate B、formal joint-preflight receipt 和 final-test opening authorization 均通过独立复审后运行 final-test；
7. 按预注册 batch 运行、报告并停止，不将结果反馈到设计环。

Pilot receipt 永远不能替代 formal joint-preflight receipt；formal lifecycle 也不得为 Phase 6A 提前暴露 final-test identity。Formal joint preflight 必须把 `pilot_nonformal` scope 或 pilot identity/hash/path/file-identity 泄漏视为 fail-closed input contamination。

## 7. Outcome Families

- **Primary solver outcome：** final makespan 和相对 strongest non-LLM baseline improvement；
- **Primary analysis population：** all scheduled independent evolution runs；不能只包含 successful freeze/deployment/evaluation。Generated-method failure runs 按统计计划记 0 improvement，并单独报告 failure/deployment/valid-portfolio rates；
- **Operator validity：** execution、feasibility/contract、optimization、structural 四轴及明确分母；
- **Robustness：** seed/family variance、worst quantile、time/iteration-to-target；
- **Portfolio：** usage entropy、selection trajectory、operator-level attribution、fallback；
- **Cost：** calls/tokens/provider latency、candidate/benchmark compute、solver runtime、amortized deployment cost；
- **Compliance：** manifest/hash、lockbox、fallback attribution 与 contamination status。

任何 smoke/demo、contaminated、inconclusive-integrity 或 `objective_v1_prototype` 结果都不得进入正式论文主效应估计。Localized generated-result failures 按统计计划的 failure-zero policy 保留；objective/input/manifest/split/lockbox/baseline-pairing integrity failure 不得补零，必须作为 contaminated/inconclusive batch 单独审计。
