# 项目审查发现

## 2026-08-12 Phase 6B-T1R3 RED findings

- 目标测试由 153 增至 164 collected；移除了 `provider_claim_mismatch` 与 `runtime_authorization_denied` 两个无充分 evidence 的合法正例，并新增 13 个 reason/evidence 语义 cases。
- `validation_receipt_invalid` 新增 5 cases：4 个无关 evidence 唯一 reject 的 cases 均按预期 RED；manifest evidence 明确 pass 的 fail-closed anchor 已通过。
- `runtime_authorization_denied` 新增 2 个无关 evidence reject cases，均按预期 RED；原有 all-evidence-pass fail-closed case 继续通过。当前 schema 不再把它定义为合法正例。
- 六个专属 predicate cases 中，real/unknown/glob/final-test/manifest-scope 的 unrelated-evidence anchors 已通过；`provider_claim_mismatch` 因缺专用 claim/runtime mismatch evidence 仍被当前实现接受，形成第 7 个预期 RED。
- 唯一授权命令结果：`python -m pytest tests/test_pilot_contract_schema_red.py -q` → **7 failed、157 passed、1 个既有 pyreadline warning**。7 个失败均是 `_assert_invalid` 收到 `SchemaValidationResult(valid=True, rejection_reasons=())`，直接证明当前 reason/evidence 泛化旁路。
- 本轮只修改目标测试与三份 planning 文件；未修改 fixtures、`pilot_contracts.py` 或其他生产代码，未运行 provider/candidate/pilot/benchmark/final-test。
- 建议下一步单独授权最小 T1R3 GREEN；T2 与 Gate P2 继续 blocked。

## 2026-08-12 Phase 6B-T1R3 GREEN contract conflict

- 已删除通用 evidence-reject 回退，并将当前 rejection enum 收窄为五种有专属 predicate 的 reasons；`validation_receipt_invalid`、`provider_claim_mismatch`、`runtime_authorization_denied` 当前 fail closed。
- 本轮规格要求 `uncontrolled_glob_forbidden` 可由 glob input mode **或** `glob_detected=true` 支持；既有两个回归测试分别把其中一项改为 false/manifest-file 并仍断言 invalid，因此实际冻结的是两项必须同时满足（AND）。
- 按“测试与合同冲突时停止并说明”要求，未修改测试/fixtures，也未自行选择 OR 或 AND。目标测试结果为 2 failed、162 passed、1 warning。
- 需用户确认：采用新规格 OR 并授权修正两个既有测试，或保留既有更严格 AND 并允许实现使用 AND。

## 2026-08-12 Phase 6B-T1R3 GREEN implementation review（完成）

- Pure-data boundary 保持：模块仅导入 dataclass/math/re/typing；静态检索未发现 path/file access、file identity、hash recomputation、runner/provider/candidate/pilot execution 能力。
- 通用 `any(evidence.decision == reject)` 回退已删除；当前 runner rejection enum 仅保留 real/unknown provider、uncontrolled glob、final-test scope、manifest scope 五种有显式 predicate 的 reasons。
- `validation_receipt_invalid`、`runtime_authorization_denied`、`provider_claim_mismatch` 已从 enum 移除且 helper 默认返回 False，因此当前 schema 下均 fail closed。
- Real/unknown 仅读取 `no_real_llm_evidence`；glob 仅读取 `no_uncontrolled_glob_evidence`；final-test 仅读取 no-final/scope；manifest-scope 仅读取 scope。无关 evidence 不能跨 reason 授权。
- **Required blocker：** glob predicate 使用 `(requested mode is glob) OR (glob_detected=True)`，与仍保留的两个 AND 回归测试冲突。Fresh 唯一授权测试为 2 failed、162 passed、1 warning；GREEN completion 不成立。
- Review verdict：Request changes（0 Critical、1 Required）。由于目标测试未全绿，Phase 6B-T2 不准入；修正并复审后才可考虑 PIV-02 RED-only。
- `preflight_validated` 仍强制 `accepted_execution=False`，status enum 仍只有两个 inert preflight states；Gate P2 未关闭，所有执行禁令保持。

## 2026-08-12 Phase 6B-T1R3-FIX findings

- 用户已批准以既有合同测试为准：`uncontrolled_glob_forbidden` 必须同时具有 glob input mode 与 `glob_detected=True`；任一单项证据不足以支持该拒绝原因。
- 最小实现只把该专属 support predicate 的 OR 改为 AND；`accepted_input_mode is None` 与 `decision == "reject"` 仍为必要条件。
- 其余 reason-specific predicates、unsupported reasons fail-closed、preflight-only status 与 `accepted_execution=False` 合同均未改变。
- 唯一授权验证命令通过：164 passed、1 个既有 pyreadline DeprecationWarning；两个 glob regression failures 已转绿。
- 该结果只支持进入 T1R3-FIX 独立 implementation review，不自动授权 T2、Gate P2 或任何 provider/pilot/实验执行。

## 2026-08-12 Phase 6B-T1R3-FIX narrow review findings（进行中）

- Tests-first 核对确认三个 glob 负例分别覆盖：mode 改为 `manifest_file`、`glob_detected=False`、evidence decision 改为 `pass`；任一条件不满足都必须 invalid。
- 实现的 glob predicate 与合同逐项一致：glob-mode **AND** detected true **AND** accepted input null **AND** evidence decision reject。
- `_rejection_is_supported()` 尾部仍显式 `return False`；`validation_receipt_invalid`、`runtime_authorization_denied`、`provider_claim_mismatch` 不在允许 enum 且没有专属 predicate，因此继续 fail closed。
- Runner status enum 仍仅含 `preflight_validated` / `preflight_rejected`；validated 分支仍要求 literal `accepted_execution=False`。
- 模块共 903 行但本次只修改一个局部布尔连接；未新增抽象、依赖、循环或 I/O/执行能力。本轮不把既有文件长度作为该窄修复的阻塞项。
- Fresh 唯一授权测试为 164 passed、1 个既有 pyreadline DeprecationWarning；未运行完整 pytest 或任何执行型工作流。
- 最终 verdict：Approve（0 Critical、0 Required）。允许进入下一项单独授权的 T2 RED-only；建议仍采用 PIV-02 scoped-hash verification tests，先测试、不得先实现。
- 所有禁令保持：真实 LLM/provider、candidate/pilot execution、benchmark、正式/大规模/final-test 实验均未授权；Gate P2 未关闭。

## 2026-08-12 Phase 6B-T2 RED design findings

- 现有规划将 PIV-02 定义为 scoped hash verification，并要求从同一 canonical bytes 重算；validator/runner receipt 规格均冻结为 RFC 8785/JCS UTF-8 与排除 ID/signature fields 的非自引用 SHA-256。
- 本轮采用独立未来模块 `mrta_rect_coverage.experiments.pilot_integrity`，避免把文件/hash 能力塞回 903 行的 pure-data `pilot_contracts.py`。
- RED tests 将冻结小而明确的函数边界：canonical bytes/object hash、SHA-256 format、pilot scope binding、validation/runner receipt ID 与 cross-receipt binding、explicit-content-only verification。
- 不需要新增 JSON fixtures：所有对象和 bytes 都可在测试内确定性构造，从而避免任何 path/file/final-test artifact 接触。
- 目标模块当前不存在；测试将延迟 import，并把预期 `ModuleNotFoundError` 转成清晰的 `pytest.fail` RED 信息，确保 collection 本身成功。
- 新测试共 59 个 collected cases，覆盖 canonical key/array/type distinctions、7 类非 JSON/非有限值、lowercase SHA-256 格式、pilot matrix/rule scoped binding、formal/final-test/non-promotion 拒绝、两级 receipt ID 与跨 receipt binding、五个 evidence objects、rejected receipts 和 no implicit file access。
- 不需要 fixture 文件，因而不存在 fixture JSON parsing 或 fixture path 访问风险；所有 final-test 内容仅为内存中的拒绝 marker，不读取或推断任何真实 artifact。
- RED 验证为 59 failed、0 passed、1 个既有 pyreadline warning。每个失败均由 `_integrity()` 将目标模块缺失转换为同一条清晰的 T2 RED failure；无 collection/syntax/fixture/infrastructure error。
- pytest 的详细回溯输出超过工具展示上限而被截断，但最终汇总与 short failure list 完整显示 59 个同源 failures；为遵守单一测试运行范围，未重复执行。
- 建议下一步仅在单独授权后进入 T2 GREEN，创建独立 `pilot_integrity` 纯内存实现；不得把 hash/path 能力合并回 `pilot_contracts.py`，也不得自动授权 runner/provider/pilot。

## 2026-08-13 Phase 6B-T2 GREEN findings

- 新增独立 `src/mrta_rect_coverage/experiments/pilot_integrity.py`；`pilot_contracts.py`、测试、docs/configs/data 均未修改。
- 公开 API 覆盖 strict JSON-domain canonical bytes、explicit bytes SHA-256、object hash、lowercase digest validation、pilot matrix/rule scoped binding、validator/runner receipt ID 和 cross binding、explicit content binding。
- Canonicalization 在序列化前递归拒绝 NaN/Infinity、bytes、tuple、set、datetime/object 和非字符串 object keys；采用 sorted-key、compact、UTF-8 JSON，保留 array 顺序与 JSON 类型差异。
- Receipt ID 都从排除自身 ID 与 `signature`/`signatures` 的完整 supplied body 重算；evidence objects 没有被选择性移除，旧 ID 在任一 evidence/status/body 变更后失效。
- Scoped verifier 要求 `pilot_nonformal`/`pilot`、literal promotion false、pilot matrix/rule object scope 和对应 canonical hashes；formal/final-test/pilot-audit hash markers fail closed。
- Explicit-content verifier 只接受显式 bytes 或 object；`file_path` 仅进行内存 marker 检查，从不打开、解析或 resolve 路径。模块没有 pathlib/open/os/subprocess 或任何 runner/provider/candidate/pilot 能力。
- T2 专项首次 GREEN：59 passed、1 个既有 pyreadline warning。选择性 T1+T2 回归：223 passed、1 个相同 warning。未运行完整 pytest。
- 当前测试冻结的是项目所需 deterministic JSON subset；完整 RFC 8785 对极端数值/Unicode edge cases 的独立 conformance vectors 尚未加入，本轮不作超出测试证据的声明。
- Gate P2 未关闭；GREEN 只支持进入独立 implementation review，不授权真实 LLM/provider、candidate/pilot、benchmark 或正式/大规模/final-test 实验。

## 2026-08-12 Phase 6B-T1R2 GREEN findings

- 只修改 `src/mrta_rect_coverage/experiments/pilot_contracts.py` 与三份 planning files；tests/fixtures、其他生产模块、configs/data 均未修改。
- Runner receipt status enum 已收窄为 `preflight_validated` / `preflight_rejected`；所有 scheduled/running/completed/aborted 等 future Gate P2 lifecycle 状态均 fail closed。Validated 继续强制 `accepted_execution=false`、无 scheduled IDs、无 Gate P2 authorization ID。
- 新增纯数据 `_rejection_is_supported` 决策：real/unknown provider 绑定 `no_real_llm_evidence`；glob 绑定输入模式、detected flag 与 reject decision；final-test/scope 绑定相应 presence/scope evidence；provider claim mismatch 绑定 artifact claim 与 requested provider 差异。其余已批准 reason 仅在至少一个具名 evidence 明确 reject 时接受。
- Provider claim mismatch 使用现有 `artifact_claimed_provider` 与 `requested_provider` 表达；claim 相同或缺失时不能支持 mismatch reason，无需新增 schema 字段。
- Validated 分支新增内部一致性：拒绝 loaded scope/manifest/path 中的 final-test marker，要求 no-glob manifest-file/false/pass，要求 no-real mock/file/pass，并要求 pilot scope/matrix/nonformal confirmation 且无 formal-final-test rejection flag。
- 所有检查仅处理传入 dict/list/string/bool；没有文件/path access、hash recomputation、runner/provider/candidate/pilot execution 或 final-test访问。
- 唯一授权测试：`python -m pytest tests/test_pilot_contract_schema_red.py -q` → **153 passed、0 failed、1 个既有 pyreadline warning**。
- T1R2 GREEN 仅建议进入 independent implementation review；不自动授权 T2、Gate P2 或任何 provider/pilot/实验执行。

## 2026-08-12 Phase 6B-T1R2 RED findings

- 仅修改 `tests/test_pilot_contract_schema_red.py` 与三份 planning files；复用原有 5 个 fixtures，未修改 `src/mrta_rect_coverage/experiments/pilot_contracts.py` 或任何其他生产代码。
- 测试从 114 增至 153 collected，共新增 39 cases。专项结果：**25 failed、128 passed、1 个既有 pyreadline warning**；原 114 项保持通过。
- Non-preflight status matrix 共 20 cases：`scheduled/running/completed/completed_with_failures/aborted/receipt_incomplete` 在 `accepted_execution=false/true` 下共 12 个预期 RED；`executed/execution_started/execution_completed/pilot_completed` 共 8 个已 fail-closed anchors 通过。
- Rejection evidence tests 覆盖 real/unknown provider、uncontrolled glob、final-test scope、manifest scope、provider claim mismatch，以及所有 evidence 均 pass 却产生 rejected receipt。现实现对其中 10 个语义矛盾 receipt 返回 valid，形成预期 RED；两个 real/unknown decision mismatch anchors 已被既有 provider branch 拒绝。
- Validated evidence tests 覆盖 final-test-present flag、loaded scopes、manifest marker、scope evidence、glob detection 与 real provider。现实现未检查 loaded `formal_final_test` scope/manifest marker 的 3 个 cases 为预期 RED；其余 4 个由既有 state/top-evidence checks 拒绝。
- 25 个失败均为 `_assert_invalid` 收到 `SchemaValidationResult(valid=True, rejection_reasons=())`；无 collection、syntax、fixture JSON、import 或基础设施错误，证明失败来自预期 schema validator 语义不严格。
- T1R2 RED 不实现 Gate P2 或 future lifecycle，只冻结当前 schema 仅允许 `preflight_validated/preflight_rejected`，且 validated 继续要求 `accepted_execution=false`。
- 建议下一步单独授权最小 T1R2 GREEN；T2、Gate P2、真实 provider、pilot 与正式实验仍 blocked。

## 2026-08-12 Phase 6B-T1R independent repair review

- Pure-data capability boundary 通过静态审查：模块仅依赖 `dataclasses`、`math`、`re`、`typing`，没有 path/file/hash recomputation、runner/provider/candidate/pilot execution 依赖或调用。
- T1R tests/fixtures 保持 inert preflight 合同并真实保留新增旁路回归；合法 validated receipt 要求 `accepted_execution=false`。
- **Required 1：** runner `status` enum 仍接受 `scheduled/running/completed/completed_with_failures/aborted/receipt_incomplete`，但 `_validate_runner_state` 只约束两个 preflight 分支。当前可构造未获本阶段批准的 non-preflight receipt，并使 `accepted_execution=true` 不触发 state rejection；这与“当前 T1R 不实现这些状态、不授权执行”冲突，且测试没有相应负例。
- **Required 2：** `preflight_rejected` 只要求 accepted fields 为空和 reason 非空；除 real/unknown provider 特例外，没有绑定 `rejection_reason` 与对应 evidence decision/content。例如 glob rejection 的 evidence 可声称 `decision=pass`、`glob_detected=false` 而仍通过。Validated no-final-test evidence 也可在 loaded scopes 中列出 `formal_final_test`，同时声称 `final_test_scope_present=false/decision=pass`。这未满足 evidence 支持决策且内部一致的合同，现有测试未覆盖这些矛盾组合。
- 文件已增长到约 814 行；仍低于常见 1000 行 inspection threshold，但若 T2 继续加入 hash contract，宜将 manifest/validator receipt/runner receipt helpers 拆为聚焦模块，作为 Consider 而非本轮 blocker。
- **最终 verdict：Request changes（0 Critical、2 Required）。** T1R 原先识别的旁路已修复且 114 tests fresh 通过，但上述未覆盖状态仍阻止 T2。

## 2026-08-12 Phase 6B-T1R corrected GREEN findings

- `preflight_validated` 严格保持 inert 语义：`accepted_execution` 必须为 literal `false`；它只表示 schema/scope/provider preflight 通过，不表示 scheduling、runner/candidate/pilot execution，也不关闭 Gate P2。
- Runner receipt 已严格区分 `preflight_validated` 与 `preflight_rejected`：validated 分支只接受 mock/file、`manifest_file`、`pilot_nonformal` 和 null rejection；rejected 分支要求所有 accepted decision fields 为 null/false 且 rejection reason 合法。
- Real/unknown provider 只能形成拒绝 receipt，不能保留 accepted provider 或 execution；其 rejection reason 和 `no_real_llm_evidence` decision 必须匹配。
- 五个具名 evidence objects 不再只检查“存在”：requested/accepted provider、input mode、manifest scope、manifest hash 和 validation receipt ID 均与 top-level 字段交叉校验。
- Manifest、validator receipt、runner receipt 的 version/type/objective/scope/matrix/status 枚举已冻结；validator valid/rejected 分支的 rejection、hash、scope、record count 和 evidence 不变量已收紧。
- `failure_summaries` 仅接受 exact object shape 和非负 strict integer；T1R 尚无批准的 output-entry schema，因此任何非空 `output_paths` 均 fail closed。
- 实现继续是 pure-data validation：未增加文件/path access、hash recomputation、runner/provider/candidate/pilot execution 或 final-test capability。
- 唯一授权测试 fresh GREEN：`python -m pytest tests/test_pilot_contract_schema_red.py -q` → **114 passed、0 failed、1 个既有 pyreadline warning**。
- 两项 T1 implementation-review Required 已在实现层关闭；下一步仅建议进入 Phase 6B-T1R implementation review，不自动进入 T2 或 Gate P2。

## 2026-08-11 Phase 6B-T1R RED findings

- 只修改 `tests/test_pilot_contract_schema_red.py` 与三份 planning files；未新增/修改 fixtures，未修改 `src/mrta_rect_coverage/experiments/pilot_contracts.py` 或任何其他生产代码。
- 测试从 53 增至 114 collected，共新增 61 cases。专项结果：49 failed、65 passed、1 个既有 pyreadline warning；原 53 项保持通过，新用例中 49 个为预期 RED、12 个验证当前已经 fail closed 的锚点。
- 49 个失败均表现为待拒绝 payload 得到 `SchemaValidationResult(valid=True, rejection_reasons=())`；没有 collection、syntax、fixture JSON、import 或测试基础设施错误。
- Provider/state RED 覆盖 real/unknown 使用 `preflight_validated`、保留 accepted provider、错误 primary rejection reason，以及 rejected receipt 保留 accepted provider/input/scope。
- Validated branch RED 覆盖 accepted decision fields/null bindings、scope/manifest-only evidence 的空值，以及 requested/accepted 顶层字段与 no-real/no-glob/scope/manifest-only evidence 的七类 mismatch。
- Enum/receipt RED 覆盖 pilot manifest schema/manifest/objective version、validator/runner receipt schema version、requested scope/matrix scope、validation valid/rejected reason/count/scope 不变量。
- Collection-shape RED 覆盖 `failure_summaries` entry 必须是 exact object 且 count/denominator 为非负 integer，以及未定义/畸形/含 formal-final-test 标记的 `output_paths` entry 必须 fail closed。
- 12 个新增 passing anchors 包括已有 accepted-execution、missing rejection reason、unsupported manifest scope/matrix/status、manifest hash type/format及 top-level list type checks；这些通过是预期回归证据，不削弱 suite 的 RED 状态。
- 请求中的 `preflight_validated + accepted_execution=false 应失败` 与批准规格/合法 fixture/既有 `true` 应失败测试冲突，本轮保留 canonical `false` 合法语义；validation receipt 使用 canonical `valid`/`rejected`。
- T1R RED 已充分证明两项 review Required 的实现缺口，建议下一步单独授权 T1R GREEN；T2、Gate P2、provider/pilot/正式实验继续 blocked。

## 2026-08-11 Phase 6B-T1 GREEN implementation review

- **结论：Request changes（0 Critical、2 Required）。** 当前模块保持 pure-data 边界，没有文件/path/hash recomputation/runner/provider/candidate/pilot capability；专项测试 fresh 结果为 53 passed、1 个既有 warning。
- **Required 1 — strict schema invariants 不完整：** manifest 的多个 version/type/objective/contamination 字段只检查为 string；validation receipt 只检查 `receipt_type`/`status` 二元配对；runner 只检查 accepted 字段各自枚举及 preflight 的少量状态。当前没有完整约束 valid/rejected branch 的 nullability、requested↔accepted↔evidence 一致性、real/unknown provider 必须处于 rejection branch、rejected receipt 的 accepted fields 必须为 null，以及 evidence/top-level 值一致。
- **Required 2 — RED coverage 未捕获上述旁路：** 现有 provider tests 只证明合法的 real/unknown rejection receipt 可以被表示，没有构造 real/unknown `preflight_validated`、rejected-but-accepted、top/evidence mismatch、invalid supported-version enum 或畸形 `failure_summaries`/`output_paths` object。因此 53 passed 不能证明 requested/accepted schema 已严格 fail closed。
- 五个 runner evidence objects 均是 top-level required objects，且 nested unknown field 会拒绝；manifest/instance unknown fields、strict bool-vs-int、数值域、formal scope 与 promotion violation 的现有覆盖有效。
- Candidate observability record 未在 T1 实现或验证，因此 T1 没有把 `invalid_solution` 放入 `execution_status`，但也不能为 execution/contract/feasibility/optimization/structural 五轴提供机器可验证证据；该项留给后续独立 observability-schema task。
- `pilot_contracts.py` 共 607 行、仅依赖 dataclasses/math/re/typing；当前规模可审查，但在加入 T1R/T2 之前可考虑按 manifest、validator receipt、runner receipt 拆分内部 schema 定义，避免单文件继续增长。
- Planning 中 RED-only scope、future-module 与 next-GREEN 的陈旧措辞已在本次 review 的 planning-only 更新中纠正；未修改生产代码、测试或 fixtures。
- 在两个 Required 关闭并复审前不进入 Phase 6B-T2；真实 LLM/provider、pilot execution、正式/大规模/final-test 实验继续禁止。

## 2026-08-11 Phase 6B-T1 GREEN findings

- 新增 `src/mrta_rect_coverage/experiments/pilot_contracts.py`，提供 manifest、manifest-validation receipt、runner receipt 三个 pure-data schema validator，并统一返回不可变 `SchemaValidationResult(valid, rejection_reasons)`。
- Manifest 校验覆盖 required/unknown fields、严格 JSON 类型（特别是 bool 不冒充 integer/number）、数值域、SHA-256 字符串格式、pilot/formal scope 组合及永久禁止 artifact promotion。
- Validation receipt 校验覆盖 valid/rejected union branch、receipt type/status 配对，以及两个具名 evidence object 的必需性和严格字段形状。
- Runner receipt 校验覆盖 requested/accepted 字段类型与枚举、五个具名 evidence objects、nested unknown fields、preflight validated/rejected 状态不变量，以及 real/unknown/provider-claim negative path 的结构化记录能力。
- Hash/ID 字段本阶段仅校验存在、JSON 类型与 64 位小写十六进制格式；没有重算 manifest、canonical manifest、validation receipt 或 runner receipt hash。
- 模块没有导入 pathlib/os/hashlib/subprocess/provider/runner/candidate 代码，也不读取路径或文件；T1 不实现 path existence、symlink/hardlink/inode、duplicate identity、runner scheduling、provider/candidate execution 或 pilot。
- 专项 fresh GREEN：`python -m pytest tests/test_pilot_contract_schema_red.py -q` → 53 passed、1 个既有 pyreadline DeprecationWarning，耗时 0.21s。
- Gate P2 仍未关闭；该结果只支持进入 Phase 6B-T1 GREEN 独立复审，不授权 provider、pilot 或任何正式/大规模/final-test 实验。

## 2026-08-11 Phase 6B-T1 RED contract

- Phase 6B-R 独立复审结论为 Approve（0 Critical、0 Required）；该结论只允许单独授权 bounded implementation task，不关闭 Gate P2。
- 用户以“Phase 6B-T1：pilot receipt / manifest schema fixtures and validation tests planning-to-code”授权首个任务；按上一轮明确建议，本轮限定为 TDD RED：先写 fixture/schema validation 失败测试，不写生产实现。
- 工作区不是 Git repository，无法使用 worktree；在用户固定项目根原地工作，并以文件范围锁保护既有内容。
- 本轮继续禁止真实 LLM/provider、mock/file provider execution、candidate execution、pilot、benchmark、正式/大规模/final-test 实验。
- 当前 `src/` 中没有 pilot manifest/receipt schema validator；现有 `operator_evolution/schemas.py` 只包含生成算子 dataclasses，不能承担 pilot manifest/receipt boundary。
- T1 冻结 future pure-data API 为 `mrta_rect_coverage.experiments.pilot_contracts`，入口分别验证 pilot manifest、manifest validation receipt 与 runner receipt，返回 `valid` + `rejection_reasons` 的结构化结果；本轮只以 RED tests 表达合同。
- JSON fixtures 只验证 schema/branch/invariant，不读取 instance 文件、不重算 manifest/file hash、不访问路径；PIV-02/PIV-03/PIV-04 与 runner/provider 行为保持后续单独授权。
- RED fixture set 包含：valid pilot manifest、valid/rejected manifest-validation receipts、preflight-validated/rejected runner receipts。Fixtures 均为 strict JSON object，且明确使用 non-formal/pilot scope 或 synthetic rejection scope。
- 新增测试共 53 项：1 个 fixture JSON 自检通过；其余 52 项全部以统一信息 `pilot schema contract module is not implemented` 失败，证明失败来自缺失的目标生产能力而非 collection、syntax 或 JSON fixture 错误。
- 52 个 RED cases 分组：manifest schema 33、validator-receipt schema 5、runner-receipt schema 14。覆盖 required/unknown/wrong-type/value-domain、scope/promotion、receipt union/evidence/state、requested/accepted separation 和四类 provider rejection recordability。
- GREEN 不得借机实现 PIV-02 hash、PIV-03 path/duplicate/file identity、PIV-04 canonical-ID integrity、runner scheduling 或任何 provider/candidate action；这些仍需后续独立 TDD task。

## 2026-08-11 Phase 6B-RR repair contract

- 本轮只关闭 Phase 6B-R review 的 4 个 Required groups：candidate failure taxonomy、machine-verifiable receipt schema、real-provider negative coverage、Gate lifecycle state。
- Candidate 记录将恢复 execution、contract、feasibility、optimization、structural 五轴；`failure_type` 只作为派生摘要，不能替代分轴字段。
- Runner receipt 将拆分 raw `requested_*` 审计字段与 nullable `accepted_*` 决策字段，并把 no-real-LLM/no-final-test/no-glob/manifest-only/scope evidence 设为具名 required objects。
- Validator/runner receipt ID 将使用 RFC 8785 canonical body、排除自身 ID/signature fields 后的 SHA-256，消除自引用；任一 evidence 变化必须改变 receipt ID。
- Test plan 将新增 real provider、unknown alias、artifact/runtime provider mismatch 两方向共 4 个专门负例，全部在 scheduling/invocation 前或 deployment gate 拒绝。
- Gate P1 只授权规划；修订通过后下一步最多是 implementation task authorization，仍不等于 Gate P2 closure 或 pilot execution。
- 回读确认：五轴 candidate schema、五个具名 runner evidence objects、requested/accepted decision fields、无自引用 runner/validator receipt IDs、T14–T17 和 Gate lifecycle 已写入磁盘。
- 同步尾项已关闭：T11 改用 `no_uncontrolled_glob_evidence`，runner/validator 明示 RFC 8785 deterministic object-member key ordering。
- 纯文档合同核验为 45/45 PASS、0 failures；这证明指定字段/边界已写入规格，不代表代码、测试或 Gate P2 evidence 已实现。
- 四项 Consider 均已同步：pilot-local split labels、invocation-scoped no-final-test evidence、baseline makespan finite/>0、transient event 与 terminal run summary 分离。
- 当前结论仅为“documentation repair complete, awaiting independent review”；implementation task authorization、Gate P2、pilot、真实 provider 和正式实验均未获授权。

## 2026-08-11 Phase 6B-R 独立复审结论

- 通过：Phase 6B 总体计划明确仅限 implementation planning，禁止 mock/file/real provider、pilot、formal/large-scale/final-test，并保持 Gate P2 open。
- 通过：observability 已按 run/operator-type、candidate、evaluation-cell 三层拆分；cell 显式保存 evolution run、method、family、instance、replicate 和 solver seed；candidate 明确禁止 `no_valid_operator`/`not_evolved`。
- Required candidate：candidate schema 把 `invalid_solution` 放入 `execution_status`，却没有独立 contract/feasibility status/subtype，退化了此前冻结的多轴 failure taxonomy，可能混淆 execution success 与 solution validity 及分母统计。
- 待核：runner receipt 的证明对象、invalid request rejection schema、receipt ID/hash canonicalization 是否无歧义；mock/file test plan 是否显式覆盖 real-provider misconfiguration rejection。
- 最终 verdict：**Request changes（0 Critical、4 Required groups）**；在修订并复审前，不允许进入 Phase 6B implementation task authorization。
- 已确认 Required candidate 2：runner receipt 表只列三个证明布尔值，未把 no-real-provider/no-final-test/no-glob evidence objects 作为具名 required schema fields，示例也缺这些对象；因此 narrative Section 6 尚不能被 schema validator 强制。
- 已确认 Required candidate 3：runner 的 accepted `command_intent` 只允许 `single_file`/`disabled`/mock-or-file，但 rejection example 使用 `directory_glob`/`requested_but_forbidden`；同一 schema 无法同时验证 accepted intent 与 rejected raw request。`provider` 也无法结构化保存 real-provider attempt。应拆成 raw requested intent 与 nullable accepted intent/decision。
- 已确认 Required candidate 4：receipt ID/hash 没有冻结无自引用的 canonical derivation（例如 hash canonical body excluding ID），无法跨实现验证“hash-bound receipt identity”。
- 已确认 Required candidate 5：13-case test plan 没有单独覆盖 real-provider config/adapter rejection；仅靠 common assertion 与 receipt boolean 不足以证明不会误调用真实 provider。
- 已确认状态同步问题：Gate P2 current-status 仍称下一步为 Phase 6A review，且 outcome `planning_only` 仍只描述 Phase 6A documents；与实际 Phase 6B planning review 不一致。此问题不自行放宽 Gate，但会误导下一授权动作。
- Required 分组：① execution/contract/feasibility taxonomy；② receipt evidence、rejection intent/provider 与 canonical ID/hash；③ real-provider misconfiguration 专门负例；④ Gate P2/Phase 6B lifecycle 状态同步。
- 通过项：planning-only 与全部禁令；三层 record ownership 和显式 cell hierarchy；candidate 禁止上层状态；validator 的 pilot scope/path/hash/duplicate/no-final-test/no-glob 主边界；13 个指定 mock/file 场景；failure-zero/batch-inconclusive、fallback non-attribution；pre/post-Gate 非循环授权；Gate P2 checkboxes 全部未关闭。
- Consider：把 pilot 的 smoke/train/dev 命名收紧为 `pilot_smoke`/`pilot_train`/`pilot_dev`；把 invocation-scoped proof 重命名为 `no_final_test_input_loaded`；为 observed relative improvement 显式要求 baseline makespan 有限且大于零；将 transient lifecycle event 与 terminal run summary schema 分开。
- 当前仍禁止真实 LLM/provider、pilot execution、正式实验、大规模实验和 final-test；本轮没有修改受审正文或算法代码。

## 2026-08-11 Phase 6B implementation-planning contract

- Phase 6A independent planning review 已 Approve（0 Critical、0 Required），因此当前只获准进入 Phase 6B implementation planning。
- Phase 6B 的交付物是未来 manifest validator、pilot-only fixtures、manifest-only runner、receipts、observability、accounting、mock/file tests 与 Gate P2 evidence 的工程任务书；本轮不实现任何能力。
- Observability 必须拆成 run/operator-type、candidate、evaluation-cell 三层；`no_valid_operator`、`not_evolved` 和 run-level deployment summary 不得重复塞入 candidate row。
- Gate P2 的 “demonstrably executable” 必须在未来由 machine-auditable validation/runner/rejection receipts、no-final-test proof 与 no-glob proof 支撑；本轮不得将任何 evidence checkbox 标为完成。
- 当前仍禁止真实 LLM/provider、mock/file provider execution、pilot、正式/大规模实验和 final-test；Phase 6B 完成后下一步只能是 planning review。
- Phase 6B 已形成六份工程规格：总体路线、基础设施任务分解、三层 observability、strict validator、runner receipt 和 17-case mock/file/provider-boundary test plan；另在 Gate P2 文档中加入未完成的机器证据 checklist。
- 关键非循环授权规则：Gate P2 前的实现证据只能使用 inert fixtures、stored responses 或 injected executor statuses 验证组件、receipt 与 accounting；实际 mock/file provider/candidate execution 只能在 Gate P2 独立批准后进行。
- Manifest validator 计划把 raw/canonical manifest hash、pilot matrix/rule runtime expectations、path/file identity、duplicate content、scope 和 non-promotion 绑定到 receipt；artifact 自报字段不建立 authority。
- Observability ownership 已明确：run/operator-type 保存 schedule/no-valid/not-evolved/deployment summary，candidate 保存逐候选安全与执行证据，evaluation-cell 显式保存 run/method/family/instance/replicate/seed 和 policy-analysis 字段。
- Failure-zero 仅适用于通过 batch integrity checks 后的 localized generated-result failure；objective/input/scope/hash/lockbox/baseline-pairing integrity violation 保持 `batch_inconclusive`，fallback 不归因，complete-case 仅 supplementary。
- 本轮未验证实现能力：validator、runner、schema、fixtures、receipts 和测试都仍是 planned，Gate P2 checklist 全部保持 open。

## 2026-08-11 Phase 6A-R 独立规划复审结论

- 五份 Phase 6A 文档均将当前阶段限定为 planning：不执行 pilot，不调用 mock/file/真实 provider，不接触 final-test，也不产生正式性能证据。
- pilot-only lifecycle 与 formal lifecycle 已分离：pilot 使用 `pilot_nonformal` / `pilot` scope、pilot-scoped matrix/split hashes，并明确禁止提升、重标、复制、链接或复用为 formal artifact。
- mock/file 场景矩阵覆盖 legal、invalid、unsafe、deployment-blocked 与 fallback 路径，并贯穿 validation、execution gate、contract/feasibility、benchmark、selection、freeze、deployment 与 attribution。
- observability 计划包含 scheduled-run 预登记、失败状态保留、failure-zero analysis value、fallback/attribution 分离及 failure/deployment rates，足以作为 Phase 6B schema 设计输入。
- Gate P1、Gate P2、Formal Gate B 与 Phase 7 real-provider gate 已分层；Gate P2 当前未关闭，因此仍禁止 pilot execution。
- 独立复审结论为 **Approve：0 Critical、0 Required**；只读 11 项一致性矩阵为 11/11 PASS。Phase 6B implementation planning 可以在单独授权后进入；本结论不关闭 Gate P2、Gate B 或 Phase 7 gate。
- 非阻塞 Consider：Phase 6B schema 规划时将 run/operator-type 状态（如 `no_valid_operator`、`not_evolved`）与 candidate/cell 记录分表或显式关联；把 Gate P2 的“demonstrably executable”落实为可审计的 validator/runner evidence；当 evaluation grid 存在时，把 evolution run、method condition、family、replicate、solver seed 作为显式字段而非仅编码在 `cell_id` 中。
- 当前仍禁止真实 LLM/provider、pilot execution、正式实验、大规模实验和 final-test；pilot 结果仍不得作为论文性能证据。

## 2026-08-11 Phase 6A planning contract

- Phase 5B-R4-R 已批准进入 Phase 6A **planning only**；Gate P2、Gate B 与 Phase 7 preflight 均未关闭。
- Phase 6A 的唯一目标是为未来 mock/file pilot 设计 closed-loop、manifest、observability 与 execution gate，不执行任何 provider、candidate、benchmark 或 pilot。
- Pilot identity domain 必须继续使用 `manifest_scope=pilot_nonformal`、`matrix_scope=pilot` 与 pilot-scoped hashes；任何 pilot artifact 永久禁止提升、重标、复制、链接或复用为 formal artifact。
- Mock/file 规划必须覆盖 legal、invalid/contract-violating、unsafe/static-rejected 与 missing-runtime-authorization frozen deployment 四类路径，同时验证 failure retention、fallback non-attribution、`no_valid_operator`/`not_evolved` 区分。
- 本阶段不得创建、读取、hash 或推断 final-test family matrix、manifest、files、hashes 或 performance；产物不构成论文性能证据。
- 五份规划文档采用单向闭环：pilot manifest allowlist → candidate persistence → static validation → execution gate → contract/feasibility → benchmark → selection → freeze → runtime deployment gate → fallback/attribution → cell/run accounting。
- Mock 规划覆盖 deterministic success、mixed failure、all-invalid、not-scheduled、deployment-blocked 和 runtime fallback；file 规划覆盖 legal、contract-invalid、unsafe 和 missing-runtime-authorization frozen artifact。
- Observability 合同同时保留原始 failure/status 与 failure-zero policy value，禁止 complete-case 丢弃、fallback makespan 归因和把 policy zero 解释为物理惩罚。
- Gate P2 证据分成 pilot identity、manifest runner、final-test isolation、fixture approval、eligibility/attribution、accounting/observability 和 verification/review 七组；文档创建本身不关闭任何 checkbox。
- 规格自审未发现 TBD/TODO、已执行性能主张或自动进入 Phase 6B 的语句。一个已知非阻塞精化项继续保留：formal leakage rejection 应逐名包含 pilot matrix/rule hashes，Gate P1 bullets 应标明为 entry 后获准规划范围。

## 2026-08-11 Phase 5B-R4 修订合同

