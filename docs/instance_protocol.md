# MR-RCRP 正式实例协议

## 1. 状态、目标与 no-go

- **状态：** Phase 5A-SR 修订候选，等待 documentation-entry review 批准；尚未生成或修改任何数据。
- **目标：** 在真实 LLM generation 或论文实验前，冻结可复现的 instance families、重复、family-level split、随机性层级与泄漏规则。
- **当前 no-go：** 仓库仅有 `R2_T6_0.txt` 与 `R2_T10_0.txt` 两个 2-robot、单 replicate 文件。它们只能用于 smoke/demo，不能支持 train/dev/final-test、泛化、显著性或论文结论。

本协议必须与批准后的 `modeling_decisions.md` objective version 绑定。若正式采用统一时间口径，实例生成前必须先完成 `travel_speed` schema 与测试；否则新数据会继承不可比较的目标定义。

## 2. Instance family 与 instance record

### 2.1 Family 的定义

一个 **instance family** 是以下生成因素的固定组合，不包含具体 replicate seed：

- `robot_count`；
- `task_count`；
- `rectangle_size_distribution`：宽/高分布、参数、最小尺寸和 aspect-ratio regime；
- `spatial_distribution`：矩形中心/边界的生成机制、工作区范围、cluster/corridor/uniform 等参数以及 overlap policy；
- `sweep_width`；
- `sweep_speed`；
- 经批准后使用的 `travel_speed`；
- `turning_time`；
- depot rule、distance metric 与 objective model version；
- `generation_rule_version`、generator name/version/code hash 与全部固定生成参数。

Family ID 应由上述 canonical JSON 的 SHA-256 派生，例如 `fam_<12hex>`，而不是只使用 `R{R}_T{T}`。改变任一生成分布、速度、turning time、overlap rule 或 objective version 都产生新 family。

### 2.2 Instance record

Family 内每个具体实例还必须记录：

- `rep_id`：family 内从 0 开始、唯一且连续的重复编号；
- `instance_seed`：独立生成 seed；
- `instance_id` 与文件名；
- 文件 SHA-256；
- generator output validation status；
- 生成前规定的 exclusion check 结果。

`rep_id` 不是 solver repetition，也不是 independent evolution-run repetition。文件名可继续保留 `R{R}_T{T}_{rep}.txt` 以兼容 loader，但正式 manifest 必须用 family ID + instance ID 消除同名/同规模歧义。

## 3. 生成分布建议

正式 family 至少覆盖以下可预注册轴；具体参数必须在生成前冻结，不能看算法结果后修改：

- **Rectangle size：** balanced rectangles、mixed aspect ratios、high-aspect rectangles；宽高始终有限正值。
- **Spatial layout：** uniform spatial、multi-cluster、corridor/anisotropic；明确工作区边界和 rectangle overlap 是否允许。
- **Service/travel balance：** 通过 sweep width、sweep/travel speed 与 turning time 定义 low/medium/high turn burden，而不是事后按求解结果挑实例。
- **Load ratio：** `task_count / robot_count` 覆盖低、中、高负载，但避免只凭一个比例把不同规模视为同一 family。

Structural diagnostics 应基于可测属性，不能用“某个方法在该实例表现差”作为 family 或 exclusion 定义。

## 4. 建议规模层级

下表是进入数据生成前待批准的目标网格。运行预算 pilot 可以在 **打开 final test 前** 缩减整个预注册 family，但不能根据方法表现选择性删除困难 family。

| 层级 | 建议 `(robots, tasks)` | 主要用途 | Replicate 口径 |
|---|---|---|---:|
| smoke/demo | 现有 `(2,6)`、`(2,10)` | parser、DP、mock/file provider、日志与失败路径检查 | 现有各 1；不作论文证据 |
| small | `(2,20)`、`(4,40)` | generation/train、快速 ablation、正确性 | 对每个已分配到某一 split 的 family 使用该 split 冻结的 per-family replicate 数 |
| medium | `(4,80)`、`(8,160)` | 主体 train/dev 与 in-distribution evaluation | 同上；同一 family 不得同时贡献 train 和 dev replicates |
| large | `(8,320)`、`(16,640)` | 可扩展性与高负载评价 | Phase 5B 按预算/precision 冻结，但不能以增加 replicates 替代 distinct families |
| stress/generalization | 未在 train 出现的 robot/task 比、规模或 spatial/size regime，例如 `(12,480)` 与分布 shift | 预注册 OOD/跨规模 exploratory generalization | 只属于预先指定的 split；不得依据生成后难度调整 |

