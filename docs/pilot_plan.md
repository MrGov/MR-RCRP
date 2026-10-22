# Train/Dev-Only Pilot Plan

## 1. 状态与目的

- **状态：** Phase 5B-R4 documentation plan；本阶段不进入 Phase 6A，也不执行 pilot。
- **核心限制：** Pilot 使用独立 pilot-only family matrix/rule 和 `pilot_nonformal` manifests；不创建、读取、推断或运行 final-test matrix、manifest、families、files、hashes 或 performance。
- **真实 LLM：** 当前禁止。只有未来单独通过 Phase 7 preflight、runtime authorization 和风险确认后，才可在 train/dev 上增加 real-provider pilot。

Pilot 的目的：

1. 估计 loader/DP/ALNS/operator evaluation 与端到端 runtime；
2. 估计 family、replicate、solver-seed 和 evolution-run variance；
3. 检查预注册 family matrix 的可生成性和难度覆盖；
4. 验证 manifest-only runner、exact input set 和 hash failure paths；
5. 验证 mock/file provider 的 generation→validation→benchmark→freeze→deployment 闭环；
6. 估计是否需要增加 distinct families、replicates 或 independent evolution runs；
7. 验证日志、四轴 failure taxonomy、fallback attribution 和 result-table fields。

Pilot 是独立 non-formal identity domain。任何 pilot instance 生成前必须冻结 pilot-only matrix/rule，并记录 `pilot_family_matrix_hash`、`pilot_split_assignment_rule_hash`。所有 pilot manifests 必须标记 `manifest_scope=pilot_nonformal`、`matrix_scope=pilot`、`artifact_promotion_allowed=false`。Pilot family/instance IDs、manifests、files、hashes、paths 与 file identities 不得提升、重标、复制、链接或直接复用于 formal artifacts。

Pilot 不用于证明 LLM 有效、优于 baseline、泛化或成本优势。

Pilot 也不得接触或修改 final-test lockbox。Train/dev-only precision evidence 若要求修改 family/run 数、`delta_MCID` 或 analysis details，必须在 final-test assignment/generation/opening 前创建新 protocol/analysis version、记录理由与 hashes，并通过独立 review。Failure-run `delta_rf=0`、all-scheduled-runs population、complete-case supplementary-only 等主规则不得在看任何 final-test 信息后修改；未经重新预注册的 pilot adjustment 无效。

## 2. Preconditions

在任何 pilot execution 前至少需要：

- `objective_v2_formal` migration 与 travel-speed tests 通过；或明确标为 `objective_v1_prototype` 的 smoke-only step；
- pilot-only family matrix 与 pilot-only split rule 已在 pilot instance 生成前冻结并记录 pilot-scoped hashes；
- versioned generator/schema 和 pilot-only train/dev family assignment 已批准；
- `pilot_nonformal` manifests 和 hashes 已创建；不得存在 final-test manifest/path access；
- pilot runner 的 manifest-only mode、scope rejection 和 glob rejection tests 通过；
- mock/file provider eligibility/fallback closure tests 通过；
- pilot method matrix、seeds、timeouts、budget 和 analysis script 已冻结；
- pilot-artifact exclusion receipt 的 schema/保存位置已冻结，供未来 formal preflight 做反向排除；
- independent review 无 Critical/Required。

这些条件是未来执行门槛；本文档创建不表示已满足。

## 3. Pilot Stages

### P0 — Smoke Interface Check

- **Input：** 现有 `R2_T6_0.txt`、`R2_T10_0.txt`，独立 smoke manifest；
- **Objective：** `objective_v1_prototype`；
- **Provider：** mock/file only；
- **Checks：** parser、DP、operator validation/status、fallback、logs、manifest reader dry-run；
- **Evidence boundary：** 只证明接口可运行，不进入 variance/power、baseline ranking 或论文表格。

### P1 — Objective-v2 Pilot-Only Train/Dev Systems Check

- **Input：** 未来按 pilot-only matrix 生成的 `objective_v2_formal` pilot train/dev families；全部为 `pilot_nonformal`，final-test 不生成/不可见；
- **Provider：** mock/file/manual operators；
- **Checks：** runtime decomposition、manifest-only exact input、hash mismatch fail-closed、baseline/local-search/ALNS variance、family difficulty coverage、result schema；
- **Purpose：** 估计系统预算和 solver/family noise，不检验 LLM hypotheses。

### P2 — Generated-Method Train/Dev Precision Pilot

- **Default status：** blocked；只有 Phase 7 单独批准后才可使用 real provider；否则仅用 mock/file 验证 orchestration。
- **Input：** train/dev only；
- **Checks：** evolution-run variability、candidate funnel、token/call/runtime、feedback payload、portfolio composition stability；
- **Purpose：** 冻结 formal independent evolution-run 数和 budget，不产生 final-test claim。

## 4. Pilot Sampling

