# Manifest Specification

## 1. 状态与适用范围

- **状态：** Phase 5B schema specification；尚未实现 parser/runner，也未创建 formal manifests。
- Formal experiment 的 instance input、evolution run、frozen operator/portfolio 和 result batch 必须由 versioned manifest 绑定。
- Runner 必须 **manifest-only**；wildcard/glob 不能作为正式输入权威。
- Smoke/demo manifests 与 formal manifests 必须分开，`objective_v1_prototype` 记录不得进入 `objective_v2_formal` 分析。
- Final-test manifest 是 lockbox artifact；创建、冻结、打开和污染状态受 `final_test_lockbox_protocol.md` 约束。

## 2. Manifest Types

| Type | 建议文件 | 作用 |
|---|---|---|
| Pilot family matrix | `pilot_family_matrix_<id>.json` | 只冻结 pilot-only families、non-final strata 与 pilot split rule |
| Formal family matrix | `formal_family_matrix_vN.json` | 在任何 formal instance 生成前冻结 complete formal train/dev/final-test definitions 与 split rule |
| Pilot split manifest | `pilot_train_manifest_<id>.json`, `pilot_dev_manifest_<id>.json`, `smoke_manifest_vN.json` | `manifest_scope=pilot_nonformal` 的 exact allowlist；永久 non-formal |
| Formal split manifest | `train_manifest_vN.json`, `dev_manifest_vN.json`, `final_test_manifest_vN.json` | `formal_train|formal_dev|formal_final_test` 的 exact allowlist |
| Pilot preflight | `pilot_preflight_<id>.json` | 只绑定 smoke/train/dev scoped manifests；不得包含或读取 final-test identity/content |
| Pilot-artifact exclusion receipt | `pilot_artifact_exclusion_<id>.json` | Pilot 结束时冻结 IDs/hashes/paths/file identities/generation identities，供 formal preflight 作 denylist；无 pilot 时保存显式 empty receipt |
| Joint split preflight | `joint_split_preflight_<id>.json` | 绑定三个 split manifest hashes，记录 merged-record checks、平台能力、豁免与 preflight hash |
| Evolution run | `evolution_run_<id>.json` | Provider/prompt/budget/seeds/rounds/output lineage |
| Frozen set | `operator_manifest_<id>.json`, `portfolio_manifest_<id>.json` | Code hashes、eligibility evidence、composition、selector policy |
| Result batch | `result_manifest_<id>.json` | Actual input set、conditions、raw outputs、status 与 hashes |
| Smoke/demo | `smoke_manifest_vN.json` | 当前两个 R2 文件的接口检查；永不升级为 formal manifest |

## 3. Split-Manifest Required Fields

Split manifest 是 UTF-8 JSON object，包含一个严格 header 和一个 `instances` array。下表字段对每个 instance record 均为必需；`additionalProperties=false`。字段不得以 string/number、string/list 等 union 类型表达。