- Phase 5B-R3 independent review 的唯一 Required 是 pilot/formal family-matrix authority 冲突：旧合同同时要求 full matrix 在任何实例生成前冻结、pilot 不得接触 final-test、formal matrix 在 pilot 后冻结，且 pilot manifest 又要求 full-matrix hash。
- 本轮唯一设计采用两个身份域：`pilot_nonformal` 绑定 pilot-only family matrix/split rule；formal train/dev/final-test 绑定 pilot 后、任何 formal instance generation 前冻结的 complete formal matrix/rule。
- Pilot instances、manifests、family IDs、hashes、paths 和 file identities 默认不得提升、重标、复制或复用于 formal artifacts；formal joint preflight 必须把任何命中作为 fail-closed contamination/input violation。
- `family_matrix_hash` 与 `split_assignment_rule_hash` 都是 scope-aware：pilot 绑定 pilot-only artifacts，formal 才绑定 complete formal artifacts；不得再无条件解释为 canonical full formal matrix hash。
- Gate P 拆为 planning-entry 与 pilot-execution；本轮只修订文档，不关闭或进入 Phase 6A。Gate B 与真实 LLM gate 保持独立关闭。
- 当前 schema 的具体冲突位于 `manifest_spec.md`：所有 split records/header 都要求 `family_matrix_hash`，且字段被无条件解释为 canonical full matrix；pilot runner 又明确禁止 final-test matrix/identity。修订必须让 hash 语义由 `matrix_scope` 决定。
- 当前 lifecycle 冲突同时存在于 `experiment_protocol.md`、`instance_protocol.md` 与 `final_test_lockbox_protocol.md` 的“任何实例生成前”表述；应只约束 formal instances，并为 pilot instances 增加独立、不可提升的生成/冻结顺序。
- 逐段核对进一步确认：`pilot_plan.md` 仍把 P1 命名为 “Formal-Objective” 且没有 pilot-only hash/identity 排除清单；`experiment_no_go_checklist.md` 的 Gate P 仍把 planning-entry 与实际 execution 合在一起。两处都必须同步，否则 scope-aware manifest schema 仍可能被旧 gate/命名绕回 formal 语义。
- `manifest_spec.md` 已采用 scope-aware canonical `family_matrix_hash` / `split_assignment_rule_hash`。为同时满足 pilot 审计的明确命名，pilot receipt 还需把同值显式输出为 `pilot_family_matrix_hash` / `pilot_split_assignment_rule_hash`；这不是第二套可分歧 hash，而是 scope-disambiguated audit alias。
- 主体同步后的只读核对未发现遗留的无作用域 “任何实例生成前” 或 “formal pilot” 口径；发现 `instance_protocol.md` formal lifecycle 列表因旧尾项保留产生 1–7 后跳到 9 的编辑瑕疵，已改为 8，不改变协议含义。
- 完成前版本检索只发现 lockbox 文档状态仍标 Phase 5B-R3；已同步为 R4。该状态文字不构成 execution authorization，Gate P1/P2 与 Gate B 仍保持关闭。
- **Required 已在规格层关闭：** Pilot 使用独立 pilot-only matrix/rule、scoped hashes 与 `pilot_nonformal` manifests；formal complete matrix/rule 仅在 pilot 后且任何 formal instance 生成前冻结。Pilot artifacts 通过 promotion prohibition 与 exclusion receipt 永久隔离，formal joint preflight 对命中 fail closed。
- Gate P 已拆为 P1 planning-entry 与 P2 pilot-execution。R4 两者都未关闭：本轮文档不授权 Phase 6A planning/execution、真实 provider、formal/final-test generation 或任何实验。
- Fresh 文档合同核验共 42 项、0 failures、exit 0；覆盖 7 份协议与 3 份 planning 文件的关键 required/forbidden literals、conflict markers 和 SHA-256。该证据只证明文档合同，不是实现或实验证据。
- Planning 收尾后再次从磁盘核验：44 checks、0 failures、exit 0；新增检查包含 task-plan 完成/待复审状态和 progress evidence。协议文件 hashes 与首次核验一致。

## 2026-08-11 Phase 5B-R4-R independent review（初步）

- Pilot-only family matrix、pilot-only split rule、`pilot_family_matrix_hash` / `pilot_split_assignment_rule_hash` 与 `pilot_nonformal` identity 在 experiment、instance、pilot、manifest 和 Gate P2 中均有直接文本证据。
- Manifest schema 将 `manifest_scope` 固定为四个枚举、`matrix_scope` 固定为 pilot/formal，并以 scope-aware canonical hash + pilot receipt alias 避免把 pilot hash 误称为 complete formal matrix hash。
- Promotion prohibition 覆盖重标、复制、链接、family/instance identity、file hash/path/file identity/generation identity；formal runner 明确拒绝 `pilot_nonformal`，并要求 pilot-artifact exclusion receipt。
- 生命周期已收窄为：pilot-only matrix/rule 在 pilot generation 前冻结；complete formal matrix/rule 在 pilot 后、任何 formal instance generation 前冻结；pilot 不创建、读取、hash、访问或推断 final-test identity/content/performance。
- Gate P1/P2 与 Gate B 权限分离清晰；当前三者均未因文档修订自动关闭，真实 provider 与 final-test 继续禁止。
- 待最终核对点：formal exclusion receipt 保存 matrix/rule hashes，但 manifest 第 7.3 节的逐项拒绝列表需确认是否以“pilot hash”总括覆盖 matrix/rule hash，还是存在实现者可忽略这两项的轻微歧义。
- 旧口径检索未发现无作用域的“任何实例生成前冻结 complete matrix”、`formal pilot` 或 Gate P planning/execution 合并表述；唯一 `full formal matrix hash` 出现在明确限定 formal branch 的说明中。
- Gate P1 的 bullets 描述获准后的 planning scope，Gate P2 才列实际执行前条件；Gate B 全部 EXEC-BLOCKING 与 REAL-LLM-BLOCKING 仍未关闭。`experiment_protocol.md` 的“须先通过 independent review”可由本轮 verdict 满足，但不自动满足 Gate P2 或 Gate B。
- Formal exclusion 的总体合同在 experiment/instance/lockbox/no-go 中均使用 “pilot IDs/hashes/paths/file identities/generation identities” 总括；因此 matrix/rule hash 未在 manifest §7.3 第 12 项逐名列出更适合作为 **Consider** 文档精化，而非阻止 Phase 6A planning 的 Required。
- Formal joint preflight 除现有 train/dev/final cross-split checks 外，还需要加载 pilot artifact exclusion evidence，拒绝 pilot family/instance IDs、file hashes、canonical paths、file identities、generation identities 或 source references 出现在 formal manifests。

### Final verdict

- **Critical：** 无。
- **Required：** 无。上一轮 pilot/formal family-matrix lifecycle 冲突已关闭。
- **Consider：** `manifest_spec.md` §7.3 第 12 项可在未来文档精化时把 pilot `family_matrix_hash` 与 `split_assignment_rule_hash` 明确加入逐字段 rejection list。当前 exclusion receipt 已保存 manifest/matrix/rule hashes，且 experiment/instance/lockbox/no-go 均要求拒绝 pilot IDs/hashes/path/file identity/generation identity，因此不构成 Phase 6A planning blocker。
- **FYI：** 16/16 review matrix PASS；Gate B 仍有 36 个开放 `EXEC-BLOCKING`，真实 LLM 仍有 2 个开放 `REAL-LLM-BLOCKING`。文档 approval 不是 pilot execution、formal experiment 或 provider authorization。
- **Gate：** 允许进入 Phase 6A mock/file closed-loop planning；Phase 6A 中只能规划，不能执行 pilot。真实 LLM/provider、正式/大规模/final-test 实验继续禁止；Phase 6A planning 前无需再修研究协议。

## 2026-08-07 Phase 5B-R3 修订合同

- Required 1 的唯一边界：generated-method 的 candidate/operator/attribution/result-row 局部失败属于 method outcome，对应预注册 cell 取 0；objective、input、split、hash、formal manifest、lockbox 或 baseline-pairing integrity 失败属于实验完整性问题，整批 contaminated/inconclusive，不进入主效果估计。
- “Manifest violation”不得再作为跨层级泛称。局部 malformed result row 只有在不影响 dataset/objective/split/lockbox integrity 时才是 cell-local；任何 final-test integrity 影响都必须 batch-level fail closed。
- Failure-zero 是 generated-method policy estimand；contamination/inconclusive 是实验完整性状态，二者不得混用、互相替代或通过补零挽救。
- Required 2 的生命周期分层：Phase 6A/mock/file/train-dev-only pilot 只加载 smoke/train/dev manifests，绝不创建/读取 final-test；formal gate 才联合 train/dev/final-test，生成三-manifest receipt 并执行 cross-split identity/path/hash/lockbox 检查。
- Formal joint receipt 必须先于 formal prompt/operator generation、formal train/dev evaluation、formal portfolio selection 与 final-test run；Phase 6A 不因文档修订而获准，也不接触 final-test。
- Consider：family-level strict rate 后续实现建议命名 `fully_attributable_family_rate`；baseline pairing 缺失明确为 batch-level inconclusive；unsupported hardlink/file identity 在 formal execution 继续 fail closed 或使用预注册豁免。
- Phase 5B-R3 文档合同核验结果为 27/27 PASS；这只证明规格文本一致，不证明 runner/analysis implementation 已存在，也不关闭任何 execution gate。


## 2026-08-07 Phase 5B-R2-R2 当前版本独立复审（初步）

- 当前磁盘版本仍定义 `cell(r,c,f,i,s)`、partial failure `delta_rcfis=0`、互斥 precedence、全 seed/replicate/family/run 聚合、supplementary-only complete-case、五项 rate 与 policy-estimand/non-attribution 边界。
- 当前 manifest 仍要求三 split manifests + joint-preflight receipt，并覆盖跨 split exact-byte hash、canonical path、family/generation identity、split/lockbox mismatch、file identity unsupported policy 与 family-ID non-bypass。
- **Required candidate 1 仍存在：** `localized manifest violation` 映射 cell=0，但 `objective/hash/manifest mismatch` 又使 batch contaminated；没有互斥类型或 scope 判据。
- **Required candidate 2 仍存在：** manifest joint preflight 要求先于任何 train/dev evaluation/prompt/selection，而 governing experiment flow 仍规定 train/dev pilot 时“不创建或接触 final-test”。Gate B 与旧 lockbox checklist 仍未要求 joint receipt/file-identity authority。
- 以上是磁盘文本的重新读取结果，不沿用上一轮 verdict 作为证据；最终定级待本轮 review matrix。

### Phase 5B-R2-R2 最终 verdict

- **Critical：** 无。
- **Required 1：** Partial method failures 的 zero mapping 本身完整，但 `manifest violation` 仍不唯一：`localized manifest violation → cell=0` 与泛化的 `objective/hash/manifest mismatch → batch contaminated` 同时存在，未定义互斥类型与 scope。因此用户检查项 2 未通过。
- **Required 2：** Joint preflight 本身完整，但 lifecycle/governing gates 仍冲突：preflight 必须先于任何 train/dev evaluation，而 experiment flow 要求 pilot 时不创建/接触 final-test；Gate B/旧 lockbox checklist 仍缺三 manifest receipt、cross-split file identity/generation checks 与 unsupported-identity exemption。因此用户检查项 18 未通过。
- **Consider：** `family-level evaluable rate` 的冻结定义是“全部 cells attributable success”，可在 schema/table 中改名 `fully_attributable_family_rate`；baseline pairing 缺失继续使用独立 batch-inconclusive status。
- **FYI：** 18 项 matrix 中 16 PASS；cell、failure-zero retention、fallback non-attribution、aggregation、whole-run、supplementary complete-case、five rates、policy estimand、joint load/cross-split checks、ID non-bypass、file-identity policy、preflight ordering、H1a gate 和执行禁令均有直接证据。
- **Gate：** Request changes（0 Critical、2 Required）；不允许进入 Phase 6A，真实 LLM/provider、正式/大规模/final-test 实验继续禁止。


## 2026-08-07 Phase 5B-R2-R 独立复审（初步）

- Evaluation cell 已明确为 `evolution_run × method_condition × final_test_family × instance_replicate × solver_seed`，每个预注册 generated-method cell 必须有 analysis value。
- Timeout、invalid、fallback、execution/deployment blocked、missing、localized manifest violation、evaluator/runtime error 与 no-attribution 均映射为 `delta_rcfis=0`，并有互斥 primary-status precedence。
- 聚合链明确保留全部 solver seeds、replicates、final-test families 和 scheduled evolution runs；whole-run failure 是全 cells 为 0 的退化情形。Complete-case 仅 supplementary。
- 五项强制报告 rate 已给出固定分母，failure-zero 明确是 policy estimand 而非物理 penalty；fallback baseline 不得归因。
- Formal runner 现在要求三份 split manifests 与 joint-preflight receipt；merged-record checks 覆盖跨 split ID/hash/canonical path/file identity/family/generation identity/split/lockbox/path safety。
- File identity unsupported 时 formal final-test 默认 fail closed，只有预注册 stronger-control exemption 可继续；`family_id` 不能豁免 duplicate exact-file。
- **待定 Required candidate：** `statistical_analysis_plan.md` §4.2 将 `localized manifest violation` 作为 cell=0，§9 又将未限定范围的 `objective/hash/manifest mismatch` 作为整批 contamination。若没有统一定义“cell-local result artifact violation”与“input/objective/lockbox integrity violation”，相同事件可能被实现为 cell=0 或整批不出 confirmatory estimate。
- **待定 Required candidate：cross-document joint-preflight 顺序冲突。** `manifest_spec.md` §7.1/7.4 要求 joint preflight/receipt 先于任何 train/dev evaluation、portfolio selection 或 prompt generation；`experiment_protocol.md` §6 step 3 却要求先运行 train/dev pilot 且“不创建或接触 final-test”。两者不能同时执行。必须明确在任何设计性 train/dev 工作前生成并密封 final-test manifests、由隔离 preflight 只返回 receipt，或收窄 joint-preflight 的适用阶段并保持用户批准的 leakage policy。
- **待定 Required candidate：formal gate 尚未同步 joint authority。** `experiment_no_go_checklist.md` Gate B 和 `final_test_lockbox_protocol.md` 的执行清单仍只要求单 manifest/hash、family/instance split 不相交与 exact allowlist，没有强制三 manifest joint receipt、跨 split duplicate exact-byte hash/canonical path/file identity/generation identity 和 unsupported-identity exemption。未来可能在未满足 Phase 5B-R2 新合同的情况下误关 Gate B；建议与上一项合并修订。
- **待定 Consider：** baseline pairing 缺失被定义为 batch `inconclusive`，是对“每个预注册 cell 都有 analysis value”的合理 denominator guard，但建议在实现 schema 中区分 generated-cell method failure 与 baseline/infrastructure batch invalidity。
- **待定 Consider：** 当前 `family-level evaluable rate` 实际定义为“该 run×condition×family 的全部 cells 都 attributable success”，更接近 fully-attributable-family rate。公式已唯一，不影响估计量，但实现/论文列名宜避免把“至少一项可评价”误读为同一指标。

### Phase 5B-R2-R 最终 verdict

#### Critical

- 无。当前仍是未执行的协议文档，且 Gate B、真实 LLM 与 final-test 均保持关闭；没有已发生的数据泄漏或正式结果污染。

#### Required

1. **Manifest failure 层级仍不唯一。** `statistical_analysis_plan.md` line 58 把 `localized manifest violation` 映射为 cell=0，line 170 又把未限定范围的 `manifest mismatch` 定义为 batch contaminated。当前没有结构化判据说明 result-row/attribution manifest failure 与 objective/input/split/hash/lockbox integrity failure 的边界；这会改变某事件是进入主估计量为 0，还是使整批不产生 confirmatory estimate。
2. **Joint-preflight 生命周期与 governing gates 未同步。** `manifest_spec.md` line 173/211 要求 joint preflight/receipt 先于任何设计性 train/dev evaluation、prompt generation、portfolio selection 和 final-test run；`experiment_protocol.md` line 120 却要求 train/dev pilot 阶段“不创建或接触 final-test”。此外 Gate B 与旧 lockbox execution checklist 尚未要求三 manifest receipt、cross-split exact-file/path/file-identity/generation checks 和 unsupported-identity exemption。协议无法同时执行，且未来可能误关 Gate B。

#### Consider

- 将当前严格的 `family-level evaluable rate` 在 schema/table 中命名为 `fully_attributable_family_rate`，同时保留 “any attributable cell” 诊断，减少读者误解；不改变现有公式。
- Baseline pairing 在固定 retry 后缺失时整批 `inconclusive` 是合理的 denominator guard；实现时应与 generated-method cell failure 使用不同 status namespace。
- Joint preflight 在 sealed boundary 暴露的 receipt 应保持最小化；三 manifest hashes 可审计，但任何 family/geometry-derived metadata 不应流向 prompt/selection。

#### FYI / passed

- 16/16 用户列出的核心控制均有直接文本证据：cell、partial failure-zero、无 cell deletion、全 seed/replicate/family 聚合、whole-run 退化、supplementary complete-case、五项 rates、policy estimand、joint load、cross-split checks、file-identity policy、family-ID non-bypass、preflight ordering、H1a gate 和所有执行禁令。
- Verdict：**Request changes（0 Critical、2 Required）**。在两项跨文档冲突关闭前，不允许进入 Phase 6A。


## 2026-08-07 Phase 5B-R2 修订合同

- 上轮复审为 0 Critical、2 Required；二者均是进入 Phase 6A 前的研究协议阻断项。
- Required 1 是缺少 **partial evaluation-cell policy**：已有 whole-run failure 记 0 的规则，尚不能唯一决定“portfolio 已部署但部分 cells 失败”的主估计量。
- 本轮将 cell 冻结为 `evolution_run × method_condition × final_test_family × instance_replicate × solver_seed`；每个预注册 generated-method cell 必须贡献可归因的 relative improvement，或对预注册失败状态贡献 policy value `0`。
- 失败记 0 是 intention-to-evaluate 风格的 policy estimand，不是物理 makespan 惩罚。fallback baseline 输出不能归因于 generated operator，质量估计必须与 deployment/failure rates 并列报告。
- Required 2 是缺少 **joint train/dev/final-test manifest preflight**：逐 split 验证无法排除跨 split 的重复内容、路径别名、family 泄漏或 lockbox 标签矛盾。
- Joint preflight 必须由 lockbox-aware 边界在任何 train/dev evaluation、prompt generation、portfolio selection 或 final-test execution 前完成；下游 train/dev/LLM 组件只接收 pass/fail receipt 与 hashes，不接收 final-test records。
- 跨平台 inode/hardlink 检测能力是剩余风险。若不支持，formal final-test 必须 fail closed；只有预注册 stronger hash/path/storage controls 的豁免才可继续，smoke/demo 只能 warning 且不得形成正式结果。

### Phase 5B-R2 文档修订结果

- **Required 1 已关闭（待独立复审）：** `statistical_analysis_plan.md` 现在冻结完整 `run × condition × family × replicate × solver_seed` cell grid。成功且可归因的 generated result 才计算 relative improvement；timeout、invalid、fallback、blocked、missing、manifest violation、evaluator/runtime error 与无归因结果均取 policy value 0。
- Cell primary failure 使用固定 precedence，额外 evidence 仅作 multi-label diagnostics。Seed→replicate→family→evolution-run 的每一级都包含全部预注册 cells；whole-run failure 是全 cells 为 0 的退化情形，不再是另一套规则。
- Complete-case valid-cell analysis 仅为 supplementary；主结果强制并列 cell failure、family-level evaluable、run-level deployable portfolio、fallback、attributed generated success rates，以及 two-part/dominated sensitivity。
- **Required 2 已关闭（待独立复审）：** `manifest_spec.md` 现在要求 formal runner 同时持有 train/dev/final-test manifests 与 matching joint-preflight receipt。Merged checks 覆盖 ID、exact-byte hash、canonical path、file identity、family、generation identity、split/lockbox mismatch 和 path alias/symlink/hardlink/traversal。
- Joint preflight 在 lockbox boundary 内先于 train/dev evaluation、portfolio selection、LLM prompt generation 与 final-test run；下游只得到 receipt/hash，不能看到 final-test records。
- **Consider 已同步：** reproducibility gate 更正为 `H1a→H6→H3`；若 H2 共享 evolution seed/provider time block，Phase 6/7 前必须预注册 paired-block bootstrap。
- **Consider 延后为 EXEC-BLOCKING：** joint-preflight parser/runner、cell ledger/analysis implementation、platform-specific file identity 与 exemption enforcement 尚未实现；本轮不进入 Phase 6A，也不产生任何实验授权。
- **文档核验：** 完成前从磁盘检查 28 项 cell mapping、aggregation、rates、joint identities、lockbox isolation、unsupported file identity、H1a gate、H2 paired-block 与 result-table 合同，28/28 PASS；无 merge conflict markers。

## 审查范围与约束

- 待审查：`src/`、`experiments/`、`configs/`、`tests/`、`docs/`、`README.md`、`pyproject.toml`。
- 本阶段不重构、不实现新功能、不删除文件、不运行耗时实验。
- 允许静态阅读及必要的轻量级检查。

## 研究目标与问题定义

- 目标问题为多机器人矩形覆盖路径问题（MR-RCRP）：机器人从仓库 `(0, 0)` 出发，覆盖分配给它们的矩形任务并返回仓库，以最小化所有机器人路线代价的最大值（makespan）。
- `AGENTS.md` 将仓库描述为“已部分实现的 baseline”，强调当前阶段先稳定确定性基线；README 则记录已扩展到 ALNS、advisor 和离线算子演化。两者反映的阶段口径不完全同步，实际代码需作为事实来源继续核实。

## 项目结构

- 实际 Python 项目根目录是工作区下的 `mrta_rect_coverage/`，而非工作区顶层；用户指定的 `src/`、`experiments/`、`configs/`、`tests/`、`docs/` 均位于该子目录。
- 主包采用 `src` 布局：`src/mrta_rect_coverage/` 下分为 `core`、`heuristics`、`llm`、`experiments`、`utils`、`visualization`。
- LLM 算子演化实现集中在 `llm/operator_evolution/`，并有独立 prompts、运行时配置和 provider 抽象。
- 根级 `experiments/` 当前仅有一个算子演化包装入口；包内另有 benchmark 与 operator evolution runner。
- 测试覆盖模型加载、DP 评估、下界、求解器、邻域、LLM runtime/provider、候选加载/评估/冻结/演化闭环等模块。
- `docs/` 当前文件清单中仅见 `operator_evolution.md`。

## 核心算法流程

- README 声称确定性主链路为：实例解析/校验 → 每任务生成 8 个状态 → 分层 DP 评估固定任务序列 → 用 makespan 评估多机器人解 → 构造初解 → 局部搜索或 ALNS → 可视化/结果输出。
- ALNS 已声明包含 destroy/repair 算子、自适应权重/奖励、`improvement_only` 与模拟退火接受准则，并可选择 DP-aware insertion。
- 固定路线 DP 的层是任务位置、节点是该任务的 8 个状态；首层加入 depot→entry，层间加入前状态 exit→后状态 entry，节点加入 processing time，末层再加入 exit→depot，并回溯最优状态链。路线缓存键为任务 ID 元组。
- 多机器人评价逐路线调用 DP，目标值为各路线总代价最大值；当前评价器本身未验证任务是否恰好覆盖一次，这一可行性主要依赖构造/邻域/repair 保持。
- baseline 初解支持按 task id 轮转，或按矩形中心 `x+y` 排序后轮转；局部搜索采用 first-improvement，可选单一跨路线 relocate 或包含瓶颈 relocate、路线内 swap/2-opt、路线间 swap 的增强组合。
- ALNS 每轮流程为：构造搜索上下文 → advisor 或按权重抽取 destroy/repair → 移除固定比例任务 → repair → 仅做 1 次增强局部搜索 → improvement/模拟退火接受 → 按全局改进 8、当前改进 3、仅接受 1 计分 → 用平均得分更新算子权重。

## LLM 参与位置

- 存在两条相互区分的参与路径：
  1. ALNS 运行期 advisor 接口，用当前最优 makespan、各路线成本、瓶颈路线、近期改进和算子表现建议算子/算子对/搜索阶段；当前实现口径为 `none`、mock 或 rule-based，并非真实在线 LLM。
  2. 离线算子演化，provider 生成 repair（主）和 destroy（辅）Python 候选，经加载验证、固定基准评估、指标聚合、结构化反馈和多轮修订后冻结到 ALNS 可加载的注册表。
- 离线 provider 包括确定性 `mock`、人工文件交换 `file`、真实 `langchain_openai_compatible`；真实 LLM 依赖是可选项，核心求解不硬绑定 SDK。
- rich prompt 限制候选仅用标准库、禁止文件/网络/子进程、固定函数签名与返回 dataclass，并提示 DP-aware、瓶颈平衡、几何/HV-gap 等问题特定方向；这些是提示约束而非执行级安全边界。
- 运行期 advisor 目前只在 ALNS 中调用 `suggest_destroy_repair`；接口中的 `suggest_operator` 与 `suggest_search_phase` 并未在求解主循环独立使用。rule-based advisor 用最近 8 个 best makespan 的变化判断停滞。
- LangChain 返回先按 JSON（也允许单 dict）解析，失败后抽取 Python fenced blocks；均失败则保存原始响应并返回空候选，不中止演化轮次。

## 进化计算部分

- 当前“进化”主要是 LLM 驱动的多轮算子代码生成/修订与择优冻结，并非经典种群个体上的遗传算法；ALNS 本身通过算子自适应评分进行搜索。
- 文档明确采用 repair-first：repair 直接控制移除任务的重插入并影响 makespan；destroy 仅做较轻量的固定 repair 配套评估。
- 闭环产物包括逐轮 CSV/候选 JSON/提示词/原始回复、汇总、最佳算子注册表和趋势图；冻结结果可通过配置接入 ALNS。
- ALNS 内置 destroy 为 random、瓶颈路线、geometry-aware；repair 为 greedy、regret-k、瓶颈平衡和 `dp_aware_insertion`。但代码中的 `dp_aware_insertion` 当前只是直接调用 greedy，而 greedy 本身已经对每个插入位置执行完整路线 DP，因此两者行为实质相同，命名上的消融区分可能不足。
- geometry-aware destroy 以矩形长宽比、水平/垂直处理时间差和瓶颈路线权重打分；所谓 bottleneck balancing repair 在 makespan 上附加路线成本绝对偏差惩罚。
- 冻结算子通过注册表路径动态导入；运行异常被捕获并分别回退到 greedy/random。动态导入失败也被静默忽略，这提高鲁棒性但削弱错误可见性。
- 已冻结示例算子是 template 级：destroy 移除展平任务序列前若干项；repair 优先非瓶颈路线并按任务数最少追加，未调用路线 DP。
- 候选验证流程是动态导入 → 精确参数名/顺序检查 → 空任务 dummy smoke test；它不会静态检查提示中禁止的 import、I/O、网络或子进程，也不会在隔离进程执行。
- repair benchmark 从 round-robin 完整解的瓶颈路线末端确定性移除约 30% 任务；destroy benchmark 用候选移除后配固定 DP 贪心 repair。每个候选跨实例和种子聚合 delta、相对改进、成功率、运行时间、软超时、错误率和无效解率。
- 关键指标问题：repair 的 `makespan_delta` 计算为“部分解 makespan − 修复后完整解 makespan”。由于修复会加回任务，通常天然为负；`success` 要求该值为正。这并不是相对原完整解或统一 repair baseline 的改进，可能系统性错误评价 repair 候选。
- `top_k_to_keep` 出现在 `EvolutionLoopConfig` 和 YAML 中，但当前演化主循环没有使用；feedback builder 自己固定默认 top-2，演化也没有保留/变异显式种群，只把排行榜摘要反馈给下一轮 LLM。
- 最佳算子按 `avg_relative_improvement` 单指标跨轮选择；排序未优先排除 invalid/error/timeout，虽然无效候选被赋 0、错误率 1，但当所有有效候选得分为负时，无效候选的 0 可能反而被选为 best。

## 任务分配建模

- 输入文件名遵循 `R{robots}_T{tasks}_{rep}.txt`，内容包含任务/机器人数量、扫掠宽度、速度、转弯时间及各矩形边界；文件名元数据必须与内容一致。
- 每个矩形任务生成 `4 个入口角 × 2 种扫掠模式 = 8` 个状态。水平/垂直模式的扫掠次数分别由矩形高/宽除以扫掠宽度向上取整，处理时间由扫掠距离/速度与转弯时间组成；出口角由模式、入口角和扫掠次数奇偶性确定。
- 机器人在矩形之间的移动采用曼哈顿距离；`CostMatrix` 预计算 depot↔状态以及不同任务状态之间的 exit→entry 成本。速度只用于矩形内部处理时间，跨任务移动距离没有除以速度，意味着当前总成本混合了“移动距离”和“覆盖时间”；这需确认是否隐含单位速度假设或建模遗漏。
- 解表示仅为 `routes: List[List[int]]`；状态选择不编码在解中，而是在每次路线评价时由 DP 联合优化。

## 实验入口、配置与测试

- 主程序文档入口：`python -m src.mrta_rect_coverage.main --config configs/default.yaml`。
- 离线算子演化入口有包内模块和根级薄包装脚本；mock 示例支持轮数与 `--freeze-best`，LangChain 另有 YAML 配置。
- `default.yaml` 实际默认选择 `alns`（200 迭代、模拟退火、DP-aware insertion），与 README 中“Default config keeps baseline mode enabled”矛盾；`small_demo.yaml` 也选择 ALNS，并启用 stronger local search 与 rule-based advisor。
- `operator_evolution_langchain.yaml` 配置 3 轮，每轮 3 个 repair/2 个 destroy 候选，对全量匹配实例用 seeds `[0,1,2]`，超时阈值 2000 ms，保留 top-2；环境变量承载模型/API 配置。
- 算子候选安全当前只做到接口级校验，无沙箱；超时仅测量而非强制终止；LangChain provider 同步执行。这是运行真实 LLM 生成代码时的重要研究与安全限制。
- batch benchmark 的 5 个模式为 `baseline`、`baseline_stronger_ls`、`alns`、`alns_dp_aware`、`alns_advisor`；逐实例记录 robots/tasks/rep、makespan 和 runtime。ALNS 三个模式固定 180 迭代、模拟退火，但没有多随机种子、最优性 gap、方差或显著性统计。
- 可用实例目前仅 `R2_T6_0.txt` 与 `R2_T10_0.txt`，规模和重复数很小；尚不足以支持稳健的算法比较或泛化结论。
- 脚本入口包括跨平台 demo 脚本以及 mock 算子演化脚本；后者默认 2 轮、每轮 3 repair/1 destroy、匹配全部实例并冻结 best。
- 已有输出表明主求解曾生成 `R2_T10_0` 的 solution、convergence、operator usage 图。
- 当前落盘的算子演化 `round_000` 中 3 个 repair 和 2 个 destroy 全部标记 `invalid`、error/invalid rate 为 1，但 `best_operators.json` 仍选择了 invalid 的 repair/destroy，并已有对应冻结 template。这实证确认了 best 选择未过滤 invalid 的风险；这些结果不能视为有效演化证据。
- `pytest --collect-only -q` 成功收集 82 个测试（0.20s），覆盖基础建模、DP/cache/lower bounds、构造与邻域、ALNS/advisor、benchmark、LLM runtime/provider/parsing/prompt、候选验证/评估/冻结/ALNS 接入；仅出现外部 `pyreadline` 的弃用警告。按用户要求未执行测试主体。
- 测试多数是 smoke/形状/非负性契约；算子 evaluator 测试只检查指标字段存在，没有断言 repair 指标方向、invalid best 排除、超时隔离或实际性能提升，因此上述研究有效性问题不会被现有测试捕获。

## 风险、缺口与未决问题

- 工作区顶层存在 `.git/` 目录，但在顶层和实际项目子目录运行 Git 状态命令均报告“not a git repository”；后续不能依赖 Git 来核对变更范围，需用文件清单与时间/内容核对。
- 三份规划文档按初始工作目录创建在工作区顶层；实际代码项目位于其子目录。鉴于用户要求不删除文件，本阶段继续将工作区顶层作为规划文档位置，并以 `mrta_rect_coverage/` 为代码审查根目录。
- 配置项允许任何非 `alns` 的算法字符串走 baseline 分支，缺少显式枚举校验；需结合 `config.py` 进一步核实。
- 真实研究消融中 `greedy_insertion` 与 `dp_aware_insertion` 目前没有算法差异，可能导致“ALNS vs ALNS DP-aware”标签无法归因。
- 外部算子异常/导入失败大多静默回退，实验汇总若未显式记录回退次数，可能把 baseline 回退结果误归因于生成算子。
- repair benchmark 的参照量定义疑似不成立，应在开展论文级实验前优先确认并重设公平 baseline。
- `top_k_to_keep` 未接入闭环，当前“进化保留”主要停留在反馈文本而非显式精英保留。
- prompt 安全约束未由 loader 强制执行，真实 LLM 候选具有任意 Python 代码执行风险。
- benchmark 缺少多规模、多重复实例、多随机种子与统计检验，当前输出不足以支撑论文级比较。
- README、`AGENTS.md` 与默认 YAML 对项目阶段/默认算法的描述不一致，应在确定真实研究主线后统一。
- 配置解析缺少算法、接受准则、比例、迭代数、DPI 等参数的范围/枚举校验；相对 config 文件的 `base_path` 参数目前未用于解析路径，所有相对路径都固定相对项目根。
- Phase 3 只读复核发现：destroy evaluator 在 repaired solution 无效时仍可能把正 delta 计入 `success_rate`；selection 会因 `invalid_solution_rate` 排除该候选，但指标语义仍不一致。应先补 RED 测试再修正。
- `top_k_to_keep` 已限制反馈数量，但 feedback builder 当前仍从全部 rows 排序，invalid/error/timeout 候选在特定分数分布下可能进入 `top_operators`，从而误导下一轮 revision。应在后续 TDD 中明确 top/weak 是否只来自 eligible pool。
- frozen operator 的缺文件、缺函数、导入异常和运行异常已可观测，但无可用 import spec/loader 的分支仍会静默返回；registry 文件本身不存在也仍按“未启用”处理。需明确后者是允许的可选配置还是配置错误。
- evaluator timeout 仍是执行完成后的软标记，不是隔离进程的硬超时；fallback 当前以事件列表输出，次数可推导，但尚未生成独立 count/reason histogram 或实验 CSV 字段。
- frozen wrapper 只捕获异常，尚未对返回对象结构和最终解 feasibility 做强校验；这属于候选执行安全与验证边界，不在本轮最小 GREEN 范围内。

## 关键文件索引

- `mrta_rect_coverage/AGENTS.md`：项目阶段约束、输入格式和建模规则。
- `mrta_rect_coverage/README.md`：整体能力、入口和研究扩展说明。
- `mrta_rect_coverage/configs/*.yaml`：主求解与算子演化参数。
- `mrta_rect_coverage/docs/operator_evolution.md`：离线算子演化闭环、provider、输出和限制。
- `mrta_rect_coverage/experiments/operator_evolution_runner.py`：包内 runner 的薄包装。
- `mrta_rect_coverage/src/mrta_rect_coverage/main.py`：配置驱动的 baseline/ALNS demo 主入口。
- `mrta_rect_coverage/src/mrta_rect_coverage/core/`：实例、状态、成本矩阵、路线 DP、解评价与下界。
- `mrta_rect_coverage/src/mrta_rect_coverage/heuristics/`：构造、局部搜索、ALNS 与冻结算子接入。
- `mrta_rect_coverage/src/mrta_rect_coverage/llm/operator_evolution/`：候选生成、验证、评价、反馈、多轮演化和冻结。
- `mrta_rect_coverage/src/mrta_rect_coverage/experiments/benchmark_runner.py`：5 模式批量消融入口。
- `mrta_rect_coverage/tests/`：82 个可收集测试。
- `mrta_rect_coverage/outputs/operator_evolution/`：已有但当前全部候选无效的演化产物。

## 2026-07-21：LLM 算子演化正式规格复核

- 已批准采用“规范性工程契约 + 论文研究协议”的混合设计：工程部分用 MUST/SHALL 风格定义门禁、产物和验收；研究部分定义贡献、消融和成本证据。
- 当前实现已具备 repair 对固定 greedy repair 的完整解比较，且 `makespan_delta = baseline - candidate`，正值表示候选更优；destroy 使用候选 destroy + 固定 greedy repair 与原完整 incumbent 比较。
- 当前 best selection 与 freeze 已排除 validation invalid、error、timeout 和 invalid solution；所有候选不合格时 best 可为空。正式规格进一步要求显式输出 `no_valid_candidate`，防止语义含混。
- `top_k_to_keep` 当前实际控制 feedback 中保留数量，但尚不是带 lineage、去重和 diversity 的显式精英种群；论文中不得把现状直接描述为完整 EA elite retention。
- candidate loader 仍在主进程通过 `importlib` 执行候选，再检查签名和 dummy smoke behavior；prompt 中的安全约束不是执行边界。
- 当前 timeout 仅在候选返回后按 wall time 标记，不能终止挂起或恶意候选；正式规格要求隔离进程与硬超时。
- 当前评价输出缺少完整逐 trial 审计、stdout/stderr、exception 类型、exit code、code hash、sandbox 环境和版本化 manifest。
- 当前 feedback 从全部 rows 排序，仍可能把不合格候选写入 top/weak 反馈；应在后续 TDD 中先明确 eligible pool。
- destroy evaluator 中 invalid repaired solution 仍可能因正 delta 计为 success；正式规格规定 invalid/error/timeout/fallback 与 success 互斥。
- frozen fallback 已有部分事件列表，但还缺 aggregate count/rate/reason、污染 run 标记、registry hash 验证和返回解 feasibility 强校验。
- 本轮读取时 `docs/modeling_decisions.md` 与 `docs/evaluation_protocol.md` 不存在，与此前 Phase 2 请求不一致；这属于现有文档状态缺口，本轮未扩大范围补建。
- 正式规格将研究主线固定为：baseline 稳定化 → ALNS 研究 → LLM 离线算子演化论文。真实 LLM 大规模实验必须晚于安全边界和可复现 benchmark。

## 2026-07-22：Phase 4 GREEN 根因分析

- RED 的共同根因不是缺少几个输出字段，而是候选执行边界位于错误位置：`candidate_loader` 当前先在主进程 `exec_module`，随后才检查签名和 smoke；evaluator 再直接调用已经导入的生成函数。
- 因此单纯在 evaluator 外围计时无法形成硬超时；候选已经能够在 import、smoke 或 benchmark 阶段阻塞主进程。
- 最小修复边界应把 AST 检查放在任何 import 前，并让文件候选保持为 path-based proxy；import 和 call 均在可终止子进程内完成。
- Windows `spawn` 启动成本不应混入候选算法的 100 ms budget。执行协议需要先等待子进程完成受限 import/ready，再从发送 call 指令开始计算候选 runtime；import 本身使用独立硬上限。
- Phase 3 的可信 in-memory callable 测试仍可直接执行，因为闭包在 Windows spawn 下不可序列化；这条兼容路径不得用于 provider 持久化的 LLM candidates。
- frozen fallback 的根因是 wrapper 只返回内置结果并追加事件，主循环随后仍按原 frozen operator 名称更新 reward。最小修复可用每次迭代前后 fallback event 数量判定污染，只把该次 generated operator reward 置零，不改变接受或搜索逻辑。
- Windows `Path.write_text` 可能将 `\n` 落盘为 CRLF；若 candidate record 对规范化源码字符串计算 hash、freeze/deploy 对原始 bytes 计算 hash，同一代码会被误判篡改。Phase 4 统一采用 UTF-8 `read_text` 后的规范化源码 SHA-256。
- 自审发现仅禁止直接 `open(...)` 仍可被 `builtins.open`、`importlib` 或 `inspect` 绕过；最小 denylist 已补充这些明显动态加载/反射根，并禁止属性形式的 `open/eval/exec/compile/__import__`。这仍是静态门禁而非完整 OS sandbox。
- 文件候选现在不再把 generated function 导入 orchestrator；loader 返回 path-based proxy，smoke 和 benchmark 分别在 spawn 子进程中 import/call，父进程可在 deadline 后 terminate/kill。
- timeout budget 从子进程完成 import 并 ready 后开始计算；candidate import 另有 1 秒硬上限，从而避免 Windows spawn 开销误伤 100 ms 算法预算。
- round candidate record 现包含 `validation_status`、`execution_status`、`fallback_used`、`fallback_reason`、`runtime_ms` 和规范化源码 `code_hash`；selection 明确输出 `no_valid_operator`。
- freeze 同时检查 eligible 状态和源码 hash，并把 hash 写入 registry；部署端对提供 hash 的 registry entry 再校验，hash mismatch 记录为 import-stage fallback。
- frozen runtime fallback 仍允许内置算子完成求解，但本迭代 history 标记 fallback，`llm_operator_success=False`，对应 generated operator reward 置零；接受判定和解更新不变。
- 剩余风险：AST denylist 不能替代操作系统级 sandbox；子进程尚未限制 CPU/内存，也未捕获/限流 stdout/stderr；可信 in-memory callable 兼容路径仍是同进程软计时，只应用于单元测试，不应接收 provider/LLM 代码。
# Phase 4 GREEN 代码审查（2026-07-31）

