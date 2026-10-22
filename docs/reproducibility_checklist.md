# Reproducibility Checklist

## 1. 使用方法与状态

- **状态：** Phase 5B documentation checklist；下列项目尚未因本文档创建而完成。
- 每个 pilot、evolution run、frozen deployment 和 result batch 都必须保存 machine-readable evidence；没有 evidence 的项目不能靠叙述性 notes 补齐。
- Final-test 前冻结 checklist version 与负责人员；所有偏差、重试、失败和污染必须保留。

## 2. Code、Environment 与 Objective

- [ ] Code commit hash；若无 Git，保存完整 file snapshot/archive hash 与逐文件 hash manifest。
- [ ] Python、OS、CPU/内存、依赖 lockfile/environment snapshot。
- [ ] `objective_version`；formal 只能是 `objective_v2_formal`。
- [ ] `travel_speed`、`sweep_speed`、turning time 和单位说明。
- [ ] Config canonical hash 与所有 CLI/runtime overrides。
- [ ] Pilot 与 formal manifest IDs/hashes 分开记录；不得把 pilot manifest hash 作为 formal evidence。
- [ ] Manifest schema version、canonical serialization version、manifest hash algorithm 与 validation result。
- [ ] Pilot-only matrix/rule 与 `pilot_family_matrix_hash`/`pilot_split_assignment_rule_hash`；complete formal matrix/rule 与各自 formal-scope hashes，分开记录且不可互换。
- [ ] Generator/schema version 与 code hash。

## 3. Data、Split 与 Lockbox

- [ ] **Pilot lifecycle（仅 Phase 6A scope）：** 在任何 pilot instance 生成前冻结 pilot-only matrix/rule；只加载 `manifest_scope=pilot_nonformal`、`matrix_scope=pilot`、`artifact_promotion_allowed=false` 的获准 smoke/train/dev manifests；未创建、读取、hash 或记录 final-test manifest/files/family matrix/assignment；pilot receipt 不能升级为 formal evidence。
- [ ] Pilot preflight 覆盖 pilot-scoped matrix/rule hashes、schema/path、duplicate exact file、family overlap、generation identity、split mismatch 与 exact allowlist；unsupported file identity 只允许 warning + non-formal 标记。
- [ ] Pilot-artifact exclusion receipt 保存 pilot family/instance IDs、file hashes、canonical paths、file identities、generation identities、manifest/matrix/rule hashes；formal preflight 对该集合 fail closed。
- [ ] Pilot artifacts 未被重标、复制、链接或复用为 formal artifacts；formal identity version 与 pilot identity domain 分离。
- [ ] **Formal lifecycle：** complete formal matrix/rule 在任何 formal instance 生成前冻结；随后才生成三类 formal instances/manifests。以下 three-manifest checks 只用于 formal lockbox；其 receipt 必须早于 formal prompt/operator generation、formal train/dev evaluation、formal portfolio selection 和 final-test run。
- [ ] 每个 instance 的 canonical `instance_id`、family ID、replicate ID、integer generation seed、normalized file path/hash。
- [ ] Duplicate ID/path/file hash、path alias/symlink/traversal validation evidence；任何命中均 fail closed。
- [ ] Family/instance IDs 在 train/dev/final-test 间不相交。
- [ ] Train/dev/final-test 三份 manifests 已由 lockbox-aware joint preflight 同时加载；receipt/hash 绑定三个 manifest hashes 和 preflight policy version。
- [ ] 三份 manifests 分别为 `formal_train`、`formal_dev`、`formal_final_test`，共享 formal matrix/rule hashes 和 formal identity version；formal runner 拒绝 `pilot_nonformal`。
- [ ] Merged-record evidence 覆盖 duplicate `instance_id`、跨 split `file_hash`、canonical resolved path、file identity/hardlink、family ID、generation identity、split/lockbox mismatch 与 final-test cross-membership。
- [ ] Joint preflight 的 derived identity view 包含 generation rule/seed、full family parameter tuple、canonical resolved path 和 lockbox status；不同 IDs 不得豁免 duplicate bytes/path。
- [ ] `file_identity_check_status`、platform/filesystem identity 与 hardlink detection evidence；若 unsupported，formal final-test 有预注册 stronger-control exemption，否则 fail closed。
- [ ] Formal joint-preflight pass/hash 早于任何 formal prompt/operator generation、formal train/dev evaluation、formal portfolio selection 或 final-test run；下游仅收到 receipt，不收到 final-test records。
- [ ] Formal joint-preflight receipt 绑定 pilot-artifact exclusion receipt/hash；任一 pilot ID/hash/path/file identity/generation identity 命中均 fail closed。
- [ ] Current two R2 files 只存在于 smoke/demo manifest。
- [ ] Formal runner actual input set 与 manifest allowlist 完全相等。
- [ ] Final-test lockbox status、manifest hash、approval/opening events。
- [ ] `contamination_owner`、contamination audit 与 exclusion/replacement records。
- [ ] Adaptive selector 跨 instance/seed/evolution-run/test-file 重置证据。

