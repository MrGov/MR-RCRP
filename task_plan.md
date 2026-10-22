# 项目审查与后续工作计划

## 目标

在不修改项目代码、不运行耗时实验的前提下，完成项目结构与研究实现现状审查，形成可持续维护的事实记录、后续计划和进度日志。

## 当前阶段

Phase 6B-T4R RED-only 已获授权：仅新增 TOCTOU、record/header formal leakage、promotion 与 URI-like syntax 失败测试；生产实现保持只读。暂不进入 T5；Gate P2、真实 LLM/provider、pilot、正式/大规模/final-test 实验继续 blocked。

### Phase 6B-T1：Pilot receipt/manifest pure schema validators（GREEN）

- [x] Phase 6B-R 独立复审为 Approve（0 Critical、0 Required），允许请求首个 bounded implementation task。
- [x] 将本轮授权解释为上一轮建议的 PIV-01/receipt-schema RED-only 切片，不扩大到 GREEN 或 runner/provider execution。
- [x] 审查现有测试布局、schema/validator 模块与可复用 fixture 约定。
- [x] 只新增 manifest/validator/runner receipt schema fixtures 与失败测试。
- [x] 运行新增专项测试，确认因缺少 schema/validator 实现而 RED，且失败原因符合规格。
- [x] 更新 findings/progress，记录测试名称、失败原因与下一步 GREEN 边界。
- [x] 实现 `mrta_rect_coverage.experiments.pilot_contracts` 三个纯对象 schema validator。
- [x] 仅运行 `python -m pytest tests/test_pilot_contract_schema_red.py -q` 并取得 GREEN 证据。
- [x] 确认未引入 hash recomputation、path/file access、runner/provider/candidate/pilot execution。
- [x] 独立 implementation review：核对 pure-data 边界、tests/fixtures、requested/accepted、evidence、provider rejection、taxonomy scope 与 planning 状态。
- [x] **Required 1：** 以 TDD 补齐 manifest/validator-receipt/runner-receipt 的 exact enum、branch/state、requested↔accepted↔evidence 交叉一致性；real/unknown provider 的非拒绝 receipt 必须 fail closed（T1R 原定范围已关闭）。
- [x] **Required 2：** 增加能捕获上述旁路的 RED tests，包括 schema/version enum、valid/rejected branch required/nullability、rejected accepted-fields、evidence/top-level mismatch 与 summary object shape（T1R 原定范围已关闭）。

**范围锁：** RED 仅修改本任务 tests/fixtures；GREEN 仅新增 `src/mrta_rect_coverage/experiments/pilot_contracts.py` 并更新 planning files。始终不修改其他生产模块、`configs/`、`data/` 或协议正文；不运行 provider、candidate、pilot、benchmark、正式/大规模/final-test 实验；不调用真实 LLM。

**状态：** implementation review complete — Request changes（0 Critical、2 Required）；专项 53 passed、1 个既有 pyreadline warning。本阶段不是 Gate P2 closure，不允许进入 T2。

**RED API contract（历史）：** RED 冻结 module `mrta_rect_coverage.experiments.pilot_contracts` 及结构化 `valid`/`rejection_reasons` API；GREEN 已实现该模块。

**下一步：** 先执行 Phase 6B-T1R TDD RED/GREEN，关闭两个 Required 后再复审。仍不包含 raw-byte/hash recomputation、path/file access、manifest runner、provider/candidate/pilot execution。

### Phase 6B-T1R：Pilot contract schema bypass tests（RED only）

- [x] 增加 real/unknown provider 非拒绝分支、错误 reason 与 accepted-field 旁路测试。
- [x] 增加 preflight rejected/validated branch、required evidence/hash/scope 不变量测试。
- [x] 增加 top-level requested/accepted 与五类 evidence object 的一致性测试。
- [x] 增加 exact schema/version/objective/status enum 与 validation-receipt branch 测试。
- [x] 增加 `failure_summaries` / `output_paths` entry shape、unknown field、type/domain 测试。
- [x] 只运行 `python -m pytest tests/test_pilot_contract_schema_red.py -q`，确认预期 RED。
- [x] 更新 findings/progress 并确认生产文件未修改。

**合同冲突处理：** approved `preflight_validated` 是 inert pre-Gate receipt，必须保持 `accepted_execution=false`；请求中“false 应失败”与既有合法 fixture、规格和现有 `true` 应失败测试直接冲突，本轮不加入该矛盾断言。Validation receipt 使用现有 canonical `valid` / `rejected` status 名称。

**状态：** RED complete — 114 collected、49 expected failures、65 passed、1 个既有 warning；61 个新增 cases 中 49 个暴露 validator 旁路、12 个为既有 fail-closed 回归锚点。等待单独 GREEN 授权；不得进入 T2。

#### Phase 6B-T1R GREEN

- [x] 保持 `preflight_validated.accepted_execution=false`，收紧 validated/rejected/provider branch invariants。
- [x] 绑定 requested/accepted top-level fields 与五类 evidence objects。
- [x] 冻结 manifest/receipt/objective/scope/status enums 与 validation receipt invariants。
- [x] 严格校验 failure summary entries，并对未定义 output entry schema fail closed。
- [x] 只运行目标 pytest 文件并取得 114 项 GREEN 证据。
- [x] 确认未新增 I/O、hash recomputation、runner/provider/candidate/pilot execution。

**状态：** GREEN complete — `114 passed`、1 个既有 pyreadline warning；等待独立 implementation review。Inert preflight 不授权 execution，不关闭 Gate P2。

#### Phase 6B-T1R independent repair review

- [x] 只读审查 tests/fixtures、实现与 planning records，并确认 pure-data capability boundary。
- [x] fresh 运行唯一授权测试文件：114 passed、1 warning。
- [ ] **Required 1：** 当前阶段只允许 preflight receipt；删除/拒绝未实现的 `scheduled/running/completed/completed_with_failures/aborted/receipt_incomplete` branches，或为其增加当前不可满足的 fail-closed Gate P2 authority contract。先以 RED tests 证明这些状态不能携带 execution authorization。
- [ ] **Required 2：** 为每个 `preflight_rejected.rejection_reason` 冻结并测试 supporting evidence invariant；同时拒绝 validated evidence 内部自相矛盾（例如 final-test scope 已列入 loaded scopes 却声称 pass/absent）。

**状态：** Request changes（0 Critical、2 Required）；不得进入 T2。修复应继续 TDD，并保持 tests/implementation 为 pure-data，不实现 Gate P2 或 runner。

#### Phase 6B-T1R2 RED：non-preflight status and evidence semantics

- [x] 为所有 scheduled/running/completed 类状态增加 `accepted_execution=false/true` fail-closed tests；当前只允许两个 inert preflight statuses。
- [x] 为 real/unknown/glob/final-test/scope/provider-claim rejection reason 增加 supporting-evidence semantic tests。
- [x] 为 validated no-final-test/no-glob/no-real evidence 内部矛盾增加 fail-closed tests。
- [x] 只运行目标 pytest 文件，确认新增 tests 因现有 validator 语义不严格而 RED。
- [x] 更新 findings/progress，记录 collected/failed/passed 与生产代码未修改证据。

**范围锁：** 仅修改 `tests/test_pilot_contract_schema_red.py` 与三份 planning files；fixtures 仅在必要时新增，本轮预计复用现有 fixtures。禁止修改任何 `src/`、configs/data 或执行 provider/candidate/pilot/benchmark/final-test。

**状态：** RED complete — 153 collected、25 expected failures、128 passed、1 个既有 warning；等待单独 T1R2 GREEN 授权，不得进入 T2。

#### Phase 6B-T1R2 GREEN

- [x] Runner receipt status enum 仅保留 `preflight_validated` / `preflight_rejected`。
- [x] 将 rejection reasons 绑定到对应具名 evidence，无法表达的语义 fail closed。
- [x] 拒绝 validated no-final-test/no-glob/no-real/scope evidence 内部矛盾。
- [x] 仅运行目标 pytest 文件并取得 T1+T1R+T1R2 GREEN。
- [x] 确认未新增 path/hash/runner/provider/candidate/pilot capability，并更新 planning records。

**状态：** GREEN complete — 153 passed、1 个既有 warning；等待 independent implementation review。Inert preflight 仍不授权 execution、不关闭 Gate P2。

#### Phase 6B-T1R2 independent implementation repair review

- [x] 只读核对 pure-data capability boundary、preflight-only status、branch invariants、evidence consistency 与新增 RED coverage。
- [x] 仅运行授权测试文件：153 passed、1 个既有 pyreadline warning。
- [ ] **Required：** 移除 `_rejection_is_supported()` 对剩余 rejection reasons 的“任意 evidence reject”通用回退；`validation_receipt_invalid` 必须绑定 manifest/validation receipt evidence，`runtime_authorization_denied` 在缺专用 runtime-authority evidence 时必须 fail closed。新增“无关 evidence=reject 不能支持 reason”的 RED 回归，并调整现有正例合同。

**状态：** Request changes（0 Critical、1 Required）；暂不允许进入 T2。Gate P2、provider/pilot/formal/large-scale/final-test gates 均未关闭。

#### Phase 6B-T1R3 RED：rejection reason semantic support

- [x] 将 `validation_receipt_invalid` 的无关-evidence reject 旁路冻结为失败测试。
- [x] 将当前无专用 evidence 的 `runtime_authorization_denied` 正例改为 fail-closed 负例。
- [x] 覆盖每个保留 rejection reason 只能由专属 predicate 支持。
- [x] 仅运行目标 pytest 文件并确认新增失败来自当前通用回退，不修改生产代码。

**状态：** RED complete — 164 collected、7 expected failures、157 passed、1 个既有 warning；等待单独 T1R3 GREEN 授权。T2、Gate P2、provider/pilot/formal/large-scale/final-test gates 继续 blocked。

#### Phase 6B-T1R3 GREEN：strict rejection support predicates

- [x] 当前 enum 仅保留能由现有 evidence schema 明确证明的 rejection reasons。
- [x] 删除任意 evidence reject 通用回退，所有无 predicate reasons fail closed。
- [x] 保持 preflight-only、accepted_execution=false 与 pure-data capability boundary。
- [ ] 解决本轮 OR 规格与既有 glob predicate tests 的直接冲突后，再完成目标 pytest 验证。

**状态：** blocked pending contract clarification — 当前实现按新规格使用 `(glob mode) OR (glob_detected=true)`，但两个既有测试要求 AND；2 failed、162 passed。未修改 tests/fixtures；不进入 T2，不关闭 Gate P2。

#### Phase 6B-T1R3 GREEN implementation repair review

- [x] 只读审查 pure-data boundary、reason enum、专属 predicates、preflight branch 与 T1R3 regression coverage。
- [x] Fresh 运行唯一授权目标测试文件。
- [ ] **Required：** 解决 glob support predicate 的 OR/AND 合同冲突；当前实现 OR 与既有两个 AND regression tests 不一致，目标套件仍 2 failed。保持测试不变时应将 predicate 收紧为 AND，并复审。

**状态：** Request changes（0 Critical、1 Required）；2 failed、162 passed、1 warning。暂不允许 T2；Gate P2 与所有 provider/pilot/formal/final-test gates 未关闭。

#### Phase 6B-T1R3-FIX：uncontrolled glob predicate alignment

- [x] 沿用既有两个失败回归作为 RED 证据，不修改测试、fixtures 或协议正文。
- [x] 将 `uncontrolled_glob_forbidden` 的支持条件从 `(glob mode) OR (glob_detected)` 收紧为两项同时成立，并保留 accepted-input-null 与 reject-decision 条件。
- [x] 仅运行授权的目标 pytest 文件，确认 T1/T1R/T1R2/T1R3 合同全部通过：164 passed、1 个既有 warning。
- [x] 更新 findings/progress 并提交独立 implementation review；不自动进入 T2。

**状态：** GREEN complete — 164 passed、1 个既有 warning；建议进入独立 T1R3-FIX implementation review。T2、Gate P2 与所有 provider/pilot/formal/large-scale/final-test gates 保持未关闭。

#### Phase 6B-T1R3-FIX narrow implementation review

- [x] Tests-first 核对两个单项 glob evidence 旁路与 decision 非 reject 负例。
- [x] 核对 AND predicate、accepted-input-null、reason-specific evidence 与 unsupported-reason fail-closed 行为。
- [x] 核对 preflight-only status、`accepted_execution=False` 和 pure-data capability boundary。
- [x] Fresh 运行唯一授权目标测试：164 passed、1 个既有 warning。
- [x] 按 Critical / Required / Consider / FYI 形成 verdict；不自动进入 T2 或关闭任何 execution gate。

**状态：** Approve（0 Critical、0 Required）；允许下一步单独授权 Phase 6B-T2 PIV-02 scoped-hash verification RED-only。Gate P2 与真实 LLM/provider、pilot、正式/大规模/final-test 实验仍 blocked。

#### Phase 6B-T2 RED：PIV-02 scoped-hash verification contracts

- [x] 读取用户批准的 RED-only 合同并核对现有 PIV-02、manifest/validator/runner receipt hash 规格。
- [x] 冻结测试边界：仅新增 `tests/test_pilot_scoped_hash_red.py`，全部使用内存 JSON objects/bytes，不创建或读取数据文件。
- [x] 为 canonical JSON、SHA-256 格式与非 JSON/非有限值拒绝编写 RED tests。
- [x] 为 pilot matrix/rule scope、non-promotion 与 formal/final-test marker 拒绝编写 RED tests。
- [x] 为 manifest→validator receipt→runner receipt 的非自引用 ID/evidence binding 编写 RED tests。
- [x] 为 explicit-content-only/no implicit file access 编写 RED tests。
- [x] 仅运行 `python -m pytest tests/test_pilot_scoped_hash_red.py -q`：59 collected、59 expected failures、1 个既有 warning；失败均来自目标模块尚未实现。
- [x] 更新 findings/progress；本轮不实现 GREEN，不自动关闭 Gate P2。

**状态：** RED complete — 59 failed、0 passed、1 个既有 warning；collection 正常。等待单独 T2 GREEN 授权，生产代码与所有执行 gate 未改变。

#### Phase 6B-T2 GREEN：PIV-02 pure in-memory integrity implementation

- [x] 恢复 59-case RED 证据并读取 GREEN 授权、完整目标测试和 package 边界。
- [x] 冻结最小实现：独立 `pilot_integrity.py`、不可变 validation result、严格 JSON canonicalization、显式 bytes/object hashing、scoped/receipt binding。
- [x] 实现测试要求的纯内存 API；不修改 `pilot_contracts.py` 或测试。
- [x] 运行 `python -m pytest tests/test_pilot_scoped_hash_red.py -q`：59 passed、1 个既有 warning；首次即全绿，无失败修补。
- [x] 选择性运行 T1+T2 两文件联合回归：223 passed、1 个既有 warning；未运行完整 pytest。
- [x] 更新 findings/progress 并提交独立 GREEN review；不关闭 Gate P2。

**状态：** GREEN complete — T2 59 passed；T1+T2 223 passed；均只有 1 个既有 warning。建议进入独立 T2 GREEN review；Gate P2 与所有执行禁令保持。

#### Phase 6B-T2 GREEN independent implementation review（2026-08-13）

- [x] 只读审查 `pilot_integrity.py`、T2 tests、`pilot_contracts.py` 修改证据与 planning records。
- [x] 确认 pure in-memory capability boundary；无 file/path identity、runner/provider/candidate/pilot execution。
- [x] 运行唯一授权 T2 专项：59 passed、1 个既有 warning。
- [x] 运行授权 T1+T2 联合回归：223 passed、1 个既有 warning。
- [ ] **Required 1：** 增加 RED 覆盖并拒绝 pilot manifest record/header 内 `formal_train` / `formal_dev` 引用；不能只检测 `final_test` marker。
- [ ] **Required 2：** 以独立 RFC 8785/JCS conformance vectors 冻结 canonicalization，或明确版本化并批准不同的 canonical JSON 算法；测试 oracle 不得复制被测 `json.dumps` 规则作为唯一证据。
- [ ] **Required 3：** cross-receipt binding 必须独立拒绝缺失/非法 `manifest_hash`，不能让 validator/runner/evidence 三处 `None` 或同一非法值因相等而通过。
- [ ] 完成 T2R RED→GREEN→review 后才评估 T3；不得用当前 223-pass 关闭未覆盖合同。