> 审查范围：operator execution boundary 的 validator、isolated execution、evaluator、selection、freeze/registry 与 ALNS frozen-operator adapter。以下为审查中的证据化结论；本轮不修改生产代码。

## Critical

- **候选评测使用了可终止的子进程，但还不是能力隔离的 sandbox。** `candidate_security.py` 采用模块/调用名 denylist；别名和未列入清单的等价能力仍可能绕过，例如从允许模块导入文件打开函数，或通过未禁网络模块访问网络。子进程还继承宿主环境、工作目录、文件系统和网络权限。硬超时能停止挂起进程，但不能阻止其在超时前读取文件、泄露环境变量、访问网络或制造副作用。因此当前边界只适合可信/mock 候选，尚不满足运行真实 LLM 生成代码的安全前置条件。
- **冻结后的生成算子绕过了候选执行边界。** `ALNSSolver` 直接在主进程中动态导入并调用 frozen operator；registry 缺少 `code_hash` 时仍允许加载，也没有在部署时重新执行 AST 校验或硬超时。冻结是晋级状态，不应等同于把不可信代码提升为可信代码；当前路径可令主求解进程被挂起或执行未经校验的能力。
- **frozen operator 的返回值缺少强 feasibility/contract 校验，可能污染搜索与奖励。** repair wrapper 直接返回 `result.solution`，destroy wrapper 直接返回 partial solution/removed tasks；没有在进入 evaluator、接受判定和奖励更新前验证任务恰好一次、路线数量、removed-set 一致性等。一个“正常返回但不可行”的生成算子可能被计为 `llm_operator_success`，并获得 operator reward。

## Required

- **失败分类字段存在，但聚合率没有保持同一语义。** evolution loop 为 validation-invalid 行统一写入 `error_rate=1`、`invalid_solution_rate=1`、`timeout_rate=0`，即使实际 `execution_status` 是 `validation_failed` 或 `timeout`。这会把互斥失败类型重复计数，并使失败反馈与论文统计失真。
- **fallback 的零奖励只按发生 fallback 的算子类型处理，配对评价仍可能交叉污染。** 同一 ALNS 迭代中，若 frozen destroy fallback、frozen repair 正常返回，repair 仍可能获得由 fallback destroy 共同产生的分数（反之亦然）。尽管迭代级 `llm_operator_success` 会置为 false，但 operator reward 归因仍不干净。
- **加载失败前的文件读取不在受控错误路径内。** `load_and_validate_candidate()` 在 `try` 之前读取候选源码；文件缺失、编码错误或读取失败会直接中断流程，而不是形成带 `validation_failed`/`runtime_error`、`code_hash` 和原因的候选记录。
- **隔离执行未捕获或限制 stdout/stderr，也没有 CPU/内存/进程树限制。** 候选可污染实验日志或造成资源耗尽；当前记录也缺少子进程退出码和截断后的输出摘要，难以审计失败原因。

## Consider

- 每个 smoke test 以及每个 candidate × instance × seed trial 都重新 spawn/import 一个 Python 进程；Windows 上固定开销可能显著。可考虑“每候选一个可回收 worker、逐 trial 消息调用，timeout 后销毁 worker”，同时分别记录候选函数耗时和端到端 wall time。
- AST 对任意对象的 `.run`、`.call`、`.request`、`.connect` 等属性一律拒绝，容易误杀无害算法代码。后续宜以最小 import/capability allowlist、别名解析和 OS 级隔离为主，而不是继续扩大全局属性 denylist。
- `runtime_ms`、`code_hash`、`fallback_reason` 已进入候选/回退记录，但尚无 instance、seed、timeout budget、Python/依赖版本、子进程退出信息等逐 trial manifest；进入论文实验前应补齐。
- 选择摘要对“本轮没有演化该算子类型”和“演化过但无有效候选”都可能写成 `no_valid_operator`，建议区分 `not_evolved` 与 `no_valid_operator`，避免报表误读。

## FYI

- 正向部分：benchmark 路径已明确区分 `validation_failed`、`runtime_error`、`timeout`、`invalid_solution`、`success`；selection/freezing 的 eligibility gate 会排除非 success、fallback 和非零失败率候选；冻结时会核对已记录 hash；实现仅使用标准库。
- 当前测试覆盖了直接危险 import/call、100 ms timeout、全无效候选不冻结、单个 frozen operator fallback 不奖励等主路径，但尚未覆盖别名绕过、frozen 缺 hash/重新校验/硬超时、正常返回但不可行、以及 repair/destroy 配对 fallback 的交叉奖励污染。

## Phase 4B RED 测试设计约束（2026-07-31）

- `AGENTS.md` 再次确认当前阶段不得增加真实 LLM 集成或重依赖；Phase 4B RED 将只验证安全元数据、冻结部署边界、可行性与可观测性合同。
- 测试优先走真实 loader/executor/evolution/frozen-ALNS 路径。仅“不可移植地制造文件读取权限错误”允许在最低层 `Path.read_text` 使用窄范围 monkeypatch；断言对象仍是 loader 返回的真实结构化结果，而不是 mock 调用次数。
- RED 的通过标准是：新增测试均被正常收集，并因目标生产行为缺失而失败；collection/import/fixture 错误不算有效 RED。
- 既有 Phase 4 测试已提供可复用的真实路径：源码候选 → evolution loop → candidate JSON，以及 registry → `ALNSSolver.solve()` → history/fallback/operator stats。Phase 4B 将沿用该路径，避免只测试人为构造的字典。
- 既有 frozen integration 仅验证 freeze 产物能被注册，没有覆盖 registry metadata 缺失、部署前重校验、运行硬超时和返回值 contract；这些正是 Phase 4B 的新增边界。
- `CandidateExecutionResult` 当前只有 `status/runtime_ms/result/error_message`；没有 `sandbox_level`、`safe_to_execute`、`exit_code`、stdout/stderr、truncation 或端到端 `wall_time_ms`，可直接用真实 `execute_candidate_process()` 写 RED 合同。
- `load_and_validate_candidate()` 在构造 validation record 和进入 `try` 之前读取 UTF-8 源码并计算 hash；缺失、解码和读取异常会逸出函数，适合分别用真实缺失文件、真实非法 UTF-8 和最低层窄 monkeypatch 验证 `source_read_failed` 合同。
- 项目已有 `is_solution_complete()`，其排序比较可以检查任务全集、重复和丢失；Phase 4B repair contract 可直接复用该语义。destroy 还需额外断言 `remaining ∪ removed == original` 且二者互斥、无重复。
- ALNS 当前仅按“哪一类型产生 fallback event”给同类型 generated operator 清零，另一类型仍收到 joint score；RED 应允许两种合规设计：精确单边归因，或显式 `attribution_ambiguous=True` 且双方 generated reward 均为零。当前实现两者都不满足。
- frozen registry 当前把 `code_hash` 当可选字段，并将外部函数对象直接包入 ALNS；没有统一的 execution outcome 或 invalid status 通道。测试需要同时检查“未注册”和结构化 fallback，而不能只检查最终求解仍可完成。
- failure breakdown 当前只有三个独立布尔率，没有 `validation_failed/source_read_failed` 计数或通用 `failure_type_breakdown`；而 evolution loop 的 invalid row 固定写成 error+invalid。Phase 4B RED 应要求互斥 breakdown，并保留既有 rate 字段的向后可解释性。
- `_is_eligible()` 已能排除非 success 和非零失败率行，因此 benchmark invalid 不进入 best；新增测试重点应放在“分类正确”和 frozen deployment 产生的 invalid 是否能进入相同 gate，而不是重复已有 eligibility 主路径。
- 代码、配置与现有文档中均不存在 `sandbox_level` 或 `safe_to_execute`。最小 RED API 可要求 validation/candidate artifact 明确记录 `sandbox_level="timeout_only"`，且 real-provider (`langchain_openai_compatible`) 在该等级下 `safe_to_execute=False`；这不会要求本阶段实现 Docker/OS sandbox。
- freeze 产出的 registry 目前只有 name/type/path/round/hash，没有 validation/security metadata。Phase 4B frozen 测试应要求部署端拒绝手写的缺 metadata registry，同时保留对正式 freeze 产物未来补齐 metadata 的升级空间。
- 既有 Phase 3 fallback 回归使用缺 hash/validation metadata 的手写 registry；Phase 4B GREEN 收紧 registry 后，这些测试需要补齐可信 metadata 或改为断言 registry-validation fallback。RED 本轮不修改它们，避免提前适配实现。
- `ALNSConfig` 当前没有 frozen timeout/output budget 字段。Phase 4B RED 将先通过 registry 中的每算子 `timeout_ms` 表达硬预算，避免在本轮测试里先规定更广的主搜索配置 API。

## Phase 4B RED 验证结果（2026-07-31）

- 新增 `tests/test_operator_execution_boundary_hardening_red.py`，pytest 正常收集 27 个测试；无 collection、import 或 fixture 错误。
- 新增文件运行结果为 27 failed、0 passed，失败均能映射到审查发现的缺失生产合同：sandbox metadata、frozen metadata/AST/隔离、feasibility、reward attribution、failure breakdown、source-read status 和 process observability。
- frozen feasibility 的短回溯诊断确认：repair/destroy 不可行返回不会产生 fallback event；joint fallback 虽会按同类型清零，但没有 `reward_attribution` 或 `attribution_ambiguous` 证据，因此研究归因仍不可审计。
- 当前 RED 只要求诚实区分 `timeout_only` 和 capability sandbox；没有要求或声称已经实现 Docker、容器、namespace 或 OS 权限隔离。
- **明确剩余风险：** CPU/内存配额、后代进程树清理、文件系统/网络隔离、环境变量最小化和跨平台 sandbox 能力降级仍未覆盖；这些必须保留在 Phase 4B 后续计划与复审门槛中。

## Phase 4B GREEN 实现约束复核（2026-07-31）

- 27 个 RED 合同允许最小且一致的实现：统一使用 `CandidateProxy` 执行 frozen operator，registry 提供每算子 `timeout_ms`；ALNS 主进程只保存 proxy 和 metadata，不 import 生成模块。
- reward attribution 采用保守方案：同一 joint iteration 任一 generated operator fallback 时，标记 `attribution_ambiguous=True`，双方 generated reward 均为零；这比在联合结果上猜测单边贡献更适合研究有效性。
- `sandbox_level="timeout_only"` 是事实标签，不表示 capability sandbox；`langchain_openai_compatible` 候选在该等级下必须 `safe_to_execute=False`。
- Executor 的最小可观测实现可在 child 内用有界返回策略捕获 stdout/stderr，并由 parent 统一截断、记录 truncation、exit code 与从 spawn 前开始的 wall time；timeout 时仍可可靠记录 exit code/wall time，但被强杀前尚未回传的输出可能不可得，需作为剩余限制保留。
- Source read 必须先构造不依赖源码内容的 validation record，再在 `try` 内读取与计算 hash；读取失败使用 `failure_type="source_read_failed"`，不创建 proxy。
- Candidate rows 与 freeze registry 需要贯通 `source_provider/sandbox_level/safe_to_execute/timeout_ms`；selection 与 freeze 必须要求 `safe_to_execute=True`，因此 timeout-only 的真实 LLM 候选即使产生评测记录也不能晋级或部署。
- Frozen contract 校验放在 ALNS adapter 边界最小且不改变搜索策略：repair 要求路线数正确且任务全集恰好一次；destroy 要求 remaining 与 removed 构成原解的无重叠、无重复完整分区。
- 为兼容既有 fallback 事件精确断言，`execution_status` 只在 runtime/timeout/validation/invalid 等有明确状态的事件中追加；纯 file-not-found 等历史导入事件保持原有字段集合。
- 首次 executor GREEN 子集暴露 stderr 截断根因：标准 `warnings.warn` 在消息前加入长临时路径/行号，简单 head truncation 会在候选正文前耗尽限额。隔离 worker 应使用紧凑 warning formatter，使有限预算优先保留候选实际 warning 内容。
- 完成前自审发现“父进程截断、child 内无限 StringIO”仍可造成输出内存增长；最终实现改为 child 内 `_BoundedTextBuffer`，从写入时即限制字符数并单独回传 truncation 标志。

## Phase 4B GREEN 最终实现发现（2026-07-31）

- Frozen operator 现在只以 `CandidateProxy` 注册；ALNS 主进程不再 import 生成模块。加载前依次检查文件存在、必需 registry metadata、授权状态、规范化源码 hash 和 AST/security validation。
- Repair adapter 校验机器人路线数量与任务全集恰好一次；destroy adapter 用 multiset partition 校验 remaining/removed 的完整性、无重叠与 removed 无重复。失败统一记录 `invalid_solution` 并调用内置 fallback。
- 双 generated repair/destroy 联合试验中任一方 fallback 时采用保守归因：`attribution_ambiguous=True`，双方 generated reward 均为零；单 generated fallback 只清零该 generated operator。
- Candidate/evolution artifacts 已记录 `failure_type` 和逐 trial breakdown；validation-invalid 不再重复污染 runtime error 与 invalid solution rate。
- `source_read_failed` 在读取、解码或 OS read error 时返回结构化 validation record，不创建 callable/proxy，也不能进入 selection/freeze。
- 执行结果包含 `sandbox_level="timeout_only"`、exit code、runtime/wall time、有界 stdout/stderr 和 truncation；真实 LLM 来源标记 `safe_to_execute=False`、`requires_human_risk_ack=True`，并被 selection/freeze gate 排除。
- **仍需诚实保留：** 当前不是 capability sandbox；没有 CPU/内存、子进程树、文件系统、网络或环境变量权限隔离。timeout 强杀前尚未回传的 stdout/stderr 可能不可得，Windows spawn 开销也仍存在。

## Phase 4R 独立复审发现（2026-07-31，完成）

- 已确认 executor 的代码和文档均使用 `sandbox_level="timeout_only"`，并明确说明不会移除文件系统或网络权限；当前没有把它在实现层面误称为 capability sandbox。
- **Critical（已确认）：validation-to-execution TOCTOU。** frozen ALNS loader 只在注册时读取源码、核对 hash 并做 AST validation，随后返回仅保存文件路径的 `CandidateProxy`；每次调用时 child 再从该路径 import，且 executor 不接收/复核 expected hash。注册后替换文件即可让未验证的新源码进入子进程执行，因此 frozen operator 仍能绕过 validation/hash（虽仍受 timeout，但没有 capability sandbox）。
- **Required（已确认）：contract gate 对畸形对象不是异常封闭的。** repair 的 `_is_valid_full_solution()` 直接对 `solution.routes` 做 `len`，destroy 校验同样假定 `partial.routes` 可迭代；若生成代码返回 `MultiRobotSolution(routes=None)` 或其他畸形 shape，异常会从主进程 adapter 逸出，而不是结构化为 `invalid_solution` 并 fallback。现有测试只覆盖语义上的丢失/重复任务，未覆盖 shape/type 异常。
- **Critical（已确认）：`safe_to_execute=False` 没有阻止真实 LLM 候选执行。** loader 虽把 `langchain_openai_compatible` 标成 unsafe/需人工确认，但仍立即创建 proxy 并执行 smoke test；`_run_one_type()` 又仅按 `validation_status == "valid"` 把候选送入 benchmark，没有检查 `safe_to_execute` 或风险确认。因此真实 LLM 生成代码会在当前仅 timeout-limited、仍有文件/网络权限的子进程中执行，只是在 best selection/freeze 阶段才被排除。`requires_human_risk_ack` 目前只是记录字段，不是执行门禁。
- **Required（已确认）：selection/freezing 辅助门禁存在 fail-open 默认值。** `_is_eligible()` 对缺失 `failure_type/safe_to_execute/failure rates` 使用 success/True/0 默认值；`_is_freezable()` 同样把缺失 `failure_type` 视作 success、缺失 `safe_to_execute` 视作 True。正式 loop 当前会写齐字段，且 frozen registry 最终把缺失 safe 转为 False，但手工/旧 artifact 可被选中或复制，违背“缺安全证据即拒绝”的 hard gate 口径。
- **Required（已确认）：benchmark 对畸形成功返回没有异常封闭。** repair/destroy evaluator 在 `outcome.status == "success"` 后直接访问 result 字段并调用完整性/repair/evaluator；属性、shape 或类型异常会中断整个 evolution loop，而不是形成互斥的 runtime_error/invalid_solution trial。
- **Required（已确认）：安全文档口径不一致。** executor docstring/metadata 正确写明 `timeout_only` 且非 capability sandbox，但 `docs/operator_evolution.md` 仍声称“无 sandboxed execution、timeout 只是 soft”，已经落后于实现；正式规格把目标阶段称为 `sandboxed execution`，README 又直接给出真实 LLM 运行方式而未注明当前 `safe_to_execute`/人工风险确认并未阻断 smoke/benchmark。运行真实 LLM 前必须统一“当前能力”和“目标能力”的文档与 CLI 门禁口径。
- **Critical 的轻量证据：** 未执行候选的静态诊断显示 `from io import FileIO as F` 可通过当前 AST validator，说明“明显文件能力”仍能借助未列入 denylist 的标准库与别名进入候选；结合 real-provider 仍会执行 smoke/benchmark，timeout-only 子进程不能阻止文件访问。该结论不依赖复杂反射绕过。
- **Required 的轻量证据：** 只有 `validation_status=valid`、`execution_status=success`、`code_hash` 的缺安全证据 row，当前 `_is_eligible()` 与 `_is_freezable()` 均返回 True；`MultiRobotSolution(routes=None)` 使 frozen repair contract helper 抛出 `TypeError`。
- **FYI（验证）：** 相关 operator evolution/frozen/ALNS 测试为 66 passed、69 deselected；完整测试为 135 passed、1 个外部弃用 warning。现有测试全部通过，但没有覆盖上述 TOCTOU、unsafe-before-smoke、fail-open metadata 和畸形 shape 路径。
- **Required（registry 鲁棒性）：** `_register_frozen_operators()` 直接解析 JSON 并索引 `row["name"]`/`row["file_path"]`；registry 编码、JSON、顶层/row shape 或字段类型异常会中断 solver 初始化，而不是形成结构化 registry-validation fallback。该问题不是 validation 绕过，但不符合 frozen 加载边界的 fail-closed/observable 目标。
- **已验证有效的正向结论：** 对内部正常生成且字段完整的 candidate row，validation/source-read/runtime/timeout/invalid 均被 `_is_eligible()` 排除，freeze 也检查成功状态、fallback 与三类失败率；ALNS frozen runtime/invalid fallback 会生成事件，单 generated fallback 不获 reward，双 generated 联合 fallback 双方 reward 为零且标记 ambiguous。
- **Consider（架构）：** frozen registry、proxy、contract 和 attribution 逻辑已使 `alns_solver.py` 达 847 行。修复 Critical 后可将 frozen deployment adapter/registry validation 提取到 operator-evolution 所属模块，ALNS 只消费 typed outcome；这是可维护性建议，不是本轮安全结论的前置条件。
- **Consider（性能/复现）：** 每个 smoke/trial/frozen call 都 spawn 并重新 import；应分别记录 candidate call、IPC/import 和端到端 wall time。timeout 强杀前未回传输出、后代进程树未回收仍需保留为限制。
- **最终判定：Request changes。** 共有 2 个 Critical：真实 LLM unsafe 标记未阻断 capability-rich smoke/benchmark，以及 frozen 源码验证后可被替换并在运行时绕过 hash/AST。Phase 5 和真实 LLM 均继续阻塞。

## Phase 4C RED 测试发现（2026-07-31）

- 新增 31 个参数化后测试节点，24 个按预期 RED、7 个验证既有正确行为；没有 collection、import、fixture 或测试构造错误。
- execution gate RED 直接观察到 real-provider 候选仍调用 smoke，benchmark 收到 1 个 unsafe candidate，且 config 没有默认关闭的 `allow_unsafe_candidate_execution`。
- TOCTOU RED 观察到 proxy/executor 均无 `expected_code_hash`，替换 frozen 源码后运行期报告普通 runtime error，若替换代码可行则会被当成 generated success。
- Required RED 复现畸形 route shape 抛异常/被接受、benchmark 畸形返回中断、selection/freezing 缺证据 fail-open、registry JSON/shape/type 错误中断初始化，以及旧文档口径。
- AST 对抗组中 `io.FileIO` alias 仍被接受；pathlib/importlib/builtins/getattr/dunder-subclasses 已被现有 validator 拒绝并作为回归保留。
- 完整 `pytest -q` 为 24 failed、142 passed；24 个失败全部属于新增 Phase 4C 文件，说明 135 个旧测试未回归。当前 RED 证据足以进入后续最小 GREEN，但不构成任何 Critical 已修复的证据。

## Phase 4C GREEN 实现决策（2026-08-02，进行中）

- 执行授权作为 loader 的显式输入，默认 False；AST/source read 始终先做，真实 provider 在 timeout-only 下未授权时返回 `risk_ack_required` 且不创建 proxy、不 smoke。
- `CandidateProxy` 必须携带 `expected_code_hash`，executor/child 在 import 前核对源码文本 hash；hash mismatch 作为独立 execution status 返回，从而复用既有 ALNS fallback/reward 隔离。
- 本阶段继续使用 `sandbox_level="timeout_only"` 事实标签，不把显式人工授权解释成 capability sandbox。

## Phase 4C GREEN 完成发现（2026-08-02）

- **两个 Phase 4C Critical 已在默认路径关闭。** real-provider 候选会完成源码读取、hash 与 AST 检查，但默认返回 `risk_ack_required`，不创建 proxy、不 smoke、不 benchmark、不入选也不冻结；`allow_unsafe_candidate_execution` 默认 False，并同时接入 YAML/CLI。候选 draft 与配置任一方标识 real provider 时均按 real provider 处理，避免仅靠配置名绕过门禁。
- **Frozen TOCTOU 改为 hash 绑定的单次源码快照执行。** registry 注册时复核源码/hash/AST并把 expected hash 传给 proxy；每次 child 调用先读取一次源码、核对 hash，再从同一文本快照 compile/execute。替换文件返回独立 `source_hash_mismatch`，ALNS 记录 fallback，`llm_operator_success=False` 且 generated reward 为零。
- **Fail-closed 证据链已补齐。** selection/freezing 要求显式 validation/execution/failure/safety/risk-ack/sandbox/provider/hash 证据；缺字段、blocked、fallback 或任何非 success 状态均不可选、不可冻结。freeze registry 同步保存 failure type 与 risk-ack 字段。
- **畸形结果和 registry 不再逸出边界。** repair/destroy route shape 必须是指定数量的 list-of-list，task id 必须是严格 int，并继续验证 complete/partition；benchmark 缺字段或畸形 shape 结构化为 runtime_error/invalid_solution；损坏 JSON、错误顶层/row/字段类型转为 registry-validation fallback，不中断 solver 初始化。
- **AST 加固覆盖本轮明确绕过。** `io.FileIO`（含 alias）、pathlib/importlib/builtins、getattr/setattr/delattr、dunder/reflection 等明显能力被拒绝。该 denylist 仍不是能力隔离，不能替代 OS/container sandbox。
- **文档口径已同步。** README 在真实 LLM 命令前给出 checklist/warning，`docs/operator_evolution.md` 删除 soft-timeout 旧描述，LangChain 配置默认禁止 unsafe execution；所有位置均明确 `timeout_only` 不是 capability sandbox。
- **剩余风险（非本轮 Critical）：** 显式风险确认只代表用户授权，不会提升隔离强度；CPU、内存、环境变量、文件系统/网络权限和后代进程树仍未隔离。真实 provider 保持禁用，直到后续独立复审确认无新的 Critical；即使复审通过，也只能进入文档化协议，不能据此宣称可安全运行生成代码。
- **验证证据：** Phase 4C 专项 31 passed；Phase 4/4B/4C 合并相关测试 79 passed；operator-evolution/frozen-ALNS 集合 97 passed；完整套件 166 passed、1 个既有 `pyreadline` 弃用 warning。未运行真实 LLM/provider或实验。

## Phase 4C 独立复审工作记录（2026-08-02）

- **测试覆盖初核：** 31 个 Phase 4C 节点覆盖默认 real-provider smoke/benchmark 阻断、五类 AST 绕过、expected hash、源码替换 fallback/零奖励、四类畸形 repair shape、两类畸形 benchmark return、七类 selection/freezing 缺字段、四类 registry 损坏和两处文档口径。测试为行为型主路径，未把“绿测”本身当作完整 sandbox 证明。
- **Execution gate 初核：** `allow_unsafe_candidate_execution` 在 dataclass、YAML builder 与 CLI 中默认 False；loader 在 AST 后、proxy/smoke 前返回 `risk_ack_required`。evolution benchmark 还要求 validation/execution/failure success、safe、risk-ack false、hash、sandbox 与 callable，并对 real-provider + timeout-only 再检查 allow flag，不再只看 `validation_status`。
- **Provenance 初核：** evolution 将 config provider 与 draft source 合并；任一方声明 `langchain_openai_compatible` 都采用 real-provider 门禁，降低配置名与 draft provenance 不一致造成的绕过风险。
- **待继续核证：** schema 的 `safe_to_execute=True` 默认值虽不使 real-provider evolution 主路径失守，但属于通用 validation record 的 fail-open 默认，需结合 evaluator/freezing/frozen registry 所有入口判断是否构成 Required；还需核查 optional expected hash、child 快照执行、registry metadata 类型与 reward attribution 的完整调用链。
- **TOCTOU 正向结论：** canonical loader 与 frozen deployment 都向 `CandidateProxy` 传入非空 expected hash；child 只读取一次源码，先 hash compare，再从同一 `source_text` compile/exec，因此注册后替换路径内容不会被 import/call。mismatch 是独立 status，ALNS 运行 fallback 会进入迭代事件并使 generated success 为 false、对应 reward 为零。
- **Required 候选 1——底层 hash API 仍可 fail open：** `CandidateProxy.expected_code_hash` 默认空字符串，`execute_candidate_process.expected_code_hash` 默认 None，worker 仅在 expected hash truthy 时比较。当前 canonical 生产调用均传 hash，故未形成 frozen 主路径 Critical；但这与“path execution 缺 expected hash 应拒绝”的边界契约不一致，任何未来/旁路直接构造 proxy 都会执行未绑定源码。
- **Required 候选 2——frozen registry 加载证据不完整：** canonical freezing 会写 failure_type、source_provider、sandbox_level 与 risk-ack，但 ALNS registry loader 只强制 code_hash、validation_status、execution_status、safe_to_execute。手写/降级 registry 缺 failure/provenance/sandbox/risk-ack 仍可注册并执行，属于 deployment 边界的 fail-closed 缺口；AST/hash/timeout 仍在，因此暂不定为本轮 Critical。
- **Required 候选 3——registry 数值类型仍可中断初始化：** `timeout_ms` 未做结构/范围校验，直接 `float(...)`；字符串垃圾、None、NaN/无穷等可能抛异常或形成无效 timeout，未完全满足“字段类型错误不应中断 solver 初始化”。
- **Required 候选 4——selection/freezing 的非安全字段仍有成功默认：** 两个 helper 已严格要求用户点名的 validation/execution/failure/safe/risk-ack/sandbox/provider/hash；但 `fallback_used` 缺失默认 False，三类 failure rate 缺失默认 0。canonical evaluator 会写全字段，故正常演化不污染；对畸形/旧 artifact 仍不完全 fail closed。
- **Contract 正向结论：** frozen repair 使用 list-of-list、严格 int、机器人路线数和 complete/unique；destroy 额外检查 remaining+removed 与 original Counter 相等、互斥及 removed 无重复。invalid 均记录 `invalid_solution` fallback。
- **Consider——destroy benchmark 可补更广的畸形返回对抗测试：** 代码未先显式验证 remaining/removed partition，异常捕获也不是最终兜底；但使用未知 task id 的临时诊断已返回结构化 `runtime_error`，没有复现整轮中断，因此不把它列为当前 Required bug。
- **文档初核：** README 在真实 provider 命令之前明确 timeout-only、非 capability sandbox、隔离主机/无 secrets/无网络权限、hash review 与显式风险确认，默认未确认会 blocked。`docs/operator_evolution.md` 也明确当前边界不是完整 capability sandbox；但正式 `docs/llm_operator_evolution_spec.md` 的“当前实现差距”仍写主进程动态 import、soft timeout、缺 hash/feasibility 强校验等 Phase 4 前事实，已与当前实现冲突，列为 Required 文档债务。
- **Critical——execution allow flag 未做严格布尔校验。** YAML builder 把 `allow_unsafe_candidate_execution` 原样传入 dataclass，loader/evolution 使用 truthiness。只读临时诊断传入字符串 `"false"` 时，real-provider 候选仍调用 smoke，并被改写为 `safe_to_execute=True`、`requires_human_risk_ack=False`、`execution_status=success`。一个常见的引号/配置类型错误会把“意图关闭”解释成显式授权，因此真实 provider 执行门禁还不是完全 fail closed。
- **已证实 Required：** 临时诊断显示缺 fallback/rate 字段时 `_is_eligible=True` 且 `_is_freezable=True`；缺 failure/provenance/sandbox/risk-ack 的 registry row 会进入 `frozen_repair_ops`；`timeout_ms="not-a-number"` 会在 solver 初始化抛 `ValueError`。这些不是静态推测。

## Phase 4C 独立复审最终结论（2026-08-02）

### Critical

- `allow_unsafe_candidate_execution` 只靠类型注解和 truthiness，YAML builder 不校验严格 bool。字符串 `"false"` 可越过 loader 与 evolution gate，调用 smoke 并把 real-provider 候选标为 safe/success/risk-ack false。该问题阻止进入 Phase 5，且继续禁止真实 LLM。

### Required

- Path executor/proxy 的 expected hash 仍可为空；canonical loader/frozen path 当前正确传入，但底层边界对未来或旁路调用 fail open。
- Frozen registry loader 未强制 failure_type、source_provider、sandbox_level、requires_human_risk_ack；timeout_ms 未做类型/有限正数校验，错误字符串会中断 solver 初始化。
- Selection/freezing 对用户点名的安全字段已经 fail closed，但缺 fallback_used 和三类 failure rate 时仍默认“无失败”；canonical row 不受影响，畸形/旧 artifact 仍可能污染 best/freeze。
- 正式 `llm_operator_evolution_spec.md` 的当前实现差距仍描述主进程 import、soft timeout、缺 hash/contract，已与 Phase 4C 实现不一致，进入任何实验协议前必须同步。

### Consider

- 把 execution policy/eligibility/registry evidence 建成单一 typed validator，由 loader、evolution、freezing、ALNS deployment 共用，避免四处条件漂移；默认值应 fail closed。
- `alns_solver.py` 已达 937 行，frozen registry/proxy/contract/attribution 可后续提取为 operator-evolution deployment adapter；这是架构维护任务，不是当前 Critical 修复前置。
- 为 destroy benchmark 增加 unknown id、非 int removed、错误 partition 和 evaluator 异常对抗测试；本轮未知 id 已结构化为 runtime_error，未发现当前中断 bug。
- 每个 smoke/trial/frozen call 的 Windows spawn/import 成本仍未量化；Phase 5 以后应分别报告 candidate runtime 与端到端 wall time。

### FYI

- 对严格 bool False 的 canonical real-provider 路径，source read/AST 后会在 proxy/smoke 前返回 risk_ack_required，benchmark/selection/freeze 都被阻断。
- 本轮要求的 FileIO/pathlib/importlib/builtins/getattr/dunder 绕过均被拒绝；文档正确声明 AST denylist 与 timeout-only subprocess 都不是 capability sandbox。
- Frozen expected-hash + 单次 source snapshot 已消除已知源码替换 TOCTOU；mismatch 不 import/call，记录 fallback，不计 LLM success 或 generated reward。
- Repair/destroy frozen contract 与 canonical invalid/timeout/blocked/fallback 的 selection、freeze、reward 隔离正确。
- 新鲜验证：compileall 通过；Phase 4B/4C 边界测试 58 passed；完整套件 166 passed、1 个既有 `pyreadline` warning。绿测不覆盖上述非 bool 配置 Critical。

### Gate 结论

- **不允许进入 Phase 5 文档化实验协议。** 先修复 Critical 并复审。
- **继续禁止运行真实 LLM。** 当前仍无 capability sandbox，且 execution gate 存在非 bool 配置绕过。
- **继续禁止大规模实验。** 评价 artifact 的 fail-closed Required 与正式规格同步尚未完成。
- **Review verdict：Request changes。**

## Phase 4D RED 测试设计（2026-08-02）

- 新增测试覆盖严格 YAML/config bool、loader/evolution 执行门禁、literal True 的其余安全证据、expected-hash 底层绑定、frozen registry 完整证据与 timeout、selection/freezing 缺失字段及正式规格过期口径。
- 测试模块参数化后共 59 个节点且收集无错误；后续 RED 失败应归因于现有生产/文档合同缺口，而非 import、fixture 或收集问题。
- RED 实测为 45 failed、14 passed。严格 bool 缺口可在 runner、loader、evolution 三层复现；truthy 字符串/整数会执行 smoke 或进入 benchmark，而 falsey 非 bool 只是偶然被现有 truthiness 阻断，并不构成类型验证。
- 底层 path executor/proxy 在 expected hash 缺失时仍可执行；frozen registry 缺 8 类安全/失败证据仍可注册；timeout 对非数字/None 可能中断初始化，对 NaN/inf/非正数未 fail closed。
- Selection/freezing 对 fallback 与三类 failure rate 仍有成功默认；正式规格仍保留 Phase 4 前的实现差距描述。上述结果与 Phase 4C 复审的 Critical/Required 证据一致。
- 完整套件为 45 failed、180 passed，且所有失败节点都在新增 Phase 4D 文件中；166 个既有测试全部通过。因此当前 RED 是隔离且可归因的，适合作为后续最小 GREEN 的验收基线。
- 当前 gate 结论不变：strict bool Critical 修复并复审前，不进入 Phase 5、不运行真实 LLM、不运行大规模实验；timeout-only 边界仍不是 capability sandbox。
- 收尾核验发现完整既有 pytest 会刷新项目根的 `generated_operators/`，而新增 Phase 4D evolution 测试已正确使用 `tmp_path`。这是既有测试隔离/工作区洁净度债务，不影响本轮 45 个 RED 的行为结论，也不在本轮扩展修复。

## Phase 4D GREEN 实现定位（2026-08-03）

- 59 项合同可由一个标准库-only policy 模块集中表达：严格 bool 解析、执行/benchmark row eligibility、selection/freezing evidence、registry metadata 和有限正 timeout；调用方保留各自 I/O 与状态构造职责。
- 当前重复条件分布于 runner、candidate loader、evolution loop、freezing 与 ALNS frozen deployment。最小改法是让这些入口调用共同 helper，不重排 ALNS 搜索或 evaluator 数据流。
- Frozen artifact hardening 是双端合同：freezing 必须持久化 fallback/rates，ALNS registry deployment 必须验证同一组字段并结构化拒绝非法 timeout；只加 reader gate 会让当前 canonical frozen artifact 全部失效。
- `CandidateProxy` 与 `execute_candidate_process` 当前空 hash 会绕过校验。最小 fail-closed 行为是在创建子进程之前返回 `source_hash_missing`，从而避免任何未绑定源码被 import/compile/call。
- 既有 canonical freeze 流程使用 evaluator 产生的完整 metrics row，因此可在 freezing writer 中原样持久化 fallback/rates 并由 registry reader 强校验；无需改变 ALNS 搜索策略。
- 正式规格的主要事实冲突位于第 10 节四条旧差距（主进程 import、soft timeout、缺 registry hash、缺 feasibility），适合原位改写为当前 timeout-only/hash-bound/contract-gated 状态与仍缺 capability isolation 的风险。
- Phase 4D GREEN 采用纯函数 policy 而非把 I/O 搬入公共层：各入口仍构造自己的 validation/fallback artifacts，但是否可执行、benchmark、选择、冻结或部署由同一证据规则决定。
- Phase 4D 专项 59 项首次运行全部通过，证明 strict bool、real-provider gate、expected hash、registry/timeout、selection/freezing 与规格口径的目标行为均由生产修改满足；该结果尚不替代旧边界/完整回归。
- 四阶段回归暴露的是测试 fixture schema 迁移而非 production gate 漏洞：旧 Phase 4B/4C 用“不完整但曾被接受”的 registry row 来测试下游行为，新 policy 正确地把它们挡在 registry validation。若放宽 reader 会直接违背 Phase 4D RED；正确兼容方式是给旧 fixture 补齐成功 evidence，使其继续测试原目标路径。
- Fixture 迁移保持测试语义：direct executor 仍验证 timeout-only/输出/硬超时，只是显式绑定所执行源码；frozen tests 仍验证 AST、runtime、contract、TOCTOU、fallback 与 reward，只是先满足新的 registry admission contract。
- 迁移后四阶段边界集合 135 项全绿，说明 stricter admission 与既有 AST/timeout/TOCTOU/contract/reward 行为可以同时成立。
- Canonical evolution → freeze → ALNS integration 继续通过：writer 新增 evidence 后，reader 的完整 metadata/timeout gate 没有阻断合法 frozen artifact。

## Phase 4D GREEN 结论（2026-08-03）

- Strict eligibility Critical 已在配置、loader 与 evolution 三层关闭：literal bool 以外的值不会启用 unsafe execution；runner/dataclass 报配置类型错误，loader 以 `config_invalid` fail closed。
- Execution、benchmark、selection、freezing 与 registry deployment 共享同一 policy 事实源；缺 validation/execution/failure/safe/risk/sandbox/provider/hash/fallback/rates 证据时不再使用成功默认值。
- Generated/frozen path execution 已把 expected hash 变成底层 mandatory gate；缺 hash 不创建子进程，hash mismatch 仍阻止 compile/call，从而保持 Phase 4C TOCTOU 修复。
- Frozen writer 与 reader 的 schema 已同步，timeout 只接受有限正数；无效 timeout 不再中断 solver 初始化，而是产生 `registry_validation` fallback。
- 正式规格已改为当前事实：timeout-limited subprocess、expected hash、execution gate、fail-closed selection/freezing 和 contract/feasibility validation；同时明确它不是 capability sandbox。
- 验证证据为完整 225 passed、compileall exit 0，仅保留既有 `pyreadline`/`collections.Callable` 弃用 warning。该结果足以进入 Phase 4D 独立复审，但不足以授权真实 LLM 或大规模实验。

## Phase 4D 独立复审工作记录（2026-08-03）

