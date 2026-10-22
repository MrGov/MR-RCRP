# Experiment No-Go Checklist

## 1. 使用方法

本清单严格拆分授权层级。Gate A 只控制是否允许进入 **Phase 5B 文档化实验协议**；Gate P1 控制是否允许进入 Phase 6A mock/file closed-loop **planning**；Gate P2 控制是否允许实际执行 pilot/mock/file；Gate B 控制是否允许执行 formal experiment。通过 Gate A、P1 或 P2 都不代表通过 Gate B，也不授权真实 provider、formal solver、final-test 或大规模实验。

当前结论：**Gate A PASSED（documentation only）；Gate B NO-GO。** 允许进入 Phase 5B 编写/冻结实验协议文档，但仍禁止调用真实 LLM、打开 final-test lockbox或运行正式、大规模或论文实验。

## 2. Gate A：Phase 5B documentation-entry

只有以下六项全部满足，才可提交 Phase 5B documentation-entry review。Review 批准后也**只允许编写/冻结实验协议文档**，不允许运行实验：

- [x] **DOC-BLOCKING** `docs/modeling_decisions.md` 已批准 B：统一时间 + independent `travel_speed`，并限定 estimated-time assumptions。
- [x] **DOC-BLOCKING** `docs/instance_protocol.md` 的 Phase 5A-SR 修订已通过独立复审（0 Critical、0 Required）。
- [x] **DOC-BLOCKING** `docs/final_test_lockbox_protocol.md` 的 Phase 5A-SR 修订已通过独立复审（0 Critical、0 Required）。
- [x] **DOC-BLOCKING** 当前两个 R2 文件已明确为 smoke/demo-only，不进入正式统计或 lockbox。
- [x] **DOC-BLOCKING** default glob 自动纳入全部实例的泄漏风险及 manifest-only 目标已写清。
- [x] **DOC-BLOCKING** formal-experiment execution blockers 已完整登记在本清单 Gate B 和 `task_plan.md`。

**Gate A 当前状态：PASSED（documentation only）。** 此处只同步 Phase 5A-SR-R 独立复审结果并授权 Phase 5B 文档工作；不关闭 Gate B，不授权 provider、solver、data generation、final-test 或任何实验。

## 3. Gate P：Phase 6A pilot 的 planning 与 execution 分离

Gate P 与 formal lockbox preflight 分离。本轮 Phase 5B-R4 **不关闭 Gate P1/P2，也不进入 Phase 6A**。

### 3.1 Gate P1：Phase 6A planning-entry

通过后只允许规划以下内容，不允许执行 pilot：

- [ ] 规划 mock/file closed-loop、pilot-only manifests 和 pilot-only runner checks；
- [ ] 规划独立 pilot-only family matrix/split rule、scoped hashes 与 `pilot_nonformal` identity；
- [ ] 规划 pilot preflight receipt、pilot-artifact exclusion receipt 与 failure accounting；
- [ ] 独立 review 确认 planning 不创建、不读取、不推断 final-test matrix/manifest/files/hashes/families/performance；
- [ ] 明确 planning 不授权真实 LLM/provider、formal instance/final-test generation、正式/大规模/final-test execution。

Gate P1 通过只表示可以编写 Phase 6A mock/file closed-loop 计划；不允许运行 smoke/pilot、生成 pilot/formal 数据或关闭 Gate P2/Gate B。

### 3.2 Gate P2：Pilot execution

真正运行 pilot/mock/file 前，必须全部满足：

- [ ] pilot-only family matrix 已在任何 pilot instance 生成前冻结，并记录 `pilot_family_matrix_hash`；
- [ ] pilot-only split rule 已在任何 pilot instance 生成前冻结，并记录 `pilot_split_assignment_rule_hash`；
- [ ] pilot manifests 通过 pilot-scoped schema validation，且均为 `manifest_scope=pilot_nonformal`、`matrix_scope=pilot`、`artifact_promotion_allowed=false`；
- [ ] pilot runner 只使用 manifest allowlist，拒绝 glob、formal manifests 和 `formal_final_test`；
- [ ] pilot preflight 已验证 schema/scoped hash/path、duplicate exact file、family overlap、split mismatch、allowlist 和 actual inputs；
- [ ] pilot-artifact exclusion receipt 已定义并记录 pilot IDs、hashes、paths、file identities 和 generation identities；
- [ ] final-test matrix/manifest/files/hashes/families 不存在于 pilot workspace 或由权限边界保证不可访问；pilot config/parser 对其 fail closed；
- [ ] pilot用途仅为 runtime、variance、pipeline、manifest-only execution、mock/file closed-loop、failure accounting 与 precision/power planning；不支持 formal/final-test claim；
- [ ] 当前两个 R2 文件仍仅限 smoke/demo；所有 pilot artifacts 永久为 non-formal 且不得提升；
- [ ] 独立 review 无 Critical/Required，并获得明确 pilot-execution authorization。