| Field | Type / format | Contract |
|---|---|---|
| `manifest_version` | non-empty string | Schema/version identifier；修改创建新版本 |
| `manifest_scope` | enum string | `pilot_nonformal`, `formal_train`, `formal_dev`, `formal_final_test`；决定唯一 schema branch，禁止跨 branch coercion |
| `matrix_scope` | enum string | `pilot` 或 `formal`；必须与 `manifest_scope` 匹配 |
| `objective_version` | enum string | `objective_v1_prototype` 或 `objective_v2_formal`；formal 只能为 v2 |
| `instance_id` | lowercase SHA-256 hex string | Instance record 的 canonical unique key；manifest 内及跨 splits 不得重复 |
| `family_id` | string | 由 canonical family definition hash 派生 |
| `split` | enum string | `smoke`, `train`, `dev`, `final_test`；同 family 只能一个 split |
| `size_stratum` | enum string | `small`, `medium`, `large`, `stress_generalization` |
| `distribution_stratum` | non-empty string | 例如 D1/D2/D3；引用冻结参数对象 |
| `robots` | positive integer | Robot count |
| `tasks` | positive integer | Task count |
| `sweep_width` | finite positive number | Distance unit 与 schema 绑定 |
| `sweep_speed` | finite positive number | Distance/time |
| `travel_speed` | finite positive number | 独立参数；formal 不得缺失或隐式取 sweep speed |
| `turning_time` | finite non-negative number | 与 objective 时间单位一致 |
| `generation_rule_version` | non-empty string | Generator algorithm/schema version |
| `generation_seed` | integer | 可重放的 instance seed；不得用 numeric string |
| `replicate_id` | non-negative integer | Family 内唯一、连续；不是 solver seed |
| `file_path` | normalized relative path | 必须位于批准 data root；不得 wildcard |
| `file_hash` | SHA-256 hex | 对 exact bytes 计算；final-test 冻结后不可改变 |
| `family_matrix_hash` | SHA-256 hex | Scope-aware canonical field：`matrix_scope=pilot` 时绑定完整 pilot-only matrix，并在 pilot receipt/audit 中以 `pilot_family_matrix_hash` 同值暴露；`matrix_scope=formal` 时绑定 complete formal train/dev/final-test matrix。只有 formal branch 可称为 full formal matrix hash |
| `split_assignment_rule_hash` | SHA-256 hex | Scope-aware canonical field：pilot branch 绑定 pilot-only split rule，并在 pilot receipt/audit 中以 `pilot_split_assignment_rule_hash` 同值暴露；formal branch 绑定任何 formal instance 生成前冻结的 formal split rule |
| `artifact_promotion_allowed` | boolean literal | 必须严格为 `false`；缺失、`true` 或非 bool 均 fail closed |
| `formal_identity_version` | string | Pilot branch 固定为 `not_applicable`；formal branch 为冻结的非空 identity version，并进入 family/instance identity derivation |
| `pilot_source_reference` | discriminator-fixed | Formal branches 必须为 JSON `null`；pilot root manifest 为 JSON `null`。若未来定义 derived pilot schema，须新 schema version，不得在当前 schema 使用 string/null truthiness |
| `contamination_owner` | non-empty string | 负责泄漏判断与处置的 actor ID |
| `lockbox_status` | enum string | `not_applicable`, `draft`, `assignment_frozen`, `frozen`, `opened`, `reported`, `contaminated` |
| `created_at` | string | ISO-8601 UTC，格式 `YYYY-MM-DDTHH:MM:SSZ`；不可用于方法排序 |
| `approved_by` | non-empty string | 单一审批 actor ID；附加审批写入 header `audit_history` objects |
| `notes` | string | 审计说明；无内容用空字符串，不能覆盖结构化字段 |

### 3.1 Instance identity 与 duplicate contract

`instance_id` 固定为以下 object 经第 5 节 canonical serialization 后的 SHA-256。Identity object 显式包含 scope，因此 pilot identity 不可能通过重标字段成为 formal identity：

```json
{
  "family_id": "<family_id>",
  "file_hash": "<file_hash>",
  "manifest_scope": "formal_train",
  "formal_identity_version": "formal_identity_v1",
  "generation_seed": 0,
  "objective_version": "objective_v2_formal",
  "replicate_id": 0
}
```

Pilot branch 使用 `manifest_scope="pilot_nonformal"` 与 `formal_identity_version="not_applicable"`；formal branch 使用对应 formal scope/version。该 object 的字段集合固定，不包含 `file_path`。Runner 必须同时验证：

- `instance_id` 在 manifest 内唯一，在 train/dev/final-test manifests 之间两两不相交；
- `(family_id, replicate_id)` 在一个 split 内唯一；
- 同一 `instance_id` 只对应一个 `file_path` 和一个 `file_hash`；
- 同一 normalized/resolved `file_path` 只对应一个 `instance_id`；
- 任意重复 `file_hash` 标记 `duplicate_file` 并使整个 formal manifest validation fail closed；不得静默 deduplicate、保留第一条或跳过重复记录。
- Pilot `family_id` 由 `{matrix_scope:"pilot", pilot matrix definition, generator identity}` 派生；formal `family_id` 由 `{matrix_scope:"formal", formal_identity_version, formal matrix definition, generator identity}` 派生。两者不得相等或直接复用；即使参数相同，formal 也必须重新生成并取得新的 formal identity。