- Strict bool helper 本身正确拒绝 bool 以外所有类型；Phase 4D 测试覆盖 YAML、loader 与 evolution 的常见 truthy/falsey 非 bool 值。
- 待核证 Required 候选：`candidate_is_freeze_eligible()` 对缺失 timeout 使用 1000ms 默认；`validation_failed_rate`/`execution_blocked_rate` 被列为 optional，缺失不阻断 selection/freezing。两者可能不满足本轮“缺证据即拒绝”的复审口径。
- 待核证安全标签候选：policy 允许字符串 `capability_sandbox`，但当前 executor 明确只有 timeout_only；需确认是否存在能力证明/独立 executor，否则该标签可能成为元数据自声明绕过。
- Real-provider canonical 路径正确：runner/config/draft provenance 取保守 real-provider 值，非 bool 或默认 False 均在 smoke 前阻断；CLI truthiness 的输入是 argparse `store_true`，不是 YAML 任意值。
- `no_valid_operator` 仍同时表示“该类型没有合格候选”和“该类型根本未演化”；invalid/fallback 只能从 candidate rows/breakdown 推断，selection_status 本身没有明确区分。该问题会影响实验协议语义，列为 Required 候选。
### Phase 4D independent review — targeted policy diagnostics (2026-08-03)

- Strict boolean parsing is effective: `candidate_is_execution_eligible` rejects strings, numbers, `None`, lists, and mappings as the unsafe-execution flag.
- Fail-closed evidence is still incomplete: an otherwise successful artifact is selection-eligible without `validation_failed_rate` / `execution_blocked_rate`, and freeze-eligible without those fields or `timeout_ms` (the freeze policy supplies a 1000 ms default).
- A real-provider validation object labeled `capability_sandbox` is execution-eligible even with `allow_unsafe_candidate_execution=False`. Because the implemented executor is only `timeout_only`, this label must be bound to trusted executor evidence rather than accepted as self-declared metadata; frozen-registry exploitability is under review.
- Frozen registry deployment validates `sandbox_level` only as row metadata and accepts `capability_sandbox`, then constructs the same timeout-only `CandidateProxy`; therefore a manually altered artifact can mislabel the actual isolation level and bypass the real-provider acknowledgement rule. This is a lifecycle execution-gate defect, not evidence of a capability sandbox.
- Documentation correctly warns that the current boundary is timeout-only, but `docs/llm_operator_evolution_spec.md` currently overstates that every missing selection/freezing rate field is rejected.
- `candidate_loader` uses only `parse_strict_bool` from the shared policy and still implements its own real-provider decision plus directly flips `safe_to_execute` / `requires_human_risk_ack`; benchmark/selection/freezing/registry use shared eligibility functions. This is policy drift risk and weakens the claimed single execution gate.
- `evolution_summary.json` emits `no_valid_operator` for every missing best row, including operator types not requested for evolution; `not_evolved` is not represented, so no-valid and not-run are conflated.
- Canonical loader and frozen registry do AST validation before constructing a hash-bound proxy, and the child compiles the same source snapshot whose hash it checked. However, the low-level public executor itself checks only expected hash, not AST validation; a direct caller that supplies the hash can execute denylisted code. Canonical paths are protected, but the boundary API is not self-contained.
- Feedback/round leaderboard construction sorts all rows without eligibility filtering. Consequently validation-blocked/invalid rows can enter `top_operators` (for example, score 0 can outrank a valid negative-improvement row), even though final best selection correctly filters them. This does not contaminate frozen best/reward, but it can contaminate cross-round LLM feedback and must be separated before operator-evolution experiments.

## Phase 4D independent review conclusion (2026-08-03)

### Critical

- **Untrusted sandbox label bypasses the lifecycle gate.** The policy accepts `capability_sandbox` and exempts a real provider from `allow_unsafe_candidate_execution`, while registry deployment trusts that JSON field and still constructs the same timeout-only proxy. Editing an otherwise hash-valid artifact's sandbox label can therefore authorize real-provider generated code without actual capability isolation or risk acknowledgement. The sandbox level must come from trusted executor configuration/attestation, and the current implementation must reject any level other than its actual `timeout_only` boundary.

### Required

- Make `validation_failed_rate`, `execution_blocked_rate`, and freeze `timeout_ms` mandatory rather than optional/defaulted; keep writer, reader, selection, freeze, and spec schema aligned.
- Make the execution boundary self-contained: centralize loader gate decisions and ensure the worker/executor validates the exact source snapshot (or requires a non-forgeable validation receipt), not merely a caller-supplied hash.
- Filter leaderboard/feedback through eligibility and distinguish `not_evolved` from `no_valid_operator`; retain concrete invalid/fallback reasons separately.
- Correct the formal spec's overstatement that every evidence field is already fail-closed.

### Consider / FYI

- Add a versioned/signed registry schema and executor-generated isolation attestation; preserve the known CPU/memory/filesystem/network/environment/process-tree risks as blockers for real LLM execution.
- Requested AST cases, canonical hash/TOCTOU checks, malformed contract/registry handling, fallback/reward attribution, strict bool parsing, and all test suites reviewed are otherwise correct.
- Fresh evidence: Phase 4D 59 passed; combined boundaries 135 passed; operator evolution 17 passed; frozen/ALNS 4 passed; full suite 225 passed with one existing pyreadline warning; compileall exit 0.
- Review disposition: **Request changes**. Phase 5 documentation, real LLM, and large experiments remain blocked until the Critical gate defect is fixed and independently re-reviewed.

## Phase 4E RED test-design basis (2026-08-05)

- The user-approved RED matrix directly operationalizes the Phase 4D review findings; no production design choice is needed in this turn.
- Tests will treat sandbox authority as runtime-owned evidence, not candidate/registry metadata, and will exercise both policy helpers and canonical frozen deployment.
- Evidence completeness, same-snapshot AST validation, loader-policy reuse, status separation, and feedback eligibility are separate failure groups so GREEN can remain minimal and attributable.
- Current policy explicitly treats `capability_sandbox` as allowed/strong using candidate-owned `validation.sandbox_level`; registry metadata uses the same rule, while `CandidateExecutionResult` and `CandidateProxy` are hard-coded to `timeout_only` and expose no trusted executor identity.
- `validation_failed_rate`/`execution_blocked_rate` are optional and freeze defaults a missing timeout to 1000 ms; this gives direct, deterministic RED assertions without provider calls.
- The child worker hashes a source snapshot and immediately compiles it, but does not run `validate_candidate_source` on that snapshot. A marker-file test can prove that correctly hashed `open(...)` code is actually executed today.
- `candidate_loader` imports only `parse_strict_bool`, duplicates real-provider gating, and directly flips safety/risk fields before smoke. A narrow policy-hook monkeypatch can detect whether loader delegates its pre-execution decision.
- Evolution summary sorts all round rows, feedback sorts all rows, and both selection statuses default to `no_valid_operator`; behavior tests can independently expose ineligible feedback/leaderboard and `not_evolved` conflation.

## Phase 4E RED evidence (2026-08-05)

- 23 tests collect cleanly; authoritative run is 18 failed / 5 passed. Every failure is an expected assertion against missing behavior, not a collection, fixture, or accidental exception failure.
- The Critical is reproduced at every lifecycle gate: execution, benchmark, selection, freezing, actual freeze output, and frozen registry admission all accept a self-declared capability claim while runtime remains timeout-only.
- The correctly hashed dangerous-source test returned `success` and created its marker, proving hash binding alone does not enforce the AST policy at the low-level execution API.
- Missing validation/execution-blocked rates and timeout remain fail-open; existing fallback/error/timeout/invalid-rate omissions remain correctly fail-closed.
- Loader policy delegation, `not_evolved`, eligible-only feedback/leaderboard, and trusted-authority documentation each have isolated RED evidence.
- Existing Phase 4/4B/4C/4D boundary tests remain 135 passed; full suite is 18 failed / 230 passed, and every full-suite failure belongs to the new Phase 4E file.
- Phase 4E remains RED-only: no production source, existing test, or documentation body was changed; no provider or experiment was run.

## Phase 4E GREEN implementation mapping (2026-08-05)

- Canonical evaluated rows are assembled in both repair and destroy evaluator paths; they must carry trusted authority plus explicit zero validation/execution-blocked rates so the stricter shared artifact policy does not reject legitimate candidates.
- Invalid/unbenchmarked rows are assembled separately in the evolution loop and need the same schema with failure-specific validation/execution-blocked rates.
- `CandidateExecutionResult` is the runtime-owned evidence source. Adding immutable current executor identity/effective level there, and mirroring those constants into validation records, avoids treating artifact claims as authority.
- The existing worker already reads/hash-checks one `source_text` snapshot. Calling `validate_candidate_source(source_text, operator_type)` immediately after hash verification closes the direct executor bypass without another read or dependency.
- Freezing and registry deployment use the same artifact policy, so the writer must persist claimed/effective/identity plus all rates and explicit timeout; the reader must compare them with current runtime constants before constructing `CandidateProxy`.

## Phase 4E GREEN 结论（2026-08-05）

- **Trusted executor authority 已成为唯一 sandbox 授权来源。** 当前 runtime 常量为 `timeout_only_subprocess_v1` / `timeout_only`；candidate、metrics 与 registry 中的 sandbox 字段只作为 claim/audit evidence。claim 与 runtime、或 `sandbox_level` 与 `claimed_sandbox_level` 不一致时，execution/benchmark/selection/freezing/registry 均 fail closed。
- **真实 provider 默认门禁保持关闭。** loader 使用统一 pre-execution/eligibility policy；非 literal bool 配置、缺风险确认、缺安全证据或不可信 sandbox claim 均不会进入 smoke/benchmark，也不会成为 best/frozen/generated success。
- **底层 executor 边界自包含。** child 对一次读取的同一 `source_text` 先校验 expected SHA-256，再执行 AST/security validation，之后才 compile/call；因此“危险源码 + 正确 hash”不能绕过静态门禁，path execution 缺 hash 仍返回 `source_hash_missing`。
- **完整 evidence 已接通。** evaluator/invalid rows、selection、freezing 与 frozen registry 统一要求 success/fallback/provider/hash/runtime authority、显式有限正 timeout，以及 error/timeout/invalid/validation-failed/execution-blocked 五类 rate。缺字段、非零失败率、错误类型或不可信 claim 均拒绝。
- **研究语义已隔离。** feedback 的 top/weak 与 round leaderboard 只使用 eligible、non-fallback success rows；失败仍进入独立 breakdown。未参与演化输出 `not_evolved`，参与但无合格候选输出 `no_valid_operator`。
- **frozen deployment 保持 TOCTOU 与 contract 防线。** registry 先做完整 metadata/runtime authority 校验；每次 proxy 执行仍重读、验 hash、验 AST。fallback/invalid/timeout/blocked 不记 generated success，也不获得 generated reward。
- **规格已同步。** `docs/llm_operator_evolution_spec.md` 明确 artifact 不能自我声明 capability、当前 capability sandbox 未实现，并保留 CPU、内存、文件系统、网络、环境变量与后代进程树未隔离的风险。
- **测试迁移事实。** Phase 4E 完整 evidence 使旧 Phase 4B–4D 的“有效 registry”fixture 被 fail-closed 拒绝；只补齐 fixture metadata，未改变断言或放宽生产门禁。另通过补充 RED/GREEN 锁定分离 `claimed_sandbox_level` alias 的绕过路径。
- **验证证据：** Phase 4E 24 passed；五阶段边界 158 passed（补充 alias 测试前的分组运行，随后完整套件覆盖新增节点）；operator evolution 17 passed；frozen/ALNS 4 passed；最终 `pytest -q` 249 passed、1 个既有 `pyreadline` warning；最终 `python -m compileall -q src` exit 0。
- **结论边界：** Phase 4E GREEN 实现完成但尚待独立复审。当前结果不等于 capability sandbox；在复审前不进入 Phase 5，继续禁止真实 LLM 与大规模实验。

## Phase 4E 独立复审诊断（2026-08-05）

- **Critical 已复现：frozen registry 仍可绕过 real-provider runtime risk gate。** 临时目录中构造 `source_provider=langchain_openai_compatible`、`sandbox_level/effective=timeout_only`、正确 executor identity/hash，并在 JSON 自报 `safe_to_execute=True`、`requires_human_risk_ack=False`、全零 failure rates；`ALNSSolver` 将其加入 `frozen_repair_ops`，且无 fallback。部署路径没有 runtime `allow_unsafe_candidate_execution` 或不可伪造的风险确认 authority，因此真实 provider 并非在 frozen deployment 默认 blocked。
- **Capability claim 本身已正确封闭。** 同一 registry row 只把 claim 改为 `capability_sandbox` 后，operator 未注册，fallback reason 为 `untrusted_sandbox_claim: claimed sandbox does not match runtime`。因此 Phase 4E 的原始 sandbox self-elevation Critical 已修复，但 real-provider 风险确认仍由 artifact 自报字段代替 runtime authority。
- **Required 候选已复现：execution eligibility 缺 runtime evidence 时 fail open。** 对缺 `effective_sandbox_level` 和 `executor_identity` 的 validation object，公共 `candidate_is_execution_eligible(..., allow=True)` 返回 True，因为 `getattr` 将缺字段默认成可信 runtime 常量；函数还只检查 callable 非空，不要求 `CandidateProxy`/可信 executor receipt。canonical loader 正常填充这些字段，但公共边界与文档“缺证据即拒绝”不一致。
- **Artifact gates 同样信任自报 risk flags。** 完整 real-provider row 只凭 JSON 中 `safe_to_execute=True` / `requires_human_risk_ack=False` 即通过 selection 与 freezing；这解释了 frozen registry 的 canonical 绕过，而不是单纯测试替身问题。

## Phase 4E GREEN 独立复审结论（2026-08-05）

### Critical

- **Frozen real-provider deployment 缺 runtime 授权 authority。** `candidate_is_selection_eligible`、`candidate_is_freeze_eligible` 和 `validate_registry_metadata` 只读取 artifact/registry JSON 自报的 `safe_to_execute=True` 与 `requires_human_risk_ack=False`；`ALNSConfig`/registry loader 没有 `allow_unsafe_candidate_execution` 或独立人工确认输入。实测 forged real-provider timeout-only row 通过 selection/freezing 并注册进 `frozen_repair_ops`。修复必须把 deployment authorization 移到 runtime policy（或使用不可伪造 validation receipt），不能继续由候选 artifact 自证。该问题阻止 Phase 5、真实 LLM 和大规模实验。

### Required

- **Execution policy 公共边界未完全 fail closed。** 缺 `effective_sandbox_level` / `executor_identity` 时，`candidate_is_execution_eligible` 用可信常量作为默认值；它也接受任意非空 callable，而非要求 `CandidateProxy`/可信 executor receipt。`OperatorValidationResult` 同时默认 `safe_to_execute=True`、risk-ack false 和可信 authority 字符串。canonical loader 会覆盖这些值，但旁路/API 调用可构造无 runtime evidence 的 eligible object。
- **回归测试缺少两条关键负例。** 现有 capability registry 测试同时伪造 claim 和 executor identity，未覆盖“claim 为真实 timeout-only、只伪造 real-provider risk acknowledgement”的 canonical deployment 绕过；也未覆盖 execution object 缺 runtime authority evidence 或使用非 proxy callable。
- **文档需要按事实收敛。** 正式规格仍标为“截至 Phase 4D”，声称真实 LLM 在所有路径默认阻止，与 frozen deployment 事实冲突；又把已实现的 eligible-only top/weak filtering 和未实现的 lineage/diversity 混写。`docs/operator_evolution.md` 同时写“no sandboxed execution”和“timeout-only subprocess”，应明确为“没有 capability sandbox”。

### Consider

- 将 `ALNSSolver` 中 frozen registry、proxy、contract 与 reward attribution 提取为 operator deployment adapter；当前文件约 812 行，这个子域已具备独立 policy 与测试边界。
- 在 Phase 5 以后分别报告 Windows spawn/import、candidate runtime 与端到端 wall time；当前每个 smoke/trial 启动新进程，安全语义清楚但成本不可忽略。
- 后续 artifact schema 可增加版本与不可伪造 receipt/签名，并校验排序指标为有限数，避免手工或旧 artifact 用 NaN/畸形质量字段污染 ranking。

### FYI

- Artifact/registry 声称 `capability_sandbox` 已无法提升权限；claim 与 runtime `timeout_only` 不一致会结构化拒绝。实际 frozen executor 始终构造 `CandidateProxy`，不会根据 JSON 选择更强 executor。
- Bottom-level path executor 对同一 `source_text` 依次执行 expected hash 与 AST validation 后才 compile/call；当前 identity/level 明确为 `timeout_only_subprocess_v1` / `timeout_only`。
- Selection/freezing 对五类 failure rates、fallback、timeout、provider、hash、status 与 runtime authority 字段缺失均 fail closed；`not_evolved`/`no_valid_operator` 已区分，top/weak/leaderboard 已过滤 eligibility。
- AST denylist 覆盖本阶段点名的明显绕过，但文档正确承认它不是 capability sandbox；CPU、内存、文件系统、网络、环境变量和后代进程树仍未隔离。
- 新鲜验证：`pytest -q` 249 passed、1 个既有 warning；`python -m compileall -q src` exit 0。测试通过不否定上述未覆盖且已单独复现的 Critical。

### Gate

- **不允许进入 Phase 5 文档化实验协议。** 先关闭 frozen real-provider runtime authorization Critical 并复审。
- **继续禁止运行真实 LLM。** 当前不仅缺 capability sandbox，frozen deployment 还缺 runtime 风险确认 authority。
- **继续禁止大规模实验。** 安全/归因 artifact 的部署门禁仍可被伪造 metadata 绕过。
- **Verdict：Request changes。**

## Phase 4E 独立复审复核确认（2026-08-05）

- 当前磁盘状态再次复现同一 **Critical**：真实 provider 的 frozen artifact 可仅凭 registry JSON 自报 `safe_to_execute=True`、`requires_human_risk_ack=False` 与其余完整 metadata，通过 selection、freezing 并被 solver 注册；部署路径仍没有独立 runtime allow / human-risk acknowledgement authority。
- `sandbox_level=capability_sandbox` 的自声明提升已正确封闭：当前 runtime 为 `timeout_only` 时会返回 `untrusted_sandbox_claim`，不会注册。
- execution eligibility 缺 `effective_sandbox_level` / `executor_identity` 时仍默认成可信常量并返回 eligible；该 Required 与 validation schema 的 fail-open 默认值仍未修复。
- fresh verification：`pytest -q` 为 249 passed、1 个既有 warning；`python -m compileall -q src` exit 0。现有测试未覆盖上述已复现 Critical。
- Gate 保持 **Request changes**：Phase 5 文档化实验协议、真实 LLM 与大规模实验均继续禁止。

## Phase 4F RED 测试设计依据（2026-08-05）

- 项目约束允许最小测试变更但禁止真实 LLM；本阶段将使用临时目录、真实 `ALNSSolver` registry 加载路径和静态 operator 源码验证部署结果，不断言 mock 自身行为。
- 现有 Phase 4E 测试已覆盖 capability claim 与 executor identity，但没有覆盖“claim 保持真实 `timeout_only`、仅由 artifact 伪造 safety/risk acknowledgement”的 frozen deployment 路径。
- Phase 4F 将把 registry deployment、strict runtime bool、execution authority evidence、schema defaults 和文档事实拆成独立测试组，确保每个 RED 都能映射到单一缺失合同。
- `ALNSConfig` 当前没有 real-provider frozen deployment allow、runtime risk acknowledgement 或 authorization source 字段；registry loader 只调用 artifact metadata validator 后构造 `CandidateProxy`。
- `candidate_is_execution_eligible` 对 effective sandbox / executor identity 使用可信默认值，并只要求 callable 非空；`OperatorValidationResult` 也默认 safe、无需风险确认和可信 runtime identity，均可由无执行 receipt 的对象触发。
- RED 选择的 timeout-only 策略为：仅当当前 runtime 同时提供 literal `allow_real_provider_frozen_deployment=True`、`explicit_runtime_risk_ack=True` 和明确 authorization source 时才允许继续部署；该授权不代表 capability sandbox。

## Phase 4F RED 证据（2026-08-05）

- 37 项收集无错误；专项为 36 failed / 1 passed。36 项均是预期 assertion failure，不是 import、fixture、异常或测试拼写问题。
- 完整、正确 hash、合法 timeout、五类零 failure rate 的 real-provider registry row 在没有 runtime authority 时仍被加入 `frozen_repair_ops`；即使 artifact 自报 runtime allow/ack/source 也同样注册，直接重现 Critical。
- 两类 runtime flag 的字符串、整数、None、list、dict 等 20 个非 bool 节点以及 literal False 节点均被当前 solver 忽略并继续部署，证明 frozen 路径尚无 strict runtime policy。
- execution policy 对五类缺失 authority evidence 均返回 True；任意 lambda 也可充当 callable；schema 默认仍为 safe、无需 risk ack 和可信 runtime identity。
- 唯一通过的是 runtime literal allow=True + literal ack=True + current-runtime source 的 timeout-only 正例，锁定本阶段选定的授权策略而非全面禁止部署。
- 既有 Phase 4–4E 边界 159 passed；完整套件 36 failed / 250 passed，36 个失败全部属于 Phase 4F 新文件，既有 249 个测试全部通过。

## Phase 4F GREEN 实现映射（2026-08-05）

- Canonical candidate loader 已使用 `CandidateProxy`，适合把“可信 callable”收紧为 proxy 类型；需要由 `configure_candidate_preexecution_policy` 显式填入 trusted executor/effective level 与 runtime authorization evidence，不能继续依赖 schema 默认值。
- 直接 policy 正例测试仍使用 lambda 和旧 schema defaults；生产合同收紧后应仅迁移该 canonical-valid fixture 为 `CandidateProxy` + 显式 runtime evidence，不改变其“完整证据可 eligible”的断言。
- `ALNSConfig` 是 frozen deployment 当前 runtime authority 的自然入口；新增字段默认 false/empty 不影响未启用 frozen operator 的主搜索路径。

## Phase 4F GREEN 静态核对（2026-08-05）

- Frozen deployment gate 的 allow、risk ack、authorization source 均从当前 `self.config` 传入；effective level 与 executor identity 来自代码内 runtime constants。Artifact row 只向 gate 提供 provider 分类，row 中同名 authorization 字段未被读取。
- `ALNSConfig` 三项授权默认 false/false/empty；两类 bool 由 `parse_strict_bool` 验证，非 bool 结构化为 `real_provider_deployment_blocked`，缺失/false/source 不合格为 `missing_runtime_authorization`。
- Public execution eligibility 不再为缺 effective/identity 注入可信默认，且要求 `CandidateProxy`、显式 runtime source 和 literal bool evidence；canonical loader 是显式注入可信 runtime 字段的唯一生成路径。
- Registry runtime gate 位于 metadata validation 之后、source import/proxy construction 之前；拒绝 operator 不会进入 `frozen_*_ops`，因此不会被标为 generated success 或获得 generated reward。
- 文档已与实现同步为 Phase 4F、runtime-only frozen authorization 和 timeout-only 非 capability sandbox；资源/能力隔离风险继续保留。

## Phase 4F GREEN 结论（2026-08-05）

- **Named Critical 已关闭。** 对 registry 中明确分类为 real provider 的 frozen row，artifact 自报 safe/risk ack/source 不再授权部署；默认 config 结构化 fallback，只有当前 runtime 的 literal allow=True、literal ack=True、accepted source 与代码内 executor authority 同时成立才构造 proxy/注册 frozen operator。
- **Failure/reward 隔离成立。** 未授权 row 在注册前被拒绝，fallback event 记录 `missing_runtime_authorization` 或 `real_provider_deployment_blocked` 与 `failure_type`；operator 不进入 frozen set/stats，因此不产生 generated success 或 reward。
- **Public execution boundary 收紧。** 缺 effective sandbox、executor identity、runtime source、两类 bool evidence或使用任意 callable 均 ineligible；canonical loader 显式构造 `CandidateProxy` 并注入 runtime facts。
- **Schema/documentation 收敛。** Validation 默认 unknown/unsafe/requires ack；Phase 4F spec 和 operator guide 明确 runtime-only authorization、artifact 自证无效和 timeout-only 非 capability sandbox。
- **验证证据：** Phase 4F 37 passed；Phase 4–4F boundary 196 passed；operator evolution 17 passed；frozen/ALNS 4 passed；最终完整 286 passed、1 个既有 warning；compileall exit 0。
- **仍需复审的 provenance 风险：** `source_provider` 分类本身仍是未签名 registry metadata。Phase 4F 关闭的是 provider 已明确为 real-provider 时的 safety/risk 自证绕过；真实 provider 解禁前应评估 versioned/signed receipt 或 runtime provenance binding。
- **Gate：** Phase 4F GREEN 尚未独立复审；Phase 5、真实 LLM 和大规模实验继续禁止。

## Phase 4F 独立复审：provider provenance 绕过（2026-08-05）

- **Critical（已复现）：** `validate_frozen_deployment_authorization()` 直接读取 registry row 的 `source_provider`，且当值不在 real-provider 名单时立即放行；该字段没有 runtime receipt、manifest signature 或其他不可由 artifact 篡改的 provenance binding。
- **最小证据：** 完整 real-provider row 在默认 `ALNSConfig` 下正确返回 `missing_runtime_authorization`；仅把 `source_provider` 改为 `mock`，相同源码/hash/evidence 随即注册进 `frozen_repair_ops`，且没有 fallback event。
- **影响：** artifact 虽不能再通过自报 safe/risk/sandbox 字段直接授权，但仍能通过自报 provider 类别避开 real-provider 专属 runtime gate；当前文档“任何 artifact 自证均无效”的表述强于实现事实。
- **修复方向（本轮不实现）：** provider provenance 必须由当前 runtime/可信 manifest receipt 决定，或在缺可信 provenance 时对所有 generated frozen artifact 统一要求 deployment authorization；metadata digest/signature 应同时绑定源码 hash 与 provider/validation lineage。

## Phase 4F 独立复审最终结论（2026-08-05）

### Critical

- **Provider relabel 可绕过 frozen runtime authorization。** `validate_frozen_deployment_authorization()` 在 `source_provider` 不属于 real-provider 名单时直接成功返回，而 `source_provider` 完全来自 registry row。源码 hash 只绑定 `.py` 内容，不绑定 provider/validation lineage。实证中仅把标签由 `langchain_openai_compatible` 改为 `mock`，默认配置即从结构化拒绝变为成功注册、无 fallback。该 operator 一旦运行成功，会因 frozen-set membership 被视为 generated operator，可能污染 success/reward。

### Required

- 新增 provider relabel、未知/缺可信 provenance、manifest metadata 与源码 hash 分离篡改的回归测试；runtime deployment gate 不得用 artifact 自报 provider 决定是否需要授权。
- 建立 runtime-owned provider identity/authorization receipt，或在尚无可信 provenance 时对所有 generated frozen artifact 统一要求 runtime allow + explicit risk ack。仅允许 `mock/file/manual` 豁免时，也必须由当前 runtime 构造的可信来源证明，而不是 registry 字符串。
- 修正文档事实边界：目前 artifact 的 safety/risk/sandbox 自报不能授权，但 provider 分类仍可自报；因此“任何 artifact 自证均无效”和“真实 provider frozen deployment 默认阻止”尚不是全路径事实。

### Consider

- 将 code hash、provider identity、validation/benchmark evidence、schema version 与 executor identity 绑定进 versioned manifest digest/签名；冻结时产生 receipt，部署时由 runtime verifier 验证，避免继续新增独立可篡改字段。
- 将 frozen registry 验证、runtime authorization 与 proxy 构造从 `ALNSSolver` 抽成 deployment adapter，便于集中验证 provenance、审计 fallback 并减少策略漂移。
- 当前 execution eligibility 的 identity/source/ack 仍是普通字段，不是不可伪造 capability token；在真实 provider 解禁前应明确可信调用边界，而不能把 Python 字符串本身视作安全证明。

### FYI

- 对 provider 标签保持 `langchain_openai_compatible` 的 canonical row，artifact 自报 `safe_to_execute=True` / `requires_human_risk_ack=False` 已不能部署；当前 runtime literal allow、literal ack、accepted source 缺一即拒绝。
- 两类 runtime authorization flags 只接受 literal bool；schema 默认 unknown/unsafe/requires ack；缺 effective sandbox/executor identity/runtime source/allow/ack 或使用普通 callable 均不 eligible。
- Frozen path executor 每次读取待执行源码，在同一文本上校验 expected hash 和 AST 后才 compile/call；当前 executor 明确是 `timeout_only_subprocess_v1` / `timeout_only`，不是 capability sandbox。
- Selection/freezing 对 statuses、failure type、fallback、五类 failure rate、timeout、provider、hash 与 executor evidence 缺失 fail closed；contract/fallback 路径继续隔离 generated reward。mock/file/manual 既有回归未被误伤。
- 新鲜证据：相关专项 124 passed；完整 `pytest -q` 286 passed、1 个既有 warning；compileall exit 0。现有测试未覆盖上述已单独复现的 provider relabel Critical。

### Gate

- **不允许进入 Phase 5 文档化实验协议。**
- **继续禁止运行真实 LLM。**
- **继续禁止大规模实验。**
- **Verdict：Request changes；存在 1 个必须先修复的 Critical 与其配套 Required。**

## Phase 4G RED 测试设计依据（2026-08-05）

- Phase 4F 已有完整 registry fixture、真实 `ALNSSolver` 注册路径、strict bool 参数化和 runtime-authorization 正向锚点；Phase 4G 可复用其结构但必须独立覆盖 claimed provider 重标，不能把 provider label 当作测试前提。
- 当前 `validate_registry_metadata()`/selection/freezing 只要求非空 `source_provider`，没有 `claimed_source_provider`、`provider_provenance`、`lineage`、`generation_run_id` 或 `artifact_identity` 合同；这些字段的缺失/畸形可通过真实 policy assertion 形成 RED。
- 当前 solver 的 runtime authorization 只对 real-provider 名单生效；mock/file/manual/rule_based/openai/deepseek/unknown claimed labels 会跳过 strict runtime bool 与 authorization source。Phase 4G 将参数化这些 claim，证明所有 generated frozen artifacts 都必须经过统一 gate。
- 当前 feedback/leaderboard 复用 `candidate_is_selection_eligible()`；因此在 selection policy 中锁定 provenance evidence，可同时防止 claimed mock/file 候选进入 top/weak/leaderboard，无需测试 mock 调用次数。
- Freezing 当前原样写 `source_provider`，没有显式 claimed/trusted 区分。RED 应要求 registry 保留 `claimed_source_provider` 审计字段且不得把 artifact provider 写成 trusted provenance。
- 为避免无条件禁用 frozen deployment，Phase 4G 保留“完整 lineage/provenance audit fields + 当前 runtime literal allow/ack/source”的正向锚点；负例分别移除/篡改证据。

## Phase 4G RED 初步证据（2026-08-05）

- 42 项成功收集；专项稳定为 40 failed / 2 passed。失败全是行为 assertion，不是 collection、fixture、import 或未捕获异常。
- real-provider honest label 已被 Phase 4F 默认 gate 阻止，但同一 artifact 重标 `mock` 后仍注册；mock/file/manual/rule_based/openai/deepseek/unknown 七类 claimed label 均绕过 runtime authorization。
- metadata/selection/freezing 当前忽略 claimed provider、provider provenance、lineage、generation run 与 artifact identity；缺失、unknown、类型错误和 claim mismatch 均返回 eligible/valid。
- mock claimed path 完全跳过两类 runtime deployment bool 校验，字符串、数字、None 与容器等 16 个节点均继续注册 generated frozen operator。
- selection/freezing/feedback 仍接纳缺 provider provenance 的 claimed mock/file 候选；freezing registry 不写 `claimed_source_provider`；formal spec 不包含明确的 claimed-provider/trusted-provenance/capability-token 口径。
- literal allow=True、runtime ack=True、accepted source 的正向部署锚点通过，证明 Phase 4G RED 不是无条件禁止 generated frozen deployment。
- 既有 Phase 4–4F 边界 196 passed，新增 RED 没有破坏既有测试。
- 完整套件为 40 failed / 288 passed；40 个失败全部来自 Phase 4G 新文件。当前 RED 证据足以进入后续最小 GREEN，但在修复并复审前 Phase 5、真实 LLM 和大规模实验仍必须 blocked。

## Phase 4G GREEN 结论（2026-08-05）

- **Provider relabel Critical 已在部署路径关闭。** Frozen deployment authorization 不再依据 `source_provider`/`claimed_source_provider` 分类；real、mock、file、manual、rule_based、openai、deepseek 或 unknown claim 均经过同一个 generated-artifact runtime gate。默认 allow/ack 为 False，只有 literal bool 授权组合、受认可的当前 runtime source 与 runtime executor evidence 同时满足时才继续部署。
- **Provider 字段已降级为审计 claim。** Evaluator/evolution/freezing 产出 `artifact_type`、`claimed_source_provider`、`provider_provenance={trust_level: artifact_claim, ...}`、`generation_run_id`、`artifact_identity` 与 lineage；freezing 不生成 `trusted_provider_provenance`，registry 明确标记仍需 runtime authorization。
- **生命周期 eligibility 保持统一且 fail closed。** 缺失/unknown/畸形 provenance、claim mismatch、lineage/id 缺失会在 selection/freezing/registry validation 被拒绝；feedback/top/weak/leaderboard 继续从统一 eligible pool 构建，claimed mock/file 不获得较低门槛。
- **部署拒绝与 reward 隔离。** 未授权或 provenance 不合格的 artifact 在 `CandidateProxy` 注册前结构化 fallback，不加入 frozen/generated operator 集合，因此不会被计为 generated success 或获得 reward；Phase 4G usage/reward 回归已覆盖 provider 重标路径。
- **兼容性边界。** Phase 4F real-provider allow/ack 字段保留为严格布尔兼容授权组合，但不再触发 provider-specific bypass；非 bool 值仍 fail closed。旧 canonical-valid 测试夹具只补齐显式 provenance/lineage 与 current-runtime authorization，负例及断言未放宽。
- **文档事实已同步。** 正式规格和 operator guide 明确：provider identity 不能由 artifact 自证；当前没有可信签名 provenance receipt；executor identity/runtime source 只是普通运行时证据，不是不可伪造 capability token；所有 generated frozen deployment 目前都需当前 runtime 授权。
- **验证证据。** Phase 4G 专项 42 passed；Phase 4–4G boundary 238 passed；operator evolution 17 passed；frozen/ALNS 4 passed；完整 `pytest -q` 328 passed、1 个既有 `pyreadline` warning；`python -m compileall -q src` exit 0。
- **剩余风险。** 当前仍是 timeout-only subprocess，不是 capability sandbox；CPU、内存、文件系统、网络、环境变量和后代进程树未隔离。可信、版本化/签名 provider provenance receipt 尚未实现，runtime identity/source 也不是密码学 authority。
- **Gate。** Phase 4G GREEN 已实现但尚待独立复审；不进入 Phase 5，不运行真实 LLM，不运行大规模实验。

## Phase 4G GREEN 独立复审进行中（2026-08-05）

- Phase 4G 测试通过真实 registry/solver 路径证明同一源码与 hash 的 real/mock claim 在默认无 runtime authorization 时都被拒绝；正向锚点要求当前 runtime 配置授权，测试不是只针对内部 helper。
- `validate_frozen_deployment_authorization()` 不读取 `source_provider` 或 `claimed_source_provider` 作授权分支；四个 allow/ack 输入全部经 `type(value) is bool` 的严格解析，provider claim 只在 metadata consistency validation 中用于审计。
- Freezing 从 `claimed_source_provider` 写兼容 `source_provider`，provenance 仍明确为 `artifact_claim`，并标记 `runtime_authorization_required`；没有写入 `trusted_provider_provenance`。
- Selection/freezing/feedback 分别直接或间接复用 `_artifact_failure_reason()` / `candidate_is_selection_eligible()`；缺 provenance/lineage/failure evidence 与 fallback/blocked 状态会被统一排除。
- 尚待核对：ALNS registry gate 的调用顺序及 fallback/reward 隔离、provider factory 的真实 provider 命名边界、mock/file/manual 非 frozen 路径，以及文档是否精确匹配兼容授权字段。
- ALNS 当前唯一 authorization-helper 调用点严格先执行 `validate_registry_metadata()`；因此现有 registry 部署路径没有 metadata 绕过。不过公共 `validate_frozen_deployment_authorization()` 单独对空 mapping + 完整 runtime allow/ack 会返回 success，它依赖调用顺序而不是自包含验证。当前无第二调用者，暂列架构收口候选而非现有部署 Critical；应考虑合并为单一 deployment eligibility API 或在 helper 内要求 validated artifact evidence。
- 文档准确声明 provider claim 只是 `artifact_claim`、可信 receipt 尚未实现、runtime identity/source 不是 capability token，并披露 timeout-only 的能力隔离缺口；没有把当前 provenance 描述成签名或不可伪造证明。

## Phase 4G GREEN 独立复审结论（2026-08-05）

### Critical

- 无。未发现 `source_provider`/`claimed_source_provider` 可提升 frozen deployment 权限的现有调用路径；同源码 real→mock 重标在默认无当前 runtime authorization 时仍在 proxy 注册前被拒绝。

### Required

- 无。当前变更满足 Phase 4G 的 provider-agnostic gate、strict bool、freezing provenance、registry fail-closed、统一 selection/feedback 与文档事实要求。

### Consider

- `validate_frozen_deployment_authorization()` 是第二阶段 authorization helper，单独调用时不重做 artifact metadata validation；唯一生产调用点严格先调用 `validate_registry_metadata()`，所以当前无绕过。为降低未来误用，考虑用 typed `ValidatedFrozenArtifact` 或单一 `candidate_is_deployment_eligible()` 原子执行 metadata + runtime authority 两阶段，并移除当前几乎未使用的 `row` 参数。
- Phase 4F 的 `allow_real_provider_frozen_deployment` / `explicit_runtime_risk_ack` 仍可作为严格布尔兼容 pair 授权任意 generated frozen artifact；这是当前 runtime-owned、provider-agnostic 且已文档化的兼容行为，不构成 claim 绕过，但命名容易误解。考虑提供弃用提示并迁移到通用 generated allow/ack。
- Mock/file 非 frozen 回归未被误伤；但 file/manual 候选仍是在 timeout-only 边界执行的代码。若未来把它们视为非受信输入，应复用显式风险确认，并在真实 LLM 解禁前补 capability sandbox、CPU/内存/文件系统/网络/环境变量/后代进程树隔离和可信 receipt。
- `generation_run_id`/`artifact_identity`/lineage 当前是审计字段而非签名绑定；Phase 5 文档应继续把版本化 manifest digest、去重/diversity 与可信 provenance receipt 列为后续协议，而非宣称已完成。

### FYI