Gate P2 不要求、也禁止为 pilot 创建或读取 final-test manifest。真实 LLM 仍禁止，除非未来 Phase 7 单独批准；pilot receipt 不能关闭 Gate B。

## 4. Gate B：Formal-experiment execution

Gate B 只有在 Gate A 已通过且以下所有 **EXEC-BLOCKING** 项有可审计证据时才可关闭。任何未完成项都阻止正式 experiment execution，但不阻止已获授权的纯文档 Phase 5B。

### 4.1 建模实现

- [ ] **EXEC-BLOCKING** `objective_model_version` 已命名、批准并写入 schema/manifests。
- [ ] **EXEC-BLOCKING** instance/config 已加入 independent `travel_speed`，且不默认等于 sweep speed。
- [ ] **EXEC-BLOCKING** 三类 travel transition 已实现 `Manhattan distance / travel_speed`。
- [ ] **EXEC-BLOCKING** loader/evaluator/lower-bound、README、AGENTS、实例格式与 configs 已同步。
- [ ] **EXEC-BLOCKING** travel-speed 相关 tests 已更新且全部通过。
- [ ] **EXEC-BLOCKING** 旧 prototype 结果、cache、ranking 和 frozen artifacts 已隔离，不与 formal objective 混用。

当前证据：建模决策已批准，但代码仍为内部 `length/speed + turn`、外部 raw Manhattan distance；现有 `speed=1` 只支持 prototype smoke。`travel_speed=sweep_speed` 仅为 sensitivity，不是正式主口径。

### 4.2 实例协议、generator 与数据

- [ ] **EXEC-BLOCKING** versioned instance generator 或等价 manifest-driven instance flow 已实现并验证。
- [ ] **EXEC-BLOCKING** complete formal family matrix、robots/tasks、distributions、distinct-family floors、replicates、seeds 与 exclusion/replacement rules 已在任何 formal instance 生成前冻结。
- [ ] **EXEC-BLOCKING** formal family→split assignment 在任何 formal instance 生成前冻结，formal-scope `family_matrix_hash` 与 `split_assignment_rule_hash` 已记录。
- [ ] **EXEC-BLOCKING** train/dev/final-test manifests 已冻结且 family/instance IDs 两两不相交。
- [ ] **EXEC-BLOCKING** 三份 formal manifests 均使用 formal scope/new formal identity，`artifact_promotion_allowed=false`，且不含 pilot IDs/hashes/paths/file identities/generation identities。
- [ ] **EXEC-BLOCKING** 已达到 distinct-family minimum；当前两个 smoke 实例不能满足此项。
- [ ] **EXEC-BLOCKING** family/instance/file hashes 和数据生成报告已归档。

### 4.3 Final-test lockbox

- [ ] **EXEC-BLOCKING** final-test manifest 已创建、冻结并记录 manifest SHA-256。
- [ ] **EXEC-BLOCKING** manifest 包含 objective/generator/schema/code/config、family matrix/split rule、instance/file hashes、seeds、统计与 exclusions。
- [ ] **EXEC-BLOCKING** portfolio/operator/prompt/model/budget/selector/statistical plan 已在打开前冻结。
- [ ] **EXEC-BLOCKING** final-test 不向 LLM、prompt、generation、feedback、selection、portfolio、model choice 或 tuning 暴露。
- [ ] **EXEC-BLOCKING** adaptive selector 仅限单 run 内，跨 instance/seed/evolution run/test file 强制重置。
- [ ] **EXEC-BLOCKING** `contamination_owner`、基础设施重试与新 lockbox version 规则已有执行和审计证据。
- [ ] **EXEC-BLOCKING** 在任何 formal prompt/operator generation、formal train/dev evaluation、formal portfolio selection 或 final-test run 前，三份 formal manifests 已通过 joint preflight 与 pilot-artifact exclusion check，并生成 immutable receipt/hash；Phase 6A pilot receipt 不得替代。

### 4.4 Runner、default glob 与 smoke closure

- [ ] **EXEC-BLOCKING** formal runner 只接受 frozen manifest allowlist，不再使用不受控 glob。
- [ ] **EXEC-BLOCKING** default config 不会自动把 final-test 纳入 generation/dev benchmark。
- [ ] **EXEC-BLOCKING** formal preflight 联合加载 train/dev/final-test manifests，验证 exact input set、file hashes/canonical paths/file identity、family/instance/generation identity、split/lockbox status、manifest hashes 与 pilot-artifact exclusion receipt，并生成绑定三份 manifests 的 receipt。
- [ ] **EXEC-BLOCKING** unsupported hardlink/file-identity check 对 formal execution fail closed；若使用豁免，须在 lockbox opening 前预注册 stronger controls、data-root snapshot 与 exemption hash。
- [ ] **EXEC-BLOCKING** tests 证明 final-test 文件即使匹配 `data/R*_T*_*.txt` 也不会被 formal run 读取。
- [ ] **EXEC-BLOCKING** output manifest 记录实际输入清单、split manifest hash、family matrix hash 与 split rule hash。
- [ ] **EXEC-BLOCKING** mock/file provider 的最小闭环在正式 manifests 上通过且没有 fallback/invalid attribution 污染。