## 4. Method、Prompt 与 Provider

- [ ] Method condition ID、baseline/ablation definition 与 implementation hash。
- [ ] Prompt version、template hash、rendered prompt hash 和 feedback payload hash。
- [ ] Model/provider/endpoint 的精确标识与 claimed/runtime distinction。
- [ ] Temperature、sampling parameters、context/token limits。
- [ ] Retry policy、infrastructure-failure definition 与实际 retries。
- [ ] Provider 调用时间块和 method-order randomization/blocking。
- [ ] Input/output token counts、LLM call count、provider latency 与价格版本。
- [ ] Explicit runtime authorization、risk acknowledgement 与 authorization source（如适用）。

## 5. Candidate 与 Execution Boundary

- [ ] Candidate ID、operator type、source/code hash、parent lineage 和 evolution round。
- [ ] AST/static validation status 与 rule version。
- [ ] Executor identity、trusted/effective sandbox level 和 claimed sandbox metadata。
- [ ] Timeout policy、timeout budget、exit code、stdout/stderr truncation status。
- [ ] Eligibility、execution、feasibility、optimization、structural statuses。
- [ ] Fallback used/reason、invalid subtype、blocked/source-read/runtime/timeout reason。
- [ ] Candidate runtime、subprocess startup/overhead、wall time 分开记录。
- [ ] Expected hash/revalidation evidence for every path/frozen execution。
- [ ] Generated operator success/reward 不包含 fallback 或 attribution-ambiguous trials。

## 6. Evolution Run 与 Selection/Freezing

- [ ] 每个 planned run 在 generation 前分配 immutable `scheduled_run_id`，并保留 method condition/block assignment。
- [ ] Independent evolution-run ID 与 seed。
- [ ] Candidate/round/call/token/evaluation budgets。
- [ ] Train/dev access manifest 与 benchmark/solver seed lists。
- [ ] Leaderboard、eligible pool、elite retention 和 feedback records。
- [ ] Selection/freezing 使用完整 fail-closed evidence；no-valid/not-evolved 状态分开。
- [ ] 每个 scheduled run 的互斥 primary status、failure subtype、deployment/valid-portfolio/evaluable indicators。
- [ ] Frozen operator/portfolio member hashes、registry/manifest hash。
- [ ] Portfolio size、behavior descriptors、dedup/correlation objective 与 dev composition stability。
- [ ] Selector algorithm、initial weights、update/reset rules 与 usage trajectory。

## 7. Solver Evaluation

- [ ] Instance family/replicate 与 solver seed。
- [ ] ALNS iterations/time budget、local-search budget、acceptance/selector config。
- [ ] Initial/final makespan、route costs、relative baseline gap 和 time-to-target。
- [ ] Operator usage/reward 与 generated operator attribution。
- [ ] Runtime decomposition：candidate runtime、subprocess overhead、benchmark/DP/ALNS/end-to-end wall time。
- [ ] Invalid、timeout、fallback、blocked 与 infrastructure failure 全量记录。
- [ ] Baseline pairing block 与 strongest non-LLM selection provenance。