- Frozen registry loader 的顺序为：row shape → 完整 metadata/provenance/evidence → current runtime authorization → source read/hash → AST validation → `CandidateProxy`；任何拒绝项均不加入 frozen set。
- Freezing 仅写 `claimed_source_provider`、兼容 `source_provider` 和 `artifact_claim` provenance，并明确 `runtime_authorization_required`；不生成 `trusted_provider_provenance`。
- Selection、freezing、evolution leaderboard 和 feedback top/weak 都复用 `eligibility_policy`；invalid、blocked、timeout、fallback、缺 evidence/provenance/lineage 的 row 不进入这些语义。
- 未授权 operator 不注册，因此不会成为 generated-selected operator；runtime fallback 仍记录并隔离 `llm_operator_success` 与 generated reward。
- Provider factory 仅支持 canonical `mock`、`file`、`langchain_openai_compatible`；mock/file candidate loader/evolution 回归与 built-in ALNS 路径保持通过。
- 文档明确 source provider 是 claimed metadata、可信 receipt 尚未实现、runtime identity/source 不是 capability token、当前只有 timeout-only boundary，不存在 provenance 或 sandbox 过度声明。
- 新鲜验证：专项 48 passed、1 个既有 warning；完整 `pytest -q` 328 passed、1 个既有 `pyreadline` warning；`python -m compileall -q src` exit 0。

### Gate

- **Approve。允许进入 Phase 5 文档化实验协议。**
- **继续禁止运行真实 LLM。**
- **继续禁止大规模实验。**
- Phase 5 仅限文档/协议设计；上述 Consider 不阻塞文档阶段，但真实代码执行或实验解禁前必须重新评估 capability isolation 与 provenance authority。

## Phase 5A：研究定位事实底稿（2026-08-06）

- 五份目标文档 `research_positioning.md`、`innovation_review.md`、`llm_operator_evolution_research_plan.md`、`paper_contribution_plan.md`、`research_hypotheses.md` 当前均不存在，本阶段将从现有事实创建，而不是迁移旧结论。
- 实体模型：每个矩形任务具有轴对齐边界；实例包含 depot、机器人数量、速度、扫幅、转弯时间和任务集合。解是每机器人一个有序 task-id route，完整可行解应让每个任务恰好出现一次；目标评价是各 route cost 的最大值（makespan）。
- 每个任务生成 4 个入口角 × 2 个 sweep mode 共 8 个状态；状态包含出口角、入口/出口坐标、sweep 数和内部 processing time。内部覆盖时间实现为 `n_sweeps * traversal_length / speed + (n_sweeps - 1) * turning_time`。
- Route DP 对固定 task 顺序逐层选择状态链，最小化 depot→首任务、任务间转移、processing time 和末任务→depot 的总和；它优化的是覆盖状态/方向，不改变任务分配或任务顺序。空 route 成本为 0，route sequence 可缓存。
- 多机器人 evaluator 独立调用 route DP，并以最大 route total cost 作为 makespan。
- **重要建模事实：** 当前 `CostMatrix` 的 depot/任务间转移直接使用 Manhattan distance，没有除以 instance speed；processing time 则除以 speed。因此只有在 `speed=1` 或距离已被解释为时间时单位一致。Phase 5A 必须把这一点写成当前假设/有效性风险，不能宣称一般 speed 下已经统一。
- ALNS 已实现 destroy→partial evaluation→repair→一轮 stronger local search→acceptance→operator reward/weight 更新的组合搜索；destroy/repair 可从人工内置或经过 gate 的 frozen generated operators 选择。Local search 是独立后处理改进，不是 LLM 组件。
- Advisor 当前只有 mock 与 rule-based 实现；它可基于 makespan、路线成本、瓶颈路线、近期改进和 operator performance 建议 destroy/repair/phase。没有在线真实 LLM advisor；无效建议回到 ALNS 自适应选择。
- 当前 ALNS 的每轮 local search 固定调用 stronger local search 一次；acceptance 支持 improvement-only 与 simulated annealing。Operator 权重由累计 reward/uses 更新，advisor 若给出有效 operator pair 则覆盖该轮 weighted pick。
- 内置 `greedy_insertion`、`regret_k_insertion`、`bottleneck_balancing_insertion` 的候选插入都调用 route DP；`dp_aware_insertion` 当前只是 `greedy_insertion` 的别名。因此“DP-aware ALNS”是已实现架构事实，但不能未经消融就声称为独立新算法贡献，现有 `alns`/`alns_dp_aware` 差异需谨慎核验。
- Offline operator evolution 已实现 provider abstraction（mock/file/langchain）、候选持久化、AST/hash/timeout-only execution boundary、smoke/benchmark、repair 对固定 baseline repair 的评价、destroy+固定 repair 评价、failure metrics、eligible top/weak feedback、多轮 revision、单个 best-per-type selection、freeze registry 与 ALNS deployment gate。
- 当前闭环中的“elite retention”主要表现为跨轮 feedback 中的 top-k/weak rows 与全局 best row 更新；没有把 top-k elite code 明确复制进下一代候选池，也没有显式多样性维护、行为去重、portfolio selection 或可信 lineage receipt。
- 当前 freezing 每个 operator type 最多冻结一个 best row；因此“LLM-generated portfolio”尚未实现，只能作为候选研究机制。
- 当前 failure feedback 会聚合 `failure_type_breakdown`，但 invalid/timeout/blocked/fallback 候选不会进入 top/weak 示例；尚无按失败类型组织的代码结构诊断、定向 revision instruction 或 failure-specific critic。方向 D 与当前架构相容，但属于计划机制。
- 当前没有 instance-feature-conditioned generation：generation/revision prompt 的输入主要是 operator type、round、previous summary/top/weak；机器人数量、任务规模、矩形分布、路线失衡和停滞特征尚未形成明确 feature schema 或 conditioning protocol。
- Initial prompts 已含 MR-RCRP、DP-aware insertion、bottleneck/geometry/H-V gap 等 problem-specific hints；这属于提示先验，不等于 instance-conditioned generation，也不能单独作为强论文贡献。
- Repair evaluator 将候选与固定 greedy repair 在同一 partial solution 上比较；destroy evaluator 将候选 destroy 与固定 greedy repair 配对，再与原完整 incumbent 比较。指标含 makespan delta、relative improvement、success、invalid/error/timeout，评价调用 problem-aware solution/route DP。
- 当前 feedback 给 revision prompt 的是 aggregate summary、eligible top rows 和 eligible weak rows；failure type 仅以计数进入 summary，没有向 LLM 提供失败源码片段、contract violation 详情、结构诊断或 matched failure cases。
- 当前 evolution 默认 `benchmark_instance_glob=data/R*_T*_*.txt`，配置也覆盖全部 `data/`；没有 generation/train、selection/dev、held-out final test 的物理或清单隔离。Phase 5A 必须规定 final test 在设计冻结前不可见，并且 final test 结果不得回流 LLM。
- 现有 benchmark runner 只有单次逐实例 mode 运行与 CSV；没有多 seed 聚合、置信区间/配对检验、LLM 成本、泛化 split 或 contamination 标记。当前任何优越性、泛化、稳定性和成本收益均属于未实验支持主张。
- `alns_dp_aware` 仅额外启用 `dp_aware_insertion`，而该算子当前调用与 greedy 完全相同，且其他 insertion 已使用 route DP；因此现有 ablation 不能支持“新增 DP-aware operator 带来独立收益”。论文若保留 DP-aware ALNS 贡献，必须把它定位为统一精确评价架构并设计真正可识别的对照。
- 本阶段授权范围未包含外部文献检索；因此“新颖性潜力”只能作为相对当前项目与常见 framing 的候选判断，不能写成已完成 novelty check 或无先例声明。

### 用户确认的论文定位

- 采用跨领域 AI-for-Optimization 定位：论文核心问题不是“如何为 MR-RCRP 构造更强 ALNS”，而是“如何把 LLM 生成的搜索算子经过可验证、可复用、fail-closed 的离线演化流程转换成组合优化组件”。
- MR-RCRP 是结构化组合优化验证载体；DP-aware ALNS 是执行和精确评价 generated operators 的宿主框架。二者必须完整说明，但不与 LLM operator evolution 争夺主贡献位置。
- 内置基础算子、rule-based advisor 和 problem-specific operators 的论文角色是 baseline、control、ablation 与 scaffold，不应被包装为主要 LLM 创新。
- 优先贡献轴：multi-round generation/revision、portfolio/frozen reuse、DP/feasibility-aware feedback、fail-closed evaluation/deployment，以及 cost/validity/fallback/generalization analysis。

### Phase 5A 最终研究设计结论

- 五份研究文档已经创建并采用同一层级：A 是唯一主创新；C 与 D 是需要独立消融支持的辅助创新；B 只作为条件化/跨规模泛化消融。
- A 的可验证对象不是“是否调用 LLM”，而是等预算的 generation→validation→benchmark→elite retention→feedback→revision→freeze→reuse lifecycle。当前显式 top-k code retention 尚未实现，研究计划已将其列为实验前机制缺口。
- C 必须依据候选在实例/seed 上的行为互补性构造，不能把 score top-k 改名为 portfolio。当前代码只冻结每类 single best，因此所有 portfolio 表述均标为 planned/conditional。
- D 将 invalid、timeout、feasibility、performance 和 structural failure 分开；其中 structural label 必须由预先定义、可审计规则产生。当前实现只有 failure breakdown 和 eligible top/weak summary，尚未提供 failure-specific revision payload。
- B 的 feature schema 只能由 generation/train 与 dev 确定；只有在未见规模、多 seed、等 token controls 下稳定胜过 unconditional A 与 rule-based/shuffled controls，才可考虑提升其贡献地位。
- final test 被定义为 lockbox：方法、prompt、预算、elite/portfolio selection、ALNS 参数和统计方案冻结后才可打开；其任何结果都不能回流 LLM、prompt、selection 或调参。发生回流的 run 必须标为 contaminated。
- 论文贡献候选被划分为：A 核心方法；C/D 条件性辅助方法；fail-closed protocol 支撑性工程；性能/有效率/失败/泛化/成本为实验贡献；MR-RCRP + DP-aware ALNS 为验证框架。
- 安全口径保持克制：当前是 timeout-limited subprocess，不是 capability sandbox；CPU、内存、文件系统、网络、环境变量与后代进程树隔离仍未解决。
- 建立 H1–H7。H1–H6 覆盖 multi-round、DP-aware feedback、portfolio、跨规模迁移、成本摊销和 structured failure feedback；H7 是 B 的探索性条件化假设。每项均明确 independent variable、dependent variables、baselines、ablations、falsification condition 与所需日志。
- 所有新颖性只表述为候选潜力；未进行外部 literature/novelty check。所有性能、泛化、稳定性与成本收益均保持待实验验证状态，未声称真实 LLM 已证明有效。

## Phase 5A-R：Research-validity review（2026-08-06）

### 第一轮：定位与创新比较

- `research_positioning.md` 对 A/C/D/B 的贡献层级、LLM/ALNS/route-DP 角色和已实现/计划/未支持主张区分总体清楚；特别明确了 `dp_aware_insertion` 是 greedy alias、portfolio 尚未实现、真实 LLM 无效果证据以及 timeout-only 非 capability sandbox。
- 成本单位风险被准确保留：跨任务 Manhattan travel 未除以 speed，不能把一般 speed 下的目标当作已统一时间单位。该问题在实验协议冻结前仍是研究有效性的阻断条件，而不仅是论文 limitation。
- `innovation_review.md` 已覆盖 equal generation/benchmark budget、one-shot、no/rank/shuffled feedback、single/top-k/random/human portfolio 和跨规模 controls，方向选择具有基本可证伪性。
- 待继续核对的高风险点：实验独立单位与嵌套随机性、dev selection bias、portfolio selector 的额外在线自由度、structural failure 标签的可操作定义，以及“多实例/seed 参数接口”是否与实际代码能力完全一致。
- 新颖性评分明确只是候选潜力，没有冒充 literature novelty conclusion；本轮 research-validity review 不进行外部查新。

### 第二轮：研究计划、贡献与假设

- 三份文档都把 final test 设为 lockbox、要求等 token/evaluation/ALNS budget，并为 A/C/D/B 提供对照与证伪条件；贡献层级没有把 portfolio、真实 LLM 效果或 capability sandbox 写成既成事实。
- **候选 Required：统计独立单位尚未定义。** 当前只写 paired instances/seeds、均值/置信区间，没有明确“独立 operator-evolution run”才是 LLM 方法随机性的重复单位，也没有规定候选、seed、instance 嵌套时如何避免伪重复。单次 LLM run 产生的多个 candidates 不能作为独立样本支持 A/D/C。
- **候选 Required：H2 混合了两个干预因素。** “DP-aware performance feedback 与 feasibility information”同时变化，无法分别归因；应采用 2×2 factorial 或拆为 H2a（DP-aware performance signal）与 H2b（feasibility signal），且严格等 token/information budget。
- **候选 Required：failure taxonomy 未给互斥优先级。** `invalid` 的“返回结构无效”与 `feasibility` 的 duplicate/missing/partition/contract shape 可重叠；`performance` 又不是执行失败。需要 canonical mutually-exclusive primary outcome、可多标签 secondary diagnostics、固定分母与 aggregation rule。
- **候选 Required：final-test 在线选择边界有歧义。** C 允许预先固定的 ALNS adaptive selector 在测试实例内部依据搜索反馈选算子，但 lockbox 又禁止 test operator-selection trajectory 回流。需要明确“允许单个 test run 内按预注册规则更新；禁止跨 test instance、跨 seed、跨 run 持久化或回写 portfolio/prompt”。
- **候选 Required：H5 的 break-even 缺少共同效用单位。** makespan quality 与 token/货币/compute 不能直接互相“抵消”；应预注册 quality-constrained cost、cost-constrained quality、Pareto/frontier 或明确 willingness-to-pay，避免事后选择 break-even 定义。
- **候选 Required：可复用范围需收窄。** 现有验证只覆盖 MR-RCRP 实例/规模；“reusable”当前最多指 frozen operator 在同一问题族跨实例复用，不能外推为跨组合优化领域复用。跨领域 AI-for-Optimization 是研究定位，不是跨领域实验证据。
- **候选 Consider：structural failure 容易把人工偏好写入 oracle。** 即使规则预定义，按“是否使用几何/负载敏感性”惩罚代码可能排斥有效但不同机制；更稳妥的是以可测行为、复杂度和退化测试定义 structural diagnostics，并单独报告标签可靠性。

### 第三轮：与代码/正式规格交叉核对

- `CostMatrix` 的三类 travel 均直接调用 Manhattan distance；state processing time 才除以 speed，证实五份文档的 speed=1/归一化时间风险判断准确。
- Evolution config/runner 确实提供 seeds 参数并在 repair/destroy evaluator 内按 instance×seed 循环；但这只证明 benchmark trial seed 接口存在，不等于论文已有独立 evolution-run replication 或有效置信区间。
- 当前 evolution loop 的 `previous_feedback` 只把 summary/top/weak 传到下一轮；`top_k_to_keep` 控制反馈示例数量，不是显式 elite source retention。文档将 elite retention 标为缺口是准确的。
- 当前结果仍是 `best_operators.json`/每类单 best 与 `freeze_best_operators`，没有 portfolio manifest/behavioral portfolio selection 实现；C 的 planned 标签准确。
- 正式规格已经要求固定实例、seed、初始解、repair/destroy pairing、trial 级日志和 paired statistics，但同样没有把独立 LLM evolution run、层级统计模型和 candidate-selection winner's curse 写成强制合同。
- Repair 的代码指标方向是 `baseline_makespan - candidate_makespan`，destroy 是 `incumbent_makespan - repaired_candidate_makespan`，正值为改善；相关文档口径一致。Destroy 指标衡量 destroy+fixed-repair 组合效果，不能直接解释成纯 destroy 因果效应。

### 第四轮：当前 benchmark 与数据可用性

- 当前 `data/` 只有 `R2_T6_0.txt` 与 `R2_T10_0.txt` 两个实例，均为 2 robots、单 replicate；现有数据无法同时支持 generation/train、selection/dev、final test，更不能支持跨机器人数量、跨规模或 geometry-family 泛化。五份文档虽要求扩展/拆分，但没有把“现有两实例绝不可用于三分割主实验”写成显式 no-go gate。
- `operator_evolution_langchain.yaml` 默认 glob 会把上述全部实例同时用于 evolution benchmark，seeds 只有候选内部随机数变化；不存在 split manifest。
- `benchmark_runner.py` 的 `rep` 来自文件名，不是运行重复；ALNS mode 使用默认 `random_seed=0`，runner 没有多 solver-seed 入口。研究文档不能把当前 batch runner 描述为已有多-seed solver experiment protocol。
- Repair benchmark 对每个实例只构造一个 deterministic partial solution，所有 seeds 共享同一 partial/full/baseline；seed 仅改变 generated candidate 的 RNG。确定性 candidate 在多个 seed 下会重复同一 observation，不能把这些重复当独立统计样本。
- 当前 failure breakdown 把“合法执行但未改善”计入 execution `success`，同时 `TrialMetric.success=False`；计划中的 D `performance` failure 尚不是当前 primary failure status。正式研究协议必须区分 execution success、feasibility validity 与 optimization improvement 三条轴，不能复用一个 `success/failure_type` 名称。
- Destroy shape/contract 异常当前可能落入 `runtime_error`，完整性问题落入 `invalid_solution`；这进一步证明 planned D taxonomy 需要新的、互斥且版本化的标注规则，不能直接把现有 breakdown 当五类 ground truth。

### 第五轮：协议一致性与进入下一阶段的门槛

- Formal spec 同样把 baseline stabilization（成本单位、feasibility、可复现核心）列在真实 LLM/论文实验之前，说明 Phase 5A 文档承认的 speed 与数据缺口不是可忽略事项。
- 当前只有两个 2-robot 实例的事实应提升为显式实验 no-go：在新实例族、分组 split manifest 和冻结生成规则存在前，不允许把当前两个文件硬拆成 train/dev/test，也不允许使用 final-test 实例设计生成器分布。
- 七个假设目前都共享同一 primary metric，但只在末尾笼统要求多重比较标注；应明确 confirmatory hierarchy。建议 H1 为唯一核心 confirmatory，H6 与 H3 为按顺序检验的辅助 confirmatory，H2/H4/H5 为关键 secondary，H7 保持 exploratory。
- Final test “一次性评价”应定义为一次锁定的 batch（包含预注册 instances×solver seeds×independent evolution runs），而不是只跑一个 seed；失败后不得重新调参并把同一 test set 当新 lockbox。
- 文档正确把 baseline/runner/portfolio/D mechanisms 视为未完成或验证载体，没有违反 AGENTS 的“先稳定 baseline”方向；但 README 已暴露真实 provider 命令，研究计划仍须维持当前不授权执行的 gate。

### Phase 5A-R 最终裁决

#### Critical（实验执行 no-go）

1. **独立统计单位与层级设计未封闭。** `paired instances/seeds + CI` 不足以评价随机 LLM evolution。主方法的独立重复应是从 provider generation 开始的完整 evolution run；candidate、round、benchmark seed 和 instance 都嵌套其中。若不按 evolution run/instance family 聚类，central A/C/D evidence 会发生伪重复与 winner's-curse 低估。
2. **现有数据不能支持任何三分割或泛化结论。** 磁盘只有两个 R2、单 replicate 实例。进入实验前必须先冻结实例生成与纳入规则、family/group split、最小规模/重复数和 final-test manifest；同时解决已知 speed 成本单位口径。当前两个文件不能被硬拆为 generation/dev/test。

#### Required

1. H2 必须拆分 DP-aware performance feedback 与 feasibility feedback，保持 evaluator、candidate pool 和 token/information budget 不变，避免把联合干预归因给 DP-aware signal。
2. D 必须定义互斥 primary outcome precedence；execution status、feasibility validity、performance improvement 和 structural diagnostics 应是分轴记录，不能把当前 `success/failure_type` 直接扩成五类 ground truth。
3. C 必须明确 test-time selector state：允许预注册规则在单次 test run 内自适应，禁止其状态跨 instance、seed 或 run 持久化，更禁止回写 LLM/prompt/portfolio。
4. H5 必须定义可比较的成本 estimand。质量与货币不能直接“抵消”；应使用 quality-constrained cost、cost-constrained quality、Pareto frontier，或明确 willingness-to-pay 后再定义 break-even。
5. “可复用”必须限定为 MR-RCRP 问题族内的 frozen reuse。除非后续加入第二个组合优化领域，否则跨领域 AI-for-Optimization 只能表示研究社区定位，不能表示跨领域泛化证据。

#### Consider

- 将 H1 设为唯一核心 confirmatory，H6/H3 作为顺序检验的辅助 confirmatory，H2/H4/H5 为 secondary，H7 保持 exploratory；预先规定多重比较控制。
- Structural diagnostics 优先基于可观测行为、复杂度和退化测试；若包含人工/LLM critic 标签，报告盲标规则、一致性与 label-error sensitivity。
- 对真实 provider 运行按 block 随机化方法顺序，记录精确模型/endpoint/time/version、temperature、重试和 token；云模型漂移时把时间块纳入分析。
- Portfolio construction 应报告 dev-fold/bootstrap stability，避免单个 dev 集上的 behavior matrix 偶然决定组合。

#### FYI

- 五份文档准确保持 A 主线、C/D 辅助、B exploratory ablation；没有声称真实 LLM、portfolio、泛化或成本收益已经成立。
- Route DP 的条件精确性、destroy+fixed-repair 归因、`dp_aware_insertion` alias、fallback/reward 隔离和 timeout-only 非 capability sandbox 口径与代码一致。
- Review verdict：**Request changes**。只允许继续文档修订；不授权真实 LLM、实验或大规模计算。

## Phase 5A-R：Research validity revision（2026-08-06）

- **Critical 1 文档修复：** `llm_operator_evolution_research_plan.md` 与 `research_hypotheses.md` 现把完整 LLM evolution run 定义为 generated-method 独立重复；candidate/round/benchmark seed/instance 明确嵌套。实验层级、run×family primary estimand、cluster-aware/hierarchical analysis、双层 bootstrap、独立 run 数量报告和 H1→H6→H3 gatekeeping 已写入。
- **Critical 2 文档修复：** 定位、研究计划、假设与贡献文档明确当前仅两个 R2 单-replicate 实例，只能 smoke/demo；禁止硬拆三组或形成 LLM/泛化/显著性结论。正式实验前必须冻结 generation rules、families、robot/task combinations、replicates、family-level splits、seeds、exclusion、leakage 与 final-test manifest。
- **Modeling no-go：** travel/processing speed 单位问题被提升为 blocking decision；未固定 speed=1 或统一单位前，makespan 只能叫 prototype metric，不能解释为最终物理时间。
- **Required 1 修复：** H2 采用 DP-aware performance × feasibility/failure 的 2×2；H2a/H2b 是主效应，H2c 交互仅 exploratory，并要求 evaluator、candidate pool、rounds、benchmark 与 token/information budget 配平。
- **Required 2 修复：** D 改为 execution、feasibility/contract、optimization、structural 四轴；前三轴 primary labels 互斥，structural 可多标签；precedence 与分母均固定。`no_improvement` 被定义为 tied/worsened 的派生指标，避免重复计数。
- **Required 3 修复：** portfolio composition/set/policy 在 train/dev 后冻结；final test 只允许单 run 内预注册 adaptive update，并在每个 instance/seed/evolution run/test file 重置，禁止持久化或设计回流。
- **Required 4 修复：** H5 改成 quality-constrained cost、cost-constrained quality 与 Pareto frontier；break-even 只在预注册 utility/WTP 下作 sensitivity analysis。
- **Required 5 修复：** 五份文档统一把 reusable 限定为 MR-RCRP problem family 内跨实例/规模/运行复用；AI-for-Optimization 是社区定位，不是 cross-domain empirical claim。
- **Consider 纳入计划但未实现：** provider 时间块随机化、精确 model/endpoint/temperature/retry/token 记录、portfolio dev-fold/bootstrap stability、behavior-first structural diagnostics 与标签一致性。它们没有被描述成当前能力。

## Phase 5A-S：建模与数据协议事实核对（2026-08-06）

- 四份目标文档 `docs/modeling_decisions.md`、`docs/instance_protocol.md`、`docs/final_test_lockbox_protocol.md`、`docs/experiment_no_go_checklist.md` 在本阶段开始时均不存在，需要新建，不能把 Phase 5A-R 的原则性 no-go 当成已冻结协议。
- `state_generator.py` 的内部覆盖成本为 `n_sweeps * traversal_length / speed + (n_sweeps - 1) * turning_time`；`cost_matrix.py` 的 depot→state、state→depot、state→state 三类移动成本均为原始 Manhattan distance，没有除以速度。
- 当前 `Instance`/文本格式只有一个 `speed`，没有独立 `travel_speed`。因此当前目标只有在 `speed=1`、或把 Manhattan distance 预先解释为归一化时间/代价时才量纲一致；否则是混合量纲 prototype metric。
- 当前 `data/` 只有 `R2_T6_0.txt` 和 `R2_T10_0.txt`，均为 2 robots、单 repetition；只能用于 smoke/demo 和接口闭环，不能支持 family-level train/dev/final-test、泛化或统计推断。
- `configs/operator_evolution_langchain.yaml` 与 `EvolutionConfig` 默认使用 `data/R*_T*_*.txt`，`evolution_loop.py` 直接展开该 glob。正式实验必须改用显式 split manifest/allowlist 并在 preflight 中验证不相交与 hash；仅靠命名或目录约定不足以形成 lockbox。
- 统一物理时间口径会影响 cost matrix、实例 schema/loader、路线 DP 的输入成本、lower bounds、相关测试、README/config 文档以及所有既有 makespan 解释。任何正式结果必须在口径实现和测试冻结后重新生成。
- 三种建模候选已正式比较：A 与当前代码最一致但只适合 prototype；B 统一为时间、物理解释最强；C 是可行的无量纲加权目标，但权重/normalization 容易弱化 MR-RCRP 的完成时间解释。
- **推荐但尚未批准的正式决策：** 采用 B，并使用独立 `travel_speed`，而不是隐式把 sweep speed 用作 travel speed。旧格式可制定显式迁移规则，但不能通过未记录默认值获得正式结果。
- `instance_protocol.md` 将 family 定义为 robot/task counts、rectangle/spatial distributions、sweep width/speed、travel speed、turning time、metric/objective/generator version 的固定组合；replicate 与 seed 是 family 内 instance record，不是新 family，也不是 solver/evolution repetition。
- 规模提案区分 smoke、small、medium、large 与 stress/generalization；confirmatory generated conditions 建议目标 20 个 independent evolution runs。Benchmark/solver seeds 只嵌套估计运行方差，不能替代 evolution-run repetition。
- Final test 被定义为冻结 batch，而不是单文件/单 seed。允许预注册 portfolio selector 在单 run 内更新，但必须跨 instance、seed、evolution run 和 test file 重置；任何 test 信息回流都使 lockbox contaminated。
- `experiment_no_go_checklist.md` 当前结论为 **NO-GO**：四份协议虽已创建，但尚待批准；建模代码、正式实例、manifests 和 manifest-only runner 均未实现。文档完成不能被解释为实验阻塞项已物理关闭。

## Phase 5A-S-R：Modeling/data protocol 独立复审（2026-08-06）

### 初审确认

- 候选 B 已给出明确公式、独立 `travel_speed`、单位约束、schema/CostMatrix/DP/tests/docs 影响面、旧结果作废与重跑规则，具备负责人批准所需的主要信息。候选 A/C 的限制也没有被隐藏。
- 混合单位风险没有被误写成已解决事实：当前 A 被限定为 `travel_speed=1`/归一化解释下的 prototype metric，禁止进入 confirmatory result；B 未批准、实现、测试前不允许物理时间主张。
- 两个现有 R2 单-replicate 文件在 instance、lockbox、checklist 三处均限定为 smoke/demo，禁止用于三分割、LLM 效果、泛化或统计推断。
- Family schema 覆盖 robots/tasks、geometry/spatial distributions、sweep/travel/turn parameters、objective/generator version；replicate、instance seed、solver seed 与 independent evolution run 已分层，candidate/benchmark seed 不会被冒充独立 evolution repetition。
- Lockbox 禁止 final-test feature/performance/failure/trajectory/cost 回流 prompt、generation/revision、selection、portfolio、model choice 或 tuning；run-local adaptive selector 允许但跨 instance/seed/evolution run/file 强制重置。
- Default glob 风险被准确识别，正式路径要求 manifest-only allowlist、exact input set、hash、split 不相交和 fail-closed preflight；实现前继续 no-go。

### 候选 Required

1. `experiment_no_go_checklist.md` 把“进入 Phase 5B 文档化实验协议”和“开始论文级/真实实验”绑定为同一组 33 个 BLOCKING 条件。数据生成、manifest-only runner、正式 manifest 和建模实现本应阻止**实验执行**，但不应阻止继续编写用于冻结这些细节的 Phase 5B 文档。需要拆成 `Phase 5B documentation-entry gate` 与 `formal-experiment execution gate`，否则阶段语义自相矛盾且无法用 Phase 5B 完成预注册设计。
2. 规模表写“每 family：train 10；dev 10”，后文又规定同一 family ID 只能属于一个 split。虽然 6.1 可解释为 train-assigned/dev-assigned families 各 10，但表面措辞仍可能诱导把同一 family 的 replicates 分到两组；需明确每个 family 只取其所属 split 的 repetitions。
3. 候选 B 把 makespan 表述为“完成所有机器人任务所需时间”，但目前只显式 caveat Manhattan metric。正式批准时还需冻结 constant speed、无障碍/冲突/拥堵、无加减速、无能耗/补能等简化假设，或改称“该运动模型下的 estimated completion time”，避免量纲统一后升级为未经支持的真实世界时间主张。
4. 协议给出了每 family replicates，却没有冻结每个 split 至少包含多少个**不同 family IDs**。主分析需要 over evolution runs and instance families 的聚合/CI；若 final test 只有一个或极少 family，family-level uncertainty 无法估计。至少应在 Phase 5B 冻结 family matrix 与每个 split/stratum 的最小 family 数。

### 当前 gate 倾向

- 未发现需要推翻 A/B/C 或 lockbox 架构的 Critical。
- 在负责人批准 B + independent `travel_speed`、批准 instance/lockbox protocol，并澄清 Phase 5B documentation gate 前，不建议进入 Phase 5B。
- 即使允许 Phase 5B 文档化，真实 LLM、正式 operator evolution、final-test 和大规模实验仍必须保持禁止，直到 experiment-execution gate 全部关闭。

### 代码与既有研究规格交叉核对

- 生产事实再次确认：`state_generator.py` 只对 coverage length 使用 `/speed`；`CostMatrix` 三类 travel 都直接返回 Manhattan distance；loader 第二行严格为三个值；现有两个实例 speed 均为 1。`modeling_decisions.md` 没有把尚不存在的 travel speed 写成已实现事实。
- `EvolutionConfig` 和 langchain YAML 都默认 `data/R*_T*_*.txt`，loop 直接 `project_root.glob(...)`。文档提出的 manifest-only/exact-input gate 是未来机制而非当前能力，口径准确。
- Phase 5A-R 的 hierarchy 与新 instance protocol 一致：完整 evolution run 是独立重复，candidate/round/benchmark seed/instance 嵌套，solver seed 估计 frozen set 运行方差；主结果先按 evolution run × family 聚合。
- 既有研究计划要求 bootstrap/CI 同时保留 evolution-run 与 family 层级，因此 distinct final-test family 数不能无限期只写“以后进 manifest”；Phase 5B 文档必须把 family matrix/最小 family count 作为显式冻结项。
- 全库 Phase 5B 文本确认 gate 语义确有混用：`experiment_no_go_checklist.md` 与四份 Phase 5A-S 文档把“Phase 5B”同真实实验/lockbox execution 并列禁止，而研究计划本身需要后续文档化来冻结精确预算和统计脚本。应在批准前明确 Phase 5B 的定义，避免把 protocol-writing 与 experiment-running 视为同一授权。

### 最终复审裁决

#### Critical

- 无。三种成本候选、R2 smoke-only、family-level split、lockbox、default-glob 风险和随机性层级都没有事实性反转或会直接使后续设计失效的缺口。

#### Required

1. **先完成建模决策确认。** 负责人需明确批准 B + independent `travel_speed`，并把“物理时间”限定为在 Manhattan/constant-speed/no-interaction 等简化运动模型下的 estimated completion time；否则只批准了量纲，未批准物理解释边界。
2. **拆分两级 no-go gate。** `Phase 5B documentation-entry` 只要求建模/instance/lockbox 决策已批准并解决本轮文档歧义；`formal-experiment execution` 才要求 schema/CostMatrix 实现、数据生成、manifests、runner 测试和全部审计证据。当前清单把二者混为一体，阻止用 Phase 5B 文档冻结后续实验细节。
3. **收紧 family split 合同。** 明确表中 train/dev 数量指“各自 split 内不同 family 的 per-family repetitions”，任何 family 不可同时贡献两组 repetitions；family→split assignment 或其确定性规则必须在实例生成前冻结，不能生成后按几何难度选择。
4. **冻结 distinct-family 数量。** Phase 5B 必须预注册每个 split/size/distribution stratum 的最小 distinct family count；否则既有 over-family aggregation/bootstrap 没有足够 sampling unit。Replicate 数不能替代 family 数。

#### Consider

- 为 B 增加 shared-speed sensitivity (`travel_speed=sweep_speed`) 作为次要对照，但不与正式 independent-speed 结果混用。
- Lockbox manifest 可增加 `split_assignment_rule_hash`、`family_matrix_hash` 与 contamination owner，强化审计；这不阻止文档化阶段。
- 目标 20 个 evolution runs 和 10/20 replicates 应在看 final test 前以 precision/power 与预算校准；校准只能改变预注册整体设计，不能按方法表现删 family。

#### FYI

- 文档正确把 manifest-only runner、travel-speed schema、正式数据与 lockbox 都标为未实现；所以通过本次文档复审不会自动关闭正式实验 no-go。
- Review verdict：**Request changes（0 Critical，4 Required）**。当前不允许进入 Phase 5B；完成 Required 并由负责人批准后，可进入**仅文档化** Phase 5B。真实 LLM、正式 operator evolution、final-test 与大规模实验仍禁止。

### 建模决策批准记录（2026-08-06）

- 负责人已批准候选 B：统一时间单位，并使用独立 `travel_speed` 作为正式实验主口径。
- 正式目标解释为 Manhattan travel、constant speed、no collision/congestion、no acceleration/deceleration、no charging/refueling 假设下的 **estimated completion time**；不声称是实际机器人系统的完整物理执行时间。
- `travel_speed=sweep_speed` 仅作为 sensitivity，不是主口径，也不得作为未记录默认迁移值。
- Phase 5A-S-R Required 1 已关闭。`objective_model_version` 命名、代码/schema/CostMatrix 实现和测试仍未完成；当前代码输出仍是 prototype metric。
- 其余 3 个 Required 保持开放：拆分 documentation/execution gate、收紧 family split contract、冻结 distinct-family minimum。Phase 5B、真实 LLM、正式/final-test/大规模实验仍禁止。

## Phase 5A-SR：Required revisions 初始核对（2026-08-06）

- `modeling_decisions.md` 已包含获批 B、独立 `travel_speed`、estimated-time 假设和实现前 prototype gate，但 A/C 标题仍是“候选”，需要显式改为 `prototype legacy metric` 与 `alternative but not selected`，以免贡献/实验文档继续把三者看作未决并列选择。
- `instance_protocol.md` 已定义完整 family 字段和 family-ID hash，但规模表仍以 `train 10；dev 10` 表示 per-family 数量，且 split assignment 仍允许“生成后、只要未看 performance”；这不足以关闭 Required 3。
- 当前生成顺序是先生成全部实例、再分配 split，与“family→split rule 必须在实例生成前冻结”冲突，需要把 assignment rule/family matrix 的冻结移到生成之前。
- 当前协议只有 per-family replicate 建议，没有按 `split × size stratum × distribution stratum` 固定 distinct-family minimum；Required 4 尚未关闭。
- 建模代码/schema、formal data、manifests 与 runner 都仍未实现；这些应进入 formal-experiment execution gate，而不是阻止 Phase 5B 文档化协议的编写。

### Phase 5A-SR 修订结果

- **Required 1 已文档化修复：** B 明确为 formal experiment modeling decision；A 改为 prototype legacy metric；C 改为 alternative but not selected。迁移合同覆盖 instance/config independent `travel_speed`、`Manhattan distance / travel_speed`、README/AGENTS/tests/configs/实例格式/旧结果同步；迁移前输出仍只允许 prototype smoke，禁止论文结论。
- **Required 2 已文档化修复：** `experiment_no_go_checklist.md` 现拆成 Gate A（Phase 5B documentation-entry）与 Gate B（formal-experiment execution）。Gate A 即使通过也只授权文档；真实实验仍需关闭全部 EXEC-BLOCKING，真实 LLM 还需 Phase 7 preflight 与显式风险确认。
- **Required 3 已文档化修复：** family 字段包含 robots/tasks、rectangle/spatial distributions、sweep width/speed、independent travel speed、turning time、generation rule version。Family 不跨 split；assignment/rule 在生成前冻结；geometry/baseline/LLM performance 后选 split 被禁止；`family_matrix_hash` 与 `split_assignment_rule_hash` 进入 protocol/manifests，final-test assignment 成为 lockbox 对象。
- **Required 4 已文档化修复：** 每个实际纳入的 split×size×distribution stratum 预注册最低 distinct-family floor 为 train 4、dev 4、final-test 8。Family ID 是 CI/bootstrap 抽样单位；replicates 只估计 family 内变异，不能替代 family 数。低于 floor 或资源不足只能报告 pilot/exploratory。
- Study tiers 已明确：现有两个 R2 文件仅 smoke/demo；formal pilot 只使用 train/dev 估计 runtime/variance/difficulty/precision，不接触 final-test；formal experiment 必须满足 floor 和 Gate B。
- 20 个 independent evolution runs、train/dev 每 family 10 和 final-test 每 family 20 仅保留为 Phase 5B precision/power 候选，不是本轮硬性承诺；实际数量必须在打开 lockbox 前冻结并报告。
- Consider 已纳入：manifest 规划增加 `family_matrix_hash`、`split_assignment_rule_hash`、`contamination_owner`；provider 时间块、精确模型版本和 portfolio dev stability 延后 Phase 5B/6/7。

### Phase 5B 建议

- 建议下一步进行 **Phase 5B documentation-entry independent review**，核对 Gate A 中 instance protocol 与 final-test lockbox protocol 的批准项。
- 本轮不直接进入 Phase 5B。Gate A 当前仍为 NOT PASSED；即使后续通过，也只允许文档工作。
- Gate B 当前全部为未来执行证据，真实 LLM、formal operator evolution、final-test 和大规模实验继续禁止。
## 2026-08-06：Phase 5A-SR-R 复审初步发现

- 四份受审协议已明确批准 B + independent `travel_speed`，并把 estimated completion time 限定在 Manhattan、恒速、无碰撞/拥堵、无加减速、无充换能的简化模型内。
- `travel_speed=sweep_speed` 只作为预注册 sensitivity；当前 prototype metric 与 formal objective 的证据边界明确。
- NO-GO 已拆为 Gate A（只授权 Phase 5B 文档工作）和 Gate B（正式实验执行）；Gate B 覆盖建模迁移、测试、generator/manifests、manifest-only runner、统计冻结和 Phase 7 real-LLM preflight。
- 同一 family 不跨 split，assignment/rule 在实例生成前冻结并哈希，禁止生成后按 geometry、baseline 或 LLM performance 挑选 split。
- 每个纳入的 split×size×distribution stratum 已设 distinct-family floor：train 4、dev 4、final-test 8；family-level CI/bootstrap 以 distinct family 为抽样单位，replicate 不替代 family 数量。
- 当前两个 R2 文件仍明确只限 smoke/demo。初步未发现 substantive Critical/Required；仍需交叉核对代码/数据事实，并处理本次 review 通过后 Gate A 状态的行政同步。