矩形 size/spatial/burden 各轴不要求做不可承受的完整笛卡尔积；应在生成前选定一个覆盖平衡的 family matrix，并将未纳入组合列为 out of scope。若 large/stress 超出预算，应删除整个 family 并在 manifest 冻结前记录理由，而不是降低失败方法的运行次数。

## 5. Family-level split

### 5.1 三个互斥集合

1. **Generation/train：** 可用于 prompt examples、候选 generation/revision、failure feedback、训练期 benchmark。
2. **Selection/dev：** 可用于候选 ranking、portfolio composition、停止规则、超参数与 model/prompt variant 选择；不得伪装成 final test。
3. **Final-test lockbox：** 方法、prompt、operator set/portfolio、selector、预算、统计方案和排除规则冻结后才可打开。

同一个 family ID 只能属于一个 split。禁止随机拆 raw files，使同一生成参数的 replicates 分散到 train/dev/test。Train/dev repetition 指**各自 split 内不同 families 的 per-family repetitions**，不表示同一 family 可以分别贡献 train 和 dev replicates。

实例协议有两个不可互换的 scope。任何 pilot instance 生成前，必须冻结并 canonicalize pilot-only family matrix 与 pilot-only split rule，记录 `pilot_family_matrix_hash` 与 `pilot_split_assignment_rule_hash`；pilot 不包含、读取或推断 final-test family。Pilot 完成后、任何 formal instance 生成前，必须另行冻结 complete formal family matrix、formal family→split assignment 或可重放的确定性 rule，并记录 formal-scope `family_matrix_hash` 与 `split_assignment_rule_hash`。两种 scope 都禁止先生成对应 scope 的全部实例，再根据矩形几何难度、baseline performance、LLM performance、solver failure 或人工偏好选择/交换 split。生成失败只能使用对应 scope 预先冻结的 exclusion/replacement-seed rule。

Pilot 与 formal 是不同 identity domains。Pilot family/instance IDs、files、hashes、paths、file identities 和 manifests 不得直接提升、重标、复制、硬链接/软链接或复用于 formal train/dev/final-test；默认也不得复用 pilot family ID。若 formal protocol 采用相同概念参数组合，必须按冻结的 formal generator/rule 重新生成并赋予新的 formal identity，且 formal joint preflight 仍拒绝相同 bytes/hash/path/file identity 或 generation identity。

### 5.2 建议 split 结构

- train 覆盖 small/medium 的基础 rectangle/spatial regimes；
- dev 使用不同 family 参数组合，并保留与 train 相邻的规模，用于选择而非最终主张；
- final-test 同时包含：
  - 预注册的 in-distribution held-out families；
  - 未在 train/dev 出现的规模或分布组合，用于 exploratory generalization；
- B（instance conditioning）泛化消融必须使用预先指定的 held-out family，不能事后选择显示收益的规模。

精确 family IDs 和 split 数量必须进入 versioned manifests；本文件不给尚未生成的数据虚构 ID。Final-test family assignment 是 lockbox 的组成部分，从 assignment rule 冻结起即不得依据任何生成后或方法结果调整。

## 6. Distinct families、重复与随机性层级

### 6.1 Study tiers

| Tier | 数据范围 | 允许用途 | 禁止主张 |
|---|---|---|---|
| smoke/demo | 现有 `R2_T6_0.txt`、`R2_T10_0.txt` | parser、DP、mock/file、日志与失败路径 | 不进入正式统计，不支持 LLM/泛化/显著性结论 |
| pilot_nonformal / Phase 6A pilot | 独立 pilot-only matrix 的 smoke/train/dev；不创建、读取或推断 formal final-test instances/families | 估计 runtime、solver/candidate variance、instance difficulty，验证 pipeline/manifest-only/mock-file 闭环与 precision/power 需求 | 所有 artifacts 标记 non-formal、不得提升；不得打开 final-test 或声称 confirmatory result |
| formal experiment | 满足下面 distinct-family floor，并通过 formal-experiment execution gate | 预注册的 train/dev/final-test evaluation | 未满足 floor 或 gate 时不得升级为 confirmatory evidence |