`instance_id`、path 或 hash 映射的任何冲突都使 manifest 无效；不能用记录顺序解决冲突。

### 3.2 Required family-definition extension

为使 `family_id` 可验证，family matrix 还必须包含：rectangle-size distribution 及参数、spatial distribution/workspace/overlap policy、depot rule、distance metric、speed/turn burden parameters、generator name/version/code hash、objective version 和全部 fixed generation parameters。

Formal joint preflight 必须为每条 record 取得或确定性派生以下完整 identity view；pilot preflight 对其 supplied non-final records 使用同一字段合同：`manifest_scope`、`matrix_scope`、`formal_identity_version`、`instance_id`、`family_id`、`split`、`file_hash`、运行时计算的 `canonical_resolved_path`、运行时 file identity、`generation_rule_version`、`generation_seed`、`generation_identity_hash`、完整 family parameter tuple、`artifact_promotion_allowed` 和 `lockbox_status`。完整 family parameter tuple 至少包含 robots、tasks、rectangle-size distribution 及参数、spatial distribution/workspace/overlap policy、sweep_width、travel_speed、sweep_speed、turning_time、depot/distance rules、objective version、generation rule version 和所有 fixed generation parameters；不得用 `family_id` 字符串替代 tuple 验证。

### 3.3 Scope compatibility 与 promotion prohibition

| `manifest_scope` | Required `matrix_scope` | Allowed record `split` | Promotion/consumer contract |
|---|---|---|---|
| `pilot_nonformal` | `pilot` | `smoke`, `train`, `dev` | 只能由 pilot runner/preflight 使用；永久 non-formal |
| `formal_train` | `formal` | `train` | 只能由 formal runner 使用 |
| `formal_dev` | `formal` | `dev` | 只能由 formal runner 使用 |
| `formal_final_test` | `formal` | `final_test` | 只能由 formal runner + opening authorization 使用 |

- Pilot instances/manifests 不得直接提升、重标、复制或链接为 formal train/dev/final-test artifacts；pilot manifests 不得通过改 header 变成 formal manifests。
- Pilot family IDs 默认不得用于 formal。唯一允许的概念级复用是：formal protocol 在不读取 final-test performance 的前提下重新声明参数、重新生成 bytes，并用新 `formal_identity_version` 派生不同的 formal family/instance identities；任何相同 pilot file hash、path、file identity 或 generation identity 仍必须拒绝。
- `artifact_promotion_allowed=false` 是 invariant，不是授权开关；未来 schema 不得把它改成 runtime opt-in。
- Pilot 与 formal schema 由 `manifest_scope` 判别。每个 branch 内字段类型唯一；不得在未先验证 discriminator 时接受 union/coercion。

### 3.4 Required header fields 与 JSON types

- `manifest_type`: enum string；
- `schema_version`, `manifest_version`, `manifest_id`: non-empty string；
- `manifest_scope`, `matrix_scope`, `artifact_promotion_allowed`, `formal_identity_version`, `pilot_source_reference`: 与第 3/3.3 节 branch contract 完全一致；
- `manifest_hash`: lowercase SHA-256 hex string；
- `instance_count`, `family_count`: non-negative integer；
- `strata_counts`: object whose values are non-negative integers；
- `exclusion_rule_version`, `replacement_seed_rule_version`: non-empty string；
- `generator_code_hash`, `instance_schema_version`: non-empty string；hash 字段须为 lowercase SHA-256 hex；
- `family_matrix_hash`, `split_assignment_rule_hash`: lowercase SHA-256 hex string，按 `matrix_scope` 重新计算并验证；
- `parent_manifest_hash`: string；root manifest 使用空字符串，derived manifest 使用 lowercase SHA-256 hex；
- `contamination_status`: enum string；
- `audit_history`: array of fixed-shape objects `{event_id:string, actor_id:string, action:string, created_at:string}`；
- `instances`: array of第 3 节 fixed-shape objects。

