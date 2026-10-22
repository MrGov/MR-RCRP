# Final-Test Lockbox Protocol

## 1. 目的与当前状态

本协议防止 final-test information 进入 LLM prompt、operator generation/revision、candidate selection、portfolio composition、model choice 或超参数调优。

- **状态：** Phase 5B-R4 protocol revision；尚未创建或打开 final-test manifest，本文件不构成 execution authorization。
- **当前两个 R2 实例：** 已用于开发上下文，只能是 smoke/demo，不能进入 lockbox。
- **权限：** 本文件不授权 Phase 6A、真实 LLM、pilot/formal experiment 或 final-test access。

## 2. Lockbox 对象

Final test 是一个冻结 evaluation batch，而不是单个文件或单个 seed。它至少包含：

- final-test family IDs 与每个 family 的生成参数 hash；
- family matrix、final-test family assignment 与 `family_matrix_hash`；
- 生成前冻结的 split assignment rule 与 `split_assignment_rule_hash`；
- instance IDs、rep IDs、paths 与 file SHA-256；
- objective model version、instance schema version、generator version/hash；
- 预注册 evolution-run/portfolio manifests；
- solver seed 列表、run budget、timeout/failure policy；
- primary/secondary estimands、聚合、CI、缺失与多重比较规则；
- exclusion criteria；
- selector state reset policy；
- 授权打开次数、负责人、`contamination_owner`、冻结时间与 manifest hash。

建议未来保存三个不可覆盖文件：

- `manifests/train_manifest_v1.json`
- `manifests/dev_manifest_v1.json`
- `manifests/final_test_manifest_v1.json`

路径只是规划，不在本阶段创建。正式 manifest 应使用 canonical serialization 并记录 SHA-256；任何修改都创建新版本，不覆盖原文件。

### 2.1 Family assignment authority

Final-test family assignment 本身是 formal lockbox 的一部分，而不是实例生成后再做的分析选择。Complete formal family matrix、formal family→split assignment 或确定性 assignment rule 必须在任何 **formal instance** 生成之前 canonicalize 并冻结；scope 为 formal 的 `family_matrix_hash` 与 `split_assignment_rule_hash` 必须进入 protocol approval record 和三个 formal split manifests。该规则不要求、也不允许 Phase 6A pilot 提前创建或推断 formal/final-test matrix。

禁止在生成全部实例后，依据矩形几何难度、baseline performance、LLM performance、solver failure、人工偏好或预期论文叙事交换 family/split。预注册生成失败只能按冻结的 exclusion/replacement-seed rule 处理，不能改变 family assignment。任何生成后改动都创建新 protocol version，并使旧 final-test assignment 标为 contaminated/abandoned。

### 2.2 Pilot 与 formal lockbox 的生命周期隔离

Final-test lockbox **不参与 Phase 6A pilot**。Phase 6A/mock/file/train-dev pilot 使用独立的 pilot-only family matrix、pilot-only split rule 和 `pilot_nonformal` manifests；不得创建、读取、hash、访问或推断 final-test manifest、final-test files、final-test family matrix/assignment、final-test families、hashes 或 performance。Pilot preflight/receipt 只证明 non-final input contract；它不能冻结 final-test composition，不能升级为 formal receipt，也不能支持 final-test claim。

Pilot instances/manifests/family IDs/instance IDs/hashes/paths/file identities 永久为 non-formal artifacts，不得提升、重标、复制、链接或直接复用于 formal train/dev/final-test。Formal lifecycle 在 pilot 完成后，先用 pilot 结果做 precision/power planning 与协议调整；随后在任何 formal instance 生成前另行冻结 complete formal family matrix 与 formal split assignment，再生成具有新 formal identity 的三类 instances 与三份 manifests。只有 manifests 生成后才能创建 formal lockbox receipt。

正式 prompt/operator generation、formal train/dev evaluation、formal portfolio selection 与 final-test execution 之前，lockbox boundary 必须联合验证 train/dev/final-test manifests，并对 pilot-artifact exclusion receipt 做反向排除，产生 immutable three-manifest receipt。下游方法组件只获得 receipt/pass-fail，不获得 final-test records。Formal preflight 命中 `pilot_nonformal` scope、pilot hash/path/file identity 或 pilot family/instance identity 时必须 fail closed。

## 3. 生命周期

| 状态 | 允许操作 | 禁止操作 |
|---|---|---|
| draft | 设计 family、统计与预算；不生成实例、不运行方法 | 不得称为 held-out evidence |
| assignment_frozen | 在任何 formal instance 生成前冻结 complete formal family matrix/formal split rule 及其 hashes | 不得依据生成后 geometry、baseline 或 LLM 表现换 split；pilot matrix/receipt 不得替代 |
| frozen | 校验实例/manifest hash 和不相交性；保存审批记录 | 不得修改方法或依据 test 特征设计规则 |
| opened | 按预注册 batch 运行并只记录结果 | 不得调 prompt/operator/portfolio/hyperparameter 后重跑同一 lockbox |
| reported | 汇总预注册结果、失败与成本 | 不得将结果反馈给未来同一 lockbox run |
| contaminated | 记录泄漏来源和时间 | 不得进入 confirmatory result；需新 lockbox/version |

进入 `assignment_frozen` 需要记录 protocol version、complete formal family matrix、formal split rule、两个 formal-scope hashes、formal identity version、批准人和日期。进入 `frozen` 还需要两人或负责人+自动审计的批准记录：三份 formal manifest hashes、pilot-artifact exclusion receipt/hash、code/config hash、planned method conditions、run counts、`contamination_owner` 与日期。没有 hash 的“口头冻结”无效。