Pilot_nonformal 的结果可以在后续 formal design freeze 前用于 precision/power planning、冻结计算预算候选、replicate 数和 independent evolution-run 数，但不能用于选择或推断 final-test families，也不能接触 final-test geometry/performance。它不构成 formal evidence。

### 6.2 Phase 5B distinct-family minimum

以下是 formal experiment 的**预注册最低 floor**，按每个实际纳入的 `split × size stratum × distribution stratum` 分别计算：

| Split | 每个 size×distribution stratum 的最低 distinct families | 用途 |
|---|---:|---|
| train | 4 | generation/revision 与训练期 benchmark |
| dev | 4 | selection、portfolio composition 与 tuning |
| final-test | 8 | held-out family-level evaluation 与 bootstrap/CI |

该 floor 不要求建立 size/distribution 的完整笛卡尔积；实际纳入哪些 strata 必须在 family matrix 中预先声明。一旦某个 stratum 被纳入正式实验，就必须满足对应 floor。Final-test 任一纳入 stratum 少于 8 个 distinct families，或 train/dev 任一纳入 stratum 少于 4 个，整个相关分析只能标为 pilot/exploratory，不能声称 confirmatory result。

Family-level CI/bootstrap 的抽样单位是 **distinct family ID**，不是 raw trial row、instance replicate、solver seed 或 candidate row。Replicates 用于估计 family 内变异，不能替代 distinct-family 数量。所有结果表必须同时报告 independent evolution-run repetitions、distinct test families、每 family replicates 与 solver seeds。

### 6.3 Instance replicates

- 每个 family 的 replicate 数必须在 Phase 5B 经 precision/power 与预算分析后固定，并在同一 stratum 内一致；
- train/dev 每 family 10、final-test 每 family 20 可作为规划候选，不是本轮硬性承诺；
- replicate 数减少不能补偿 distinct-family floor，不满足 floor 时必须降级为 pilot/exploratory；
- generation failure 或预注册几何 invalid 只能按冻结 exclusion rule 处理；不得因某方法性能差而排除。

### 6.4 Independent evolution-run repetitions

每个 generated-method condition 的独立重复单位是完整 evolution run。建议：

- confirmatory H1 条件：目标 20 个 independent evolution runs；
- gate-kept H6/H3：目标 20；若预算不足至少 10，并把置信度/检验能力不足明确报告；
- secondary/exploratory 条件：至少 10，或只报告描述性结果；
- one-shot 与其他 LLM controls 必须使用相同 run-level provider/model/time-block、candidate、token 与 evaluation budget 配对。

目标 20 个 independent evolution runs 是后续 precision/power analysis 的候选，不是本轮硬性承诺。数量可在只使用 `pilot_nonformal` train/dev、且不创建或接触 final-test family/性能后，为 formal protocol 冻结。Candidate、round、instance、benchmark seed 都不能替代 evolution-run repetition；资源不足时只能降级为 pilot study。

### 6.5 Benchmark seed 与 solver seed 的嵌套

层级固定为：

`method condition → evolution-run repetition → frozen operator/portfolio → family → instance replicate → solver seed → run result`。

- `evolution_run_seed` 控制完整 generation/revision run，并写入 run manifest；
- train/dev candidate benchmark 建议每 instance 使用 5 个预注册 benchmark seeds，用于估计候选随机方差；
- frozen evaluation 建议每 evolution run × instance 使用 10 个 solver seeds；
- baseline 使用同一 instance/solver-seed block 配对；确定性 baseline 可只计算一次，但统计表仍关联同一 block，而不是复制成多个独立 observation；
- seed 列表必须显式保存，不能只保存 master seed；派生算法与版本也必须记录；
- 统计先在 evolution run × family 内聚合，再跨 runs/families；不能 bootstrap raw candidate rows。