Header 同样 `additionalProperties=false`。除当前 discriminator branch 明确要求 `pilot_source_reference=null` 外，`null`、numeric string、NaN、Infinity、comments、trailing commas 和 schema 未声明字段均拒绝。Header 与每条 record 的 scope/identity fields 必须完全一致。

## 4. Evolution/Operator/Portfolio Fields

Evolution run manifest 至少记录：

- method condition、independent `evolution_run_id`/seed；
- train/dev manifest IDs/hashes；不得包含 final-test paths/content；
- provider/model/endpoint、temperature、retry policy、time block；
- prompt version/hash、rounds、candidate/call/token/information/evaluation budgets；
- candidate IDs、code hashes、lineage、validation/execution/feasibility/failure statuses；
- executor identity、effective sandbox level、timeout policy、runtime authorization evidence；
- leaderboard/elite/freeze outputs 与 failure feedback hashes；
- calls/tokens/provider latency/candidate runtime/benchmark compute；
- fallback/invalid/timeout/blocked attribution 与 contamination status。

Artifact 中的 provider、sandbox、safety 字符串只能作为 claimed metadata；部署授权必须来自当前 runtime policy，不由 artifact 自证。

Frozen operator/portfolio manifest 还必须记录：

- operator type、source snapshot/path、expected code hash；
- complete eligibility/failure-rate evidence；
- candidate/evolution-run lineage；
- portfolio members、fixed `k`、selection objective/descriptor versions；
- selector algorithm、initial weights、update/reset policy；
- composition/freeze approval、registry hash；
- deployment authorization status 和 fallback policy。

## 5. Canonicalization 与 Hashing

- 所有 JSON artifacts 使用 UTF-8 **without BOM**，并按 RFC 8785 JSON Canonicalization Scheme（JCS）生成 canonical bytes：object keys lexicographically sorted、规定的 JSON number/string encoding、无 insignificant whitespace、无 comments/trailing commas；
- 在 canonicalization 前，所有 `file_path` 将 `\\` 转为 `/`，移除 `.` segment；包含空 segment、`..`、drive/UNC prefix、absolute prefix 或 wildcard 的 path 直接拒绝，不做猜测式修复；
- `instances` array 按 `instance_id` 升序排列；`audit_history` 按 `(created_at,event_id)` 升序排列；其他 array 的排序语义由各 schema 固定。输入未按 canonical order 时 validation fail closed；
- `manifest_hash` 固定计算方式：复制完整 manifest，将 header `manifest_hash` 设置为 64 个小写 `0`，对该 object 的 RFC 8785 canonical UTF-8 bytes 计算 SHA-256；禁止选择性排除其他字段；
- `family_matrix_hash` 固定使用相同规则：family-matrix artifact 的 `family_matrix_hash` 字段置为 64 个小写 `0` 后 canonicalize 并 SHA-256；
- `split_assignment_rule_hash` 固定对 versioned split-rule JSON artifact 的 `split_assignment_rule_hash` 字段置为 64 个小写 `0` 后 canonicalize 并 SHA-256；
- Data `file_hash` 直接对文件 exact bytes 计算 SHA-256，不做换行或编码归一化；

### 5.1 Manifest artifact 与 PIV-04 receipt 的 hash domain