**状态：** Request changes（0 Critical、3 Required）；暂不允许进入 Phase 6B-T3。Gate P2、真实 LLM/provider、pilot、正式/大规模/final-test 实验继续 blocked。

#### Phase 6B-T2R RED-only：scoped-hash integrity gap tests（2026-08-13）

- [x] 恢复 T2 review 的 3 个 Required 与执行禁令。
- [x] **Required 1 RED：** 为 pilot 顶层/嵌套 scope 语义中的 `formal_train`、`formal_dev`、`formal_final_test` 增加 fail-closed tests；复用已有 matrix/formal top-level controls。
- [x] **Required 2 RED：** 增加手写 RFC 8785/JCS canonical bytes vectors，覆盖 key ordering、nested ordering、number formatting、UTF-8/control escaping 与 non-finite rejection。
- [x] **Required 3 RED：** 增加 cross-receipt missing/null/empty/malformed/uppercase/wrong-length `manifest_hash` 与 validation receipt ID evidence tests。
- [x] 仅运行 `python -m pytest tests/test_pilot_scoped_hash_red.py -q`：89 collected、13 failed、76 passed、1 warning；失败均命中三个目标缺口。
- [x] 更新 findings/progress 并保持 production/docs/configs/data 不变；不进入 T3。

**状态：** RED complete — 89 collected、13 expected failures、76 passed、1 个既有 warning；等待单独 T2R GREEN 授权。Gate P2 与真实 LLM/provider、pilot、正式/大规模/final-test gates 均 blocked。

#### Phase 6B-T2R GREEN：scoped-hash integrity fixes（2026-08-13）

- [x] 恢复 13 个 RED failures，并完成 root-cause tracing。
- [x] **Required 1 GREEN：** 递归拒绝 pilot manifest 中 `formal_train`、`formal_dev`、`formal_final_test` 以及 semantic `matrix_scope=formal`，仅检查显式内存对象。
- [x] **Required 2 GREEN：** 用标准库实现最小 RFC 8785/JCS serializer，覆盖 strict JSON domain、UTF-16 key ordering、UTF-8 strings 与 ECMAScript/JCS number formatting vectors。
- [x] **Required 3 GREEN：** runner/validator/evidence cross binding 在 equality 前逐项校验 lowercase 64-hex hash/id，缺证据即 fail closed。
- [x] T2/T2R 目标测试：89 passed、1 个既有 warning；13 个 RED 全部转绿。
- [x] 授权 T1+T2 联合回归：253 passed、1 个既有 warning。
- [x] 更新 planning records；确认 `pilot_contracts.py`、tests/docs/configs/data 未修改，不关闭 Gate P2。

**状态：** GREEN complete — 89/89 T2、253/253 T1+T2；等待独立 T2R implementation review。Gate P2 与所有执行禁令保持。

#### Phase 6B-T2R GREEN independent implementation review（2026-08-14）

- [x] 恢复 GREEN/RED/planning 证据并锁定只读 review 范围。
- [x] Tests-first 核对 formal scope、独立 JCS vectors、cross-receipt invalid hash/id、explicit-content-only cases。
- [x] 审查 `pilot_integrity.py` 的 correctness/readability/architecture/security/performance 与 RFC 8785 口径。
- [x] 通过时间戳、文件大小、静态能力边界与既有 planning evidence 确认 `pilot_contracts.py` 未被 T2R GREEN 修改；工作区无 Git 元数据，不能提供 commit diff 证据。
- [x] 运行授权 T2 专项：89 passed、1 个既有 warning；运行 T1+T2 联合回归：253 passed、1 个既有 warning；未运行完整 pytest。
- [x] 按 Critical / Required / Consider / FYI 形成 T3 准入 verdict 并更新 findings/progress。
- [ ] **Required：** `canonical_json_bytes()` 当前接受任意 Python `int` 并直接 `str(value)`，但模块声明 RFC 8785/JCS；RFC 8785 要求 JSON number 适配 IEEE-754 double 并按 ECMAScript 序列化，官方 `2**68` 样例不是精确整数十进制。先增加官方 Appendix B / integer-domain RED tests，再选择拒绝超域整数或按明确的 binary64 语义处理并复审。

**状态：** Request changes（0 Critical、1 Required）；暂不允许进入 Phase 6B-T3。建议下一步为 T2R2 RFC 8785 integer-domain/Appendix-B RED-only，而不是直接开始 manifest validator integration。Gate P2 与所有执行禁令保持。

#### Phase 6B-T2R2 RED-only：RFC 8785 integer-domain and Appendix-B tests（2026-08-14）

- [x] 恢复 T2R review、测试布局与纯内存边界。
- [x] 冻结保守 integer policy：Python `int` 仅允许 ECMAScript safe-integer domain `[-(2**53-1), 2**53-1]`；域外整数拒绝，不做隐式 binary64 coercion。
- [x] 增加 safe-boundary acceptance、just-outside rejection、`2**68`/任意精度整数 rejection 与嵌套域外整数测试。
- [x] 增加以 IEEE-754 bit pattern 构造的 18 个 RFC 8785 Appendix B 浮点边界向量，证明 float 路径与 Python-int 拒绝策略分离。
- [x] 仅运行 `python -m pytest tests/test_pilot_scoped_hash_red.py -q`：118 collected、8 expected failures、110 passed、1 个既有 warning；失败均为当前 arbitrary-precision int 旁路。
- [x] 更新 findings/progress；确认未修改任何 `src/`、fixtures/docs/configs/data，未运行或接触任何 provider/pilot/final-test。

**状态：** RED complete；等待单独 T2R2 GREEN 授权，不进入 T3，不关闭 Gate P2。

#### Phase 6B-T2R2 GREEN：RFC 8785 integer-domain fail-closed fix（2026-08-14）

- [x] 恢复 8 个 genuine RED failures、safe-domain 合同与授权边界。
- [x] 定位单一根因：`_validate_json_value()` 将所有 Python `int` 无条件视为有效，后续 serializer 因而输出 arbitrary-precision decimal。
- [x] 在递归 JSON-domain validation 中加入 `[-(2**53-1), 2**53-1]` 检查，不做 float coercion/truncation。
- [x] 将 canonicalization version 更新为 `jcs-v1-safe-int-domain`，保留 `RFC8785-JCS` algorithm 标识。
- [x] 运行授权 T2 专项：118 passed、1 个既有 warning；运行 T1+T2 联合回归：282 passed、1 个既有 warning；未运行完整 pytest。
- [x] 更新 findings/progress，确认 `pilot_contracts.py`、tests/docs/configs/data 与执行能力边界未改变。

**状态：** GREEN complete；建议进入独立 T2R2 implementation review，不进入 T3，不关闭 Gate P2。

#### Phase 6B-T2R2 GREEN independent implementation review（2026-08-14）

- [x] 恢复 RED/GREEN 测试、实现和 planning evidence，锁定只读 review 范围。
- [x] Tests-first 核对 safe integer、嵌套拒绝和 18 个 Appendix B vectors。
- [x] 核对 object/receipt hash 与 runner binding：实现调用链继承 fail-closed，但对应 direct regression coverage 与声称不一致。
- [x] 核对 pure in-memory、scope、hash/id、evidence、explicit-content 和 `pilot_contracts.py` unchanged boundary。
- [x] fresh 运行授权 T2 专项：118 passed、1 warning；运行 T1+T2 联合回归：282 passed、1 warning；未运行完整 pytest。
- [x] 按 Critical / Required / Consider / FYI 形成 T3 准入 verdict，并更新 findings/progress。
- [x] **Required：** 增加直接 tests，证明 unsupported int 不能进入 `compute_object_hash()`、validation/runner receipt ID preimage，且 `verify_runner_receipt_binding()` 返回结构化 invalid；同时冻结 `CANONICALIZATION_ALGORITHM == "RFC8785-JCS"` 和 `jcs-v1-safe-int-domain`。新增 19 cases 直接通过，作为 coverage-only closure，未修改生产实现。

**状态：** Request changes（0 Critical、1 Required）；暂不允许 T3。建议下一步为 T2R3 hash/receipt/version evidence RED-only；Gate P2 与所有执行禁令保持。

#### Phase 6B-T2R3：hash/receipt/version evidence coverage tests（2026-08-14）

- [x] 恢复 T2R2 review Required、现有 receipt fixtures/helpers 与 coverage-only 规则。
- [x] 直接测试 `compute_object_hash()` 对 object/list/nested unsupported int 的拒绝，并证明 digest 未开始。
- [x] 直接测试 validation receipt ID 和 runner receipt ID preimage 中 unsupported int 的拒绝，覆盖五个 evidence objects 与 adjacent fields。
- [x] 直接测试 `verify_runner_receipt_binding()` 对 validator/runner/evidence unsupported int 的结构化 invalid，且无需 schema validator 前置。
- [x] 冻结 `CANONICALIZATION_ALGORITHM` 和 safe-int-aware version。
- [x] 仅运行授权 T2 专项并运行 T1+T2 联合回归；结果分别为 137 passed 与 301 passed，均 1 个既有 warning；未运行完整 pytest。
- [x] 更新 findings/progress 并以 SHA-256 确认两份 production modules 未修改；提交独立 T2R3 review，不进入 T3。

**状态：** coverage-only closure complete，等待独立 T2R3 review；无 GREEN 生产修改。Gate P2 与所有执行禁令保持。

#### Phase 6B-T3：pure-object pilot manifest pre-validator/core（RED→GREEN，2026-08-14）

- [x] T2R3 independent review 为 Approve（0 Critical、0 Required），仅授权进入 T3 RED-only。
- [x] 读取 T3 附件授权并锁定 production、provider、runner、pilot、final-test 禁区。
- [x] 恢复 schema、integrity、receipt 与 manifest-validator 协议合同；发现 object-only API/无 I/O 与现有唯一 raw-bytes/path validator 合同冲突，且 `validation_valid` 与批准的 `valid` status 冲突。
- [x] 用户确认将 T3 收窄为独立 pure-object pre-validator/core；full raw-bytes/path validator、正式 receipt 与 I/O 验证留待后续授权，status 仅用 `valid/rejected`。
- [x] 新增 `tests/test_pilot_manifest_prevalidator_core_red.py`，覆盖 schema→integrity 短路顺序、双层负例、happy path、object binding、explicit-content-only、non-impersonation 与 no-execution 语义。
- [x] 仅运行 T3 目标测试：29 collected、28 expected failures、1 baseline pass、1 warning；失败均来自目标模块未实现。授权 T1+T2 回归为 301 passed、1 warning。
- [x] 更新 findings/progress，以 SHA-256 确认 `pilot_contracts.py` / `pilot_integrity.py` 未变化并提交单独 T3 GREEN 授权请求。
- [x] 在单独 GREEN 授权下只新增 `pilot_manifest_prevalidator.py`，组合既有 schema 与 scoped-integrity 纯对象检查。
- [x] 固定 schema-first 短路、`valid/rejected`、`pure_object_prevalidation`、object-hash binding 和非自引用 `prevalidation_result_id`。
- [x] 明确禁止 full receipt 字段、execution authorization 与 Gate P2 closure；未加入 raw bytes、path/file、runner/provider/candidate/pilot 能力。
- [x] 仅运行 T3 专项与获准的 T1+T2+T3 回归，分别为 29 passed 与 330 passed（各 1 个既有 warning）。
- [x] 执行独立 Phase 6B-T3 implementation review；结论为 Request changes，修复前不进入下一实现任务。

**状态：** GREEN complete；pure-object core 已实现，full validator 仍未实现。独立 review 为 Request changes（0 Critical、1 Required）；Gate P2 不关闭。

#### Phase 6B-T3 independent implementation review（2026-08-15）

- [x] Tests-first 核对 schema→integrity 顺序、短路、状态、object hash、非 receipt 语义、后置变更与 no-I/O/no-execution tests。
- [x] 逐行审查 prevalidator，并静态核对 contracts/integrity 依赖方向与能力边界。
- [x] Fresh 运行 T3 专项：29 passed、1 个既有 warning。
- [x] Fresh 运行获准的 T1+T2+T3 回归：330 passed、1 个既有 warning；未运行完整 pytest。
- [x] **Required：** rejected prevalidation result 必须绑定其输入对象，或明确标记为不可验证并使 binding verification fail closed（T3R GREEN 已关闭）。
- [x] **Consider：** schema/integrity/result hashing 使用单一入口快照并检测 validator 期间 mutation（T3R GREEN 已采纳）。

**状态：** Request changes（0 Critical、1 Required）；不得进入 T4。建议下一步为 T3R RED-only object-binding/snapshot tests，不扩大到 full validator 或 I/O。

#### Phase 6B-T3R RED-only：rejected-input binding and snapshot consistency（2026-08-15）

- [x] 恢复 T3 review 的 1 个 Required 与 snapshot Consider，并锁定 tests/planning-only 写入范围。
- [x] 增加 schema-rejected 不同 manifest 同 rejection summary 不得互换 result 的测试。
- [x] 增加 integrity-rejected 不同 manifest、family matrix、split rule 不得互换 result 的测试。
- [x] 要求 canonicalizable rejected inputs 保存三个 lowercase object hashes，并由 `prevalidation_result_id` 覆盖。
- [x] 要求 non-canonicalizable rejected inputs 显式 `binding_available=false`/reason，且 verifier 不得返回 valid。
- [x] 以 monkeypatch 覆盖 schema 后与 integrity 后的 mid-build manifest mutation：必须使用入口快照或结构化拒绝。
- [x] 仅运行 T3 目标测试：46 collected、14 expected failures、32 passed、1 个既有 warning；无 collection/syntax/fixture 错误。
- [x] 运行授权的 T1+T2+T3 组合回归：347 collected、14 expected failures、333 passed、1 个既有 warning；失败集合仅为新增 T3R cases。
- [x] 在单独授权下仅修改 `pilot_manifest_prevalidator.py`，实现 canonical rejected binding、noncanonical unavailable 状态与入口 snapshot/mutation detection。
- [x] T3/T3R 专项：46 passed、1 个既有 warning；14 个 RED 全部转绿。
- [x] T1+T2+T3 回归：347 passed、1 个既有 warning；未运行完整 pytest。
- [x] 执行独立 T3R implementation review；结论 Approve（0 Critical、0 Required）。

**状态：** GREEN + independent review complete；允许下一步单独授权 T4 RED-only。仅 prevalidator production 文件变化；Gate P2 不关闭。

#### Phase 6B-T3R independent implementation review（2026-08-15）

- [x] Tests-first 复核 rejected schema/integrity binding、noncanonical fail-closed 与 mutation controls。
- [x] 确认 canonical rejected result 的三个 object hashes 被纳入非自引用 result ID，并且不能跨 invalid object replay。
- [x] 确认 binding-unavailable result 无可复用 result ID，verifier 一律 fail closed。
- [x] 确认入口 deep-copy snapshot、validator 后 mutation detection 与 result reconstruction 保持同一对象绑定语义。
- [x] 静态确认无 file/path/raw-bytes/full-validator/runner/provider/candidate/pilot capability；`pilot_contracts.py` 与 `pilot_integrity.py` 哈希未变。
- [x] Fresh 运行授权 T3 专项：46 passed、1 个既有 warning；授权 T1+T2+T3 回归：347 passed、1 个既有 warning。
- [ ] **Consider：** 在未来将 core 暴露给更宽泛调用者前，对 `deepcopy`/cyclic/non-JSON custom object 异常做结构化 `binding_unavailable`，或在 snapshot 前收紧为 strict JSON builtins。
- [ ] **Consider：** 在 prevalidation result 持久化或进入 I/O integration 前，评估是否将新增 binding fields 对应的 schema version 从 `pilot-prevalidation-core-v1` 显式升版。

**状态：** Approve（0 Critical、0 Required）。可单独授权 T4；建议最小 T4 为 PIV-03 controlled path/duplicate boundary 的 RED-only tests，不实现 runner/provider/pilot，不关闭 Gate P2。

#### Phase 6B-T4 RED-only：PIV-03 controlled path and duplicate boundary（2026-08-15）