## 2026-08-06：Phase 5A-SR-R 独立复审结论

- **Verdict：Approve。** 0 Critical、0 Required；四份协议足以进入 Phase 5B 的 documentation-only experiment protocol 工作。
- **建模：** B + independent `travel_speed` 已明确批准；estimated completion time 的 Manhattan/恒速/无碰撞拥堵/无加减速/无充换能边界完整；共享速度只作 sensitivity。
- **门禁：** Gate A 只授权文档，Gate B 覆盖 objective/code/tests、generator/data/manifests、lockbox、manifest-only runner、统计和 real-LLM preflight。当前 Gate B 有 32 个开放 EXEC-BLOCKING，另有 2 个 REAL-LLM-BLOCKING，故不能运行正式/大规模实验或真实 LLM。
- **数据有效性：** family 不能跨 split；assignment/rule 在生成前冻结并哈希；禁止 post-hoc split；train/dev/final-test floor 为每纳入 stratum 4/4/8；bootstrap/CI 单位是 distinct family，replicates 不替代 families。
- **事实交叉核对：** 当前 data 只有两个 R2 实例；loader 只有单一 `speed`；CostMatrix 仍用 raw Manhattan distance；默认 evolution config/runner 仍用全量 glob。协议中的执行 NO-GO 与代码事实一致。
- **Consider：** 4/4/8 是最低 floor，不是 power 证明。Phase 5B 应用 train/dev-only pilot 或先验 precision analysis 检查 final-test family 数是否需要提高；无论如何不得在看 final-test 后调整。
- **行政状态：** 受审 checklist 仍保留“等待本次 review”的两个未勾选项，因为本轮是 review-only、未改受审正文。本复审记录即为独立批准；Phase 5B 的首次文档同步应把两项标为通过并更新 Gate A 状态，不需要再次做建模选择。
- **用户决策：** 进入 Phase 5B documentation-only 不需要再次批准 B、family split 或 lockbox 原则。具体 objective version、family matrix、replicate/evolution-run 数及 manifests 仍须在 Phase 5B/执行前冻结，但不是当前 documentation-entry blocker。
## 2026-08-06：Phase 5B 文档入口事实

- Phase 5A-SR-R 已独立批准 B + independent `travel_speed`、family-level split、lockbox 与双层 NO-GO；Phase 5B 只获准编写论文级实验协议。
- 8 份目标文档当前均不存在：`research_questions.md`、`experiment_protocol.md`、`ablation_plan.md`、`reproducibility_checklist.md`、`result_table_plan.md`、`manifest_spec.md`、`statistical_analysis_plan.md`、`pilot_plan.md`。
- 本阶段不得运行真实 LLM/provider、正式/final-test/大规模实验，不得修改 `src/`、`configs/`、`data/`、`tests/`，也不得把两个 R2 smoke/demo 实例当论文证据。
- Gate A 的两个待 review 项可同步为完成；这不关闭 Gate B，也不构成真实 LLM 或实验授权。

## 2026-08-06：Phase 5B 上游研究合同

- H1 是唯一 primary confirmatory；H6、H3 仅按固定顺序 gate-kept；H2/H4/H5 是 secondary/exploratory，H7 始终 exploratory。
- Generated-method 的独立重复单位是完整 evolution run；candidate、round、instance、benchmark/solver seed 均为嵌套 observations。
- Primary estimand 固定为 held-out final-test families 上 multi-round LLM-evolved frozen portfolio 相比 strongest non-LLM ALNS 的平均相对 makespan improvement。
- A 是核心 offline operator evolution，C 是 behavior-complementary frozen portfolio，D 是 four-axis failure-informed revision，B 只作条件化/泛化消融。
- “可复用”仅限 MR-RCRP problem family 内跨实例/规模/运行复用；AI-for-Optimization 是社区定位，不是跨优化问题领域实证主张。
- 当前 portfolio、真实 top-k elite retention、failure-specific revision 和正式 split 尚非完整实现；实验协议不得把 planned mechanism 写成 implemented fact。
- fail-closed gate 是支撑性工程贡献，当前仍是 `timeout_only` subprocess，不是 capability sandbox。

## 2026-08-06：Phase 5B 上游数据与门禁合同

- 正式 objective 只能使用 `objective_v2_formal` 语义：coverage 使用 `sweep_speed`/turning time，travel 使用 Manhattan distance / independent `travel_speed`；当前实现仍只能标为 prototype。
- Family split 在生成前冻结，同一 family 不跨 split；现有 floor 是每个纳入的 split×size×distribution cell 中 train/dev/final-test 至少 4/4/8 个 distinct families。
- Final-test manifest 是 lockbox artifact；composition、selector、prompt、预算和统计须在打开前冻结，run-local adaptive selector 必须跨 instance/seed/evolution-run/test-file 重置。
- Formal runner 必须 manifest-only、验证 exact input set 和 file hashes；默认 glob 不能作为正式输入权威。
- Gate A 已在 `experiment_no_go_checklist.md` 同步为 PASSED（documentation only）；所有 Gate B 与 REAL-LLM blockers 保持开放。

## 2026-08-06：Phase 5B 协议设计结果

- 新建 8 份 paper-grade 文档，覆盖 RQ1–RQ7、正式 objective/family matrix/method budgets、A/C/D/H2 消融、层级统计、manifest-only schema、复现证据、9 张结果表和 train/dev-only pilot。
- Phase 5B minimum matrix 使用 D1 balanced-uniform、D2 mixed-clustered 和 stress D3 high-aspect-corridor；small/medium 用于 train/dev/ID test，large 与 `(12,480)/(16,800)` stress 作为 held-out generalization。
- 每个纳入 cell 的 distinct-family floor 保持 train/dev/final-test 4/4/8；planning minimum replicates 为 10/10/20，confirmatory generated conditions 目标 20 independent evolution runs。它们需要 train/dev-only precision/power review，不是已证明充分。
- Statistical plan 固定 H1→H6→H3、run×family 聚合、two-way cluster bootstrap、Holm exploratory correction，并提出 `δ_MCID=0.02` 与 projected CI half-width `≤0.02`，待独立 protocol review。
- Manifest spec 要求 strict canonical hash、exact input allowlist、manifest-only runner、final-test lockbox/file hash、claimed metadata 与 runtime authority 分离。
- Pilot 分 P0 smoke、P1 objective-v2 mock/file systems pilot 和仅在 Phase 7 批准后的 P2 train/dev real-provider precision pilot；任何阶段均不产生 final-test claim。
- 初次文档合同核验 161/161 PASS；跨文档扫描无 TODO/TBD/FIXME 或越权运行表述；`src/configs/data/tests` 修改数为 0。
- 修正核验脚本转义后，最终完整合同核验 189/189 PASS；8 份目标文档 SHA-256 已输出，Gate B 的 32 个 EXEC-BLOCKING 与 2 个 REAL-LLM-BLOCKING 均保持开放。
## Phase 5B-R research-protocol review（初步，2026-08-06）

- 已审阅 `research_questions.md`、`experiment_protocol.md`、`ablation_plan.md`、`statistical_analysis_plan.md`、`manifest_spec.md`、`reproducibility_checklist.md`。
- 已确认的强项：正式实验唯一采用 `objective_v2_formal`；`objective_v1_prototype` 限于 smoke/demo；LLM-generated method 的独立重复单位是完整 evolution run；candidate、round、instance、solver/benchmark seed 明确为嵌套观测，不能当作独立重复；family-level split、manifest-only、final-test lockbox、A/C/D 消融、H2 2×2 因子设计及 H5 cost-quality/Pareto 口径均已写入协议。
- 初步 Critical 风险：主 estimand 从 “valid paired result” 开始聚合，但 `no_valid_operator`、冻结/部署失败或整轮无可评价 generated portfolio 的处理尚未冻结，只留待未来制定 conservative handling/sensitivity。若直接排除这些 evolution runs，会对 generated method 产生幸存者偏差，并破坏独立 evolution-run 层级上的主分析。
- 初步 Required 风险：H1 的 MCID 口径不一致。协议预注册 `delta_MCID=0.02`，但支持规则为点估计达到 0.02 且置信区间下界仅大于 0；这只能同时表达“点估计具实践量级”和“统计优于 0”，不能支持效应高于 MCID 的强结论。
- 初步 Required 风险：stage-1 seed/replicate 聚合仍写成候选规则（例如 median-over-seeds 后 mean-over-replicates，或 review 后另行冻结），尚非唯一、可执行的预注册分析规则。
- 初步 Required 风险：H2a/H2b 已消除因素混杂，但尚未分别冻结 primary response/estimand、效应尺度与检验链接；目前 factorial contrast 只定义了 cell 均值差，未明确均值对应 makespan、validity rate 还是其他结果。
- 初步 Required 风险：manifest 仍有机器合同歧义，包括缺少显式 `instance_id`，以及 `generation_seed`、`approved_by`、`notes` 等字段允许多种类型；这会影响严格 schema、唯一性检查与 canonical hash 的一致实现。
- 上述结论需在审阅 `result_table_plan.md`、`pilot_plan.md` 与 `experiment_no_go_checklist.md` 后定级确认；本条不是最终 review verdict。

## Phase 5B-R research-protocol review（最终结论，2026-08-06）

### Critical

1. **Primary estimand 尚未定义 generated-method 整轮失败的处理，存在幸存者偏差。** `statistical_analysis_plan.md` 从 `valid paired result` 计算相对改善，却只承诺未来为 missing/invalid/timeout/fallback 预注册 conservative handling/sensitivity；`no_valid_operator`、冻结失败、部署被阻止或整轮没有可评价 portfolio 的 independent evolution run 因此可能被排除。主分析必须以 scheduled independent evolution runs 为总体，冻结 intention-to-treat-like 的 run-level 规则：明确每种失败是否记为预注册 penalty、baseline-equivalent/no-improvement、censored/not-evaluable，以及对应 primary/sensitivity estimand；不得以 complete-case valid pairs 作为 generated method 的唯一主结果。Table 1 还应同时给 scheduled-run denominator 和 failure-aware primary estimate。

### Required

1. **H1/MCID 支持判据不一致。** `delta_MCID=0.02` 与“点估计 >= 0.02 且 95% CI 下界 > 0”不能证明效应超过 MCID。必须二选一并统一 RQ、SAP 与 Table 1：若主张 practical superiority，则 CI 下界应超过 0.02；若主张仅 statistical superiority，则 CI 下界 > 0，并把点估计达到 MCID 作为独立的 practical-relevance 描述，不得合并成单一强结论。
2. **Stage-1 与 primary model 仍有分析者自由度。** `median-over-seeds -> mean-over-replicates` 仍写为优先方案或可另选规则，mixed/two-way-clustered 分析也未冻结唯一主方法、权重、baseline 与 generated-run 的不对称层级处理及诊断失败 fallback。必须在 Phase 6A 前形成唯一可执行主路径，并将其他方法标为 sensitivity。
3. **H2 2×2 已避免 factor 混杂，但 estimand 未完成。** H2a/H2b contrast 尚未分别绑定 primary response、分母、效应尺度/链接函数与 multiplicity 角色。至少需要预注册 DP-aware feedback 的一个 primary quality response，以及 feasibility/failure feedback 的一个 primary validity response；其他 response 为 secondary，H2c 保持 exploratory。
4. **Manifest spec 尚不足以直接成为严格、canonical 的 manifest-only runner 合同。** 需要显式 `instance_id` 或冻结唯一复合键；将 `generation_seed`、`approved_by`、`notes` 等 union 类型收敛为唯一 JSON 类型；定义 record 唯一性、canonical ordering/serialization、duplicate/path-alias/symlink 规则，并明确 schema validation 失败必须 fail closed。否则 exact allowlist、split 不相交和 manifest hash 在不同实现间可能不一致。

### Consider

1. 为 dev 上选择 strongest non-LLM baseline 预注册 tie-break、候选数和选择稳定性/敏感性，避免 baseline 选择规则成为隐藏自由度。
2. `4/4/8` distinct-family floors、20 evolution-run target、每 family 10/20 replicates 和 0.02 precision/MCID 都是 planning values；应由 train/dev-only pilot 或保守先验给出 precision 依据，资源不足时按现有协议降级为 exploratory。
3. 预注册 provider/model 时间块、方法顺序随机化、版本/endpoint/temperature/retry/token 记录，以及 portfolio composition 的 dev-fold/bootstrap stability；这些不阻塞本轮协议修订，但在真实 provider Phase 7 前必须冻结。

### FYI / 已通过检查

- 当前文档持续明确禁止真实 LLM、正式/大规模实验和 final-test；Gate B 为 NO-GO。
- `objective_v2_formal` 是正式实验唯一口径，`objective_v1_prototype` 仅限现有两个 R2 smoke/demo。
- independent evolution run 已正确作为 generated method 的独立重复；candidate/round/instance/seed 未被当作独立重复。
- family-level split、同 family 不跨 split、distinct-family minimum、pre-generation assignment freeze、final-test lockbox 与 manifest-only/no-glob 原则一致。
- A/C/D 消融结构可区分主线与辅助贡献；H2 使用 2×2；H5 使用 quality-constrained cost、cost-constrained quality 与 Pareto，而非 makespan 和货币直接抵消。
- 九张计划表均列出允许/不允许结论；pilot 只使用 smoke/train/dev，明确不得接触 final-test，也不产生 LLM effectiveness claim。

### Review verdict

- **Request changes：1 Critical、4 Required。** 在这些协议问题关闭前，不建议进入 Phase 6A mock/file closed-loop planning。
- 真实 LLM、正式/大规模实验及 final-test 继续禁止。
- Phase 6 前的 EXEC-BLOCKING 工作至少包括：先关闭上述统计/manifest 协议缺口；随后才能规划 `objective_v2_formal`/independent `travel_speed` 迁移、versioned generator/family manifests、strict manifest-only runner/no-glob tests、mock/file closed-loop、analysis script/pre-registration、lockbox artifact 与 hashes。真实 provider 仍另受 Phase 7 preflight 和 runtime authorization 限制。
## Phase 5B-R statistical/manifest revision contract（2026-08-07）

- 本轮正式范围来自附件：仅修改 statistical/experiment/ablation/manifest/result/reproducibility/pilot/research-hypotheses 协议及三份 planning 文件；禁止修改 `src/configs/data/tests`、运行测试/实验/provider 或进入 Phase 6A。
- Critical 修订目标：主分析总体改为 all scheduled independent evolution runs；generated-method failure run 不得因 `no_valid_operator`、freeze/deployment blocked、missing runtime authorization、all-invalid 或 portfolio not evaluable 被 complete-case 删除。
- 预定 primary failure rule：每个 scheduled failure run 的 relative improvement 记为 0（相对 strongest non-LLM baseline 无改善），同时单独报告 failure/deployment/valid-portfolio rates；fallback 不能归因于 generated operator。Dominated/worst-rank 与 two-part endpoint 仅作 sensitivity/supplementary。
- Required 目标：区分 H1a CI lower > 0 与 H1b CI lower > 0.02；冻结唯一层级聚合/权重/CI/fallback；为 H2a/H2b 固定 response/scale/denominator；把 manifest 转为可机器执行的严格、唯一类型、canonical、path-safe、fail-closed 合同。
- 修订后仍需独立 review；本轮不会把文档完成当作 Phase 6A、真实 LLM、正式/大规模/final-test 实验授权。

### 修订前事实核对

- `statistical_analysis_plan.md` 当前确实从 `valid paired result` 定义 primary delta，missing/failure 仅写为未来 conservative handling/sensitivity；这不能保证 scheduled failure runs 进入主估计量。
- H1 当前判据为 point estimate >= 0.02 且 CI lower > 0，混合了 statistical superiority 与 practical relevance，不能支持“CI 超过 MCID”的声明。
- Stage 1 当前保留 `median-over-seeds then mean-over-replicates` 或另选规则；primary mixed model 与 bootstrap 的主次也未唯一冻结。
- H2 factorial 已固定 F00/F10/F01/F11 与预算，但 H2a/H2b contrasts 未分别绑定唯一 response、effect scale 和 denominator。
- Split manifest records 当前缺显式 `instance_id`，并允许 `generation_seed`、`approved_by`、`notes` 等 union 类型；canonicalization/path/duplicate 要求存在原则性描述，但还不是无歧义的 strict JSON contract。

### 本轮唯一设计选择

- Primary analysis population：all scheduled independent evolution runs。
- Primary failure rule：任何不能形成并评价 generated frozen portfolio 的 scheduled run，所有预注册 final-test families 上的 run×family relative improvement 记为 0；不使用 fallback makespan 归因 generated improvement。Failure/deployment/valid-portfolio rates 同时报告。
- Supplementary only：complete-case conditional-quality、two-part endpoint 和 dominated/worst-rank sensitivity；与主分析冲突时以 failure-aware primary 为准。
- Primary aggregation：seed arithmetic mean → replicate arithmetic mean → equal-weight family arithmetic mean → equal-weight evolution-run arithmetic mean；replicate/seed 不增加 family 权重。
- Primary CI：two-way cluster bootstrap over evolution runs and final-test families，固定 5,000 resamples 与 percentile 95% CI；hierarchical/mixed model 降为 sensitivity，从而消除“模型不收敛时再决定”的主分析自由度。
- H2a primary：scheduled-run-level failure-aware held-out portfolio relative improvement，百分点差；all scheduled runs 为总体且失败 run 记 0。H2b primary：valid deployable portfolio rate，分母为 all scheduled evolution runs，报告 risk difference；H2c exploratory。

### 正文修订后核对

- 统计计划已去除 `valid paired result` 的主分析进入条件，明确 scheduled runs、failure-zero rule、contamination 例外、complete-case supplementary-only 和冲突时以 primary 为准。
- H1a/H1b、equal-family/equal-run 聚合和 5,000-resample two-way cluster bootstrap 已在统计计划、假设、结果表和复现清单中交叉同步。
- H2a 使用 failure-aware quality percentage-point difference；H2b 使用 all-scheduled-run deployability risk difference；candidate-level rates 明确降为带独立分母的 secondary diagnostics。
- Manifest 已增加 `instance_id` canonical derivation、duplicate-file fail-closed、fixed JSON types、RFC 8785 hashing、canonical array ordering、data-root/symlink/alias/traversal 防线与 no-glob fallback 禁令。
- Heading/legacy-string scan 未发现旧 H1 主判据或旧 primary valid-pair 口径；仍出现的 `valid paired results` 只位于明确的 supplementary complete-case 边界。
- 文档保留 “不得以 string/list 等 union 类型表达” 作为禁止性说明；严格 schema 表内的 `generation_seed`、`approved_by`、`notes` 已分别固定为 integer、non-empty string、string。后续合同检查必须匹配旧完整字段行，不能只搜索被正文引用的禁用术语。

### Phase 5B-R revision disposition

- **Critical closed in documentation：** 主分析 population 固定为 all scheduled independent evolution runs；无法交付可评价 generated portfolio 的 run 在每个 family 主分析记 0 improvement，fallback 不归因；complete-case/two-part/dominated 分别降为 supplementary/sensitivity。Contaminated final-test batch只保留 accounting，不产生 confirmatory estimate。
- **Required 1 closed：** H1a statistical superiority 需要 CI lower > 0；H1b practical superiority 需要 CI lower > 0.02。点估计超过 MCID 但 CI 只超过 0 不再支持 practical claim。
- **Required 2 closed：** 唯一主链为 solver-seed arithmetic mean → replicate arithmetic mean → equal-family arithmetic mean → equal-scheduled-run arithmetic mean；5,000-resample run×family two-way cluster percentile CI 是 primary。Mixed model 仅 sensitivity；primary bootstrap 不能执行时结论 `inconclusive`。
- **Required 3 closed：** H2a 是 all-scheduled-run failure-aware held-out quality percentage-point effect；H2b 是 valid deployable portfolio scheduled-run risk difference；二者同属 Holm secondary family，H2c exploratory，四 cells 预算/访问固定。
- **Required 4 closed：** Manifest record/header 使用 fixed JSON types 与 `additionalProperties=false`；新增 canonical `instance_id`、RFC 8785 hashes、duplicate/path/symlink/alias/traversal checks 和整 run fail-closed/no-glob fallback。
- **Consider deferred：** strongest non-LLM dev selection tie-break/stability；4/4/8 family、20 runs、10/20 replicates 与 MCID/precision 的 train/dev-only justification；provider time-block/method-order randomization、版本/temperature/retry/token 及 portfolio stability。这些保留给后续 protocol/Phase 6/7 planning，不构成本轮已实现能力。
- **Gate：** 文档修订本身不授权 Phase 6A。需下一轮独立 review 达到 0 Critical/Required；真实 LLM、正式/大规模/final-test 实验继续禁止。
- **Verification evidence：** 完成前重新读取磁盘执行 80 项 literal/forbidden/conflict 合同，0 failures、exit 0；11 个修订/planning 文件均生成 SHA-256。未以空白的 forbidden-scope timestamp 输出作为证据。
## Phase 5B-R-R research-protocol revision review（初步，2026-08-07）

- 已复核 `statistical_analysis_plan.md`、`experiment_protocol.md`、`ablation_plan.md`、`manifest_spec.md` 以及三份 planning 上下文。
- 初步通过：analysis population 明确为 all scheduled independent evolution runs；`no_valid_operator`、all-invalid、freeze/deployment blocked、no deployable/not evaluable portfolio 不构成删行条件；failure run 主规则唯一为每 family `delta_rf=0`；fallback 不归因；complete-case/two-part/dominated 已分别限制为 supplementary/sensitivity。
- 初步通过：H1a CI lower > 0 与 H1b CI lower > 0.02 分离；seed→replicate→equal-family→equal-run arithmetic-mean 链唯一；primary CI 固定 5,000 次 run×family two-way cluster bootstrap，raw trial/candidate/seed 不作为 bootstrap 单位。
- 初步通过：H2a response/percentage-point scale/all-scheduled denominator 与 H2b binary deployability/risk-difference/all-scheduled denominator均明确；H2c exploratory；四 cells 预算和 evaluator access 固定。
- 初步通过：manifest record/header 采用固定 JSON types、canonical `instance_id`、RFC 8785 serialization/hash、path-root/symlink/alias/traversal checks、unknown/missing/wrong-type/no-glob fail closed。
- 待核实 1：统计计划对“整个 scheduled run 无可评价 portfolio”有零改善规则，但尚未在已读部分明确已部署 portfolio 的部分 family/replicate/solver-seed timeout/invalid/missing cell 如何形成 `delta_rf`；若其余文档未补足，仍可能产生 cell-level complete-case bias。
- 待核实 2：manifest 声明 `instance_id` 跨 splits 不相交，并拒绝 duplicate file hash，但需确认 runner/preflight 是否明确对 train/dev/final-test manifests 的合并集合执行 file-hash/path duplicate 检查，而非只在单一 manifest 内检查。
- 本条为初步证据，不是最终 verdict；未修改受审协议、代码、配置、数据或测试，未运行实验/provider。

### 初步残余 findings（待最终定级）

- **Required candidate 1 — cell-level missingness 未冻结：** `delta_rfis` 只对成功、可评价 solver cells 定义；whole-run 无 portfolio 才有 `delta_rf=0`。一个已部署 portfolio 若只在部分 family/replicate/solver-seed 上 timeout、invalid、fallback 或 missing，协议未规定是把失败 cell 记 0、把整个 run×family 记 0，还是把整个 run 记 failure。第 6 节又要求对“全部预注册 seeds/replicates”取 mean，因此实现者仍可 complete-case 删除失败 cells。需冻结 scheduled evaluation grid 和唯一 cell→replicate→family 映射。
- **Required candidate 2 — cross-split exact-file leakage 未完全封闭：** `instance_id` 因包含 `family_id`，同一 exact file 若被赋予不同 family metadata 会得到不同 ID；当前 duplicate `file_hash` fail-closed 文本没有明确 formal preflight 必须联合加载 train/dev/final-test manifest set 并在合并 records 上检查 duplicate file hashes、resolved paths/file identity。单 manifest runner 无法发现另一 split 的重复内容。
- **Consider — hierarchy label：** `reproducibility_checklist.md` 仍写 `H1→H6→H3`，而统计计划明确 gate 是 H1a→H6→H3；上一行虽已区分 H1a/H1b，但执行 checklist 最好使用 H1a 以避免误把 H1b 作为 gate。
- **Consider — planning state：** `task_plan.md` 较早的 `Phase 5B-R: Research-Protocol Independent Review` 仍显示 `in_progress` 和多项未勾选，而当前 revision/review 已另有新 section；这不会改变研究 estimand，但会使持久计划的当前状态产生歧义，应在 review 收尾时归档为 complete/request-changes historical record。

## Phase 5B-R-R final review verdict（2026-08-07）

### Critical

- 无。上一轮由 whole-run complete-case exclusion 导致的主要幸存者偏差已关闭。

### Required

1. **Partial evaluation cells 仍缺唯一 failure-aware 映射。** `statistical_analysis_plan.md` 只为成功的 `delta_rfis` 和 whole-run 无 portfolio 的 `delta_rf=0` 定义数值。已部署 portfolio 若只在部分 family/replicate/solver-seed timeout、invalid、fallback 或 missing，协议既要求平均“全部预注册” cells，又没有定义这些 cell 的 delta。实现者仍可能丢弃失败 cells、将 family/run 宣告失败或采用临时 penalty，改变 primary estimate。必须冻结完整 scheduled evaluation grid 和 cell→replicate→family→run 的唯一规则。
2. **Duplicate exact-file leakage 尚未明确跨 split manifests 联合检查。** `instance_id` 包含 `family_id`，同一 exact file 在不同 claimed family 下可有不同 IDs。当前 formal runner 接收单一 `manifest_path`/`split`，而 duplicate `file_hash` 条款未明确在 train/dev/final-test 合并 records 上执行。必须增加 joint manifest-set/preflight authority，拒绝跨 split 的重复 file hash、resolved path/file identity 和 family/instance overlap，并记录联合检查 hash/evidence。

### Consider

- `reproducibility_checklist.md` 的 gate shorthand 应由 `H1→H6→H3` 改为 `H1a→H6→H3`；上一行虽已区分 H1a/H1b，但精确标签更利于实现审计。
- H2 factorial 若按 provider/time block 或 common evolution seeds 配对，应在正式预注册前明确 bootstrap 是重采样独立 runs 还是配对 blocks；当前不影响 H2 response/denominator 的正确性。
- `delta_rf=0` 是“失败后没有可归因改善”的 policy estimand，不是对失败算法质量的物理 penalty；论文应始终并列 deployment/valid-portfolio rates 与 dominated/two-part sensitivity。
- Hardlink/file-identity detection 的跨平台能力可能不同；manifest implementation plan 应定义无法可靠检测时的 fail-closed/platform-support policy。

### FYI / passed

- all scheduled independent evolution runs、whole-run failures retained、唯一 failure-zero rule、complete-case supplementary-only 均通过。
- H1a/H1b、MCID lower-bound、唯一层级聚合、run×family two-way bootstrap、H2a/H2b/H2c 均通过。
- strict types、canonical `instance_id`、RFC 8785、path safety、单 manifest duplicate/fail-closed，以及 Table 0/Table 1 accounting 均通过。
- Phase 6A 当前未授权；Gate B、真实 LLM、正式/大规模/final-test 实验禁令保持。
- Review contract：16 项中 14 pass、2 open；最终为 **Request changes（0 Critical、2 Required）**。

### Gate conclusion

- 当前不允许进入 Phase 6A mock/file closed-loop planning；先修复上述两项 Required 并复审。
- 真实 LLM、正式/大规模/final-test 实验继续禁止。
- 完成前验证的第一次 literal assertion 因 `cross split` 与实际“跨 split”措辞不一致而未通过；这是检查器错误，已记录并要求使用实际文本重新验证，不能作为 review pass 证据。
# Phase 5B-R3 protocol reconciliation findings (2026-08-07)

- `docs/statistical_analysis_plan.md` currently uses `manifest_violation` in both cell-failure and batch-contamination contexts. This is ambiguous: a generated result-row defect may be mapped to the failure-zero policy estimand, while objective/input/split/hash/lockbox/baseline-pairing defects invalidate the affected preregistered integrity unit and must not be assigned a generated-method effect value.
- The unique revision rule will therefore use two mutually exclusive classes: `localized_result_artifact_failure` (cell value `0`, retained in every denominator) versus `batch_input_lockbox_contamination_or_inconclusive` (no effect value, retained only in scheduled/accounting and integrity reporting, with preregistered rerun or abandonment handling).
- `docs/manifest_spec.md` and related documents currently make the three-manifest joint preflight precede any train/dev evaluation. That conflicts with the approved Phase 6A train/dev-only mock/file pilot, which must not create, read, hash, or reveal a final-test manifest or family matrix.
- The lifecycle revision will define a pilot preflight over smoke/train/dev manifests only and a separate formal lockbox joint preflight over train/dev/final-test manifests. Only the latter may produce the three-manifest receipt required before formal prompt/operator generation, formal train/dev evaluation, formal portfolio selection, or final-test execution.
- Unsupported hardlink/file-identity inspection remains fail-closed for formal execution unless a stronger-control exemption is preregistered; pilot may record a warning but cannot produce formal evidence.
- Required 1 is now closed at the specification level: the statistical plan uses a fail-closed decision order and mutually exclusive localized/batch labels. Final-test integrity events are always contamination; missing/unverifiable baseline pairing is batch-inconclusive; neither receives a synthetic zero effect.
- Required 2 is now closed at the specification level: Phase 6A pilot preflight is non-final and receipt-scoped, while the formal lifecycle alone uses the three-manifest receipt before formal design/evaluation actions.
- The reporting name is tightened to `fully attributable family rate`; implementation of its machine-readable field remains a later Phase 6/formal EXEC-BLOCKING task.
# Phase 6B-T1R2 GREEN independent review（2026-08-12，完成）

- 已确认 `pilot_contracts.py` 仍为纯数据校验模块：只导入 dataclass/math/re/typing；未出现路径访问、文件身份检查、哈希重算、runner/provider/candidate/pilot 执行能力。
- Runner receipt status enum 已收紧为 `preflight_validated` / `preflight_rejected`；validated 分支强制 `accepted_execution=False`、无 scheduled IDs、无 Gate P2 authorization、无 started timestamp。
- T1R2 RED 覆盖包含 20 个 non-preflight status/accepted_execution 组合、reason-specific evidence 负例和 validated evidence 自相矛盾负例。
- **Required：** `_rejection_is_supported()` 对 `validation_receipt_invalid` 与 `runtime_authorization_denied` 使用“任意具名 evidence 的 decision=reject 即可”的通用回退，不能证明 rejection reason 由对应 evidence 支持。现有测试只覆盖“所有 evidence 都 pass”时拒绝，未覆盖“无关 evidence reject”旁路；既有 `runtime_authorization_denied` 正例实际借用 inherited `manifest_only_evidence.decision=reject` 通过。
- Manifest/validator receipt 分支保持 strict JSON type、enum、required/unknown-field 与 inert receipt 校验；hash 字段仅做 64 位小写十六进制格式校验，没有重算。
- `output_paths` 在 T1R 无批准 record schema 时仅允许空 list；`failure_summaries` 只接受固定三字段与非负整数 count/denominator。
- 当前模块没有 candidate-row validator，也未出现 `execution_status`/`invalid_solution` 等 candidate taxonomy 逻辑；因此本轮没有把 `invalid_solution` 放回 execution axis，也没有改变此前五轴合同。
- Fresh verification：唯一授权命令 `python -m pytest tests/test_pilot_contract_schema_red.py -q` 为 153 passed、1 warning；通过测试不足以覆盖上述 reason/evidence 交叉语义。
- Review verdict：Request changes（0 Critical、1 Required）；T2 暂不准入。

# Phase 6B-T2 GREEN implementation review（2026-08-13，进行中）

- `pilot_integrity.py` 的能力边界符合 T2：仅导入 `dataclasses/hashlib/json/math/re/typing`，没有文件读取、路径解析、文件身份检查、runner/provider/candidate/pilot 执行能力。
- `pilot_contracts.py` 的修改时间早于 T2；源码仍声明并保持 pure schema validation，未见 T2 改写证据。
- **Required candidate：** scoped verifier 的递归 marker 检查只识别 `final_test`；批准的 validator 合同还要求 pilot record/header 引用 `formal_train` 或 `formal_dev` 时 fail closed。保持顶层 `pilot_nonformal/pilot`、仅把 instance split 改成 `formal_train`/`formal_dev` 的对象目前可能通过。
- **Required candidate：** 实现使用 Python `json.dumps(sort_keys=True, separators=...)` 的项目确定性 JSON 子集，但批准的 receipt/hash 文档明确指定 RFC 8785/JCS；当前测试没有 JCS 数字序列化等 conformance vectors，不能把现实现声称为 RFC 8785。
- 待进一步核验 cross-layer receipt binding 对缺失或非法 `manifest_hash` 是否独立 fail closed，并运行授权专项/联合回归后形成最终 verdict。
- **Required candidate：** `verify_runner_receipt_binding()` 只比较 validator、runner 与 `manifest_only_evidence` 的 `manifest_hash` 是否相等，不先要求 validator hash 为合法 lowercase SHA-256；三处都缺失/为 `None` 时可通过这一层。作为公开 integrity API，它不能仅依赖调用者先跑 schema validator，需用 RED 测试冻结 fail-closed 前置证据。
- T2 测试的 canonical oracle 与实现同为 `json.dumps(..., sort_keys=True)`，所以现有绿灯是同构实现检查，不是独立 RFC 8785 conformance 证据。

## Final verdict

- **Critical：0。** 未发现文件/路径、provider、runner、candidate 或 pilot 执行能力；没有 final-test 访问行为。
- **Required 1 — incomplete pilot/formal scope rejection：** `_contains_final_test_marker()` 只匹配 `final_test`。批准协议要求 record/header 引用 `formal_train`、`formal_dev` 或 `formal_final_test` 都拒绝；当前测试仅在顶层 manifest 同时被重标为 formal 时覆盖 `formal_train`，没有 isolating case。
- **Required 2 — canonical algorithm mismatch/evidence gap：** 文档冻结 RFC 8785/JCS，当前实现与测试 oracle 都使用 Python `json.dumps`。它虽稳定、拒绝非 JSON/非有限值，但未证明 JCS 数字编码等行为；跨实现 receipt identity 不可据此声称可复现。
- **Required 3 — cross-layer missing hash bypass：** `verify_runner_receipt_binding()` 没有验证 validator `manifest_hash` 的存在和 lowercase-64-hex 格式；三层相同缺失或同一非法值可通过 equality checks。T1 schema 可能在规范调用链先拒绝，但公开 integrity verifier 本身不 fail closed，且尚无 orchestrator 强制该前置顺序。
- Fresh tests：T2 59 passed；T1+T2 223 passed；各 1 个既有 pyreadline warning。没有运行完整 pytest。
- Review verdict：**Request changes（0 Critical、3 Required）**；下一步应是最小 T2R RED-only，而非 T3。

# Phase 6B-T2R RED-only findings（2026-08-13）

- 仅修改 `tests/test_pilot_scoped_hash_red.py` 与 planning records；未创建 fixture，未修改 `pilot_integrity.py`、`pilot_contracts.py` 或其他 production/docs/configs/data。
- **Required 1 reproduced：** 4 个 isolating cases 失败：顶层仍为 `pilot_nonformal/pilot` 时，instance `split=formal_train/formal_dev` 以及 nested semantic `manifest_scope=formal_train` / `split=formal_dev` 被当前 verifier 接受。顶层 formal scope、formal matrix 与 nested `formal_final_test` 控制仍通过。
- **Required 2 reproduced：** 手写 RFC 8785/JCS vectors 中 `1e-7`、`1e-6`、`-0.0` 三项失败，实际分别为 Python JSON 的 `1e-07`、`1e-06`、`-0.0`；sorted keys、nested ordering、`4.5`、直接 UTF-8 和 control escaping 控制通过。既有 non-finite 集合补入 `-Infinity` 并通过拒绝。
- **Required 3 reproduced：** validator/runner/evidence 三层 `manifest_hash` 同时 missing/null/empty/non-hex/uppercase/wrong-length 的 6 个 cases 全部被接受。独立 runner/evidence validation receipt ID 缺失/非法控制已被现实现拒绝，说明旁路集中在 manifest hash 格式前置校验。
- Fresh authorized test：89 collected、13 failed、76 passed、1 个既有 pyreadline warning；无 syntax、collection 或 fixture parsing error。
- T2R RED 证明三个 review finding 都是可复现行为；建议单独授权 T2R GREEN，仍不得进入 T3 或关闭 Gate P2。

# Phase 6B-T2R GREEN root-cause analysis（2026-08-13）

- Root cause 1：scope scanner 的 predicate 固定为 substring `final_test`，因此 formal train/dev 从未进入 rejection path；修复点应是单一递归 formal-scope predicate，而不是在每个字段处散布条件。
- Root cause 2：whole-object `json.dumps` 不是 RFC 8785/JCS number serializer；失败集中在 exponent zero、decimal/scientific threshold 与 negative zero。需要按 JSON type 递归序列化，并单独规范化 finite float；不能继续复用同构 oracle。
- Root cause 3：cross binding 直接比较三个 manifest hashes，未先验证各自 evidence domain；这使相同无效值成为假阳性。修复应采用格式 predicate→条件 equality 的固定顺序，并同时验证 top-level/evidence validation receipt IDs。
- 最小实现仍可保持纯内存与标准库；无需新增依赖、文件/路径能力或 runner/provider/candidate/pilot 代码。

## GREEN implementation result

- Required 1 closed in implementation：单一递归 predicate 审计 manifest/family matrix/split rule 的显式对象；任何 `formal_train`、`formal_dev`、`formal_final_test` marker，以及 scope/split/manifest/lockbox semantic context 下的 `formal` 均拒绝。
- Required 2 closed for the approved vectors：新增 `RFC8785-JCS` / `jcs-v1` 常量；递归 serializer 使用 UTF-16 code-unit key ordering、标准 JSON string escaping/direct UTF-8、无 whitespace，并将 finite float 的 exponent/decimal threshold、冗余 `.0` 与 negative zero 规范化。Non-finite、lone surrogate 与非 JSON type fail closed。
- Required 3 closed：cross binding 对 validator/runner/evidence 三个 validation receipt IDs 与三个 manifest hashes 分别先做 exact-string lowercase-64-hex domain validation，仅在全部合法时比较 equality；`None == None` 与相同非法值不再可通过。
- 能力边界保持：imports 仅 standard-library dataclass/hashlib/json/math/re/typing；没有 open/pathlib/path resolution/file identity/subprocess/provider/runner/candidate/pilot 能力。
- Fresh tests：T2/T2R 89 passed；T1+T2 253 passed；均只有 1 个既有 pyreadline warning。未运行完整 pytest。
- `pilot_contracts.py` mtime 保持 2026-08-12 21:54:57；T2R tests mtime 保持 RED 阶段 2026-08-13 21:48:58，GREEN 未修改二者。
# Phase 6B-T2R GREEN independent review notes (2026-08-14)