- 本文第 3/5 节的 header `manifest_hash` 是 **manifest artifact self-hash**：按上一节固定的 zeroed-field canonical-object 规则计算。它属于 artifact-header domain。
- PIV-04 validation receipt 中同名的 `manifest_hash` 具有不同且唯一的 receipt 语义：`SHA-256(raw_manifest_bytes)`。receipt builder 必须从调用方显式传入的 bytes 重新计算，禁止直接复制 artifact header 的 `manifest_hash`。
- receipt `raw_manifest_bytes_hash` 如出现，必须等于 receipt `manifest_hash`，仅用于显式标注 raw-byte domain。
- receipt `manifest_object_hash` 是对解析所得完整 `manifest_obj` 按已绑定 canonicalization algorithm/version 计算的 object-domain hash；它不等于也不替代 artifact-header self-hash。
- 禁止把 canonical/object/artifact-header hash 写入 receipt `manifest_hash`，也禁止把 raw-byte digest 写入 `manifest_object_hash`。跨 domain 相等即使偶然发生，也不能替代分别重算与字段绑定。
- 所有 digest 使用 lowercase 64-character hex，并在 schema 中固定算法 `sha256`；
- 禁止绝对机器特定路径进入 family hash；`file_path` 使用 normalized project/data-root relative path；
- `created_at`、approval/audit events 不进入 family ID，但进入 manifest hash；
- 任何 field、record、file 或 assignment 变化都创建新 manifest/version/hash，不覆盖冻结 artifact；
- Parser 必须在 hash verification 前完成 strict type/shape validation，随后按上述唯一算法重算所有 hashes；任何差异 fail closed。

### 5.1 Path safety 与 alias rejection

- `file_path` 必须是 approved experiment data root 下的 normalized relative path；不得是 absolute、UNC、drive-qualified、URI、wildcard 或 parent traversal path；
- Runner 以不跟随 symlink/reparse-point 的方式逐段检查路径；路径本身或任一 ancestor 是 symlink/reparse point 时拒绝；
- Resolve/canonicalize 后的 target 必须仍位于 approved data root 内；大小写、短文件名、hardlink 或其他 path alias 导致两个 records 指向同一底层文件时拒绝；
- 同一 resolved path 不得由多个 lexical paths 引用；
- Missing/unreadable file、root escape、alias、symlink、file-size change 或 `file_hash` mismatch 均使整个 formal input validation fail closed。

## 6. Manifest-Only Runner Contracts

### 6.1 Train/dev pilot runner

Phase 6A mock/file closed-loop 与 train/dev-only pilot 只接受显式 smoke/train/dev manifest allowlists：

1. runner config 必须显式声明 `pilot_mode=true`、`active_split=smoke|train|dev` 和所需 pilot manifest paths/hashes；未知字段、glob/wildcard 或路径外输入 fail closed；
2. 每份输入必须为 `manifest_scope=pilot_nonformal`、`matrix_scope=pilot`、`artifact_promotion_allowed=false`，并验证 pilot-only matrix/rule hashes；pilot runner 拒绝 `formal_train`、`formal_dev`、`formal_final_test`，尤其不得把 formal final-test 当作 dev；
3. config/schema 不得接受 `final_test_manifest_path`、formal family-matrix/split-rule hash、final-test record/path/file hash或其派生 feature；发现任一项立即拒绝 pilot；
4. 在读取实例前执行第 7.1 节 pilot preflight，并验证 active-split allowlist、schema/hash/path safety 与 actual input set 完全一致；
5. 输出只记录实际使用的 pilot manifests、pilot family-matrix/rule hashes、pilot-preflight receipt/hash、code/config/operator hashes，并显式标记 `non_formal_pilot=true`；
6. pilot receipt、instances、manifests、IDs、hashes、paths 与 file identities 不能替代、提升或复制为 formal evidence。

### 6.2 Formal runner

Formal runner 必须：

1. 要求显式 `train_manifest_path`、`dev_manifest_path`、`final_test_manifest_path` 和匹配三者 hashes 的 valid joint-preflight receipt；缺任一项即 fail closed；
2. 三份 manifests 必须分别为 `formal_train`、`formal_dev`、`formal_final_test`，且全部为 `matrix_scope=formal`、相同 `formal_identity_version`、complete formal matrix/rule hashes 和 `artifact_promotion_allowed=false`；任何 `pilot_nonformal` 输入即拒绝；
3. 对当前要执行的 split 还必须要求显式 `active_split`，且其 exact allowlist 必须来自上述三份已联合验证 manifests 之一；
4. 验证 fixed schema version、`additionalProperties=false`、所有 required fields/types、objective/status 和全部 hashes；
5. 将 exact allowlist resolve 到批准 data root，按 3.1/5.1 拒绝 duplicate、path alias、symlink、traversal 和 missing files；
6. 在读取任何 instance 前按第 7 节重新验证 joint-preflight receipt、三个 manifest hashes、pilot-artifact exclusion receipt 和 preflight policy version；
7. 验证实际读取集合与 active-split allowlist **完全相等**，多/少一个都拒绝；
8. 禁止 formal mode 调用 `glob`/wildcard 发现额外实例；
9. 输出 actual-input manifest、三个 split manifest hashes、formal matrix/rule hashes、pilot-exclusion receipt/hash、joint-preflight receipt/hash、code/config/operator hashes；
10. final-test 只接受 `manifest_scope=formal_final_test`、`lockbox_status=frozen` 且经显式 opening authorization 的 manifest。