- P1 首先从每个计划纳入的 train/dev size×distribution cell 使用完整 distinct-family minimum（每 cell 4 families），避免用单个容易 family 估计 runtime/variance；
- Per-family replicate/solver-seed pilot 可分阶段增加，但所有 scheduled/failed runs 保留；
- Baselines 使用相同 family×replicate×seed blocks；
- P2 的独立 evolution-run 数只由 train/dev precision needs 决定；candidate/round rows不增加有效 run 数；
- 当前 planning values：train/dev 10 replicates/family、confirmatory generated conditions 目标 20 evolution runs；pilot 可按预注册 rule要求增加，不得因方法表现方向选择性调整。

## 5. Metrics and Diagnostics

### 5.1 Runtime

- provider latency、validation、subprocess startup/overhead、candidate runtime；
- DP/benchmark、ALNS/local search 和 end-to-end wall time；
- timeout frequency、memory/CPU observations（只作风险记录，不宣称隔离）。

### 5.2 Variance and precision

- family、replicate、solver-seed components；
- generated arms 的 evolution-run component；
- projected two-way clustered 95% CI half-width for primary estimand；
- floor `4/4/8` 与 target 20 runs 下的 precision simulation。

### 5.3 Family matrix checks

- generation validity、geometry summary、service/travel/turn burden coverage；
- baseline runtime 与 difficulty distribution，只用于检测退化/不可运行 cells；
- 不得根据某 LLM/method 的相对性能交换 split 或删除困难 families。
- 该检查只作用于 pilot-only matrix；不得据此读取、生成、挑选或推断 final-test family matrix。Pilot 结束后若形成 formal design，必须在任何 formal instance 生成前另行冻结 complete formal matrix/rule。

### 5.4 Pipeline validity

- exact manifest allowlist、file/family/split hashes；
- four-axis statuses and denominators；
- fallback/generated attribution；
- leaderboard/feedback eligibility filtering；
- frozen expected-hash execution 与 registry fallback；
- reproducibility/result-table required fields completeness。

## 6. Pre-Registered Decision Rules

- Primary planning target：projected 95% CI half-width `≤ 0.02` for relative makespan improvement；
- 若 family-level variance 主导且 target 未达，增加 distinct families；
- 若 evolution-run variance 主导，增加 independent evolution runs；
- 若 seed/replicate noise 主导，再增加 per-family replicates/solver seeds；
- 不得以增加 raw candidates 替代 evolution runs，或以增加 replicates 替代 families；
- 若资源无法达到 target，研究降级为 pilot/exploratory，删除 confirmatory wording；
- Family/replicate/run 数只能使用 train/dev pilot 或保守先验调整，并在 final-test assignment/generation/opening 前冻结；
- Difficulty coverage 调整必须作用于整个预注册 cell/rule，创建新 protocol/hash，不按方法性能挑实例。

所有 decision、输入统计、simulation code/hash、批准人和时间必须写入 `pilot_decision_log.json` 或等价不可变 artifact。

## 7. Outputs

- pilot-only family matrix/rule 与 `pilot_family_matrix_hash`、`pilot_split_assignment_rule_hash`；
- `pilot_nonformal` manifest 与 exact actual-input manifest；
- pilot preflight receipt 与 immutable pilot-artifact exclusion receipt（覆盖 IDs、hashes、paths、file identities、generation identities）；
- runtime/variance/precision report；
- family-generation/geometry validation report；
- mock/file pipeline compliance report；
- failure/fallback/attribution summary；
- recommended family/replicate/evolution-run budget 和理由；
- deviations、errors、retries、excluded/invalid records；
- updated protocol version/hashes（若依据预注册 rule 调整）。

Pilot outputs 只能用于 Phase 5B/6/7 planning、precision/power planning 和正式协议设计冻结，不得作为 final-test performance、论文 main result 或真实 LLM effectiveness evidence。Pilot artifacts 本身不得升级为 formal train/dev/final-test instances、manifests 或 evidence；formal instances 必须在 complete formal matrix/rule 冻结后重新生成并取得新的 formal identity。

## 8. Exit Criteria

Pilot 只有在以下条件满足时才可建议进入后续 execution review：

- manifest-only runner 和 exact-input/hash gates 有测试证据；
- objective_v2、generator/schema、baseline/ALNS pipeline 稳定；
- scheduled failure/fallback/status 记录完整；
- all scheduled evolution runs accounting、failure-run zero-improvement primary rule 与 complete-case supplementary output 可重放；
- sample-size/precision decision 已冻结；
- no final-test access/contamination；
- pilot-artifact exclusion receipt 完整，且所有 outputs 保持 `pilot_nonformal` / promotion prohibited；
- latest independent review 无 Critical/Required；
- real provider（如计划）另有 Phase 7 authorization。

即使 exit criteria 满足，也只允许提交 formal design/Gate B/Phase 7 review，不自动授权正式或 final-test execution，也不允许把 pilot artifacts 重标为 formal artifacts。