- [x] 确认 T3R 独立 review 已 Approve，恢复 Gate P2 与全部执行禁令。
- [x] 核对附件与 `pilot_manifest_validator_spec.md` / PIV-03，无合同冲突。
- [x] 仅新增 `tests/test_pilot_path_duplicate_boundary_red.py`，使用 pytest `tmp_path` 构造 pilot-only 文件/目录/link fixtures。
- [x] 覆盖 approved-root confinement、symlink/reparse、hardlink/file identity、duplicate identities、pilot/formal leakage、explicit no-glob 与 no-execution 语义。
- [x] 仅运行最终 T4 目标 pytest：44 collected、40 expected failures、4 symlink capability skips、1 个既有 warning；失败均因 `pilot_path_validator` 未实现。
- [x] 运行授权 T1+T2+T3 回归：347 passed、1 个既有 warning；未运行完整 pytest。
- [x] 记录 production hashes 不变、无 data/final-test 访问、无 provider/candidate/pilot/benchmark 执行。

**状态：** RED complete；44 collected、40 expected failures、4 capability skips；T1+T2+T3 回归 347 passed。生产代码未修改，path validator 未实现。T4 GREEN 需单独授权，Gate P2 不关闭。

#### Phase 6B-T4 GREEN：controlled path and duplicate validator（2026-08-17）

- [x] 恢复 40-failure RED 证据与 4 个平台 symlink skips，读取完整 GREEN 授权。
- [x] 冻结最小范围：只新增 `pilot_path_validator.py` 和 planning records，不修改 tests/contracts/integrity/prevalidator。
- [x] 实现 approved-root confinement、explicit-file validation、symlink/reparse fail-closed 与 content-hash verification。
- [x] 实现 duplicate instance/hash/canonical-path/file-identity/family-split/generation-identity 检测。
- [x] 实现 pilot-only scope/formal-marker/no-glob/no-discovery 与 inert result 语义。
- [x] 运行 T4 目标 pytest，取得 40 passed、4 个平台性 symlink skips、1 个既有 warning。
- [x] 运行授权 T1+T2+T3+T4 回归：387 passed、4 skipped、1 个既有 warning；未运行完整 pytest。
- [x] 核对修改范围、production hashes 与 no-provider/no-data/no-final-test 边界。

**状态：** GREEN complete；等待独立 Phase 6B-T4 implementation review。Gate P2 不关闭，所有 execution/formal/final-test 禁令保持。

#### Phase 6B-T4 independent implementation review（2026-08-17）

- [x] Tests-first 审查 approved-root、链接、duplicate、formal marker、no-discovery 与 inert-result 合同。
- [x] 审查 `pilot_path_validator.py` 的 correctness/readability/architecture/security/performance 和 PIV-03 规格一致性。
- [x] 以 SHA-256 核对 `pilot_contracts.py`、`pilot_integrity.py`、`pilot_manifest_prevalidator.py` 未被 T4 修改。
- [x] Fresh 运行授权 T4 专项：40 passed、4 skipped、1 个既有 warning。
- [x] Fresh 运行授权 T1+T2+T3+T4 回归：387 passed、4 skipped、1 个既有 warning；未运行完整 pytest。
- [ ] **Required 1 — stable path/file binding：** 增加 RED 覆盖并消除 link/rename replacement TOCTOU；当前 link check、resolve、`is_file`、`stat`、`open/read` 分离，不能证明读取的是同一个已验证且仍位于 approved root 的文件。
- [ ] **Required 2 — record/header formal leakage：** 增加 RED 覆盖并拒绝 record-level `split=formal_train/formal_dev/formal_final_test`、其他 scope/header 引用及不安全 promotion/URI syntax；当前只检查 top-level scope、file path 和部分 lockbox marker。

**状态：** Request changes（0 Critical、2 Required）；Phase 6B-T5 暂不允许。建议下一步为 bounded Phase 6B-T4R RED-only tests，再做最小 GREEN 与独立复审。Gate P2 与所有 execution/formal/final-test 禁令保持。

#### Phase 6B-T4R RED-only：TOCTOU and formal-leakage boundary tests（2026-08-17）

- [x] 读取完整 RED-only 授权并确认与 PIV-03/现有 review findings 无合同冲突。
- [x] 增加 regular content replacement、rename/swap、symlink swap 和 post-read identity change RED tests。
- [x] 增加 record/header/nested formal split/scope 与 artifact promotion RED tests。
- [x] 增加 URI/UNC syntax 及 ID/hash/meta 中 formal/final-test marker RED tests。
- [x] 仅运行 T4 目标 pytest：89 collected、44 expected failures、40 passed、5 capability skips、1 warning。
- [x] 运行授权 T1+T2+T3+T4 联合回归：44 expected failures、387 passed、5 skipped、1 warning；未运行完整 pytest。
- [x] 核对 production hashes 未变并更新 findings/progress。

**范围锁：** 仅修改 `tests/test_pilot_path_duplicate_boundary_red.py` 与三份 planning files；不修改任何 `src/`、docs/configs/data，不运行 provider/candidate/pilot/benchmark，不扫描项目 data 或接触真实 final-test。

**状态：** RED complete；44 个失败均命中 TOCTOU/formal-promotion/URI-marker 旁路，5 个 skip 均为 Windows symlink capability。等待单独 T4R GREEN 授权；T5 和 Gate P2 保持 blocked。

### Phase 6B-RR：Implementation-planning protocol repair

- [x] 恢复 0 Critical / 4 Required review 状态并读取正式修订合同。
- [x] 恢复 execution/contract/feasibility/optimization/structural candidate taxonomy。
- [x] 冻结 requested/accepted receipt schema、具名 evidence objects 与无自引用 canonical receipt IDs。
- [x] 增加 real/unknown/mismatched provider 专门拒绝场景。
- [x] 同步 Gate P1/P2/implementation authorization/Gate B 生命周期。
- [x] 同步 Consider、planning records 并执行只读文档合同核验。

**状态：** documentation repair complete；45/45 document-contract checks PASS；等待独立 Phase 6B-R planning review，不自动进入 implementation authorization。

**范围锁：** 只修改用户列出的规划 Markdown 与三份 planning files；不修改 `src/`、`configs/`、`data/`、`tests/`，不运行测试/provider/pilot/实验。

### Phase 6B-R：Independent implementation-planning review

- [x] 恢复 planning 状态并确认 review-only 范围。
- [x] 审查 Phase 6B planning-only 与所有 execution/final-test 禁令。
- [x] 审查三层 observability ownership、状态 taxonomy 和 failure-zero accounting。
- [x] 审查 validator/runner receipt 的 strict schema、hash/path/scope/duplicate 与拒绝证据。
- [x] 审查 13-case mock/file plan、pre/post-Gate 非循环授权和 Gate P2 evidence。
- [x] 按 Critical / Required / Consider / FYI 给出 implementation-task authorization verdict。
- [x] 只更新 planning review records；不修改受审正文或运行测试/provider/pilot。

**状态：** complete — Request changes（0 Critical、4 Required groups）。

#### Implementation-task authorization 前必须关闭

- [x] **Required 1 — failure taxonomy：** candidate schema 将 execution、contract、feasibility、optimization、structural 分轴；`invalid_solution` 已移出 execution status，跨轴 invariants 与 test expectations 已同步（documentation repaired；awaiting review）。
- [x] **Required 2 — receipt schema：** requested/accepted schema、五个具名 evidence objects、rejection enum 与 runner/validator canonical IDs 已冻结（documentation repaired；awaiting review）。
- [x] **Required 3 — real-provider negative coverage：** T14–T17 已覆盖 real、unknown 和 provider mismatch 两方向，并要求 invocation/import/call proof 为零（documentation repaired；awaiting review）。
- [x] **Required 4 — lifecycle state：** Gate P1/P2、Phase 6A/6B-R、implementation authorization、Gate B 与 next action 已同步；所有 Gate P2 checkbox 继续 open（documentation repaired；awaiting review）。
- [x] 修订后再次独立复审；结论 Approve（0 Critical、0 Required），允许单独请求 bounded implementation task authorization。

**范围锁：** 不修改受审规格、算法代码、配置、数据或测试；不运行测试、provider、pilot、真实 LLM 或实验。

### Phase 6A-R：Independent planning review

- [x] 恢复 planning 状态并确认 review-only 权限。
- [x] 审查 planning-only、provider/pilot/formal/final-test 禁令。
- [x] 审查 pilot/formal manifest identity 与 non-promotion 边界。
- [x] 审查 mock/file case coverage、eligibility、freeze、deployment、fallback 和 attribution。
- [x] 审查 observability、scheduled-run accounting、failure-zero 与 Gate P2 条件。
- [x] 核对 Phase 6A/6B/6C/7 分层，形成 Critical / Required / Consider / FYI verdict。
- [x] 仅更新 planning review records；不运行测试/provider/pilot/实验。

**状态：** complete — Approve；0 Critical、0 Required，11/11 文档审查控制 PASS。Phase 6B implementation planning 可在单独授权后进入，但 Gate P2 仍未关闭。

**范围锁：** 不修改算法代码或五份受审规划正文；不运行测试、provider、pilot、真实 LLM 或实验。

### Phase 6A：Mock/file closed-loop planning

- [x] 读取 Phase 6A 附件规格并恢复 planning 状态。
- [x] 定义 Phase 6A planning-only 权限边界和 Phase 6B/6C/7 分层。
- [x] 规划 pilot-only manifest、scope-aware hashes 与不可提升合同。
- [x] 规划 mock/file legal、invalid、unsafe、deployment-blocked 闭环。
- [x] 规划 execution/selection/freeze/deployment/attribution 与 failure-zero observability。
- [x] 规划 Gate P2 的执行前条件，不关闭或执行 Gate P2。
- [x] 更新 findings/progress 并做文档级一致性自审；不运行任何测试、provider 或实验。

**状态：** complete（documentation planning only）；下一步是 Phase 6A planning review，不自动进入 Phase 6B/Gate P2。

**范围锁：** 只创建/更新用户指定的 Phase 6A 文档与三份 planning 文件；不修改 `src/`、`configs/`、`data/`、`tests/`，不运行 mock/file/真实 provider，不执行 pilot，不接触 final-test。

### Phase 6B：Pilot infrastructure implementation planning

- [x] 将 strict pilot manifest validator 拆成后续 TDD tasks。
- [x] 规划 pilot manifest generator/fixtures 与 pilot-artifact exclusion receipt。
- [x] 规划 manifest-only pilot runner 和 uncontrolled-glob rejection。
- [x] 规划 scheduled-run registry、failure-zero accounting 与 batch-inconclusive handling。
- [x] 规划 mock/file candidate fixture layout 和 deterministic identities/hashes。
- [x] 规划 observability schema、event log、result rows 与 replay checks。
- [x] 形成 implementation review/Gate P2 evidence package；不得执行 provider/pilot。

**状态：** protocol revision submitted；等待独立 Phase 6B-R planning review。不得自动进入 implementation、Gate P2 或 Phase 6C。

**范围锁：** 不修改 `src/`、`configs/`、`data/`、`tests/`；不运行 pytest、mock/file/真实 provider、pilot 或实验；不创建、读取或推断 final-test artifact。

### Phase 6C：Pilot execution after Gate P2（未授权）

- [ ] 仅在 Gate P2 通过后运行 approved mock-provider pilot。
- [ ] 运行 file-provider legal candidate pilot。
- [ ] 运行 file-provider invalid/contract-violation pilot。
- [ ] 验证 unsafe candidate 在执行前被拒绝。
- [ ] 验证 frozen deployment runtime-authorization block/fallback/non-attribution。
- [ ] 审查 scheduled-run/failure-zero/observability evidence 并作 no-go decision。

**状态：** blocked by Gate P2；当前禁止执行。

### Phase 7：Real LLM preflight（未授权）

- [ ] 仅在 Phase 6 review 后规划 real-provider train/dev-only preflight。
- [ ] 要求 explicit risk acknowledgement、runtime authorization 与 provider provenance policy。
- [ ] 保持 final-test 不可见、不可访问、不可反馈。
- [ ] 明确当前仍是 timeout-only subprocess；若无外部 capability sandbox，不得过度声明隔离。

**状态：** blocked；真实 LLM/provider 当前禁止。

### Phase 5B-R4-R：Research-protocol independent review

- [x] 恢复 planning 状态并确认 review-only 范围。
- [x] 逐项核对 pilot-only matrix/rule、scope-aware hashes 与 manifest/matrix scopes。
- [x] 核对 pilot artifact promotion prohibition 与 formal joint-preflight exclusion。
- [x] 交叉核对 experiment/manifest/lockbox/instance/pilot/no-go 生命周期与 gate 权限。
- [x] 执行只读 review matrix；按 Critical / Required / Consider / FYI 形成 verdict。
- [x] 仅更新 planning review records；不修改协议正文，不运行测试/实验/provider。

**状态：** complete — Approve；16/16 review controls PASS，0 Critical、0 Required。Phase 6A 仅 planning-entry allowed；Gate P2、Gate B 与 real-provider gates 未关闭。

**范围锁：** 不修改协议正文、算法代码、配置、数据或测试；不运行测试、实验、solver 或 provider。

### Phase 5B-R4：Pilot/formal family-matrix lifecycle alignment

- [x] 恢复 planning 状态并读取 Phase 5B-R3 independent-review Required。
- [x] 冻结设计：pilot-only 与 formal 是两个不可提升、不可混用的 artifact identity domains。
- [x] 在 experiment/instance/pilot/lockbox 文档中统一 pilot→formal 顺序与 formal-generation freeze boundary。
- [x] 在 manifest schema 中加入 scope、scoped matrix/rule hash、promotion prohibition 与 identity fields。
- [x] 规定 formal joint preflight 拒绝 pilot hash/path/file identity/family identity 泄漏。
- [x] 将 Gate P 拆为 Phase 6A planning-entry gate 与 pilot-execution gate；Gate B 保持独立且关闭。
- [x] 同步 reproducibility checklist、planning records 并执行纯文档合同核验。
- [x] 准备 independent-review handoff；本轮不进入 Phase 6A，不运行任何实验/provider。

**范围锁：** 仅修改用户列出的协议 Markdown 与 `task_plan.md`、`findings.md`、`progress.md`；不得修改 `src/`、`configs/`、`data/`、`tests/`。

### Phase 5B-R3：Manifest taxonomy and preflight lifecycle alignment

- [x] 恢复 planning 上下文并读取附件中的正式修订合同。
- [x] **Required 1：** 将 generated-method localized result/artifact failure 与 batch-level objective/input/split/hash/manifest/lockbox integrity failure 定义为互斥 taxonomy。
- [x] 冻结 localized failure 的 cell=0、no-deletion、rate reporting 与 supplementary complete-case 规则。
- [x] 冻结 batch contamination/inconclusive 的 exclusion、scheduled accounting、audit 和预注册 rerun/abandonment 规则。
- [x] **Required 2：** 将 smoke/train/dev pilot preflight 与 formal three-manifest lockbox joint preflight 拆成两个生命周期。
- [x] 同步 `manifest_spec.md`、`experiment_protocol.md`、`experiment_no_go_checklist.md`、`final_test_lockbox_protocol.md` 的 gate 与顺序。
- [x] 同步 reproducibility/result tables、fully-attributable-family naming、baseline-pairing batch status 与 file-identity risk。
- [x] 执行纯文档合同核验并更新 planning；不进入 Phase 6A。

**范围锁：** 仅修改附件允许的协议 Markdown 与三份 planning 文件；不得修改 `src/`、`configs/`、`data/`、`tests/`，不得运行测试、实验或 provider。

**状态：** Phase 5B-R3 documentation revision complete；27/27 document-contract checks PASS。等待 independent protocol review；本状态不授权 Phase 6A 或任何实验。

### Phase 5B-R2-R2 当前版本独立复审

- [x] 重新读取 planning 状态与本轮声明更新的七份文件。
- [x] 重新核对 evaluation-cell mapping、aggregation、rates、joint preflight 与 H1a gate。
- [x] 交叉读取 governing experiment、lockbox 与 no-go 条款；确认当前版本仍有两个 cross-document conflict candidates。
- [x] 执行本轮 18 项 review matrix 与只读一致性核验。
- [x] 按 Critical / Required / Consider / FYI 形成新 verdict，仅更新 planning 文件。

**状态：** complete — 18 checks：16 PASS、2 FAIL；Request changes（0 Critical、2 Required）。Phase 6A 前继续使用下方既有两项 Required 作为唯一修订清单。

### Phase 5B-R2-R 独立复审