- Review scope remains read-only for production/test artifacts; only the two explicitly authorized pytest commands may be run.
- RFC 8785 requires JSON number serialization compatible with ECMAScript/IEEE-754 semantics and recursive UTF-16 property ordering. The current implementation passes the newly added basic handwritten vectors, but its direct serialization of arbitrary Python `int` values exceeds the declared contract: `_validate_json_value()` accepts all integers and `_serialize_jcs_number()` returns `str(value)`, whereas RFC 8785 Appendix B explicitly serializes the IEEE-754 value near `2**68` as `295147905179352830000`, not Python's exact integer `295147905179352825856`. This is a Required interoperability/integrity gap.
- The bounded implementation otherwise satisfies the reviewed boundary: only in-memory objects/bytes are consumed; there is no path resolution, file read, identity check, provider/runner/candidate/pilot capability; formal train/dev/final-test markers are rejected; lowercase 64-hex validation precedes cross-receipt equality; evidence remains inside the non-self-referential receipt preimage.
- Fresh authorized evidence: T2 `89 passed, 1 warning`; combined T1+T2 `253 passed, 1 warning`. The warning remains the unrelated existing `pyreadline` deprecation warning.
- `pilot_contracts.py` retains the pre-T2R timestamp `2026-08-12 21:54:57`, size `38168`, and current SHA-256 `2902BB3CB8F3D78B9A5A764708672D7E35C3C73133FFA1DD6902E90707D1C873`; the workspace is not a Git repository, so unchanged status is supported by phase timing/planning evidence rather than a commit diff.
- Verdict: 0 Critical, 1 Required; T3 remains blocked pending a TDD correction of the RFC 8785 integer domain/serialization contract.
- No file/path access, provider, runner, candidate, pilot, benchmark, or final-test activity is authorized or needed for this review.

# Phase 6B-T2R2 RED design findings (2026-08-14)

- The approved conservative policy is frozen as the ECMAScript safe-integer interval `[-9007199254740991, 9007199254740991]`. Python integers outside it must raise `TypeError` or `ValueError`; the current canonicalization version must not coerce them to binary64.
- Appendix B vectors should enter tests as independent handwritten expected bytes. IEEE-754 values will be constructed in memory from fixed 64-bit hexadecimal patterns, avoiding any file/fixture access and separating float serialization conformance from Python arbitrary-precision integer rejection.
- Existing test helpers are sufficient; no fixture file is needed. The current production code still accepts every Python `int`, so just-outside and `2**68` rejection cases should produce genuine RED failures.
- RED result confirms the diagnosis precisely: all six scalar out-of-domain integers and both nested out-of-domain integers were accepted, producing 8 `DID NOT RAISE` failures. The accepted safe-integer endpoints passed.
- All 18 official Appendix B finite binary64 samples used in the test passed under the current float serializer, including signed zero, minimum subnormal, maximum finite double, `2**53`, the `2**68` approximation, notation thresholds, and round-to-even. Therefore the remaining Required is the Python-int input-domain gate, not a demonstrated float serializer defect.
- Total targeted result: 118 collected, 8 failed, 110 passed, 1 unrelated existing `pyreadline` deprecation warning. No syntax, collection, fixture, import, or infrastructure error occurred.

# Phase 6B-T2R2 GREEN findings (2026-08-14)

- The minimal root-cause fix belongs in recursive JSON-domain validation, not number serialization: exact Python `int` values are now accepted only in `[-9007199254740991, 9007199254740991]`; values outside it raise `ValueError` with `canonicalization_integer_domain` context before `_serialize_jcs()` runs.
- No binary64 coercion, truncation, or arbitrary-precision decimal emission is introduced. Therefore Python `2**68` cannot enter canonical bytes or any object/receipt hash preimage, while an explicitly supplied IEEE-754 `float` continues to follow the approved Appendix B behavior.
- `CANONICALIZATION_ALGORITHM` remains `RFC8785-JCS`; the policy is now explicit in `CANONICALIZATION_VERSION = "jcs-v1-safe-int-domain"`.
- Fresh authorized evidence: T2/T2R/T2R2 `118 passed, 1 warning`; T1+T2 combined `282 passed, 1 warning`. The warning is the existing unrelated `pyreadline` deprecation warning.

# Phase 6B-T2R2 GREEN independent review notes (2026-08-14)

- Static implementation tracing confirms the range check is recursive and all public object/receipt hash computations eventually call `canonical_json_bytes()`. `verify_runner_receipt_binding()` catches the resulting `TypeError`/`ValueError` and records `non_canonical_json`, so the production behavior inherits fail-closed semantics.
- Tests directly cover scalar and nested `canonical_json_bytes()` rejection plus Appendix B float behavior, but the current test file does **not** directly inject an unsupported integer into `compute_object_hash()`, validation/runner receipt IDs, or `verify_runner_receipt_binding()`, and contains no assertion for `CANONICALIZATION_ALGORITHM`/`CANONICALIZATION_VERSION`. This differs from the GREEN request's stated RED coverage and must be classified after completing the review.
- Final correctness finding: production behavior is fail closed. `compute_object_hash()` always invokes `canonical_json_bytes()`; both receipt-ID calculators invoke `compute_object_hash()` on the non-self-referential body; runner verification catches canonicalization exceptions and records `non_canonical_json`. No arbitrary-precision integer can reach a digest preimage through these public paths.
- Final evidence finding (Required): that transitive behavior and the version constants are not directly regression-tested despite being explicitly listed as RED coverage. In an integrity boundary, the structured verifier result and version contract are separately observable behavior, not merely implementation detail; a future bypass/error-handling regression could pass all current safe-int tests.
- All other reviewed controls pass: pure in-memory only; no file/path/identity/provider/runner/candidate/pilot capability; formal train/dev/final-test rejection retained; lowercase-64-hex and evidence-bound receipt IDs retained; explicit-content-only retained; current RFC vectors pass.
- Verdict: Request changes, 0 Critical and 1 Required. T3 remains blocked until a bounded RED-only evidence patch and review close the test-contract discrepancy.

# Phase 6B-T2R3 coverage-only findings (2026-08-14)

- Added 19 direct regression cases in `tests/test_pilot_scoped_hash_red.py`; no fixture or production module was changed.
- `compute_object_hash()` is now directly observed rejecting unsupported integers in object, array, and nested-object preimages. A monkeypatched digest entry point confirms rejection occurs before SHA-256 starts, so no invalid preimage is hashed.
- `compute_validation_receipt_id()` is directly covered for evidence, status-adjacent, and nested unsupported integers. `compute_runner_receipt_id()` is directly covered across all five named evidence objects plus requested/accepted-adjacent fields.
- `verify_runner_receipt_binding()` is directly invoked without a schema-validator prerequisite for unsupported integers in validator, runner, `manifest_only_evidence`, and `no_real_llm_evidence`; every case returns structured invalid with `non_canonical_json` or equivalent canonicalization reason.
- The public contract is frozen explicitly as `CANONICALIZATION_ALGORITHM == "RFC8785-JCS"` and `CANONICALIZATION_VERSION == "jcs-v1-safe-int-domain"`, documenting JCS plus fail-closed safe integers without arbitrary Python-int-to-binary64 coercion.
- All new cases passed immediately, so this is a coverage-only closure rather than a RED→GREEN implementation change. Targeted T2 result: 137 passed, 1 existing `pyreadline` warning. Authorized T1+T2 regression: 301 passed, 1 existing warning.
- Production hashes remain unchanged: `pilot_integrity.py` SHA-256 `D09170932E3C46045F4AE212E4EFDB126B394DD1F43FAC70C5B1171969F8B95E`; `pilot_contracts.py` SHA-256 `2902BB3CB8F3D78B9A5A764708672D7E35C3C73133FFA1DD6902E90707D1C873`.
- No file/path access, runner, provider, candidate, pilot, benchmark, real LLM, or final-test activity occurred. T3 remains unauthorized pending independent T2R3 review; Gate P2 remains open.

# Phase 6B-T3 RED contract conflict (2026-08-14)

- The T3 attachment explicitly says to stop before editing tests if its contract conflicts with approved docs. Two direct conflicts were found, so no RED test file was created.
- `docs/pilot_manifest_validator_spec.md` defines the future validator as the only entry point from raw manifest bytes, requires `manifest_path`, and orders strict UTF-8 reading, path normalization, raw instance-file hashing, and file-identity checks. The T3 request instead proposes `manifest_obj`/matrix/rule pure-object APIs and forbids file reads/path resolution/identity checks. These can coexist only if T3 is explicitly named and specified as a subordinate pure-object pre-validator rather than the complete validator.
- The approved validator receipt schema and fixture use `status in {valid, rejected}`. The T3 happy-path text requires `status=validation_valid`, which `validate_manifest_validation_receipt_schema()` currently rejects. Tests cannot freeze both contracts.
- A third semantic choice follows from the first conflict: the approved `manifest_hash` binds exact raw manifest bytes, while an object-only API has no raw-byte input. It can compute `canonical_manifest_hash`, but cannot honestly issue the approved raw `manifest_hash` without an explicit trusted byte/hash argument.
- No production, existing test, fixture, config, data, or docs file was modified; no target pytest was run because no coherent RED contract could be created. Gate P2 and all execution prohibitions remain active.

# Phase 6B-T3 pure-object pre-validator/core RED findings (2026-08-14)

- The clarified contract resolves the earlier conflict by defining `pilot_manifest_prevalidator` as a subordinate pure-object core. It composes existing schema validation and in-memory scoped integrity only; it is not the approved full raw-bytes/path validator and cannot issue a formal validation receipt.
- Added one test file and no fixture: `tests/test_pilot_manifest_prevalidator_core_red.py`. The in-memory baseline control passes both existing `validate_pilot_manifest_schema()` and `verify_pilot_scoped_hash_binding()`, proving RED failures do not come from malformed setup.
- The 28 expected RED cases freeze: schema-before-integrity order; schema short-circuit for unknown/type/formal scope/promotion/formal split failures; structured integrity-layer rejection for object-hash mismatches, hidden formal/final-test markers, and unsafe integers; valid inert result semantics; canonical object bindings; post-build mutation detection; `valid/rejected` status only; no full-receipt impersonation; no file reads; and no runner/provider/candidate/pilot calls.
- T3 target result: 29 collected, 28 failed, 1 passed, 1 existing `pyreadline` warning. Every failure is the explicit `Phase 6B-T3 RED: ... core is not implemented` assertion caused by the absent target module; there are no syntax, collection, import-chain, or fixture errors.
- Authorized T1+T2 regression remains green at 301 passed, 1 existing warning. No full suite was run.
- Production evidence is unchanged: `pilot_integrity.py` SHA-256 `D09170932E3C46045F4AE212E4EFDB126B394DD1F43FAC70C5B1171969F8B95E`; `pilot_contracts.py` SHA-256 `2902BB3CB8F3D78B9A5A764708672D7E35C3C73133FFA1DD6902E90707D1C873`; target core file does not exist.
- No raw manifest bytes, path normalization, instance-file hashing, file identity, provider, runner, candidate, pilot, benchmark, real LLM, or final-test capability was implemented or invoked. Gate P2 remains open.

# Phase 6B-T3 pure-object pre-validator/core GREEN findings (2026-08-14)

- Added only `src/mrta_rect_coverage/experiments/pilot_manifest_prevalidator.py` as the production implementation. It is a subordinate pure-object composition layer, not the raw-bytes/path full validator.
- `validate_pilot_manifest_core()` invokes schema validation first and returns a schema-layer rejection without calling integrity; only schema-valid input reaches `verify_pilot_scoped_hash_binding()` and canonical object hashing.
- The core result is inert: status is only `valid` or `rejected`, scope is `pure_object_prevalidation`, and both `execution_authorized` and `gate_p2_closed` are always false.
- `build_pilot_prevalidation_result()` binds the supplied manifest, pilot family matrix, and pilot split rule via explicitly named object hashes. Its non-self-referential `prevalidation_result_id` does not claim to be a formal `validation_receipt_id` or raw manifest hash.
- `verify_pilot_prevalidation_result()` independently checks its exact pure-object result shape, lowercase SHA-256 result ID, canonical result body, and deterministic binding to the current three input objects; post-build mutations fail closed.
- Unsupported JCS values, including out-of-domain integers nested in the manifest, are classified as integrity-layer rejection before a manifest object hash is emitted.
- Fresh authorized evidence: T3 target `29 passed, 1 warning`; T1+T2+T3 regression `330 passed, 1 warning`. The warning is the existing unrelated `pyreadline` deprecation warning.
- Existing boundary modules remain unchanged: `pilot_integrity.py` SHA-256 `D09170932E3C46045F4AE212E4EFDB126B394DD1F43FAC70C5B1171969F8B95E`; `pilot_contracts.py` SHA-256 `2902BB3CB8F3D78B9A5A764708672D7E35C3C73133FFA1DD6902E90707D1C873`.
- No raw manifest bytes, file/path access, path normalization, file identity, instance-file hashing, formal receipt, runner, provider, candidate, pilot, benchmark, real LLM, or final-test capability was implemented or invoked. Full validation and Gate P2 remain open.

# Phase 6B-T3 independent implementation review findings (2026-08-15)

- Pass: the module is a pure-object orchestrator. Imports are limited to dataclasses/typing and the existing schema/integrity helpers; no file/path/raw-bytes/runner/provider/candidate/pilot capability was added.
- Pass: schema validation precedes integrity and schema rejection short-circuits it. Result states remain `valid/rejected`, scope is `pure_object_prevalidation`, and execution/Gate P2 flags are always false.
- Pass: valid results use explicitly named object hashes, a non-self-referential result ID, exact result fields, and deterministic comparison against current manifest/matrix/split objects. Existing valid-result post-build mutation tests are meaningful.
- **Required object-binding gap:** `_result_body()` writes all three object hashes as `None` whenever validation is rejected. Consequently, two different canonical invalid inputs that produce the same layer and rejection reasons produce the same body/result ID. `verify_pilot_prevalidation_result()` rebuilds that same unbound rejection summary, so a result built from invalid object A can verify against changed invalid object B. This contradicts the verifier's stated binding-to-the-same-three-objects contract and leaves rejected audit evidence non-attributable.
- Coverage gap corresponding to the Required: current mutation tests start only from a valid result. They do not mutate a schema-rejected or integrity-rejected input while preserving its rejection classification.
- **Consider:** valid build currently hashes mutable matrix/rule/manifest objects multiple times across scoped integrity, core validation, and result construction. A concurrent/in-call mutation can separate the snapshot that passed scoped integrity from the hashes recorded in the result. A single immutable canonical snapshot/hashes passed through validation and construction would remove that TOCTOU window and reduce repeated work.
- Fresh authorized evidence: T3 `29 passed, 1 warning`; T1+T2+T3 `330 passed, 1 warning`. The warning is the existing unrelated `pyreadline` deprecation warning; no full suite was run.
- Verdict: Request changes — 0 Critical, 1 Required. T4 is blocked pending bounded T3R RED→GREEN→review. Gate P2 and all execution/experiment prohibitions remain active.

# Phase 6B-T3R RED-only findings (2026-08-15)

- Added 17 focused cases to the existing T3 core test file; no fixture was required. Production modules, docs, configs, and data remained untouched.
- Schema-rejected RED proves two different manifests with the same `unknown_field` rejection summary currently share the same `prevalidation_result_id`, and a result built from A verifies as valid against B.
- Integrity-rejected RED proves the same interchangeability for manifests with equal hash-mismatch summaries and for changed family-matrix/split-rule objects that preserve the rejection category.
- Canonicalizable rejected inputs currently expose `None` for all three object hashes. Both schema- and integrity-rejected hash-presence cases fail exactly at the lowercase SHA-256 assertion.
- Non-canonicalizable rejected inputs currently lack an explicit `binding_available=false`/reason and their rejected result verifies as valid against the same unbound input. Both schema-short-circuit and integrity-layer forms are covered.
- Mid-build mutation tests instrument both after-schema and after-integrity boundaries. The current implementation returns `status=valid` while recording the mutated manifest hash rather than the entry hash, demonstrating that no single snapshot currently spans validation and result construction.
- Three added hash-tampering controls pass immediately: if an object-hash field is changed without recomputing `prevalidation_result_id`, current verification rejects it. The gap is missing rejected-input hashes, not a failure to cover fields already present in the result body.
- Target evidence: `46 collected, 14 failed, 32 passed, 1 warning`; all failures correspond to the approved rejected binding/noncanonical/snapshot gaps. The warning is the existing unrelated `pyreadline` deprecation warning.
- Authorized combined evidence: `347 collected, 14 failed, 333 passed, 1 warning`; the failure set is identical to the target run, so T1/T2 and the original 29 T3 cases remain green.
- Production hashes remain unchanged: prevalidator `36C52D0C265DABEA0CF14CDCF8A208735FD34CCC8903C32CF408BAB365FD2FEF`, contracts `2902BB3CB8F3D78B9A5A764708672D7E35C3C73133FFA1DD6902E90707D1C873`, integrity `D09170932E3C46045F4AE212E4EFDB126B394DD1F43FAC70C5B1171969F8B95E`.
- T3R RED is valid and ready for separately authorized minimal GREEN. T4 and every execution/experiment gate remain blocked.

# Phase 6B-T3R GREEN findings (2026-08-15)

- The minimal fix is contained in `pilot_manifest_prevalidator.py`. Existing schema and integrity modules, tests, docs, configs, and data were not modified.
- A single deep-copied entry snapshot now captures manifest, pilot family matrix, and pilot split rule. Schema and integrity retain their required order; after each validator call, the originals are compared with the entry snapshot and any mutation becomes a structured rejection.
- All result object hashes are computed once from the entry snapshot and carried into result construction. Valid and canonicalizable rejected results therefore bind the same three object snapshots without re-reading mutable input.
- Canonicalizable schema- and integrity-rejected results now contain three lowercase object hashes. These hashes, rejection layer/reasons, status/scope, canonicalization metadata, and inert execution/Gate flags are covered by the non-self-referential `prevalidation_result_id`.
- Non-canonicalizable inputs produce `status=rejected`, `binding_available=false`, a non-empty `binding_unavailable_reason`, null object hashes, and no `prevalidation_result_id`. Verification always returns invalid for binding-unavailable results, even when the supplied input reproduces the same rejection.
- Replay of a canonical rejected result against a different invalid manifest, family matrix, or split rule now fails because verifier rebuilds hashes from the current input snapshot and compares the complete deterministic result.
- Fresh authorized evidence: T3/T3R `46 passed, 1 warning`; combined T1+T2+T3 `347 passed, 1 warning`. The warning remains the existing unrelated `pyreadline` deprecation warning; no full suite was run.
- Updated prevalidator SHA-256 is `D353CB4EC89A7B2906CB8AA2EB57C5325E2336E1D56E2D5CC2521DF3FDA59371`. Contracts and integrity hashes remain unchanged at `2902BB3CB8F3D78B9A5A764708672D7E35C3C73133FFA1DD6902E90707D1C873` and `D09170932E3C46045F4AE212E4EFDB126B394DD1F43FAC70C5B1171969F8B95E`.
- No file/path/raw-bytes/full-validator/runner/provider/candidate/pilot capability was introduced. Gate P2 and all experiment restrictions remain active pending independent review.

# Phase 6B-T3R independent implementation review findings (2026-08-15)

- **Verdict: Approve — 0 Critical, 0 Required.** The prior rejected-result binding gap and snapshot-consistency concern are closed by implementation plus focused tests.
- Canonicalizable schema- and integrity-rejected results bind the manifest, pilot family matrix, and pilot split rule with three lowercase SHA-256 object hashes. The non-self-referential result ID covers those hashes and the rejection/status/scope/canonicalization/inert-gate fields; replay against a different invalid object fails.
- Non-canonicalizable inputs fail closed with `binding_available=false`, a non-empty reason, null object hashes, and no reusable result ID. `verify_pilot_prevalidation_result()` never reports such a result as valid.
- One entry `deepcopy` snapshot is used for result hashes. Schema remains first, integrity is skipped after schema rejection, and mutation after either validator becomes a structured rejection. Verification reconstructs the expected result from the current input and detects post-build mutation.
- Capability boundary passes: no file/raw-byte/path normalization/file identity/instance-hash/full-validator/runner/provider/candidate/pilot behavior exists in the prevalidator. Result scope remains `pure_object_prevalidation`; status remains `valid/rejected`; execution and Gate P2 flags remain false; no formal validation or runner receipt is emitted.
- Fresh authorized evidence: T3/T3R **46 passed, 1 warning**; T1+T2+T3 **347 passed, 1 warning**. The warning is the existing unrelated `pyreadline` deprecation warning. No full suite or prohibited execution was run.
- Unchanged dependency evidence: `pilot_contracts.py` SHA-256 `2902BB3CB8F3D78B9A5A764708672D7E35C3C73133FFA1DD6902E90707D1C873`; `pilot_integrity.py` SHA-256 `D09170932E3C46045F4AE212E4EFDB126B394DD1F43FAC70C5B1171969F8B95E`.
- **Consider:** before a broader public/I/O integration, either constrain snapshot inputs to strict JSON builtins before `deepcopy` or convert snapshot/cyclic/custom-object failures into structured binding-unavailable results.
- **Consider:** before persisting these objects, explicitly decide whether the added binding fields require a new `prevalidation_schema_version`; current T3 artifacts are non-formal and non-persistent, so this is not blocking T4 RED-only work.
- T4 may be separately authorized. The smallest next task is PIV-03 controlled path/duplicate-boundary **RED-only** tests; it must not execute providers/candidates/pilot or close Gate P2.

# Phase 6B-T4 RED-only initial findings (2026-08-15)

- The authorized T4 contract matches the approved PIV-03 plan: controlled root confinement, alias/link rejection, duplicate ID/content/path/file-identity/generation checks, pilot-only scope, and explicit no-glob behavior.
- T4 is tests-only. The proposed production module `mrta_rect_coverage.experiments.pilot_path_validator` does not yet exist and must remain absent during RED.
- All filesystem cases will use pytest `tmp_path` synthetic pilot-only artifacts. Project `data/`, formal manifests, and real final-test resources are outside scope and will not be scanned or accessed.
- Link tests must use platform capability detection and skip with an explicit reason when creation is unsupported; unsupported capability must not cause fixture/setup errors.
- Gate P2 remains open. A future validator result must stay inert: no runner receipt, scheduling ID, execution acceptance, provider/candidate/pilot call, or Gate P2 closure.
- The final test file collects 44 cases. The authorized target run produced 40 expected failures and 4 platform skips; all failures are the explicit missing-module RED message for `mrta_rect_coverage.experiments.pilot_path_validator`.
- Windows symlink creation is unavailable in the current isolated tmp directory, so the four symlink cases skip with an explicit capability reason. Hardlink creation is supported and its file-identity case reaches the expected missing-module RED failure.
- There were no syntax, collection, or fixture-setup errors. The only warning is the existing unrelated `pyreadline` deprecation warning.
- A dedicated behavioral sentinel test patches the existing provider factory, candidate-process executor, and evaluator invocation entry points. Future valid path validation must complete without touching any of them.
- The authorized T1+T2+T3 regression remains green at 347 passed with the same single existing warning.
- Final scope evidence: `pilot_path_validator.py` remains absent; `pilot_contracts.py`, `pilot_integrity.py`, and `pilot_manifest_prevalidator.py` retain SHA-256 values `2902BB3CB8F3D78B9A5A764708672D7E35C3C73133FFA1DD6902E90707D1C873`, `D09170932E3C46045F4AE212E4EFDB126B394DD1F43FAC70C5B1171969F8B95E`, and `D353CB4EC89A7B2906CB8AA2EB57C5325E2336E1D56E2D5CC2521DF3FDA59371`.
- T4 RED is complete. A separately authorized GREEN may implement only the minimal controlled path/duplicate validator required by these tests; full validation receipts, runner/provider/candidate/pilot execution, Gate P2 closure, and formal/final-test behavior remain out of scope.

# Phase 6B-T4 GREEN initial findings (2026-08-17)

- The GREEN authorization exactly matches the observed T4 RED API: one public `validate_pilot_paths_and_duplicates(manifest_obj, approved_root=...)` result with `valid`, rejection reasons, and inert execution/Gate fields.
- The minimal implementation can validate only explicitly listed paths in one pass. It needs `Path.lstat/resolve/stat/read_bytes` and SHA-256, but no directory enumeration, glob, runner, provider, candidate, or pilot dependency.
- Root confinement must reject lexical parent components before resolution, then reject resolved paths outside the resolved approved root. Windows drive-like syntax must be rejected independently of the host platform.
- Duplicate detection keys are instance ID, declared/verified file hash, canonical resolved path, supported file identity, family-to-split assignment, and the frozen generation-rule/seed/family-parameter tuple.
- Result semantics remain validator-only with `execution_authorized=false` and `gate_p2_closed=false`; this task cannot produce formal or runner receipts or close Gate P2.

# Phase 6B-T4 GREEN findings (2026-08-17)

- Added only `src/mrta_rect_coverage/experiments/pilot_path_validator.py` as production code. Existing contracts, integrity, prevalidator, tests, docs, configs, and data were not modified.
- Approved-root confinement rejects parent components and host-incompatible drive syntax before filesystem resolution, checks lexical containment, rejects symlink/reparse components, resolves explicitly supplied files, and checks resolved containment again.
- Explicit file validation rejects missing/non-string/empty paths, wildcard patterns, directories, missing or malformed hashes, missing targets, read failures, and content-hash mismatches. It never enumerates a directory or calls glob/walk.
- Duplicate checks cover instance IDs, declared file hashes, canonical resolved paths, supported `(st_dev, st_ino)` file identities/hardlinks, family-to-split conflicts, and the approved generation-rule/seed/family-parameter identity tuple.
- Pilot-only checks reject formal manifest/matrix scopes, formal/final-test path markers, and final-test lockbox markers. All test resources remained isolated under pytest `tmp_path`; no project data or real final-test resource was accessed.
- File-identity support is surfaced as `supported_pass`, `not_reached`, or `unsupported_file_identity_check`; unsupported identity evidence fails closed rather than silently claiming full verification.
- The result is inert: scope is `path_duplicate_validation`, `execution_authorized=false`, and `gate_p2_closed=false`; no receipt, scheduling, provider, candidate, runner, or pilot capability exists in the module.
- Fresh authorized evidence: T4 **40 passed, 4 skipped, 1 warning**; combined T1+T2+T3+T4 **387 passed, 4 skipped, 1 warning**. The four skips are Windows symlink-capability skips and the warning is the existing unrelated `pyreadline` deprecation warning.
- Existing production hashes remain unchanged: contracts `2902BB3CB8F3D78B9A5A764708672D7E35C3C73133FFA1DD6902E90707D1C873`, integrity `D09170932E3C46045F4AE212E4EFDB126B394DD1F43FAC70C5B1171969F8B95E`, prevalidator `D353CB4EC89A7B2906CB8AA2EB57C5325E2336E1D56E2D5CC2521DF3FDA59371`. New path validator hash: `7F6607F6A110161F836ED7F772949A686B5615E884F03A4ADCE3B9759B58604D`.
- T4 GREEN is ready for independent implementation review. Gate P2 remains open; real LLM/provider, pilot execution, formal experiment, large-scale experiment, and final-test remain prohibited.

# Phase 6B-T4 independent implementation review findings (2026-08-17)

- **Verdict: Request changes — 0 Critical, 2 Required.** The implementation is correctly bounded to controlled path/duplicate validation and is not a full validator or execution path, but two approved PIV-03 contracts remain open.
- **Required — validation/read TOCTOU:** `pilot_path_validator.py:271-312` checks link components, resolves the path, calls `is_file`, obtains identity via a separate `stat`, and then reopens the pathname for hashing. A concurrent rename/symlink replacement after the checks can make the read target differ from the validated target and can escape the approved root. This conflicts with `docs/pilot_manifest_validator_spec.md:71-73`, which requires rejection when resolution changes and reading/binding the exact resolved file. The repair should use a stable opened handle/identity and revalidation appropriate to each supported platform, with deterministic replacement tests.
- **Required — incomplete record/header formal leakage:** `pilot_path_validator.py:174-177` checks only top-level scopes, while `:237-251` checks only `lockbox_status` and `file_path`. A benign path with record-level `split=formal_train`, `formal_dev`, or `formal_final_test` is not rejected by this module. It also does not enforce the pilot header's literal `artifact_promotion_allowed=false`, and URI-like syntax is not explicitly rejected. This conflicts with the record/header rejection contract at `docs/pilot_manifest_validator_spec.md:106-112` and the review's formal-marker criterion.
- Pass: lexical parent traversal, outside absolute paths, host-incompatible drive forms, resolved-root escape, static symlink/reparse aliases, directories, wildcard patterns, missing files/hashes, and hash mismatches fail closed for tested cases.
- Pass: duplicate instance ID, declared hash, canonical resolved path, supported file identity/hardlink, family split, and generation identity cannot be bypassed by changing family/instance IDs.
- Pass: there is no directory enumeration, glob, `os.walk`, provider, candidate, runner, pilot, formal receipt, or execution authorization in the implementation. Results remain `execution_authorized=false` and `gate_p2_closed=false`.
- **Consider:** `file_identity_check="supported_pass"` is emitted even when a duplicate identity is found and the overall result is invalid. Rename this state to capability-oriented `supported`/`performed`, or distinguish `supported_failure`, before it becomes audit evidence.
- **Consider:** hashing explicitly listed files is streaming and bounded by manifest cardinality, but there is no per-file/aggregate byte budget. Define a pilot input-size limit before execution authorization to prevent resource-exhaustion inputs.
- **Consider:** four symlink tests remain skipped on this Windows host. Add a reliable Windows reparse/junction or mocked platform-boundary test before treating cross-platform link rejection as fully evidenced.
- Fresh authorized evidence: T4 **40 passed, 4 skipped, 1 warning**; T1+T2+T3+T4 **387 passed, 4 skipped, 1 warning**. No full suite or unauthorized provider/pilot/final-test operation ran.
- SHA-256 evidence confirms the reviewed dependencies retain their pre-T4 hashes: contracts `2902BB3CB8F3D78B9A5A764708672D7E35C3C73133FFA1DD6902E90707D1C873`, integrity `D09170932E3C46045F4AE212E4EFDB126B394DD1F43FAC70C5B1171969F8B95E`, prevalidator `D353CB4EC89A7B2906CB8AA2EB57C5325E2336E1D56E2D5CC2521DF3FDA59371`.
- Recommended next slice: Phase 6B-T4R RED-only tests for stable-handle/path-replacement rejection plus complete record/header formal/promotion/URI fail-closed behavior. T5 remains blocked pending RED→GREEN→review.

# Phase 6B-T4R RED-only initial findings (2026-08-17)

- The attachment matches the two Required findings and authorizes tests only; no protocol or fixture conflict was found.
- Deterministic TOCTOU coverage will inject mutation at the existing identity/hash boundary using only pytest `tmp_path`: in-place content replacement, rename/object swap, platform-gated symlink-to-outside replacement, and post-read path identity replacement.
- Formal leakage coverage will exercise record and nested header/meta `split`/`manifest_scope`, literal promotion fields, URI/UNC path syntax, and formal/final-test markers outside `file_path`.
- No project data or real final-test artifact is needed. The tests will use only synthetic temporary files and will not invoke provider, candidate, runner, pilot, or benchmark behavior.
- Production modules are locked read-only; T4R GREEN and T5 require separate authorization after observed RED evidence.

# Phase 6B-T4R RED-only findings (2026-08-17)

- Added 45 collected T4R cases to the existing test file: four TOCTOU cases (one platform-gated symlink), nine formal-split cases, nine record/header manifest-scope cases, four promotion cases, eight URI/UNC cases, eight family/instance marker cases, one file-hash marker case, and two nested scope/lockbox cases.
- Three executable TOCTOU tests deterministically mutate only `tmp_path` files at the current identity/hash seams. Current code accepts in-place content replacement, rename/object swap, and post-read identity replacement as valid when content hash matches; these are expected RED failures. The outside-symlink swap is skipped because this Windows environment cannot create the temporary symlink.
- Record/header failures prove top-level pilot scope does not protect nested `split`/`manifest_scope`: all 18 direct/nested formal split/scope combinations currently pass incorrectly.
- All four promotion cases currently pass: top-level true, missing top-level evidence, record-level true, and nested-header true.
- URI-like strings are rejected only later as missing files or other generic path outcomes, not as forbidden URI syntax; UNC is rejected as outside-root rather than explicit forbidden syntax. The tests also prove no URI/UNC read helper is invoked.
- Family/instance markers and nested scope/lockbox metadata currently pass. A final-test marker in `file_hash` is rejected only as malformed hash, so it lacks the required leakage classification.
- Authorized T4 target result: **89 collected, 44 failed, 40 passed, 5 skipped, 1 warning**. All 44 failures correspond to the intended missing contracts; no syntax, collection, fixture, or unexpected execution error occurred.
- Authorized combined result: **44 failed, 387 passed, 5 skipped, 1 warning**. The 44 failures are exactly the T4R set; prior T1/T2/T3 and original T4 behavior remain green/expected-skip.
- Production hashes remain unchanged: path validator `7F6607F6A110161F836ED7F772949A686B5615E884F03A4ADCE3B9759B58604D`, contracts `2902BB3CB8F3D78B9A5A764708672D7E35C3C73133FFA1DD6902E90707D1C873`, integrity `D09170932E3C46045F4AE212E4EFDB126B394DD1F43FAC70C5B1171969F8B95E`, prevalidator `D353CB4EC89A7B2906CB8AA2EB57C5325E2336E1D56E2D5CC2521DF3FDA59371`. Updated test hash: `2B7FF019B0678979DE1FBD49A10B64498525C904ADCF625E38081C158D7801FC`.
- No production code, docs, configs, data, provider, candidate, runner, pilot, benchmark, real LLM, or real final-test artifact was modified or accessed. T4R RED is ready for separately authorized GREEN; T5 and Gate P2 remain blocked.

# Phase 6B-T4R GREEN findings (2026-08-17)

- Modified only `src/mrta_rect_coverage/experiments/pilot_path_validator.py` as production code, plus the three planning files. Tests, fixtures, docs, configs, data, and the contracts/integrity/prevalidator modules were not changed.
- Closed the path/read TOCTOU cases with a pre-open path snapshot, the existing identity seam, an opened-file `fstat` check, hashing from that same stable handle, an after-read handle snapshot, and a final pathname/link/identity snapshot comparison. A pre/open/post mismatch returns a structured `path_toctou_detected` / `file_identity_changed` reason even when the replacement content hash matches.
- The stable handle is held for the complete byte read. It is released immediately after the handle snapshot so Windows rename/swap attempts can be observed by the required post-read pathname identity check; the hash helper does not reopen the path during controlled validation.
- Added recursive explicit-object checks for formal train/dev/final-test split or scope markers, lockbox/final-test metadata, identity/hash markers, and `artifact_promotion_allowed`. Missing or true top-level promotion evidence fails closed.
- URI-like `://` syntax and UNC/network syntax are rejected lexically before resolution or file reads. Existing root confinement, traversal, symlink/reparse, duplicate, no-glob, and no-discovery behavior remains green.
- Authorized T4/T4R result: **84 passed, 5 skipped, 1 warning**. Authorized T1+T2+T3+T4 regression: **431 passed, 5 skipped, 1 warning**. The five skips are Windows symlink-capability skips; the warning is the existing unrelated `pyreadline` deprecation warning.
- Current hashes: path validator `8516E309EC38010F062F022664B01088542330ED155EFECC2B13BA5D5ED92639`; unchanged contracts `2902BB3CB8F3D78B9A5A764708672D7E35C3C73133FFA1DD6902E90707D1C873`; unchanged integrity `D09170932E3C46045F4AE212E4EFDB126B394DD1F43FAC70C5B1171969F8B95E`; unchanged prevalidator `D353CB4EC89A7B2906CB8AA2EB57C5325E2336E1D56E2D5CC2521DF3FDA59371`; unchanged T4/T4R test `2B7FF019B0678979DE1FBD49A10B64498525C904ADCF625E38081C158D7801FC`.
- No project `data/` scan or real final-test access occurred. No full validator, formal/runner receipt, runner, provider, candidate execution, pilot execution, benchmark, or real LLM capability was implemented or invoked. Gate P2 remains open and T5 awaits independent review.

# Phase 6B-T5 RED-only protocol blocker (2026-08-17)

- The requested T5 contract directly conflicts with the currently approved PIV-04/schema boundary, so RED test authoring stopped before creating files as instructed by the attachment's conflict clause.
- `docs/pilot_infrastructure_task_breakdown.md` PIV-04 requires the receipt to bind raw manifest bytes. `docs/pilot_manifest_validator_spec.md` requires `manifest_hash`, and the strict `validate_manifest_validation_receipt_schema()` requires a non-null valid `manifest_hash`.
- T5 simultaneously forbids raw manifest bytes and requires the receipt not to claim that a raw bytes hash was verified. The suggested builder accepts only `manifest_obj`; it therefore cannot produce a truthful full `status=valid` PIV-04 receipt under the approved contract.
- Existing integrity semantics also need clarification: `verify_manifest_receipt_binding()` currently compares receipt `manifest_hash` with `compute_object_hash(manifest)`, while the approved runner/validator documents describe `manifest_hash` as the exact raw manifest SHA-256. This conflates two distinct hash domains.
- Required decision before RED: either (A) define a separately versioned object-only, inert, non-full validation-stage receipt that cannot claim PIV-04/full validity, or (B) authorize raw manifest bytes and preserve distinct `raw_manifest_bytes_hash` and `manifest_object_hash` bindings in the full receipt contract.
- No test, fixture, production module, docs, configs, or data was modified. `pilot_validation_receipt.py` and `test_pilot_validation_receipt_red.py` remain absent. No pytest/provider/candidate/pilot/benchmark/data/final-test operation ran.

# Phase 6B-T5C contract reconciliation findings (2026-08-17)

- The T5 conflict is resolved at the contract level by accepting caller-supplied `raw_manifest_bytes: bytes` together with `manifest_obj`; T5 remains no-I/O and must not accept or read a manifest path, directory, glob, discovered input, or final-test resource.
- PIV-04 receipt hash domains are now explicit and non-interchangeable: receipt `manifest_hash` is the SHA-256 of exact raw manifest bytes; optional `raw_manifest_bytes_hash` is only an equal explanatory alias; `manifest_object_hash` is the canonical parsed-object hash under the recorded algorithm/version.
- The manifest artifact header's existing `manifest_hash` remains a separate zeroed-field canonical-object self-hash. It cannot be copied into the PIV-04 receipt raw-byte field.
- A future receipt must strict-parse the supplied bytes, reject invalid/ambiguous JSON, require the parsed object to equal `manifest_obj`, and bind that object hash to prevalidation and any available path-validation object evidence. Hash-domain mismatch is always rejection.
- Receipt status is exactly `valid` or `rejected`. Even a valid receipt is inert: `execution_authorized=false`, `gate_p2_closed=false`, no runner/scheduled/provider/candidate/pilot result, and no formal or final-test readiness claim.
- Existing production remains intentionally unchanged. In particular, `pilot_integrity.py` currently uses `manifest_hash` for a canonical object hash in part of its receipt-binding API; this is a naming/domain ambiguity and must not be propagated. Any production/schema migration requires a separately authorized TDD phase and a new or explicitly migrated receipt version.
- This phase changes documentation/planning only. It does not implement a receipt builder/verifier, full validator, runner, provider, candidate execution, pilot, or path acquisition.
- The next eligible task is T5 **RED-only** tests for the explicit raw-manifest-bytes receipt contract. Gate P2 and every execution prohibition remain unchanged.