以下任一情况必须使整个 formal run 在读取任何 instance 前 fail closed：missing required field、wrong JSON type、unknown field/status/enum、duplicate ID/path/hash、hash mismatch、split/family overlap、count mismatch、path safety violation、uncontrolled glob/wildcard 或实际输入集合不等于 allowlist。Runner 不得 silently skip、fallback 到旧 schema、fallback 到 glob、自动修复记录或把 validation failure 降级为 warning。

当前默认 `data/R*_T*_*.txt` 只能用于 smoke/demo。即使 final-test 文件匹配该 pattern，formal runner 也不得发现或读取它。

## 7. Two Preflight Lifecycles

### 7.1 Train/dev pilot preflight

Phase 6A mock/file closed-loop 或 train/dev-only pilot 的 preflight 只能联合加载实际获准的 smoke/train/dev manifests；不得创建、定位、读取、hash、推断或记录 final-test manifest、final-test files、final-test family matrix/assignment 或 performance。它必须在任何 pilot input read 前：

- 分别 strict-validate supplied manifests 为 `pilot_nonformal`/`pilot` branch，验证 pilot family-matrix/rule canonical hashes、`artifact_promotion_allowed=false`、objective/status 与 approved-root path safety；
- 在 supplied records 上拒绝 duplicate `instance_id`、`file_hash`、canonical path、file identity、family overlap、generation identity、split mismatch、alias/symlink/hardlink/traversal 和 missing/hash-mismatched files；
- 验证 actual input set 与 active split allowlist 完全一致，禁止 glob/discovery；
- 生成只绑定 supplied pilot manifests/matrix/rule 的 immutable `pilot_preflight_receipt`，记录 scope、policy version、checks、platform/file-identity capability、warning/status 和 receipt hash；receipt 必须显式记录 `pilot_family_matrix_hash=family_matrix_hash` 与 `pilot_split_assignment_rule_hash=split_assignment_rule_hash`，避免将 pilot hash 误称为 full formal matrix/rule hash；
- 在 pilot 结束时生成 immutable pilot-artifact exclusion receipt，至少列出 pilot family/instance IDs、file hashes、canonical paths、可用时的 file identities、generation identities、manifest/matrix/rule hashes。该 receipt 只用于 formal denylist audit，不包含 final-test 信息。

若 file identity 检查不受支持，pilot 可记录 `unsupported_file_identity_check` warning，但必须标为 non-formal，不能形成 formal evidence。Pilot 只支持 runtime/variance/pipeline、manifest-only runner 和 precision/power planning；不能支持 final-test claim、冻结 final-test composition 或关闭 Gate B。

### 7.2 Formal lockbox joint-preflight scope、order 与 isolation

Formal runner 不得只验证单一 split manifest。进入任何 **formal** prompt/operator generation、formal train/dev evaluation、formal portfolio selection 或任何 final-test run 前，lockbox-aware preflight component 必须联合加载 train、dev、final-test 三份 manifests，分别完成 strict schema/hash/path validation，再在合并 records 上执行本节检查。若 preflight 未通过，以上所有操作均 fail closed。

若曾运行 pilot，formal preflight 还必须加载冻结的 pilot-artifact exclusion receipt；若未运行 pilot，必须加载显式 `no_pilot_artifacts` empty receipt。缺 receipt、receipt hash mismatch 或无法证明 denylist completeness 均 fail closed。Formal component 只使用 pilot identity/hash/path denylist，不接收 pilot performance。