- [x] 恢复 planning 上下文并确认 review-only 范围。
- [x] 复核 evaluation cell、failure-zero mapping、全 grid 聚合、complete-case 与强制 rate reporting。
- [x] 复核 joint train/dev/final-test preflight、跨 split identity/path/hash/family/lockbox checks 与 file-identity policy。
- [x] 交叉核对 contamination、lockbox 与 NO-GO 文档；确认存在 cell-local/batch contamination 分界和 joint-preflight 顺序/门禁同步的 Required candidates。
- [x] 执行只读 review contract，并按 Critical / Required / Consider / FYI 形成 verdict。
- [x] 只更新 `task_plan.md`、`findings.md`、`progress.md`；不得修改受审协议或进入 Phase 6A。

**状态：** complete — Request changes（0 Critical、2 Required）；16/16 requested core controls 有直接证据，但 2 个 cross-document protocol conflicts 阻塞 Phase 6A。

#### Phase 6A 前必须关闭

- [x] **Required 1：** 在统计协议中互斥定义 cell-local result/attribution manifest violation 与 objective/input/split/hash/lockbox integrity violation；前者按预注册 cell mapping，后者使 batch contaminated，禁止实现者自行选择层级（Phase 5B-R3 specification closed）。
- [x] **Required 2：** 统一 joint-preflight 生命周期：消除“preflight 先于任何 train/dev evaluation”与“train/dev pilot 时不创建/接触 final-test”的冲突，并把三 manifest receipt、cross-split exact-file/path/file-identity/generation checks、unsupported-identity exemption 同步到 `experiment_protocol.md`、`final_test_lockbox_protocol.md` 和 Gate B checklist（Phase 5B-R3 specification closed）。
- [ ] 修订后再次独立复审；0 Critical/Required 后才允许 Phase 6A mock/file closed-loop planning。

### Phase 5B-R2 验收清单

- [x] 冻结预注册 evaluation cell 网格与唯一的 failure-to-zero 主分析映射。
- [x] 冻结覆盖全部 replicate、solver seed、family 和 independent evolution run 的聚合规则，禁止 cell-level complete-case 删除。
- [x] 定义 cell failure、family evaluability、deployable portfolio、fallback 与 attributed generated success 的强制报告口径。
- [x] 增加 train/dev/final-test manifests 的 fail-closed joint preflight，覆盖跨 split 的 identity、family、path、hash、generation identity 与 lockbox 检查。
- [x] 定义 hardlink/file identity 不可可靠检测时的正式实验阻断与预注册豁免边界。
- [x] 同步 reproducibility、result tables、`H1a→H6→H3` gatekeeping 与条件性的 H2 paired-block bootstrap 要求。
- [x] 完成 planning 记录与复审交接；不得进入 Phase 6A。

**状态：** documentation revision complete；28/28 document-contract checks PASS；awaiting independent research-protocol review。

**范围锁：** 只允许修改用户列出的协议 Markdown 与 planning 文件；`src/`、`configs/`、`data/`、`tests/` 不得变更。

## 阶段

### 阶段 1：项目结构与实现审查

- [x] 审查 `src/`、`experiments/`、`configs/`、`tests/`、`docs/`、`README.md`、`pyproject.toml`
- [x] 梳理项目目标、问题建模、核心算法流程、LLM 参与位置、进化计算部分和实验入口
- [x] 将证据与重要发现写入 `findings.md`
- **状态：** complete

### 阶段 2：确定建模口径与实验有效性基线

- [x] 明确跨任务移动成本采用 `Manhattan distance / travel_speed`，正式主口径使用独立 `travel_speed`
- [ ] 明确任务完整性/唯一性约束应由数据模型、评价器还是求解器保证
- [ ] 定义 repair/destroy 候选的公平参照、成功指标、invalid/timeout 淘汰规则
- [ ] 明确项目当前主线是“稳定 baseline”还是“ALNS + LLM 算子演化研究”
- **状态：** pending

### Phase 5A-S：Modeling and data split blockers

- [x] 核对 processing/travel 成本实现、实例 schema、现有数据清单与默认 benchmark glob
- [x] 在 `docs/modeling_decisions.md` 比较 prototype、统一时间与归一化代价三种口径并提出正式推荐
- [x] 在 `docs/instance_protocol.md` 冻结实例族、规模、重复、family-level split 与随机性层级协议
- [x] 在 `docs/final_test_lockbox_protocol.md` 定义 manifest、访问、冻结、执行与污染处置规则
- [x] 在 `docs/experiment_no_go_checklist.md` 建立进入 Phase 5B 前的逐项 gate
- [x] 将后续代码修改、数据生成、manifest 与验证工作登记为未执行任务
- [x] 更新 `findings.md`、`progress.md` 并执行只读文档合同核验
- **状态：** modeling decision approved；instance/lockbox decisions 与实际实现、数据、manifest 尚未完成（Phase 5B/real LLM/experiments blocked）

### Phase 5A-S-R：Modeling/data protocol independent review

- [x] 逐段审查四份 Phase 5A-S 文档并与代码、实例、配置事实交叉核对
- [x] 复核 A/B/C 决策是否可批准以及 prototype/physical-time 主张边界
- [x] 复核 family/replicate/evolution-run/seed 层级与 split/lockbox 泄漏防线
- [x] 复核 default glob 的 formal-mode 规避与 Phase 5B no-go checklist
- [x] 按 Critical / Required / Consider / FYI 形成结论并更新三份 planning 文件
- [x] 执行只读文档审查合同核验；不运行测试、实验或 provider
- [x] **Required：** 批准 B + independent `travel_speed`，并冻结 estimated-time 简化假设
- [x] **Required：** 把 Phase 5B documentation-entry 与 formal-experiment execution no-go 拆成两级 gate
- [x] **Required：** 消除 per-family train/dev repetition 歧义，并在生成前冻结 family split rule
- [x] **Required：** 冻结每 split/stratum 的最小 distinct-family 数量
- **状态：** required revisions addressed；awaiting independent documentation-entry review

### Phase 5A-SR：Modeling and data protocol required revisions

- [x] 恢复 planning 上下文并读取已批准建模决策与当前 instance protocol
- [x] Required 1：把 B 标为 formal decision、A 标为 prototype legacy、C 标为未选 alternative，并完整登记迁移/no-paper-evidence 边界
- [x] Required 2：把 checklist 拆成 Phase 5B documentation-entry 与 formal-experiment execution 两级 gate
- [x] Required 3：冻结 family definition、split 互斥、生成前 assignment rule 与 `split_assignment_rule_hash`
- [x] Required 4：预注册 formal minimum distinct-family/replicate 方案与 family-level inference 边界
- [x] 同步 final-test manifest 的 family assignment、family matrix/hash、contamination owner
- [x] 更新 `findings.md`、`progress.md`，给出 4 Required 修复判定和 Phase 5B documentation-entry review 建议
- [x] 执行纯文档规格合同与修改范围核验；不运行测试、provider 或实验
- **状态：** complete — 4 Required fixed in documentation；43 contract checks PASS；documentation-entry review recommended

### Phase 5A-SR-R：Modeling and data protocol independent review

- [x] 恢复 planning 上下文并逐份读取四份 Phase 5A-SR 协议
- [x] 复核 B + independent `travel_speed`、estimated-time 假设与 sensitivity 边界
- [x] 复核 Gate A/Gate B 的权限分离和 formal/real-LLM execution blockers
- [x] 复核 family 定义、split 互斥、生成前冻结、post-hoc selection 禁令与 lockbox
- [x] 复核 distinct-family floor、family-level inference、replicate/evolution-run 层级与 R2 smoke-only 边界
- [x] 与当前 data、travel-cost 实现和 default glob 做只读事实交叉核对
- [x] 按 Critical / Required / Consider / FYI 形成独立判定并更新 planning 记录
- [x] 执行 24 项只读 review contract；全部 PASS
- **状态：** complete — Approve；0 Critical、0 Required；Phase 5B documentation-only entry allowed

### Phase 5B：Paper-grade experiment protocol documentation

- [x] 恢复 planning 上下文并读取附件中的 Phase 5B 正式规格
- [x] 盘点 8 份目标文档；确认均需新建
- [x] 读取 Phase 5A 研究问题/假设、建模、实例、lockbox 与 NO-GO 上游合同
- [x] 同步 Gate A 两项独立批准；保持 Gate B/real-LLM blockers 全部开放
- [x] 创建 `docs/research_questions.md`
- [x] 创建 `docs/experiment_protocol.md`
- [x] 创建 `docs/ablation_plan.md`
- [x] 创建 `docs/statistical_analysis_plan.md`
- [x] 创建 `docs/manifest_spec.md`
- [x] 创建 `docs/reproducibility_checklist.md`
- [x] 创建 `docs/result_table_plan.md`
- [x] 创建 `docs/pilot_plan.md`
- [x] 交叉核验 RQ/H、方法条件、预算、统计、manifest、表格和 pilot 边界
- [x] 更新 `findings.md`、`progress.md` 并执行纯文档合同/修改范围核验
- **状态：** complete（189/189 final contract PASS；documentation only；Gate B/real LLM/formal/final-test/large experiments remain blocked）

#### Phase 5B 后续 review/implementation blockers

- [ ] 对 8 份协议做 research-validity independent review，关闭 Critical/Required 后才可进入后续实现规划
- [ ] 复审 `δ_MCID=0.02`、two-way precision target、family matrix 规模和 10/10/20 replicate planning minimum
- [ ] 将 manifest/statistical contracts 转化为后续 TDD 实现计划；本阶段不实现
- [ ] 逐项关闭 Gate B 的 32 个 EXEC-BLOCKING；未关闭前不得正式实验
- [ ] 真实 LLM 另行通过 Phase 7 的 2 个 REAL-LLM-BLOCKING、runtime authorization 和风险确认

### Phase 5B-R：Research-Protocol Independent Review

- [x] 恢复 planning 上下文并确认 review-only 范围
- [x] 逐份读取九份 Phase 5B 协议
- [x] 复核 objective、方法条件、A/C/D/H2 消融与成本 estimands
- [x] 复核 independent evolution-run、family-level inference、missing/failure handling 与 multiplicity
- [x] 复核 manifest-only runner、split/lockbox、pilot 与 final-test 泄漏边界
- [x] 与当前 Gate B/代码/数据事实做只读交叉核对
- [x] 按 Critical / Required / Consider / FYI 形成 verdict 和 Phase 6A gate
- [x] 更新 `findings.md`、`progress.md` 并执行只读 review contract
- **状态：** complete — prior verdict Request changes（1 Critical、4 Required）；subsequent revision submitted

#### 批准后但尚未授权执行的建模任务

- [x] 批准正式主口径：统一时间 + independent `travel_speed`；shared speed 仅作 sensitivity
- [ ] 命名并批准 `objective_model_version`
- [ ] 为 `Instance`、loader 与 versioned instance schema 增加显式 `sweep_speed`/`travel_speed` 及有限正数验证
- [ ] 让 `CostMatrix` 的 depot/state/transition Manhattan distance 除以显式 `travel_speed`
- [ ] 核对 route DP、solution evaluator、lower bounds 与 traces 的时间单位和字段命名
- [ ] 新增 `travel_speed != 1` 的 loader、cost matrix、DP、solution、lower-bound、baseline/ALNS/benchmark 回归测试
- [ ] 更新 README、AGENTS、config/data schema 与旧实例迁移说明
- [ ] 隔离旧 objective version 的结果、cache、operator ranking 与 frozen artifacts；正式实验全部重跑

#### 批准后但尚未授权执行的数据与 lockbox 任务

- [ ] 实现并测试 versioned instance generator、family canonicalization、family/instance ID 与 hash
- [ ] 在生成前批准具体 family matrix、distribution 参数、replicate 数、seeds 与 exclusion criteria
- [ ] 达到每个纳入 stratum 的 distinct-family floor：train 4、dev 4、final-test 8；不足时降级为 pilot/exploratory
- [ ] 生成并验证 train/dev/final-test families；当前两个 R2 文件继续只作 smoke/demo
- [ ] 创建 versioned train/dev/final-test manifests，记录 `family_matrix_hash`、`split_assignment_rule_hash`、final-test manifest SHA-256 与 contamination owner
- [ ] 将 formal runner 改为 manifest-only allowlist；禁用 default glob，校验 exact input set、hash 与 split 不相交；确保 default config 不自动纳入 final-test
- [ ] 使用正式 manifests 完成 mock/file provider 最小闭环且无 fallback/invalid attribution 污染
- [ ] 固定 evolution-run repetitions、benchmark/solver seeds、统计脚本与 contamination/retry policy
- [ ] 真实 LLM 如需运行，另行通过 Phase 7 preflight、runtime authorization 与显式风险确认
- [ ] 逐项关闭 `docs/experiment_no_go_checklist.md`；在全部 BLOCKING 项关闭前保持 NO-GO

### 阶段 3：修正算子演化评价与选择协议

- [x] 先增加失败测试：repair 基准方向、无效候选不得入选、top-k 行为、回退可观测性（RED 已验证：8 个失败）
- [x] 重设 repair benchmark，以固定 greedy repair 完整解作为公平 baseline；destroy 继续使用固定 repair
- [x] 将 validation/error/timeout/invalid 作为 best selection 与 freeze 的硬门槛
- [x] 接通 `top_k_to_keep`，使其控制跨轮 feedback 数量
- [x] 记录 frozen operator 导入与运行期 fallback 事件，并随 ALNS result 暴露
- **状态：** complete

### 阶段 4：建立安全、可复现的候选执行边界

- [x] 先补 RED 测试：AST 拒绝危险 import/call、执行状态、硬超时、选择/冻结门槛和 fallback 归因（18 个预期失败）
- [x] GREEN 1：在 import 前完成 AST 禁止模块/调用/dunder-reflection 检查与 SHA-256 记录
- [x] GREEN 2：文件候选通过子进程代理执行，smoke/benchmark 设置硬 wall-clock timeout、终止与回收机制
- [x] GREEN 3：统一 validation/execution/fallback/runtime/code-hash 记录和显式 no-valid selection
- [x] GREEN 4：freeze 只接受完整 eligible 证据并写入 code hash；frozen fallback 不获得 generated reward
- [x] GREEN 5：依次通过新增 18 测试、相关回归和完整 `pytest -q`
- [x] 区分 validation_failed、runtime_error、timeout、invalid_solution、success、no_valid_operator 和 fallback
- [x] freeze/deploy 复核 code hash，并记录导入/运行 fallback reason
- [ ] 扩展审计（deferred）：有界 stdout/stderr、exit code、CPU/内存限制和 sandbox 能力降级
- [ ] 扩展复现（deferred）：逐 trial seed/environment、版本化 manifest/jsonl schema 与完整 feasibility 审计
- **状态：** complete（最小版；扩展项 deferred）

### 阶段 4R：代码审查整改门槛

- [x] 按 Correctness、Security boundary、Research validity、Architecture、Performance、Reproducibility 审查 GREEN 改动
- [ ] **Critical：** 将候选执行从“可终止子进程”提升为 capability sandbox；采用明确 import/capability allowlist，限制文件系统、网络、环境变量和子进程能力，并增加别名/间接访问对抗测试
- [x] **Critical：** smoke/benchmark 前强制执行 `safe_to_execute`/风险确认门禁；real-provider 在默认配置下只读源码和做 AST 校验，不执行候选
- [x] **Critical：** frozen proxy 绑定 expected hash；child 从一次读取并复核 hash 的源码快照执行，替换源码结构化为 `source_hash_mismatch`
- [x] frozen registry 已要求 metadata/hash、部署前 AST 校验，并通过 timeout-limited subprocess 调用，不在 ALNS 主进程 import/call 生成代码
- [x] **Required：** frozen repair/destroy contract gate 对畸形类型/shape 异常封闭，统一转为 `invalid_solution` fallback
- [x] **Required：** validation_failed/source_read_failed/runtime_error/timeout/invalid_solution/success 已分开并保留 breakdown
- [x] **Required：** 双 generated 算子联合试验发生 fallback 时标记 `attribution_ambiguous`，双方 generated reward 均为零
- [x] **Required：** 候选文件缺失/解码/读取失败已收敛为结构化 `source_read_failed`
- [x] **Required：** child 内有界捕获 stdout/stderr，并记录 truncation、exit code 与 wall time
- [x] **Required：** selection/freezing 对缺失 safety/failure 证据 fail closed，不使用 success/True/0 默认值
- [x] **Required：** benchmark 对畸形 candidate result 结构化为 runtime_error/invalid_solution，不中断 evolution loop
- [x] **Required：** frozen registry JSON/row/path/metadata 类型错误结构化记录，不因 KeyError/JSON/Unicode 错误中断 ALNS 初始化
- [x] **Required：** 同步 README、`docs/operator_evolution.md`、LangChain YAML 与 CLI 风险门禁，明确当前仅 timeout-only
- [ ] **Required remaining：** CPU、内存、后代进程树与文件系统/网络 capability 限制或平台降级策略
- [ ] **Consider：** 降低 Windows 下每 trial spawn/import 开销，分别报告 candidate runtime、sandbox overhead 和端到端 wall time
- [ ] **Consider：** 区分 `not_evolved` 与 `no_valid_operator`，并补齐逐 trial instance/seed/timeout/environment manifest
- [x] 已按 RED 测试完成最小修复，并重跑 operator evolution/ALNS 回归和完整 `pytest -q`
- [x] 对 Phase 4B GREEN 做独立代码复审
- [x] 已为本轮 2 个 Critical 和 Required 项补齐 Phase 4C RED 测试
- [x] 经授权完成最小 GREEN 修复与全量测试验证
- [x] 对 Phase 4C GREEN 做独立代码复审
- [x] **Critical：** unsafe allow flag 严格 bool/schema 校验并补非 bool 对抗测试；GREEN 已完成，待再次独立复审
- [x] **Required：** expected hash 底层 API、registry 完整 metadata/timeout、selection/freezing 完整 evidence、正式规格同步
- **状态：** GREEN complete；awaiting independent review（真实 LLM/Phase 5 blocked）