## 4. 信息隔离规则

在 final test 打开前和打开后，以下信息不得反馈给 LLM 或设计环：

- final-test rectangles、families、instance features 或文件内容；
- makespan、相对改善、validity、fallback、failure cases；
- operator usage/selection trajectories；
- per-family subgroup 表现；
- cost/token/runtime result；
- 任何能让 prompt、candidate pool、portfolio、selector、budget 或 hyperparameters 针对 lockbox 调整的信息。

任何上述信息回流都构成 contamination，不得进入 confirmatory result。

Final-test manifest 可由执行负责人/脚本读取，但 generation、feedback 与 tuning 程序只应获得 train/dev manifests。若操作环境无法实施该隔离，正式实验保持 no-go。

## 5. 打开前冻结项

以下所有对象必须以 hash 或 immutable version 标识：

- source code 与 environment/依赖；
- objective model 和 instance protocol；
- family matrix、split assignment rule、`family_matrix_hash` 与 `split_assignment_rule_hash`；
- method conditions、baselines 与 ablations；
- prompts、provider/model settings、candidate/token/call budget；
- 每个 independent evolution run 的 frozen operator/portfolio；
- portfolio composition、selector algorithm、初始权重与更新规则；
- ALNS/DP/baseline configs；
- instance/family/solver seeds；
- primary hypothesis hierarchy和统计脚本；
- failure taxonomy、fallback/invalid/timeout 处理；
- 允许的重试仅限基础设施失败，并预定义判定规则。

任何缺项都阻止打开。

## 6. Adaptive portfolio 的边界

允许预注册 adaptive selector 在**单个 test run 内**根据该 run 的内部搜索状态更新 operator weights。必须：

- 在每个 test instance、solver seed、independent evolution run 和 test file 开始时重置；
- 不跨进程/文件持久化 learned state；
- 不改变 frozen portfolio composition、operator code、selector algorithm 或 hyperparameters；
- 将轨迹用于最终报告或预注册分析，不用于后续设计反馈。

跨任一边界保留 learned weights 均构成 contamination。

## 7. 正式执行与审计

每个 final-test batch 必须：

1. 验证 formal three-manifest joint-preflight receipt/hash 在三份 formal manifests 生成后创建，并早于任何 formal prompt/operator generation、formal train/dev evaluation、formal portfolio selection 和 final-test run；重新验证 manifest/file hashes、pilot-artifact exclusion receipt/hash 与 receipt policy version；
2. 验证实际 family matrix/split assignment 与 `family_matrix_hash`、`split_assignment_rule_hash` 一致；
3. 验证实际输入恰好等于 manifest allowlist，拒绝 wildcard/glob 额外文件；
4. 验证 code/config/operator/portfolio hashes；
5. 用预注册顺序或随机化 block 运行全部 conditions；
6. 捕获每个 run 的状态、runtime、fallback、invalid、timeout 与资源/LLM 成本；
7. 保存不可变 raw result manifest；
8. 只执行预注册聚合，探索性分析另行标记；
9. 报告 independent evolution runs、distinct families、replicates、solver seeds 与所有 exclusions。

“一次性”指一次预注册完整 batch，可包含多个 instances/seeds/evolution runs，不是只运行一个 trial。

## 8. 失败、重试与污染

- 候选/solver 的 invalid、timeout、fallback 是方法结果，不得自动重跑直至成功。
- 只有预定义的基础设施故障可按冻结次数重试；原失败日志保留，替代规则预先确定。
- 若代码 bug 改变目标或方法语义，停止 batch、标记本 lockbox opened/contaminated；修复后需要新的未见 test set 或把后续结果降为 exploratory。
- 若 final-test result 被用于任何设计修改，同一 lockbox 的后续结果全部标为 contaminated。
- Objective/input hash、formal manifest schema/hash、split/family overlap、uncontrolled glob、cross-split exact-file duplicate 或任何 final-test integrity violation 使受影响的 formal integrity unit contaminated；baseline pairing missing/unverifiable 使其 inconclusive。这些事件不得作为 localized cell failure 补零。
- Negative result、null result 或高方差不能成为重新打开和调参的理由。

## 9. Default glob 防线

当前 `data/R*_T*_*.txt` 默认 glob 不符合 lockbox 要求。正式 runner 必须实现 manifest-only formal mode，并 fail closed：

- 未提供 split manifest 时拒绝；
- manifest/文件 hash 不匹配时拒绝；
- final-test ID 出现在 train/dev 输入或缓存时拒绝；
- 实际读取集合与 allowlist 不完全相等时拒绝；
- 输出必须记录输入 manifest hash。
- formal runner 必须要求有效 three-manifest joint-preflight receipt；pilot receipt 或只验证 active split 均不足；任何 `pilot_nonformal` record 或命中 pilot exclusion identity 的 formal record都必须拒绝。

在该防线实现并测试前，物理目录隔离只能用于 smoke，不能认定 lockbox 已成立。

## 10. 关闭与公开

主分析完成后可以公开 final-test manifest、instances 和 raw results，但公开时点必须在方法冻结和正式 batch 完成之后。公开不改变此前 lockbox 的有效性；任何基于已公开 test 的后续方法改进都必须使用新的 test version，并清楚标为新研究周期。