该顺序不授权 train/dev、selection 或 LLM 组件查看 final-test 内容。Preflight 必须在隔离的 lockbox boundary 内完成；下游只接收固定 shape 的 pass/fail receipt、三个 manifest hashes、preflight hash 和 contamination status，不接收 final-test paths、family parameters、records 或派生性能/难度信息。

任何一个 manifest、data file、data root、schema、preflight policy 或预注册 exemption 变化都会使 receipt 失效，必须重新 preflight；不得复用旧 pass 状态。Final-test opening authorization 与 joint preflight pass 是两个独立 gate，前者不能替代后者。

### 7.3 Formal merged-record fail-closed checks

联合 records 上必须执行并全部通过：

1. `instance_id` 在三个 splits 的并集内唯一；
2. `file_hash` 在不同 splits 间不得重复；即使 `instance_id` 或 `family_id` 不同也必须以 `duplicate_file_hash_across_splits` 拒绝；
3. `canonical_resolved_path` 在不同 splits 间不得重复；lexical path 不同不能规避；
4. 平台支持时，底层 file identity（例如 device/inode 或 Windows file ID）在不同 splits 间不得重复，以识别 hardlink/alias；
5. 同一 `family_id` 不得出现在多个 splits；
6. 对 canonical `{generation_rule_version, generation_seed, full_family_parameter_tuple}` 计算 `generation_identity_hash`；该 hash 在不同 splits 间重复即拒绝，以阻止相同生成身份/内容换文件名进入多个 splits；
7. 每个 record 的 `split` 必须与所在 manifest/header/active allowlist 一致；
8. train/dev records 的 `lockbox_status` 必须为 `not_applicable`，final-test records 在 formal preflight 时必须为 `frozen`；任何 status/header/audit-history contradiction 均拒绝；
9. final-test record 不得出现在 train/dev，train/dev record 不得出现在 final-test；检查必须基于 ID、hash、resolved path、file identity、family 和 generation identity，而不只看 split 字符串；
10. 任一 path alias、symlink/reparse point、hardlink duplicate、parent traversal、root escape、case/short-name alias 或 unreadable target 均拒绝。
11. 三份 manifests 的 `manifest_scope` 必须分别为 `formal_train`、`formal_dev`、`formal_final_test`，共享同一 `matrix_scope=formal`、formal identity version、complete formal matrix/rule hashes；任何 `pilot_nonformal` row/header 均拒绝；
12. 任一 formal family/instance ID、file hash、canonical path、file identity、generation identity、manifest hash 或 source reference 命中 pilot-artifact exclusion receipt，均以 `pilot_artifact_leakage` 拒绝。改文件名、复制 bytes、hardlink、重标 split 或仅换 manifest header 都不能豁免。

`family_id` 只是一条需要验证的 identity signal，绝不是 duplicate-file exemption。不同 IDs 或文件名不能覆盖相同 `file_hash`、resolved path、file identity 或 generation identity 的 fail-closed 结果。

### 7.4 Unsupported file-identity checks

Joint preflight receipt 必须记录 `file_identity_check_status`（`supported_pass`、`unsupported` 或 `failed`）、platform/filesystem identity、检查实现版本和 error summary。`failed` 始终拒绝。

若当前平台/文件系统不能可靠检测 hardlink/file identity，必须记录 `unsupported_file_identity_check`：

- formal final-test execution 默认 fail closed；
- 只有在 final-test opening 前预注册并冻结的 exemption 才可继续。Exemption 必须绑定三个 manifest hashes、preflight policy/hash、approved data-root snapshot/archive hash，并同时要求跨 split exact-byte `file_hash`、canonical resolved-path、generation-identity checks 通过，且说明为何存储介质/只读解包流程排除了 hardlink alias；
- exemption ID、批准者、理由、stronger controls 证据和 hash 必须进入 receipt 与 result manifest；不得运行时临时批准；
- smoke/demo 可降级为 warning，但必须标 `non_formal_due_to_unsupported_file_identity_check`，不得进入 formal/confirmatory result。