### 阶段 4B：Operator execution boundary hardening

- [x] RED 1：为 sandbox capability 等级、`safe_to_execute` 与 metadata 口径增加失败测试
- [x] RED 2：为 frozen registry 完整 metadata、部署前 AST/hash 复核、隔离超时与 fallback 记录增加失败测试
- [x] RED 3：为 frozen repair/destroy contract 与全局 feasibility、invalid reward/freeze gate 增加失败测试
- [x] RED 4：为互斥 failure-type breakdown 和 aggregate metrics 增加失败测试
- [x] RED 5：为 repair/destroy 配对 fallback 的奖励归因增加失败测试
- [x] RED 6：为缺失/编码/读取失败源码的结构化 `source_read_failed` 增加失败测试
- [x] RED 7：为有界 stdout/stderr、truncation、exit code 与 wall time 增加失败测试
- [x] 运行新增测试并逐项确认因目标能力缺失而 RED；不删除、skip 或放宽既有测试
- [x] 将失败测试、失败原因和最小 GREEN 顺序写入 `progress.md`
- [x] GREEN：按 metadata/schema → source read → executor observability → frozen deployment → contract/reward → metrics 顺序完成最小实现
- [x] GREEN 后运行新增测试、既有 operator evolution/ALNS 回归和完整 `pytest -q`
- [x] 按 Phase 4R 做独立代码复审
- [ ] **剩余风险（不纳入本阶段最小实现）：** CPU、内存、子进程树、文件系统/网络 namespace 与跨平台 OS sandbox；不得因 RED/GREEN 通过而宣称完整 capability sandbox
- **状态：** GREEN tests pass；review request changes（2 Critical open）

### 阶段 4C：Execution gate and frozen operator TOCTOU fixes

- [x] RED：real-provider unsafe/risk-ack 在 smoke 与 benchmark 前形成执行门禁
- [x] RED：evolution config 默认 `allow_unsafe_candidate_execution=False`，并核对 provider/sandbox metadata
- [x] RED：AST 拒绝 FileIO/pathlib/importlib/builtins/getattr/dunder-reflection 绕过
- [x] RED：path proxy 每次执行前绑定 expected code hash，frozen 源码替换走 fallback 且零奖励
- [x] RED：畸形 contract/benchmark 返回结构化为 invalid/error，不中断流程
- [x] RED：selection/freezing 缺安全证据 fail closed；registry 解析错误结构化 fallback
- [x] RED：文档不再描述旧 soft timeout，真实 LLM 命令前有安全警告/checklist
- [x] 运行新增测试并确认因生产合同缺失而 RED；记录失败名称、原因和 GREEN 顺序
- [x] GREEN：按 execution policy → hash binding → contract/metrics → registry → docs 顺序最小实现
- [x] GREEN 后运行 Phase 4C、相关 operator-evolution/frozen-ALNS 回归和完整 pytest
- [x] **Critical follow-up：** `allow_unsafe_candidate_execution` 严格要求 bool；字符串、整数、None 等非 bool 配置拒绝/阻断，loader/evolution 使用共同 policy
- [x] **Required follow-up：** `CandidateProxy`/executor 缺 expected hash 时拒绝执行，避免未来旁路 fail open
- [x] **Required follow-up：** frozen registry 加载强制 failure/provenance/sandbox/risk-ack，并结构化校验有限正数 timeout
- [x] **Required follow-up：** selection/freezing 缺 fallback 与三类 failure rate 时 fail closed；统一 typed eligibility policy
- [x] **Required follow-up：** 更新 `docs/llm_operator_evolution_spec.md` 的过期“当前实现差距”段落
- [x] 独立复审 Phase 4C；结论为 Request changes
- **状态：** review complete；1 Critical + 4 Required groups（Phase 5/real LLM/large experiments blocked）

### 阶段 4D：Strict eligibility policy and config hardening

- [x] RED：非 bool unsafe allow 值全部 fail closed，且不得 smoke/benchmark/select/freeze
- [x] RED：只有 literal bool True 才可能授权，并仍需满足 validation/risk/provider/sandbox/safety policy
- [x] RED：runner YAML 配置严格类型验证，loader/evolution 使用统一严格 policy
- [x] RED：path execution 缺 expected hash 时拒绝执行
- [x] RED：frozen registry 缺完整 evidence 时拒绝；timeout 必须为有限正数且错误结构化 fallback
- [x] RED：selection/freezing 缺 fallback/rates evidence 时 fail closed
- [x] RED：正式规格不得保留 Phase 4 前的过期实现描述
- [x] 运行新增测试确认因现有生产/文档缺口而 RED；记录节点、原因与 GREEN 顺序
- [x] GREEN：统一 strict-bool/execution eligibility policy，并封闭 hash、registry/timeout、selection/freezing 与规格口径
- [x] GREEN 后运行 Phase 4D 专项、Phase 4/4B/4C、operator evolution、frozen/ALNS、完整 pytest 与 compileall
- [x] 对 Phase 4D GREEN 做独立代码复审；结论 Request changes
- [x] **Critical：** sandbox level 绑定可信 executor 事实；timeout-only executor/registry 拒绝自声明 `capability_sandbox`，真实 provider 不能借 artifact 绕过 allow/risk gate（Phase 4E GREEN）
- [x] **Required：** selection/freezing/registry 强制 `validation_failed_rate`、`execution_blocked_rate` 与显式有限正 `timeout_ms`，取消 optional/default 成功证据（Phase 4E GREEN）
- [x] **Required：** 统一 loader 执行决策，并让底层 executor 对同一源码快照执行 AST validation（Phase 4E GREEN）
- [x] **Required：** feedback/leaderboard 仅从 eligible pool 产生；区分 `not_evolved`、`no_valid_operator`、invalid 与 fallback（Phase 4E GREEN）
- [x] **Required：** 同步正式规格，移除过度声明并记录 trusted runtime authority（Phase 4E GREEN）
- [ ] Consider（不扩大本阶段）：将既有会写入项目 `generated_operators/` 的测试迁移到临时目录，避免完整 pytest 刷新研究产物
- **状态：** review follow-ups implemented in Phase 4E；等待 Phase 4E 独立复审（Phase 5/real LLM/large experiments blocked）

### 阶段 4E：Trusted executor authority and sandbox-claim hardening

- [x] RED：artifact/registry 自声明 `capability_sandbox` 不得取得 real-provider 执行、benchmark、selection 或 freeze 授权
- [x] RED：execution eligibility 使用可信 executor identity/runtime sandbox level，并将当前 effective level 固定为 `timeout_only`
- [x] RED：frozen registry sandbox claim 与 runtime authority 不匹配时结构化 fallback
- [x] RED：selection/freezing 强制全部 failure-rate evidence 与显式有限正 `timeout_ms`
- [x] RED：底层 path executor 对同一源码快照再次执行 AST/security validation，正确 hash 不能授权危险源码
- [x] RED：candidate loader 通过统一 policy 决策，不自行复制 real-provider/safety 状态转换
- [x] RED：区分 `not_evolved` 与 `no_valid_operator`；feedback/leaderboard 过滤 ineligible rows
- [x] RED：正式规格声明 sandbox level 来自可信 runtime authority，且只在实现确实完整时声称 evidence fail closed
- [x] 运行 Phase 4E 新增测试确认 RED，并运行既有边界回归确保新增测试未改生产行为
- [x] 将失败分组、原因与最小 GREEN 顺序写入 `progress.md`
- [x] GREEN：实现 trusted executor authority、完整 evidence、same-snapshot AST、统一 loader policy、状态/feedback 和文档最小修复
- [x] GREEN 后运行 Phase 4E、Phase 4/4B/4C/4D、operator evolution/frozen ALNS、完整 pytest 与 compileall
- [x] 补充 alias-claim TDD：`sandbox_level` 与 `claimed_sandbox_level` 不一致时 selection/freezing/registry fail closed
- [x] 对 Phase 4E GREEN 做独立代码复审；结论 Request changes
- [x] **Critical：** frozen registry 不再把 artifact JSON 的 safety/risk 字段当 runtime 授权；real-provider deployment 现要求独立 runtime allow/人工确认/source（Phase 4F GREEN）
- [x] **Required：** execution eligibility 缺 runtime authority 时拒绝并要求 `CandidateProxy`；validation schema 改为保守默认（Phase 4F GREEN）
- [x] **Required：** 增加 frozen real-provider 伪造 ack、缺 runtime evidence/任意 callable 的回归测试（Phase 4F RED/GREEN）
- [x] **Required：** 同步正式规格 Phase 4F 与 frozen runtime gate，修正 `docs/operator_evolution.md` sandbox 措辞
- [ ] **剩余风险（本阶段不实现）：** CPU、内存、文件系统、网络、环境变量和后代进程树隔离；当前仍不是 capability sandbox
- **状态：** review complete — Request changes（1 Critical + Required；新鲜完整 249 passed、compileall exit 0；Phase 5/real LLM/large experiments blocked）

### 阶段 5：形成论文级实验协议（documentation allowed）

- [ ] 实现显式 top-k elite set、lineage、AST/行为去重和 diversity retention
- [ ] feedback 的 top/weak 候选只从 eligible pool 产生，并包含规范化失败案例
- [ ] 修正 destroy invalid trial 不得计 success，增加 fallback count/rate/reason 与 contaminated-run 标记
- [ ] 扩展实例规模、机器人/任务组合与 repetition，建立 train/dev/test 或生成/评估隔离
- [ ] 对随机算法使用多种子，报告均值、标准差/置信区间、配对检验、运行时间与 gap
- [ ] 重新设计消融，确保 `alns` 与 `alns_dp_aware` 存在真实且唯一的算法差异
- [ ] 增加 baseline、内置算子、mock/file/真实 LLM、冻结算子和回退模式的公平比较
- [ ] 报告 LLM token/货币成本、候选有效率、sandbox overhead、失败/重试成本和每个冻结算子成本
- **状态：** Phase 5A documentation complete；Phase 5B 尚未开始，不授权真实 LLM 或大规模实验

#### Phase 5A：LLM innovation framing and research positioning

- [x] 恢复 planning context，读取 README、AGENTS、现有研究文档目录并确认五份目标文档均尚不存在
- [x] 审查实际问题模型、route DP、ALNS/advisor/operator-evolution 实现与既有研究规格
- [x] Brainstorming：确定跨领域 AI-for-Optimization 定位；LLM offline operator evolution 为主创新，MR-RCRP + DP-aware ALNS 为验证载体
- [x] Brainstorming：批准 A 主线 + C/D 辅助、B 仅作泛化消融的设计
- [x] 创建 `docs/research_positioning.md`
- [x] 创建 `docs/innovation_review.md`
- [x] 创建 `docs/llm_operator_evolution_research_plan.md`
- [x] 创建 `docs/paper_contribution_plan.md`
- [x] 创建 `docs/research_hypotheses.md`
- [x] 自查事实/计划/创新/未验证主张边界、假设可证伪性、held-out test 隔离与五份文档一致性
- [x] 更新 planning 文件并结束 Phase 5A；不进入 Phase 5B
- **状态：** complete — 五份文档已形成一致的 A 主线 + C/D 辅助 + B 消融设计；等待用户审阅，不自动进入 Phase 5B

#### Phase 5A-R：Research-validity review

- [x] 逐份审查五份 Phase 5A 文档，核对事实、计划、候选贡献和未验证主张的标签
- [x] 与实际 MR-RCRP model、route DP、ALNS/advisor、operator evolution、evaluation/freezing 事实交叉核对
- [x] 审查 train/generation、selection/dev、final-test lockbox、预算公平性与污染规则
- [x] 审查 A/C/D/B 的可识别性、baseline/ablation、归因和 falsification criteria
- [x] 检查安全/可信部署口径是否被误写为 capability sandbox 或可信 provenance
- [x] 按 Critical / Required / Consider / FYI 给出结论并更新 `findings.md`、`task_plan.md`、`progress.md`
- [x] **Critical（实验执行 no-go）：** 在论文统计协议中定义独立 operator-evolution run、instance-family/solver-seed 层级、主 estimand、cluster-aware CI/test 和 confirmatory hypothesis hierarchy，禁止把同一 evolution run 的 candidates 或确定性重复 seed 当独立样本
- [x] **Critical（实验执行 no-go）：** 现有仅 `R2_T6_0`/`R2_T10_0` 两实例不得硬拆 train/dev/test；先冻结实例生成/纳入规则、family/group split、最小规模与 final-test manifest，并先解决 speed travel/processing 单位口径
- [x] **Required：** 将 H2 拆为 DP-aware performance feedback 与 feasibility feedback 两个因素，采用 2×2 或 H2a/H2b，并保持相同 evaluator/candidate pool/token budget
- [x] **Required：** 为 D 建立互斥 primary outcome precedence，并把 execution、feasibility、optimization performance、structural diagnostics 分轴；固定分母、聚合和标签版本
- [x] **Required：** 明确 C 在 final test 内只允许预注册、run-local 的 adaptive selector；禁止跨 instance/seed/run 持久化状态或回写 prompt/portfolio
- [x] **Required：** 把 H5 改成预注册的 quality-constrained cost、cost-constrained quality 或 Pareto estimand；若保留 break-even，必须明确共同效用/价格假设
- [x] **Required：** 将“可复用”限定为 frozen operators 在 MR-RCRP 问题族内跨实例/规模复用；没有多领域实验不得声称跨组合优化问题复用
- [x] **Consider deferred：** provider 时间块随机化、精确 model/endpoint/temperature/retry/token、portfolio dev stability 与 behavior-first structural diagnostics 已写入计划，不是当前实现
- **状态：** revision complete — 2 Critical + 5 Required 已文档化修复；逐项合同检查通过；不进入 Phase 5B，真实 LLM/实验继续 blocked

### 阶段 4F：Runtime authorization for real-provider frozen deployment