## 7. Default glob 风险与强制规避

当前 `benchmark_instance_glob = "data/R*_T*_*.txt"` 会自动纳入全部匹配文件。该行为对 smoke 方便，但对正式 split 是数据泄漏风险。

正式运行必须满足：

- runner 接受显式 `split_manifest` 与 `split=train|dev|final_test`；
- formal mode 禁止 wildcard/glob 作为权威输入；
- preflight 读取 allowlisted instance IDs/paths，并验证文件 hash；
- preflight 检查 train/dev/final-test family IDs 与 instance IDs 两两不相交；
- evolution/feedback 进程无权发现 final-test paths，日志也不暴露 final-test geometry；
- output manifest 记录实际读取文件清单并与预期 manifest 比较；`exact input set` 必须完全相等，多/少任一文件都 fail closed。

在上述代码/配置门禁实现前，**不得开始正式实验**。手工把文件移到临时目录可用于 smoke，但不能替代可审计的 formal-mode gate。

## 8. Smoke/mock/file provider 使用规则

现有两个 R2 文件允许用于：

- loader/state/DP/solution 的轻量检查；
- mock provider 的 deterministic closed-loop smoke；
- file provider 的人工候选格式、AST/contract/fallback 路径检查；
- 文档示例与 demo。

现有 `R2_T6_0.txt` 与 `R2_T10_0.txt` 不得用于：

- 真实 LLM 效果、operator evolution 收益或泛化主张；
- train/dev/final-test 三分；
- prompt/model/portfolio 在其 performance 上调优后再称 held-out；
- 统计显著性或 evolution-run replication 的替代品。

若任何新实例被用于 prompt debugging、generation、feedback 或方法选择，它立即属于 train/dev 信息域，永远不能再进入 final-test lockbox。

## 9. 生成、验证与冻结顺序

### 9.1 Pilot-only lifecycle

1. 批准 `modeling_decisions.md` 和 pilot 使用的 objective model version；
2. 在任何 pilot instance 生成前冻结 pilot-only family matrix、pilot-only split rule、replicates、seeds 和 exclusion/replacement rules，记录 `pilot_family_matrix_hash` 与 `pilot_split_assignment_rule_hash`；
3. 实现并测试 versioned generator/schema 与 pilot manifest-only runner；
4. 按 pilot rule 生成 `pilot_nonformal` instances/manifests，只运行方法无关的 schema/geometry 和 pilot-scoped preflight；
5. 保存 pilot receipt 与 pilot-artifact exclusion receipt；不得创建、读取或推断 final-test matrix/manifest/files/hashes/families/performance；
6. Pilot 输出只用于 runtime/variance、pipeline/mock-file closure 和 precision/power planning；不得升级为 formal artifacts/evidence。

### 9.2 Formal lifecycle

1. Pilot 结束后仅使用其 precision/power 与 pipeline evidence 调整 protocol；
2. 在任何 formal instance 生成前，批准并冻结 complete formal family matrix、生成分布、distinct-family floor、replicate 计划、formal family→split assignment/rule、seeds 与 exclusion/replacement rules；记录 formal-scope `family_matrix_hash` 与 `split_assignment_rule_hash`；
3. 按冻结 formal rule 生成具有新 formal identity 的 train/dev/final-test instances，只运行方法无关的 schema/geometry checks；
4. 生成 `formal_train`、`formal_dev`、`formal_final_test` 三份 manifests，计算 file/formal matrix/formal split rule/manifest hashes；
5. Formal joint preflight 同时验证三份 manifests 并拒绝任何 pilot IDs/hashes/paths/file identities/generation identities；
6. 将 final-test family assignment、三份 manifest receipt 与 pilot-artifact exclusion receipt/hash 按 `final_test_lockbox_protocol.md` 冻结；
7. 实现并验证 manifest-only formal runner；
8. 只有 formal-experiment execution gate 全部关闭后，才能另行申请运行实验。

任何实例重生成、family 参数、objective version、排除规则或 split 变化都产生新 protocol version；不得覆盖旧 manifest。