当前规避方案只完成文档设计，尚未实现；因此 Gate B 保持关闭。

### 4.5 重复、统计与研究有效性

- [ ] **EXEC-BLOCKING** 每个 generated condition 的 independent evolution-run repetitions 已由 precision/power 方案批准并冻结。
- [ ] **EXEC-BLOCKING** per-family replicates、benchmark seeds、solver seeds 及嵌套关系已冻结。
- [ ] **EXEC-BLOCKING** H1 primary、H6/H3 gatekeeping、多重比较、family-level bootstrap/cluster analysis 已进入预注册分析脚本。
- [ ] **EXEC-BLOCKING** candidate/round/raw trial 不会被当作独立重复；replicate 不会替代 distinct family。
- [ ] **EXEC-BLOCKING** quality/cost estimands、failure denominators 与 missing/invalid/timeout/fallback 处理已冻结。
- [ ] **EXEC-BLOCKING** localized result-artifact failure 与 batch input/manifest/lockbox contamination taxonomy 已在 analysis implementation 中互斥；baseline pairing missing 按 batch inconclusive，而非 failure-zero。
- [ ] **EXEC-BLOCKING** 最新 independent review 没有开放的 Critical 或 Required findings。

### 4.6 Real LLM 与 generated-code 边界

- [ ] **REAL-LLM-BLOCKING** 如需运行真实 LLM，必须另行通过 Phase 7 preflight、显式运行时授权和人工风险确认。
- [ ] **REAL-LLM-BLOCKING** 当前 `timeout_only` subprocess 的 CPU、内存、文件系统、网络、环境变量和后代进程树风险已接受或由更强隔离解决。
- [ ] **EXEC-BLOCKING** generated frozen deployment 的 runtime authorization/provenance evidence 已归档。
- [ ] **EXEC-BLOCKING** fallback、invalid、timeout、blocked 与 unsafe candidates 不会污染 success、reward、selection、freeze 或 feedback。

Phase 4G 测试通过不等于 capability sandbox 已实现，也不自动授权真实 LLM。

## 5. 已登记的后续工作与 Consider

- [x] `task_plan.md` 已记录 speed/travel 口径的未来代码、测试、文档与结果迁移任务。
- [x] `task_plan.md` 已记录 instance generator、family manifests、default-glob formal gate 与 lockbox 任务。
- [x] `findings.md` 已记录当前成本事实、两个实例限制和 glob 风险。
- [x] `progress.md` 将记录本轮只完成文档协议，不会把未实现 gate 写成完成。
- [x] Manifest 规划包含 `family_matrix_hash`、`split_assignment_rule_hash` 与 `contamination_owner`。
- [x] **Consider documentation：** Phase 5B reproducibility/experiment protocol 已要求 provider 时间块、精确模型版本和 portfolio dev stability；执行值仍须在 Gate B/Phase 7 前冻结。
- [x] **Consider documentation：** Phase 5B 将 train/dev 每 family 10 replicates、final-test 每 family 20 replicates 设为 planning minimum，并将 20 个 independent evolution runs 设为 confirmatory target；最终执行数量仍须由 train/dev-only precision/power plan 冻结，本文档化不构成 Gate B 证据。

## 6. Gate 判定

Gate A、Gate P1、Gate P2 与 Gate B 独立判定：

- Gate A 任一 `DOC-BLOCKING` 未完成：不得进入 Phase 5B；
- Gate A 全部完成并通过 documentation-entry review：只允许 Phase 5B 文档工作；
- Gate P1 通过且另行授权：只允许进入 Phase 6A mock/file closed-loop planning；不得执行 pilot、生成实例或创建/读取 final-test；
- Gate P2 通过且另行授权：只允许执行 `pilot_nonformal` smoke/train-dev mock/file pilot；不得创建/读取 final-test，也不得形成或提升为 formal evidence；
- Gate B 任一 `EXEC-BLOCKING` 未完成：不得运行正式实验；
- 真实 LLM 还必须额外关闭所有 `REAL-LLM-BLOCKING`，Gate B 通过本身不构成真实 LLM 授权。

本轮当前允许的工作仅包括：

- Phase 5B 研究问题、实验协议、消融、统计、manifest、复现、结果表和 pilot 文档的创建、审查与冻结；
- 文档审查/批准；
- 在后续明确授权下实现建模、generator、manifest 和 formal-runner 任务。

当前不允许进入 Phase 6A、运行 smoke/pilot、调用真实 LLM、执行正式 operator evolution、访问 final-test 或运行大规模实验。Gate A 的通过不得用作关闭 Gate P1/P2、任何 `EXEC-BLOCKING` 或 `REAL-LLM-BLOCKING` 的证据。