- [x] RED：伪造完整 artifact safety/risk 字段的 real-provider frozen row 在无 runtime authorization 时不得部署
- [x] RED：artifact 自报 risk acknowledgement 不得替代当前运行时显式授权
- [x] RED：runtime allow / risk ack 仅接受 literal bool，非 bool 全部 fail closed
- [x] RED：timeout-only 下的 real-provider 部署行为与非 capability sandbox 口径明确
- [x] RED：execution eligibility 缺 runtime authority evidence 或仅提供任意 callable 时拒绝
- [x] RED：validation/schema 默认 safety、risk、sandbox 与 executor authority 必须保守
- [x] RED：规格与 operator 文档准确描述 frozen runtime authorization 和 timeout-only 边界
- [x] 运行 Phase 4F 专项并确认失败来自生产/文档合同缺失；运行既有边界回归确认无意外回归
- [x] 将失败分组、原因与最小 GREEN 计划写入 `progress.md`
- [x] GREEN：实现 runtime-owned deployment authorization、保守 schema/execution evidence 和文档同步
- [x] GREEN 后运行 Phase 4F、Phase 4–4E、operator evolution/frozen ALNS、完整 pytest 与 compileall
- [x] 对 Phase 4F GREEN 做独立复审（Request changes；provider provenance Critical）
- [x] **Critical review follow-up：** 在可信 receipt 未实现时，对所有 generated frozen artifact 使用 provider-agnostic runtime authorization；registry 的 `source_provider` 不再决定授权
- [x] 增加“相同 real-provider artifact 仅重标 `source_provider=mock` 仍必须拒绝”的部署回归测试
- [x] 增加缺失/unknown/畸形 provenance、claim mismatch 与 lineage 缺失的 fail-closed 回归测试
- [x] 采用并文档化保守策略：所有 generated frozen artifact 均要求当前 runtime deployment authorization，不给 mock/file/manual claim 豁免
- [x] 修正 formal spec/operator guide，使其准确描述 claimed provider、artifact-claim provenance 与 provider-agnostic gate
- [ ] **复审风险：** `source_provider` provenance 仍来自未签名 registry metadata；真实 provider 解禁前评估 versioned/signed receipt 或 runtime provenance binding
- **状态：** independent review complete — Request changes（1 Critical + Required follow-ups；专项 124 passed、full 286 passed、compileall exit 0；Phase 5/real LLM/large experiments blocked）

### 阶段 4G：Trusted provider provenance and generated artifact deployment gate

- [x] RED：同源码/hash/evidence 的 real-provider row 与重标 `mock` row 在缺可信 provenance/runtime authorization 时均拒绝部署
- [x] RED：`source_provider` 仅作为 claimed metadata；缺失/unknown/类型错误 provenance、claim/provenance 不一致均 fail closed
- [x] RED：缺 lineage、generation_run_id 或 artifact_identity 的 generated frozen artifact 拒绝部署
- [x] RED：mock/file/manual/rule_based/real/unknown 等所有 generated frozen artifact 默认要求当前 runtime deployment authorization
- [x] RED：deployment allow/risk ack 非 literal bool 全部拒绝，默认 False
- [x] RED：freezing 不把 claimed provider 写成 trusted provenance；selection/feedback 不因 claimed mock/file 降低门槛
- [x] RED：正式规格准确区分 claimed provider、trusted provenance 与普通字符串 evidence
- [x] 运行 Phase 4G 专项并确认失败来自生产/文档合同缺失，不是测试错误
- [x] 运行既有 Phase 4–4F 边界回归，确认新增失败仅来自 Phase 4G
- [x] 将失败分组、原因与最小 GREEN 顺序写入 `progress.md`
- [x] GREEN：统一 generated artifact metadata/provenance schema，并让 registry/selection/freezing fail closed
- [x] GREEN：所有 generated frozen deployment 使用 provider-agnostic runtime gate；strict bool，默认关闭
- [x] GREEN：freezing/evolution 只记录 claimed provider 和 untrusted artifact provenance，不生成伪 trusted receipt
- [x] GREEN：selection/feedback/leaderboard 过滤缺 provenance/lineage evidence 的候选
- [x] GREEN：同步正式规格并分层运行 Phase 4G、Phase 4–4G、完整 pytest 与 compileall
- [x] 独立复审 provider relabel、统一 deployment gate、eligibility/feedback、兼容路径与文档事实
- [x] 重新运行 Phase 4G 专项、完整 pytest 与 compileall，记录 Critical / Required / Consider / FYI gate
- [ ] Consider：把 registry metadata validation + runtime authorization 收敛为单一 typed deployment eligibility API，避免未来调用者漏掉前置验证
- [ ] Consider：逐步弃用 Phase 4F 的 real-provider 命名兼容授权 pair，统一到 generated frozen allow/ack 并提供迁移提示
- [ ] Consider：真实 LLM 或非受信 file/manual 候选解禁前，引入 capability sandbox、资源/网络/环境/进程树隔离和可信 provenance receipt
- **状态：** independent review approved（no Critical/Required；Phase 5 documentation allowed；real LLM/large experiments blocked）

### 阶段 7：LLM 算子演化正式设计规格

- [x] 明确 LLM、EA/ALNS 与 DP 的职责边界及非目标
- [x] 规定 generation 到 ALNS deployment 的完整候选生命周期
- [x] 规定 AST 门禁、隔离进程、硬超时、输出捕获与代码哈希
- [x] 规定 repair/destroy 公平评价、硬门槛、多实例多 seed 和 fallback 归因
- [x] 规定 top-k、diversity、失败反馈、problem-specific hints 与逐轮文件契约
- [x] 形成四项论文贡献候选、消融与成本分析要求
- **状态：** complete

### 阶段 6：统一入口、配置与文档

- [ ] 显式校验算法名、接受准则和参数范围
- [ ] 统一 README、`AGENTS.md`、默认 YAML 的阶段与默认模式口径
- [ ] 明确两套模块运行方式及规划文件长期位置
- [ ] 最后运行完整测试、轻量 demo 与小规模 mock 闭环并记录证据
- **状态：** pending

## 关键问题

1. 当前任务分配问题的实体、约束、目标函数和输入输出如何定义？
2. 主求解流程如何组织，进化计算与其他启发式方法分别承担什么角色？
3. LLM 在候选生成、选择、评估、冻结或运行时求解中的具体位置是什么？
4. 已有哪些可复现实验入口、配置、测试与结果产物？
5. 下一阶段最值得优先验证或补齐的研究与工程缺口是什么？

## 决策

| 决策 | 理由 |
|---|---|
| 本阶段只读取项目文件并更新三份规划文档 | 遵守用户“不修改代码”的边界 |
| 优先进行静态审查，仅在必要时做轻量检查 | 避免触发耗时实验或产生非预期产物 |
| 后续优先修正评价协议，再扩展真实 LLM 或大实验 | 当前指标与 best 选择可直接破坏研究结论有效性 |
| 将候选执行安全与可观测性列为独立阶段 | 真实 LLM 输出会被动态导入执行，风险不能只依赖 prompt |
| LLM 算子演化采用“规范性工程契约 + 论文研究协议”混合规格 | 同时提供可测试的 MUST 门槛与可验证的论文贡献，避免实现和研究口径脱节 |
| 规格明确区分当前实现与目标要求 | 当前仍缺 AST sandbox、硬超时和完整审计，不能把设计声明当作实现证据 |
| 后续按 baseline 稳定化 → ALNS 研究 → LLM 离线演化论文推进 | 防止在基础评价口径未稳定时提前运行昂贵且不可归因的真实 LLM 实验 |
| Phase 4 使用 AST gate + 文件候选子进程代理 | 避免在验证前或 benchmark 中把生成代码导入主进程，同时保留现有 evaluator 接口的最小兼容性 |
| 子进程先完成受限 import，再单独计候选 call 的 timeout budget | 既约束顶层 import，又避免 Windows 进程启动时间被误算为候选算法运行时间 |

## 错误记录

| 错误 | 尝试 | 处理 |
|---|---:|---|
| 初次按工作区顶层查找指定目录，均显示缺失 | 1 | 枚举目录后确认实际项目根为 `mrta_rect_coverage/`，后续从该目录审查 |
| `git status` / `git rev-parse` 报告当前不是 Git 仓库 | 1 | 不依赖 Git，改用显式文件清单核对；未尝试修复 `.git` |
| 独立 Python 诊断首次无法导入 `mrta_rect_coverage` | 1 | 设置 `PYTHONPATH=src` 后诊断成功；未修改项目配置 |
| pytest 无权写入既有 `.pytest_cache` | 1 | 测试执行与 RED 结果不受影响；记录警告，不修改缓存权限 |
| `spec-driven-development` 技能在当前环境不可用 | 1 | 经用户批准，使用 brainstorming 审批后的混合规格方案继续，只编写设计文档 |
| 本轮复核发现 `docs/modeling_decisions.md`、`docs/evaluation_protocol.md` 不存在 | 1 | 记录为既有文档缺口；本轮不越界补建，规格直接基于 README、AGENTS、规划记录和代码事实 |
| Phase 4 首次独立 Python 诊断无法导入包 | 1 | 设置 `PYTHONPATH=src` 后成功读取 validation error；未修改项目安装状态 |
| AST attribute denylist 将正常的 `list.remove` 误判为文件删除 | 1 | 根据实际 error message 仅移除泛化的 `remove` 属性禁令；危险模块根和文件 API 禁令保留 |
| Phase 4 完成记录的首次多文件补丁上下文不匹配 | 1 | 读取实际 Phase 4 段落后使用精确小补丁；生产代码与测试结果不受影响 |
| Phase 4B executor 首次 stderr 截断测试未保留 warning marker | 1 | 根因是标准 warning 的长路径前缀占满 head limit；改为 child 内紧凑 warning formatter，不放宽输出上限或测试 |
| Phase 4B 相关回归有 1 个 legacy registry fixture 被新 metadata gate 拒绝 | 1 | 保持生产端拒绝缺 metadata；仅给既有 runtime-fallback 测试补齐 hash/validation/safe/timeout fixture |
| Phase 4B 首次完整 pytest 另发现 1 个 Phase 4 legacy registry fixture 缺 validation/safe metadata | 1 | 同样只补测试 fixture，不放宽 frozen metadata gate；随后先跑原失败测试再重跑全套 |
| Phase 4B 完成记录首次多文件补丁上下文不匹配 | 1 | 读取实际 Phase 4R 段落并拆成小补丁；生产代码和测试证据不受影响 |
| Phase 4R 首次追加 findings 使用了不匹配的尾部上下文 | 1 | 读取 `findings.md` 实际尾部后按精确上下文追加；审查对象与结论不受影响 |
| Phase 4C 复审临时 Python 诊断首次无法导入包 | 1 | 保持生产文件不变，下一次以 `PYTHONPATH=src` 重跑同一只读/临时目录诊断 |
| Phase 4C Critical 记录的首次多文件补丁上下文不匹配 | 1 | 读取三个规划文件实际尾部后使用精确小补丁；审查证据不受影响 |
| Phase 4D RED 首次 pytest 输出超过报告上限，未保留最终汇总 | 1 | 使用临时输出文件和 `--tb=no` 紧凑重跑，只回显失败节点及末尾汇总。 |
| 收尾时仅凭 30 分钟文件时间窗口误判新增 evolution 测试写入默认生成目录 | 1 | 回读测试确认其 `generated_dir`/`output_dir` 已显式使用 `tmp_path`；生产源码时间早于本轮新增测试，近期生成产物来自完整既有套件。 |
| Phase 4D GREEN fixture 核对时在 Windows `rg` 路径参数使用 `tests/test_alns*` 通配符，报 os error 123 | 1 | 改为搜索 `tests` 目录，并通过 `-g 'test_alns*.py'` / `-g 'test_operator*.py'` 过滤；不重复错误命令。 |
| Phase 4/4B/4C/4D 合并回归首次运行 23 failed、112 passed | 1 | Phase 4D 59 项已绿；失败均因旧 executor/registry fixtures 缺新 mandatory hash/evidence 而在更早 gate 被拒绝。按系统化调试核对 helper 与失败节点后做最小 fixture 迁移，不放宽生产 gate。 |
| Phase 4E 独立复审首次假设存在 `operator_evolution/selection.py` | 1 | 项目实际由 `evolution_loop.py` + `eligibility_policy.py` 承担 selection；改按真实模块读取，不重复错误路径。 |
| Phase 4F GREEN 首轮正例被 runtime source allowlist 拒绝 | 1 | 测试合同使用 `current_runtime_config`，实现漏列该明确 current-runtime source；补入 allowlist 后重跑，不放宽 bool/ack/executor 门禁。 |
| Phase 4–4F 合并回归 1 个旧 direct-policy 正例失败 | 1 | 旧 fixture 使用 lambda 与 trusted schema defaults；按 Phase 4F 新合同迁移为 proxy + 显式 runtime evidence，保持 `eligible=True` 断言。 |
| Phase 4F GREEN 收尾规划补丁上下文不匹配 | 1 | 读取实际 Phase 5/4F 段落后拆成小补丁；生产实现与测试证据不受影响。 |
| Phase 4F 完成段首次插入到较早 progress 上下文 | 1 | 删除错误位置的重复段并追加到 `progress.md` 末尾，保持日志时间顺序。 |
| Phase 4G freezing RED 首轮用直接键访问缺失 claimed-provider 字段 | 1 | 将测试改为 `.get(...) == "mock"`，使缺失能力表现为预期 assertion failure，不修改生产合同。 |
| Phase 4G GREEN 旧 fixture 批量迁移补丁上下文不匹配 | 1 | eligibility import 结构与假设不同；确认补丁未应用，改为逐文件精确小补丁。 |
| Phase 4G 合并回归的 yielded cell 在上下文恢复后不可用 | 1 | 使用同一轻量 pytest 命令重新运行并取得完整汇总；未依赖丢失结果作结论。 |
| 收尾审计在 PowerShell 中使用 Bash brace path 语法 | 1 | PowerShell 解析失败；改为逐个显式路径，不重复该命令。 |
| 工作区顶层 `.git` 是空目录，Git 状态/差异命令不可用 | 1 | 不修复或初始化仓库；改用明确文件清单、源码检索、测试与 compileall 核对范围。 |
| Phase 5A 创建 `innovation_review.md` 时工具回显因长度截断，落盘状态一度不明 | 1 | 未重复写入；先用 `Test-Path`、文件长度、标题和尾部内容核验，确认文件已完整创建。 |
| Phase 5A 最终 PowerShell 核验在双引号中使用 `$label:` 导致变量解析错误 | 1 | 改用格式化字符串 `-f` 后重跑；五份文件、H1–H7 字段和 Phase 5A 清单均验证通过。 |
| completion gate 首次使用与正文不完全一致的 sandbox 固定短语 | 1 | 正文实际写为“不是完整 capability sandbox”；调整核验词为原文精确口径后重跑，不为迎合检查改写正文。 |
| Phase 5A-R 组合 `rg` 的末尾 success-count 正则在 PowerShell/regex 双重转义后成为未闭合分组 | 1 | 前三组文档锚点已正常返回；代码锚点改用多个简单 literal/regex 查询，不重复复杂组合表达式。 |
| Phase 5A-S 首次文档合同检查有 3 个同义措辞谓词未命中 | 1 | 回读正文确认规则存在；补充统一审计标签与明确文件绑定后重新运行完整合同检查，不修改生产代码或降低门禁。 |
| 建模批准收尾检查的 `approved_status` Markdown 正则未命中 | 1 | 正文状态正确，正则把粗体星号位置写错；改用 literal matching 重跑，不修改决策正文迎合检查。 |
| Phase 5A-SR 首个 modeling+instance 组合补丁上下文顺序不匹配 | 1 | 4.4 hunk 在补丁中排到候选 C 之后，与原文件顺序相反；补丁未应用，改为按文件和原文顺序拆分小补丁。 |
| Phase 5A-SR-R 尝试使用 `git status/diff` 核对修改范围，但项目根不是 Git 仓库 | 1 | 不初始化或修复 Git；改用受审文件 SHA-256、显式合同检查和代码/数据只读检索。审查结论不依赖 Git。 |
| Phase 5B 最终 PowerShell 合同脚本用反引号包裹 manifest 字段名，破坏字符串解析 | 1 | 文档未执行检查也未受影响；改为直接搜索字段名并拆除 Markdown 反引号转义，不重复失败表达式。 |

## Phase 4E 独立复审复核 gate（2026-08-05）

- [x] 重新核验 trusted/effective sandbox、同快照 hash+AST、完整 evidence、状态语义与 feedback filtering
- [x] 重新执行 forged real-provider frozen registry 与缺 runtime authority 的只读临时诊断
- [x] 重新运行完整 `pytest -q` 与 `python -m compileall -q src`
- [ ] **Critical：** frozen real-provider deployment 引入独立 runtime authorization / 显式人工风险确认 authority，不能使用 artifact 自报 safety/risk 字段授权
- [ ] **Required：** execution eligibility 缺 runtime authority evidence 时 fail closed，并移除 validation schema 的可信默认值
- [ ] **Required：** 增加上述 canonical deployment 与公共 execution boundary 的负例回归测试
- [ ] **Required：** 修正规格 Phase 标题、frozen gate 事实、feedback 实现状态及 operator 文档的 sandbox 矛盾措辞
- **Gate：** Request changes；Phase 5、真实 LLM、大规模实验继续 blocked。
## Phase 5B-R — Research-protocol review（2026-08-06，进行中）