### 7.5 Formal joint-preflight receipt

Receipt 使用 strict JSON schema、`additionalProperties=false` 与第 5 节 canonical serialization。至少记录：schema/policy version、preflight ID/status、train/dev/final-test manifest IDs 与 hashes、`manifest_scope` triplet、`matrix_scope=formal`、formal identity version、complete formal family-matrix/split-rule hashes、pilot-artifact exclusion receipt/hash/status、merged record/family counts、每项 check 的 status、`file_identity_check_status`、exemption ID/hash（无豁免用空字符串）、platform/filesystem identity、data-root snapshot identity、contamination status、audit event 和 `joint_preflight_hash`。只有所有 required checks、pilot leakage checks 通过且 unsupported case 具有有效预注册 exemption 时，formal status 才能为 `pass`。

Receipt/hash 必须在首次 formal prompt/operator generation、formal train/dev evaluation、formal portfolio selection 或 final-test run 前写入 immutable audit log。任何顺序违反标记 contamination；不得事后补 receipt 将既有结果升级为 formal evidence。Phase 6A pilot receipt 不满足本条。

## 8. Final-Test Lockbox Rules

- Complete formal family matrix、formal final-test assignment、`family_matrix_hash` 和 `split_assignment_rule_hash` 在任何 formal instance 生成前冻结；pilot matrix/rule 不属于 lockbox；
- final-test `file_hash`、manifest hash、objective/generator/schema/code/config、seeds、methods、statistics 和 exclusions 在打开前冻结；
- 三个 split manifests 必须先通过第 7.2–7.5 节 formal joint preflight，receipt/hash 在任何 formal prompt/operator generation、formal train/dev evaluation、formal portfolio selection 或 final-test run 前冻结；preflight boundary 之外不得暴露 final-test records；
- generation/feedback/tuning processes 不接收 final-test manifest、paths、features 或 results；
- `opened` 后不得改 prompt/operator/portfolio/selector/hyperparameters；
- 任何信息回流将 `lockbox_status` 改为 `contaminated`，相关结果不得进入 confirmatory tables；
- Smoke/demo 文件永不复制、重标或提升为 final-test artifact。
- Pilot non-formal IDs、hashes、paths、file identities、generation identities 与 manifests 不得出现在 formal manifests；joint preflight 必须以 pilot-exclusion receipt 验证。

## 9. Validation Checklist for Future Implementation

- [ ] JSON/schema validation fail closed；
- [ ] pilot preflight 只加载 `pilot_nonformal` manifests，验证 pilot-scoped matrix/rule hashes，拒绝 final-test identity/content，并生成不可升级为 formal evidence 的 pilot receipt/exclusion receipt；
- [ ] `instance_id` canonical derivation、family/instance IDs 唯一且 split 不相交；
- [ ] duplicate ID/path/file hash、alias、symlink、traversal 全部 fail closed；
- [ ] train/dev/final-test joint preflight 在 merged records 上拒绝跨 split ID/hash/path/file-identity/family/generation-identity 重复与 split/lockbox mismatch；
- [ ] formal joint preflight 拒绝任何 pilot scope、family/instance ID、file hash、canonical path、file identity、generation identity、manifest hash 或 source reference；
- [ ] formal joint-preflight receipt 绑定三个 manifest hashes、policy、platform capability 与 exemption evidence，并在任何 formal prompt/operator generation、formal train/dev evaluation、formal selection 或 final-test action 前冻结；
- [ ] unsupported file-identity check 在 formal final-test 默认 fail closed，smoke/demo 仅 warning 且不可形成 formal result；
- [ ] finite speed/time 与 objective-v2 contract；
- [ ] canonical hashes 可重放；
- [ ] exact input set 与 file hashes 校验；
- [ ] formal mode 禁用 uncontrolled glob；
- [ ] final-test lockbox status/authorization 校验；
- [ ] smoke/formal artifact 隔离；
- [ ] malformed/old manifest 不会默认成功；
- [ ] output manifest 足以复现实验和失败归因。