## 8. Statistics 与 Results

- [ ] Independent evolution-run repetitions 和 distinct family counts。
- [ ] Analysis population 明确为 all scheduled independent evolution runs，scheduled-run accounting 与 Table 0 一致。
- [ ] Per-family replicates、benchmark/solver seed counts。
- [ ] 完整预注册 cell grid：`evolution_run × method_condition × final_test_family × instance_replicate × solver_seed`，每个 cell 有互斥 primary status 和 analysis value。
- [ ] Primary estimand、`δ_MCID`、aggregation、CI/bootstrap/model 和 multiplicity version。
- [ ] H1a CI lower > 0 与 H1b CI lower > 0.02 分开判定；不得用 point estimate + lower > 0 替代 H1b。
- [ ] Localized timeout/invalid/fallback/blocked/missing/error/no-attribution cells 使用 `delta_rcfis=0`；cell、family、run 层均不 complete-case 删除，whole-run method failure 是全 cells 为 0 的退化情形。
- [ ] Objective/input/manifest/split/lockbox integrity failure 与 baseline pairing missing 不使用 failure-zero：分别标 batch contaminated/inconclusive，排除 primary effect estimate但保留 scheduled/integrity accounting。
- [ ] Cell failure、fully attributable family、run-level deployable portfolio、fallback、attributed generated success 的 counts/rates 与固定分母。
- [ ] Fallback baseline result 不归因于 generated improvement；failure/deployment rates、two-part endpoint 和 dominated sensitivity 与主结果并列。
- [ ] H1a→H6→H3 gatekeeping status；其它 hypotheses 标 secondary/exploratory。
- [ ] 若 H2 arms 共用 evolution seed/provider time block，Phase 6/7 前已预注册 paired-block IDs、缺 block 规则和 paired-block bootstrap；否则明确使用非配对 clustered analysis。
- [ ] Scheduled/executed/valid/evaluable denominators。
- [ ] Missingness、retry、fallback、timeout、invalid 和 contamination handling。
- [ ] Raw result manifest、analysis script hash、table-generation script hash。
- [ ] Positive、negative、null 和 inconclusive outcomes 均保留。

## 9. Cost Accounting

- [ ] Provider calls、tokens、latency、currency/price timestamp。
- [ ] Candidate validation/execution/benchmark compute。
- [ ] Solver and local-search runtime、hardware utilization assumptions。
- [ ] Failed/blocked/timeout candidate cost 纳入主成本分析。
- [ ] Reuse/deployment count 与 amortization horizon。
- [ ] Quality-constrained、cost-constrained 和 Pareto analysis inputs。
- [ ] Break-even 若报告，具有预注册 utility/willingness-to-pay；否则只作 sensitivity。

## 10. Release 与审计

- [ ] Immutable manifests、raw logs、frozen sources 和 analysis artifacts 可追溯。
- [ ] Secrets/API keys 不进入 snapshots、prompts、logs 或 release bundle。
- [ ] Provider metadata 不被描述为不可伪造 provenance receipt。
- [ ] 当前 boundary 明确记录为 timeout-only，不宣称 capability sandbox。
- [ ] Final-test 公开时点晚于 method freeze 和完整 batch。
- [ ] Deviations、contamination、excluded runs 和 known limitations 随论文发布。

## 11. Phase Gates

- [ ] Gate B 全部 EXEC-BLOCKING 有可审计证据。
- [ ] 最新 protocol/code review 无 Critical/Required。
- [ ] 真实 LLM 如需执行，Phase 7 preflight、runtime authorization 和风险确认另行通过。
- [ ] Final-test opening 另行批准；Phase 5B 文档完成本身不勾选本节任何项。