- [x] 完整审阅九份 Phase 5B 协议文档。
- [x] 核对 objective_v2/v1、A/C/D 消融、H2 factorial 与 H5 成本 estimand。
- [x] 核对 independent evolution-run、family split、lockbox 与 manifest-only 原则。
- [x] 核对 result-table claim boundary、pilot 边界与两级 NO-GO gate。
- [x] 复核统计 estimand、失败轮处理、MCID、聚合规则及 manifest 可执行性。
- [x] 输出 Critical / Required / Consider / FYI 与 Phase 6A 准入结论。

### Phase 5B-R required revisions（阻塞 Phase 6A）

- [x] **Critical:** 冻结 scheduled independent evolution-run 的 failure-aware primary estimand；不得只分析 valid paired results。
- [x] **Required:** 统一 H1 statistical superiority 与 `delta_MCID` practical-relevance 判据。
- [x] **Required:** 冻结唯一 stage-1 aggregation、primary model/CI、权重和 model-failure fallback；其余只作 sensitivity。
- [x] **Required:** 为 H2a/H2b 分别冻结 primary response、denominator、effect scale/link 与 multiplicity 角色。
- [x] **Required:** 将 manifest 收敛为严格 schema：显式 instance identity/唯一键、单一字段类型、canonical ordering/serialization、duplicate/path alias/symlink 与 fail-closed validation。
- [ ] 修订后再次执行独立 research-protocol review；0 Critical/Required 后才允许进入 Phase 6A mock/file closed-loop planning。

### Phase 5B-R：Experiment protocol statistical and manifest revision（2026-08-07）

- [x] 恢复 planning 上下文并读取附件中的正式修订合同。
- [x] **Critical:** 冻结 all scheduled independent evolution runs 的 failure-aware 主分析总体、唯一失败规则与 complete-case 限制。
- [x] **Required 1:** 将 H1 拆为 statistical superiority 与 practical superiority/MCID 两个明确判据。
- [x] **Required 2:** 冻结 seed→replicate→family→evolution-run 聚合、equal-family weighting、two-way cluster bootstrap 与模型失败 fallback。
- [x] **Required 3:** 为 H2a/H2b 固定 primary response、effect scale、denominator 与预算合同；H2c 保持 exploratory。
- [x] **Required 4:** 将 manifest 收敛为 strict typed schema，加入 instance identity、duplicate/path/hash/canonical serialization 与 fail-closed runner rules。
- [x] 同步 result tables、reproducibility、experiment protocol、pilot 与 research hypotheses。
- [x] 执行纯文档合同核验并更新 findings/progress；不运行 tests/provider/experiment。
- [ ] 修订后提交独立 review；本轮不进入 Phase 6A。
- **状态：** documentation revision complete；80/80 contract PASS；awaiting independent review；Phase 6A/real LLM/formal experiments blocked

### Phase 5B-R-R：Research-protocol revision review（2026-08-07）

- [x] 恢复 planning 上下文并确认只读 review 范围。
- [x] 逐份复核 statistical/experiment/ablation/manifest/result/reproducibility/pilot 与 planning records。
- [x] 初步核对 all-scheduled-runs population、failure-zero rule、H1a/H1b、唯一聚合、run×family bootstrap 与 H2 estimands。
- [x] 核对部分 family/replicate/seed 评价失败的主分析映射，确认仍有 Required gap。
- [x] 核对 duplicate file/hash/path 和 family/instance identity 是否跨 train/dev/final-test manifests 联合 fail closed，确认仍有 Required gap。
- [x] 核对 result accounting、reproducibility、pilot 和所有执行禁令。
- [x] 按 Critical / Required / Consider / FYI 给出 Phase 6A 准入 verdict并更新 planning。
- **状态：** complete — Request changes（0 Critical、2 Required）；14/16 review checks pass

#### Phase 6A 前必须关闭的 protocol revisions

- [x] **Required:** 为全部 scheduled `run × condition × family × replicate × solver_seed` evaluation cells 冻结唯一失败映射；timeout/invalid/fallback/blocked/missing/error/no-attribution 均在 cell 层取 policy value 0，禁止任何 cell-level complete-case deletion。
- [x] **Required:** 定义 joint split-manifest preflight：联合加载 train/dev/final-test manifests，在合并 records 上拒绝 duplicate `file_hash`、resolved path/file identity、family/instance/generation overlap；单 split runner 不得单独证明无泄漏。
- [x] 同步 `reproducibility_checklist.md` 的 gate shorthand 为 H1a→H6→H3，并为上述两项增加 machine-readable evidence checks。
- [ ] 修订后再次独立 review；0 Critical/Required 后才允许 Phase 6A mock/file closed-loop planning。

#### 后续 EXEC-BLOCKING implementation tasks（本轮不实施）

- [ ] 实现并测试 immutable scheduled-cell ledger、failure precedence、cell=0 mapping、全 grid 聚合与五项强制 rate 输出。
- [ ] 实现 strict joint-manifest loader/preflight、sealed receipt/hash、跨 split content/path/file-identity/family/generation checks 与 no-glob runner gate。
- [ ] 为不支持 reliable file identity 的平台实现预注册 exemption schema、stronger storage/hash controls 和 formal fail-closed 行为。
- [ ] 若 H2 使用 common evolution seed/provider time block，在 Phase 6/7 前冻结 paired-block bootstrap artifact 与实现测试。

### Phase 6B-T4R GREEN：TOCTOU and formal-leakage fixes（2026-08-17）

- [x] 保留 `_file_identity` / `_hash_explicit_file` RED 测试缝，并将显式文件读取绑定到已打开且经 `fstat` 核验的稳定句柄。
- [x] 比较 pre-open path snapshot、open-handle identity/snapshot、post-read path snapshot；identity、metadata、link 或 path-object 变化均 fail closed。
- [x] 递归拒绝 manifest/header/record/nested metadata 中的 formal split/scope、final-test/lockbox marker 与 artifact promotion。
- [x] 在任何文件读取前拒绝 URI-like 与 UNC/network path syntax；保留 approved-root、no-glob/no-discovery 和 duplicate checks。
- [x] 运行授权 T4/T4R 专项：84 passed、5 skipped、1 existing warning。
- [x] 运行授权 T1+T2+T3+T4 回归：431 passed、5 skipped、1 existing warning。
- [x] 更新 planning 证据；未修改 tests、fixtures、docs、configs、data 或其他生产模块。
- [ ] 提交 Phase 6B-T4R independent implementation review；通过前不进入 T5。
- **Gate：** Gate P2 未关闭；真实 LLM/provider、pilot execution、正式/大规模/final-test 实验继续禁止。

### Phase 6B-T5：PIV-04 validation-receipt RED-only（2026-08-17，协议阻塞）

- [x] 读取 T5 RED-only 授权、PIV-04、manifest validator receipt schema、fixtures 与 integrity receipt-ID 规则。
- [x] 确认 production receipt module 与 T5 test file 均不存在，T1–T4 production hashes 保持不变。
- [x] **BLOCKER resolved by T5C：** 已冻结 raw-manifest-bytes hash 与 canonical manifest-object hash 的唯一字段/语义合同。
- [x] **BLOCKER resolved by T5C：** 已选择扩展未来 T5 输入以接收调用方显式提供的 raw manifest bytes；仍禁止 T5 自行读取 path。
- [x] 协议经 T5C 确认后已新增 `tests/test_pilot_validation_receipt_red.py` 并观察真实 RED。
- **历史状态：** 此 pause 已由 T5C 合同修订解除；随后 T5 RED-only 已完成。Production module 仍未创建，Gate P2 仍未关闭。

### Phase 6B-T5C：minimal validation-receipt contract reconciliation（2026-08-17）

- [x] 采用方案 2：未来 T5/PIV-04 接收调用方显式提供的 `raw_manifest_bytes` 与 `manifest_obj`，但不接收或读取 manifest path。
- [x] 冻结三类 hash domain：receipt `manifest_hash=SHA-256(raw_manifest_bytes)`；可选 `raw_manifest_bytes_hash` 必须与其相等；`manifest_object_hash` 为 canonical parsed-object hash。
- [x] 规定 raw bytes 必须严格解析为单一 JSON object，且解析结果必须与 `manifest_obj`、prevalidation object hash 及可用的 path-result object evidence 一致；任一不一致 fail closed。
- [x] 冻结 receipt 状态仅为 `valid` / `rejected`，并保持 `execution_authorized=false`、`gate_p2_closed=false`；禁止 runner/schedule/provider/candidate/pilot/final-test readiness 字段。
- [x] 区分 manifest artifact header self-hash 与 PIV-04 receipt raw-byte hash；禁止跨 hash domain 复制或改名。
- [x] 记录现有 `pilot_integrity.py` 将 `manifest_hash` 用于 canonical object hash 的命名歧义；本阶段不修改 production，后续必须通过独立 TDD/schema-version 授权迁移。
- [x] 仅更新协议与 planning 文件；未修改 `src/`、`tests/`、`configs/` 或 `data/`，未运行 pytest/provider/pilot/benchmark。
- [x] 后续已在独立授权下完成 **Phase 6B-T5 RED-only：raw-manifest-bytes validation receipt tests**；未进入 GREEN、full validator、runner 或 pilot execution。
- **Gate：** T5C documentation reconciliation complete；Gate P2 未关闭；真实 LLM/provider、pilot execution、正式/大规模/final-test 实验继续禁止。

### Phase 6B-T5 RED-only：raw-manifest-bytes validation receipt tests（2026-08-18，完成）

- [x] 恢复 T5C hash-domain、no-I/O、inert receipt 与 Gate P2 合同。
- [x] 确认未来目标模块尚不存在，且 legacy receipt schema/integrity naming 不得作为新合同 oracle。
- [x] 新增 `tests/test_pilot_validation_receipt_red.py`，覆盖 raw/object hash、strict parse、receipt identity、prevalidation/path evidence、status composition、rejection taxonomy、inert/no-I/O/no-overclaim。
- [x] 只运行新 T5 测试文件：120 collected、120 failed、1 existing warning；全部为预期 missing target module RED，无 syntax/collection/fixture 错误。
- [x] 运行授权 T1–T4 可选回归：431 passed、5 platform skips、1 existing warning；未运行完整套件。
- [x] 核对 production hashes 未变且 `pilot_validation_receipt.py` 仍不存在；未创建 fixture。
- [x] 更新 RED 数量、失败原因、production hash 与下一步独立 GREEN 授权边界。
- [x] 后续已在用户单独授权下完成 **Phase 6B-T5 GREEN**；实现范围保持为最小 pure in-memory receipt builder/verifier。
- **状态：** RED-only complete；禁止 production/doc/config/data 修改，禁止 provider/candidate/pilot/benchmark/final-test，Gate P2 保持未关闭。

### Phase 6B-T5 GREEN：raw-manifest-bytes validation receipt implementation（2026-08-18，完成）

- [x] 恢复 120 个预期 RED 与 T5C hash-domain/no-I/O/inert receipt 合同。
- [x] 仅新增 `src/mrta_rect_coverage/experiments/pilot_validation_receipt.py`，实现最小 pure in-memory builder/verifier。
- [x] 运行 T5 专项至 GREEN：120 passed、1 existing warning；未修改测试。
- [x] 运行授权 T1–T5 五文件回归：551 passed、5 platform skips、1 existing warning；未运行完整套件。
- [x] 完成 no-path/no-glob/no-provider/no-execution 静态审计，并核对既有模块/测试 hashes 未变。
- [x] 更新 production hash、测试结果、能力边界与独立 implementation review gate。
- [x] 完成 Phase 6B-T5 independent implementation review；结论为 0 Critical、1 Required、Request changes。
- **状态：** GREEN tests complete, independent review requests T5R repair；Gate P2 未关闭；禁止真实 LLM/provider、candidate/pilot、benchmark、正式/大规模/final-test 实验。

### Phase 6B-T5 independent implementation review（2026-08-18，完成）

- [x] Tests-first 核对 120 个 T5 合同测试及 pure in-memory/no-I/O/inert 边界。
- [x] 逐段审查 receipt raw/object hash domain、严格 JSON 解析、evidence binding、receipt ID 与 verify 顺序。
- [x] 核查 malformed/self-hashed 上游 evidence 是否可被错误组合为 `valid`；确认存在 1 个 Required fail-closed 缺口。
- [x] 运行授权 T5 专项与 T1–T5 组合回归，核对 hashes 与能力边界。
- [x] 给出 Critical/Required/Consider/FYI 独立结论：**Request changes**；暂不授权 T6。
- [x] Phase 6B-T5R RED-only：新增 malformed/self-hashed prevalidation/path evidence 合同测试。
- [ ] Phase 6B-T5R GREEN：严格验证上游 evidence required fields、types、branch invariants 与安全状态。
- **Gate：** 0 Critical、1 Required；T5 tests GREEN but review requested changes。Gate P2 未关闭，全部 provider/pilot/formal/final-test 禁令继续有效。

### Phase 6B-T5R RED-only：malformed/self-hashed upstream evidence（2026-08-18，完成）

- [x] 恢复 T5 review Required、T5C hash-domain 与 inert/no-I/O gate。
- [x] 读取用户批准的 T5R RED-only 合同；写范围锁定为 T5 测试文件与 planning 文件。
- [x] 新增 self-hashed malformed prevalidation evidence 测试。
- [x] 新增 self-hashed malformed path evidence 测试。
- [x] 覆盖 missing/wrong-type/invalid-enum/branch invariant、replay 与 validator identity 非认证语义。
- [x] 仅运行授权 T5 测试文件并确认预期 RED；运行授权 T1–T5 组合回归。
- [x] 记录 production hash 不变证据并完成 RED planning 收尾。
- [x] 用户已独立授权进入 T5R GREEN；T6 仍未授权。
- **状态：** RED-only complete；220 collected、97 expected failures、123 passed。禁止修改 production/docs/configs/data，禁止 provider/candidate/pilot/benchmark/final-test；Gate P2 未关闭，T6 未授权。

### Phase 6B-T5R GREEN：strict upstream evidence validation（2026-08-20，进行中）

- [x] 恢复 97 个预期 RED、production hashes 与 Gate P2 边界。
- [x] 读取完整 GREEN 授权；写范围锁定为 `pilot_validation_receipt.py` 与 planning 文件。
- [ ] 实现 strict prevalidation evidence schema/type/hash/branch validation。
- [ ] 实现 strict path evidence schema/type/enum/duplicate/branch validation。
- [ ] 保持 receipt-ID-first verify、hash-domain、inert/no-I/O/no-auth 既有合同。
- [ ] 运行授权 T5 专项至 GREEN，再运行授权 T1–T5 回归。
- [ ] 核对未授权模块 hashes、静态能力边界，并更新 planning。
- **Gate：** GREEN implementation only；禁止 tests/其他 production/docs/configs/data 修改，禁止 provider/candidate/pilot/benchmark/final-test；Gate P2 未关闭，T6 未授权。
### Phase 6B-T5R GREEN implementation checklist (active)

- [x] Add strict prevalidation evidence required-field/type/hash/branch invariants.
- [x] Add strict path evidence required-field/type/enum/duplicate-summary/branch invariants.
- [x] Bind the expanded upstream evidence fields into the validation receipt body and ID.
- [x] Make verification reject coherently self-hashed receipts whose supplied upstream evidence is malformed, while preserving receipt-ID-first verification order.
- [x] Run only the authorized T5 test file, then the authorized T1–T5 regression if T5 passes.
- [x] Record results and keep Gate P2 open.

Status: Phase 6B-T5R GREEN implementation complete; independent implementation review is the next permitted step. Gate P2 remains open/unclosed.

### Phase 6B-T5R2 RED-only: exact upstream evidence envelope (2026-09-28)

- [x] Reconcile the T5R review finding against T3/T4/T5 production and target tests.
- [x] Freeze the real T3 prevalidation key set and version (`pilot-prevalidation-core-v1`) from production output.
- [x] Record that current T4 production returns `PilotPathValidationResult`, not the expanded T5 mapping/result-ID envelope.
- [x] Add a positive control produced by the real T3 builder and consumed by the T5 builder/verifier.
- [x] Add missing/wrong-type/wrong-version/old-version/near-miss prevalidation cases.
- [x] Add self-hashed unknown-field cases for prevalidation and the existing T5 path envelope.
- [x] Exercise builder and verifier paths after recomputing upstream IDs; receipt IDs are generated/recomputed coherently by the code under test.
- [x] Run only `tests/test_pilot_validation_receipt_red.py`: 25 expected failures, 221 passes, no collection/import/fixture errors.
- [x] Confirm production hashes unchanged and keep Gate P2 open.