# Phase 6B-T5 raw-manifest-bytes validation receipt RED findings (2026-08-18)

- The proposed production module `mrta_rect_coverage.experiments.pilot_validation_receipt` is absent, so the RED suite can use the established phase-test import helper pattern and fail each behavior with an explicit missing-module message rather than a collection error.
- Existing helpers provide the exact primitives needed for independent expected values: `sha256_hex_bytes`, `compute_object_hash`, canonical receipt hashing, pure-object prevalidation results, and inert controlled path-validation results. The T5 tests must not reuse the ambiguous legacy `verify_manifest_receipt_binding()` as their oracle.
- `pilot_contracts.py` still describes the legacy validation-receipt v1 field set (`manifest_hash` plus `canonical_manifest_hash`). T5 RED targets the separately reconciled future contract and must not modify or silently reinterpret that production schema during RED.
- Test fixtures can be constructed entirely in memory. No new filesystem fixture is required for raw-byte/object/receipt binding; no project data or final-test resource needs to be read.
- The RED suite will require source-qualified rejection details, inert gate fields, explicit raw/object hash domains, non-self-referential receipt identity, full prevalidation/path evidence binding, and strict no-I/O sentinels.
- The new test file collects 120 cases and cleanly observes RED: all 120 failures are the intended missing target module message. No test passes accidentally, and no syntax/collection/fixture failure masks the missing behavior.
- The suite needs no JSON fixture files: compact/pretty raw bytes, malformed JSON, large-integer input, evidence records, tampering, and no-I/O sentinels are generated in memory.
- Coverage includes distinct raw/object/artifact-header domains; strict bytes/UTF-8/object/duplicate-key/large-int parsing; non-self-referential receipt IDs and tamper cases; complete prevalidation/path evidence; four-way status composition; source-qualified schema/integrity/binding/raw/path/duplicate/scope reasons; exact `valid`/`rejected` states; inert fields; no path/glob/walk access; and no full-validator/formal/final-test overclaim.
- The optional authorized T1–T4 regression remains green at **431 passed, 5 skipped, 1 warning**. Skips are existing platform-gated link cases; the warning is the existing unrelated `pyreadline` deprecation warning.
- Production hashes remain unchanged: contracts `2902BB3CB8F3D78B9A5A764708672D7E35C3C73133FFA1DD6902E90707D1C873`; integrity `D09170932E3C46045F4AE212E4EFDB126B394DD1F43FAC70C5B1171969F8B95E`; prevalidator `D353CB4EC89A7B2906CB8AA2EB57C5325E2336E1D56E2D5CC2521DF3FDA59371`; path validator `8516E309EC38010F062F022664B01088542330ED155EFECC2B13BA5D5ED92639`.
- New test SHA-256 is `6BDBFD7136403E8762C0B81AC8A8909FDDEBCB268FE2D3737746EFEBCDB7C21E`. The target production module and optional fixture directory are both absent.
- T5 RED is complete. A future GREEN requires separate authorization and may implement only the minimal pure in-memory builder/verifier needed by these tests; it may not implement path acquisition, a full validator, runner/provider/candidate/pilot execution, formal/final-test behavior, or Gate P2 closure.

# Phase 6B-T5 GREEN findings (2026-08-18)

- Added one production module, `pilot_validation_receipt.py`, implementing only a pure in-memory builder/verifier over explicit bytes and evidence mappings.
- Receipt raw-byte `manifest_hash` and equal alias `raw_manifest_bytes_hash` are computed with SHA-256 over the supplied bytes; `manifest_object_hash` is computed independently with the approved JCS safe-integer canonicalizer. Artifact-header self-claims are never used as receipt hashes.
- Strict parsing requires literal bytes, UTF-8, one JSON object, no duplicate keys or nonstandard constants, safe canonical number domain, and semantic equality with `manifest_obj`.
- Receipt identity is a lowercase SHA-256 of the canonical body excluding `validation_receipt_id`, `signature`, and `signatures`. Verification establishes ID integrity before interpreting receipt semantics and reconstructs the full expected body from current explicit inputs.
- Prevalidation and path evidence are copied through fixed allowlists, their result IDs are recomputed, object bindings and inert flags are checked, and rejected evidence is preserved with source-qualified layers.
- Status is `valid` only when raw/object consistency and both evidence branches are valid; otherwise it is `rejected`. Receipt execution/formal/Gate fields remain false.
- Fresh authorized evidence: T5 **120 passed, 1 warning**; combined T1–T5 **551 passed, 5 skipped, 1 warning**. No full suite or prohibited execution ran.
- Static capability audit found no file/path acquisition, glob/walk, provider, runner, candidate, or pilot capability. Search matches are limited to the module boundary docstring and evidence/rejection field names.
- New production SHA-256 is `8457CA3A3916F3076008D7D2049C3E7E8477227FD4B209D68D604B5D9835EFB5`. Existing contracts, integrity, prevalidator, path validator, and T5 tests retain their pre-GREEN hashes.
- The module does not modify or call the legacy ambiguous `verify_manifest_receipt_binding()` path. It computes the reconciled raw-byte and object domains independently.
- T5 GREEN is ready for independent implementation review. Gate P2 and all provider/pilot/formal/final-test prohibitions remain active.

# Phase 6B-T5 independent review working findings (2026-08-18)

- Tests strongly cover the reconciled raw-byte/object hash domains, strict raw JSON parsing, inert states, receipt-ID ordering, source-qualified rejection reasons, and no-I/O sentinels.
- Static implementation review confirms the new module has no path/provider/runner/candidate/pilot imports or execution calls.
- A fail-closed question remains under review: the receipt copies several prevalidation/path evidence fields but currently validates only a subset of their required types/values; a self-consistent evidence object may therefore be content-bound without being contract-valid.
- `validation_receipt_id` is a content hash, not an authentication token. `validator_identity` is bound as ordinary content but is not independently trusted by the verifier; the final review must avoid overstating this guarantee.
- The T5 builder validates upstream result IDs and selected fields, but does not call the existing prevalidation verifier or enforce all copied evidence fields. In particular, valid prevalidation family/split hashes and valid path approved-root/duplicate/file-identity evidence can be missing or malformed while a caller recomputes the upstream result ID.
- The actual T4 `PilotPathValidationResult` currently exposes only `valid`, rejection reasons, scope, file-identity status, and inert flags; it does not yet produce the mapping/result ID/evidence envelope consumed by T5. This is an integration gap for a later task, not proof that the T5 pure receipt code performs path validation.
- Existing T5 tests mutate already-valid evidence and verify old-receipt mismatch, but do not construct self-hashed malformed evidence (missing/wrong-type required hashes/summaries, inconsistent valid-state fields). Therefore 120/120 GREEN does not close the upstream-evidence semantic validation gap.

# Phase 6B-T5 independent review conclusion (2026-08-18)

- **Critical: 0.** Hash domains, strict explicit-byte parsing, receipt-ID ordering, inert semantics, and no-I/O/no-execution boundaries are correctly implemented for the tested contract.
- **Required: 1.** Upstream evidence validation is incomplete. `_prevalidation_evidence` does not validate the family/split object hashes or valid-branch schema/integrity/rejection invariants; `_path_validation_evidence` copies but does not validate approved-root fingerprint, duplicate summary, or file-identity status. Recomputing an upstream result ID can therefore make malformed evidence content-addressed without making it contract-valid, yet T5 may emit `status=valid`.
- The required repair should begin with T5R RED-only cases for missing/wrong-type/self-hashed evidence and inconsistent valid branches, followed by a narrow GREEN that rejects them. T6 is not authorized until this review finding is closed.
- **Consider:** treat `validator_identity` and `validation_receipt_id` accurately as ordinary content-bound evidence and a content hash, not authenticated identity or a capability token. A later trusted receipt requires a separately designed trust/signature mechanism.
- **FYI:** the existing T4 result is not yet the full T5 evidence envelope. After T5R closes, the smallest T6 task should be a non-executing adapter/integration contract that produces and verifies the complete path/prevalidation evidence envelope; it must not become a runner or close Gate P2.

# Phase 6B-T5R RED-only working findings (2026-08-18)

- The approved RED contract requires attacker-style evidence that is semantically malformed but has a freshly recomputed upstream result ID; old-receipt tamper tests are insufficient.
- The current fixture field names are `pilot_family_matrix_object_hash`, `pilot_split_rule_object_hash`, `no_glob_confirmed`, and `no_directory_discovery_confirmed`; T5R will test these approved equivalents rather than invent a second schema.
- For malformed upstream evidence, the required behavior is twofold: the builder must not emit `status=valid`, and the verifier must fail closed rather than treat a self-consistent rejection receipt as ordinary verified success.
- Content-hash coverage for `validator_identity` will assert ordinary string binding and absence of authentication/authority claims; it will not introduce a signature or trust mechanism.
- Exactly 100 new cases were collected: 97 expose the intended upstream-evidence gap and 3 coverage cases already pass (receipt-ID ordering, omitted-malformed-reason tamper rejection, and validator-identity non-authentication semantics).
- The 97 expected failures split into 49 prevalidation cases and 48 path cases. They fail either because malformed self-hashed evidence still produces `status=valid`, or because a rejected receipt over malformed evidence is still returned as verifier `valid=True`.
- No new failure is caused by collection, syntax, fixture setup, I/O, provider invocation, or unrelated T1–T4 behavior.

# Phase 6B-T5R RED-only conclusion (2026-08-18)

- Added 100 pure in-memory contract cases to the existing T5 file. The new coverage spans required-field deletion, hash/ID format, strict types/enums, valid/rejected branch invariants, explicit self-hashed replay attacks, receipt-ID-before-semantics ordering, omitted-malformed-reason tampering, and validator identity's non-authentication boundary.
- Target result is a clean RED: **220 collected, 97 failed, 123 passed, 1 existing warning**. The three newly passing cases are coverage-only invariants already satisfied; all 97 failures correspond to the reviewed evidence-validation gap.
- Optional combined result is **97 failed, 554 passed, 5 platform skips, 1 existing warning**; existing T1–T4 behavior remains green.
- Production hashes are unchanged: receipt `8457CA3A...5EFB5`, contracts `2902BB3C...1C873`, integrity `D0917093...8B95E`, prevalidator `D353CB4E...59371`, path validator `8516E309...92639`. Updated T5 test SHA-256 is `E419D5211293DDC2F4D796052F1C9A51473FE8A236CDF2ECED7457841CD1583B`.
- The minimal future GREEN is to enforce exact upstream evidence fields/types/enums and branch invariants in both build and verify paths. It must remain pure in-memory and inert; no full validator, runner, provider, candidate, pilot, or Gate P2 capability is authorized.

# Phase 6B-T5R GREEN working findings (2026-08-20)

- The approved GREEN must not treat a correct result ID as semantic evidence. Exact required-field sets, strict JSON/Python types, lowercase SHA-256 formats, enums, and valid/rejected branch invariants must all pass independently.
- Build and verify already share `_build_from_snapshots`; tightening the two evidence helpers there preserves receipt-ID-first verification while ensuring the reconstructed expected receipt carries malformed-evidence reasons.
- The approved T5 path evidence envelope uses `approved_root_fingerprint`, a fixed five-counter `duplicate_validation_summary`, `file_identity_check`, `no_glob_confirmed`, and `no_directory_discovery_confirmed`. No new T4 I/O or controlled-path field will be invented in this repair.
- `validator_identity` remains a non-empty content-bound string only; no trust/signature/authority field or behavior is authorized.
## Phase 6B-T5R GREEN implementation decisions (in progress)

- Upstream prevalidation and path evidence will be validated with branch-specific required-field, type, enum, hash-format, and invariant checks; a self-consistent receipt hash is not sufficient to make malformed evidence verifiable.
- Receipt verification will continue to verify `validation_receipt_id` first, then rebuild raw/object bindings, and will fail closed when either upstream evidence object is structurally or semantically malformed.
- Legitimate rejected upstream results remain distinguishable from malformed evidence: rejected branches require explicit failure layer/reasons, while valid branches require all success invariants and inert gate fields.
- The implementation remains pure in-memory and will not add path access, hash-domain changes, runner/provider/candidate/pilot execution, or Gate P2 authorization.

## Phase 6B-T5R GREEN result

- Malformed or self-hashed upstream evidence is no longer made verifiable merely by recomputing its upstream ID and the enclosing validation receipt ID.
- Prevalidation evidence now enforces required fields, strict booleans, canonicalization identity, object-hash domains, binding state, and valid/rejected branch semantics.
- Path evidence now enforces required fields, strict booleans, lowercase SHA-256 fields, exact duplicate-summary shape/count types, file-identity state, inert/no-glob/no-discovery guarantees, and valid/rejected branch semantics.
- Verification preserves receipt-ID-first ordering and subsequently fails closed on malformed upstream evidence.

- The follow-up attachment was checked against the implemented contract: required prevalidation/path schema checks, self-hashed attack closure, verifier ordering, inert receipt semantics, and non-authenticating `validator_identity` semantics are already represented by the current implementation and tests.

## Phase 6B-T5R2 exact upstream evidence-envelope findings

- The real T3 output envelope has exactly 18 fields: `prevalidation_schema_version`, `prevalidation_result_id`, `status`, `result_scope`, `schema_valid`, `integrity_valid`, `failure_layer`, `rejection_reasons`, three object hashes, `binding_available`, `binding_unavailable_reason`, canonicalization algorithm/version, and the two inert gate flags.
- The real T3 schema version is exactly `pilot-prevalidation-core-v1`. The existing T5 helper's `pilot-prevalidation-v1` is stale and is now an explicit rejection case rather than a source of truth.
- T3 production verifies exact key equality, result ID, scope/status, object bindings, binding state, and inert flags. A positive control now calls the real T3 builder, verifies its exact output shape/ID, and passes that result through both T5 APIs.
- T4 production currently returns a six-field dataclass: `valid`, `rejection_reasons`, `result_scope`, `file_identity_check`, `execution_authorized`, and `gate_p2_closed`. It does not produce the expanded T5 path mapping with schema version, result ID, manifest/root hashes, duplicate summary, or no-discovery flags.
- The path RED cases therefore freeze exactness of the existing T5 synthetic mapping (`pilot-path-validation-v1`) without claiming that T4 already emits it. The T4-to-T5 adapter/envelope remains a separate integration gap.
- Before the T5R2 GREEN attempt, T5 `_PREVALIDATION_FIELDS` omitted `prevalidation_schema_version`, `_PATH_VALIDATION_FIELDS` omitted `path_validation_schema_version`, and neither evidence validator rejected unknown top-level fields.
- The 25 new failures cover missing, old, wrong, near-miss, and wrong-type versions; alias/typo keys; and unknown extra fields for both evidence branches. Upstream IDs are recomputed after every mutation, and both builder and verifier are evaluated.
- All failures are the intended fail-open behavior: malformed self-hashed evidence produces/validates a `valid` receipt. The real-upstream positive control and all prior T5 cases pass.

Gate finding: P2 remains open. T6, provider/candidate/pilot/benchmark/final-test, and production changes remain unauthorized.

## Phase 6B-T5R2 GREEN attempt findings

- `pilot_validation_receipt.py` now defines the approved versions `pilot-prevalidation-core-v1` and `pilot-path-validation-v1`, includes both schema-version fields in the copied evidence, rejects any key-set difference, and rejects wrong/missing/wrong-type versions.
- The 25 new T5R2 cases all pass after this change, including self-hashed unknown-field and version-spoofing cases. No tests were edited.
- The frozen pre-existing helper `_prevalidation_result()` still emits `pilot-prevalidation-v1`. Nine older baseline tests use that helper as a valid receipt source and now fail, while the real T3 positive control passes.
- This is an irreconcilable contract conflict under the current authorization: accepting the stale helper would violate the explicit requirement that `pilot-prevalidation-v1`, aliases, and near-miss versions fail closed. A manifest-shape or caller-specific exception would weaken the exact-version contract and was not added.
- Target result: **237 passed, 9 failed**. The 9 failures are fixture/expectation drift only; no syntax, import, collection, or new-contract failures occurred.

Gate P2 remains open. T6 and all real execution paths remain unauthorized. GREEN cannot be claimed until the frozen test contract is reconciled under separate authorization.

## Phase 6B-T5R2C reconciliation result

- The 9 failures were individually traced to `_build()` using the default `_prevalidation_result()` or `_binding_unavailable_prevalidation()` helper, both of which still emitted `pilot-prevalidation-v1`.
- The affected tests were: raw/object hash-domain positive path, raw-format verifier mismatch, both hash-domain tamper cases, raw-parse verifier case, signature-exclusion positive path, valid/valid status composition, raw-manifest hash mismatch, and explicit-bytes/no-path positive path.
- Each failure's receipt was rejected or verifier-invalid solely because strict production correctly rejected the stale version; the real T3 positive control and all 25 T5R2 exact-envelope/version cases already passed.
- Updated only the two canonical helper defaults to `pilot-prevalidation-core-v1`. The explicit `pilot-prevalidation-v1` legacy negative case remains unchanged and continues to require rejection.
- No production relaxation, version alias, normalization, skip, xfail, or test deletion was introduced.
- T4 production still returns the six-field dataclass; the T5 expanded path evidence mapping remains a separate unresolved adapter/integration task.

Verification: T5 target `246 passed`; authorized T1-T5 regression `677 passed, 5 skipped`; no warnings reported by these commands. T5R2C is test-contract reconciliation, not independent review. Gate P2 remains open and T6 remains unauthorized.

## Phase 6B-T5R3 contract-gap finding

- Current T4 production result is `PilotPathValidationResult(valid, rejection_reasons, result_scope, file_identity_check, execution_authorized, gate_p2_closed)`.
- T4 can supply `status` via `valid`, `result_scope`, `file_identity_check`, `rejection_reasons`, and the inert flags. An explicit `manifest_obj` invocation context can supply `manifest_object_hash`; schema version and result ID are deterministic derived fields once a complete mapping exists.
- `approved_root_fingerprint` has no T4 result field, no approved fingerprint algorithm, and no existing provenance helper.
- `duplicate_validation_summary` requires five exact counts, but T4 exposes only deduplicated reason strings; exact counts cannot be reconstructed from the result.
- `no_glob_confirmed` is enforced by T4 path syntax rejection but is not emitted as result-level evidence. `no_directory_discovery_confirmed` is an implementation property of the current validator, not an emitted result claim.
- The synthetic T5 path helper contains values for these fields, but no current production source proves them. Constructing them as `True`, `0`, `{}`, or a guessed root hash would violate the no-invented-evidence rule.

Conclusion: the T4-to-T5 integration contract is currently contradictory/incomplete. The minimum next task must define and produce these provenance fields at the T4-side result/evidence source, including the root-fingerprint algorithm and duplicate-count semantics. No adapter, tests, or production integration was added in this RED recovery turn.

## Phase 6B-T4E contract-ambiguity finding

- T4's real validator performs duplicate checks by emitting deduplicated reason strings such as `duplicate_instance_id`, `duplicate_file_hash`, `duplicate_canonical_path`, `duplicate_file_identity_hardlink`, and `duplicate_generation_identity`; it does not expose counts.
- T5 currently freezes only the five-key `duplicate_validation_summary` shape: `instance_id_duplicates`, `file_hash_duplicates`, `canonical_path_duplicates`, `file_identity_duplicates`, and `generation_identity_duplicates`. The source does not define whether each value means duplicate findings, collision groups, rejected duplicates, or another quantity.
- `approved_root_fingerprint` remains undefined: no current T4 result field, canonical root preimage, or approved hashing rule exists.
- `no_glob_confirmed` is ambiguous between “all explicit input records passed glob-syntax checks” and “the validator used no glob/discovery capability.” `no_directory_discovery_confirmed` is similarly ambiguous between an input/result claim and a producer-declared implementation invariant.
- Because these meanings are not frozen, any RED positive fixture or GREEN producer would choose semantics rather than recover them. The prompt explicitly requires stopping on CONTRACT AMBIGUITY.

Required clarification before implementation: freeze the root-fingerprint preimage/algorithm, define each duplicate counter's unit, and decide whether the no-glob/no-directory fields are evidence of input checks, declared producer invariants, or both. Gate P2 remains open and T6 remains unauthorized.

## Phase 6B-T4E-R1 findings

- PRE-RED A-E all pass. T4 uses `Path(approved_root).resolve(strict=True)` for confinement, implements all five duplicate checks, retains enough per-record state for additional-record counts, uses `_GLOB_CHARS`, and consumes only explicit caller records.
- `approved_root_fingerprint` is `compute_object_hash({"schema": "pilot-approved-root-fingerprint-v1", "canonical_approved_root": os.path.normcase(str(resolved_root))})`. It identifies the canonical root path and does not hash directory contents.
- `duplicate_validation_summary` counts each record after the first match independently in the five existing uniqueness dimensions. One record may increment multiple counters; reasons remain deduplicated categorical codes.
- `no_glob_confirmed` records whether every supplied string path passed the existing prohibited-glob syntax rule. It is independent of overall validity.
- `no_directory_discovery_confirmed` is a producer-declared, content-bound invariant of the explicit-record-only validator. It is not authentication, filesystem isolation, a sandbox guarantee, or a cryptographic proof.
- The canonical producer emits the exact T5 13-field mapping at fixed version `pilot-path-validation-v1`; `path_validation_result_id` hashes every field except itself with the existing canonical object hash.
- `manifest_object_hash` is explicit caller context and must be lowercase SHA-256 hex. The producer does not read or discover a manifest path.
- Real valid T4 evidence builds and verifies a valid T5 receipt. Real duplicate-rejected T4 evidence remains a rejected receipt and verifies as an internally coherent rejected receipt.
- During combined verification, existing Windows snapshot logic intermittently compared a stale pathname `st_ctime_ns` with a refreshed handle value. Python 3.13 exposes stable `st_birthtime_ns`; using it when available removed 500/500 probe mismatches while retaining the original `st_ctime_ns` fallback and all identity/size/mtime/hash checks.
- T5 exact key/version/type/hash/branch validation was not modified or relaxed.

Gate P2 remains OPEN. T6 and provider/candidate/pilot/benchmark/formal/final-test execution remain unauthorized.

## Phase 6B-T4E-R1R bounded repair findings

- Closed the sole Required finding from the independent review. `_snapshot_from_stat()` no longer unconditionally prefers `st_birthtime_ns`.
- `_select_snapshot_change_timestamp()` now applies the platform contract explicitly: Windows (`os.name == "nt"`) uses valid `st_birthtime_ns` and falls back to valid `st_ctime_ns`; all non-Windows platforms use `st_ctime_ns` only.
- Synthetic tests demonstrate that non-Windows birthtime stability cannot hide a ctime-only metadata mutation.
- Hardlink/file identity remains exclusively `(st_dev, st_ino)`; timestamps are not used to classify same-file identity.
- No root-confinement, duplicate counter, evidence schema, result ID, glob, directory-discovery, manifest binding, or T5 integration semantics changed.
- Consider items from the prior review (unsupported identity producer case and malformed manifest hash direct test) were not expanded into this bounded repair; they remain follow-up considerations, not blockers for this Required finding.

Gate P2 remains OPEN. T6, R0, provider/candidate/pilot/benchmark/formal/final-test remain unauthorized.

## Phase R0 Core Runtime Bring-Up findings

- The repository is a source-layout Python project under `mrta_rect_coverage`; the canonical invocation is `PYTHONPATH=src` followed by `python -m mrta_rect_coverage.main --config <config>`.
- The recovered runtime chain is config -> instance loader -> state generation -> cost matrix -> Route DP -> multi-robot evaluation -> baseline/ALNS -> visualization output.
- `R2_T6_0` has 2 robots, 6 tasks, sweep width 2.0, speed 1.0, and turning time 0.5. `R2_T10_0` has 2 robots, 10 tasks, sweep width 3.0, speed 1.0, and turning time 5.0.
- Baseline and ALNS both completed on both inputs with exit code 0. All four solutions have exact task coverage, no duplicates or invalid IDs, finite Route-DP costs, finite makespan, and `makespan == max(route_costs)`.
- T6 baseline and ALNS repeated runs are identical for routes, per-route costs, and makespan under seed 0.
- The authorized core test target passed: `10 passed`.
- Existing non-blocking warning: Matplotlib cannot use `Annotation` objects as legend handles at `src/mrta_rect_coverage/visualization/plot_solution.py:118`.
- Known P0 risks remain recorded for R1: travel/time unit consistency, universal solution-feasibility validation, and scientific distinction of `dp_aware_insertion` from `greedy_insertion`.

R0 conclusion: `CORE_RUNTIME_READY = TRUE`. This is runtime bring-up evidence only, not paper-grade optimization evidence or permission for any provider, candidate, pilot, benchmark, formal, large-scale, final-test, or T6 action. Gate P2 remains OPEN.

## Phase R1 Scientific Correctness findings

- P0-A contract recovery found no ambiguity: `docs/modeling_decisions.md` had already approved independent sweep and travel speeds. The former three-value instance line and distance-only transitions were the implementation gap.
- The R1 instance schema is `sweep_width sweep_speed travel_speed turning_time`. Legacy implicit-travel-speed inputs fail closed; both speeds must be finite and positive.
- `CostMatrix` converts depot-to-state, state-to-state, and state-to-depot Manhattan distance to time using the explicit travel speed. Coverage processing continues to use sweep speed and the DP recurrence is unchanged.
- P0-B was confirmed: the previous general evaluator returned finite values for missing/duplicate solutions. Complete evaluation now validates route count, legal IDs, exact coverage, duplicates, and missing tasks before Route DP. Empty routes remain legal.
- ALNS destroy states now use the distinct partial evaluator. It allows missing tasks while retaining route-count, ID, and duplicate checks; no generic skip-validation flag exists.
- P0-C was confirmed: greedy, regret, and bottleneck repair already use Route DP, while `dp_aware_insertion` directly called greedy. The alias remains only as a private compatibility method and cannot be selected or enabled as an independent operator.
- `alns_dp_aware` was removed from approved benchmark labels. The deprecated config flag fails closed when true, and shipped configs set it false.
- The speed-1 smoke instances explicitly declare travel speed 1, so the R0 objective values remain exactly 228, 206, 1061, and 904.

R1 does not establish paper-grade data, empirical performance, physical-system timing, collision/congestion behavior, energy constraints, or operator innovation. Those remain outside the scientific-core claim.

## Phase R2 Paper-Grade Instance/Data Protocol findings

- Current production instance schema is six non-empty lines with explicit `sweep_width`, `sweep_speed`, `travel_speed`, and `turning_time`; filename metadata must match content and the depot is `(0, 0)`.
- Only `data/R2_T6_0.txt` and `data/R2_T10_0.txt` existed before R2. They remain smoke/demo inputs and are not development, held-out, or final evidence. Existing operator-evolution defaults still contain a broad `data/R*_T*_*.txt` glob; the new protocol does not rely on it.
- Added `dataset_protocol.py` with versioned `FamilySpec`, deterministic SHA-256 seed derivation, non-overlapping rectangle generation, production-loader round-trip, intrinsic feature extraction, exact manifest schema/hash checks, split-scoped allowlist loading, and explicit overwrite refusal.
- The sanity matrix has six disjoint family IDs: two development, two held-out, and two final, one replicate each. Family labels are intrinsic generation factors only; no solver result is read or stored.
- Sanity artifacts are under `data/r2_sanity/` with manifests under `manifests/`; each split has two instances. Manifest entries contain input/provenance metadata and no makespan, solver, ranking, or LLM fields.
- The manifest loader verifies relative-path confinement, exact file SHA-256, split/metadata consistency, and the production six-line parser. It performs no wildcard or directory discovery.
- The full paper dataset remains a future plan requiring a frozen family matrix, independent replicates, and separate authorization. R2 did not execute baseline/ALNS benchmark, significance testing, LLM/provider, candidate, operator evolution, tuning, pilot, or final-test solver work.
- Final verification: protocol target **7 passed**; restricted core regression **57 passed**, no warnings. Six generated files and all three manifests reloaded with exact SHA-256 matches; static forbidden-capability scan for the protocol module found no matches. Pilot/gate production hashes are unchanged from the R1/T4E baseline.
- R2 definition of done is satisfied for the protocol scope: `PAPER_DATA_PROTOCOL_READY = TRUE`. This is data/provenance readiness, not empirical optimization evidence or Gate P2 closure.

## Phase R3 Optimization Diagnostics findings

- The current Track A inventory is no longer the two-file R2 audit state. There are 61 root-level non-final files, all accepted by `parse_instance_filename()` and `load_instance()`.
- Inventory groups are `R2_T6: 1`, `R2_T10: 10`, `R2_T20: 10`, `R4_T40: 10`, `R4_T60: 10`, `R8_T80: 10`, and `R8_T100: 10`.
- The two R2 final-manifest paths are explicitly excluded. R2 controlled development and held-out instances remain Track B; held-out has not been opened for behavioral analysis.
- Track A has no authoritative family provenance, so no geometry/spatial/travel/HV family labels will be inferred. It will be described only by computed intrinsic features.
- Existing R2 intrinsic features omit several R3 requirements: pairwise distances, min/max summaries, relative H/V gaps and preference fractions, processing-load pressure, and state variability.
- Existing ALNS history lacks repair-before-local-search objective, assignment/order/local-search gain, accepted-move state-chain diffs, DP cascade, objective components, and Route-DP call/cache statistics. Complete R3 claims require focused instrumentation before diagnostic execution.

### R3 final findings

- Completed 45 built-in-only diagnostic runs: 29 Track A, 10 controlled development, and 6 held-out. Consolidation retains 65 non-final inventory rows and produces 11 source-aware behavioral summaries.
- Legacy Track A/development run IDs were normalized in memory to include source/family provenance. All 45 IDs are unique; the six raw JSON inputs were not rewritten and their hashes are embedded in `outputs/r3_diagnostics/metadata.json`.
- Track A mean relative improvement spans 0.0965-0.3554. Route-cost CV falls from a development mean of 0.0769 to 0.0080, while positive bottleneck relief has rho 0.967 with relative improvement.
- Accepted positive gain attribution over development runs is assignment 15,014.24, ordering 367.27, and local search 9,723.24. Assignment is the aggregate leader; local search remains substantial and is kept separate from repair attribution.
- Development accepted-move state switching averages 0.293 and DP cascade averages 0.168. Destroy-specific state-switch means range 0.122-0.262 and cascade means 0.077-0.160, supporting non-trivial outer/inner coupling.
- Controlled destroy ranking changes from random in both development families to geometry-aware in both held-out families. The result holds for both pre-LS repair gain/use and the frozen H3 positive objective gain/use metric.
- Held-out H1 is mixed: higher H/V gap raises cascade from 0.1624 to 0.2254 but lowers state switching from 0.4923 to 0.2699. H2 and H3 are supported without post-access metric or threshold changes.
- Route-DP compute accounts for about 86-94% of runtime on Track A T20-T100, but only 13.6% at T6. It is the main measured medium/large-scale bottleneck, not a universal small-scale bottleneck.
- The evidence gates are C1 `SUPPORTED`, C2 `SUPPORTED`, and C3 `PARTIALLY SUPPORTED`. The recommended R4 direction is DP-grounded, complementarity-aware operator design with bounded failure-guided revision.
- Final verification: R3 focused **12 passed**; restricted core/R2 regression **55 passed**; 0 failures and 0 warnings. Eight plots were exported in both PDF and 300-DPI PNG and visually inspected.
- Static audit found no provider/network/subprocess imports in R3 files. Consolidated runs contain no provider/generated-operator use and no final path. The five pilot/gate hashes remain unchanged.

R3 conclusion: `OPTIMIZATION_DIAGNOSTICS_READY = TRUE`. Gate P2 remains OPEN; T6 and R4 are not authorized automatically.
# Phase R4 findings - real-time threat verification and modified Option A freeze

- The threat matrix is grounded in source-level evidence. Formal publication metadata was preferred; inaccessible fields remain `UNKNOWN` or `NOT VERIFIED`.
- EoH-S directly implements instance-performance complementarity and heuristic-set design. ReVEL directly implements behavior-aware grouping and structured performance feedback. Behaviour Space Analysis directly implements generic behavior-space analysis but leaves integration into the evolution loop as future work. RouteRepair directly implements instance-level failure diagnosis and targeted repair.
- Generic complementary sets, generic behavior feedback, generic behavior analysis and generic failure repair are excluded from the R4 novelty claim.
- The only retained potential distinction is exact deterministic Route-DP response used as structured feedback for offline MR-RCRP operator evolution: state-switch fraction, H/V mode switches, entry/exit changes, indirect DP cascade, bottleneck relief and travel/coverage/turning response. This remains `POTENTIAL_DIFFERENTIATION - NOVELTY_UNVERIFIED`.
- C1 is primary; C2 is a constrained secondary mechanism; C3 is an optional secondary ablation.
- C2 uses no arbitrary weighted sum. The frozen order is eligibility gate, minimum quality floor, best-quality anchor, maximum marginal structural-regime coverage, exact-DP behavioral tie-break and fixed small set size.
- Invalid, infeasible, timeout-heavy, fallback-heavy, contract-invalid and runtime-unacceptable operators cannot enter the set.
- Structural regimes use existing intrinsic features, including task/robot ratio, heavy-task ratio, spatial dispersion, H/V sensitivity and travel/coverage regime. Candidate metric alternatives and the recommended default are recorded in `docs/research_method_vNext.md`.
- The main chain is B0 manual ALNS, L0 one-shot generation, L1 scalar/top-weak feedback, L2 exact-DP behavioral evolution and L3 L2 plus exact-DP-response complementarity. C3 is outside the main chain.
- ReVEL-like generic feedback, EoH-S-like instance-performance complementarity and RouteRepair-like targeted repair comparisons are required.
- The comparison protocol is frozen in `docs/r4_experiment_comparison_protocol.md` with equal-budget accounting, direct threat baselines and no-execution boundaries.
- R3's six diagnostic held-out runs are `diagnostic-heldout-consumed`; they cannot be future confirmatory held-out data. New selection-validation and confirmatory-heldout splits are required. Final-test remains locked.
- R4 is documentation-only and does not implement the mechanism or authorize R5. Gate P2 remains OPEN; T6 and all real execution gates remain unauthorized.

## Phase R5 contract recovery

- R5 authorization is limited to a trusted mock/file research pipeline. The existing legacy file provider reads Python source and the candidate loader/proxy can execute it; those paths are not suitable for R5 and will not be invoked.
- The R5 implementation target is an isolated structured-fixture pipeline covering R4 schemas, behavior profiles, feedback modes, lineage, archive, lexicographic selection, deployment policies, C3 payloads, split manifests, budget ledger and yield metrics.
- R5 evidence may demonstrate only end-to-end plumbing under trusted fixtures. It cannot support real LLM effectiveness, generalization, novelty, SOTA or final-test claims.
- R5 RED is clean: the scoped test module fails only on the missing target module. This establishes the tests-first baseline before production implementation.
- R5 implementation intentionally avoids the legacy source-execution path. The new module has no dynamic import, `exec`, subprocess, network, solver, pilot or final-test capability; all candidate behavior is trusted structured fixture metadata.
- R5 target tests passed: **17 passed**. Focused non-RED operator/R2/R3 regression passed: **28 passed**; full suite was not run.
- Scenarios A-D passed in a fresh deterministic mock run. The selected set and trace are audit artifacts only; they are not optimization evidence.
- Current protected hashes include Route-DP `38832DA77524C00C4FBCD649D8001DCDD89F3B841A723507FF556709C47DBE4A`, validation receipt `DC7C77094F2A5F42F4C3DFB55D4D9D37084CB6CFCFE1F6A93C7CB1475010D36D`, prevalidator `D353CB4EC89A7B2906CB8AA2EB57C5325E2336E1D56E2D5CC2521DF3FDA59371`, and path validator `7AED6E24F1A58314F63F5FCBEE8A537111A75DE77CC46DA2CD689458A244912E`; these were not modified by R5.
- `MOCK_RESEARCH_PIPELINE_READY = TRUE` is a plumbing claim only. It does not authorize R6, real-provider pilot, formal experiment, final-test or T6.

## Phase R6 independent readiness review (read-only)

- Fresh scoped verification passed: R5 target 17 tests; R2/R3 focused regression 19 tests; combined scoped target 36 tests. Full suite was not run.
- R6 verdict is `Request changes`: 0 Critical, 6 Required, 3 Consider.
- Required gaps are exact-DP metric computation/binding to R3 definitions, intrinsic regime binding, verifiable lineage/source-hash binding, actual elite reuse, persisted evaluation hierarchy, and enforced trusted-fixture allowlisting.
- Static R5 boundary scan found no dynamic import, `exec`, subprocess, network, legacy candidate-loader/proxy or final-test capability in the R5 module/tests.
- `REAL_PROVIDER_GENERATION_READY = FALSE`; `UNTRUSTED_EXECUTION_READY = FALSE`; Gate P2 remains OPEN and T6 remains NOT AUTHORIZED.
- Full details: `docs/r6_independent_readiness_review.md`.

## Phase R5R provenance and trust repair

- R1: R5 profile construction now calls the canonical R3 `state_chain_diff`; trusted fixtures supply before/after state chains and moved-task IDs, and self-declared DP values are overwritten by deterministic results.
- R2: R5 candidates with intrinsic features must exactly match the versioned deterministic regime mapper. Fixture structural regimes are derived, not declared.
- R3: generation>0 lineage binds every parent candidate ID to its archived source hash; wrong hashes and same-ID source replacement fail closed.
- R4: versioned elite retention events identify run/from/to/ID/hash/mode and are validated against real next-generation parent reuse.
- R5: persisted `evaluation_records.jsonl` contains deterministic evaluation IDs and the complete run/generation/candidate/instance/replicate/seed/result hierarchy; duplicate addresses fail closed and aggregates derive from trial records.
- R6: `TrustedFixtureRegistry` enforces fixture ID allowlisting, relative root-confined paths, schema/type, and exact SHA-256 before the dry-run file provider accepts an entry. The path remains read/parse-only.
- RED evidence: R5R-A 2 failed/1 passed; R5R-B 3 failed/3 passed; R5R-C 2 failed/6 passed, each failure attributable to its missing Required contract.
- Fresh GREEN: R5+R5R 26 passed; R2/R3 focused 19 passed; core non-provider 32 passed; compileall passed.
- Fresh disk reconstruction: 10 unique trial evaluations, 10 archive records, 1 validated elite retention event, 7 selection-trace entries, and per-candidate aggregates reconstructed.
- Static scan found no importlib, exec, subprocess, socket/network client, candidate-loader, or CandidateProxy capability in the R5R path.
- Protected hashes remain unchanged for R3 diagnostics and pilot receipt/prevalidator/path-validator modules.
- `R5_REPAIR_READY_FOR_REVIEW = TRUE`. This does not change `REAL_PROVIDER_GENERATION_READY`; Gate P2 remains OPEN, T6 remains NOT AUTHORIZED, and the next action is separately authorized R6 independent re-review.