Status: clean RED complete. T6 is not authorized. The next permitted action is a separately authorized T5R2 GREEN limited to exact upstream envelope/version validation.

### Phase 6B-T5R2 GREEN attempt (2026-09-28)

- [x] Re-read the current T3 production result field set and T5 path-side approved mapping before editing.
- [x] Add exact approved key-set checks, exact schema-version constants, and exact version/type checks in `pilot_validation_receipt.py` only.
- [x] Preserve existing hash domains, receipt-ID-first verifier ordering, branch invariants, and inert/no-I/O behavior.
- [x] Confirm all 25 newly added T5R2 cases pass.
- [ ] Target suite is not green: 9 pre-existing baseline tests still expect the stale helper version `pilot-prevalidation-v1` to produce a valid receipt; target result is 237 passed, 9 failed.
- [ ] Do not run T1-T5 regression while the authorized target is not green.

Status: GREEN implementation is blocked by a frozen-test contract contradiction. Strict production behavior is retained; no compatibility exception for the forbidden legacy version was added. Await explicit direction on the test-contract conflict before claiming GREEN.

### Phase 6B-T5R2C test-contract reconciliation (2026-09-28)

- [x] Re-run the authorized T5 target with short tracebacks and map all 9 historical failures to their helper/evidence source.
- [x] Confirm every failure was caused by the default synthetic prevalidation helper emitting forbidden `pilot-prevalidation-v1`; no independent production or new-case failure was found.
- [x] Update only the canonical test helper defaults to `pilot-prevalidation-core-v1`; preserve explicit legacy-version negative cases.
- [x] Re-run T5 target: `246 passed`.
- [x] Run the authorized T1-T5 combined regression: `677 passed, 5 skipped`.
- [x] Recompute production and test hashes; confirm T4-to-T5 expanded path-envelope integration remains unimplemented.

Status: T5R2C complete. The strict production contract was preserved; only stale synthetic helper defaults were reconciled. Next permitted action is Phase 6B-T5R2 independent implementation review. Gate P2 remains open and T6 remains unauthorized.

### Phase 6B-T5R3 RED-only contract recovery (2026-09-28)

- [x] Read the current T4 path validator, T5 receipt consumer, integrity helpers, and T4/T5 tests.
- [x] Recover the actual six-field `PilotPathValidationResult` and its valid/rejected/file-identity/inert semantics.
- [x] Build the T4-to-T5 field/source/transformation gap table before writing code.
- [x] Confirm that `approved_root_fingerprint`, exact duplicate counters, `no_glob_confirmed`, and `no_directory_discovery_confirmed` have no result-level T4 provenance or approved derivation in the current production contract.
- [x] Stop before production/test edits under the prompt's CONTRACT GAP rule; do not invent adapter defaults or claim integration.

Status: CONTRACT GAP, not GREEN. A separately authorized minimal source-contract task is required before a real T4 result can compose the T5 expanded path evidence envelope. Gate P2 remains open and T6 remains unauthorized.

### Phase 6B-T4E RED-only contract recovery (2026-09-28)

- [x] Re-read the current T4 path validator, T5 receipt consumer/tests, integrity helper, and planning records.
- [x] Confirm the current approved-root input, canonical path confinement, glob syntax rejection, non-recursive behavior, duplicate reason categories, and file-identity state.
- [x] Confirm T5's exact path envelope shape and `pilot-path-validation-v1` version.
- [x] Stop under the explicit CONTRACT AMBIGUITY rule: `duplicate_validation_summary` has shape but no frozen counter semantics; `approved_root_fingerprint` has no frozen preimage/algorithm; `no_glob_confirmed` and `no_directory_discovery_confirmed` have unresolved input-vs-capability/invariant semantics.
- [x] Do not modify production or tests; do not run target tests while the contract remains ambiguous.

Status: CONTRACT AMBIGUITY, not RED/GREEN. Await explicit contract clarification before T4 evidence tests or a minimal producer GREEN.

### Phase 6B-T4E-R1: real T4 path-evidence provenance (2026-09-28)

- [x] Complete PRE-RED coherence checks A-E against the real T4 implementation.
- [x] Freeze the four provenance meanings from the authorized normative contract.
- [x] Add focused producer and real T4-to-T5 integration RED tests.
- [x] Observe clean RED: 11/11 failures were the missing canonical T4 evidence producer.
- [x] Implement a minimal T4-side 13-field evidence builder without changing T5.
- [x] Count all five duplicate dimensions in the existing single validation pass.
- [x] Bind the canonical approved-root identity and all provenance fields into the result ID.
- [x] Preserve the existing six-field public T4 validation result and inert gate flags.
- [x] Verify in order: T4E 11 passed; T4 84 passed, 5 skipped; T5 246 passed; authorized combined regression 688 passed, 5 skipped.
- [x] Audit hashes and prohibited capabilities; update planning records only.
- [ ] Phase 6B-T4E-R1 independent implementation review (separate authorization required).

Status: T4E-R1 implementation complete. Gate P2 remains OPEN and T6 remains NOT AUTHORIZED. After independent review, the recommended direction is to pause further pilot-infrastructure expansion and request separate authorization for R0 Core Runtime Bring-Up.

### Phase 6B-T4E-R1R: bounded platform timestamp repair (2026-09-28)

- [x] Recover the review finding: unconditional `st_birthtime_ns` changed non-Windows stable-snapshot semantics.
- [x] Add synthetic platform-neutral RED tests for non-Windows ctime selection, metadata-only ctime mutation, Windows birthtime/fallback, and hardlink identity independence.
- [x] Confirm clean RED: 2 expected semantic failures, 2 platform/identity controls passed.
- [x] Add the minimal `_select_snapshot_change_timestamp()` helper: Windows prefers birthtime with ctime fallback; non-Windows always uses ctime.
- [x] Preserve `(st_dev, st_ino)` hardlink identity and all T4E evidence semantics.
- [x] Run authorized verification in order: timestamp 4 passed; T4E 11 passed; T4 84 passed, 5 skipped; T5 246 passed; combined 692 passed, 5 skipped.
- [x] Complete hashes and capability audit.
- [ ] Phase 6B-T4E-R1R independent implementation review (separate authorization required).

Status: bounded repair complete. Gate P2 remains OPEN and T6 remains NOT AUTHORIZED. Do not enter R0 or any execution phase before the next independent review and explicit authorization.

### Phase R0 Core Runtime Bring-Up (2026-09-28)

- [x] Confirm workspace root, Python project root, package import, and canonical `src`-layout CLI.
- [x] Recover and record the core call chain from config loading through output visualization.
- [x] Verify smoke metadata for `R2_T6_0` and `R2_T10_0`; both use `speed=1.0`.
- [x] Add minimal baseline/ALNS smoke configs with built-in operators, no advisor, and 20 iterations.
- [x] Run baseline and ALNS on both smoke instances with exit code 0.
- [x] Audit route count, exact task coverage, duplicate/invalid IDs, Route-DP evaluation, finite costs, and makespan identity for all four runs.
- [x] Verify same-seed T6 baseline and ALNS reproducibility.
- [x] Run the authorized core target: `10 passed`.
- [x] Add `docs/RUNBOOK.md` with environment, commands, inputs, outputs, limitations, and gate boundaries.
- [x] Record the existing Matplotlib annotation-legend warning as non-blocking.
- [x] Keep Gate P2 open and do not enter R1, T6, provider, candidate, pilot, benchmark, formal, or final-test execution.

Status: R0 runtime evidence is complete. `CORE_RUNTIME_READY = TRUE` is supported by the four successful smoke runs, validity audit, reproducibility audit, core target test, and runbook. The next permitted action is separately authorized `R1 - Scientific Correctness`; do not start it automatically.

### Phase R1 Scientific Correctness (2026-09-28)

- [x] Recover the approved model contract: independent `sweep_speed` and `travel_speed`, with all route components measured in time.
- [x] P0-A RED: 8 expected failures for explicit schema, fail-closed legacy input, speed domain, and three transition classes.
- [x] P0-A GREEN: migrate the two smoke inputs to explicit travel speed and divide all Manhattan transitions by `travel_speed` in `CostMatrix` only.
- [x] P0-B RED: 8 expected failures for the missing complete/partial evaluator contract.
- [x] P0-B GREEN: complete evaluation enforces robot count, known task IDs, exact task universe, and no duplicates; partial evaluation permits only missing tasks.
- [x] Confirm legal empty robot routes remain valid.
- [x] P0-C RED: 5 expected failures for selectable/enableable alias behavior, invalid benchmark labeling, and shipped config drift.
- [x] P0-C GREEN: retain only a private greedy compatibility alias, reject independent enablement, remove the alias from selection/benchmark modes, and correct documentation.
- [x] Confirm greedy insertion scores candidates through `RouteDPEvaluator`.
- [x] Run authorized core regression and all four R0 smoke commands; objective values remain 228/206/1061/904.
- [x] Update README, AGENTS, modeling decisions, research positioning, RUNBOOK, and planning records.
- [x] Keep pilot/gate infrastructure paused; do not run provider, candidate, pilot, benchmark batch, formal/large-scale experiment, final-test, or T6.

Status: R1 complete. Final fresh verification is `54 passed`; all four smoke objectives and validity checks pass. `SCIENTIFIC_CORE_READY = TRUE`. Do not enter R2 automatically. Gate P2 remains OPEN and T6 remains NOT AUTHORIZED.

### Phase R2 Paper-Grade Instance/Data Protocol (2026-09-29)

- [x] Audit current six-line instance schema, loader constraints, smoke data, configs, and existing glob leakage risk.
- [x] Freeze versioned schema identity, compact family taxonomy/matrix, deterministic seed semantics, and split policy.
- [x] Add focused tests first and observe collection RED caused only by the missing protocol module.
- [x] Implement the pure-stdlib deterministic generator, non-overlap placement, production-loader round trip, intrinsic features, exact manifest validation, and manifest-only access.
- [x] Generate six small sanity instances: two each in development, held-out, and final; record file and generation-config hashes.
- [x] Add dataset, family-matrix, and final-test lockbox documentation; update README and runbook boundaries.
- [x] Run final R2 target, authorized core regression, static capability audit, and report `PAPER_DATA_PROTOCOL_READY`.

Status: R2 complete. `PAPER_DATA_PROTOCOL_READY = TRUE`. Gate P2 remains open and T6 remains unauthorized; stop before R3 until separately authorized.

### Phase R3 Optimization Diagnostics (2026-09-29)

- [x] Read the final R3 authorization and preserve all provider/pilot/formal/final/T6 prohibitions.
- [x] Inventory root-level Track A instances with the production filename parser and loader; exclude every final-manifest path.
- [x] Extend solver-free intrinsic features to the complete R3 contract.
- [x] Run representative scale sanity and freeze the 100-iteration built-in-only diagnostic budget and seeds.
- [x] Add RED tests for route balance, decomposition, attribution, state-chain diff, cascade, workload, serialization, and consolidation identity.
- [x] Implement minimal built-in-only R3 instrumentation, output writer, and offline analysis/plotting script.
- [x] Run Track A diagnostics (29 runs) and add only two controlled development families (10 runs).
- [x] Predeclare H1-H3 before held-out access, then run two held-out families (6 runs); never access final.
- [x] Normalize all 45 run IDs without rewriting raw evidence; consolidate 65 inventory rows and 11 behavioral instances.
- [x] Produce versioned CSV/JSON outputs, 8 PDF/PNG plots, and the Q1-Q9/C1-C3 report.
- [x] Verify 12 focused tests and 55 restricted core/R2 tests with no failures or warnings.
- [x] Complete static provider/generated/final boundary audit and confirm pilot/gate hashes unchanged.

Status: R3 complete. `OPTIMIZATION_DIAGNOSTICS_READY = TRUE`; C1/C2 are SUPPORTED and C3 is PARTIALLY SUPPORTED. Gate P2 remains OPEN and T6 remains NOT AUTHORIZED. Stop before R4; R4 requires separate authorization.
# Phase R4 - LLM Research Method Design (frozen design record)

- [x] Real-time verification completed using formal publication pages, arXiv full text and official repositories where available.
- [x] Contribution hierarchy frozen: C1 exact-DP-grounded behavioral operator evolution (primary); C2 exact-DP-response complementary operator set (secondary); C3 structured counterexample-guided revision (optional secondary ablation).
- [x] EoH-S, ReVEL, Behaviour Space Analysis and RouteRepair recorded as direct threats; generic set complementarity, generic behavior feedback/analysis and generic failure repair are not novelty claims.
- [x] Option A modified version frozen as six-stage lexicographic constrained selection.
- [x] Main experiment chain frozen as B0, L0, L1, L2, L3; C3 remains secondary.
- [x] ReVEL-like, EoH-S-like and RouteRepair-like threat comparisons added to the protocol design.
- [x] Added `docs/r4_experiment_comparison_protocol.md` with equal-budget comparisons, contamination rules and stop boundaries.
- [x] R3 held-out contamination frozen: six diagnostic runs are `diagnostic-heldout-consumed`; new selection-validation and confirmatory-heldout splits are required; final-test remains locked.
- [x] `LLM_RESEARCH_METHOD_READY = TRUE`.
- [ ] Do not implement production mechanism, call a real LLM/provider, run candidate/pilot/benchmark/formal/final-test, or enter R5 without separate authorization.

### Phase R5 Mock/File Research Pipeline (authorized 2026-09-30)

- [x] Recover R4 contract-to-code mapping and preserve the trusted-fixture-only boundary.
- [x] Add tests-first coverage for schemas, metrics, archive, lineage, elite retention, eligibility, quality floor, lexicographic selection, budgets, splits and yields.
- [x] Implement trusted scripted fixtures, mock provider and safe file/dry-run provider without importing candidate Python.
- [x] Run Scenarios A-D and authorized R5 scoped verification only.
- [x] Report `MOCK_RESEARCH_PIPELINE_READY = TRUE` only after the full R5 definition of done is freshly verified.
- [x] Stop after R5; do not enter R6, T6, real-provider pilot, formal experiment or final-test.

Status: R5 complete. `MOCK_RESEARCH_PIPELINE_READY = TRUE` is supported by the scoped target and focused regression evidence. Gate P2 remains OPEN; the next permitted action is separately authorized R6 Pre-Real-Provider Experimental Readiness Review.

### Phase R6 - Pre-Real-Provider Experimental Readiness Review (read-only)

- [x] Review R4 frozen method and literature threat contract against R5 code, tests and artifacts.
- [x] Reconcile R3 exact-DP metric definitions, split/contamination rules, hierarchy, budgets and yield denominators.
- [x] Verify trusted fixture/file safety boundary and historical RED taxonomy without running provider/candidate/final-test paths.
- [x] Run scoped fresh verification: 17 R5 tests, 19 R2/R3 focused tests, 36 combined.
- [x] Record `docs/r6_independent_readiness_review.md` and stop at the review gate.
- [ ] Bounded repair of Required findings only after separate authorization.

R6 decision: `Request changes`; Critical 0, Required 6, Consider 3. `REAL_PROVIDER_GENERATION_READY = FALSE`; `UNTRUSTED_EXECUTION_READY = FALSE`; Gate P2 OPEN; T6/R6A not authorized.

### Phase R5R - Research Pipeline Provenance & Trust Repair

- [x] R5R-A RED/GREEN: bind DP evidence to canonical R3 computation and regimes to intrinsic features.
- [x] R5R-B RED/GREEN: bind parent hashes, validate real elite reuse and persist the complete evaluation hierarchy.
- [x] R5R-C RED/GREEN: enforce registry allowlist, hashes and root confinement without execution capability.
- [x] Run target/focused/core regressions and reconstruct the fresh mock run from disk artifacts.
- [x] Record safety/hash evidence and stop without R6/R6A/provider/candidate/final-test/T6 execution.

Status: `R5_REPAIR_READY_FOR_REVIEW = TRUE`; next permitted recommendation is separately authorized R6 independent re-review.
