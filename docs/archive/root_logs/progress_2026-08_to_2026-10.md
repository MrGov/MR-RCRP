# 进度日志

## 2026-08-12：Phase 6B-T1R2 GREEN 启动

- 用户已单独授权最小 GREEN；25 个 T1R2 failures 已在 RED 阶段确认来自 validator 语义旁路。
- 本轮只修改 `src/mrta_rect_coverage/experiments/pilot_contracts.py` 与三份 planning files；tests/fixtures 保持只读。
- 实现范围仅为两个 inert preflight statuses、rejection reason/supporting evidence 映射和 validated evidence 内部一致性；不实现 Gate P2 或任何执行能力。
- 唯一授权测试命令仍为 `python -m pytest tests/test_pilot_contract_schema_red.py -q`。
- 已在 `pilot_contracts.py` 将 runner status enum 收窄为两个 preflight states；future execution lifecycle status 不再属于当前 schema version。
- 已增加 reason-specific supporting-evidence 校验和 validated evidence final-test/glob/provider/scope 内部一致性校验；全部为 pure-data predicates。
- 首次 GREEN 验证：`python -m pytest tests/test_pilot_contract_schema_red.py -q` → **153 passed、0 failed、1 warning**，exit 0（0.32s）。
- 未修改 tests/fixtures；未实现 path access、hash recomputation、runner、manifest-only execution、provider、candidate execution、pilot、benchmark 或 final-test。
- **状态：** T1R2 GREEN complete，等待 independent implementation review；T2、Gate P2/Gate B 与所有执行禁令保持。
- 完成前 fresh 复验同一唯一授权命令：**153 passed、1 warning、exit 0**（0.40s）；planning 更新后结果未漂移。

## 2026-08-12：Phase 6B-T1R2 RED 启动

- 用户授权只新增 runner receipt non-preflight status 与 evidence semantics 旁路测试；生产 `pilot_contracts.py` 和其他 `src/` 全部只读。
- RED 范围包括：未来 execution lifecycle statuses、rejection reason/supporting evidence 映射，以及 validated no-final-test/no-glob/no-real evidence 的内部一致性。
- 将复用现有 runner fixtures，不实现 Gate P2、runner/provider/candidate/pilot，也不接触 final-test；唯一测试命令为 `python -m pytest tests/test_pilot_contract_schema_red.py -q`。
- 已仅向 `tests/test_pilot_contract_schema_red.py` 新增 39 cases；未新增/修改 fixtures，未修改生产实现、configs 或 data。
- 新增类别：20 个 non-preflight status × accepted-execution matrix、12 个 rejection reason/supporting-evidence cases、7 个 validated evidence contradiction cases。
- 唯一测试命令结果：`python -m pytest tests/test_pilot_contract_schema_red.py -q` → **153 collected、25 failed、128 passed、1 warning**，exit 1；warning 为既有 pyreadline DeprecationWarning。
- 25 个失败全部是应拒绝 payload 被 validator 判为 valid；原 114 tests 全部保持通过，新增另有 14 个既有 fail-closed anchors 通过。
- **状态：** Phase 6B-T1R2 RED complete；建议进入单独授权的最小 GREEN。T2、Gate P2/Gate B、真实 LLM/provider、pilot execution、正式/大规模/final-test 实验继续禁止。
- 用户重复提交同一 T1R2 RED 授权后，已先核对磁盘，确认 39 个新增 cases 和三份 planning 结论均已存在，因此未重复编辑测试或 fixtures。fresh 重跑唯一授权命令仍为 **153 collected、25 failed、128 passed、1 warning**（1.04s，exit 1）；25 个失败集合和原因未漂移，生产代码继续未修改。

## 2026-08-12：Phase 6B-T1R independent implementation repair review 启动

- 使用 `planning-with-files` 恢复 Gate/T1R 状态，并按 `code-review-and-quality` 先审测试合同、再审实现。
- 本轮只读审查 `pilot_contracts.py`、目标 tests/fixtures 与 planning records；不修改生产代码、测试、fixtures 或协议正文。
- 唯一允许的执行验证是 `python -m pytest tests/test_pilot_contract_schema_red.py -q`；不运行完整 pytest、provider、candidate、pilot、benchmark、真实 LLM 或 final-test。
- 当前待核对重点：pure-data capability boundary、inert preflight 分支、provider/evidence/receipt invariants、严格枚举、failure summary/output fail-closed 与 T1R RED 回归覆盖。
- 已完整读取 114-case 测试合同：原 T1 coverage 与新增 T1R 旁路回归均保留；新增测试明确覆盖 real/unknown provider、validated/rejected nullability、top-level/evidence mismatch、strict enums、validation receipt branch、failure summaries 与无 schema output entries。
- 测试本身保持 inert contract：合法 `preflight_validated` fixture 被接受，而 `accepted_execution=true` 被拒绝；未把预检通过误写成执行授权。
- **只读检索错误：** 一次组合 `rg` 正则因 PowerShell/转义形成未闭合 group，exit 1；未修改文件。后续改用 literal/分项检索，不重复该表达式。
- 已完整读取 5 个 fixtures 与约 814 行实现。静态 capability boundary 符合 pure-data 范围，但识别两个待完成验证的 Required candidates：未实现的 future runner statuses 仍被 schema 接受且无 state invariants；一般 rejected reason 尚未与对应 evidence 语义绑定。
- fresh 验证仅运行获准命令 `python -m pytest tests/test_pilot_contract_schema_red.py -q`：114 passed、1 个既有 pyreadline warning、exit 0，耗时 0.29s；没有运行完整 suite 或其他项目命令。
- Review 结论：**Request changes（0 Critical、2 Required）**。Required 1 是当前未授权 non-preflight status 可绕过 state invariants；Required 2 是 rejection reason/supporting evidence 和 validated no-final-test evidence 的语义一致性仍不完整。
- 未修改生产代码、tests、fixtures 或协议正文；只更新三份 planning records。T2/Gate P2/Gate B、真实 LLM/provider、pilot execution、正式/大规模/final-test 实验继续 blocked。
- 用户重复请求同一独立复审后，已重新核对磁盘实现与测试覆盖：两个 Required 仍存在，未发现修复提交。再次仅运行授权测试文件，结果为 114 passed、1 个既有 warning、exit 0（0.33s）；verdict 与 Gate 状态不变。

## 2026-08-12：Phase 6B-T1R corrected GREEN 启动

- 用户确认沿用已批准 inert preflight：`preflight_validated.accepted_execution=false`；该状态只证明 contract/schema/scope/provider preflight，不代表 scheduling、candidate/pilot execution 或 Gate P2 closure。
- 本轮只修改 `src/mrta_rect_coverage/experiments/pilot_contracts.py` 与三份 planning files；tests、fixtures、docs、其他生产模块保持只读。
- GREEN 目标是关闭 49 个预期旁路：branch invariants、provider rejection、evidence consistency、exact enums、validation receipt 与 summary/output shape。
- 唯一授权测试命令仍为 `python -m pytest tests/test_pilot_contract_schema_red.py -q`。
- 已只修改 `src/mrta_rect_coverage/experiments/pilot_contracts.py` 与三份 planning files；tests、fixtures、docs、其他生产模块未修改。
- 已收紧 manifest、validation receipt 和 runner receipt 的 exact enums、validated/rejected branch invariants、real/unknown provider rejection 与 top-level/evidence 交叉一致性。
- `preflight_validated.accepted_execution=false` 保持不变；本轮没有新增 scheduled/running/executed 状态，也没有提供任何 execution authorization。
- 已严格校验 `failure_summaries` entry；未定义 output-entry schema 的非空 `output_paths` 采用 fail-closed。
- 唯一授权测试命令 fresh 结果：`python -m pytest tests/test_pilot_contract_schema_red.py -q` → **114 passed、0 failed、1 warning**，exit 0；warning 为既有 pyreadline DeprecationWarning。
- 未实现或调用 path/file access、hash recomputation、runner、provider、candidate execution、pilot execution、benchmark 或 final-test。
- **状态：** Phase 6B-T1R corrected GREEN complete；建议进入独立 implementation review。T2、Gate P2/Gate B、真实 LLM/provider、pilot execution、正式/大规模/final-test 实验仍禁止。

## 2026-08-11：Phase 6B-T1R RED 启动

- 用户授权只修改现有 schema test/必要 fixture 与 planning files；生产 `pilot_contracts.py` 和其他 `src/` 全部只读。
- RED 范围：provider branch、preflight branch、requested/accepted/evidence consistency、exact enums、validation receipt invariants、summary/output entry shapes。
- 识别一处直接合同冲突：approved `preflight_validated` 必须 `accepted_execution=false`，且现有测试已要求 `true` 时拒绝；因此不添加“false 也拒绝”的不可能断言，其余要求照常覆盖。
- validation receipt 沿用 fixtures/实现既有 `status=valid|rejected`，把请求中的 `validation_valid|validation_rejected` 解释为分支语义而非新增字符串枚举。
- 继续禁止 provider/candidate/pilot/benchmark/final-test；唯一允许运行的项目命令是目标 pytest 文件。
- 已仅向 `tests/test_pilot_contract_schema_red.py` 新增 61 个 cases；没有新增或修改 fixture，也没有修改任何生产文件。
- 新增类别：real/unknown provider branch、preflight accepted/rejected invariants、top/evidence mismatch、schema/version/objective enum、validation receipt branch、failure summary/output path shape。
- 唯一执行命令 `python -m pytest tests/test_pilot_contract_schema_red.py -q`：114 collected，49 failed、65 passed、1 warning，exit 1；warning 为既有 pyreadline DeprecationWarning。
- 49 个失败全部来自当前 validator 对不一致 payload 返回 `valid=True`，与 review 指出的旁路一致；无 collection/syntax/import/fixture 错误。原 53 tests 保持通过，另有 12 个新增 fail-closed anchors 通过。
- Phase 6B-T1R RED complete；建议单独授权最小 GREEN。T2、Gate P2/Gate B、真实 LLM/provider、pilot execution、正式/大规模/final-test 实验继续禁止。

## 2026-08-11：Phase 6B-T1 GREEN implementation review

- 只读审查 `pilot_contracts.py`、53 项 RED/GREEN tests、5 个 JSON fixtures 与三份 planning files；未修改生产代码、测试或 fixtures。
- capability boundary 核对：生产模块只导入 dataclasses/math/re/typing；没有 path/file access、symlink/hardlink/inode/file identity、hash recomputation、runner scheduling、provider/candidate/pilot execution。
- fresh verification 仅运行授权命令 `python -m pytest tests/test_pilot_contract_schema_red.py -q`：53 passed、1 个既有 pyreadline warning、0 failed，耗时 0.22s，exit 0。
- Review verdict：Request changes（0 Critical、2 Required）。Required 是跨字段/branch strictness 与相应 RED coverage，不是 capability 越权。
- 已只在 planning files 中登记 T1R：补 exact enums、valid/rejected nullability/state、requested/accepted/evidence consistency、real/unknown non-rejection bypass、summary object shape；修复并复审前不进入 T2。
- Gate P2/Gate B 未关闭；真实 LLM/provider、pilot execution、正式/大规模/final-test 实验继续禁止。

## 2026-08-11：Phase 6B-T1 GREEN 启动

- 用户已授权最小 GREEN；现有 53 项 RED 测试和已批准 schema 文档构成实现合同，不修改测试或 fixtures。
- 实现范围仅为 `mrta_rect_coverage.experiments.pilot_contracts` 的 pure-data validation：required/unknown fields、严格 JSON 类型、枚举、pilot/formal scope、promotion、receipt branch/evidence/state 一致性。
- 明确排除 raw/canonical/receipt hash 重算、路径/文件系统检查、runner 调度、provider/candidate execution、pilot、benchmark 和 final-test 访问。
- 验证范围锁定为 `python -m pytest tests/test_pilot_contract_schema_red.py -q`；不运行完整测试套件。
- 已创建 `src/mrta_rect_coverage/experiments/pilot_contracts.py`；未修改 RED 测试、fixtures、configs、data 或其他生产模块。
- 已实现 `validate_pilot_manifest_schema`、`validate_manifest_validation_receipt_schema`、`validate_runner_receipt_schema` 和不可变 `SchemaValidationResult`。
- 校验器只处理传入的 Python/JSON object；hash/id 仅检查格式，不重算；没有 path access、runner、provider、candidate execution、benchmark 或 pilot 逻辑。
- 唯一测试命令 `python -m pytest tests/test_pilot_contract_schema_red.py -q`：53 passed、1 warning、0 failed，exit 0；warning 为既有 `pyreadline` DeprecationWarning。
- Phase 6B-T1 GREEN complete，建议进入独立 GREEN review；Gate P2/Gate B 未关闭，真实 LLM/provider、pilot execution、正式/大规模/final-test 实验继续禁止。
- 完成前 fresh verification 重跑同一唯一授权命令：53 passed、1 个既有 warning、0 failed，耗时 0.19s，exit 0。

## 2026-08-11：Phase 6B-T1 RED 启动

- 已将 Phase 6B-R 独立复审结果登记为 Approve（0 Critical、0 Required），并接受首个 bounded implementation-task 授权。
- 本轮使用 planning-with-files、brainstorming、executing-plans、using-git-worktrees 与 test-driven-development 工作流；现有设计/计划已通过用户与独立复审，因此不重新扩展设计。
- Git 检测确认项目根不是 repository，无法创建 worktree；保持固定项目根并严格限制修改范围。
- 授权范围按上一轮建议限定为 RED-only：只新增 pilot manifest/receipt schema fixtures 与 validation 失败测试；不修改生产代码，不进入 GREEN。
- 真实 LLM/provider、provider/candidate execution、pilot、benchmark、正式/大规模/final-test 实验继续禁止；Gate P2/Gate B 均未关闭。
- 已审查 README、pyproject、现有 operator-evolution schema/hashing helpers、pytest 约定与 manifest/receipt 规格；确认没有可复用的 pilot contract validator。
- 已冻结 T1 测试接口：future `mrta_rect_coverage.experiments.pilot_contracts` 提供 manifest、validator receipt、runner receipt 三个纯数据 schema validators，统一返回结构化 validity/reasons；本轮不创建该生产模块。
- 新增 `tests/test_pilot_contract_schema_red.py` 和 `tests/fixtures/pilot_contracts/` 下 5 个 JSON fixtures；未创建 `src/mrta_rect_coverage/experiments/pilot_contracts.py`。
- `pytest tests/test_pilot_contract_schema_red.py --collect-only -q`：首次 55 collected、exit 0；随后收紧错误语义，移除两个重复 type/promotion 参数。
- `pytest tests/test_pilot_contract_schema_red.py -q` 最终结果：53 collected，52 failed、1 passed、1 个既有 pyreadline deprecation warning，exit 1。通过项仅验证 fixture 文件集合与 JSON object 解析；52 个失败均为预期缺失模块 `mrta_rect_coverage.experiments.pilot_contracts`。
- RED 分组：manifest schema 33 failures；manifest-validation receipt schema 5 failures；runner receipt schema 14 failures。没有 collection error、fixture parse error、provider/candidate/pilot invocation。
- Phase 6B-T1 RED complete；等待用户单独授权最小 GREEN。GREEN 仅允许纯数据 schema validators，不自动扩展到 hashing/path/runner/provider/pilot。
- 完成前 fresh verification：目标 fixture 文件 5 个、RED test 文件存在、`src/mrta_rect_coverage/experiments/pilot_contracts.py` 不存在；重新运行专项测试仍为 52 failed、1 passed、1 warning（exit 1），与预期 RED 完全一致。

## 2026-08-11：Phase 6B-R protocol repair 启动

- 已恢复上轮 Request changes（0 Critical、4 Required groups）状态并读取附件中的正式修订合同。
- 已登记 failure taxonomy、receipt canonicalization/evidence、4 个 provider 负例和 Gate lifecycle 四条修订主线。
- 本轮仅修改规划文档；不修改代码/配置/数据/测试，不运行测试、provider、pilot、真实 LLM 或实验，不进入 implementation authorization。
- 已修订 `pilot_observability_schema.md`：`invalid_solution` 移出 execution axis，增加 contract、feasibility、optimization、structural axes 及跨轴 invariants；failure type 降为派生摘要。
- 已同步 legal/invalid/unsafe/timeout test expectations，并补充 baseline makespan finite/>0 与 transient-event/terminal-summary 边界。
- 已重构 `pilot_runner_receipt_spec.md`：requested/accepted 字段分离，real/unknown/glob/formal/mismatch 决策顺序唯一，五个 evidence objects 成为 required fields。
- 已冻结 runner 与 validator receipt 的 RFC 8785、UTF-8、排除自身 ID/signature fields 的 SHA-256 derivation，并修正 rejection example 使其符合 schema。
- 已同步 pilot-local split 命名、provider rejection fixtures 和 Phase 6B 的 17-scenario exit criterion。
- 已新增 T14–T17：real provider、unknown alias、artifact mock/runtime real、artifact real/runtime mock-file 四个专门负例，均要求 invocation/import/call counter 为零并绑定 Gate P2 evidence。
- 已同步 Gate 生命周期：Phase 6A passed、Gate P1 planning-only、Phase 6B-R awaiting review、implementation task authorization ≠ Gate P2、Gate B independent/incomplete；所有 Gate P2 checkboxes 保持 open。
- 两轮只读回查确认主要修订落盘；识别 T11 旧布尔字段和 canonical sorted-key 明示两个尾项，下一步仅修正文档后做合同核验。
- 已关闭两个尾项：T11 使用具名 glob evidence object；runner/validator 明示 RFC 8785 deterministic sorted-key rule。
- 只读文档合同核验结果：45/45 checks PASS、0 failures、exit 0；未运行 pytest 或任何项目代码。
- Phase 6B-R documentation repair 完成并等待独立复审；未进入 implementation authorization，Gate P2 checkbox 全部 open。
- 收尾只读核验：taxonomy、requested/accepted schema、五个 evidence objects、canonical IDs、T14–T17、Gate lifecycle/open checkboxes、planning blockers 共 11/11 PASS，exit 0；该核验不是项目测试。

## 2026-08-11：Phase 6B independent implementation-planning review 启动

- 已恢复 planning 状态并读取总体计划、基础设施任务分解和三层 observability schema。
- 已确认 planning-only、provider/pilot/formal/final-test 禁令与三层 record ownership 基本成立。
- 初步发现 candidate execution/contract taxonomy 可能退化；将与 validator、runner receipt、test plan 和 Gate P2 证据交叉核对后定级。
- 本轮不修改受审正文，不运行测试、provider、pilot、真实 LLM 或实验。
- 已读取 validator、runner receipt、13-case test plan 与 Gate P2 文档；确认 receipt schema/evidence、rejection intent、receipt hash derivation、real-provider rejection coverage 和 Gate current-status 存在 Required candidates。
- 独立复审完成：0 Critical、4 Required groups，结论为 Request changes；当前不允许进入 implementation task authorization。
- 已把四组修订项写入 `task_plan.md`：failure taxonomy、receipt schema/ID/hash、real-provider negative coverage、Gate lifecycle state。
- 本轮只更新 `task_plan.md`、`findings.md`、`progress.md`；未修改七份受审规格或算法代码，未运行测试/provider/pilot/真实 LLM/实验。
- 完成前只读文档矩阵核验：8 个通过控制、5 个开放模式（其中 receipt evidence 与 rejection schema 合并为同一 Required group），与最终 0 Critical / 4 Required groups verdict 一致；命令 exit 0。该矩阵不是项目测试。

## 2026-08-11：Phase 6B implementation planning 启动

- 已读取用户附件规格并恢复 Phase 6A-R approved 状态；Phase 6B 仅做规划，不实现、不测试、不执行。
- 已将 Phase 6B 标记为 `in progress`，登记六份目标规格、Gate P2 evidence 补充和三份 planning records 更新任务。
- 真实 LLM/provider、mock/file provider、pilot execution、formal/large-scale/final-test experiments 继续禁止；Gate P2 未关闭。
- 为读取附件和恢复 planning 状态，使用了只读 `Get-Content`/session-catchup；未执行项目代码、测试、provider 或实验。此项作为“不要运行任何命令”限制下的必要只读偏差透明记录；后续仅使用文件补丁编辑。
- 已创建 `docs/phase6b_implementation_plan.md`：冻结 planning-only 权限、未来依赖顺序、fail-closed/research-accounting invariants 和 Phase 6B exit criteria。
- 已创建 `docs/pilot_infrastructure_task_breakdown.md`：把 validator、fixtures、runner、scheduled-run/failure-zero accounting、candidate fixtures 和 Gate P2 evidence 拆成可单独授权的后续 TDD slices。
- 已创建 `docs/pilot_observability_schema.md`：将 run/operator-type、candidate、evaluation-cell 分层，显式定义层级键、failure-zero/batch-inconclusive precedence、denominators 和 replay invariants。
- 已创建 `docs/pilot_manifest_validator_spec.md`：定义 strict inputs/output union、validation order、hash/path/duplicate/file-identity 规则、pilot/formal/final-test rejection、诚实限定的 no-final-test/no-glob evidence，以及 valid/rejection receipt examples。
- 已创建 `docs/pilot_runner_receipt_spec.md`：定义 receipt states、required fields、structured command intent、validation binding、scheduled-run/output reconciliation 和机器可审计 Gate P2 evidence。
- 已创建 `docs/mock_file_pilot_test_plan.md`：规划 13 个必需场景，并把 Gate P2 前 inert/injected component evidence 与 Gate P2 后 mock/file execution 分开，避免循环授权。
- 已更新 `docs/pilot_execution_gate_plan.md`：补充全部保持未勾选的 machine-auditable closure evidence；Phase 6B 文档本身不关闭 Gate P2。
- Phase 6B planning 已完成：六份目标规格均已创建，Gate P2 evidence plan 已引用；未创建或修改任何 `src/configs/data/tests` 内容。
- 完成时做了逐要求的文档合同核对：范围、A–G infrastructure、三层 schema、validator/runner receipts、13 个 test scenarios 和 Gate P2 非循环证据均有明确落点。因用户禁止命令/测试，本轮未运行 pytest、lint、provider、pilot 或自动化文档检查；结论仅表示规格已写入，不表示实现通过。
- 下一步仅为独立 Phase 6B planning review；不自动进入 implementation、Gate P2 或 Phase 6C。

## 2026-08-11：Phase 6A independent planning review 启动

- 已恢复 task plan、findings 与 progress，并运行 session catch-up；无额外未同步输出。
- 审查范围为五份 Phase 6A planning 文档与三份 planning records；不修改算法代码或受审正文。
- 本轮不运行测试、provider、pilot、真实 LLM、benchmark 或实验；Phase 6B/6C/7 继续未授权。
- 已完整阅读五份 Phase 6A 规划和三份 planning records，并逐项核对 planning-only 边界、artifact 隔离、mock/file 场景、observability 与 Gate P2。
- 已完成跨文档术语与门禁一致性矩阵核验：11/11 PASS。
- 最终结论：0 Critical、0 Required；Phase 6B implementation planning 可在单独授权后进入，但不得自动执行 Phase 6B、Gate P2 或 pilot。
- Consider：后续 schema 需规范 run/operator-type、candidate、cell 的记录层级；Gate P2 validator/runner evidence 应机器可审计；evaluation grid 的层级键应显式记录。
- 本轮未修改五份受审规划正文或算法代码；未运行测试、provider、pilot、真实 LLM、benchmark 或实验。

## 2026-08-11：Phase 6A mock/file closed-loop planning 启动

- 已读取附件规格并恢复 planning 状态；Phase 6A 仅允许文档规划，不执行 pilot。
- 已登记五份目标文档、Phase 6A/6B/6C/7 分层、Gate P2 条件和 mock/file 四类候选闭环。
- 真实 LLM/provider、mock/file provider execution、pytest、benchmark、formal/final-test/large-scale experiments 均保持禁止。
- 本阶段不修改 `src/configs/data/tests`，不创建或读取任何 final-test artifact，不自动进入 Phase 6B。
- 已创建 `docs/phase6a_mock_file_closed_loop_plan.md`：定义 planning-only 权限、闭环顺序、artifact flow、failure handling 和退出边界。
- 已创建 `docs/pilot_manifest_plan.md`：定义 `pilot_nonformal`/`pilot`、pilot-scoped hashes、non-promotion、runner/receipt 与 invalid-manifest 规划。
- 已创建 `docs/mock_file_validation_plan.md`：定义 mock batches 与 file legal/invalid/unsafe/deployment-blocked fixtures 的期望状态。
- 已创建 `docs/closed_loop_observability_plan.md`：定义 candidate/execution/deployment/attribution/cell/run 字段和 invariants。
- 已创建 `docs/pilot_execution_gate_plan.md`：定义 Gate P2 七类证据、outcome states 和 stop conditions；当前状态保持 `planning_only`。
- 已在 `task_plan.md` 登记 Phase 6B infrastructure planning、Phase 6C Gate-P2 execution 和 Phase 7 real-LLM preflight，均未进入或执行。
- 已做内存中规格自审：五份文档覆盖附件八部分要求，无 TBD/TODO，无性能/实现完成主张；下一步仅为 Phase 6A planning review。
- 未运行 pytest、benchmark、mock/file/real provider、solver 或实验；未进入 Gate P2/Phase 6B，未创建 formal/final-test artifacts。
- 为读取用户附件与强制技能说明，使用了只读 `Get-Content`；未执行任何项目代码或验证命令。此项作为“不要运行任何命令”限制的透明偏差记录。

## 2026-08-11：Phase 5B-R4 independent review 启动

- 已按 `planning-with-files` 恢复 task plan、progress 与 findings，并运行 session catch-up；无额外未同步输出。
- 按 `code-review-and-quality` 以 correctness、cross-document consistency、fail-closed boundary 和 authorization semantics 为审查轴。
- 本轮只读协议正文；只允许更新 planning review records，不运行测试、实验、solver 或 provider，不进入 Phase 6A。
- Planning 更新第一次因错误假设 progress 标题为“项目进展记录”而匹配失败；已读取实际标题“进度日志”并改用精确上下文，未重复失败操作。
- 已完成第一轮跨文档检索：16 项请求中的 pilot-only matrix/rule、scoped hashes、scope enums、promotion prohibition、formal freeze ordering、final-test isolation 和 Gate P1/P2 均有直接证据。
- 正在核对 formal exclusion receipt 的逐字段消费合同及是否仍存在旧的无作用域冻结/授权措辞；尚未形成最终 verdict。
- 第二轮检索确认无旧生命周期冲突；Gate P1 仅授权 planning，Gate P2/Gate B/real-LLM gates 保持独立未完成。
- 初步定级为 0 Critical、0 Required；一个非阻塞 Consider 是在 `manifest_spec.md` §7.3 的 pilot leakage 枚举中显式写出 pilot matrix/rule hashes，以与 exclusion receipt 字段列表完全一一对应。下一步执行只读 16 项 review matrix 后形成最终 verdict。
- 已执行只读 16 项 review matrix：16/16 PASS；Gate B 检出 36 个开放 `EXEC-BLOCKING`，real-provider 门禁检出 2 个开放 `REAL-LLM-BLOCKING`。
- Final verdict：Approve，0 Critical、0 Required、1 Consider。允许进入 Phase 6A mock/file closed-loop planning，但 Gate P2/pilot execution、真实 LLM/provider、正式/大规模/final-test 实验继续禁止。
- 未修改任何协议正文或算法代码，未运行测试、实验、solver 或 provider；本轮仅更新 `task_plan.md`、`findings.md`、`progress.md` review records。

## 2026-08-11：Phase 5B-R4 启动

- 使用 `planning-with-files` 恢复状态；当前没有 `spec-driven-development` skill，按用户给出的 A–G 条款作为正式验收规格。
- `brainstorming` 设计门禁已核对；用户请求已明确批准 pilot-only/formal 双身份域设计，无需新增选择题或替代方案。
- 已登记唯一 Required、manifest schema 修订、artifact promotion prohibition、formal preflight rejection 和 Gate P 拆分任务。
- 范围仅限指定协议/planning Markdown；不修改 `src/configs/data/tests`，不运行测试、实验、solver 或 provider，不进入 Phase 6A。
- 已读取 experiment/instance/lockbox/manifest/pilot/no-go/reproducibility 的相关条款，确认 schema hash authority、instance-generation freeze boundary、artifact promotion 和 Gate P 层级需要同步修改。
- 已逐段定位旧冲突：三份 lifecycle 文档仍保留“完整 matrix 在任何实例生成前冻结”，pilot plan 尚无 pilot-only hash/不可提升身份合同，Gate P 尚未拆分 planning 与 execution。下一步以同一 scope contract 同步正文。
- 已完成 experiment/instance/lockbox/pilot lifecycle、Gate P1/P2 和 reproducibility checklist 的主体同步；manifest schema 还将补充 pilot hash 的显式 audit aliases，随后做只读一致性检查。
- Manifest pilot receipt 已增加两个 pilot-scoped audit alias；第一轮跨文档核对确认 scope/promotion/gate 关键文字齐全，并修正 instance formal lifecycle 列表编号。尚需执行完整的纯文档合同与范围检查，再更新完成状态。
- 已同步 lockbox 文档的 R4 状态标签；准备执行 fresh 文档合同检查。未运行测试、代码、实验或 provider。
- 已完成 7 份协议文档与 3 份 planning 文件的 R4 修订。Pilot/formal 生命周期、scope-aware manifest schema、artifact promotion prohibition、pilot exclusion receipt、Gate P1/P2 和 formal lockbox ordering 已同步。
- 第一次完整纯文档合同核验：42 checks、0 failures、exit 0，并输出 10 个目标文件 SHA-256；未运行 pytest、compileall、solver、benchmark、实验或 provider。
- 当前结论：Phase 5B-R4 revision complete、等待 independent review；不进入 Phase 6A，真实 LLM/provider、正式/大规模/final-test 实验继续禁止。
- Planning 收尾后的第二次 fresh 合同核验：44 checks、0 failures、exit 0；7 份协议 hashes 与第一次一致。该核验仅为文档检查，未执行任何测试或实验。
- 修改顺序冻结为：manifest scope schema → experiment/instance/lockbox lifecycle → pilot plan → Gate P/reproducibility → 纯文档一致性核验。

## 2026-08-07：Phase 5B-R3 开始

- 已读取附件中的 Phase 5B-R3 正式规格；当前环境没有 `spec-driven-development` skill，按附件逐项作为验收合同。
- 授权范围仅为指定协议/planning 文档；不修改 `src/configs/data/tests`，不运行测试、实验、solver、provider 或真实 LLM，不进入 Phase 6A。
- 已登记两项修订：manifest failure 的互斥 cell/batch taxonomy，以及 pilot preflight/formal joint-preflight 双生命周期。
- 下一步读取七份协议的当前相关章节，按 statistics → manifest → experiment/gates/lockbox → reproducibility/tables 顺序修改。

## 2026-08-07：Phase 5B-R3 文档修订完成

- **Required 1 closed：** `docs/statistical_analysis_plan.md` 现以互斥 taxonomy 区分 localized generated-result/artifact failure 与 batch input/manifest/split/lockbox integrity failure。前者保留 cell 并按 policy estimand 记 `0`；后者标 contaminated/inconclusive、不产生 effect value，但保留 scheduled/integrity accounting。
- **Required 2 closed：** `docs/manifest_spec.md`、`docs/experiment_protocol.md`、`docs/experiment_no_go_checklist.md` 与 `docs/final_test_lockbox_protocol.md` 现分离 train/dev pilot preflight 和 formal three-manifest joint preflight；pilot 不创建/读取 final-test，formal receipt 必须早于 formal prompt/operator generation、formal train/dev evaluation、formal portfolio selection 和 final-test run。
- **同步项：** reproducibility/result tables 使用 `fully attributable family rate`；baseline pairing missing 固定为 batch-inconclusive；unsupported hardlink/file identity 对 formal execution 继续 fail closed 或要求预注册 stronger-control exemption。
- **范围与执行：** 仅修改允许的协议/planning Markdown；没有修改 `src/`、`configs/`、`data/`、`tests/`。按用户要求未运行 tests、compileall、solver、experiment 或 provider。
- **Gate：** 本轮不进入 Phase 6A；真实 LLM/provider、正式实验、大规模实验和 final-test 继续禁止。下一步仅可提交 independent protocol review。
- **完成前验证：** 运行 27 项纯文档合同断言，27 PASS、0 FAIL、exit 0；覆盖 taxonomy、cell/batch action、双 preflight lifecycle、receipt ordering、file-identity gate、H1a→H6→H3、执行禁令及 merge-marker 检查。未运行代码测试。


## 2026-08-07：Phase 5B-R2-R2 当前版本独立复审开始

- 使用 `planning-with-files` 和 `code-review-and-quality`，重新从磁盘审查用户列出的七份更新文件，并交叉读取 experiment/lockbox/no-go governing clauses。
- 协议正文只读；不修改 `src/configs/data/tests`，不运行测试、实验、solver、provider 或真实 LLM。
- 初步证据显示 16 项核心控制仍存在，但 manifest-failure scope 与 joint-preflight lifecycle/gate synchronization 两项冲突也仍存在。
- 下一步执行本轮 18 项 review matrix，并据此形成独立 verdict；Phase 6A 与全部执行权限保持 blocked。

## 2026-08-07：Phase 5B-R2-R2 当前版本独立复审完成

- 只读 18 项 review matrix：16 PASS、2 FAIL；`scope_conflict=True`、`order_conflict=True`、`gate_sync_gap=True`。
- FAIL 2：manifest violation 的 cell-zero/batch-contamination scope 不唯一。
- FAIL 18：仍有 2 个 Required，joint-preflight lifecycle 与 Gate B/lockbox governing clauses 未同步。
- Verdict：Request changes（0 Critical、2 Required）；Phase 6A 不获准。
- 仍禁止真实 LLM/provider、正式实验、大规模实验和 final-test。
- 仅修改 `task_plan.md`、`findings.md`、`progress.md`；协议正文、算法代码、配置、数据和测试保持只读。
- 未运行测试、compileall、solver、benchmark、实验或 provider。
- 完成前只读核验：6/6 verification checks PASS、0 failures、exit 0；确认 16 个预期 core passes、检查项 2/18 的两个预期 failures、Request-changes verdict、全部 NO-GO 和无 merge markers。该核验支持本轮审查结论，不代表协议通过。


## 2026-08-07：Phase 5B-R2-R 独立复审开始

- 使用 `planning-with-files` 恢复上下文，按 `code-review-and-quality` 对 Phase 5B-R2 做 review-only 复核。
- 已读取统计、manifest、reproducibility 和 result-table 的相关完整章节；没有修改受审协议、算法代码、配置、数据或测试。
- 初步确认 cell hierarchy、failure-zero、全 grid aggregation、supplementary complete-case、五项 rates、joint manifest preflight、cross-split fail-closed、unsupported file identity 与 H1a gate 均有文本证据。
- 正继续核实 cell-local manifest failure 与 batch contamination 的适用范围是否唯一；最终 verdict 前 Phase 6A 和全部执行禁令保持 blocked。
- Cross-document 核对确认两个 Required candidates：manifest failure 的 cell/batch classification 未定义；joint preflight 与 train/dev pilot 顺序冲突，且 Gate B/lockbox execution checklist 未同步 joint receipt/file-identity authority。
- 未运行 pytest/compileall、solver、benchmark、实验、provider 或真实 LLM。
- **记录错误：** 首次同步第二轮 findings 的组合补丁把 progress 标题误作为 `findings.md` context，导致 patch verification failed 且未应用；随后拆分为正确文件上下文，不重复该错误。

## 2026-08-07：Phase 5B-R2-R 独立复审完成

- **核心审查：** 16/16 requested controls PASS，覆盖 evaluation cell、partial failure mapping、complete-case 禁令、全层级聚合、five rates、joint preflight、cross-split/file-identity、family non-bypass、H1a gate 与执行禁令。
- **Cross-document hazards：** `hazard_manifest_scope=True`、`hazard_preflight_order=True`；Gate B 和旧 lockbox checklist 均未出现 joint receipt authority。
- **Verdict：** Request changes（0 Critical、2 Required）。Required 1 是 cell-local manifest failure 与 batch contamination 的互斥分类；Required 2 是 joint-preflight 生命周期和 governing gate/checklist 同步。
- **Gate：** 不允许进入 Phase 6A；真实 LLM/provider、正式实验、大规模实验和 final-test 继续禁止。
- **修改范围：** 仅更新 `task_plan.md`、`findings.md`、`progress.md`；未修改受审协议、算法代码、配置、数据或测试。
- **未执行：** 未运行 pytest/compileall、solver、benchmark、实验、provider 或真实 LLM。
- **完成前只读核验：** 21/21 review-evidence checks PASS、0 failures、exit 0；其中 16 项证明核心控制存在，3 项证明两处协议冲突与 gate-sync gap 确实存在，另 2 项确认 verdict/NO-GO 和无 merge markers。该结果支持 Request changes，不代表协议已获批准。


## 2026-08-07：Phase 5B-R2 启动

- **状态：** in progress；Phase 6A 仍 blocked。
- 恢复 Phase 5B-R 复审状态并确认剩余 2 个 Required 协议问题。
- 已复读 statistical analysis、manifest、reproducibility 与 result-table 文档，准备按唯一验收合同修订。
- 本轮锁定为文档/planning 修改；不修改生产代码、配置、数据或测试，不运行测试、实验、真实 LLM 或 provider。
- 下一步：先冻结 cell-level 主分析规则，再加入跨 split joint preflight，并同步报告与复现证据。

## 2026-08-07：Phase 5B-R2 协议修订完成，待验证/复审

- 修改 `docs/statistical_analysis_plan.md`：定义完整 evaluation cell、互斥 failure precedence、failure-to-zero policy estimand、全 cell 聚合、whole-run 退化关系、supplementary complete-case 边界和五项强制 rates。
- 修改 `docs/manifest_spec.md`：增加 joint split-preflight artifact/receipt、merged-record fail-closed checks、sealed lockbox ordering、unsupported file-identity policy 与 formal exemption contract。
- 同步 `docs/reproducibility_checklist.md`：新增 joint-preflight/cell-grid evidence，修正 `H1a→H6→H3`，记录条件性 H2 paired-block preregistration。
- 同步 `docs/result_table_plan.md`：Table 0/1/S1/9 纳入 cell accounting、failure-aware rates、two-part/dominated sensitivity 与 joint-preflight evidence。
- 更新 `task_plan.md`、`findings.md`、`progress.md`；新增 Phase 6/7 的 cell-ledger、joint-runner、platform identity 和 paired-block EXEC-BLOCKING tasks，但未开始实施。
- Git 范围审计不可用：项目根目录没有 `.git` metadata；不将失败的 `git status/diff` 作为完成证据。
- 未运行 pytest、compileall 或其他测试；未运行 solver、benchmark、实验、真实 LLM/provider；未修改 `src/`、`configs/`、`data/` 或 `tests/`。

### 完成前文档核验

- 第一次 28 项 literal audit 为 27 PASS / 1 FAIL；失败来自检查器错误地搜索英文 `full family parameter tuple`，而正文实际是“完整 family parameter tuple”，不是协议缺失。
- 修正检查词后重新从磁盘执行完整 audit：`document_contract_checks=28`、`document_contract_failures=0`、exit 0；cell hierarchy/failure classes/zero policy/全层聚合/五项 rates、三 manifest receipt/跨 split identities/path controls/file-identity policy/lockbox isolation、H1a gate、H2 paired-block、result tables 和 gate 状态全部 PASS。
- **最终状态：** Phase 5B-R2 documentation revision complete，等待独立 research-protocol review；未进入 Phase 6A。真实 LLM/provider、正式/大规模/final-test 实验继续禁止。

## 2026-07-15：第一阶段项目审查

- **状态：** complete
- **已完成：**
  - 读取 `planning-with-files` 工作流要求。
  - 确认项目根目录原先不存在 `task_plan.md`、`findings.md`、`progress.md`。
  - 创建三份规划文档并记录审查范围、约束和关键问题。
  - 定位实际 Python 项目根目录为 `mrta_rect_coverage/`，完成指定目录的首轮文件清单。
  - 阅读 `AGENTS.md`、`README.md`、`pyproject.toml`、全部 YAML 配置、算子演化文档与根级实验包装脚本。
  - 记录研究目标、两类 LLM 参与路径、离线算子演化闭环、问题输入/状态规则及文档与默认配置不一致处。
  - 审查确定性核心与 heuristics：状态生成、成本矩阵、路线 DP、多机器人 makespan、构造器、局部搜索、ALNS 和冻结算子接入。
  - 识别单位一致性、解可行性校验、DP-aware 消融等需要后续确认的研究问题。
  - 审查 advisor、prompt、LLM runtime、三种 provider、候选验证、benchmark evaluator、反馈聚合、跨轮闭环与冻结流程。
  - 发现 repair 评价参照、best 选择、未使用 `top_k_to_keep` 和候选执行安全边界等关键风险。
  - 阅读全部测试文件，核对其行为契约与覆盖缺口。
  - 枚举 data、scripts、outputs、generated operators，并核实现有演化产物全部候选无效却仍被选为 best。
  - 完成后续六阶段研究与工程路线图。
- **当前状态：**
  - 第一阶段审查已结束，等待用户确认后续研究口径与代码修改授权。
- **本轮允许修改的文件：**
  - `task_plan.md`
  - `findings.md`
  - `progress.md`

## 轻量检查结果

| 检查 | 结果 |
|---|---|
| 目录与文件清单 | 指定目录均存在于 `mrta_rect_coverage/` 子目录；已记录模块分布 |
| Git 仓库识别 | 顶层和项目子目录均失败；本阶段不修复，改用显式文件核对 |
| `pytest --collect-only -q` | 成功；收集 82 个测试，耗时 0.20s；1 条外部 `pyreadline` 弃用警告 |
| 耗时实验/完整测试 | 未运行，符合用户约束 |

## 未决问题

- 工作区顶层 `.git/` 为何无法被 Git 识别（不属于本阶段修复范围）。
- 三份规划文档长期应保留在工作区顶层，还是后续迁入 Python 项目根目录。
- 跨任务曼哈顿距离是否隐含单位速度，还是应转换为移动时间。
- repair benchmark 应与原完整解、固定 repair baseline，还是当前轮 incumbent 比较。
- 项目下一阶段以稳定 baseline 为主，还是正式推进 ALNS + LLM 算子演化论文主线。
- 现有全部无效的演化产物是否应保留作失败样例，还是后续在获得授权后清理/隔离。

## 下一步

1. 请用户确认建模单位、研究主线和 repair benchmark 参照。
2. 获得修改代码授权后，从 `task_plan.md` 阶段 2 开始，以测试驱动方式修正评价协议。
3. 在评价与安全边界稳定前，不运行真实 LLM 生成代码或大规模实验。

## 本轮文件变更范围

- 仅创建/更新工作区顶层 `task_plan.md`、`findings.md`、`progress.md`。
- 未修改 `mrta_rect_coverage/` 下任何源代码、配置、测试、文档、数据或实验产物。

## 2026-07-15：正式项目根目录确认

- **状态：** complete
- **确认结果：**
  - 正式代码项目根目录固定为 `mrta_rect_coverage/`。
  - 当前 `task_plan.md`、`findings.md`、`progress.md` 均已位于 `mrta_rect_coverage/` 根目录。
  - 工作区顶层未发现同名旧规划文件，因此当前无需迁移，也没有删除任何文件。
  - 已重新读取项目根中的三份规划文件以及 `README.md`、`AGENTS.md`。
- **迁移方案（仅在未来再次发现外部旧副本时采用，本次不执行）：**
  1. 以 `mrta_rect_coverage/` 下三份文件作为唯一活动版本。
  2. 先比较旧副本与活动版本，将尚未同步的事实和进度合并进项目根文件。
  3. 在确认内容、时间和引用均已同步后，再单独征得删除或归档旧副本的授权。
- **后续路径约定：**
  - 所有代码审查、测试、文档、配置与实验命令均以 `mrta_rect_coverage/` 为工作目录和项目根。
  - 规划文件中的相对路径均相对于 `mrta_rect_coverage/` 解释。
- **说明：**
  - 上一节关于“规划文件位于工作区顶层”的记录属于当时的历史状态，不再代表当前文件位置。
- **本次修改：**
  - 仅更新 `mrta_rect_coverage/progress.md`；未修改业务代码、配置、测试或实验文件。

## 2026-07-15：Phase 3 RED——算子演化评价与选择协议

- **状态：** complete（仅完成 TDD 的 RED，本轮不进入实现）
- **使用工作流：** `planning-with-files`、`test-driven-development`
- **新增测试文件：** `tests/test_operator_evolution_protocol_red.py`
- **生产代码修改：** 无
- **目标测试命令：** `pytest -q tests\\test_operator_evolution_protocol_red.py`
- **结果：** 8 failed，0 passed；所有新增测试均因目标行为缺失而按预期失败。

### 失败测试与原因

| 测试 | 预期合同 | 当前失败原因 |
|---|---|---|
| `test_repair_metrics_compare_candidate_with_fixed_baseline_repair` | 固定 greedy repair 为基准；正 delta 表示候选更优 | 当前仍用部分解作基准，实际 delta `-51.0`，正确基准下应为 `+14.5` |
| `test_ineligible_candidate_is_not_selected_as_best[invalid]` | validation invalid 不得入选 | 当前仍返回 `repair_r000_000` |
| `test_ineligible_candidate_is_not_selected_as_best[error]` | trial error 候选不得入选 | 当前仍返回 `repair_r000_000` |
| `test_ineligible_candidate_is_not_selected_as_best[timeout]` | timeout 候选不得入选 | 当前仍返回 `repair_r000_000` |
| `test_all_invalid_candidates_produce_no_frozen_operator` | 全部 invalid 时 registry 为空且不复制文件 | 当前仍复制 invalid 候选并写入冻结 registry |
| `test_top_k_to_keep_limits_next_round_feedback` | `top_k_to_keep=1` 时下一轮 top/weak 各最多 1 个 | 当前 feedback 各包含 2 个，配置未生效 |
| `test_frozen_operator_import_failure_is_recorded` | 导入失败形成结构化 fallback event | 当前 `fallback_events` 为空，导入失败被静默忽略 |
| `test_frozen_operator_runtime_failure_is_recorded` | 运行失败记录算子、阶段与异常原因 | 当前执行 greedy fallback 但不记录事件 |

### RED 判定

- 测试均已被 pytest 正常收集并执行，没有 collection error。
- repair 测试通过真实 benchmark case、固定 repair 和真实 evaluator 比较指标方向。
- invalid/error/timeout 测试通过完整 evolution loop 检查落盘 summary/best 行为。
- top-k 测试检查真实跨轮 feedback，而非只测试配置对象。
- fallback 测试触发真实动态导入与运行期回退路径。
- pytest 另报告外部 `pyreadline` 弃用警告及既有 `.pytest_cache` 写权限警告；不影响 8 个预期失败的判定。

### 下一步

1. 保持这些测试为 RED 证据，不修改其期望来迎合当前实现。
2. 用户授权进入 GREEN 后，按最小实现顺序修复 repair baseline、候选资格过滤、top-k 和 fallback observability。
3. 每完成一个最小实现即重跑对应测试，再运行既有相关回归测试。

## 2026-07-15：Phase 3 GREEN——最小协议实现

- **状态：** complete
- **范围：** 仅修正 evaluator、候选选择/反馈、freeze/registry 与 frozen fallback observability；未改变 ALNS 主搜索流程，未调用真实 LLM，未运行实验。

### 修改文件

- `src/mrta_rect_coverage/llm/operator_evolution/evaluator.py`
  - repair 候选改为和固定 greedy repair 的完整解比较。
  - `makespan_delta = baseline_makespan - candidate_makespan`，正值表示候选更优；relative improvement 使用 baseline makespan 作分母。
- `src/mrta_rect_coverage/llm/operator_evolution/evolution_loop.py`
  - 将 `top_k_to_keep` 传入跨轮 feedback。
  - best selection 排除 validation invalid、error、timeout 或 invalid solution 候选；全部不合格时 best 保持空对象/空 ID。
- `src/mrta_rect_coverage/llm/operator_evolution/feedback_builder.py`
  - 拒绝小于 1 的 top-k，避免无意义配置。
- `src/mrta_rect_coverage/llm/operator_evolution/freezing.py`
  - freeze 前独立复核候选资格，防止不合格 best JSON 被复制和注册。
- `src/mrta_rect_coverage/heuristics/alns_solver.py`
  - 为 frozen operator 缺文件、缺函数、导入异常和运行异常记录结构化 fallback events。
  - `ALNSResult` 暴露 fallback events；原有 greedy/random fallback 与搜索策略不变。
- `tests/test_operator_evolution_protocol_red.py`
  - 沿用上一轮已验证的 8 个 RED 合同；本轮未放宽测试期望。

### 测试结果

| 测试 | 结果 |
|---|---|
| `pytest -q tests\\test_operator_evolution_protocol_red.py` | 8 passed，2 warnings，0 failed |
| 相关 evaluator/loop/freezing/frozen integration/ALNS 回归 | 首次 2 failed（既有 generated operator 文件及 pytest cache 写权限）；获准写测试产物后重跑为 16 passed，1 warning |
| `pytest -q` | 90 passed，1 warning，0 failed，2.73s |

- 完成记录后再次执行最终验证：`pytest -q` → 90 passed，1 warning，0 failed，2.13s。

- 唯一持续警告来自外部 `pyreadline` 对 `collections.Callable` 的弃用用法。
- 测试会刷新 `generated_operators/round_000`、`round_001` 中的 mock 候选并产生 `__pycache__`；未删除或清理这些既有测试/实验产物。

### 只读复核结论

- 核心 8 个 RED 合同均已转为 GREEN，完整测试通过。
- 未扩大修复范围；新发现的问题已写入 `findings.md`。

### 剩余风险

1. destroy invalid trial 的 success 语义仍需独立 RED 测试。
2. feedback 的 top candidates 尚未按 eligibility 过滤。
3. timeout 仍为软标记，不会终止挂起候选。
4. fallback events 尚无独立聚合计数/原因直方图或 CSV 字段。
5. frozen operator 返回值与最终 feasibility 尚未强校验。

## 2026-07-21：LLM 算子演化正式设计规格

- **状态：** complete
- **范围：** 仅创建设计规格并更新规划记录；未修改业务代码、测试、配置或实验实现，未运行真实 LLM 和耗时实验。

### 已完成

- 读取并遵循 `planning-with-files`；`spec-driven-development` 在当前技能列表中不可用，经用户批准后采用已评审的混合规格方案。
- 确认三份规划文件均位于正式项目根 `mrta_rect_coverage/`。
- 复核 `README.md`、`AGENTS.md`、现有算子演化文档、evolution loop、candidate loader、evaluator、feedback、metrics、freezing 和 LangChain 配置。
- 创建 `docs/llm_operator_evolution_spec.md`，正式规定：
  - LLM 只生成/修订 ALNS repair/destroy，EA/ALNS 搜索，DP 精确评价；
  - generation、validation、sandbox、benchmark、ranking、elite、feedback、revision、freeze、deployment 生命周期；
  - AST 门禁、隔离进程、硬超时、stdout/stderr/exception 捕获和 SHA-256 code hash；
  - repair 固定 baseline、destroy 固定 repair、硬门槛、多实例多 seed 与 fallback 归因；
  - top-k、diversity、失败反馈、problem-specific hints、逐轮输入输出文件契约；
  - 四项论文贡献候选、消融和 LLM/sandbox 成本分析。
- 将需要实现的安全、审计、elite/diversity、评价语义和论文实验事项写入 `task_plan.md`。
- 将当前实现与目标规格差距写入 `findings.md`。

### 本轮未决问题

1. `docs/modeling_decisions.md` 与 `docs/evaluation_protocol.md` 当前不存在；需确认是未落盘、被移除，还是后续需按 Phase 2 决策重建。
2. 空路线是否允许以及移动成本是否显式采用 `Manhattan distance / speed`，仍需由建模决策文档统一。
3. AST 允许列表、跨平台 sandbox 资源限制和 trial schema 的具体实现尚待 Phase 4 TDD。
4. diversity 的相似度指标与门槛、elite quality/diversity 配额需在实现前形成可测试的详细决策。

### 下一步

1. 进入 Phase 4 RED：先为危险 AST、隔离进程、硬超时、输出捕获、code hash 和 freeze hash 验证编写失败测试。
2. 恢复或重建建模与评价协议文档，明确 speed、空路线和 feasibility 的权威口径。
3. 安全边界稳定后，再实现显式 elite/diversity/lineage 和论文级多实例、多 seed 实验协议。

## 2026-07-22：Phase 4 RED——候选算子执行边界

- **状态：** RED complete，等待 GREEN 授权
- **范围：** 只新增测试并更新规划记录；未修改任何生产代码，未调用真实 LLM，未运行大规模实验，也未使用 `security-and-hardening` skill。

### 新增测试文件

- `tests/test_operator_execution_boundary_red.py`
- pytest 成功收集 18 个测试：11 个静态危险能力参数、1 个状态/记录测试、1 个硬超时测试、4 个无有效候选参数和1个 fallback 归因测试。

### RED 执行证据

| 命令 | 结果 |
|---|---|
| `pytest --collect-only -q tests\\test_operator_execution_boundary_red.py` | 18 collected，0 collection errors，1 个外部弃用警告 |
| `pytest -q tests\\test_operator_execution_boundary_red.py` | 最终验证：18 failed，0 passed，1 个外部弃用警告，3.58s；失败均来自目标能力尚未实现 |
| 既有 candidate loader/evaluator/protocol/freezing 相关测试 | 12 passed，0 failed，1 个外部弃用警告，0.41s |

### 失败测试与原因

| 测试 | 参数/数量 | 预期失败原因 |
|---|---:|---|
| `test_static_validation_rejects_dangerous_candidate_capabilities` | 11 | loader 未在动态 import 前做 AST 检查；`os`、`subprocess`、`socket`、`open`、`eval`、`exec`、`__import__`、`pathlib`、`urllib` 及明显属性调用均被错误标为 `valid` |
| `test_candidate_records_distinguish_validation_and_execution_outcomes` | 1 | round candidate records 缺少 `execution_status`，也尚未统一记录 `fallback_used`、`fallback_reason`、`runtime_ms` 和 `code_hash` |
| `test_benchmark_timeout_is_hard_and_recorded` | 1 | benchmark 会等待慢候选自然返回；timeout 只是事后软标记，没有硬终止，最终测试以 100 ms 预算运行 2 秒候选，实测约 2.03 秒才返回 |
| `test_no_eligible_candidate_is_explicit_and_cannot_freeze` | 4 | invalid、runtime error、timeout、invalid solution 虽不会成为 best/frozen，但 summary 缺少显式 `repair_selection_status = no_valid_operator` |
| `test_frozen_runtime_fallback_is_not_credited_as_generated_success` | 1 | fallback event/history 缺少统一 `fallback_used`、`fallback_reason`、`llm_operator_success`；当前搜索奖励路径也没有明确阻止给发生 fallback 的 frozen operator 记分 |

### RED 判定

- 所有测试均被正常收集和执行，不存在测试语法、导入或 fixture 错误。
- 静态危险代码全部放在不可达分支中，RED 过程未实际打开文件、建立网络连接或启动子进程；测试验证的是 import 前 AST 拒绝契约。
- runtime error、timeout 和 invalid solution 均通过真实 evolution loop/benchmark 路径触发，而不是直接构造伪造 metrics。
- timeout 测试同时约束硬终止时间和落盘 `execution_status=timeout`。
- fallback 测试强制选择真实 broken frozen repair，要求回退可观测且不获得生成算子成功/奖励归因。

### 下一步

1. 保持本测试文件为 RED 证据，不调整期望去适配现有实现。
2. 用户授权 GREEN 后，按最小顺序实现：AST gate → 状态/审计 schema → 隔离硬超时 → 显式 no-valid selection → fallback 归因与冻结复核。
3. 每个最小实现先跑本文件对应测试，再跑既有 operator evolution/frozen integration 回归，最后运行 `pytest -q`。

## 2026-07-22：Phase 4 GREEN——候选算子执行边界最小版

- **状态：** complete（RED→GREEN）
- **范围：** 只修改 operator evolution、安全执行和 frozen deployment 归因边界；未修改 problem model、route DP、solution evaluator、baseline、local search、ALNS 邻域/接受判定，未调用真实 LLM，未运行实验。

### 修改文件

- `src/mrta_rect_coverage/llm/operator_evolution/candidate_security.py`（新增）：import 前 AST 拒绝危险模块/调用/反射；计算规范化源码 SHA-256。
- `src/mrta_rect_coverage/llm/operator_evolution/candidate_execution.py`（新增）：path proxy；spawn 子进程 import/call；硬超时后 terminate/kill/reap。
- `src/mrta_rect_coverage/llm/operator_evolution/candidate_loader.py`：删除主进程 dynamic import/smoke，改为 AST validation、isolated smoke 与 proxy。
- `src/mrta_rect_coverage/llm/operator_evolution/schemas.py`：validation record 增加 execution status、runtime 和 code hash。
- `src/mrta_rect_coverage/llm/operator_evolution/evaluator.py`：隔离执行文件候选；输出明确状态和六个要求字段；invalid/error/timeout 不计 success。
- `src/mrta_rect_coverage/llm/operator_evolution/evolution_loop.py`：CSV/JSON 增加审计字段；summary 增加 `no_valid_operator`；eligibility 增加 execution/fallback gate。
- `src/mrta_rect_coverage/llm/operator_evolution/freezing.py`：freeze 要求 execution success、无 fallback、hash 完整匹配；registry 记录 hash。
- `src/mrta_rect_coverage/heuristics/alns_solver.py`：仅调整 frozen integration 可观测性和奖励归因；hash 校验、fallback 字段、iteration contamination 标记、发生 fallback 的 generated reward 置零。未改变候选解、局部搜索、接受判定、最优解更新或 operator selection。
- `tests/test_operator_evolution_protocol_red.py`：必要适配旧 fallback exact-dict 期望；未删除或放宽 Phase 4 RED 测试。

### RED→GREEN 结果

| 测试组 | RED | GREEN |
|---|---:|---:|
| 11 个危险 AST 参数 | 11 failed | 11 passed |
| 候选状态与六字段记录 | 1 failed | 1 passed |
| 100 ms hard timeout | 1 failed（2 秒候选约 2.03 秒后返回） | 1 passed（在测试的 1 秒上限内硬终止） |
| invalid/error/timeout/invalid-solution no-valid 与 freeze | 4 failed | 4 passed |
| frozen fallback 成功/奖励归因 | 1 failed | 1 passed |
| 合计 | 18 failed | 18 passed |

### 测试命令与结果

| 命令 | 结果 |
|---|---|
| `pytest -q tests\\test_operator_execution_boundary_red.py` | 18 passed，0 failed，1 warning，4.24s |
| `pytest -q tests -k "operator_evolution or frozen_operator or alns_solver"` | 21 passed，87 deselected，0 failed，1 warning，8.22s |
| `pytest -q` | 最终验证：108 passed，0 failed，1 warning，14.80s |

- 唯一警告仍来自外部 `pyreadline` 的 `collections.Callable` 弃用用法。
- 额外静态自审验证：`sys`、`shutil`、`requests`、`compile`、`builtins.open` 与 dunder 访问全部被拒绝；`python -m compileall -q src\\mrta_rect_coverage` 成功。

### 实现中发现并处理的问题

1. AST 初版把正常 `list.remove` 误判为文件删除；读取实际 validation message 后，仅删除过宽的属性禁令。
2. Windows CRLF 使“源码字符串 hash”和“原始 bytes hash”不一致；freeze/deploy 统一使用规范化文本 hash。
3. 首次独立诊断未设置 `PYTHONPATH=src`；设置后成功复现，未修改安装环境。

### 剩余风险

1. 当前是最小静态门禁与进程隔离，不是完整 OS sandbox；尚无 CPU、内存、文件系统或网络 namespace 限制。
2. 子进程 stdout/stderr 尚未捕获和限流，exit code/termination reason 尚未形成完整逐 trial schema。
3. smoke timeout 固定为 1000 ms，candidate import timeout 固定为 1 秒；未来需配置化并记录环境能力。
4. 为兼容 Phase 3 的 in-memory callable 单元测试，该可信路径仍使用同进程软计时；provider 持久化候选始终走 path proxy。
5. AST denylist 只能阻断明显危险能力，不能证明任意 Python 代码安全。

### 下一步

- 停留在 Phase 4 完成状态，不进入 Phase 5。
- 后续如获授权，优先补 Phase 4 deferred 的 stdout/stderr、资源限制、逐 trial manifest 与更强 adversarial static-validation tests。

## 2026-07-31：Phase 4 GREEN 代码审查

- **状态：** review complete；发现 Critical 阻断项，未批准真实 LLM 或 Phase 5
- **范围：** 只审查 operator execution boundary 及 frozen deployment 相关实现，并更新 `findings.md`、`task_plan.md`、`progress.md`；未修改生产代码、测试、配置或实验逻辑，未运行真实 LLM/实验。

### 审查结论

| 等级 | 数量 | 结论 |
|---|---:|---|
| Critical | 3 | 子进程不是 capability sandbox；frozen operator 绕过隔离边界并在主进程执行；frozen 返回值缺强 feasibility/contract 校验，可能污染接受、success 与 reward |
| Required | 4 | validation-invalid 的 rate 分类失真；配对 fallback 可交叉污染另一 generated operator 的 reward；候选文件读取失败不结构化；stdout/stderr 与资源/退出信息未受控 |
| Consider | 4 | 每 trial spawn/import 成本；全局属性 denylist 误杀风险；逐 trial manifest 不足；`not_evolved` 与 `no_valid_operator` 未区分 |
| FYI | 2 | benchmark 状态与 eligibility/freezing gate 主路径已建立；现有测试覆盖直接危险能力与基本 timeout/fallback，但未覆盖上述对抗与部署路径 |

### 六个维度判定

- **Correctness：部分通过。** 顶层 `execution_status` 能区分 validation/runtime/timeout/invalid/success，summary 能显式给出 no-valid；但 validation-invalid 的 rate 字段重复/错误分类，frozen 正常返回但不可行时没有 invalid gate。
- **Security boundary：未通过真实 LLM 准入。** AST denylist 与 hard timeout 能挡住显式危险调用和挂起，但不能限制子进程权限；frozen 路径又直接回到主进程 import/call。
- **Research validity：未通过。** benchmark selection/freeze 会排除已知 invalid/error/timeout/fallback；但部署期不可行返回和 repair/destroy 配对 fallback 仍可污染奖励归因。
- **Architecture：部分通过。** validator、process executor、evaluator、freezing 的模块划分基本清楚；selection 仍嵌在 evolution loop，frozen adapter 没有复用统一 execution outcome/validation boundary。
- **Performance：需量化。** 正常文件候选每个 smoke/trial 都 spawn/import；功能测试规模可接受，但尚无大候选池开销证据。
- **Reproducibility：部分通过。** 已记录 `runtime_ms`、`code_hash`、`fallback_reason`；缺少逐 trial seed/instance/environment、wall overhead、exit/output 信息。

### 验证证据

| 命令 | 结果 |
|---|---|
| `pytest -q` | 108 passed，0 failed，1 warning，15.53s |

- 唯一 warning 来自外部 `pyreadline` 对 `collections.Callable` 的弃用用法。
- Git 改动范围命令无法使用：当前工作区及正式项目根均未被 Git 识别为仓库；因此本轮通过用户指定范围、现有 Phase 4 记录和显式源码/测试文件清单审查。

### 下一步

1. 先为 frozen 缺 hash、重新 AST 校验、硬超时、不可行返回和配对 fallback 污染增加 RED 测试。
2. 再为 AST 别名/间接能力绕过、stdout/stderr 洪泛与候选文件读取失败增加 RED 测试。
3. 经用户另行授权后按 `task_plan.md` 的 Phase 4R 做最小整改；整改完成并复审前，不运行真实 LLM、不进入 Phase 5。

## 2026-07-31：Phase 4B RED——operator execution boundary hardening

- **状态：** RED complete；等待 GREEN 授权
- **范围：** 只新增 `tests/test_operator_execution_boundary_hardening_red.py` 和更新规划记录；生产代码、既有测试、配置和实验逻辑均未修改。
- **已写合同：** sandbox capability 等级/real-provider safe 标记、frozen metadata/AST/主进程隔离/超时、repair/destroy contract、invalid reward、joint fallback 归因、互斥 failure breakdown、`source_read_failed`、有界 stdout/stderr、exit code 与 wall time。
- **约束：** 未调用真实 LLM，未进入 Phase 5，未运行大规模实验。

### RED 执行证据

| 命令 | 结果 |
|---|---|
| `pytest --collect-only -q tests\\test_operator_execution_boundary_hardening_red.py` | 27 collected，0 collection errors，1 个外部弃用 warning |
| `pytest -q tests\\test_operator_execution_boundary_hardening_red.py` | 27 failed，0 passed，1 warning，7.08s；全部因目标生产合同缺失 |
| feasibility/attribution 短回溯诊断 | 5 failed，22 deselected，0 test-construction errors，0.38s |
| `pytest -q tests\\test_operator_execution_boundary_red.py` | 既有 Phase 4 回归 18 passed，0 failed，1 warning，4.12s |

### 失败测试与原因

| 测试组 | 数量 | 当前失败原因 |
|---|---:|---|
| `test_execution_result_declares_timeout_only_not_capability_sandbox` | 1 | `CandidateExecutionResult` 没有 `sandbox_level`，无法区分 timeout boundary 与 capability sandbox |
| `test_real_llm_candidate_is_not_marked_safe_under_timeout_only_boundary` | 1 | real-provider 候选记录没有 `sandbox_level`/`safe_to_execute`，当前无法阻止误标安全 |
| `test_frozen_operator_missing_required_metadata_is_rejected[...]` | 4 | registry loader 忽略缺失的 hash、validation、execution 和 safe metadata，仍把算子注册为 generated frozen operator |
| `test_frozen_operator_source_is_ast_validated_again_before_loading` | 1 | frozen 源码加载前不重跑 AST/security validation，含 `import os` 的文件仍被注册 |
| `test_frozen_operator_is_not_imported_into_alns_main_process` | 1 | frozen 模块直接进入主进程 `sys.modules` |
| `test_frozen_repair_failure_uses_fallback_and_records_distinct_status[...]` | 2 | runtime fallback event 缺 `execution_status`；2 秒 frozen 调用无硬超时，约 2 秒后作为成功返回 |
| `test_frozen_repair_invalid_solution_falls_back_to_complete_unique_solution[...]` | 2 | missing/duplicate-task repair 返回没有 contract gate，也没有 invalid fallback event |
| `test_frozen_destroy_invalid_partition_is_rejected[...]` | 2 | lost/overlap/duplicate partition 没有一致性校验，也没有 invalid fallback event |
| `test_frozen_invalid_solution_is_not_rewarded_as_generated_success` | 1 | invalid repair 没有被识别，未形成 invalid/fallback 证据，无法阻止 success/reward 污染 |
| `test_joint_fallback_reward_has_explicit_non_polluting_attribution[...]` | 2 | history 没有精确 `reward_attribution`，也没有 `attribution_ambiguous` 联合试验标记 |
| `test_failure_types_are_mutually_exclusive_in_candidate_metrics[...]` | 4 | validation row 仍重复计 error+invalid；所有行均缺 `failure_type` 和互斥 breakdown |
| `test_evolution_summary_preserves_failure_type_breakdown` | 1 | evolution summary 没有跨候选 failure-type 聚合 |
| `test_*candidate_source*source_read_failed` | 3 | 缺失文件、非法 UTF-8 和读取 PermissionError 直接逸出 loader，没有结构化 `source_read_failed` |
| `test_candidate_output_is_captured_bounded_and_reports_wall_time` | 1 | executor 没有 output limit 参数，也不记录 stdout/stderr/truncation/exit code/wall time |
| `test_timeout_records_exit_code_and_wall_time` | 1 | timeout 能终止候选，但结果没有 `exit_code` 和 `wall_time_ms` |

### RED 判定

- 27 个新增测试全部先于生产实现编写并亲眼确认失败，符合严格 TDD RED。
- 失败来自缺失行为而非拼写、收集、fixture 或测试替身错误；源码读取 PermissionError 的 monkeypatch 仅替代不可移植的 OS 权限条件，断言仍针对真实 loader 返回合同。
- 未修改任何生产代码、既有测试、配置或实验逻辑；未删除或 skip 测试，未调用真实 LLM，未运行实验。
- 唯一 warning 仍来自外部 `pyreadline` 对 `collections.Callable` 的弃用用法。

### 下一步 GREEN 计划（需用户授权）

1. 先扩展 schema/metadata：`sandbox_level`、`safe_to_execute`、failure type、process observability 字段。
2. 将 source read 纳入 loader 结构化边界，生成 `source_read_failed`，并阻断后续 validation/benchmark/selection/freeze。
3. 扩展隔离执行结果：有界 stdout/stderr、truncation、exit code、wall time；保留 `timeout_only` 的诚实标注。
4. frozen registry 强制 metadata/hash，重新 AST 校验，并通过子进程代理执行与硬超时，不再主进程 import/call。
5. 在 frozen adapter 增加 repair 完整唯一性和 destroy partition contract；invalid 走 fallback 且 reward 为零。
6. 增加显式 reward attribution/ambiguous 标记及互斥 failure breakdown 聚合。
7. 依次运行新增 27 测试、既有 operator evolution/ALNS 回归、完整 `pytest -q`，随后重新代码审查。

### 仍不在 Phase 4B 最小 GREEN 内的风险

- CPU/内存配额、子进程树清理、文件系统/网络 namespace、环境变量隔离及跨平台 OS sandbox 降级策略仍待后续 hardening；即使 27 个测试转绿，也只能声称受控 timeout/restricted-process 边界，不能声称完整 capability sandbox。

## 2026-07-31：Phase 4B GREEN 实现

- **状态：** GREEN complete；等待独立代码复审
- **当前完成：** 扩展 validation/execution schema；source read 失败已结构化；subprocess result 已增加 `timeout_only` 标签、stdout/stderr 捕获与限长、truncation、exit code 和 wall time。
- **当前修改：** `schemas.py`、`candidate_execution.py`、`candidate_loader.py`。
- **边界声明：** 当前仍是 timeout-limited subprocess，不是 capability sandbox；未运行真实 LLM。
- **首个 GREEN 子集：** sandbox/source-read/executor/metrics 相关 12 passed、15 deselected、1 个外部 warning；candidate row 已贯通 safe/sandbox metadata，failure breakdown 已互斥聚合。
- **新增修改：** `evaluator.py`、`evolution_loop.py`、`freezing.py`。
- **Frozen 边界已实现：** registry metadata/hash/AST 复核、`CandidateProxy` 隔离调用、repair/destroy contract fallback、invalid/runtime/timeout 状态记录和 joint attribution ambiguity；仅修改 `heuristics/alns_solver.py` 的 frozen adapter/归因边界。
- **相关回归首次结果：** 26 passed、1 failed、108 deselected；唯一失败是 Phase 3 手写 runtime registry 缺少 Phase 4B 必需 metadata。生产 gate 保持不变，已仅适配该测试 fixture。
- **首次完整测试：** 134 passed、1 failed；唯一失败是 Phase 4 的另一个手写 runtime registry 只有 hash、缺 validation/safe metadata。已仅补齐 fixture，生产安全门槛不变。
- **完成前自审修正：** 输出限制由“父进程收到后截断”加强为“child 写入时即有界”，避免 noisy candidate 在回传前无限占用 StringIO；需重新执行全部验证。

### 最终修改文件

- `src/mrta_rect_coverage/llm/operator_evolution/schemas.py`
- `src/mrta_rect_coverage/llm/operator_evolution/candidate_execution.py`
- `src/mrta_rect_coverage/llm/operator_evolution/candidate_loader.py`
- `src/mrta_rect_coverage/llm/operator_evolution/evaluator.py`
- `src/mrta_rect_coverage/llm/operator_evolution/evolution_loop.py`
- `src/mrta_rect_coverage/llm/operator_evolution/freezing.py`
- `src/mrta_rect_coverage/heuristics/alns_solver.py`（仅 frozen 加载/调用/contract/归因边界）
- `tests/test_operator_evolution_protocol_red.py`、`tests/test_operator_execution_boundary_red.py`（仅为新 registry metadata 合同补齐 legacy fixture）
- `task_plan.md`、`findings.md`、`progress.md`

### 最终验证证据

| 命令 | 结果 |
|---|---|
| `pytest -q tests\\test_operator_execution_boundary_hardening_red.py` | 27 passed，0 failed，1 warning，8.66s |
| `pytest -q tests -k "operator_evolution or frozen_operator or alns_solver"` | 27 passed，108 deselected，0 failed，1 warning，10.41s |
| `pytest -q` | 135 passed，0 failed，1 warning，27.11s |

- 唯一 warning 仍来自外部 `pyreadline` 对 `collections.Callable` 的弃用用法。
- 未运行真实 LLM、真实 provider 或大规模实验；未进入 Phase 5。

### 剩余风险与下一步

1. 当前是 timeout-limited subprocess，不是 capability sandbox；CPU/内存、后代进程树、文件系统/网络 namespace 与环境变量隔离仍未实现。
2. timeout 强杀前未通过 pipe 回传的 stdout/stderr 可能丢失；成功/异常完成路径已在 child 写入时有界。
3. 每 trial 仍会 spawn/import 新进程，Windows 开销尚未量化或优化。
4. 真实 LLM 候选现在明确 `safe_to_execute=False` 且不能 best/freeze；在更强隔离或人工风险确认流程复审通过前仍不得运行。
5. 下一步仅进行 Phase 4R 独立代码复审；不进入 Phase 5。

## 2026-07-31：Phase 4R 独立复审开始

- **状态：** in progress
- **范围：** 只审查 Phase 4B operator execution boundary hardening 的测试与生产调用链；不实现新功能、不调用真实 LLM、不运行实验。
- **复审门槛：** frozen validation/metadata/contract、failure-type 对 selection/freeze/reward 的隔离、fallback 归因、timeout-only sandbox 标注及全量测试。
- **初步范围核对：** hardening RED 文件含 697 行合同测试；核心审查文件包括 validator/executor/loader/evaluator/evolution/freezing 与 847 行 `alns_solver.py`，尚未形成严重级别结论。
- **测试先行审阅（第一段）：** 已确认测试覆盖缺失 metadata、部署前 AST 复验、主进程不 import 和 timeout-only 标签；复审将额外检查 metadata 值伪造/类型异常与加载后源码变化等未由字段缺失测试直接覆盖的边界。
- **测试先行审阅（完成）：** 合同测试覆盖 repair 完整唯一性、destroy 分区、invalid reward、双 generated fallback 归因、failure-type 互斥、source-read 失败及输出可观测性。测试对 registry metadata 主要覆盖“字段缺失”，因此实现审查将验证字段值、路径/hash 绑定和 TOCTOU，而不把现有绿色测试视为充分安全证明。
- **实现调用链发现：** frozen 注册只做一次 hash/AST，运行时 proxy 按可变路径重新 import，已确认存在 TOCTOU validation 绕过（Critical）；contract validator 对 `routes=None` 等畸形结果会抛异常而非 `invalid_solution` fallback（Required）。
- **演化门禁发现：** real-provider 的 `safe_to_execute=False`/risk-ack 仅被 selection/freeze 使用，smoke 与 benchmark 仍会执行候选（Critical）；selection/freezing 对缺失安全字段有 fail-open 默认值，benchmark 畸形返回也可能中断整轮（Required）。
- **标注复核：** executor 自身诚实标为 `timeout_only`；但 `docs/operator_evolution.md` 仍描述旧的 soft timeout，README 直接给真实 provider 命令，和当前未执行 risk-ack gate 的事实组合后具有误导性，列为 Required 文档/入口整改。
- **只读/轻量诊断：** AST validator 接受 `io.FileIO` 别名；缺 safety/failure 字段 row 同时被 selection/freezing helper 接受；畸形 `routes=None` 从 contract helper 抛出 `TypeError`。诊断未运行候选代码、未调用 LLM、未修改生产代码。
- **相关回归：** `pytest -q tests -k "operator_evolution or frozen_operator or operator_execution_boundary or alns_solver"` → 66 passed，69 deselected，1 warning，24.27s。
- **全量验证：** `pytest -q` → 135 passed，1 warning，26.99s；唯一 warning 仍来自外部 `pyreadline` 的 `collections.Callable` 弃用。

### Phase 4R 复审结论

- **状态：** complete；Request changes
- **Critical：** 2 项——real-provider unsafe/risk-ack 未阻断 smoke/benchmark；frozen validation/hash 与按路径执行之间存在 TOCTOU。
- **Required：** contract/benchmark 对畸形返回异常封闭；selection/freezing 缺证据 fail closed；registry 解析结构化失败；安全文档与 CLI 口径同步。
- **通过项：** 完整 metadata 的 canonical failure rows 不进入 best/freeze；frozen fallback/invalid 不计 generated success，reward 归因符合保守协议；executor 正确标注 `timeout_only`；candidate source-read failure 和执行可观测字段已接通。
- **后续：** 先为复审缺口补 RED 测试，再做最小修复并再次复审。Critical 清零前不进入 Phase 5、不运行真实 LLM。
- **变更边界：** 本轮没有修改任何生产代码或测试，只更新 `task_plan.md`、`findings.md`、`progress.md`。

## 2026-07-31：Phase 4C RED 开始

- **状态：** in progress
- **范围：** 只新增 execution gate、TOCTOU 与复审 Required 项的失败测试；不修改生产代码、既有测试或文档正文。
- **约束：** 不调用真实 LLM/provider，不运行实验，不进入 Phase 5。
- **测试策略：** 使用静态 provider/test fixture；真实 provider 仅作为 provenance metadata 字符串。smoke/benchmark 未执行性使用窄 monkeypatch，其他断言走真实 loader/evolution/executor/frozen ALNS 路径。
- **新增文件：** `tests/test_operator_execution_gate_toctou_red.py`，覆盖默认 execution gate、smoke/benchmark 阻断、AST 别名、expected hash、frozen 源码替换、reward、畸形 contract/benchmark、fail-closed metadata、registry 鲁棒性与文档口径。
- **生产边界：** 尚未修改任何 `src/`、配置、既有测试或文档正文。
- **收集结果：** `pytest --collect-only -q tests\\test_operator_execution_gate_toctou_red.py` → 31 collected，0 collection errors，1 个外部 warning。
- **RED 结果：** `pytest -q tests\\test_operator_execution_gate_toctou_red.py` → 24 failed，7 passed，1 warning，2.99s。7 个通过项是已有的 pathlib/importlib/builtins/dunder 拒绝、缺 validation/execution 拒绝及 blocked row 不可选/冻结回归；24 个失败均对应尚缺生产/文档合同。
- **既有相关回归：** Phase 3/4/4B 三个相关测试文件 → 53 passed，1 warning，18.50s。
- **完整测试：** `pytest -q` → 24 failed（全部来自新 Phase 4C 文件）、142 passed、1 warning，29.79s；因此所有 135 个既有测试与新文件中的 7 个已有行为回归均通过。

### Phase 4C RED 失败测试与原因

| 测试/参数组 | RED 数 | 失败原因 |
|---|---:|---|
| `test_evolution_config_defaults_unsafe_candidate_execution_to_false` | 1 | `EvolutionLoopConfig` 缺少默认 False 的显式 unsafe execution flag |
| `test_real_provider_candidate_is_blocked_before_smoke_test` | 1 | real-provider 候选仍调用 `_smoke_test`，未形成 execution-blocked/risk-ack 状态 |
| `test_real_provider_candidate_does_not_enter_benchmark_by_default` | 1 | evolution benchmark 实际收到 1 个 unsafe candidate，而非空列表 |
| `test_static_validation_rejects_capability_and_reflection_bypasses[fileio-alias]` | 1 | `from io import FileIO as F` 仍通过 AST；其余 4 个既有拒绝用例通过 |
| `test_path_execution_requires_expected_hash_and_rejects_changed_source` | 1 | `CandidateProxy`/executor 均没有 `expected_code_hash` 合同 |
| `test_frozen_operator_source_replacement_is_detected_before_call` | 1 | 替换源码被实际调用，记录为 `runtime_error` 而非 source hash mismatch |
| `test_frozen_source_replacement_is_not_generated_success_or_rewarded` | 1 | 可行替换源码无 fallback，被记作 generated success/获得 reward |
| `test_frozen_repair_malformed_shape_is_structured_invalid_fallback[...]` | 4 | `routes=None`/异类 task id 抛异常；tuple routes/route 被错误接受，无 invalid fallback |
| `test_benchmark_malformed_success_is_structured_failure[...]` | 2 | 缺 result 字段或 `routes=None` 从 evaluator 逸出，中断 benchmark |
| `test_selection_and_freeze_fail_closed_when_evidence_is_missing[...]` | 5 | 缺 safe/risk-ack/sandbox/provider/failure 证据仍 eligible；缺 validation/execution 已正确拒绝 |
| `test_malformed_frozen_registry_is_structured_fallback[...]` | 4 | invalid JSON、顶层 list、非对象 row、字段类型错误均直接中断 solver 初始化 |
| `test_operator_evolution_docs_do_not_describe_obsolete_soft_timeout` | 1 | 文档仍写 `Timeout is soft`，缺 timeout-only/非完整 sandbox 当前口径 |
| `test_readme_warns_before_real_llm_execution_command` | 1 | 真实 LLM 命令前没有 safety warning/checklist |

### RED 判定与 GREEN 计划

- **RED 判定：** 31 collected；24 个失败均来自缺失的生产/文档行为，不是 collection、fixture、拼写或测试替身错误；7 个通过节点用于锁定已有正确行为。
- **GREEN 1：** 增加 fail-closed execution policy 与默认 False flag，在 smoke/benchmark 前处理 provider、sandbox、safe 和 risk ack。
- **GREEN 2：** proxy/worker 绑定 expected hash，每次 import 前校验；ALNS frozen registry 将验证 hash传入 proxy，mismatch 结构化 fallback/零奖励。
- **GREEN 3：** AST 补 FileIO 明显能力；contract/evaluator 对 shape/type 异常封闭为 invalid/runtime failure。
- **GREEN 4：** selection/freezing 所有安全证据改为必需且 fail closed；registry parse/row/type 错误结构化记录。
- **GREEN 5：** 更新 README 与 operator evolution 文档，明确 timeout-only、风险确认和真实 LLM 阻断条件。
- **GREEN 6：** 依次运行 Phase 4C、新旧相关回归、完整 `pytest -q`，随后重新代码复审。
- **状态：** RED complete；等待用户授权 GREEN。未修改生产代码、既有测试或文档正文；未调用真实 LLM/provider，未运行实验，未进入 Phase 5。

## 2026-08-02：Phase 4C GREEN 开始

- **状态：** in progress
- **已恢复证据：** Phase 4C 为 31 collected、24 failed、7 passed；完整套件 24 failed、142 passed。
- **当前动作：** 已回读规划记录与 Phase 4C 测试前 300 行；实现顺序保持 execution gate → expected hash → contract/evaluator → registry/fail-closed → docs。
- **测试合同回读完成：** 31 个节点要求 blocked status、zero benchmark candidates、`expected_code_hash` API、source mismatch fallback/零奖励、strict list/int contract、fail-closed metadata、registry fallback 与文档警告。
- **第一层实现定位：** `candidate_loader` 当前在 AST 后无条件 smoke；`CandidateProxy` 只保存 path/type；worker 在 import 前未绑定 hash；AST denylist 缺 `io.FileIO` alias 检查。
- **约束：** 不改主搜索策略、问题建模、DP/baseline/local search，不运行真实 LLM/provider或实验，不进入 Phase 5。

## 2026-08-02：Phase 4C GREEN 完成

- **状态：** GREEN complete；等待独立复审。Phase 5 与真实 LLM 继续 blocked。
- **生产代码修改：**
  - `candidate_security.py`：补充 `io.FileIO`/alias 与明显反射、动态能力拒绝。
  - `candidate_execution.py`：proxy/executor 增加 `expected_code_hash`；child 复核 hash 后从同一源码快照执行，返回 `source_hash_mismatch`。
  - `candidate_loader.py`、`evolution_loop.py`：增加默认 False 的真实 provider execution gate；blocked 候选不 smoke/benchmark/selection/freeze；selection 证据 fail closed。
  - `evaluator.py`、`freezing.py`：畸形 benchmark 返回结构化失败；freeze 要求完整安全/失败证据并写入 registry。
  - `heuristics/alns_solver.py`：frozen proxy 绑定 expected hash；严格 repair/destroy contract；损坏 registry/row/metadata 转为结构化 fallback。
  - `experiments/operator_evolution_runner.py`：YAML 与显式 CLI 风险确认开关接入，默认禁用。
- **文档/配置修改：** `README.md`、`docs/operator_evolution.md`、`configs/operator_evolution_langchain.yaml` 明确 timeout-only 非 capability sandbox，并在真实 LLM 命令前加入安全警告/checklist。
- **规划记录修改：** 更新 `task_plan.md`、`findings.md`、`progress.md`；未修改或删除 Phase 4C RED 测试及任何既有测试。
- **RED → GREEN：** `tests/test_operator_execution_gate_toctou_red.py` 从 24 failed/7 passed 转为 31 passed。
- **测试命令与结果：**
  - `pytest tests/test_operator_execution_gate_toctou_red.py -q` → 31 passed，1 warning。
  - Phase 4/4B/4C loader/evaluator/execution 合并回归 → 79 passed，1 warning。
  - 全部 operator-evolution 与 frozen/ALNS 相关文件 → 97 passed，1 warning。
  - `pytest -q` → 166 passed，1 warning；warning 为既有 `pyreadline`/`collections.Callable` 弃用提示。
- **未决风险：** 当前仍是 timeout-limited subprocess，不限制 CPU、内存、环境变量、文件系统、网络或后代进程树；显式 allow flag 是人工风险确认，不是安全性证明。需完成独立 Phase 4C 复审后再决定是否仅进入文档化实验协议阶段。
- **范围确认：** 未修改问题建模、DP evaluator、baseline、local search 或 ALNS 主搜索策略；未调用真实 LLM/provider，未运行任何实验，未进入 Phase 5。
- **最终新鲜验证：** `python -m compileall -q src` 成功；随后 Phase 4C 专项为 31 passed（1.90s），完整 `pytest -q` 为 166 passed（27.99s），均只有同一个既有 `pyreadline` 弃用 warning。

## 2026-08-02：Phase 4C GREEN 独立复审开始

- **状态：** in progress；只读审查生产代码、测试、配置和文档，只允许更新规划记录。
- **复审轴：** execution gate、AST bypass、frozen expected-hash/源码快照、selection/freezing fail-closed、contract/registry robustness、reward attribution、文档安全口径、性能与可维护性。
- **限制：** 不修改生产代码，不进入 Phase 5，不运行真实 LLM/provider，不运行实验；只允许轻量测试复核。
- **测试先行初核：** 31 个节点的覆盖面与 Phase 4C RED 目标一致；已确认 execution gate 测试会观察 smoke 调用次数、benchmark 候选数、selection 状态、fallback event 与 reward，而非只检查字段存在。
- **第一段实现初核：** real-provider 默认在 AST 后返回 `risk_ack_required`；evolution benchmark 有独立 safety/hash/sandbox/callable gate，并对 config/draft provenance 取保守 real-provider 口径。
- **第二段实现初核：** frozen canonical path 的 expected hash 与单次源码快照消除了已知 TOCTOU；contract/reward 主路径符合测试。发现 5 个待定级 Required：底层 hash 参数可空、registry 不强制完整 provenance/sandbox/failure/risk-ack、timeout_ms 类型未封闭、selection/freezing 对 fallback/rate 缺失仍有默认成功值、destroy benchmark 对未知 task id/错误 partition 仍可能逸出。
- **诊断错误：** 首次临时 Python 诊断未设置 src-layout import path，报 `ModuleNotFoundError: mrta_rect_coverage`；已记录，下一次使用 `PYTHONPATH=src`，不重复原失败命令。
- **文档初核：** README 与 `docs/operator_evolution.md` 的 timeout-only 风险口径正确；正式演化规格的“当前实现差距”仍停留在 Phase 4 前，需作为 Required 同步任务。
- **临时诊断结果：** 缺 fallback/rate 的 row 仍 eligible/freezable；缺 provenance/sandbox/failure/risk-ack 的 registry 仍注册；非法 timeout 字符串使 solver 初始化抛 `ValueError`；未知 task id destroy benchmark 被结构化为 runtime_error。
- **Critical 已确认：** `allow_unsafe_candidate_execution="false"` 因 truthiness 被当作授权，fake smoke 被调用，validation 变为 success/safe/risk-ack false。诊断只替换 smoke 函数观察门禁，不执行候选代码或真实 provider。

## 2026-08-02：Phase 4C GREEN 独立复审完成

- **结论：** Request changes；1 Critical、4 组 Required、4 项 Consider。未修改生产代码或测试。
- **Critical：** unsafe allow flag 未严格校验 bool；字符串 `"false"` 会被当作显式授权并越过 real-provider smoke gate。
- **Required：** expected hash 底层 API 可空；frozen registry 缺完整 evidence 且 timeout 类型未封闭；selection/freezing 对 fallback/rate 缺失仍有成功默认；正式演化规格当前状态过期。
- **通过项：** canonical bool-False execution gate、指定 AST 绕过、frozen hash snapshot/TOCTOU、contract、fallback/reward/LLM-success 隔离、README 与 operator_evolution 风险口径。
- **验证：** `python -m compileall -q src` 成功；Phase 4B+4C 边界测试 58 passed（9.54s）；完整 `pytest -q` 166 passed（26.18s）；仅既有 `pyreadline` warning。
- **Gate：** 不允许进入 Phase 5 文档化实验协议；继续禁止真实 LLM；继续禁止大规模实验。Critical 修复后需再次独立复审。
- **范围：** 只更新 `task_plan.md`、`findings.md`、`progress.md`；未运行 provider 或实验。

## 2026-08-02：Phase 4D RED 开始

- **状态：** in progress；严格 TDD，只新增测试，不修改生产代码或文档正文。
- **范围：** strict bool config/execution gate、expected hash、frozen registry evidence 与 timeout、selection/freezing 完整 evidence、正式规格过期口径。
- **测试原则：** 优先真实配置/loader/evolution/executor/ALNS registry/helper；仅 smoke 未执行性使用窄 monkeypatch，不断言 mock 自身业务结果。
- **限制：** 不进入 Phase 5，不运行真实 LLM/provider，不运行实验或大规模计算。
- **新增测试：** `tests/test_operator_strict_policy_config_hardening_red.py`；未修改生产代码、既有测试或文档正文。
- **收集结果：** `pytest --collect-only -q tests/test_operator_strict_policy_config_hardening_red.py` → 59 collected，0 collection errors，1 个既有 `pyreadline` warning。
- **执行记录：** 首次 RED 输出超过报告上限，最终汇总未保留；下一次使用 `--tb=no` 和临时文件紧凑回显失败节点与总计，以该次结果为权威 RED 证据。
- **权威 RED 结果：** `pytest -q --tb=no tests/test_operator_strict_policy_config_hardening_red.py` → 45 failed、14 passed、1 warning（2.42s）；退出码 1，符合 RED 预期。
- **既有相关回归：** Phase 4/4B/4C execution boundary 三个既有测试文件 → 76 passed、1 warning（14.62s）。

### Phase 4D RED 失败测试与原因

| 测试/参数组 | RED 数 | 失败原因 |
|---|---:|---|
| `test_yaml_non_boolean_unsafe_execution_is_rejected_or_disabled[...]` | 10 | runner 将字符串、整数、None、容器等非 bool 原样传入配置，既不报 invalid config，也不统一禁用。 |
| `test_loader_non_boolean_allow_value_never_reaches_smoke[...]` | 6 | truthy 的字符串与整数 1 被视为授权，real-provider 候选进入 smoke；falsey 非 bool 的 4 个参数仅因现有 truthiness 偶然阻断。 |
| `test_evolution_non_boolean_allow_value_never_enters_benchmark_or_selection[...]` | 2 | evolution 对 `"false"` 与 `1` 使用 truthiness，候选进入 benchmark/后续选择路径。 |
| `test_literal_true_does_not_bypass_other_execution_evidence[...]` | 2 | literal True 下缺合法 sandbox 或 provider 证据仍被判为 execution eligible；其余 6 类缺失证据已能阻断。 |
| `test_direct_path_execution_without_expected_hash_is_rejected` / `test_candidate_proxy_without_expected_hash_is_rejected` | 2 | 底层 executor/proxy 把 expected hash 当可选项，直接 path 调用可执行未绑定源码。 |
| `test_frozen_registry_missing_complete_evidence_is_rejected[...]` | 8 | registry loader 未强制 failure/provenance/sandbox/risk-ack/fallback/三类 failure-rate 全部证据。 |
| `test_invalid_registry_timeout_is_structured_fallback[...]` | 6 | 非数字/None 会抛类型转换异常；NaN、inf、零和负数未按有限正数校验并结构化 fallback。 |
| `test_selection_and_freezing_reject_missing_failure_evidence[...]` | 4 | selection/freezing 对缺 fallback_used 或三类 failure rate 仍采用无 fallback/零失败默认值。 |
| `test_formal_spec_removes_obsolete_pre_hardening_statements[...]` / `test_formal_spec_records_current_timeout_only_residual_risk` | 5 | 正式规格仍保留主进程 import、soft timeout、缺 hash/feasibility 等旧状态，且未同步 timeout-only 非 capability sandbox 的当前风险。 |

- **RED 真实性：** 45 个失败均对应已知的生产/文档合同缺口；模块无收集错误。14 个通过节点锁定 literal bool 解析、部分既有门禁和合法正 timeout 等正向/回归行为。

### Phase 4D RED 完成与 GREEN 计划

- **完整测试：** `pytest -q --tb=no` → 45 failed、180 passed、1 warning（28.55s）；45 个失败全部属于 `tests/test_operator_strict_policy_config_hardening_red.py`，失败文件外计数为 0。全部 166 个既有测试继续通过。
- **GREEN 1：** 建立统一 strict-bool/config policy；runner 在边界拒绝非 bool，loader/evolution 仅以 `value is True` 识别显式授权。
- **GREEN 2：** 统一 execution eligibility，literal True 也必须满足 validation、risk acknowledgement、provider、sandbox、safe 与 hash 等完整证据。
- **GREEN 3：** executor/proxy 缺 expected hash 时 fail closed；frozen registry 使用同一证据 schema，并把 timeout 限制为有限正数且异常结构化 fallback。
- **GREEN 4：** selection/freezing 要求 fallback 与三类 failure-rate 显式存在，不再为旧/畸形 artifact 默认零失败。
- **GREEN 5：** 更新正式规格的“当前实现/剩余风险”口径，但继续明确 timeout-limited subprocess 不是 capability sandbox。
- **GREEN 6：** 依次运行 Phase 4D 专项、Phase 4/4B/4C 相关回归、完整 `pytest -q`，再做独立复审。
- **最终状态：** RED complete，等待用户授权 GREEN。只新增失败测试并更新三份规划文件；未修改生产代码、既有测试或文档正文，未调用真实 LLM/provider，未运行实验，未进入 Phase 5。
- **收尾隔离核验：** 新增 evolution 测试显式使用 `tmp_path/generated` 与 `tmp_path/outputs`。生产源码最近修改时间为 18:19–18:20，早于本轮测试文件的 18:44；本轮未修改生产源码。完整既有套件会刷新项目 `generated_operators/`（18:48），作为后续测试隔离债务记录，本轮不删除或改写该产物。

## 2026-08-03：Phase 4D GREEN 开始

- **授权与基线：** 用户授权从 59 collected、45 failed/14 passed 的 Phase 4D RED 进入最小 GREEN；166 个既有测试在 RED 完整套件中通过。
- **范围：** 仅 operator evolution policy/loader/evolution/execution/selection/freezing、runner config、frozen deployment 最小边界及正式规格；不改 problem model、DP、baseline、local search 或 ALNS 主搜索策略。
- **顺序：** strict bool + typed eligibility → loader/evolution gate → expected hash → registry/timeout → selection/freezing → formal spec → 分层测试与 compileall。
- **限制：** 不运行真实 LLM/provider，不运行实验，不进入 Phase 5，不引入重依赖。
- **RED 合同回读：** 59 项测试直接覆盖 runner YAML、loader smoke gate、evolution benchmark gate、`_can_enter_benchmark`、底层 executor/proxy、ALNS frozen registry、selection/freezing helper 与正式规格；不需要修改测试。
- **初始调用图：** runner 原样传 allow flag；loader/evolution 使用 truthiness；executor 只在 expected hash truthy 时比较；registry 直接 float 转 timeout；selection/freezing 对 fallback/rates 有成功默认。适合新增单一轻量 policy 模块并由现有入口调用。
- **具体落点：** `CandidateProxy.execute()` 把空 hash 转 None，worker 仅在 truthy 时复核；ALNS `_load_external_function()` 只要求 4 个 metadata 字段且 `float(metadata.get(...))` 可抛异常；freeze registry 目前未写 fallback/rate 字段。GREEN 必须同时补写与补读，避免 canonical artifact 被新 gate 自己拒绝。
- **核对错误：** Windows `rg` 对路径参数中的 `tests/test_alns*` 通配符返回 os error 123；后续使用目录 + `-g` 过滤，不影响代码状态。
- **兼容性核对：** canonical freeze/ALNS integration 测试由 evolution evaluator 生成完整 row，可通过 writer 同步新增 registry evidence；手工旧 registry fixtures 需要按新的 fail-closed 合同判断，不能通过 reader 默认值迁就。
- **规格定位：** 过期内容集中在 `docs/llm_operator_evolution_spec.md` 第 10 节；其他章节已经陈述硬 timeout/hash/feasibility 目标，可仅替换“当前实现与目标规范差距”事实段并补剩余 capability 风险。
- **首轮生产实现：** 新增 `eligibility_policy.py`，集中 strict bool、execution/benchmark、selection/freezing、registry metadata 与有限正 timeout；runner、loader、evolution、executor、freezing、ALNS frozen deployment 已接线。底层 executor 在 spawn 前返回 `source_hash_missing`，registry writer/reader 同步 fallback 与 failure-rate 证据。
- **Phase 4D 首次 GREEN：** `pytest -q tests/test_operator_strict_policy_config_hardening_red.py` → 59 passed、1 个既有 `pyreadline` warning（4.46s）；原 45 个 RED 全部转绿，未改测试。
- **首次四阶段回归：** Phase 4/4B/4C/4D 合并为 23 failed、112 passed、1 warning。失败分成两类：3 个旧 direct executor 调用缺 expected hash；20 个 frozen 测试的 registry helper/手工 row 缺 Phase 4D mandatory evidence，导致在 registry gate 提前拒绝，后续 AST/timeout/contract/reward 断言无法到达。生产 fail-closed 行为本身符合新合同。
- **必要旧 fixture 迁移：** 仅给 3 个 Phase 4B direct executor 测试补源码 hash，并给 Phase 4/4B/4C 的 registry helper/手工 row 补 failure/risk/fallback/rates 成功证据；未改变断言、未删除/skip 测试，Phase 4D 缺字段拒绝测试保持原样。
- **四阶段回归复验：** 同一 Phase 4/4B/4C/4D 集合 → 135 passed、1 个既有 warning（18.25s）；确认 23 个失败的根因与 fixture 迁移假设正确，生产门禁未放宽。
- **Operator evolution 回归：** 8 个 `test_operator_evolution*.py` 文件 → 17 passed、1 warning（7.90s）。
- **Frozen/ALNS 回归：** `test_alns_solver.py` + `test_alns_frozen_operator_integration.py` → 4 passed、1 warning（1.16s）。

## 2026-08-03：Phase 4D GREEN 完成

- **生产修改：**
  - 新增 `llm/operator_evolution/eligibility_policy.py`：strict bool、execution/benchmark、selection/freezing、registry metadata 与有限正 timeout 的共同 fail-closed policy。
  - 修改 `candidate_loader.py`、`evolution_loop.py`、`operator_evolution_runner.py`：非 bool 配置拒绝/结构化阻断；real-provider smoke/benchmark 只接受 literal True 与完整安全证据。
  - 修改 `candidate_execution.py`：generated/frozen path 缺 expected hash 时在 spawn 前返回 `source_hash_missing`；child 始终进行 hash compare。
  - 修改 `freezing.py`、`heuristics/alns_solver.py`：writer/reader 同步完整 failure/risk/fallback/rates evidence；非法或非有限正 timeout 结构化 registry fallback。
  - 更新 `docs/llm_operator_evolution_spec.md`：移除 Phase 4 前旧事实，记录 strict policy、hash-bound timeout-only subprocess、contract gate 和剩余 capability 风险。
- **必要测试适配：** `test_operator_execution_boundary_red.py`、`test_operator_execution_boundary_hardening_red.py`、`test_operator_execution_gate_toctou_red.py`、`test_operator_evolution_protocol_red.py` 的旧 fixture 补 mandatory hash/registry evidence；断言与 Phase 4D RED 均未删除、skip 或放宽。
- **验证：**
  - Phase 4D 专项：59 passed、1 warning（4.46s）。
  - Phase 4/4B/4C/4D 边界：135 passed、1 warning（18.25s）。
  - operator evolution：17 passed、1 warning（7.90s）。
  - frozen/ALNS：4 passed、1 warning（1.16s）。
  - 完整 `pytest -q`：225 passed、1 warning（26.75s）。
  - `python -m compileall src`：exit 0。
- **剩余风险：** 当前仍是 `timeout_only` 子进程，不是 capability sandbox；CPU、内存、文件系统、网络、环境变量与后代进程树隔离未解决。真实 LLM、Phase 5 和大规模实验继续禁止，需先完成独立复审。
- **状态：** Phase 4D GREEN complete；等待独立 code review。
- **最终新鲜验证：** 收尾重新运行 `pytest -q` → 225 passed、1 个既有 warning（25.94s）；随后 `python -m compileall -q src` → exit 0。最终验证发生在所有生产、测试适配与文档修改之后。

## 2026-08-03：Phase 4D GREEN 独立复审开始

- **范围：** 只读审查测试、strict policy、runner/loader/evolution、executor、freezing/registry、ALNS contract/reward 与 README/docs；只更新三份规划文件。
- **审查轴：** Critical/Required/Consider/FYI，覆盖 correctness、architecture、security boundary、research validity、performance、reproducibility 与验证证据。
- **限制：** 不修改生产代码或测试，不进入 Phase 5，不运行真实 LLM/provider，不运行实验或大规模计算。
- **测试/策略初核：** strict bool 本身使用 `type(value) is bool`；必需三类 rate、fallback、安全/状态/provider/hash 均显式要求。待核证 3 个候选缺口：freeze 缺 `timeout_ms` 默认 1000；validation_failed/execution_blocked rates 缺失仍被视为可接受；`capability_sandbox` 标签是否有真实执行能力证明。
- **调用链初核：** runner YAML 与 dataclass 均 strict parse；CLI 的剩余 truthiness 只作用于 argparse `store_true` bool。loader 对 real provider 默认 risk_ack_required，非 bool config 在 smoke 前 config_invalid；evolution benchmark 与 selection 使用 policy，freezing/registry 也委托 policy。
- **状态语义候选：** evolution summary 对未包含在 `operator_types_to_evolve` 的类型仍输出 `no_valid_operator`，未与 `not_evolved` 区分；candidate failure rows 虽保留具体 failure_type，但 selection status 不区分 invalid/fallback。
### Phase 4D independent review — targeted diagnostics (2026-08-03)

- Ran a read-only policy diagnostic with `PYTHONPATH=src`.
- Confirmed non-boolean unsafe-execution values fail closed.
- Confirmed remaining gaps: optional validation/execution-blocked failure rates, defaulted freeze timeout, and untrusted `capability_sandbox` labeling.
- Next: trace the frozen registry path, verify documentation wording, then rerun the requested test evidence.

### Phase 4D independent review — fresh verification (2026-08-03)

- `pytest -q tests/test_operator_strict_policy_config_hardening_red.py` → 59 passed, 1 existing pyreadline warning.
- Phase 4/4B/4C/4D boundary files → 135 passed, 1 existing pyreadline warning.
- Static registry trace confirmed that `capability_sandbox` is accepted as untrusted JSON metadata although deployment still uses the timeout-only executor.
- Remaining verification: operator-evolution subset, frozen/ALNS subset, full pytest, and compileall.
- Operator-evolution subset (`test_operator_evolution*.py`) → 17 passed, 1 existing warning.
- Frozen/ALNS subset (`test_alns_solver.py` and `test_alns_frozen_operator_integration.py`) → 4 passed, 1 existing warning.
- Remaining verification: full pytest and compileall.
- Full `pytest -q` → 225 passed, 1 existing pyreadline warning.
- `python -m compileall -q src` → exit 0.
- Final static checks found status-semantic (`not_evolved`) and policy-centralization/API-boundary debt in addition to the sandbox-label and incomplete-evidence issues.

## 2026-08-03：Phase 4D GREEN 独立复审完成

- **结论：Request changes。** 发现 1 个 Critical：`capability_sandbox` 是可由 artifact 自声明的 metadata，但实际执行器始终为 `timeout_only`；真实 provider 可经冻结 registry 路径绕过风险确认/unsafe allow 门禁。
- **Required：** failure-rate/timeout 证据仍有 optional/default；loader 与底层 executor 的策略/AST 边界未完全自包含；`not_evolved` 与 `no_valid_operator` 混同；feedback/top pool 未过滤 ineligible rows；正式规格“缺字段即拒绝”表述过强。
- **正向结论：** strict bool、canonical real-provider 默认阻断、指定 AST denylist、expected-hash/TOCTOU、contract/registry robustness、fallback/reward 隔离均有效。
- **新鲜验证：** Phase 4D 59 passed；四阶段边界 135 passed；operator evolution 17 passed；frozen/ALNS 4 passed；完整 225 passed、1 个既有 warning；compileall exit 0。
- **准入：** 不允许进入 Phase 5 文档化实验协议；继续禁止真实 LLM 和大规模实验。先修 Critical，随后独立复审；Required 需在实验执行前关闭并同步文档。

## 2026-08-05：Phase 4E RED 开始

- **授权与范围：** 用户要求严格 TDD RED；只新增失败测试并更新规划文件，不修改生产代码、既有测试或文档正文。
- **目标：** 用可信 executor authority 封闭 artifact 自声明 sandbox level，同时锁定完整 evidence、同快照 AST、统一 loader policy、状态语义和 eligible-only feedback 合同。
- **限制：** 不进入 Phase 5，不运行真实 LLM/provider，不运行实验或大规模计算。
- **测试设计：** 优先真实 policy/loader/executor/registry/evolution/feedback 路径；只有验证 smoke/benchmark 未被调用时使用窄 monkeypatch。
- **既有覆盖复用：** Phase 4C/4D 已提供 real-provider provider stub、完整 candidate/registry row、临时 registry/solver、evolution loop 与文档断言 helper；Phase 4E 将复制必要的完整 fixture 到新测试文件，不修改既有测试。
- **测试反模式约束：** monkeypatch 只拦截 smoke/benchmark 以证明“不得调用”，其余断言直接检查真实 policy、executor、registry、feedback 和 summary 行为。
- **生产缺口映射完成：** policy 强沙箱判定、registry metadata、worker hash→compile、loader 本地条件、optional rates/default timeout、unfiltered feedback/leaderboard 和统一 no-valid status 均有独立可触发路径。
- **RED 文件方案：** 新建单一 `tests/test_operator_trusted_executor_authority_red.py`；用临时目录和 mock/static provider，不访问真实 LLM，不写默认 generated/output 目录。
- **新增测试文件：** `tests/test_operator_trusted_executor_authority_red.py` 已创建；只包含新测试/fixture，未修改任何生产代码、既有测试或文档正文。
- **收集结果：** `pytest --collect-only -q tests/test_operator_trusted_executor_authority_red.py` → 23 collected、0 collection errors、1 个既有 `pyreadline` warning。
- **权威 RED：** `pytest -q --tb=short tests/test_operator_trusted_executor_authority_red.py` → 18 failed、5 passed、1 warning（退出码 1）。所有失败均为断言失败，无 import/fixture/未捕获异常。

### Phase 4E RED 失败分组

| 分组 | RED 数 | 失败原因 |
|---|---:|---|
| trusted sandbox authority：execution/benchmark/selection/freezing/actual freeze | 5 | policy 与 artifact gate 直接信任 `capability_sandbox` claim，real provider 默认 allow=False 仍被视为 eligible/freezeable。 |
| frozen registry + runtime authority metadata | 2 | registry 接受伪造 executor/capability claim；execution result 没有 `effective_sandbox_level`/`executor_identity`。 |
| evolution benchmark gate | 1 | capability-claimed real candidate 进入 benchmark，捕获到 candidate count 1 而非 0。 |
| complete evidence | 3 | 缺 `validation_failed_rate`、`execution_blocked_rate` 或 `timeout_ms` 时 selection 仍返回 True，freeze 也为 timeout 使用默认值。 |
| same-snapshot AST/security | 1 | 正确 hash 的 `open(...)` 危险源码返回 success，并实际创建 marker 文件。 |
| loader unified policy | 1 | loader 未调用共同 execution eligibility hook，直接进入 smoke。 |
| status semantics | 1 | 未请求的 destroy 类型仍输出 `no_valid_operator`，未输出 `not_evolved`。 |
| eligible-only feedback/leaderboard | 2 | blocked/fallback/timeout rows 进入 top/weak pool，blocked real candidate 进入 round leaderboard。 |
| formal spec | 2 | 未声明 trusted executor authority；仍声称所有 evidence 缺失均已拒绝。 |

- **5 个通过节点：** 缺 `fallback_used`/三类既有 failure rate 已会拒绝（4）；参与演化但无有效 repair 已正确返回 `no_valid_operator`（1）。这些是 GREEN 必须保持的回归合同。
- **既有边界回归：** Phase 4/4B/4C/4D 四个测试文件 → 135 passed、1 个既有 warning（17.43s）。
- **完整套件：** `pytest -q --tb=no` → 18 failed、230 passed、1 warning（25.72s）；18 个失败全部来自新增 Phase 4E 文件，225 个既有测试全部通过。

### Phase 4E 最小 GREEN 计划

1. 建立 runtime-owned executor authority：固定当前 executor identity 与 effective `timeout_only`，candidate/artifact 的 sandbox 仅作为 claim。
2. 让 execution/benchmark/selection/freezing/registry 共用 claim-vs-authority 校验；不匹配结构化为 `untrusted_sandbox_claim`/blocked fallback。
3. 扩展 candidate/metrics/frozen schema，强制 executor identity、effective level、两类剩余 failure rate 和显式有限正 timeout；writer/reader 同步。
4. 在 child 对完成 hash 校验的同一 `source_text` 运行 AST/security validation，再 compile/call。
5. 让 candidate loader 调用统一 pre-execution policy，不再自行把 allow flag转换为 safe/risk 状态。
6. 对 feedback 和 round leaderboard 使用 eligible pool；单独保留 failure breakdown，并按配置区分 `not_evolved`/`no_valid_operator`。
7. 同步正式规格的 trusted-authority 与完整-evidence 当前事实，继续声明 timeout-only 不是 capability sandbox。
8. 按 Phase 4E → 既有四阶段边界 → operator evolution/frozen ALNS → 完整 pytest → compileall 顺序验证，并进行独立复审。

- **最终状态：** Phase 4E RED complete，等待用户授权 GREEN。未修改生产代码、既有测试或文档正文；未运行真实 LLM/provider、实验或 Phase 5。

## 2026-08-05：Phase 4E GREEN 开始

- **授权与基线：** 用户授权从 23 collected、18 failed/5 passed 的 Phase 4E RED 进入最小 GREEN；完整 RED 套件中 225 个既有测试继续通过。
- **范围：** 仅 operator evolution policy/loader/executor/evaluator/feedback/freezing、frozen registry deployment 最小边界及正式规格；不改 problem model、DP、baseline、local search 或 ALNS 搜索策略。
- **顺序：** trusted authority/policy → loader/registry → same-snapshot AST → complete evidence → state/feedback → docs → 分层验证。
- **限制：** 不运行真实 LLM/provider，不运行实验或大规模计算，不进入 Phase 5，不引入重依赖。
- **核心边界首轮实现：** executor 增加固定 `timeout_only` authority/identity 和同快照 AST validation；policy 将 artifact sandbox 视为 claim、强制 effective/identity/完整 rates/timeout；loader 通过共同 preexecution policy 与 execution eligibility 决策，不再保留本地 real-provider 分支。
- **第二轮最小实现：** evaluator/evolution rows 补齐 runtime authority 与完整 failure-rate evidence；selection/freezing/registry writer 采用显式 timeout 与完整 metadata；feedback 和 round leaderboard 仅保留 eligible rows；未参与演化的类型输出 `not_evolved`，已参与但无候选保持 `no_valid_operator`。
- **文档同步：** 正式规格已明确 `sandbox_level` 是 artifact claim，授权仅来自固定的 `timeout_only_subprocess_v1`/`timeout_only` runtime authority；当前没有 capability sandbox，claim 不一致将被阻断。
- **增量测试：** 首轮核心实现后 Phase 4E 专项由 18 failed/5 passed 收敛到 5 failed/18 passed；余下五项（状态语义、反馈/leaderboard、两项文档）均已实施对应最小修改，等待重跑确认。
- **Phase 4E 专项 GREEN：** `pytest -q --tb=short tests/test_operator_trusted_executor_authority_red.py` → 23 passed、1 个既有 `pyreadline` warning（0.90s）。原 18 个 RED 均已转绿，未放宽或跳过测试。
- **五阶段首次合并回归：** 158 collected → 32 failed、126 passed。根因分为两类：1 个真实 policy 字段漂移（修改 `sandbox_level` 后仍读取旧 `claimed_sandbox_level`）；31 个旧 Phase 4B–4D registry fixture 未迁移 Phase 4E 的 runtime authority/两类新增 failure-rate evidence，因生产 fail-closed 被拒绝，继而出现未注册 operator 与 fallback-stage 连锁失败。
- **修复原则：** 修正 policy 对 claimed/sandbox 双字段的一致性校验；仅给旧测试的有效 registry fixture 补齐新 schema，不改断言、不删除/跳过/放宽任何测试，也不降低生产 metadata 要求。
- **合并回归修复：** execution policy 现在同时校验 `sandbox_level` 与 `claimed_sandbox_level` 且要求一致；旧 Phase 4B–4D 的有效 registry fixture 仅补齐 `effective_sandbox_level`、`executor_identity`、`validation_failed_rate`、`execution_blocked_rate`，没有修改测试断言。
- **Phase 4/4B/4C/4D/4E 边界：** `pytest -q --tb=short` 对五个边界文件 → 158 passed、1 个既有 warning（15.39s）。首次合并的 32 个失败已全部消除，生产 fail-closed 要求未降级。
- **operator-evolution 首次回归：** 17 collected → 1 failed、16 passed；唯一失败为 `test_frozen_operator_runtime_failure_is_recorded` 的旧内联 registry row 缺 Phase 4E evidence，operator 因 fail-closed 未注册。下一步仅迁移该有效 fixture metadata 后重跑。
- **operator-evolution 回归 GREEN：** 给该内联有效 fixture 补齐 runtime authority/两类 failure-rate evidence 后，原 17 个 operator-evolution 测试 → 17 passed、1 个既有 warning（7.42s）；测试断言保持不变。
- **frozen/ALNS 回归 GREEN：** `pytest -q --tb=short tests/test_alns_solver.py tests/test_alns_frozen_operator_integration.py` → 4 passed、1 个既有 warning（1.06s）。
- **完整套件 GREEN：** `pytest -q` → 248 passed、1 个既有 `pyreadline` 弃用 warning（24.71s）；无失败、跳过或 xfail。
- **编译检查：** `python -m compileall -q src` → exit 0、无输出。
- **静态范围核对：** runtime deployment gate 只从 `ALNSConfig` 读取 allow/ack/source，并由代码内 executor constants 提供 effective level/identity；artifact 同名字段未进入授权参数。拒绝发生在 proxy 构造和 frozen set 注册之前。

- **范围审计限制：** 当前工作区及父目录没有 Git metadata，无法用 `git diff`；改用本轮修改记录、文件时间、静态 `rg` 与完整测试核对。业务模型、DP、baseline、local search 未出现在本轮修改清单；`alns_solver.py` 仅变更 frozen fallback outcome metadata。
- **收尾审计新发现：** artifact row 若同时给出可信的 `sandbox_level` 与伪造的 `claimed_sandbox_level`，selection validator 尚未比较二者。该路径属于同一 sandbox self-declaration Critical；将新增一个最小 RED 断言并在统一 policy 内封闭。
- **补充 TDD RED/GREEN：** 新增 `test_separate_claimed_sandbox_field_cannot_hide_capability_claim`；修改前单测 1 failed，证明分离 claim 字段可绕过 artifact gate；统一 policy 改为校验 `sandbox_level`/`claimed_sandbox_level` 合法且一致后，单测 1 passed。该修复同时作用于 selection、freeze 和 registry metadata validation。

## 2026-08-05：Phase 4E GREEN 完成

- **生产修改：** `candidate_execution.py`、`eligibility_policy.py`、`schemas.py`、`candidate_loader.py`、`evaluator.py`、`evolution_loop.py`、`feedback_builder.py`、`freezing.py`，以及 frozen deployment 所需的 `heuristics/alns_solver.py` 最小 metadata 记录。
- **文档修改：** `docs/llm_operator_evolution_spec.md` 已同步 trusted runtime authority、timeout-only 非 capability sandbox、完整 evidence 和剩余资源隔离风险。
- **测试修改：** 保留 Phase 4E 原 23 项并新增 1 个 alias-claim 回归；旧 Phase 4B–4D/协议测试只迁移有效 registry fixture metadata，所有断言保留。
- **最终 Phase 4E：** `pytest -q --tb=short tests/test_operator_trusted_executor_authority_red.py` → 24 passed、1 个既有 warning（0.89s）。
- **分层回归：** Phase 4/4B/4C/4D/4E 边界 158 passed；operator evolution 17 passed；frozen/ALNS 4 passed。
- **最终完整验证：** `pytest -q` → 249 passed、1 个既有 `pyreadline` 弃用 warning（25.40s）；`python -m compileall -q src` → exit 0。
- **未执行：** 未调用真实 LLM/provider，未运行实验或大规模计算，未进入 Phase 5。
- **剩余风险：** 当前 executor 仍是 timeout-limited subprocess，不是 capability sandbox；CPU、内存、文件系统、网络、环境变量与后代进程树隔离未实现。工作区没有 Git metadata，范围审计依赖修改记录、文件时间、静态检索与测试证据。
- **下一步：** 对 Phase 4E GREEN 做独立代码复审。复审前 Phase 5、真实 LLM 和大规模实验继续 blocked。

## 2026-08-05：Phase 4E GREEN 独立复审开始

- **范围：** 只读复审 Phase 4E 测试、trusted authority/eligibility、loader/executor、selection/freezing、frozen registry、状态/feedback 和正式规格；只更新规划文件，不修改生产代码或测试。
- **复审轴：** Correctness、Security、Architecture、Readability、Performance、Research validity、Documentation 与新鲜 verification evidence。
- **限制：** 不进入 Phase 5，不调用真实 LLM/provider，不运行实验或大规模计算。
- **上下文恢复：** 已重读 `task_plan.md`、`findings.md`、`progress.md`；session catchup 无未同步输出。工作区仍无 Git metadata，复审依赖文件事实、调用链、静态诊断和测试证据。
- **测试先行审查：** Phase 4E 24 项覆盖 canonical policy、真实 evolution benchmark gate、实际 freeze/registry、底层危险源码 marker、状态语义、feedback/leaderboard 与文档；既有 Phase 4–4D 还覆盖 strict bool、TOCTOU、contract、fallback/reward、failure breakdown、source read 与 stdout/stderr。测试多数验证行为结果而非只检查字段存在。
- **测试覆盖候选缺口：** Phase 4E 对 frozen registry 的 forged capability row 同时伪造了 sandbox 与 executor identity；需在实现审查/只读诊断中单独验证“仅伪造 sandbox claim、其余 runtime evidence 看似正确”也会被拒绝，以及 real-provider frozen timeout-only row 的风险确认语义。
- **审查读取错误：** 首轮按常见命名尝试读取不存在的 `operator_evolution/selection.py`；实际 selection 位于 `evolution_loop.py`，eligibility 位于 `eligibility_policy.py`。后续改按真实调用链读取，不重复错误路径。
- **policy/executor 静态初核：** canonical loader 在 smoke 前调用共同 policy；executor 固定 identity/level，并在 child 的同一 `source_text` 上依次 hash、AST、compile/call，边界口径明确为 timeout-only。
- **待验证风险：** `candidate_is_execution_eligible` 对缺少 `effective_sandbox_level`/`executor_identity` 的任意 validation 对象使用可信常量作为 `getattr` 默认值。若公共 API 可在缺 runtime evidence 时返回 True，则属于 fail-closed 缺口；下一步用只读诊断验证，不先下结论。
- **registry/evolution 静态初核：** frozen registry 的 capability claim 会因 claim 必须等于 runtime `timeout_only` 而拒绝，实际执行也始终构造 hash-bound `CandidateProxy`；leaderboard/best/feedback 共用 selection eligibility，`not_evolved` 与 `no_valid_operator` 已分开。
- **待验证 Critical 候选：** frozen registry deployment 没有 runtime `allow_unsafe_candidate_execution`/risk-ack 参数；它只检查 JSON 自报的 `safe_to_execute=True` 与 `requires_human_risk_ack=False`。需验证 real-provider + timeout-only + 伪造完整 metadata 是否仍会注册，从而绕过“真实 provider 默认 blocked/显式风险确认”。
- **文档/metrics 初核：** selection/freezing/registry 的必需 rate/timeout 字段与 evaluator writer 已对齐；正式规格正确声明当前不是 capability sandbox。但规格“仍未满足”段把 feedback top/weak pool 与尚未实现的 lineage/diversity 混写为整体未实现，和当前 eligible-only filtering 存在轻微事实漂移，待最终定级。
- **只读诊断结果：** capability claim 改为 `capability_sandbox` 时 registry 正确拒绝并记录 `untrusted_sandbox_claim`；但 real-provider row 使用真实 `timeout_only` claim、伪造 safe/risk-ack success metadata 时，selection=True、freeze=True、solver frozen registry 注册=True、fallback 为空。
- **Critical 确认：** frozen deployment 没有 runtime unsafe allow/人工风险确认 authority，仍把 registry JSON 的 `safe_to_execute`/`requires_human_risk_ack` 当授权证据。故 real provider 在 frozen 路径不是默认 blocked，Phase 5 不能放行。
- **Required 确认：** execution eligibility 对缺 effective level/executor identity 的对象默认填可信常量，诊断返回 True；公共边界未完全 fail closed，且可接受非 `CandidateProxy` callable。
- **AST/文档复核：** AST denylist 覆盖用户点名的模块、FileIO/open/eval/exec/compile/importlib/builtins/getattr/dunder 等明显路径；规格也明确它不是 capability sandbox。未发现 Phase 4E 新增 AST Critical，但 denylist 不能替代 OS isolation 的剩余风险仍成立。
- **文档 Required 候选：** 规格标题仍写“截至 Phase 4D”；第 291 行声称真实 LLM 在所有路径保持默认阻止，与已复现 frozen registry 绕过不一致；第 295 行又把已实现的 eligible-only top/weak filtering 和未实现的 lineage/diversity 混写为整体差距。
- **schema/type-boundary Required：** `OperatorValidationResult` 默认 `safe_to_execute=True`、`requires_human_risk_ack=False`、effective level/identity 为可信值；结合 execution policy 的 `getattr` 可信默认和“任意非空 callable”判断，非 canonical 调用者可在没有 executor receipt 时构造 eligible 对象。canonical loader 会覆盖这些值，但公共边界和 fail-closed 口径不一致。
- **runner 初核：** YAML unsafe allow 仍经 `parse_strict_bool`，CLI truthiness 来自 argparse `store_true` 的真实 bool，没有重现 Phase 4D 字符串绕过。当前 Critical 集中于 frozen deployment 缺 runtime risk authority，而非 generation runner。
- **README/docs 核对：** README 对 generation runner 的 timeout-only warning 与默认 smoke/benchmark 阻断表述正确，但未覆盖 frozen registry 的 runtime risk-authority 缺口。`docs/operator_evolution.md` 第 107 行“no sandboxed execution”与下一行“timeout-only subprocess”措辞冲突，应改成“no capability sandbox”。
- **架构/性能 Consider：** `alns_solver.py` 约 812 行，frozen registry、proxy、contract 和 reward attribution 已成为独立子域；后续可提取 deployment adapter。每个 smoke/trial 使用 Windows spawn，安全边界正确但开销需在论文成本分析中单独报告；本轮不要求重构或优化。
- **新鲜验证：** `pytest -q` → 249 passed、1 个既有 `pyreadline` 弃用 warning（27.13s）；`python -m compileall -q src` → exit 0。绿测确认现有回归稳定，但当前测试未覆盖已由临时诊断复现的 frozen real-provider runtime-ack 绕过。

## 2026-08-05：Phase 4E GREEN 独立复审完成

- **Verdict：Request changes。** Capability sandbox artifact self-elevation 已修复，但发现 1 个 Critical：frozen selection/freezing/registry 把 JSON 自报 safe/risk-ack 当作 real-provider runtime 授权，临时诊断已复现实际注册且无 fallback。
- **Required：** execution eligibility 缺 runtime authority 时仍默认可信、接受任意 callable；validation schema 默认 safety/authority 值 fail open；缺对应负例测试；正式规格与 operator 文档有事实漂移。
- **通过项：** trusted timeout-only claim 比对、same-source hash+AST、完整 failure evidence、状态区分、eligible-only feedback/leaderboard 均符合 Phase 4E 目标。
- **验证：** 完整 `pytest -q` 249 passed、1 个既有 warning；compileall exit 0。未修改生产代码或测试，未调用真实 provider，未运行实验。
- **Gate：** 不允许进入 Phase 5；继续禁止真实 LLM；继续禁止大规模实验。下一步先用 TDD 修复 frozen runtime authorization Critical 与 execution evidence Required，再独立复审。

## 2026-08-05：Phase 4E 独立复审复核

- 用户再次要求同一 Phase 4E 独立复审；本轮以当前磁盘状态重新核验，不假设上一轮结论仍成立。
- 已重读三份规划文件并运行 session catchup；无未同步输出。仍只读检查生产/测试，禁止 Phase 5、真实 LLM 和实验。
- 当前关键代码仍显示：capability claim 必须匹配 runtime `timeout_only`；executor 同快照 hash+AST；feedback/leaderboard 和状态语义实现未变化。同时 execution eligibility 仍给缺 effective/identity 的对象使用可信默认值，frozen loader 仍没有 runtime risk-ack/unsafe-allow 参数。
- **定向诊断复核：** 缺 runtime authority evidence 的 execution validation 仍返回 eligible；伪造完整 real-provider timeout-only artifact 仍通过 selection/freezing 并被 registry 注册（无 fallback）；将 claim 改为 `capability_sandbox` 则正确拒绝并记录 `untrusted_sandbox_claim`。
- **新鲜验证：** `pytest -q` → 249 passed、1 个既有 `pyreadline` warning（24.91s）；`python -m compileall -q src` → exit 0。
- **复核结论：** Request changes。此前的 1 个 Critical 与 Required 未因本轮绿测消失；未修改生产代码或测试，未运行真实 LLM/provider、实验或 Phase 5。
- **Gate：** 不允许进入 Phase 5 文档化实验协议；继续禁止真实 LLM；继续禁止大规模实验。

## 2026-08-05：Phase 4F RED 开始

- **目标：** 用失败测试锁定 real-provider frozen deployment 必须依赖当前 runtime authorization，而不能由 artifact 自报 safety/risk acknowledgement。
- **范围：** 只新增 Phase 4F 测试并更新规划记录；不修改生产代码、既有测试或文档正文。
- **测试组：** canonical registry deployment/fallback/reward、strict runtime bool、timeout-only 风险确认、execution authority evidence、schema 保守默认值、文档事实。
- **限制：** 不调用真实 LLM/provider，不运行实验或大规模计算，不进入 Phase 5。
- **约束核对：** 已读 `AGENTS.md` 与 TDD testing anti-patterns；测试优先走真实 policy/solver 路径，只在隔离外部或随机行为时使用最小 fixture/monkeypatch，不测试 mock 调用本身。
- **既有测试定位：** Phase 4E authority、Phase 4D strict policy、frozen integration、selection/freezing 与协议测试可复用完整 artifact fixture 和真实临时 registry 模式；新建独立 Phase 4F 文件，不修改既有测试。
- **fixture 设计：** 复用完整、正确 hash、五类零 failure-rate、合法 timeout 的 repair operator row，仅将 provider 设为 real provider；这样 registry RED 可唯一归因于缺 runtime deployment authorization，而不是旧 metadata gate。
- **行为断言：** 真实 solver 初始化必须不把 operator 名加入 `frozen_repair_ops`，记录结构化 fallback；测试不通过 mock 验证加载调用次数。selection/freezing 是否继续接受完整评测 artifact 与 deployment gate 必须拒绝，将按职责边界分别断言。
- **API 现状：** `ALNSConfig` 尚无 runtime deployment allow/ack/source；`validate_registry_metadata` 仅接收 row；solver 加载成功即包装 `CandidateProxy`。因此 RED 可通过给 config 附加期望 runtime 字段来验证真实加载行为，避免因尚不存在的构造参数造成 collection/error。
- **策略选择：** timeout-only 下采用“literal True allow + literal True runtime risk ack + 当前 runtime source”才允许部署；其余缺失/非 bool 结构化拒绝。该正例作为锚点，负例负责证明 artifact 不能自证。
- **新增测试文件：** `tests/test_operator_runtime_authorization_frozen_deployment_red.py`，覆盖真实 solver registry 拒绝/fallback/reward、artifact 自报 ack、两类 runtime flag 的 10 组非 bool、literal false、缺 authorization source、timeout-only 正例、五类 execution authority 缺失、任意 callable、schema 保守默认与两项文档事实。
- **生产边界：** 尚未修改任何 `src/` 文件、既有测试或文档正文；下一步先 collect，修正测试自身错误后运行专项并确认预期 RED。
- **收集结果：** `pytest --collect-only -q tests/test_operator_runtime_authorization_frozen_deployment_red.py` → 37 collected、0 collection errors、1 个既有 `pyreadline` warning。
- **权威专项 RED：** `pytest -q --tb=short tests/test_operator_runtime_authorization_frozen_deployment_red.py` → 36 failed、1 passed、1 warning（退出码 1，1.28s）。所有失败均为预期 assertion failure，无 collection、fixture 或未捕获异常。
- **正向锚点：** 唯一通过节点是 runtime literal allow=True、literal ack=True、authorization source 完整时允许 timeout-only 部署；证明测试没有无条件禁止 real-provider frozen deployment。

### Phase 4F RED 失败分组

| 测试函数/分组 | RED 数 | 失败原因 |
|---|---:|---|
| `test_forged_real_provider_artifact_is_rejected_without_runtime_authorization`、artifact self-ack、success/reward | 3 | registry loader 只验证 artifact row，完整 real-provider row 仍注册为 frozen generated operator，无 runtime fallback。 |
| `test_non_boolean_runtime_authorization_flags_fail_closed[...]` | 20 | solver/config 尚不读取两类 runtime authorization flag，所有 truthy/falsy 非 bool 均被忽略并继续部署。 |
| `test_literal_false_runtime_authorization_flags_block_deployment[...]` | 3 | literal False 也没有形成部署门禁。 |
| `test_runtime_authorization_source_is_required_for_real_provider_deployment` | 1 | runtime source 缺失不影响当前 registry 加载。 |
| `test_execution_policy_missing_runtime_authority_evidence_fails_closed[...]` | 5 | policy 对 effective level/identity 使用可信默认，并忽略 runtime source/allow/ack evidence。 |
| `test_arbitrary_callable_is_not_trusted_executor_authority` | 1 | execution eligibility 仅检查 callable 非空。 |
| `test_validation_schema_defaults_are_conservative` | 1 | validation schema 默认 safe、无需风险确认和可信 sandbox/identity。 |
| Phase 4F 规格与 operator 文档检查 | 2 | 正式规格仍写 Phase 4D 且缺 frozen runtime authorization；operator 文档仍有 sandbox 措辞冲突。 |

- **既有边界回归：** Phase 4/4B/4C/4D/4E 五文件 → 159 passed、1 个既有 warning（14.63s）。
- **完整套件：** `pytest -q --tb=no` → 36 failed、250 passed、1 warning（25.55s）；36 个失败全部来自 `tests/test_operator_runtime_authorization_frozen_deployment_red.py`，既有 249 个测试全部通过。

### Phase 4F 最小 GREEN 计划

1. 在 `ALNSConfig`/统一 eligibility policy 中增加 runtime-owned frozen deployment allow、explicit risk ack 和 authorization source，全部严格 literal bool/完整证据校验。
2. frozen registry loader 在 artifact metadata/hash/AST 之后、构造 `CandidateProxy` 之前执行 provider-aware runtime deployment gate；无授权结构化 fallback，artifact 中同名字段完全不参与授权。
3. 让 execution eligibility 对 effective sandbox、executor identity、runtime source/allow/ack 缺失 fail closed，并要求可信 proxy/receipt，而非任意 callable。
4. 将 `OperatorValidationResult` 的 safety、risk、sandbox/identity 默认改为 conservative/unknown；canonical loader 必须显式填充 runtime evidence。
5. 保持 timeout-only 策略：只有 literal allow=True、literal runtime ack=True、明确 current-runtime source 才允许 real-provider frozen deployment，同时继续标注非 capability sandbox。
6. 同步正式规格 Phase 4F 与 `docs/operator_evolution.md` 口径，不改变实验协议或运行 provider。
7. 按 Phase 4F 专项 → Phase 4–4E 边界 → operator evolution/frozen ALNS → 完整 pytest → compileall 验证，并再做独立复审。

- **最终状态：** Phase 4F RED complete，等待用户授权 GREEN。仅新增测试与规划记录；未修改生产代码、既有测试或文档正文，未运行真实 LLM/provider、实验或 Phase 5。
- **完成前核对：** 规划文件可检索到 Phase 4F RED 状态、36/1 结果与 GREEN 顺序；新增测试文件共 37 collected 节点。工具修改记录仅包含该新测试和三份规划文件，未对 `src/`、既有测试或文档正文执行编辑。

## 2026-08-05：Phase 4F GREEN 开始

- **授权与基线：** 用户授权从 37 collected、36 failed/1 passed 的 Phase 4F RED 进入最小 GREEN；既有 249 个测试在 RED 完整套件中通过。
- **实现顺序：** conservative schema/runtime evidence → unified execution/deployment policy → ALNS registry gate/fallback → canonical loader evidence → docs → 分层回归。
- **范围：** 仅 operator-evolution policy/schema/loader、frozen deployment 所需的 ALNS 注册边界、必要 fixture 迁移与两份文档；不改搜索策略、问题模型、DP、baseline 或 local search。
- **限制：** 不调用真实 LLM/provider，不运行实验、大规模计算或 Phase 5。
- **loader 映射：** `load_and_validate_candidate` 已在 smoke 前构造 `CandidateProxy` 并调用共同 eligibility；只需让 runtime configurator 显式填充 authority fields，schema 可安全改为 conservative defaults。
- **兼容性预判：** 现有一个 direct-policy 正例用 lambda/默认 authority 表示“完整证据”；GREEN 后会按新合同迁移为 proxy + 显式 evidence，保留断言语义。其余 ALNSConfig 调用默认不启用 frozen real-provider，不应受新增默认 false 字段影响。
- **首轮生产实现：** eligibility policy 要求 `CandidateProxy`、显式 effective/identity/runtime source/两类 bool evidence；runtime configurator 显式注入这些字段。新增独立 frozen deployment authorization helper，只读取 row 的 provider，授权值来自调用者 runtime 参数。
- **ALNS 部署边界：** `ALNSConfig` 新增默认 false/empty 的 allow、risk ack、source；registry metadata 通过后、构造 proxy 前调用 runtime gate，拒绝时记录 `missing_runtime_authorization`/`real_provider_deployment_blocked`、fallback_used=True。
- **保守 schema：** validation 默认 sandbox/effective/identity 为 unknown、safe=False、requires ack=True，并新增默认 false/empty runtime evidence；canonical loader 通过共同 configurator 显式提升到可信 runtime 事实。
- **Phase 4F 首轮专项：** 由 36 failed/1 passed 收敛为 3 failed/34 passed。27 个 frozen runtime gate 负例、五类 execution evidence、任意 callable 与 schema 默认均已转绿。
- **剩余三项：** 正向授权 source 使用测试约定的 `current_runtime_config`，而 allowlist 仅含 `current_config/current_session/operator_evolution_runner_policy`；另两项为尚未同步的文档。下一步补充同义的明确 runtime source 并更新两份文档，不改变门禁强度。
- **文档现状：** 正式规格的实现状态仍标 Phase 4D，尚未描述 real-provider frozen deployment 的 runtime-only allow/ack/source；operator 文档同时使用“no sandboxed execution”和“timeout-only subprocess”，且 frozen 配置只列旧三字段。
- **第二轮修复：** runtime source allowlist 补充明确的 `current_runtime_config` 同义值；正式规格更新为 Phase 4F，并明确 artifact safety/risk/sandbox/identity 仅为审计、不能授权 frozen deployment。
- **operator 文档：** 增加 real-provider generation/frozen runtime warning、三项当前配置授权要求及 artifact self-authorization 禁令；统一为“没有 capability sandbox，只有 timeout-only subprocess”，保留 CPU/内存/文件系统/网络/环境变量/后代进程树风险。
- **Phase 4F 专项 GREEN：** `pytest -q --tb=short tests/test_operator_runtime_authorization_frozen_deployment_red.py` → 37 passed、1 个既有 `pyreadline` warning（0.66s）；原 36 个 RED 全部转绿，正向 timeout-only 授权锚点继续通过。
- **六阶段首次合并回归：** 196 collected → 1 failed、195 passed。唯一失败是 Phase 4D 的 direct-policy 正例仍用 lambda 和旧 schema 默认值表达“完整证据”；新合同按设计拒绝任意 callable/缺 runtime evidence。下一步只迁移该 valid fixture 为 `CandidateProxy` + 显式 runtime fields，保留正例断言，不放宽生产 policy。
- **旧 fixture 迁移：** Phase 4D 同组正/负 direct-policy fixture 均改用 `CandidateProxy` 与完整显式 runtime authority；负例继续逐字段篡改，避免因 lambda 被提前拒绝而产生假绿。未修改断言或生产门禁。
- **Phase 4D 回归：** `tests/test_operator_strict_policy_config_hardening_red.py` → 59 passed、1 个既有 warning（1.37s）。
- **Phase 4–4F 六阶段边界：** 196 passed、1 个既有 warning（15.28s）；首次合并的唯一 fixture 失败已消除，Phase 4F 专项和此前五阶段边界全部保持 GREEN。
- **operator-evolution 回归：** `test_operator_evolution*.py` → 17 passed、1 个既有 warning（7.15s）。
- **frozen/ALNS 回归：** `tests/test_alns_solver.py tests/test_alns_frozen_operator_integration.py` → 4 passed、1 个既有 warning（1.16s）。
- **完整套件 GREEN：** `pytest -q` → 286 passed、1 个既有 `pyreadline` 弃用 warning（25.19s）；无失败、skip 或 xfail。
- **编译检查：** `python -m compileall -q src` → exit 0、无输出。

## 2026-08-05：Phase 4F GREEN 完成

- **生产修改：** `eligibility_policy.py`（runtime evidence、proxy requirement、deployment authorization gate）、`schemas.py`（保守默认）、`alns_solver.py`（默认关闭的 runtime config 与 registry pre-registration gate/fallback）。
- **文档修改：** `docs/llm_operator_evolution_spec.md`、`docs/operator_evolution.md` 同步 Phase 4F、artifact self-authorization 禁令和 timeout-only 风险。
- **测试适配：** Phase 4D direct-policy 正/负 valid fixture 迁移为 `CandidateProxy` + 显式 runtime evidence；断言保持不变，负例仍逐字段触发。Phase 4F RED 测试未删除、skip 或放宽。
- **最终专项：** Phase 4F 37 passed；Phase 4–4F boundary 196 passed；operator evolution 17 passed；frozen/ALNS 4 passed。
- **最终完整验证：** `pytest -q` → 286 passed、1 个既有 `pyreadline` warning（25.56s）；`python -m compileall -q src` → exit 0。
- **未执行：** 未调用真实 LLM/provider，未运行实验、大规模计算或 Phase 5。
- **剩余风险：** 当前仍不是 capability sandbox，CPU、内存、文件系统、网络、环境变量和后代进程树未隔离；`source_provider` provenance 仍未签名，需在真实 provider 解禁前独立复审。
- **规划日志修正：** 首次完成段因补丁命中较早上下文而落在 Phase 4E 记录前，本条已移动到文件末尾；生产实现与验证证据不受影响。
- **下一步：** 对 Phase 4F GREEN 做独立代码复审。复审前 Phase 5、真实 LLM 与大规模实验继续 blocked。

## 2026-08-05：Phase 4F GREEN 独立复审进行中

- **范围：** 只读审查 runtime authorization、schema defaults、unified eligibility、frozen registry/selection/freezing/reward 与两份设计文档；不修改生产代码或测试，不调用真实 provider，不运行实验。
- **已确认的正向行为：** registry 明确标记为 `langchain_openai_compatible` 时，缺当前 runtime allow/risk ack/source 会在注册 `CandidateProxy` 前结构化拒绝并记录 `missing_runtime_authorization` fallback。
- **Critical 复现：** 对同一源码、同一正确 hash 和同一完整 evidence，仅把未签名 registry 字段 `source_provider` 从 `langchain_openai_compatible` 改成 `mock`，默认无授权 solver 即从“拒绝 + fallback”变为“成功注册 frozen operator、无 fallback”。当前部署 gate 用 artifact 自报 provider 分类决定是否需要 runtime authorization，provider provenance 未绑定，因此真实来源 artifact 仍可通过重标标签绕过 Phase 4F 门禁。
- **诊断边界：** 使用临时目录和静态 repair fixture，仅初始化 solver；未调用候选、真实 LLM/provider 或实验。
- **下一步：** 继续核对 selection/freezing/reward、public execution authority、mock/file/manual 回归和文档表述；随后重新运行完整 pytest 与 compileall，并给出 Critical/Required/Consider/FYI gate。

## 2026-08-05：Phase 4F GREEN 独立复审完成

- **结论：** Request changes。Phase 4F 对“明确标为 real provider 的 row”实施了有效 runtime authorization，但 provider provenance 仍由 artifact 的可变 `source_provider` 字段决定，因此命名 Critical 未被完整关闭。
- **Critical：** real-provider artifact 只需把 `source_provider` 重标为 `mock`，即可绕过 `validate_frozen_deployment_authorization()` 的 real-provider 分支，在默认无 runtime allow/ack/source 时注册 frozen `CandidateProxy`。由于后续 generated 身份依赖 frozen set，成功调用后还可能进入 `llm_operator_success` 和 reward。
- **Required：** 增加 provider relabel/tampered provenance 负例；把 provider identity 绑定到 runtime-owned provenance receipt/可信 manifest，或在 provenance 缺失时对所有 generated frozen artifact 一律要求 deployment authorization；在修复前收敛两份文档中“artifact 自证均无效/真实 provider 默认阻止”的过度声明。
- **已确认：** literal bool 校验、schema conservative defaults、缺 runtime evidence fail closed、任意普通 callable 拒绝、expected hash + 同源码 AST、缺 selection/freezing evidence、invalid/timeout/fallback reward 隔离，以及 mock/file/manual 既有路径回归均保持通过。
- **专项回归：** Phase 4F + strict policy + trusted executor + frozen/ALNS → 124 passed、1 个既有 `pyreadline` warning。
- **完整验证：** `pytest -q` → 286 passed、1 个既有 warning（26.18s）；`python -m compileall -q src` → exit 0、无输出。
- **未执行：** 未修改生产代码或测试；未调用真实 LLM/provider；未运行实验、大规模计算或 Phase 5。
- **Gate：** 不允许进入 Phase 5 文档化实验协议；继续禁止真实 LLM；继续禁止大规模实验。先用 TDD 关闭 provider provenance Critical，再独立复审。

## 2026-08-05：Phase 4G RED 开始

- **目标：** 只新增失败测试，锁定 trusted provider provenance、所有 generated frozen artifacts 的 runtime deployment gate、strict runtime bool、freezing/selection/feedback claimed-provider 语义与文档事实。
- **技能约束：** 已完整读取 `planning-with-files`、`test-driven-development` 与 testing anti-patterns；使用真实 policy/solver/freezing/feedback 路径和临时文件，避免只验证 mock 调用。
- **基线：** Phase 4F 独立复审已实证同一源码/hash/evidence 仅将 `source_provider` 从 real provider 重标为 `mock` 即从拒绝变为注册；完整套件当时为 286 passed。
- **范围：** 只允许新增测试和更新三份规划文件；不修改 `src/`、既有测试或文档正文，不调用真实 provider，不运行实验、大规模计算或 Phase 5。
- **计划：** 复用 Phase 4F 完整 registry fixture，新增独立 Phase 4G 测试文件；先 collect，后运行专项观察预期 assertion failures，再跑既有边界回归确认无意外回归。
- **新增测试文件：** `tests/test_operator_provider_provenance_generated_deployment_red.py`。测试使用临时静态 repair 源码、真实 registry/solver、真实 metadata/selection/freezing/feedback 接口；没有 mock provider/API 调用。
- **测试分组：** real→mock 重标、八类 claimed provider 的统一 runtime gate、完整授权正向锚点、五类 provenance/lineage 缺失、五类 provenance 畸形/unknown、claim/provenance mismatch、两项 runtime flag 的非 bool 参数化、usage/reward 隔离、selection/freezing/feedback、freezing claimed 字段和 formal spec 事实。
- **生产边界：** 截至新增测试完成，未修改任何 `src/`、既有测试或文档正文。下一步先 collect 并修正测试自身 collection/fixture 错误，再确认预期 RED。
- **收集结果：** `pytest --collect-only -q tests/test_operator_provider_provenance_generated_deployment_red.py` → 42 collected、0 collection errors、1 个既有 `pyreadline` warning。正向锚点与各负例节点均成功收集。
- **首轮专项：** 40 failed、2 passed、1 warning。通过项是 honest real-provider 默认拒绝和 literal runtime authorization 正向锚点；其余均暴露预期合同缺失。
- **测试自身修正：** freezing claimed-provider 节点因直接访问尚不存在的 `claimed_source_provider` 产生 `KeyError`。改为 `.get(...)` 后断言缺字段，确保 RED 是预期 assertion failure；未改变期望行为或生产代码。
- **专项 RED 复核：** `pytest -q --tb=short tests/test_operator_provider_provenance_generated_deployment_red.py` → 40 failed、2 passed、1 warning（1.38s）。40 项均为预期 assertion failure；2 个通过节点分别锁定 honest real-provider 默认拒绝与 literal runtime authorization 正向锚点。
- **既有边界回归：** Phase 4/4B/4C/4D/4E/4F 六文件 → 196 passed、1 个既有 warning（16.07s）。未删除、skip、放宽或破坏既有测试。
- **完整套件 RED：** `pytest -q --tb=no` → 40 failed、288 passed、1 个既有 `pyreadline` warning（26.96s）。40 个失败全部来自新 Phase 4G 文件；此前 286 个既有测试全部通过，另有 Phase 4G 两个正向/既有锚点通过。

### Phase 4G RED 失败分组

| 分组 | RED 数 | 失败原因 |
|---|---:|---|
| real→mock 重标、七类非 canonical-real claim、usage/reward 隔离 | 9 | deployment gate 由 artifact `source_provider` 决定；非 real 名单值直接注册 frozen operator。 |
| provenance/lineage 缺失、unknown/类型错误、provider mismatch | 11 | metadata、selection 与 freezing 完全忽略新 evidence 字段，返回 valid/eligible。 |
| mock generated path 的 allow/ack 非 bool | 16 | strict bool 只在 real-provider 分支执行；mock claim 跳过 runtime gate。 |
| claimed mock/file 的 selection/freezing/feedback | 2 | 缺 provider provenance 仍进入 selection，因而也可能进入 leaderboard/top/weak。 |
| freezing claimed-provider 输出 | 1 | registry 只复制 `source_provider`，没有显式 `claimed_source_provider` 或 provenance trust-level。 |
| formal spec | 1 | 尚未明确 `source_provider` 是 claim、trusted provider provenance 合同与普通字符串不是 capability token。 |

### Phase 4G 最小 GREEN 计划

1. 在统一 eligibility policy 中定义 generated artifact audit schema：`artifact_type`、`claimed_source_provider`、结构化 `provider_provenance`、`generation_run_id`、`artifact_identity`、`lineage`，缺失/畸形/mismatch 一律拒绝。
2. 把 frozen deployment gate 改为 provider-agnostic：只要是 generated frozen artifact，在可信 provenance receipt 尚未实现时都要求当前 runtime literal allow=True、literal risk ack=True 和 accepted authorization source；默认 False，claim 值不参与授权。
3. 保留 `source_provider` 兼容审计，但重命名/复制为 `claimed_source_provider`；artifact 内 provenance 只能标记 `artifact_claim`，不得生成 `trusted` receipt。
4. 让 generation/evaluator/freezing 产出完整 lineage/audit fields，让 selection/freezing/feedback/leaderboard 共用同一 fail-closed metadata policy。
5. 未授权/缺 provenance operator 在 proxy 注册前结构化 fallback，failure type 为 `missing_provider_provenance`、`missing_runtime_authorization` 或 `generated_artifact_deployment_blocked`；不进入 frozen set、success 或 reward。
6. 同步正式规格，明确 provider identity、executor identity、runtime source 字符串的证据级别和当前无 capability token/可信签名 receipt 的事实。
7. 依次运行 Phase 4G 专项、Phase 4–4G 边界、operator evolution/frozen ALNS、完整 pytest 与 compileall；随后独立复审。

- **最终状态：** Phase 4G RED complete，等待用户授权 GREEN。仅新增测试与三份规划记录；未修改生产代码、既有测试或文档正文，未运行真实 LLM/provider、实验或 Phase 5。

## 2026-08-05：Phase 4G GREEN 开始

- **授权基线：** 用户授权从 42 collected、40 failed/2 passed 的 Phase 4G RED 进入最小 GREEN；既有 Phase 4–4F 边界 196 passed，完整套件中原 286 项全部通过。
- **设计选择：** 所有 frozen generated artifact 使用 provider-agnostic runtime gate；`source_provider`/`claimed_source_provider` 仅作审计。当前不实现可信 receipt，artifact provenance 固定为 `artifact_claim`，因此部署必须依赖当前 runtime literal allow/ack/source。
- **兼容策略：** 新增通用 `allow_generated_frozen_deployment` / `explicit_runtime_deployment_ack`，同时保留 Phase 4F 旧字段作为严格布尔的兼容授权组合；任何一组出现非 bool 都不能通过，claimed provider 不参与选择分支。
- **实现范围：** eligibility policy、evaluator/evolution artifact metadata、freezing、ALNS frozen registry gate、必要旧 valid fixtures 和两份文档；不改搜索策略、建模、DP、baseline 或 local search。
- **验证顺序：** Phase 4G 专项 → Phase 4–4G 边界 → operator evolution → frozen/ALNS → 完整 pytest → compileall；不调用真实 provider或实验。
- **统一 policy 首步：** `eligibility_policy.py` 新增 generated artifact audit metadata builder，并把 artifact_type、claimed provider、结构化 artifact-claim provenance、generation run、artifact identity 与 lineage 纳入 selection/freezing/registry 必需证据。
- **Provider-agnostic gate：** frozen deployment authorization 不再读取 provider label 分支；新增通用 allow/ack 且与 Phase 4F legacy allow/ack 组成严格布尔兼容授权，任一 pair 只有 literal True+True 才可能通过。
- **ALNS runtime config：** 新增默认 False 的 `allow_generated_frozen_deployment` 与 `explicit_runtime_deployment_ack`，并在 proxy 构造前传入统一 gate；旧字段继续作为兼容输入但不再按 provider 分类放行。
- **产物元数据：** evaluator 与 invalid-row 路径统一生成 `artifact_type`、claimed provider、`artifact_claim` provenance、generation run、artifact identity 与 lineage；CSV schema 同步新增这些字段。
- **Freezing：** registry 写入 `claimed_source_provider` 和 audit provenance/lineage，并显式记录 `deployment_authorization_status=runtime_authorization_required`；不写 trusted provider provenance。
- **失败状态兼容：** 新 failure type 使用 `missing_runtime_deployment_authorization`，reason 同时保留 `missing_runtime_authorization` 兼容标记，确保旧审计消费者和 Phase 4G 新语义都可识别。
- **Phase 4G 首轮专项：** 41 passed、1 failed；唯一失败为 formal spec 尚缺明确的 `source_provider` claimed metadata / trusted provenance / capability-token 表述，生产行为 41 项已转绿。
- **文档同步：** formal spec 更新至 Phase 4G，明确 claimed provider、artifact-claim provenance、所有 generated frozen runtime authorization 及普通字符串证据不是不可伪造 capability token；operator guide 改为 provider-agnostic 默认拒绝。
- **Phase 4G 专项 GREEN：** `pytest -q tests/test_operator_provider_provenance_generated_deployment_red.py` → 42 passed、1 个既有 `pyreadline` warning（0.78s）；原 40 个 RED 全部转绿，两个锚点保持通过。
- **合并边界首轮：** 67 failed、171 passed。根因是 Phase 4–4F 旧 canonical valid fixtures 缺新增 provenance/lineage 或默认无 generated deployment authorization，在更早 gate 被拒绝；Phase 4G 专项仍全绿。策略是不放宽生产 gate，只迁移代表“有效 artifact/已授权 runtime”的共享 fixture。
- **fixture 批量补丁首次失败：** 多文件补丁假设 `test_operator_execution_gate_toctou_red.py` 已有 eligibility import block，实际 import 结构不同，apply_patch 整体未应用。下一步逐文件读取精确 imports 后拆分小补丁，不重复该上下文。
- **旧 valid fixture 迁移：** 六个 Phase 4–4F 边界文件的共享 candidate/registry helpers 使用生产 `build_generated_artifact_metadata()` 补齐 claimed provider、artifact-claim provenance 与 lineage；需要实际加载 frozen operator 的 solver fixture 显式提供通用 runtime allow/ack/source。
- **负例保持：** missing-field、invalid-timeout、capability claim、TOCTOU、runtime error、timeout、invalid contract 和 reward 断言均未修改；只补“本来代表完整有效 artifact/已授权 runtime”的前置证据，避免假绿或放宽 gate。

## 2026-08-05：Phase 4G GREEN 完成

- **生产修改：**
  - `src/mrta_rect_coverage/llm/operator_evolution/eligibility_policy.py`：统一 generated artifact audit schema、provider-agnostic deployment authorization、strict bool、provenance/lineage fail-closed validation。
  - `src/mrta_rect_coverage/llm/operator_evolution/evaluator.py`、`evolution_loop.py`：为成功与失败候选统一产出 claimed-provider、artifact-claim provenance、generation/artifact identity 与 lineage，并同步 CSV 字段。
  - `src/mrta_rect_coverage/llm/operator_evolution/freezing.py`：registry 只保存 claimed provider/untrusted provenance，并写明 `runtime_authorization_required`，不制造 trusted receipt。
  - `src/mrta_rect_coverage/heuristics/alns_solver.py`：新增默认关闭的通用 generated frozen allow/ack，并在 proxy 注册前调用统一 runtime gate；未修改 ALNS 搜索策略。
- **文档修改：** `docs/llm_operator_evolution_spec.md` 与 `docs/operator_evolution.md` 同步 Phase 4G：source provider 是 claim、可信 receipt 尚未实现、所有 generated frozen deployment 需 runtime authorization，普通 identity/source 字符串不是 capability token。
- **测试适配：** 六个 Phase 4–4F 边界测试共享 valid fixture、`test_operator_evolution_protocol_red.py` 与 `test_alns_frozen_operator_integration.py` 补齐 canonical provenance/lineage 和显式 current-runtime authorization。未删除、skip、放宽 Phase 4G RED 或任何负例断言。
- **兼容原因修正：** 合并边界首次为 20 个 Phase 4F 非 bool 节点保留了 fail-closed 行为，但新 fallback reason 缺旧审计 token；reason 增加 `missing_runtime_authorization` 兼容标记后，Phase 4F/4G 合计 79 passed。
- **Phase 4G 专项：** `pytest -q tests/test_operator_provider_provenance_generated_deployment_red.py` → 42 passed、1 个既有 warning；原 40 个 RED 全部转绿，两个正向锚点保持通过。
- **Phase 4–4G 边界：** `pytest -q --tb=short` 加七个边界文件 → 238 passed、1 个既有 warning（16.69s）。
- **Operator evolution：** 八个 `test_operator_evolution*.py` 文件 → 17 passed、1 个既有 warning（7.70s）。
- **Frozen/ALNS：** `tests/test_alns_solver.py tests/test_alns_frozen_operator_integration.py` → 4 passed、1 个既有 warning（1.15s）。
- **完整套件：** `pytest -q` → 328 passed、1 个既有 `pyreadline` 弃用 warning（26.95s）；无失败、skip 或 xfail。
- **编译检查：** `python -m compileall -q src` → exit 0、无输出。
- **错误记录：** 上下文恢复后 yielded pytest cell id 已失效，已用同一命令重新取得完整结果；一次 PowerShell brace-path 审计命令解析失败后改为显式路径；工作区 `.git` 为空目录，故未使用 Git diff 作证据。这些均未影响生产实现或测试结果，已同步到 `task_plan.md`。
- **未执行：** 未调用真实 LLM/provider；未运行实验、大规模计算或 Phase 5；未修改建模、DP evaluator、baseline、local search 或 ALNS 主搜索策略。
- **剩余风险：** 当前仍是 `timeout_only` 子进程边界，不是 capability sandbox；CPU、内存、文件系统、网络、环境变量和后代进程树未隔离；可信签名 provenance receipt 尚未实现。
- **下一步：** 对 Phase 4G GREEN 做独立代码复审。复审前 Phase 5、真实 LLM 和大规模实验继续 blocked。
- **最终收尾复核：** 规划文件更新后再次执行 `pytest -q` → 328 passed、1 个既有 warning（28.28s）；随后 `python -m compileall -q src` → exit 0。最终状态与上述分层证据一致。

## 2026-08-05：Phase 4G GREEN 独立复审开始

- **范围：** 只读审查 claimed provider、generated frozen deployment、strict runtime authorization、freezing/registry、selection/feedback、mock/file/manual 兼容路径及两份文档；不修改生产代码或测试。
- **复审方法：** 先审 Phase 4G 与相关旧回归测试，再沿 `eligibility_policy` → freezing → ALNS registry deployment → selection/feedback 的真实调用链核对，最后运行新鲜专项、完整 pytest 与 compileall。
- **Gate：** 复审结束前不进入 Phase 5，不运行真实 LLM/provider，不运行实验或大规模计算。
- **测试审查初见：** Phase 4G 直接通过真实临时 registry/`ALNSSolver` 对比同源码 real 与 mock claim，参数化八类 provider claim、两类 runtime bool 的非 bool 值，并覆盖 selection/freezing/feedback、usage/reward 与正向授权锚点；测试意图是外部行为而非仅 mock 调用次数。
- **实现调用链初见：** `ALNSSolver` 先做完整 registry metadata 验证，再调用 provider-agnostic runtime authorization，随后才读取/hash/AST 校验并构造 `CandidateProxy`；拒绝项不会加入 frozen set。Generation 仍只支持 canonical mock/file/langchain provider，mock/file 的非 frozen provider factory 路径未被 frozen deployment policy改写。
- **专项复审回归：** Phase 4G + mock/file provider + candidate loader/evolution loop + frozen integration 共 48 passed、1 个既有 `pyreadline` warning；provider relabel/default-deny、正向 runtime authorization 与非 frozen兼容路径同时保持通过。

## 2026-08-05：Phase 4G GREEN 独立复审完成

- **结论：** Approve；无 Critical、无 Required。
- **核心确认：** provider claim 不参与 deployment authorization；real→mock 重标默认仍拒绝；所有 generated frozen artifacts 需要当前 runtime strict-bool allow/ack/source；freezing 不生成 trusted provenance；registry 不信任 JSON provider 字符串。
- **Lifecycle 确认：** selection/freezing/leaderboard/feedback 使用统一 eligibility；未授权、缺 provenance/lineage、invalid/timeout/blocked/fallback row 不进入 best/freeze/top/weak，未注册 operator 不获得 generated success/reward。
- **兼容确认：** mock/file provider、candidate loader/evolution loop、frozen 正向授权和 built-in ALNS 路径相关专项共 48 passed；manual 不是独立 provider 名称，现有人工交换由 file provider 覆盖。
- **文档确认：** formal spec/operator guide 不把 provider provenance、executor identity 或 runtime source 描述为签名/capability token；明确可信 receipt 未实现和 timeout-only 非 capability sandbox。
- **完整验证：** `pytest -q` → 328 passed、1 个既有 `pyreadline` warning（27.91s）；`python -m compileall -q src` → exit 0、无输出。
- **Consider：** 将 metadata validation + runtime authorization 合并为单一 typed deployment API；弃用 real-provider 命名兼容 pair；在真实 LLM/非受信 file code 解禁前实现 capability isolation 与可信 provenance receipt。
- **修改边界：** 未修改任何生产代码或测试；只更新 `task_plan.md`、`findings.md`、`progress.md`。未运行真实 LLM/provider、实验或大规模计算。
- **Gate：** 允许进入 Phase 5 文档化实验协议；继续禁止真实 LLM；继续禁止大规模实验。

## 2026-08-06：Phase 5A 启动

- **授权范围：** 只读代码/README/AGENTS/研究文档和 planning 文件，随后只创建研究设计文档；不改生产代码、问题模型、DP、ALNS 或 operator evolution 实现。
- **禁止项：** 不调用真实 LLM/provider，不运行实验或大规模计算，不使用最终 test instances 进行设计反馈，不进入 Phase 5B。
- **技能流程：** 使用 `planning-with-files` 持久化事实；使用 `brainstorming` 的设计审批门禁。当前环境没有 `spec-driven-development` skill，记录为能力缺失并以既有 formal spec + brainstorming 设计流程替代。
- **上下文恢复：** Phase 4G 独立复审已批准 Phase 5 文档化；目标五份研究文档目前均不存在。已读取 README、AGENTS、三份 planning 文件和 docs 文件清单。
- **当前状态：** 正在审查实际代码与研究规格；在提出候选 framing 并取得用户批准前，不写五份正式文档。
- **事实审查完成第一轮：** 已读取 core model/state/cost/route DP/solution evaluator、ALNS/local search/advisor、operator evolution/evaluator/prompts/freezing、benchmark runner 与现有 formal spec/operator guide。
- **关键边界：** route DP 只优化固定 task sequence 的 coverage states；LLM 不直接求解。现有 operator evolution 是单-best、非 instance-conditioned、无 portfolio、仅聚合 failure counts 的多轮离线闭环。
- **有效性风险：** Manhattan travel 当前未除 speed；默认 evolution benchmark 使用全部 data，无 train/dev/final-test 隔离；`dp_aware_insertion` 是 greedy alias，现有 DP-aware ablation 不可识别。
- **Brainstorming gate：** 下一步先澄清论文定位校准目标，再比较 2–3 种主线组合并请求批准；未创建五份正式文档。
- **定位选择：** 用户选择跨领域 AI-for-Optimization；LLM offline operator evolution 为论文主创新，MR-RCRP + DP-aware ALNS 为严格验证载体。下一步比较三种主线/辅助创新组合并请求最终设计批准。
- **设计批准：** 主线 A（multi-round offline operator evolution），辅助 C（behavior-complementary frozen portfolio）与 D（failure-informed revision），B 只作泛化/条件化消融。获批后开始创建五份正式文档。

## 2026-08-06：Phase 5A 完成

- **定位落盘：** 跨领域 AI-for-Optimization；A 是主创新，C/D 是辅助创新，B 只作泛化消融；MR-RCRP + DP-aware ALNS 是严格验证载体。
- **创建文档：**
  - `docs/research_positioning.md`：问题模型、route DP/ALNS/advisor/LLM 角色、实现事实/计划/候选贡献/未支持主张及 final-test lockbox。
  - `docs/innovation_review.md`：A–D 的新颖性潜力、代码匹配、实现成本、可证伪性、真实 LLM 依赖、审稿风险、baselines 与 ablations。
  - `docs/llm_operator_evolution_research_plan.md`：研究问题、数据隔离、A/C/D/B 机制、等预算协议、指标、每轮文件合同和执行顺序。
  - `docs/paper_contribution_plan.md`：核心/辅助/工程/实验贡献分层、六个候选表述裁决、claim ladder 和禁止措辞。
  - `docs/research_hypotheses.md`：H1–H7；每项包含 independent/dependent variables、baselines、ablations、falsification condition 与所需数据/日志。
- **关键边界：** portfolio、显式 top-k elite retention、failure-specific revision、instance conditioning 和 train/dev/final-test 清单隔离均标为 planned，而非已实现事实。
- **模型有效性记录：** 跨矩形 Manhattan travel 未除以 speed，内部 processing time 使用 `/speed`；文档明确只有 speed=1 或距离已按时间归一化时单位一致。
- **安全口径：** fail-closed protocol 作为可信实验支撑；当前仍是 timeout-only subprocess，不是 capability sandbox。
- **自查：** 核对五份文件存在、标题结构、A/C/D/B 一致性、one-shot/held-out/成本 controls、portfolio 未实现声明、final-test 零反馈规则和 H1–H7 六类必需字段。`TODO/TBD/FIXME` 扫描无结果；过度主张关键词只出现在“禁止措辞/不能声称/证据门槛”语境中。
- **结构化核验结果：** 五份目标文档全部存在；H1–H7 共 7 项，每个必需字段（independent/dependent variables、baselines、ablations、falsification condition、数据/日志）均出现 7 次；Phase 5A task checklist 全部完成。首次 PowerShell 核验因 `$label:` 解析失败，改用格式化字符串后成功重跑，文档内容不受影响。
- **完成门禁复核：** 最终文档检查 exit 0：五类内容检查 PASS、六类 hypothesis 字段各 7/7、无 TODO/TBD/FIXME、Phase 5A 无未勾选项、Phase 5B gate 与三份 planning 记录存在；`src_files_modified_today=0`。首次固定短语检查与正文“不是完整 capability sandbox”措辞不一致，修正检查词后重跑成功，未改正文迎合检查。
- **验证选择：** 本轮只修改 Markdown 文档和 planning 文件，没有生产代码或测试变化，因此未运行 pytest/compileall；未运行任何实验。
- **未执行：** 未调用真实 LLM/provider，未使用 final test instances，未修改算法生产代码，未进入 Phase 5B。
- **最终状态：** Phase 5A complete，等待用户审阅五份研究设计文档；后续阶段不自动开始。

## 2026-08-06：Phase 5A-R research-validity review

- **范围：** 只读复审五份 Phase 5A 文档，并与 README、AGENTS、formal spec、当前 data/config、route cost、operator evaluator/evolution/feedback、ALNS benchmark runner 交叉核对；只更新三份 planning 文件。
- **审查对象：** `research_positioning.md`、`innovation_review.md`、`llm_operator_evolution_research_plan.md`、`paper_contribution_plan.md`、`research_hypotheses.md`。用户消息中的第三个路径被截断，按 Phase 5A 完整交付范围审查全部五份。
- **正确性确认：** A/C/D/B 定位一致；LLM 不直接求解；DP 只精确评价固定 task sequence；portfolio/failure-specific revision/split 均标 planned；新颖性与性能未过度声明；安全口径明确 timeout-only 非 capability sandbox。
- **Critical no-go 1：** 缺独立 evolution-run 统计单位、嵌套/cluster-aware analysis 与 confirmatory hypothesis hierarchy；不能把同一 run 的 candidates 或确定性重复 seed 当独立样本。
- **Critical no-go 2：** 当前只有 `R2_T6_0.txt`、`R2_T10_0.txt` 两个 R2 单-replicate 实例，无法三分割或支持跨规模泛化；进入实验前还必须解决已记录的 speed 成本单位口径。
- **Required：** H2 拆因素；D failure taxonomy 分轴且互斥；C 明确 run-local test selector state；H5 定义共同成本 estimand；“可复用”限定为 MR-RCRP 问题族内复用。
- **Consider：** H1/H6/H3 confirmatory hierarchy、structural label reliability、provider drift blocking、portfolio dev stability。
- **验证证据：** 读取实际 evaluator 可见 repair baseline delta 方向正确、destroy 使用 fixed repair、seed 只驱动 candidate RNG；读取 data/config/runner 确认默认全量 glob、两实例、benchmark runner 默认 ALNS seed=0。未运行 pytest/compileall，因为生产代码和测试未修改。
- **错误记录：** 一次组合 `rg` 因末尾正则双重转义形成未闭合分组；文档锚点已返回，代码锚点随后拆成多个简单查询成功，已写入 `task_plan.md` error table。
- **修改边界：** 未修改五份研究正文、算法生产代码、测试、配置或数据；仅更新 `task_plan.md`、`findings.md`、`progress.md`。
- **结论：** Request changes（2 Critical experimental no-go + 5 Required）。只允许继续文档修订；未进入 Phase 5B，继续禁止真实 LLM、实验和大规模计算。

## 2026-08-06：Phase 5A-R research validity revision 开始

- **授权范围：** 只修改五份 Phase 5A 研究文档与三份 planning 文件；不修改 `src/`、`configs/`、`data/` 或测试，不运行真实 LLM、测试或实验，不进入 Phase 5B。
- **技能状态：** 使用 `planning-with-files`；当前环境无 `spec-driven-development` skill，以用户给出的逐项合同作为正式验收规格。
- **第一批修订：** `research_positioning.md` 已加入 MR-RCRP-family-only reuse、两实例 smoke/demo no-go、family-level split、默认 glob 风险、prototype metric blocking decision 和 final-test run-local selector state。
- **第二批修订：** `llm_operator_evolution_research_plan.md` 已加入独立 evolution-run unit、完整实验层级、primary estimand、两实例/单位 no-go、四轴 failure taxonomy、H2 2×2、cluster-aware statistics、confirmatory hierarchy、成本 estimands 与 final-test state reset。
- **第三批修订：** `research_hypotheses.md` 已把 H1 设为唯一 primary confirmatory，以 H6→H3 fixed-sequence gatekeeping；H2 改为 A/B 2×2 与 H2a/H2b/H2c；H5 改为 quality/cost constraints 与 Pareto；所有假设加入独立 run、层级 bootstrap 和 MR-RCRP-family scope。
- **第四批修订：** `innovation_review.md` 已同步 independent-run inference、两实例 no-go、四轴 D、H2 factorial、run-local portfolio selector、dev composition stability 与非 cross-domain empirical scope。
- **第五批修订：** `paper_contribution_plan.md` 已将 independent-run/family-held-out evidence 纳入 claim ladder，将成本贡献改为约束式/Pareto 分析，并禁止 cross-domain empirical reuse wording；五份文档的 D 表述统一为四轴 taxonomy。
- **合同核验：** PowerShell 文档检查 exit 0：2 Critical、5 Required 的必需术语与结构全部存在，五份目标文档齐全，无 TODO/TBD/FIXME；`src/`、`configs/`、`data/`、`tests/` 当日修改数均为 0。
- **Critical 修复摘要：** 独立 evolution-run、层级/primary estimand、cluster-aware/双层 bootstrap、H1→H6→H3 gatekeeping 已写入；两实例 smoke-only、family split、默认 glob 风险、final manifest 与 prototype-metric blocking decision 已写入。
- **Required 修复摘要：** H2a/H2b/H2c 2×2；四轴 taxonomy/precedence/denominators；portfolio run-local state reset；H5 quality/cost constraints + Pareto；MR-RCRP-family-only reuse 均已统一。
- **Consider deferred：** provider 时间块随机化与版本日志、portfolio dev-fold/bootstrap stability、behavior-first structural diagnostics 已纳入后续计划，但未实现、未宣称完成。
- **验证选择：** 用户明确禁止测试/实验，且未修改生产代码；因此没有运行 pytest、compileall、真实 LLM 或任何 benchmark。
- **最终状态：** Phase 5A-R revision complete（文档层面 2 Critical + 5 Required 已修复）。现有数据数量和 speed 单位的实际实验 no-go 仍然有效；未进入 Phase 5B。

## 2026-08-06：Phase 5A-S modeling and data split blockers

- **范围：** 只审查 README、AGENTS、Phase 5A-R 研究文档、planning 文件、相关 core 代码、当前 data 与 operator-evolution glob；只创建/更新文档和 planning 文件。未修改 `src/`、`configs/`、`data/`、`tests/`。
- **技能状态：** 使用 `planning-with-files` 维护持久计划；当前环境没有 `spec-driven-development` skill，按用户给出的逐项合同执行并进行文档合同核验。
- **代码事实：** 内部 `processing_time = length/speed + turn time`；depot/state/transition travel 都是 raw Manhattan distance；实例 schema 只有一个 `speed`。现有两个实例 speed=1，因此当前只能按隐含 `travel_speed=1` 的 prototype metric 理解。
- **数据事实：** 仅有 `R2_T6_0.txt` 和 `R2_T10_0.txt` 两个 R2 单-replicate 文件；默认 `data/R*_T*_*.txt` glob 会自动纳入全部匹配实例。
- **创建 `docs/modeling_decisions.md`：** 比较 A 当前 prototype、B 统一时间、C 归一化代价。推荐 B + independent `travel_speed` 作为正式实验口径；该推荐尚待批准、实现和测试，旧结果必须按 objective version 隔离并重跑。
- **创建 `docs/instance_protocol.md`：** 定义 family/instance record、size/spatial/burden 轴、smoke/small/medium/large/stress 层级、family-level split、replicate 建议、independent evolution-run 目标与 seed 嵌套；现有 R2 文件只允许 smoke/mock/file 闭环。
- **创建 `docs/final_test_lockbox_protocol.md`：** 定义 draft/frozen/opened/reported/contaminated 生命周期、manifest/hash、信息隔离、打开前冻结项、run-local adaptive selector、重试/污染规则与 default-glob 防线。
- **创建 `docs/experiment_no_go_checklist.md`：** 将建模批准/实现、实例生成/split、manifest、formal runner、统计、真实 LLM 隔离逐项设为 BLOCKING。当前明确为 NO-GO。
- **后续任务登记：** `task_plan.md` 已分列建模迁移（Instance/loader/CostMatrix/DP/lower bounds/tests/docs/result invalidation）和数据/lockbox（generator/families/manifests/formal runner/statistics）任务；均未在本阶段执行。
- **验证选择：** 用户禁止测试或实验且没有代码变更；本轮只执行只读文件/术语/清单检查，不运行 pytest、compileall、provider、benchmark 或 solver。
- **未决批准：** 是否采用 B + independent `travel_speed`；family matrix/replicate/evolution-run 预算；三份数据/lockbox 协议。批准之前 Phase 5B、真实 LLM、final-test 与大规模实验继续禁止。
- **下一步：** 由负责人审阅并批准/修订四份协议；即使文档获批，也需另行授权完成建模代码、数据生成与 manifest-only gate，不能直接开始实验。
- **验证修正：** 首次文档合同脚本因三个检索谓词与正文同义措辞不完全一致而 exit 1；回读确认协议语义已存在，并补充统一的 `exact input set`、两个 smoke 文件名绑定和 contamination→confirmatory 明示措辞后，重新执行完整合同核验。
- **最终文档合同：** 完整只读核验 exit 0，A/B/C、正式推荐、family 维度、五档规模、family split、重复/seed 嵌套、manifest-only、smoke 限制、lockbox/selector、NO-GO 与 planning 日志全部 PASS；四份新文档创建后 `src/configs/data/tests` 修改数为 0；NO-GO 清单仍有 33 个开放 BLOCKING 项。

## 2026-08-06：Phase 5A-S-R 独立复审开始

- **范围：** 逐段复审四份 Phase 5A-S 文档，并与当前 core cost、instance schema、data 清单、default glob 和 Phase 5A-R 统计层级交叉核对；只更新 planning 文件。
- **禁止项：** 不修改算法/配置/数据/测试，不运行 pytest、实验、solver、provider 或真实 LLM。
- **初审结论：** A/B/C 候选、prototype 边界、R2 smoke-only、family-level split、lockbox 与 manifest-only 防线总体完整，未见架构性 Critical。
- **待定 Required：** 拆分 Phase 5B-documentation 与 experiment-execution gate；消除“每 family train/dev reps”歧义；限定 B 的 estimated physical-time assumptions；在 Phase 5B 冻结每 split 的 distinct-family 最小数量。

## 2026-08-06：Phase 5A-S-R 独立复审完成

- **结论：** Request changes；0 Critical、4 Required。
- **通过项：** A/B/C 可批准候选完整；混合单位仍严格标 prototype；两个 R2 文件 smoke-only；family/replicate/evolution-run/seed 层级一致；lockbox 覆盖 prompt/generation/selection/portfolio/tuning 泄漏；default glob 有明确 manifest-only 规避目标。
- **Required 1：** 批准 B + independent `travel_speed` 时补齐 Manhattan、constant-speed、no-interaction 等 estimated-time 假设边界。
- **Required 2：** 拆分 Phase 5B documentation-entry gate 与 formal-experiment execution gate。
- **Required 3：** 明确 per-family repetitions 不跨 split，并在生成前冻结 family split assignment/rule。
- **Required 4：** 在 Phase 5B 冻结每 split/stratum 的 distinct-family 最小数量，使 family-level inference 可实施。
- **验证方式：** 逐段读取四份文档；检索 core state/cost/loader、EvolutionConfig/YAML/default glob、data 文件；与 research plan/hypotheses 的 independent-run hierarchy、primary estimand 和 bootstrap 规则交叉核对。未运行 pytest、compileall、solver、provider 或实验。
- **修改边界：** 未修改四份受审文档、算法代码、配置、数据或测试；仅更新 `task_plan.md`、`findings.md`、`progress.md`。
- **Gate：** 当前不允许进入 Phase 5B。完成 4 个 Required 并取得建模/instance/lockbox 决策批准后，可进入仅文档化 Phase 5B；真实 LLM、正式/final-test/大规模实验继续禁止。
- **收尾核验：** 16 个 review contract 项全部 PASS：A/B/C、prototype guard、R2 smoke-only、family split/hierarchy、lockbox leakage、manifest-only glob、no-go completeness、0 Critical/4 Required 与三个禁止结论均有文档证据；四份受审文档 SHA-256 已输出存档。未运行代码测试或实验。

## 2026-08-06：Phase 5A-S 建模决策获批

- **批准内容：** 候选 B——统一时间单位 + independent `travel_speed`，作为正式实验主口径。
- **解释边界：** estimated completion time under Manhattan travel、constant speed、no collision/congestion、no acceleration/deceleration、no charging/refueling；不称为完整真实机器人执行时间。
- **Sensitivity：** `travel_speed=sweep_speed` 只作 sensitivity，不作主口径或默认值。
- **文档同步：** `modeling_decisions.md` 改为 approved/正式决策并补齐假设；`experiment_no_go_checklist.md` 关闭批准与口径选择两项，但保留 objective version、实现、测试和数据门禁。
- **Planning 同步：** Phase 5A-S-R Required 1 已关闭，剩余 3 个 Required；当前仍不进入 Phase 5B，不运行真实 LLM、final-test 或大规模实验。
- **修改边界：** 未修改 `src/`、`configs/`、`data/`、`tests/`，未运行测试、provider 或实验。
- **核验修正：** 首次批准合同检查 18/19 项通过，唯一 `approved_status` 因 Markdown 正则写错星号位置未命中；正文已是“状态：已批准”，改用 literal matching 重新核验，不改正文。
- **最终核验：** 20 项批准合同全部 PASS；旧 direct-physical-time 表述不存在；`src/configs/data/tests` 在建模文档更新后修改数为 0；NO-GO 清单仍有 32 个开放 BLOCKING 项。

## 2026-08-06：Phase 5A-SR required revisions 开始

- **授权范围：** 只修改 `modeling_decisions.md`、`instance_protocol.md`、`final_test_lockbox_protocol.md`、`experiment_no_go_checklist.md` 与三份 planning 文件。
- **技能状态：** 使用 `planning-with-files`；当前环境没有 `spec-driven-development` skill，按用户给出的 Required 1–4 合同逐项验收。
- **禁止项：** 不修改 `src/configs/data/tests`，不进入 Phase 5B，不运行测试、真实 LLM、provider、solver 或实验。
- **初始状态：** Required 1 的核心批准已存在；Required 2–4 仍需文档修订。实例协议还存在 per-family train/dev 歧义、生成后 split 的允许路径和 distinct-family minimum 缺口。
- **错误记录：** 首个 modeling+instance 组合补丁因 4.4 hunk 顺序与原文件不一致而 verification failed；补丁未应用，改按单文件/原文顺序拆分，不重复同一失败方式。

## 2026-08-06：Phase 5A-SR required revisions 正文完成

- **Modeling：** B 保持获批 formal decision；A 标为 prototype legacy，C 标为 alternative not selected；迁移/no-paper-evidence 边界补齐。
- **Two-level gate：** checklist 已拆分 Gate A documentation-entry 与 Gate B formal execution；Gate A 尚缺 instance/lockbox 独立批准，状态 NOT PASSED。
- **Family split：** family 定义补 `generation_rule_version`；per-family reps 不跨 split；assignment/rule 和 hashes 在生成前冻结；禁止按 geometry/baseline/LLM performance 后选 split。
- **Distinct-family floor：** 每个纳入 stratum 设 train 4、dev 4、final-test 8；不足降级 pilot/exploratory。Replicate/evolution-run 候选数留待 Phase 5B precision/power 冻结。
- **Pilot/lockbox：** formal pilot 仅 train/dev，不接触 final-test；final assignment、family/split hashes 与 contamination owner 纳入 lockbox。
- **Gate 建议：** 4 个 Required 的正文修订均已完成，建议下一步进行 Phase 5B documentation-entry independent review；本轮不进入 Phase 5B。
- **边界：** 未修改 `src/configs/data/tests`，未运行测试、provider、真实 LLM 或实验。纯文档合同验证待执行。
- **规格核验：** 43 项合同全部 PASS，覆盖 Required 1–4、Gate A/B、Phase 7 real-LLM preflight、family split/hash、formal pilot、distinct-family floor、family-level inference、Consider 与 planning 同步；`src/configs/data/tests` 修改数为 0。
- **最终状态：** Phase 5A-SR complete。建议进入 Phase 5B documentation-entry independent review，但 Gate A 仍为 NOT PASSED，本轮未进入 Phase 5B；真实 LLM 和所有正式/大规模实验继续禁止。
## 2026-08-06：Phase 5A-SR-R independent review 开始

- 使用 `planning-with-files` 恢复上下文，并按 `code-review-and-quality` 对四份建模/数据协议做独立复审。
- 逐份读取 `modeling_decisions.md`、`instance_protocol.md`、`final_test_lockbox_protocol.md` 与 `experiment_no_go_checklist.md`；未修改受审协议正文。
- 初步确认正式 B 口径、estimated-time 限定、sensitivity、双层 gate、family split/lockbox、distinct-family inference 与 R2 smoke-only 均有明确文本证据。
- 下一步只读核对当前 data、travel-cost 与 default glob 事实，然后形成 Critical/Required/Consider/FYI 结论。
- 禁止项保持：未运行真实 LLM、provider、solver、测试或实验，未修改算法代码。

## 2026-08-06：Phase 5A-SR-R independent review 完成

- **结论：** Approve；Critical 0、Required 0。
- **只读证据：** 四份协议逐段复核，并与当前两个 R2 文件、单 `speed` loader、raw-Manhattan CostMatrix 和默认全量 glob 交叉核对。
- **合同核验：** 24/24 PASS，覆盖用户列出的 13 个重点及当前代码/数据事实。
- **Phase 5B：** 允许进入仅文档化实验协议；本轮没有进入 Phase 5B。受审 checklist 的两项待 review 标记留待 Phase 5B 首次文档同步，本次独立审查记录构成批准证据。
- **继续禁止：** 真实 LLM、provider、正式/final-test/大规模实验。Gate B 仍有 32 个 EXEC-BLOCKING，real-LLM 另有 2 个 blocking。
- **Consider：** Phase 5B 用预先规定的 precision/power 分析检验 4/4/8 family floor 是否足够；不足只能增加预注册 family 或降级 pilot，不得用 replicates 或 post-hoc selection 补偿。
- **错误记录：** 项目根不是 Git 仓库，`git status/diff` 不可用；改用 SHA-256、合同检查和显式只读检索，未重复失败命令。
- **未执行：** 未修改四份受审协议、算法代码、配置、数据或测试；未运行 pytest/compileall、solver、provider、真实 LLM 或实验。
## 2026-08-06：Phase 5B paper-grade experiment protocol documentation 开始

- 已读取附件中的完整 Phase 5B 规格；`spec-driven-development` skill 在当前环境不可用，使用用户附件作为正式验收合同。
- 8 份目标实验协议文档均不存在，将基于已批准的 Phase 5A 研究/建模/数据合同新建。
- 当前授权仅限文档：不会调用真实 LLM/provider，不运行实验或 final-test，不修改 `src/configs/data/tests`，不进入 Phase 6。
- 下一步读取上游假设、研究计划、建模、实例、lockbox 与 NO-GO，再按 RQ→protocol→ablation/statistics→manifest/reproducibility/tables/pilot 顺序落盘。

## 2026-08-06：Phase 5B 上游合同与 Gate A 同步

- 已读取并交叉核对 H1–H7、A/C/D/B 定位、正式建模、instance family/split、lockbox 与 NO-GO 文档。
- `experiment_no_go_checklist.md` 的 instance protocol 与 lockbox protocol 两项已按 Phase 5A-SR-R 独立批准标为完成；Gate A 更新为 `PASSED (documentation only)`。
- Gate B 的 EXEC-BLOCKING 与 REAL-LLM-BLOCKING 未关闭；同步没有授权代码迁移、data generation、provider、solver、final-test 或实验。

## 2026-08-06：Phase 5B paper-grade protocol 文档完成

- 创建 `research_questions.md`、`experiment_protocol.md`、`ablation_plan.md`、`statistical_analysis_plan.md`、`manifest_spec.md`、`reproducibility_checklist.md`、`result_table_plan.md`、`pilot_plan.md`。
- 固定 RQ1–RQ7/H1–H7 映射、objective_v1/v2 边界、minimum family matrix、non-LLM/generated conditions、等预算合同和 A/C/D/H2 ablations。
- 固定完整 evolution run 独立单位、run×family 推断、H1→H6→H3 gatekeeping、two-way cluster bootstrap、failure denominators 与 pilot downgrade rule。
- 定义 manifest-only exact input/hash contract、复现证据、9 张论文结果表和不接触 final-test 的 pilot lifecycle。
- 第一轮合同核验：161 checks、0 failures；forbidden scope changes=0；Gate B 仍有 32 EXEC-BLOCKING，real-LLM 仍有 2 blocking。
- 一致性扫描：无 TODO/TBD/FIXME；真实 LLM/正式/final-test/大规模实验禁令一致；stress combinations 已明确为 `(12,480)`、`(16,800)`。
- 下一步：Phase 5B research-protocol independent review。未进入 Phase 6，未运行测试、provider、solver、LLM 或实验，未修改 `src/configs/data/tests`。
- **核验错误：** 首次最终合同脚本因 PowerShell 反引号转义导致 parser error，未执行任何文档判断；已定位为检查脚本问题，将使用无反引号字段检索的替代脚本重新验证。
- **最终核验：** 替代脚本从头执行并通过：189 checks、0 failures、0 forbidden-scope changes、0 placeholder/overclaim hits；8 份文档 SHA-256 已记录在工具输出。
- **Gate 证据：** Gate A 的 DOC-BLOCKING 全部关闭；Gate B 仍有 32 个 EXEC-BLOCKING，real-LLM 仍有 2 个 REAL-LLM-BLOCKING。
## 2026-08-06：Phase 5B-R research-protocol review 开始

- 使用 `planning-with-files` 恢复上下文，并按 `code-review-and-quality` 对九份 Phase 5B 协议做独立研究有效性复审。
- 只读审查 objective、统计单位、A/C/D/H2 归因、family/lockbox、manifest-only、result claims 和 train/dev-only pilot。
- 不修改受审协议或算法代码，不运行测试、solver、provider、真实 LLM 或实验。
## 2026-08-06 — Phase 5B-R research-protocol review（进行中）

- 按 `planning-with-files` 与 `code-review-and-quality` 开始独立研究协议审阅；未修改算法代码、测试、配置、数据或被审阅协议正文。
- 已完整读取 6/9 份目标文档：`research_questions.md`、`experiment_protocol.md`、`ablation_plan.md`、`statistical_analysis_plan.md`、`manifest_spec.md`、`reproducibility_checklist.md`。
- 已记录初步证据：实验边界、objective 版本、独立 evolution-run、family split/lockbox、A/C/D、H2 factorial 与 H5 Pareto 基本一致；主分析失败轮处理、MCID 判据、唯一聚合规则、H2 response 和 manifest 严格 schema 仍需核查/修订。
- 下一步：审阅 `result_table_plan.md`、`pilot_plan.md`、`experiment_no_go_checklist.md`，执行轻量文本一致性检查，然后形成 Critical / Required / Consider / FYI 结论。
- 未运行真实 LLM、实验或测试。

## 2026-08-06 — Phase 5B-R research-protocol review（完成）

- 已完整审阅用户指定的 9 份 Phase 5B 文档，并用轻量 `rg` 做 objective、独立单位、MCID、H2、manifest、glob、lockbox 与 NO-GO 口径交叉检查。
- 结论：**Request changes（1 Critical、4 Required）**。
- Critical：主 estimand 尚未冻结 `no_valid_operator`、freeze/deployment blocked、整轮无可评价 portfolio 等 scheduled evolution-run failure 的主分析处理；只聚合 valid paired results 会造成 generated-method 幸存者偏差。
- Required：H1/MCID 支持判据不一致；stage-1 聚合和 primary model 尚非唯一；H2a/H2b 未绑定 primary response/scale/denominator；manifest schema 缺显式实例唯一合同且含多处 union 类型，尚不足以直接支撑 canonical manifest-only runner。
- 已确认通过：实验禁令、objective v2/v1 边界、独立 evolution-run、防伪重复、family split/lockbox/no-glob、A/C/D、H2 factorial、H5 Pareto、table claim boundaries 和 train/dev-only pilot。
- 准入结论：本轮不建议进入 Phase 6A；应先修复研究协议。真实 LLM、正式/大规模实验和 final-test 仍禁止。
- 仅更新 planning 文件；未修改 9 份被审阅协议、算法代码、tests、configs 或 data；未运行测试、实验或 provider。
## 2026-08-07 — Phase 5B-R statistical and manifest revision 开始

- 使用 `planning-with-files` 恢复上下文并读取附件中的 1 Critical + 4 Required 修订合同。
- 当前环境没有可调用的 `spec-driven-development` skill；以附件逐项规格作为验收合同。
- 已将 failure-aware scheduled-run estimand、H1a/H1b、唯一聚合、H2 responses 和 strict manifest schema 登记到 `task_plan.md`。
- 授权范围仅为协议/planning 文档；不修改 `src/configs/data/tests`，不运行测试、实验、solver、provider 或真实 LLM，不进入 Phase 6A。
- 已完整读取 statistical/experiment/ablation/manifest/result/reproducibility/pilot/research-hypotheses 八份相关文档，并确认上一轮 1 Critical + 4 Required 均对应现存文字缺口。
- 已冻结本轮文档设计选择：failure run=0 improvement 的 scheduled-run primary、two-way cluster bootstrap 为唯一 primary CI、H1a/H1b 分离、H2a quality/H2b deployability response，以及 strict typed manifest contract。
- 下一步：分批修改统计/假设/消融，再修改 manifest/result/reproducibility/experiment/pilot，并执行纯文本合同核验。
- 已完成八份协议正文修订：统计/假设/消融、strict manifest、scheduled-run accounting/result table、reproducibility、experiment boundary 与 pilot re-registration boundary。
- 第一轮 `rg` 核对确认新口径存在且旧 primary/MCID/aggregation union-type措辞基本清除。
- **检查错误：** 第二轮 manifest union-type regex 因 PowerShell/regex 字符类转义错误导致 `rg` parse error、command exit 1；heading 与 H1 legacy 两部分已正常输出。该错误只影响检查脚本，未修改文件；后续改用 PowerShell literal assertions，不重复该正则。
- **合同检查误报：** 首次 literal contract check 将正文中的禁止性说明“不得以 string/list 等 union 类型表达”误判为旧 schema，exit 1。实际旧 `notes | string/list` 字段行已不存在；下一次检查改为匹配旧表格完整行，不重复宽泛 token 检索。

## 2026-08-07 — Phase 5B-R statistical and manifest revision 完成

- 修改协议：`statistical_analysis_plan.md`、`experiment_protocol.md`、`ablation_plan.md`、`manifest_spec.md`、`result_table_plan.md`、`reproducibility_checklist.md`、`pilot_plan.md`、`research_hypotheses.md`。
- 修改 planning：`task_plan.md`、`findings.md`、`progress.md`。
- Critical：all scheduled evolution runs 进入 failure-aware primary；method failure run=0 improvement；fallback 不归因；complete-case supplementary-only；contaminated batch不产生 confirmatory estimate。
- Required：H1a/H1b 分离；唯一 equal-seed/replicate/family/run aggregation + primary two-way cluster bootstrap；H2a quality/H2b deployability estimands；strict typed/canonical/path-safe manifest schema。
- 同步 Table 0 scheduled-run accounting、Table 1 failure-aware main result、reproducibility scheduled IDs/schema hashes、Phase 6A/manifest implementation blockers 与 pilot re-registration boundary。
- 最终纯文档合同：`document_contract_checks=80`、`document_contract_failures=0`、`files_verified=11`，command exit 0；无 merge conflict markers。
- 未运行 pytest、compileall、solver、benchmark、provider、真实 LLM 或任何实验；未进入 Phase 6A；未修改 `src/configs/data/tests`。
- 当前状态：1 Critical + 4 Required 已在文档层修订，等待独立 research-protocol review。Phase 6A、Gate B、真实 LLM、正式/大规模/final-test 实验继续 blocked。
- 完成前从磁盘重新执行同一完整合同：80 checks、0 failures、11 files、exit 0，并输出各文件 SHA-256；该验证发生在正文与 planning 状态更新之后。
- 禁止范围的 LastWriteTime 辅助枚举未返回可用文件明细，因此不作为范围证明；本轮所有 `apply_patch` 写目标均显式限制在八份协议和三份 planning 文件。
## 2026-08-07 — Phase 5B-R-R research-protocol revision review 开始

- 使用 `planning-with-files` 恢复上下文，并按 `code-review-and-quality` 开始只读研究协议复审。
- 已读取 planning records 与 statistical/experiment/ablation/manifest 四份协议；上一轮 1 Critical + 4 Required 的主体修订均有直接文本证据。
- 正继续核对两个潜在残余边界：部分 run×family/replicate/seed 评价失败的主分析处理，以及 duplicate file hash/path 是否跨 split manifests 联合 fail closed。
- 未修改受审协议或算法代码，未运行测试、solver、provider、真实 LLM 或实验。
- 已继续读取 `result_table_plan.md`、`reproducibility_checklist.md`、`pilot_plan.md`，并对 cell missingness、cross-split duplicate 与 H1 hierarchy 做全文检索。
- 初步 verdict：0 Critical、2 Required candidates。Whole-run failure bias 已关闭，但部分 solver/family evaluation failure 仍可发生 cell-level complete-case bias；manifest duplicate-file rule 尚未明确跨 train/dev/final-test manifests 联合执行。
- 两项 Consider：reproducibility checklist 的 gatekeeping shorthand 仍写 H1 而非 H1a；旧 Phase 5B-R task-plan section 仍显示 in_progress。

## 2026-08-07 — Phase 5B-R-R research-protocol revision review 完成

- 完整复核用户指定的 7 份协议和 3 份 planning 文件；另只读交叉检索 lockbox/NO-GO 条款。
- Review check：16 项中 14 pass、2 open；结论 **Request changes（0 Critical、2 Required）**。
- 已关闭证据：all scheduled runs、whole-run failure=0、complete-case supplementary、H1a/H1b/MCID、唯一聚合、run×family bootstrap、H2 responses、strict manifest core、scheduled-run result accounting 和全部执行禁令。
- Required 1：已部署 portfolio 的部分 family/replicate/solver-seed timeout/invalid/fallback/missing 尚无唯一 primary delta 映射，仍可能出现 cell-level complete-case bias。
- Required 2：duplicate file hash/path/file identity 尚未明确在 train/dev/final-test manifests 合并集合上联合 fail closed；不同 family metadata 可让同一 exact file 获得不同 instance IDs。
- Planning hygiene：已把旧 Phase 5B-R historical section 从 stale `in_progress` 归档为 complete，并登记两项 Phase 6A 前 Required。
- Gate：暂不允许 Phase 6A；真实 LLM、正式/大规模/final-test 实验继续禁止。
- 仅修改 `task_plan.md`、`findings.md`、`progress.md`；未修改协议正文、算法代码、配置、数据或测试，未运行 pytest/compileall、solver、provider、真实 LLM 或实验。
- **验证脚本错误：** 首次完成前检查把 findings 中实际使用的“跨 split manifests 联合检查”误写为 `cross split manifests 联合检查`，因此 literal assertion exit 1；review evidence 与协议正文未变。后续改用实际中文/英文混合措辞重跑，不重复该错误检查。
# Phase 5B-R3 progress (2026-08-07)

- Started the document-only revision; no source, config, data, or test files were touched and no tests, experiments, or providers were run.
- Reviewed the statistical cell mapping, manifest contract, experiment flow, no-go gates, lockbox/reproducibility requirements, and result-table accounting.
- Confirmed two required edits: split localized result-artifact failure from batch integrity contamination, and split the train/dev pilot preflight from the formal three-manifest lockbox preflight.
- Next: apply the frozen taxonomy and lifecycle consistently across the allowed protocol documents, then perform text-only consistency checks and update planning records. Phase 6A remains unopened.
- Revised `docs/statistical_analysis_plan.md` to separate localized generated-result failures (cell `0`) from objective/input/manifest/split/lockbox/baseline-pairing integrity failures (batch contaminated/inconclusive, no effect value).
- Revised manifest, experiment, lockbox, no-go, reproducibility and result-table protocols to define distinct pilot and formal preflight receipts and ordering.
- Synchronized the `fully attributable family rate` name, baseline-pairing status and unsupported file-identity risk. No code/tests/config/data were changed; no tests, provider calls or experiments were run.
# 2026-08-12 — Phase 6B-T1R2 GREEN independent implementation repair review

- 使用 `planning-with-files` 恢复项目状态，并按 `code-review-and-quality` 开始独立复审。
- 授权边界保持：仅可运行 `python -m pytest tests/test_pilot_contract_schema_red.py -q`；不运行完整测试、provider、candidate、pilot、benchmark、真实 LLM 或 final-test。
- 复审对象限定为 `pilot_contracts.py`、目标测试/fixtures 与三份 planning 文件；不修改生产实现、测试或 fixtures。
- Gate P2、pilot execution、正式/大规模/final-test 实验继续处于 blocked 状态。
- **只读命令错误：** 首次分段输出源码时在 PowerShell 双引号字符串中使用 `$p:`，触发变量解析错误；命令未读取或修改项目文件。后续改用格式化字符串，不重复该表达式。
- 完成 tests-first 与实现审查：non-preflight 状态、validated/rejected branch、五个具名 evidence object、strict enum/type、hash-format-only 与 pure-data boundary 均符合本轮范围。
- Fresh 运行唯一授权命令 `python -m pytest tests/test_pilot_contract_schema_red.py -q`：153 passed、1 个既有 pyreadline DeprecationWarning，exit 0；未运行完整 pytest。
- Review verdict：**Request changes（0 Critical、1 Required）**。剩余问题是 `validation_receipt_invalid` / `runtime_authorization_denied` 可由任意无关 evidence 的 reject decision 支撑，违背 reason-specific evidence 语义；现有测试未覆盖该交叉旁路。
- 下一步应为最小 T1R3 RED/GREEN：先增加 unrelated-evidence rejection tests，再为两个 reason 增加对应 evidence 合同或在当前 schema 下 fail closed。修复并复审前不得进入 T2。
- 禁令保持：真实 LLM/provider、candidate、pilot、benchmark、正式/大规模/final-test 实验均未授权；Gate P2 未关闭。

# 2026-08-12 — Phase 6B-T1R3 RED

- 按 `planning-with-files` 与 `test-driven-development` 启动 RED-only 切片；只允许修改目标测试、必要 fixtures 与 planning 文件。
- 已核对 T1R2 review Required、现有 provider-negative 正例矩阵和 `_manifest_request_rejection` helper；本轮不修改 `pilot_contracts.py`。
- 计划冻结三组行为：validation receipt reason 的专属证据、当前 runtime authorization reason 无 schema 支撑时 fail closed、所有保留 reasons 的 unrelated-evidence rejection anchors。
- T2、Gate P2、真实 LLM/provider、candidate/pilot/benchmark、正式/大规模/final-test 实验继续 blocked。
- 修改 `tests/test_pilot_contract_schema_red.py`：从旧合法正例矩阵移除 `provider_claim_mismatch` 与 `runtime_authorization_denied`；复用现有 fixture，新增 evidence-decision helper 和 13 个语义 cases。
- 新增覆盖：`validation_receipt_invalid` 的四类 unrelated reject + manifest pass；`runtime_authorization_denied` 的 manifest/scope unrelated reject；五个已有专属 reason 的 unrelated reject anchors；缺专用 evidence 的 provider claim mismatch fail-closed。
- 仅运行 `python -m pytest tests/test_pilot_contract_schema_red.py -q`：164 collected（7 failed + 157 passed）、1 个既有 pyreadline warning，exit 1。
- 7 个失败全部是预期的 `valid=True` 旁路：validation receipt 4、runtime authorization 2、provider claim mismatch 1；没有 collection、import、fixture JSON、syntax 或基础设施错误。
- RED complete；未修改生产代码或 fixtures。建议下一步单独授权 T1R3 GREEN，不进入 T2。

# 2026-08-12 — Phase 6B-T1R3 GREEN

- 用户已授权最小 GREEN；沿用上一轮 fresh RED 证据（7 failed、157 passed）。
- 设计选择：当前 schema 只保留 real/unknown provider、uncontrolled glob、final-test scope、manifest scope 五种可证明 reason；validation receipt、provider claim mismatch、runtime authorization 因无专用 evidence 字段而 fail closed。
- 实现范围仅为 `_rejection_is_supported` 与 runner rejection enum/real-provider reason allowlist；不扩展 schema，不新增任何执行或 I/O 能力。
- 已修改 `pilot_contracts.py`：移除三个无专属 evidence 的 reasons、删除通用 fallback、real-provider allowlist 仅保留 `real_provider_forbidden`，未知 reason 返回 False。
- 首次目标测试：2 failed、162 passed、1 个既有 warning。原 7 个 T1R3 RED 均已转绿；剩余两个失败来自本轮 OR 文字与既有 glob tests 的直接合同冲突。
- 按用户指令停止：未修改 tests/fixtures，未继续重跑。等待确认 glob support predicate 应采用 OR 还是既有 tests 的更严格 AND。

# 2026-08-12 — Phase 6B-T1R3 GREEN implementation repair review

- 使用 `planning-with-files` 恢复 T1R3 RED/GREEN 历史，并按 `code-review-and-quality` 开始独立复审。
- 复审范围限定为 `pilot_contracts.py`、目标测试/fixtures 与三份 planning 文件；受审代码、测试和 fixtures 保持只读。
- 唯一允许执行的项目命令为 `python -m pytest tests/test_pilot_contract_schema_red.py -q`；不运行完整 pytest、provider、candidate、pilot、benchmark、真实 LLM 或 final-test。
- Fresh 目标测试结果为 **2 failed、162 passed、1 warning**，exit 1；两个失败均是 `uncontrolled_glob_forbidden` 的 OR 实现仍接受单项证据，而既有测试要求 mode 与 detected flag 同时成立。
- 因此磁盘状态不能证明 T1R3 GREEN complete；复审至少为 Request changes，T2 不可准入。
- 静态能力复核通过：无 path/file access、file identity、hash recomputation、runner/provider/candidate/pilot execution；fixtures 均可解析，validated fixture 保持 `accepted_execution=false`。
- Reason mapping 复核通过：通用 fallback 已删除；三个无专属 evidence reasons 当前 fail closed；其余五个 reasons 不跨用无关 evidence。
- 最终 verdict：**Request changes（0 Critical、1 Required）**。唯一 Required 是 glob OR 实现与两个既有 AND regression tests 的合同不一致；在目标套件全绿并复审前不允许 T2。
- 继续禁止真实 LLM/provider、pilot execution、正式/大规模/final-test 实验；本轮未运行任何未授权命令。

# 2026-08-12 — Phase 6B-T1R3-FIX GREEN

- 使用 `planning-with-files` 与 `test-driven-development` 恢复 T1R3 review 状态；沿用 fresh RED 证据：2 failed、162 passed、1 个既有 warning。
- 一次聚合式只读检查输出因规划文件较长被工具截断；随后改用 `rg` 与精确行区间读取，未重复该大输出方式，且未修改任何文件。
- 仅修改 `pilot_contracts.py` 中 `uncontrolled_glob_forbidden` 的专属 predicate：glob input mode 与 `glob_detected=True` 从 OR 收紧为 AND。
- 未修改 tests、fixtures 或 docs；未增加 path/file access、file identity、hash recomputation、runner/provider/candidate/pilot execution。
- 仅运行授权命令 `python -m pytest tests/test_pilot_contract_schema_red.py -q`：164 passed、1 个既有 pyreadline DeprecationWarning，exit 0。
- 两个 `uncontrolled_glob_forbidden` AND-contract failures 已转绿；当前目标文件无失败测试。
- Phase 6B-T1R3-FIX GREEN complete，建议进入独立 implementation review；T2、Gate P2、真实 LLM/provider、pilot、正式/大规模/final-test 实验继续 blocked。

# 2026-08-12 — Phase 6B-T1R3-FIX narrow implementation review

- 按 `planning-with-files` 恢复 FIX 记录，并按 `code-review-and-quality` 开始 tests-first 的窄范围独立复审。
- 初步静态核对确认 glob predicate 已使用 glob-mode、`glob_detected=True`、accepted-input-null、reject-decision 四项 AND；helper 尾部仍为 unsupported reason `return False`，没有通用 evidence-reject 回退。
- 能力边界初查：模块仅导入 dataclass/math/re/typing，仍声明并保持 pure parsed-data validation；未发现文件/path/hash/provider/runner/candidate/pilot 执行导入。
- 尚未形成最终 verdict；唯一可运行测试仍限定为 `python -m pytest tests/test_pilot_contract_schema_red.py -q`，所有执行 gate 保持 blocked。
- 完成 tests-first 细查：三个 glob evidence mutation tests 能捕获 mode-only、detected-only 与 non-reject decision 旁路；rejected fixture 的 accepted fields 为 null、execution 为 false。
- 完成实现细查：unsupported reasons 无 generic fallback；status 仍为 inert preflight-only；validated receipt 仍拒绝 execution/scheduling authority。
- 静态 capability token 检索仅命中用于格式校验的 `_SHA256_RE`，未发现 path/file access、hash computation 或动态执行调用。
- Fresh 运行唯一授权命令 `python -m pytest tests/test_pilot_contract_schema_red.py -q`：164 passed、1 个既有 pyreadline DeprecationWarning，exit 0；未运行完整 pytest。
- Review verdict：**Approve（0 Critical、0 Required）**。本次 AND 修复、专属 evidence、fail-closed unsupported reasons、preflight-only 与 pure-data boundary 均通过。
- 允许下一步单独授权 Phase 6B-T2，仍建议最小任务为 PIV-02 scoped-hash verification RED-only tests；本轮未进入 T2。
- Gate P2、真实 LLM/provider、candidate/pilot、benchmark、正式/大规模/final-test 实验继续 blocked。

# 2026-08-12 — Phase 6B-T2 PIV-02 scoped-hash RED

- 使用 `planning-with-files` 恢复 T1R3-FIX approval，并按 `test-driven-development` 启动 RED-only 切片。
- 附件合同已读取：只允许新增 scoped-hash 测试/可选最小 fixtures 与 planning records；严禁修改任何 `src/`、现有合同测试、docs/configs/data。
- 通过 `brainstorming` 做最小边界核对：用户附件已提供并批准完整设计，因此直接采用独立 `pilot_integrity` API、内存对象/bytes 和 no implicit file access 方案，不扩展范围。
- 现有文档事实与附件一致：PIV-02 独立、canonical receipt IDs 非自引用、evidence 纳入 hash、pilot matrix/rule hashes 不得提升为 formal。
- 当前尚未新增测试或运行 pytest；Gate P2 与所有 provider/pilot/formal/large-scale/final-test gates 保持 blocked。
- 新增 `tests/test_pilot_scoped_hash_red.py`；未新增 fixtures，因为全部合同可用内存 JSON objects/bytes 确定性表达。
- 测试冻结未来 `pilot_integrity` 的 canonical/hash-format、pilot scope/non-promotion、manifest/validator/runner receipt binding、evidence-in-hash 与 explicit-content-only APIs。
- 测试使用延迟 import，把目标模块缺失转换为清晰 pytest failure；未创建或修改任何 `src/` 文件。
- 尚未运行目标 pytest；下一步只执行附件授权的单一测试命令。
- 仅运行 `python -m pytest tests/test_pilot_scoped_hash_red.py -q`：59 collected、59 failed、0 passed、1 个既有 pyreadline DeprecationWarning，exit 1。
- 59 个 failures 全部为预期的 `Phase 6B-T2 RED: pilot scoped-hash integrity module is not implemented`；没有 collection error、syntax error、fixture parsing error 或意外通过。
- 详细失败回溯因输出量超过工具上限而被截断；最终 pytest summary 与 failure list 足以确认同一根因，未重复命令。
- 本轮只新增 `tests/test_pilot_scoped_hash_red.py` 并更新三份 planning 文件；未新增 fixtures，未修改任何 production code、现有 tests、docs/configs/data。
- 未实现 canonical/hash/receipt recomputation、path/file access、path resolution、file identity、runner/provider/candidate/pilot；未运行 provider/pilot/benchmark，也未接触真实 final-test artifact。
- Phase 6B-T2 RED complete；建议单独授权 T2 GREEN。Gate P2、真实 LLM/provider、pilot、正式/大规模/final-test 实验继续 blocked。

# 2026-08-13 — Phase 6B-T2 PIV-02 scoped-hash GREEN

- 使用 `planning-with-files` 恢复 59-case RED，并按 `test-driven-development` 接受单独 GREEN 授权。
- 完整读取附件、目标测试 752 行及 experiments package；确认只创建独立 `pilot_integrity.py`，不修改 903 行 pure-data `pilot_contracts.py`。
- 实现设计：严格递归 JSON domain validation + deterministic UTF-8 canonical bytes；显式 bytes/object SHA-256；pilot matrix/rule scope；validator/runner 非自引用 IDs 与跨 receipt binding；explicit-content-only boundary。
- 尚未写入生产实现或运行 GREEN 测试；Gate P2 与真实 LLM/provider、pilot、正式/大规模/final-test 实验继续 blocked。
- 新增 `src/mrta_rect_coverage/experiments/pilot_integrity.py`：不可变 integrity result、严格 JSON-domain validation、deterministic canonical bytes、显式 SHA-256、pilot scoped hash、validator/runner receipt IDs 与 cross binding、explicit-content-only verification。
- 实现未导入或调用 pathlib/open/os/subprocess/provider/runner/candidate；`file_path` 仅作为 final-test marker 字符串审计，不用于解析或读取。
- 首次运行 T2 专项即全绿：59 passed、1 个既有 pyreadline DeprecationWarning，exit 0；无需修改测试或进行失败修补。
- 下一步按授权可选项运行 T1+T2 两文件联合回归；不运行完整 pytest。
- 选择性运行 `python -m pytest tests/test_pilot_contract_schema_red.py tests/test_pilot_scoped_hash_red.py -q`：223 passed、1 个既有 pyreadline DeprecationWarning，exit 0。
- 使用 `verification-before-completion` 核对 fresh evidence：T2 专项与 T1+T2 联合命令均 exit 0；没有把专项通过外推为完整套件、Gate P2 或 pilot execution 通过。
- 最终修改文件仅为新增 `pilot_integrity.py` 和更新 `task_plan.md`、`findings.md`、`progress.md`；未修改 `pilot_contracts.py`、tests、docs/configs/data。
- 未实现 file/path access、path resolution、file identity、manifest runner、provider、candidate execution 或 pilot；未运行 provider/pilot/benchmark，未接触真实 final-test artifacts。
- Phase 6B-T2 GREEN complete，建议进入独立 GREEN implementation review。真实 LLM/provider、pilot、正式/大规模/final-test 实验继续禁止，Gate P2 未关闭。

# 2026-08-13 — Phase 6B-T2 GREEN implementation review

- 使用 `planning-with-files` 恢复 T2 RED/GREEN 证据，并按 `code-review-and-quality` 启动 tests-first 独立复审。
- 复审范围锁定为 `pilot_integrity.py`、T2 tests、只读确认 `pilot_contracts.py` 与三份 planning records；只允许运行 T2 专项及可选 T1+T2 联合 pytest。
- 文件时间与阶段记录一致：`pilot_integrity.py` 写于 2026-08-13；`pilot_contracts.py` 最后写入为 2026-08-12 T1R3-FIX，未见 T2 阶段改写证据。
- 初查通过 pure in-memory capability boundary：integrity 模块只导入 dataclass/hashlib/json/math/re/typing，无 open/pathlib/os/subprocess/runner/provider/candidate/pilot 能力。
- Scoped verifier 当前只拒绝 `final_test` marker，需继续核对批准合同中 `formal_train`/`formal_dev` 在 pilot instance fields 内是否也能 fail closed；最终 verdict 尚未形成。
- 一次宽范围文档搜索输出超过上下文预算并被截断；未改变文件。后续改用逐文件、窄 pattern 读取，确认 validator spec 明确拒绝 `formal_train/formal_dev/formal_final_test`，且 receipt/hash spec 明确要求 RFC 8785/JCS。
- 初步发现两项可能的 Required：pilot record 内 `formal_train/formal_dev` marker 未被 scoped verifier 拒绝；canonicalizer 尚无 RFC 8785/JCS conformance 证据。待用最小内存探针和授权 pytest 验证。
- 逐行核对 cross binding 后发现第三项 fail-closed 缺口：validator/runner/evidence 的 `manifest_hash` 同时缺失时，当前比较逻辑可因 `None == None` 而不报错；现有 T2 只测不一致值，未测缺失/非法值。
- 未运行自定义探针或越权命令；上述结论来自静态控制流与测试覆盖对照。下一步仅运行用户授权 pytest。
- Fresh T2 专项：`python -m pytest tests/test_pilot_scoped_hash_red.py -q` → 59 passed、1 warning、exit 0。
- Fresh T1+T2 联合：`python -m pytest tests/test_pilot_contract_schema_red.py tests/test_pilot_scoped_hash_red.py -q` → 223 passed、1 warning、exit 0。
- 尝试 `git status/diff` 时确认项目目录不是 Git worktree；命令 exit 1，未修改文件。改用阶段记录、源码内容与 mtime 核对，`pilot_contracts.py` 时间早于 T2，未见 T2 改写证据。
- 一次同时读取三个 skill 文件的输出被截断；随后按文件分块完成 `planning-with-files` 全文和 Codex reference 读取；`code-review-and-quality` 的完整内容已从该次输出覆盖到结尾。未重复失败命令。
- 最终 review：0 Critical、3 Required。通过项包括纯内存边界、严格 JSON domain、lowercase SHA-256、非自引用 receipt ID、evidence 参与 hash、explicit-content-only/no-read 行为；阻塞项为 formal train/dev marker、RFC 8785/JCS conformance、cross-layer missing/invalid manifest hash。
- 暂不允许 T3；建议下一步单独授权 T2R RED-only。Gate P2 未关闭，真实 LLM/provider、pilot、正式/大规模/final-test 实验均继续禁止。

# 2026-08-13 — Phase 6B-T2R RED-only

- 使用 `planning-with-files` 与 `test-driven-development` 启动 T2R；用户给出的详细 RED 合同视为已批准测试设计，不修改协议或生产实现。
- 修改范围锁定为 `tests/test_pilot_scoped_hash_red.py` 与三份 planning 文件；当前不需要 fixture，所有边界均可用显式 in-memory objects/handwritten bytes 表达。
- 计划增加三组 tests：formal train/dev scope leakage、独立 JCS vectors、cross-receipt missing/invalid hash/ID；只运行授权的 T2 单文件 pytest。
- 更新 `tests/test_pilot_scoped_hash_red.py`：新增 formal split/nested semantic scope tests、8 个手写 JCS bytes vectors、补充 negative infinity，以及 cross-receipt manifest hash/validation receipt ID fail-closed cases。
- 未新增 `tests/fixtures/pilot_integrity`：显式 in-memory objects 与 literal bytes 足以表达全部合同，避免引入文件读取语义。
- 仅运行授权命令 `python -m pytest tests/test_pilot_scoped_hash_red.py -q`：89 collected、13 failed、76 passed、1 个既有 pyreadline DeprecationWarning，exit 1。
- 13 个预期 failures：formal train/dev scope leakage 4；RFC 8785/JCS number formatting 3；三层 equal-but-invalid/missing manifest hash 6。没有 syntax、collection、fixture parsing 或非目标异常。
- 新增的顶层 formal scope、nested formal-final-test、JCS ordering/UTF-8/control、non-finite、validation receipt ID mismatch controls 通过，表明 RED 没有破坏已实现合同。
- production mtime/size 检查未显示本轮写入；未修改任何 `src/`、docs/configs/data，也未实现或调用 path/hash production fix、runner、provider、candidate、pilot。
- Phase 6B-T2R RED complete；建议进入单独授权的 T2R GREEN。T3 与 Gate P2 仍 blocked，真实 LLM/provider、pilot、正式/大规模/final-test 实验继续禁止。

# 2026-08-13 — Phase 6B-T2R GREEN

- 使用 `planning-with-files`、`test-driven-development` 与 `systematic-debugging` 接受单独 GREEN 授权；13 个 RED 已在前序阶段真实观察。
- 完成 root-cause tracing：final-test-only marker、whole-object Python JSON number formatting、cross-receipt equality-before-domain-validation 分别对应 4/3/6 failures。
- 实现范围锁定为 `pilot_integrity.py`：计划增加递归 formal scope predicate、纯内存 JCS serializer 与 strict cross-layer hash/id validation；不修改 tests、`pilot_contracts.py` 或协议。
- 修改 `src/mrta_rect_coverage/experiments/pilot_integrity.py`：增加 formal scope recursion、`RFC8785-JCS/jcs-v1` pure serializer、strict validation receipt/manifest hash evidence checks。
- T2/T2R 首次 GREEN 命令 `python -m pytest tests/test_pilot_scoped_hash_red.py -q`：89 passed、1 个既有 pyreadline warning、exit 0；13 个 RED failures 全部转绿，无补改测试。
- 授权联合回归 `python -m pytest tests/test_pilot_contract_schema_red.py tests/test_pilot_scoped_hash_red.py -q`：253 passed、1 个既有 warning、exit 0。
- 静态能力检查确认模块没有 open/pathlib/path resolution/symlink/hardlink/inode/file identity/runner/provider/candidate/pilot；`file_path` 仍只作为显式字符串 marker，不被解析或读取。
- 本轮未修改 `pilot_contracts.py`、任何 tests、docs/configs/data；未运行完整 pytest、provider、candidate、pilot 或 benchmark，也未访问真实 final-test artifacts。
- Phase 6B-T2R GREEN complete；建议进入独立 implementation review。Gate P2 未关闭，真实 LLM/provider、pilot、正式/大规模/final-test 实验继续禁止。

# 2026-08-14 — Phase 6B-T2R GREEN implementation review

- 使用 `planning-with-files` 与 `code-review-and-quality` 启动独立复审；只读审查目标实现/tests/`pilot_contracts.py`，仅 planning records 可写。
- Tests-first 初查确认 T2R 新增了 formal train/dev isolating cases、8 个手写 JCS vectors、三层 equal-but-invalid manifest hash，以及 validation receipt ID/evidence 负例；explicit-content/no-read controls 保留。
- 下一步以 RFC 8785 标准原文核对 number/string/key ordering 声明，再逐行审查实现；不运行 provider/candidate/pilot/benchmark，不接触真实 final-test artifacts。
# Phase 6B-T2R GREEN independent implementation review (2026-08-14)

- Status: complete — Request changes (0 Critical, 1 Required).
- Scope: static review of `pilot_integrity.py`, scoped-hash tests, unchanged-boundary evidence for `pilot_contracts.py`, and planning records.
- Fresh authorized test evidence:
  - `python -m pytest tests/test_pilot_scoped_hash_red.py -q` -> 89 passed, 1 existing warning.
  - `python -m pytest tests/test_pilot_contract_schema_red.py tests/test_pilot_scoped_hash_red.py -q` -> 253 passed, 1 existing warning.
- Confirmed pass areas: pure in-memory boundary; no path/file/provider/runner/execution capability; recursive formal train/dev/final-test rejection; current handwritten number/Unicode vectors; strict lowercase 64-hex checks before cross-receipt comparison; evidence-bound non-self-referential receipt IDs; explicit-content-only behavior.
- Required found: `canonical_json_bytes()` accepts arbitrary Python integers and serializes them exactly, which is not the declared RFC 8785/ECMAScript binary64 number contract for values such as `2**68`. Existing tests cover only a small selected vector set and do not expose this mismatch.
- T3 is not authorized. Recommended next bounded step: Phase 6B-T2R2 RED-only tests using official RFC 8785 Appendix B edge vectors plus a frozen policy for Python integers outside the interoperable JCS number domain; then GREEN and independent review.
- `pilot_contracts.py` was not edited in T2R according to timestamp/size and phase records; the workspace has no Git metadata for a commit-level diff.
- Restrictions remain active: no provider, candidate, pilot, benchmark, full test suite, or final-test access.

# 2026-08-14 — Phase 6B-T2R2 RED-only

- Started with `planning-with-files` context recovery and the approved `test-driven-development` RED-only boundary.
- Read the existing T2 canonicalization tests and confirmed that they currently cover selected handwritten values but not the safe-integer boundary or official Appendix B bit-pattern cases.
- Frozen the RED design: accept Python ints only through `2**53-1` in magnitude; reject `±2**53`, `2**68`, larger arbitrary-precision values, and nested out-of-domain integers; retain Appendix B binary64 cases as valid float conformance tests.
- Production code, fixtures, docs, configs, data, provider/runner/candidate/pilot paths, and final-test artifacts remain untouched.
- Modified only `tests/test_pilot_scoped_hash_red.py` plus the three planning files. Added `struct`-based in-memory IEEE-754 construction, safe-boundary cases, six scalar out-of-domain cases, two nested cases, and 18 Appendix B finite vectors; no fixture was needed.
- Ran only the authorized command `python -m pytest tests/test_pilot_scoped_hash_red.py -q`.
- Result: 118 collected, 8 failed, 110 passed, 1 existing warning, exit 1. All 8 failures are expected `DID NOT RAISE` outcomes from the current arbitrary-precision Python-int acceptance; the complete float Appendix-B vector set and existing regressions passed.
- No production implementation was modified. No hash/path implementation, file access, runner, provider, candidate, pilot, benchmark, or final-test operation was implemented or invoked.
- Post-RED metadata confirms production files retain their earlier timestamps and contents: `pilot_integrity.py` timestamp `2026-08-13 22:07:55.4490667`, SHA-256 `56D60178D383A599F7857107A653223D4725DC5BBE9F03C9DECF4B6433DFD198`; `pilot_contracts.py` timestamp `2026-08-12 21:54:57.6612576`, SHA-256 `2902BB3CB8F3D78B9A5A764708672D7E35C3C73133FFA1DD6902E90707D1C873`.
- Phase 6B-T2R2 RED complete. Recommend a separately authorized minimal GREEN that adds only the safe-integer range check in `pilot_integrity.py`, followed by the same single-file test and independent review; T3 and Gate P2 remain blocked.

# 2026-08-14 — Phase 6B-T2R2 GREEN

- Accepted the bounded GREEN authorization under `planning-with-files` and `test-driven-development`; the existing 8 `DID NOT RAISE` cases are the required prior RED evidence.
- Root cause is isolated to `_validate_json_value()`: it currently returns immediately for every exact Python `int`, so recursive object/list validation never enforces the approved interoperable range.
- Minimal implementation plan: add a single safe-integer constant/range check before serialization, update the canonicalization version to describe the policy, and rely on existing hash/receipt call chains that already route through `canonical_json_bytes()`.
- No tests, contracts, docs, configs, data, provider/runner/candidate/pilot modules, or final-test artifacts will be modified or accessed.
- Modified only `src/mrta_rect_coverage/experiments/pilot_integrity.py` and the three planning files. Added `_JCS_SAFE_INTEGER_MAX`, split bool/int validation, rejected exact Python ints outside the approved interval, and updated the canonicalization version to `jcs-v1-safe-int-domain`.
- First authorized GREEN command `python -m pytest tests/test_pilot_scoped_hash_red.py -q` -> 118 passed, 1 existing warning, exit 0. All 8 prior RED failures turned green without changing tests.
- Authorized T1+T2 regression `python -m pytest tests/test_pilot_contract_schema_red.py tests/test_pilot_scoped_hash_red.py -q` -> 282 passed, 1 existing warning, exit 0. No full pytest was run.
- The implementation does not coerce unsupported ints to float and does not silently truncate; recursive dict/list values use the same gate, and all object/receipt hashes inherit it through `canonical_json_bytes()`.
- Post-GREEN boundary evidence: `pilot_integrity.py` SHA-256 is now `D09170932E3C46045F4AE212E4EFDB126B394DD1F43FAC70C5B1171969F8B95E`; `pilot_contracts.py` remains `2902BB3CB8F3D78B9A5A764708672D7E35C3C73133FFA1DD6902E90707D1C873`; the T2 test file remains the RED-stage hash `BDC3B66340125B22462985119BCEEA54873CFD2AF05478CA2D4E8545FAC54311`.
- Static capability search found only the module docstring's explicit denial of provider/candidate capability; no file/path/subprocess/network/runner/provider/candidate/pilot implementation was introduced.
- Phase 6B-T2R2 GREEN complete; recommend independent implementation review. T3 and Gate P2 remain blocked pending that review.

# 2026-08-14 — Phase 6B-T2R2 GREEN independent implementation review

- Started a read-only, tests-first review using `planning-with-files` and `code-review-and-quality`; only the two explicitly authorized pytest commands may run.
- Initial implementation review confirms the fix is a five-line recursive input-domain gate plus version change, with no new dependency or capability.
- Initial coverage audit found a discrepancy: scalar/nested canonicalization is tested, but the claimed explicit regression coverage for unsupported ints in object/receipt hash preimages and for algorithm/version interpretability is absent. Production call-chain inheritance appears correct by static tracing; final severity remains under review.
- Static metadata confirms `pilot_contracts.py` remains SHA-256 `2902BB3CB8F3D78B9A5A764708672D7E35C3C73133FFA1DD6902E90707D1C873` and the test file remains its RED-stage hash `BDC3B66340125B22462985119BCEEA54873CFD2AF05478CA2D4E8545FAC54311`; only `pilot_integrity.py` carries the GREEN hash.
- Fresh authorized T2 run: `python -m pytest tests/test_pilot_scoped_hash_red.py -q` -> 118 passed, 1 existing `pyreadline` warning, exit 0.
- Fresh authorized combined regression: `python -m pytest tests/test_pilot_contract_schema_red.py tests/test_pilot_scoped_hash_red.py -q` -> 282 passed, 1 existing warning, exit 0. No full pytest or other command was run.
- Review pass areas: recursive safe-int gate, no `2**68` decimal emission, Appendix B floats, pure in-memory boundary, formal-scope rejection, lowercase hash/ID checks, evidence in receipt hash, explicit-content-only behavior, and unchanged `pilot_contracts.py`.
- Review Required: add direct RED coverage for unsupported integers in object hash, validation/runner receipt IDs, and runner binding structured invalid result, plus algorithm/version assertions. The implementation currently behaves correctly by call-chain tracing, but the claimed test evidence is absent.
- Final verdict: Request changes (0 Critical, 1 Required). Phase 6B-T3 is not authorized; recommend a narrowly scoped T2R3 RED-only task. Gate P2 and all provider/pilot/formal/final-test restrictions remain active.

# 2026-08-14 — Phase 6B-T2R3 coverage-only tests

- Accepted the tests-only authorization under `planning-with-files` and `test-driven-development`; production code is locked read-only.
- Reviewed existing canonicalization and receipt test helpers. The new coverage can reuse `_pilot_manifest()`, `_validation_receipt()`, `_runner_receipt()`, `_assert_invalid()`, and direct in-memory mutations; no fixture or file access is needed.
- Planned cases cover three object-hash shapes, three validation receipt preimages, six runner receipt preimages, four structured runner-binding failures, pre-digest rejection, and exact algorithm/version assertions.
- Passing immediately is explicitly allowed as coverage-only closure; no production change will be made to manufacture RED.
- Added 19 direct cases to `tests/test_pilot_scoped_hash_red.py`: 3 object-hash shapes, pre-digest rejection, 3 validation-receipt preimages, 5 runner evidence preimages, 2 runner adjacent-field preimages, 4 structured binding failures, and exact algorithm/version assertions.
- New tests passed immediately; this closes the review gap as coverage-only evidence and requires no GREEN production modification.
- Authorized command `python -m pytest tests/test_pilot_scoped_hash_red.py -q`: **137 passed, 1 warning**, exit 0.
- Authorized combined regression `python -m pytest tests/test_pilot_contract_schema_red.py tests/test_pilot_scoped_hash_red.py -q`: **301 passed, 1 warning**, exit 0.
- The warning is the existing unrelated `pyreadline` deprecation warning. No full pytest, provider, candidate, pilot, benchmark, real LLM, or final-test command was run.
- Confirmed production modules remain unchanged by SHA-256: `pilot_integrity.py` = `D09170932E3C46045F4AE212E4EFDB126B394DD1F43FAC70C5B1171969F8B95E`; `pilot_contracts.py` = `2902BB3CB8F3D78B9A5A764708672D7E35C3C73133FFA1DD6902E90707D1C873`.
- T2R3 is ready for independent review. Phase 6B-T3 is not entered; Gate P2 and all real-provider/pilot/formal/large-scale/final-test prohibitions remain active.

# 2026-08-14 — Phase 6B-T3 pilot manifest validator integration RED-only

- T2R3 independent review approved entry into a single bounded T3 RED-only slice.
- Authorized write scope is one new integration test file plus `task_plan.md`, `findings.md`, and `progress.md`; all production modules and existing tests are locked.
- Planned contract: schema validation must precede and short-circuit scoped integrity checks; only schema+integrity success may produce an inert validation receipt; receipt/object bindings must be non-self-referential and fail closed; no path/file, runner, provider, candidate, pilot, benchmark, or final-test access is allowed.
- Gate P2 remains open. This phase cannot authorize scheduling or execution and requires separate T3 GREEN authorization after expected RED evidence.
- Stopped before creating tests as required by the attachment's conflict rule. Approved `docs/pilot_manifest_validator_spec.md` defines a raw-bytes/path/file-I/O validator, while the T3 request defines a pure-object/no-I/O API under the same validator identity.
- Also confirmed an exact enum conflict: approved `pilot_contracts.py` and `valid_manifest_validation_receipt.json` require `status=valid`; the T3 request requires `status=validation_valid`.
- The approved receipt's `manifest_hash` binds raw manifest bytes, which cannot be derived honestly from `manifest_obj` alone; only a canonical object hash is available without an additional raw-byte/hash input.
- No test file or fixture was created, no pytest command was run, and no production/docs/config/data/existing-test file was modified. Awaiting user clarification before T3 RED resumes.
- User confirmed the resolution: T3 is a subordinate pure-object pre-validator/core, uses `valid/rejected`, does not emit formal receipts, and leaves raw-byte/path/file-identity validation to a later I/O-authorized phase.
- Added `tests/test_pilot_manifest_prevalidator_core_red.py`; no fixture directory was needed. The file defines 29 collected cases across call order, schema short-circuit, integrity failures, happy path, canonical object/result binding, formal-receipt non-impersonation, explicit-content-only, and no-execution semantics.
- Authorized T3 command `python -m pytest tests/test_pilot_manifest_prevalidator_core_red.py -q`: **28 failed, 1 passed, 1 warning**, exit 1. The one baseline pass proves existing schema/integrity accept the in-memory fixture; all 28 failures are the expected absent-core message. No syntax, collection, or fixture errors occurred.
- Authorized T1+T2 regression `python -m pytest tests/test_pilot_contract_schema_red.py tests/test_pilot_scoped_hash_red.py -q`: **301 passed, 1 warning**, exit 0. The warning remains the existing unrelated `pyreadline` deprecation warning.
- A discovery `rg` command returned exit 1 solely because no existing pre-validator symbols matched; subsequent direct source reads established the contract and no retry/error affected test evidence.
- Production SHA-256 values remain unchanged and `src/mrta_rect_coverage/experiments/pilot_manifest_prevalidator.py` is absent. No production/docs/config/data/existing-test file was modified.
- T3 RED is complete and ready for a separately authorized GREEN. Gate P2 and all provider/pilot/formal/large-scale/final-test prohibitions remain active.

# 2026-08-14 — Phase 6B-T3 pure-object pre-validator/core GREEN

- Accepted the separately authorized GREEN scope under `planning-with-files` and `test-driven-development`; the prior 28 missing-module failures provide the required RED evidence.
- Added one production file only: `src/mrta_rect_coverage/experiments/pilot_manifest_prevalidator.py`. No existing production module, test, fixture, docs, config, or data file was modified.
- Implemented schema-first short-circuiting, scoped-integrity composition, structured schema/integrity failure layers, canonical object hashes, an inert non-self-referential prevalidation result ID, and deterministic post-build binding verification.
- Kept the approved semantics: result status is only `valid/rejected`; `preflight` output scope is `pure_object_prevalidation`; `execution_authorized=false`; `gate_p2_closed=false`; no formal validation receipt or raw manifest hash is emitted.
- Authorized T3 command `python -m pytest tests/test_pilot_manifest_prevalidator_core_red.py -q` -> **29 passed, 1 warning**, exit 0. All 28 prior RED failures turned green.
- Authorized T1+T2+T3 command `python -m pytest tests/test_pilot_contract_schema_red.py tests/test_pilot_scoped_hash_red.py tests/test_pilot_manifest_prevalidator_core_red.py -q` -> **330 passed, 1 warning**, exit 0. No full pytest was run.
- The warning is the existing unrelated `pyreadline` deprecation warning.
- New core SHA-256: `36C52D0C265DABEA0CF14CDCF8A208735FD34CCC8903C32CF408BAB365FD2FEF`. Existing `pilot_integrity.py` and `pilot_contracts.py` hashes remain unchanged.
- No raw-byte input, file/path access, path normalization, symlink/hardlink/inode/file identity, instance-file hash verification, runner, provider, candidate, pilot, benchmark, real LLM, or final-test operation was implemented or invoked.
- Phase 6B-T3 GREEN is ready for independent implementation review. It does not implement the full validator and does not close Gate P2; all execution and experiment prohibitions remain active.

# 2026-08-15 — Phase 6B-T3 independent implementation review

- Used `planning-with-files` to restore the current gate state and `code-review-and-quality` for tests-first, five-axis review. Production code and tests remained read-only.
- Reviewed `test_pilot_manifest_prevalidator_core_red.py`, `pilot_manifest_prevalidator.py`, and the schema/integrity dependency boundaries. Static capability search found no file/path/raw-bytes/runner/provider/candidate/pilot capability in the new core.
- Fresh authorized T3 command `python -m pytest tests/test_pilot_manifest_prevalidator_core_red.py -q` -> **29 passed, 1 warning**, exit 0.
- Fresh authorized combined command `python -m pytest tests/test_pilot_contract_schema_red.py tests/test_pilot_scoped_hash_red.py tests/test_pilot_manifest_prevalidator_core_red.py -q` -> **330 passed, 1 warning**, exit 0. No full pytest or unauthorized execution was run.
- Confirmed schema-first short-circuit, scoped-integrity-only-after-schema, `valid/rejected`, explicit `manifest_object_hash`, non-self-referential valid-result binding, no formal/runner receipt fields, and inert execution/Gate P2 flags.
- Found one Required: rejected results contain no input object hashes. Different invalid objects with the same rejection summary can therefore share a result ID and pass verification against each other; current tests cover mutation only from valid inputs.
- Recorded one Consider: repeated hashing of mutable inputs leaves a validation-to-result snapshot/TOCTOU risk and avoidable canonicalization overhead.
- Verdict: Request changes（0 Critical、1 Required）. Phase 6B-T4 is not authorized. Recommended next bounded task is T3R RED-only tests for rejected-input binding and single-snapshot consistency, followed by minimal GREEN and independent review.
- Gate P2 remains open. Real LLM/provider, pilot execution, formal experiment, large-scale experiment, and final-test remain prohibited.

# 2026-08-15 — Phase 6B-T3R rejected-input binding RED-only

- Read the attached RED-only contract under `planning-with-files` and `test-driven-development`; it matches the prior independent review finding and requires no protocol clarification.
- Modified only `tests/test_pilot_manifest_prevalidator_core_red.py` and the three planning files. Added no fixture and changed no production module.
- Added 17 cases covering schema-rejected manifest interchangeability/result IDs, integrity-rejected manifest/matrix/split interchangeability, canonical rejected input hashes, hash-field tamper binding, noncanonical binding-unavailable semantics, and two mid-build mutation stages.
- Ran only the authorized command `python -m pytest tests/test_pilot_manifest_prevalidator_core_red.py -q` -> **46 collected, 14 failed, 32 passed, 1 warning**, exit 1.
- All 14 failures are expected behavioral assertions: 6 rejected-input interchangeability/ID failures, 2 missing canonical rejected hash cases, 4 missing noncanonical binding-state/fail-closed cases, and 2 snapshot-consistency failures. There are no syntax, collection, fixture, or import errors.
- The three new rejected-result hash-field tamper cases pass under current code, serving as controls that existing result-ID verification rejects a changed field when the field is present.
- Ran the optional authorized combined command `python -m pytest tests/test_pilot_contract_schema_red.py tests/test_pilot_scoped_hash_red.py tests/test_pilot_manifest_prevalidator_core_red.py -q` -> **347 collected, 14 failed, 333 passed, 1 warning**, exit 1. Its 14 failures exactly match the T3R target set; no prior T1/T2/T3 test regressed.
- SHA-256 verification confirms all production modules are unchanged: prevalidator `36C52D0C265DABEA0CF14CDCF8A208735FD34CCC8903C32CF408BAB365FD2FEF`, contracts `2902BB3CB8F3D78B9A5A764708672D7E35C3C73133FFA1DD6902E90707D1C873`, integrity `D09170932E3C46045F4AE212E4EFDB126B394DD1F43FAC70C5B1171969F8B95E`. Updated test hash is `D5CBDC97391869EE5E7BF7DCD6BD183636297B78C50C357E9B942C56D6786DB2`.
- No production code, docs, configs, data, raw-byte/path/full-validator capability, runner, provider, candidate, pilot, benchmark, real LLM, or final-test artifact was modified, implemented, or invoked.
- T3R RED is complete. Recommend separately authorized minimal GREEN followed by independent review; T4 and Gate P2 remain blocked.

# 2026-08-15 — Phase 6B-T3R GREEN

- Accepted the bounded GREEN authorization under `planning-with-files` and `test-driven-development`; the prior 14 failures are the required observed RED evidence.
- Modified only `src/mrta_rect_coverage/experiments/pilot_manifest_prevalidator.py` plus planning records. Tests, `pilot_contracts.py`, `pilot_integrity.py`, docs, configs, and data remained unchanged.
- Added a private single-evaluation model that deep-copies all three inputs once, preserves schema→integrity order, detects mutation after each validator, and computes object hashes once from the entry snapshot.
- Extended pure-object results with `binding_available` and `binding_unavailable_reason`. Canonical valid/rejected results bind all three hashes and receive a non-self-referential result ID; noncanonical rejected results expose unavailable binding, null hashes, and no reusable result ID.
- Verification now validates binding state and all three object-hash formats, rejects unavailable bindings unconditionally, verifies the result ID when binding exists, then rebuilds the expected result from a fresh current-input snapshot to prevent replay.
- Authorized target command `python -m pytest tests/test_pilot_manifest_prevalidator_core_red.py -q` -> **46 passed, 1 warning**, exit 0. All 14 prior RED failures turned green.
- Authorized combined command `python -m pytest tests/test_pilot_contract_schema_red.py tests/test_pilot_scoped_hash_red.py tests/test_pilot_manifest_prevalidator_core_red.py -q` -> **347 passed, 1 warning**, exit 0. No full pytest was run.
- Static capability search found only the module docstring's denial wording; no open/pathlib/path/file-identity/raw-bytes/runner/provider/candidate/pilot implementation was added.
- SHA-256: prevalidator now `D353CB4EC89A7B2906CB8AA2EB57C5325E2336E1D56E2D5CC2521DF3FDA59371`; contracts remains `2902BB3CB8F3D78B9A5A764708672D7E35C3C73133FFA1DD6902E90707D1C873`; integrity remains `D09170932E3C46045F4AE212E4EFDB126B394DD1F43FAC70C5B1171969F8B95E`; T3 test remains `D5CBDC97391869EE5E7BF7DCD6BD183636297B78C50C357E9B942C56D6786DB2`.
- T3R GREEN is ready for independent implementation review. T4 is not entered; Gate P2 and all real-provider/pilot/formal/large-scale/final-test prohibitions remain active.

# 2026-08-15 — Phase 6B-T3R independent implementation review

- Used `planning-with-files` and `code-review-and-quality` for a read-only, tests-first review; production code and tests were not modified.
- Reviewed rejected schema/integrity binding, noncanonical binding-unavailable behavior, result-ID coverage, entry snapshot/mutation detection, verifier reconstruction, and module capability boundaries.
- Fresh authorized T3/T3R command `python -m pytest tests/test_pilot_manifest_prevalidator_core_red.py -q` -> **46 passed, 1 warning**, exit 0.
- Fresh authorized combined command `python -m pytest tests/test_pilot_contract_schema_red.py tests/test_pilot_scoped_hash_red.py tests/test_pilot_manifest_prevalidator_core_red.py -q` -> **347 passed, 1 warning**, exit 0. No full pytest was run.
- Static capability review found no file/path/raw-bytes/full-validator/runner/provider/candidate/pilot implementation. No provider, candidate, pilot, benchmark, real LLM, or final-test action was invoked.
- Hash evidence matches the GREEN record: prevalidator `D353CB4EC89A7B2906CB8AA2EB57C5325E2336E1D56E2D5CC2521DF3FDA59371`; contracts `2902BB3CB8F3D78B9A5A764708672D7E35C3C73133FFA1DD6902E90707D1C873`; integrity `D09170932E3C46045F4AE212E4EFDB126B394DD1F43FAC70C5B1171969F8B95E`; T3/T3R tests `D5CBDC97391869EE5E7BF7DCD6BD183636297B78C50C357E9B942C56D6786DB2`.
- Verdict: **Approve (0 Critical, 0 Required)**. Two non-blocking Consider items were recorded: structured handling/narrowing of pre-snapshot non-JSON objects, and explicit result-schema version evolution before persistence.
- Phase 6B-T4 can be separately authorized; recommended minimum is PIV-03 controlled path/duplicate-boundary RED-only tests. Gate P2 remains open, and real LLM/provider, pilot execution, formal experiment, large-scale experiment, and final-test remain prohibited.

# 2026-08-15 — Phase 6B-T4 PIV-03 RED-only start

- Accepted the separately authorized tests-only task under `planning-with-files` and `test-driven-development`.
- Read the complete attachment and approved PIV-03/validator specifications. No direct contract conflict was found, so RED work may proceed without editing docs.
- Write scope is locked to one new test file plus `task_plan.md`, `findings.md`, and `progress.md`; all production code, existing tests, configs, data, and docs remain locked.
- Temporary filesystem coverage will use pytest `tmp_path` only. No project data directory or real final-test manifest/file/hash/family/performance resource will be accessed.
- No provider, candidate, pilot, benchmark, real LLM, full validator, or runner operation is authorized. Gate P2 remains open; T4 GREEN requires separate authorization after observed RED evidence.
- Added `tests/test_pilot_path_duplicate_boundary_red.py` with 44 isolated tmp-path cases. No fixture directory was needed.
- Covered approved-root confinement, parent/drive syntax, symlink/dangling/directory aliases, hardlink identity, duplicate content/path/instance/family-split/generation identity, formal/final markers, explicit no-glob/no-discovery, and inert validator results.
- Added an explicit no-provider/no-candidate behavior case by replacing the existing provider factory, candidate-process executor, and evaluator invocation entry points with forbidden-call sentinels; no provider or candidate was invoked.
- Final authorized target command `python -m pytest tests/test_pilot_path_duplicate_boundary_red.py -q` -> **40 failed, 4 skipped, 1 warning**, exit 1. All 40 failures are the expected absent `pilot_path_validator` module; all four skips are explicit Windows symlink-capability skips.
- No syntax, collection, fixture parsing/setup, or unexpected behavioral error occurred. The warning is the existing unrelated `pyreadline` deprecation warning.
- Optional authorized T1+T2+T3 regression `python -m pytest tests/test_pilot_contract_schema_red.py tests/test_pilot_scoped_hash_red.py tests/test_pilot_manifest_prevalidator_core_red.py -q` -> **347 passed, 1 warning**, exit 0. No full pytest was run.
- Final SHA-256 audit: new T4 test `9FB0C9A802C9AA9F884071BCF407D2653D3025CE4F5146374FCFDAC8687CA3EE`; contracts `2902BB3CB8F3D78B9A5A764708672D7E35C3C73133FFA1DD6902E90707D1C873`; integrity `D09170932E3C46045F4AE212E4EFDB126B394DD1F43FAC70C5B1171969F8B95E`; prevalidator `D353CB4EC89A7B2906CB8AA2EB57C5325E2336E1D56E2D5CC2521DF3FDA59371`.
- Confirmed `src/mrta_rect_coverage/experiments/pilot_path_validator.py` is still absent. No production code, existing test, fixture directory, docs, configs, or data was modified.
- T4 RED-only is complete and ready for a separately authorized GREEN. No project `data/` or real final-test resource was scanned/accessed; no provider, candidate, pilot, benchmark, or real LLM was invoked; Gate P2 remains open.

# 2026-08-17 — Phase 6B-T4 GREEN start

- Accepted the separately authorized minimal GREEN under `planning-with-files` and `test-driven-development`; the prior 40 missing-module failures are the observed RED evidence.
- Read the complete authorization, T4 tests, package boundary, and current planning state. No contract conflict requires changing tests or docs.
- Write scope is locked to new `src/mrta_rect_coverage/experiments/pilot_path_validator.py` plus the three planning files. Existing production modules, tests, configs, data, and docs remain read-only.
- Planned implementation is an inert explicit-record validator using only standard-library path metadata and hashing. It will not enumerate directories or invoke glob/walk/provider/candidate/pilot/runner behavior.
- No project data or real final-test resource will be scanned or accessed. Gate P2 remains open throughout GREEN.

# 2026-08-17 — Phase 6B-T4 controlled path/duplicate validator GREEN

- Added `src/mrta_rect_coverage/experiments/pilot_path_validator.py`; no other production module, test, fixture, doc, config, or data file was changed.
- Implemented an inert explicit-record validator for approved-root confinement, parent/drive/glob syntax rejection, symlink/reparse rejection, explicit-file SHA-256 verification, and directory/missing-file rejection.
- Added one-pass duplicate checks for instance ID, declared content hash, canonical path, supported file identity/hardlink, family split, and generation identity. Unsupported file identity is structured and fail closed.
- Added pilot-only scope/path/lockbox checks. The implementation contains no directory discovery, glob, `os.walk`, runner, provider, candidate, or pilot invocation.
- Authorized T4 command `python -m pytest tests/test_pilot_path_duplicate_boundary_red.py -q` -> **40 passed, 4 skipped, 1 warning**, exit 0. All 40 prior missing-module RED failures turned green; four Windows symlink-capability skips remain expected.
- Authorized combined command `python -m pytest tests/test_pilot_contract_schema_red.py tests/test_pilot_scoped_hash_red.py tests/test_pilot_manifest_prevalidator_core_red.py tests/test_pilot_path_duplicate_boundary_red.py -q` -> **387 passed, 4 skipped, 1 warning**, exit 0. No full pytest was run.
- The warning is the existing unrelated `pyreadline` deprecation warning. No provider, candidate, pilot, benchmark, real LLM, project data scan, or final-test access occurred.
- Existing module SHA-256 values remain unchanged: contracts `2902BB3CB8F3D78B9A5A764708672D7E35C3C73133FFA1DD6902E90707D1C873`, integrity `D09170932E3C46045F4AE212E4EFDB126B394DD1F43FAC70C5B1171969F8B95E`, prevalidator `D353CB4EC89A7B2906CB8AA2EB57C5325E2336E1D56E2D5CC2521DF3FDA59371`. New path validator SHA-256 is `7F6607F6A110161F836ED7F772949A686B5615E884F03A4ADCE3B9759B58604D`.
- T4 GREEN is complete and ready for independent implementation review. It is not a full manifest validator, emits no formal or runner receipt, does not authorize execution, and does not close Gate P2.

# 2026-08-17 — Phase 6B-T4 independent implementation review

- Used `planning-with-files` to restore/update the gate record and `code-review-and-quality` for tests-first, five-axis review. Production code and tests remained read-only.
- Reviewed the full T4 test file, path validator, approved PIV-03 path/identity specification, dependency hashes, and static capability boundary.
- Fresh authorized T4 command `python -m pytest tests/test_pilot_path_duplicate_boundary_red.py -q` -> **40 passed, 4 skipped, 1 warning**, exit 0.
- Fresh authorized combined command `python -m pytest tests/test_pilot_contract_schema_red.py tests/test_pilot_scoped_hash_red.py tests/test_pilot_manifest_prevalidator_core_red.py tests/test_pilot_path_duplicate_boundary_red.py -q` -> **387 passed, 4 skipped, 1 warning**, exit 0. No full pytest was run.
- Confirmed the module does not scan project data, call glob/walk, access real final-test resources, issue receipts, or invoke runner/provider/candidate/pilot. The only filesystem reads were the test-authorized explicit `tmp_path` files.
- Found Required 1: separated link/resolve/type/stat/open operations leave a pathname-replacement TOCTOU and do not prove the exact validated file was read.
- Found Required 2: formal leakage checks omit record/header scope such as `split=formal_train/formal_dev/formal_final_test`; pilot promotion and URI-syntax fail-closed evidence is also absent.
- Recorded three non-blocking Consider items: file-identity status naming, explicit byte budgets, and stronger Windows reparse coverage.
- Dependency hashes remain unchanged from pre-T4 evidence. Verdict: **Request changes（0 Critical、2 Required）**. T5 is not authorized; recommend T4R RED-only tests followed by minimal GREEN and independent review.
- Gate P2 remains open. Real LLM/provider, pilot execution, formal experiment, large-scale experiment, and final-test remain prohibited.

# 2026-08-17 — Phase 6B-T4R RED-only start

- Accepted the tests-only authorization under `planning-with-files` and `test-driven-development`; production code is locked read-only.
- Read the complete attachment and restored the two review Required items. No contract conflict requires modifying docs or fixtures.
- Planned deterministic tmp-path cases for pre-read replacement, symlink swap, rename swap, post-read identity change, nested formal scope/header leakage, promotion, URI/UNC syntax, and non-path marker leakage.
- No provider, candidate, runner, pilot, benchmark, project-data scan, real LLM, or final-test access is authorized or planned. Gate P2 remains open and T5 remains blocked.

# 2026-08-17 — Phase 6B-T4R RED-only complete

- Modified only `tests/test_pilot_path_duplicate_boundary_red.py` and the three planning files. No fixture directory was needed and no production module was changed.
- Added deterministic tmp-path TOCTOU tests for in-place replacement, rename swap, symlink-to-outside swap, and post-read identity change. Mutation assertions prove the three executable races actually occurred before the validator incorrectly returned valid.
- Added direct and nested record/header tests for formal split/manifest scope, explicit promotion evidence, URI/UNC syntax, family/instance/hash markers, and nested scope/lockbox markers.
- Authorized command `python -m pytest tests/test_pilot_path_duplicate_boundary_red.py -q` -> **44 failed, 40 passed, 5 skipped, 1 warning**, exit 1. The suite collected 89 cases; all failures are expected behavioral RED and all skips are Windows symlink-capability skips.
- Authorized combined command `python -m pytest tests/test_pilot_contract_schema_red.py tests/test_pilot_scoped_hash_red.py tests/test_pilot_manifest_prevalidator_core_red.py tests/test_pilot_path_duplicate_boundary_red.py -q` -> **44 failed, 387 passed, 5 skipped, 1 warning**, exit 1. No full pytest was run.
- There were no syntax, collection, fixture setup, provider/candidate/pilot invocation, project-data scan, or real final-test errors. The warning is the existing unrelated `pyreadline` deprecation warning.
- SHA-256 verification confirms all four production modules are unchanged; updated test SHA-256 is `2B7FF019B0678979DE1FBD49A10B64498525C904ADCF625E38081C158D7801FC`.
- Phase 6B-T4R RED is complete. Recommend a separately authorized minimal GREEN followed by independent review; T5, Gate P2, real provider, pilot, formal/large-scale/final-test execution remain blocked.

# 2026-08-17 — Phase 6B-T4R TOCTOU/formal-leakage GREEN

- Continued from the observed **44 failed / 40 passed / 5 skipped** RED evidence under `planning-with-files` and `test-driven-development`; no test or protocol change was needed.
- Modified `src/mrta_rect_coverage/experiments/pilot_path_validator.py` only among production files. Preserved the existing private identity/hash seams used by the deterministic race tests.
- Implemented stable-handle hashing: capture a pre-open path snapshot, call the identity seam, open the explicit file, compare `fstat` identity/snapshot, hash bytes from that same handle, capture the handle's after-read snapshot, release it, then compare the post-read pathname/link/identity snapshot. All mismatches fail closed with structured TOCTOU reasons.
- Added recursive pilot-only inspection for manifest/header/record/nested metadata, covering formal train/dev/final-test values, lockbox/final-test markers, identity/hash marker leakage, and promotion evidence. Added early URI-scheme and UNC/network-path rejection without opening those inputs.
- First authorized T4/T4R rerun left one Windows-specific failure (`explicit_file_read_failed`) because an open handle prevented the test's post-read rename. Adjusted the stable-read helper to close only after hashing and capturing its handle snapshot, before the post-read pathname comparison; the same-handle read guarantee remains intact.
- Final authorized target command `python -m pytest tests/test_pilot_path_duplicate_boundary_red.py -q` -> **84 passed, 5 skipped, 1 warning**, exit 0.
- Authorized combined command `python -m pytest tests/test_pilot_contract_schema_red.py tests/test_pilot_scoped_hash_red.py tests/test_pilot_manifest_prevalidator_core_red.py tests/test_pilot_path_duplicate_boundary_red.py -q` -> **431 passed, 5 skipped, 1 warning**, exit 0. No full pytest was run.
- Skips remain platform-gated Windows symlink cases; warning remains the existing unrelated `pyreadline` deprecation warning.
- SHA-256: path validator `8516E309EC38010F062F022664B01088542330ED155EFECC2B13BA5D5ED92639`; contracts/integrity/prevalidator and the T4/T4R test retain their prior hashes.
- Did not modify tests, fixtures, docs, configs, data, `pilot_contracts.py`, `pilot_integrity.py`, or `pilot_manifest_prevalidator.py`. Did not scan real data, access final-test, run providers/candidates/pilot/benchmark, implement a full validator/receipt/runner, or close Gate P2.
- Phase 6B-T4R GREEN is ready for independent implementation review. T5 remains blocked pending that review; real LLM/provider, pilot execution, and formal/large-scale/final-test experiments remain prohibited.

# 2026-08-17 — Phase 6B-T5 RED-only stopped on protocol conflict

- Read the complete T5 attachment under `planning-with-files` and `test-driven-development`; write scope was tests/fixtures/planning only and all production code remained locked.
- Compared the proposed object-only builder contract with PIV-04, `pilot_manifest_validator_spec.md`, the strict validation-receipt schema/fixtures, and `pilot_integrity.py` receipt binding.
- Found a direct conflict before writing tests: approved PIV-04 requires raw-manifest-byte binding and valid receipts require `manifest_hash`, while T5 forbids raw bytes and forbids claiming raw-byte verification. The suggested API has no raw-byte input.
- Also recorded the existing semantic mismatch that `verify_manifest_receipt_binding()` treats `manifest_hash` as `compute_object_hash(manifest)`, although the approved docs call it the exact raw manifest hash.
- Followed the attachment's instruction to stop and report rather than change docs or invent a contradictory RED contract. No T5 test, fixture, or production module was created and no pytest command was run.
- Confirmed T5 module/test are absent. Production SHA-256 values remain: contracts `2902BB3CB8F3D78B9A5A764708672D7E35C3C73133FFA1DD6902E90707D1C873`; integrity `D09170932E3C46045F4AE212E4EFDB126B394DD1F43FAC70C5B1171969F8B95E`; prevalidator `D353CB4EC89A7B2906CB8AA2EB57C5325E2336E1D56E2D5CC2521DF3FDA59371`; path validator `8516E309EC38010F062F022664B01088542330ED155EFECC2B13BA5D5ED92639`.
- Gate P2 remains open. Real LLM/provider, candidate/pilot execution, formal/large-scale/final-test experiments, real data scans, and final-test access remain prohibited.

# 2026-08-17 — Phase 6B-T5C minimal contract reconciliation

- Adopted the approved option 2 in documentation only: future T5/PIV-04 receives explicit `raw_manifest_bytes`, `manifest_obj`, prevalidation result, path-validation result, and validator identity; it receives no manifest path and performs no filesystem acquisition.
- Updated `docs/pilot_infrastructure_task_breakdown.md`, `docs/pilot_manifest_validator_spec.md`, `docs/pilot_runner_receipt_spec.md`, `docs/manifest_spec.md`, and `docs/pilot_manifest_plan.md` to separate raw-byte, object, and artifact-header hash domains.
- Frozen receipt meanings: `manifest_hash=SHA-256(raw_manifest_bytes)`; optional `raw_manifest_bytes_hash==manifest_hash`; `manifest_object_hash` is the canonical parsed-object hash. Raw/object domains cannot substitute for each other.
- Required strict raw-byte JSON parsing and equality with `manifest_obj`; required binding to `prevalidation_result.manifest_object_hash` and any supplied path-result object evidence; invalid JSON, non-canonicalizable input, or any mismatch rejects.
- Kept receipt status to `valid` / `rejected` and explicitly inert: execution and Gate P2 flags remain false, with no runner/schedule/provider/candidate/pilot/final-test readiness semantics.
- Recorded the existing `pilot_integrity.py` `manifest_hash` object-domain naming ambiguity as future separately authorized TDD migration work. No production or test file was changed in T5C.
- Used only read/search/edit consistency checks. No pytest, provider, candidate, pilot, benchmark, project-data scan, or final-test access was performed.
- Read-only contract audit passed 11/11 targeted checks. Existing production hashes remain unchanged: contracts `2902BB3CB8F3D78B9A5A764708672D7E35C3C73133FFA1DD6902E90707D1C873`, integrity `D09170932E3C46045F4AE212E4EFDB126B394DD1F43FAC70C5B1171969F8B95E`, prevalidator `D353CB4EC89A7B2906CB8AA2EB57C5325E2336E1D56E2D5CC2521DF3FDA59371`, and path validator `8516E309EC38010F062F022664B01088542330ED155EFECC2B13BA5D5ED92639`.
- T5C is complete at the contract level. The next step, if separately authorized, is Phase 6B-T5 RED-only raw-manifest-bytes validation-receipt tests; it is not GREEN, a full validator, a runner, or execution authorization.
- Gate P2 remains open. Real LLM/provider, pilot execution, formal experiment, large-scale experiment, and final-test remain prohibited.

# 2026-08-18 — Phase 6B-T5 raw-manifest-bytes validation receipt RED-only start

- Accepted the tests-only authorization under `planning-with-files` and `test-driven-development`; production code, existing tests, docs, configs, and data are locked read-only.
- Restored the T5C contract and read the complete RED attachment. The three hash domains remain fixed: receipt raw-byte `manifest_hash`, optional equal `raw_manifest_bytes_hash`, and canonical-object `manifest_object_hash`.
- The only planned implementation artifact is `tests/test_pilot_validation_receipt_red.py` plus planning records. No receipt builder/verifier, full validator, runner, provider, candidate, pilot, path acquisition, or Gate P2 capability will be implemented.
- The authorized execution boundary is the single new test file. No full suite, provider, pilot, benchmark, project-data scan, or final-test access is permitted.
- Added `tests/test_pilot_validation_receipt_red.py`; no fixture directory was needed. The file collects **120** contract cases spanning all eleven requested behavior groups.
- Authorized target command `python -m pytest tests/test_pilot_validation_receipt_red.py -q` -> **120 failed, 1 warning**, exit 1. Every failure reaches the explicit missing `mrta_rect_coverage.experiments.pilot_validation_receipt` RED message; there are no syntax, collection, fixture-setup, or unrelated behavioral errors.
- The warning is the existing unrelated `pyreadline` deprecation warning. Production remains unchanged and the target builder/verifier module remains absent.
- Authorized optional regression `python -m pytest tests/test_pilot_contract_schema_red.py tests/test_pilot_scoped_hash_red.py tests/test_pilot_manifest_prevalidator_core_red.py tests/test_pilot_path_duplicate_boundary_red.py -q` -> **431 passed, 5 skipped, 1 warning**, exit 0. No full suite was run.
- Final SHA-256 audit confirms all four existing production modules retain their pre-T5 values. New test hash is `6BDBFD7136403E8762C0B81AC8A8909FDDEBCB268FE2D3737746EFEBCDB7C21E`; `pilot_validation_receipt.py` and the optional fixture directory remain absent.
- Modified only `tests/test_pilot_validation_receipt_red.py`, `task_plan.md`, `findings.md`, and `progress.md`. No production, existing test, fixture, docs, configs, or data file was changed.
- No provider, candidate, pilot, benchmark, real LLM, project-data scan, or real final-test access occurred. No validation receipt/full validator/runner/provider/candidate/pilot capability was implemented, and Gate P2 remains open.
- Phase 6B-T5 raw-manifest-bytes validation receipt RED-only is complete. Recommend a separately authorized minimal T5 GREEN next; all execution and experiment prohibitions remain active.
- Final completion audit re-read the plan and caught two stale historical gate lines; they were reconciled to show that T5C removed the protocol pause and T5 RED-only is now complete. No test or production artifact changed during that documentation-only correction.

# 2026-08-18 — Phase 6B-T5 GREEN start

- Accepted the separately authorized minimal GREEN after the observed 120/120 missing-module RED.
- Write scope is locked to new `src/mrta_rect_coverage/experiments/pilot_validation_receipt.py` plus the three planning files. Tests, existing production modules, docs, configs, and data remain read-only.
- The implementation will be a pure in-memory receipt builder/verifier over explicit bytes and mappings. It will not accept/read a path, enumerate directories, invoke providers/candidates/pilot, emit runner/formal receipts, or close Gate P2.
- First authorized T5 run reached **119 passed / 1 failed**. The sole failure was semantic ordering: an old-ID `receipt_version` tamper was reported as `invalid_receipt_version` before receipt-ID mismatch. Reordered verification to establish receipt integrity first, while coherently rehashed invalid versions still reach the version gate; tests were not changed.
- Final authorized T5 target command `python -m pytest tests/test_pilot_validation_receipt_red.py -q` -> **120 passed, 1 warning**, exit 0.
- Authorized T1–T5 combined command -> **551 passed, 5 skipped, 1 warning**, exit 0. No full pytest was run; skips are existing platform-gated link cases and the warning is the existing unrelated `pyreadline` deprecation warning.
- Static source audit confirms the new module contains no path/file reads, directory discovery, glob/walk, provider, runner, candidate, or pilot execution imports/calls. It emits only an inert receipt/result.
- SHA-256: new receipt module `8457CA3A3916F3076008D7D2049C3E7E8477227FD4B209D68D604B5D9835EFB5`; unchanged contracts `2902BB3CB8F3D78B9A5A764708672D7E35C3C73133FFA1DD6902E90707D1C873`; unchanged integrity `D09170932E3C46045F4AE212E4EFDB126B394DD1F43FAC70C5B1171969F8B95E`; unchanged prevalidator `D353CB4EC89A7B2906CB8AA2EB57C5325E2336E1D56E2D5CC2521DF3FDA59371`; unchanged path validator `8516E309EC38010F062F022664B01088542330ED155EFECC2B13BA5D5ED92639`; unchanged T5 test `6BDBFD7136403E8762C0B81AC8A8909FDDEBCB268FE2D3737746EFEBCDB7C21E`.
- Modified only the new receipt production module and the three planning files. Did not modify tests, existing production modules, docs, configs, or data.
- Did not run provider/candidate/pilot/benchmark, scan project data, access real final-test, implement a full/formal validator or runner receipt, or close Gate P2.
- Phase 6B-T5 GREEN is complete and awaits independent implementation review.
- Completion audit reconciled the stale RED-stage “next GREEN authorization” checkbox with the now-completed separately authorized GREEN. This planning-only correction did not change code or test evidence.

# 2026-08-18 — Phase 6B-T5 independent implementation review start

- Began a read-only tests-first review under the authorized command boundary; production and tests remain unchanged.
- Confirmed the test suite explicitly covers hash-domain separation, strict bytes/JSON parsing, receipt identity, evidence copying/binding, inert semantics, and no file/path/provider/runner execution.
- Began line-by-line source review. Preliminary focus is whether all copied upstream evidence is also semantically fail-closed, and whether content-addressed identity is described without implying trusted authentication.
- Gate P2 remains open; no provider, candidate, pilot, benchmark, data scan, or final-test access has occurred.
- Contract cross-check confirms PIV-04 requires complete prevalidation/path evidence binding and fail-closed unknown/missing/wrong-type handling. The current review found copied evidence fields whose semantics/types are not yet enforced by T5.
- Cross-module inspection also confirms that T4 does not yet emit T5's full evidence envelope; this will require an explicit later integration task and cannot be treated as existing full-validator capability.
- Fresh authorized target run: `python -m pytest tests/test_pilot_validation_receipt_red.py -q` -> **120 passed, 1 existing warning**.
- Fresh authorized T1–T5 regression: **551 passed, 5 platform skips, 1 existing warning**. No full suite, provider, candidate, pilot, benchmark, data scan, or final-test command was run.
- SHA-256 audit reproduces the reported T5 module/test hashes and the four unchanged upstream production hashes exactly. The package directory is not a Git worktree, so verification used direct SHA-256 rather than Git diff provenance.
- Static capability search found no prohibited I/O/execution call in `pilot_validation_receipt.py`; the only provider/candidate wording is the boundary docstring.

# 2026-08-18 — Phase 6B-T5 independent implementation review result

- Verdict: **Request changes — 0 Critical, 1 Required**.
- Required finding: T5 binds upstream result IDs but does not fully validate all copied prevalidation/path evidence fields or valid-branch invariants. A malformed self-hashed evidence mapping can remain semantically invalid while being accepted into a `valid` receipt.
- Fresh evidence remains T5 **120 passed, 1 warning** and T1–T5 **551 passed, 5 skips, 1 warning**; these tests do not directly cover the identified malformed-evidence cases.
- Hashes match the reported GREEN artifacts exactly; no reviewed production or test file was modified during review. Only planning records were updated.
- T6 is not authorized. Recommended next step is T5R RED-only evidence-schema/branch tests, then narrow GREEN and another independent review.
- Gate P2 remains open. Real LLM/provider, candidate/pilot execution, benchmarks, formal/large-scale experiments, and final-test remain prohibited.

# 2026-08-18 — Phase 6B-T5R RED-only start

- Accepted tests-only authorization and read the complete attachment. Production, docs, configs, data, providers, runner, candidate, pilot, benchmark, and final-test remain out of scope.
- Planned RED cases will construct malformed prevalidation/path mappings, recompute their own result IDs, and require both receipt construction and verification to fail closed.
- The only code-under-test edit target is `tests/test_pilot_validation_receipt_red.py`; production code remains locked read-only and T6/Gate P2 remain unavailable.
- Added 100 pure in-memory T5R cases to the existing T5 test file. No fixture or production edit was needed.
- Authorized T5 command -> **220 collected, 97 failed, 123 passed, 1 existing warning**. All 97 failures are the intended malformed/self-hashed evidence bypass; there are no syntax, collection, or fixture errors.
- Authorized T1–T5 combined command -> **97 failed, 554 passed, 5 platform skips, 1 existing warning**. The same 97 T5R cases fail; existing T1–T4 coverage remains green.

# 2026-08-18 — Phase 6B-T5R RED-only complete

- Direct SHA-256 audit confirms all five production modules retain their prior hashes. Only `tests/test_pilot_validation_receipt_red.py` and the three planning files changed.
- New test file SHA-256: `E419D5211293DDC2F4D796052F1C9A51473FE8A236CDF2ECED7457841CD1583B`.
- No production, fixture, docs, configs, or data file was modified. No full suite, provider, candidate, pilot, benchmark, data scan, or final-test access occurred.
- RED is complete and ready for a separately authorized T5R GREEN. T6 and Gate P2 remain unavailable; all real-provider and experiment prohibitions remain active.

# 2026-08-20 — Phase 6B-T5R GREEN start

- Accepted the separately authorized GREEN after the observed 97 malformed/self-hashed evidence failures.
- Production write scope is limited to `src/mrta_rect_coverage/experiments/pilot_validation_receipt.py`; tests and all other production/docs/config/data files remain read-only.
- Planned change is pure in-memory schema/type/hash/enum/branch validation shared by builder and verifier. No file/path acquisition, full validator, runner, provider, candidate, pilot, benchmark, final-test, or Gate P2 capability will be added.
## Phase 6B-T5R GREEN implementation start

- Confirmed the RED failures are concentrated in malformed/self-hashed prevalidation and path evidence that the current verifier accepts after receipt-ID recomputation.
- Frozen the minimal GREEN approach: strict per-branch evidence predicates shared by build and verify, with verifier failure after receipt-ID verification when upstream evidence is malformed.
- Authorized production scope remains limited to `src/mrta_rect_coverage/experiments/pilot_validation_receipt.py`; no tests, fixtures, docs, provider, runner, candidate, pilot, configs, or data changes are authorized.

## Phase 6B-T5R GREEN verification

- Implemented strict prevalidation/path evidence schemas and branch invariants in `pilot_validation_receipt.py` only.
- `python -m pytest tests/test_pilot_validation_receipt_red.py -q`: **220 passed, 1 warning**.
- Authorized T1–T5 regression: **651 passed, 5 skipped, 1 warning**.
- The skips are the existing platform-dependent link-capability cases; the warning is the existing `pyreadline` deprecation warning.
- No full test suite, provider, candidate, pilot, benchmark, real LLM, real data scan, or final-test access was run.
- The workspace directory is not a Git repository, so final scope verification uses direct source inspection and file hashes rather than `git diff`.
- Final `pilot_validation_receipt.py` SHA-256: `549F8AF9C416C27FE77881BC1C62BA5CB6D1D921215FC9949AA91A6336508EA1`.
- Direct source scan found no `open(`, `pathlib`, `Path.*`, or `os.walk` capability; matches for provider/candidate/glob terms were documentation or inert evidence-field names only.

## Phase 6B-T5R duplicate authorization reconciliation

- Read the newly attached GREEN authorization in full; it is substantively identical to the already implemented Phase 6B-T5R contract and adds no new production, test, or execution requirement.
- No additional implementation change is required. The authorized T5 and T1–T5 commands will be rerun to provide fresh evidence for the current disk state.
- Fresh rerun: `python -m pytest tests/test_pilot_validation_receipt_red.py -q` → **220 passed, 1 warning**.
- Fresh rerun: authorized T1–T5 combined command → **651 passed, 5 skipped, 1 warning**.
- No full suite, provider, candidate, pilot, benchmark, data scan, or final-test access occurred during this reconciliation.

## 2026-09-28 - Phase 6B-T5R2 RED-only complete

- Accepted the tests/planning-only authorization. Production modules, docs, configs, data, provider/candidate/pilot/benchmark/final-test, and T6 remained out of scope.
- Read T3/T4/T5 production and tests before editing. The real T3 output is the exact 18-field `pilot-prevalidation-core-v1` envelope; current T4 output remains a six-field dataclass rather than T5's expanded path evidence mapping.
- Modified only `tests/test_pilot_validation_receipt_red.py` and the three planning records.
- Added one real T3-builder positive control plus 25 fail-closed cases for schema-version presence/type/value, the stale helper version, aliases/near-miss keys, and unknown fields in prevalidation/path evidence.
- Every malformed mapping is self-hashed after mutation. The receipt is built with the malformed input, and both builder and verifier paths are evaluated so stale upstream or receipt IDs cannot explain RED.
- Authorized target command `C:\Anaconda\Scripts\pytest.exe tests/test_pilot_validation_receipt_red.py -q` -> **25 failed, 221 passed**, exit 1. The 25 failures are all `exact upstream envelope/version validation is missing`; there are no syntax, collection, import, fixture, or positive-control failures.
- No T1-T5 regression or full suite was run because this turn authorized only the T5 target and did not separately authorize the optional regression.
- Production SHA-256 values are unchanged: receipt `549F8AF9C416C27FE77881BC1C62BA5CB6D1D921215FC9949AA91A6336508EA1`; prevalidator `D353CB4EC89A7B2906CB8AA2EB57C5325E2336E1D56E2D5CC2521DF3FDA59371`; path validator `8516E309EC38010F062F022664B01088542330ED155EFECC2B13BA5D5ED92639`.
- Gate P2 remains open; T6 remains unauthorized. The next permitted action is a separately authorized T5R2 GREEN. Stop after RED.

## 2026-09-28 - Phase 6B-T5R2 GREEN attempt stopped on frozen-helper conflict

- Applied only the authorized production change in `pilot_validation_receipt.py`: exact approved prevalidation/path key sets, exact schema-version fields and values, exact string type checks, and unknown-key rejection. No tests, upstream modules, docs, configs, or data were changed.
- Re-read current production contracts: T3 is the 18-field `pilot-prevalidation-core-v1` mapping; T4 remains the six-field dataclass; T5 path receipt remains the expanded mapping contract.
- Target command: `C:\Anaconda\Scripts\pytest.exe tests/test_pilot_validation_receipt_red.py -q --tb=no`.
- Result: **237 passed, 9 failed**. All 25 T5R2 cases pass, including the real T3 positive control. The 9 failures are pre-existing valid-receipt tests whose frozen helper still supplies forbidden `pilot-prevalidation-v1`.
- No T1-T5 regression was run because target GREEN was not achieved. No provider, candidate, pilot, benchmark, formal, large-scale, or final-test path was accessed.
- Hashes: receipt module `DC7C77094F2A5F42F4C3DFB55D4D9D37084CB6CFCFE1F6A93C7CB1475010D36D`; unchanged prevalidator `D353CB4EC89A7B2906CB8AA2EB57C5325E2336E1D56E2D5CC2521DF3FDA59371`; unchanged path validator `8516E309EC38010F062F022664B01088542330ED155EFECC2B13BA5D5ED92639`; unchanged test file `866BCA726D1ECB09BD7DE917975DA8E655EDC073F97225799B9CA87405F609C0`.
- Static audit found no file I/O, directory discovery, provider, candidate, runner, pilot, or benchmark capability added to the receipt module.
- Gate P2 remains open; T6 remains unauthorized. Independent review is not yet appropriate because the authorized target is not green. The blocking decision is whether to separately authorize correction of the frozen helper/tests or revise the exact-version contract.

## 2026-09-28 - Phase 6B-T5R2C complete

- Read the full reconciliation authorization before editing. Production exact-envelope/version behavior remained locked and strict.
- Read-only traceback confirmation established one root cause for all 9 historical failures: canonical synthetic prevalidation helpers still emitted `pilot-prevalidation-v1`, while current T3 production requires `pilot-prevalidation-core-v1`.
- Modified only `tests/test_pilot_validation_receipt_red.py`: the two canonical helper defaults now use `pilot-prevalidation-core-v1`. Explicit legacy-version, alias, near-miss, wrong-type, and unknown-field negative cases remain present.
- T5 target: `C:\Anaconda\Scripts\pytest.exe tests/test_pilot_validation_receipt_red.py -q --tb=no` -> **246 passed**.
- Authorized combined regression: `C:\Anaconda\Scripts\pytest.exe tests/test_pilot_validation_receipt_red.py tests/test_pilot_contract_schema_red.py tests/test_pilot_scoped_hash_red.py tests/test_pilot_manifest_prevalidator_core_red.py tests/test_pilot_path_duplicate_boundary_red.py -q` -> **677 passed, 5 skipped**.
- Production hashes: receipt `DC7C77094F2A5F42F4C3DFB55D4D9D37084CB6CFCFE1F6A93C7CB1475010D36D`; unchanged prevalidator `D353CB4EC89A7B2906CB8AA2EB57C5325E2336E1D56E2D5CC2521DF3FDA59371`; unchanged path validator `8516E309EC38010F062F022664B01088542330ED155EFECC2B13BA5D5ED92639`; test file `7DA735194DD64B4B55678BE4939090FC860B5AB8DC16577990F40AD505A66B87`.
- Static audit found no new file I/O, directory discovery, provider, candidate, runner, pilot, benchmark, or final-test capability in the receipt module. T4-to-T5 path-envelope integration remains explicitly incomplete.
- Gate P2 remains OPEN; T6, real provider/candidate/pilot/benchmark/formal/final-test remain unauthorized. Next permitted action: Phase 6B-T5R2 independent implementation review.

## 2026-09-28 - Phase 6B-T5R3 RED contract recovery stopped on CONTRACT GAP

- Read the full T5R3 authorization and re-read `pilot_path_validator.py`, `pilot_validation_receipt.py`, `pilot_integrity.py`, `pilot_manifest_prevalidator.py`, and the relevant T4/T5 tests.
- Confirmed current T4 output remains a six-field `PilotPathValidationResult`; T5 consumes a 13-field expanded path evidence mapping.
- Contract table shows direct/derived coverage for status, scope, file identity, rejection reasons, inert flags, manifest hash context, schema version, and result ID, but no real production provenance for `approved_root_fingerprint`, exact duplicate counters, `no_glob_confirmed`, or `no_directory_discovery_confirmed`.
- The existing expanded path mapping is only a synthetic T5 helper. No production adapter or composer was created, and no test was added because the prompt requires stopping rather than inventing evidence when the source contract is incomplete.
- No pytest, provider, candidate, pilot, benchmark, formal, large-scale, or final-test command was run in this contract-recovery stop.
- Gate P2 remains OPEN; T6 remains NOT AUTHORIZED. Next permitted action is a separately authorized minimal source-contract task defining the missing provenance fields and derivation rules, followed by a new T5R3 RED/GREEN cycle.

## 2026-09-28 - Phase 6B-T4E stopped on CONTRACT AMBIGUITY

- Read the full T4E authorization and performed the required read-only contract recovery.
- Confirmed T4 real output and duplicate reason categories, T5 exact expanded path envelope shape, and the approved path schema version.
- Found unresolved semantics, not merely missing implementation: duplicate-summary counters have no defined unit; approved-root fingerprint has no defined preimage/algorithm; no-glob and no-directory fields have unresolved input-vs-capability/invariant meanings.
- Per authorization, no RED tests, production changes, adapter, composer, or synthetic provenance values were added. No pytest or execution command was run.
- Production and test artifacts remain unchanged from T5R2C. Gate P2 remains OPEN, T6 remains NOT AUTHORIZED, and all provider/candidate/pilot/benchmark/formal/final-test restrictions remain active.
- Next action requires explicit contract clarification, then a fresh T4E RED cycle.

## 2026-09-28 - Phase 6B-T4E-R1 complete

- Completed PRE-RED coherence A-E with PASS and added `tests/test_pilot_path_evidence_red.py`.
- Clean RED: `C:\Anaconda\Scripts\pytest.exe tests/test_pilot_path_evidence_red.py -q --tb=no` -> **11 failed**. Every failure was the explicit missing-producer guard; there were no collection, import, fixture, syntax, or positive-control failures.
- Implemented `build_pilot_path_validation_evidence()` and internal single-pass provenance collection in `pilot_path_validator.py`; the existing public `PilotPathValidationResult` shape remains unchanged.
- Corrected Windows stable snapshot selection to prefer `st_birthtime_ns` when available and retain `st_ctime_ns` as the fallback. This was required for deterministic real file-identity/hardlink provenance; no T5 behavior changed.
- GREEN T4E target -> **11 passed**.
- Existing T4 target -> **84 passed, 5 skipped**.
- T5 receipt target -> **246 passed**.
- Authorized T1-T5 plus T4E regression -> **688 passed, 5 skipped, 0 warnings**.
- Final SHA-256: `pilot_path_validator.py` `E4885CD5D0FD7582A2F116C7E78754DE43775BD4A4605D8B551F447A122A055C`; T4E test `33BBE1E23600CA07C0C569B08404181CF306E74D180E2BAB2E90F0FFDF062574`.
- Unchanged upstream/T5 production hashes: receipt `DC7C77094F2A5F42F4C3DFB55D4D9D37084CB6CFCFE1F6A93C7CB1475010D36D`; prevalidator `D353CB4EC89A7B2906CB8AA2EB57C5325E2336E1D56E2D5CC2521DF3FDA59371`; integrity `D09170932E3C46045F4AE212E4EFDB126B394DD1F43FAC70C5B1171969F8B95E`; contracts `2902BB3CB8F3D78B9A5A764708672D7E35C3C73133FFA1DD6902E90707D1C873`.
- Static audit found no directory discovery, glob expansion, network, provider, candidate, runner, pilot execution, benchmark, or final-test capability added.
- No full suite or prohibited execution was run. Gate P2 remains OPEN; T6 remains NOT AUTHORIZED.
- Next permitted action: Phase 6B-T4E-R1 independent implementation review. After that review, recommended project direction is to pause pilot-infrastructure expansion and move to separately authorized R0 Core Runtime Bring-Up.

## 2026-09-28 - Phase 6B-T4E-R1R bounded repair complete

- Read the full bounded-repair authorization and review finding. No provider, candidate, pilot, benchmark, formal, large-scale, final-test, R0, or T6 action was taken.
- Added `tests/test_pilot_path_snapshot_timestamp_red.py` with synthetic stat cases. RED target: **2 expected failures, 2 controls passed**; failures were exactly non-Windows birthtime selection and ctime-only mutation detection.
- Implemented `_select_snapshot_change_timestamp()` in `pilot_path_validator.py`.
- Platform matrix: Windows prefers `st_birthtime_ns` and falls back to `st_ctime_ns`; Linux/macOS/BSD/other non-Windows uses `st_ctime_ns` even when birthtime exists.
- Hardlink identity remains `(st_dev, st_ino)`.
- Fresh verification: timestamp target **4 passed**; T4E **11 passed**; T4 **84 passed, 5 skipped**; T5 **246 passed**; authorized combined regression **692 passed, 5 skipped, 0 failed**.
- Hashes: `pilot_path_validator.py` `7AED6E24F1A58314F63F5FCBEE8A537111A75DE77CC46DA2CD689458A244912E`; timestamp test `FA6FF8297AA9C3C4AFE4E2DB401949DBF0FED247ABCD79E16BF838F67CE09DB4`; T4E test `33BBE1E23600CA07C0C569B08404181CF306E74D180E2BAB2E90F0FFDF062574`; unchanged T5 receipt `DC7C77094F2A5F42F4C3DFB55D4D9D37084CB6CFCFE1F6A93C7CB1475010D36D`; prevalidator `D353CB4EC89A7B2906CB8AA2EB57C5325E2336E1D56E2D5CC2521DF3FDA59371`; integrity `D09170932E3C46045F4AE212E4EFDB126B394DD1F43FAC70C5B1171969F8B95E`; contracts `2902BB3CB8F3D78B9A5A764708672D7E35C3C73133FFA1DD6902E90707D1C873`.
- Static audit: no directory discovery, glob expansion, network, provider, candidate, runner, pilot, benchmark, or final-test capability added. `execution_authorized=False`; `gate_p2_closed=False`.
- Next permitted action: Phase 6B-T4E-R1R independent implementation review. Stop before R0; Gate P2 remains OPEN and T6 remains NOT AUTHORIZED.

## 2026-09-28 - Phase R0 Core Runtime Bring-Up complete

- Confirmed the actual project root, package layout, CLI, data, configs, and core solver call chain.
- Added four minimal smoke configs: T6 baseline/ALNS and T10 baseline/ALNS. They use built-in operators, `advisor_mode: none`, no frozen/generated operators, and 20 ALNS iterations.
- Fresh CLI verification: all four commands exited 0 and produced solution/convergence/operator outputs under `outputs/r0_smoke/`.
- Fresh structured validity audit passed for all four runs: route count, exact task universe, no duplicates, no invalid IDs, finite Route-DP costs, finite makespan, and makespan/max-route-cost equality.
- Fresh same-seed reproducibility passed for T6 baseline and T6 ALNS.
- Authorized core tests passed: `C:\Anaconda\Scripts\pytest.exe tests/test_instance_loader.py tests/test_baseline_solver.py tests/test_dp_evaluator.py tests/test_alns_solver.py -q` -> `10 passed in 0.12s`.
- Added `docs/RUNBOOK.md` with reproducible commands, input metadata, output path, known warning, `speed=1` limitation, and Gate P2/T6 boundaries.
- Existing Matplotlib warning remains at `plot_solution.py:118`; no warning-related code change was authorized or needed.
- No provider, candidate, pilot, benchmark, formal, large-scale, final-test, or T6 execution occurred. Gate P2 remains OPEN.

R0 status: `CORE_RUNTIME_READY = TRUE`. Stop here. The next permitted action is separately authorized `R1 - Scientific Correctness`; do not enter R1 automatically.

## 2026-09-28 - Phase R1 Scientific Correctness implementation

- Recovered the approved independent-speed model from production, tests, README, AGENTS, and modeling decisions before editing.
- P0-A RED: `tests/test_scientific_correctness.py` -> 8 failed. P0-A GREEN -> 8 passed; related core regression -> 21 passed.
- P0-B RED after P0-A: 8 failed, 8 passed. P0-B GREEN -> 16 passed; solution/baseline/ALNS/local-search regression -> 8 passed.
- P0-C RED after P0-A/B: 5 failed, 17 passed. P0-C GREEN -> 22 passed; ALNS/benchmark/advisor core tests -> 7 passed.
- Added a characterization control proving greedy candidate insertion calls Route DP; scientific-correctness target is now 23 passed.
- Authorized core regression before final documentation: 53 passed.
- Four smoke CLI runs exited 0 and retained routes/costs/makespans: T6 baseline 228, T6 ALNS 206, T10 baseline 1061, T10 ALNS 904.
- Updated the instance schema/data, core time model, complete/partial evaluation boundary, compatibility alias handling, core tests, shipped configs, and R1 documentation.
- No provider, generated candidate, pilot, batch benchmark, formal/large-scale experiment, final-test, or T6 path was run. Pilot/gate modules were not modified and Gate P2 remains OPEN.

Final `SCIENTIFIC_CORE_READY` status will be set only after the fresh final core/smoke/hash/capability verification below. R2 remains unauthorized.

## 2026-09-28 - Phase R1 final verification

- Fresh authorized core target: **54 passed in 0.27s**.
- Fresh CLI objective audit: T6 baseline 228, T6 ALNS 206, T10 baseline 1061, T10 ALNS 904; all commands exited 0.
- Fresh API validity audit passed for all four results: exact robot/task contract, no duplicates/invalid IDs, finite route costs and makespan, and makespan/max-route-cost equality.
- Fresh same-seed T6 baseline/ALNS reproducibility passed for routes, per-route costs, and makespan.
- Five pilot/gate production hashes exactly match their pre-R1 values.
- Static R1 core capability scan found no provider, candidate-execution, pilot, subprocess, network, or final-test capability.
- The workspace has incomplete `.git` metadata only, so no branch merge/PR operation or Git diff provenance is available; scope evidence uses direct file inspection and SHA-256.
- No full suite or prohibited execution was run. The existing Matplotlib annotation-legend warning remains non-blocking.

R1 result: `P0-A CLOSED`, `P0-B CLOSED`, `P0-C CLOSED`, and `SCIENTIFIC_CORE_READY = TRUE`. Stop here. The next recommendation is separately authorized `R2 - Paper-Grade Instance/Data Protocol`; do not execute it automatically. Gate P2 remains OPEN and T6 remains NOT AUTHORIZED.

## 2026-09-29 - Phase R2 Paper-Grade Instance/Data Protocol

- Read the authoritative R2 prompt and current repository state. Confirmed the existing loader contract, two smoke-only root files, no existing generator/features/manifest loader, and broad glob leakage risk in operator-evolution code.
- Added focused `tests/test_dataset_protocol.py` first. Initial RED was a single collection failure because `dataset_protocol.py` did not exist; no fixture, syntax, or import-path failure occurred.
- Implemented `src/mrta_rect_coverage/experiments/dataset_protocol.py` with versioned schema constants, six-family sanity matrix, deterministic explicit seeds, non-overlapping rectangle generation, loader round-trip, intrinsic feature extraction without solver calls, exact manifest validation, hash verification, split confinement, and no-glob manifest access.
- Target protocol tests now pass: **6 passed**. A temporary full-family generation probe initially found that the 40-task clustered domain was too small; the generator was corrected by scaling high-task coordinate domains and widening deterministic cluster placement. A second probe passed all splits.
- Generated the checked-in sanity set: **6 instances total**, two per split, under `data/r2_sanity/`; manifests are `manifests/r2-sanity-v1_{development,held-out,final}.json`. Each manifest loader round-trips and verifies all listed file hashes.
- Added `docs/dataset_protocol.md`, `docs/instance_families.md`, and `docs/final_test_protocol.md`; updated README and RUNBOOK with manifest-only access and no-formal-experiment boundaries.
- No provider, candidate, operator-evolution, pilot, benchmark, formal, final-test, or T6 execution occurred. Gate P2 remains OPEN and T6 remains NOT AUTHORIZED. Verification and final `PAPER_DATA_PROTOCOL_READY` report are pending.

## 2026-09-29 - Phase R2 final verification

- R2 target: `C:\Anaconda\Scripts\pytest.exe tests/test_dataset_protocol.py -q --tb=no` -> **7 passed**, 0 failed, no warnings.
- Authorized restricted core regression (dataset protocol plus R1 core/model/cache targets) -> **57 passed**, 0 failed, no warnings. Full suite was not run.
- Sanity provenance audit: development, held-out, and final manifests each contain 2 entries; all 6 files round-trip through `load_instance`, remain within the manifest root, and match recorded SHA-256 bytes. Manifest entries contain no solver result, performance, ranking, or LLM fields.
- Static protocol capability audit found no provider/network/subprocess/candidate/pilot/benchmark/solver execution or glob/discovery capability. The generator performs only explicit artifact writes and manifest-listed reads.
- Unchanged pilot/gate production hashes: `pilot_validation_receipt.py` `DC7C77094F2A5F42F4C3DFB55D4D9D37084CB6CFCFE1F6A93C7CB1475010D36D`; `pilot_manifest_prevalidator.py` `D353CB4EC89A7B2906CB8AA2EB57C5325E2336E1D56E2D5CC2521DF3FDA59371`; `pilot_path_validator.py` `7AED6E24F1A58314F63F5FCBEE8A537111A75DE77CC46DA2CD689458A244912E`; `pilot_integrity.py` `D09170932E3C46045F4AE212E4EFDB126B394DD1F43FAC70C5B1171969F8B95E`; `pilot_contracts.py` `2902BB3CB8F3D78B9A5A764708672D7E35C3C73133FFA1DD6902E90707D1C873`.
- `PAPER_DATA_PROTOCOL_READY = TRUE`. Gate P2 remains OPEN; T6, provider/candidate/pilot/benchmark/formal/final-test remain unauthorized. The next permitted action is separately authorized R3 Optimization Diagnostics, not automatic execution.

## 2026-09-29 - Phase R3 Optimization Diagnostics inventory

- Read the final R3 prompt and restored the R0-R2 state. R3 authorizes only manual built-in baseline/ALNS diagnostics; real provider, generated/frozen operators, pilot, formal benchmark, final-test, and T6 remain prohibited.
- Production parser/loader inventory found **61 Track A root-level non-final instances**: `R2_T6=1`, `R2_T10=10`, `R2_T20=10`, `R4_T40=10`, `R4_T60=10`, `R8_T80=10`, `R8_T100=10`.
- Explicitly loaded the R2 final manifest and excluded its two paths. No final instance was loaded. Track A provenance has no family labels and will remain unlabeled beyond intrinsic features.
- Read the current ALNS, baseline, Route DP, solution evaluation, local search, neighborhood, dataset protocol, benchmark runner, and related tests. Recorded the intrinsic-feature and instrumentation gaps that must be closed before runs can support R3 Q1-Q9.

## 2026-09-29 - Phase R3 Optimization Diagnostics complete

- Extended solver-free intrinsic features and Route-DP statistics; added built-in-only R3 instrumentation, tests, and raw-run driver.
- Scale sanity and 50/100/200 probes froze a 100-iteration budget with destroy fraction 0.25, simulated annealing, one stronger-local-search step, exact 3x3 built-in operator pools, seeds 0-4 for T<=40, and seeds 0-2 for T>=60/held-out.
- Completed 29 Track A runs and 10 controlled development runs. Froze H1-H3 in `docs/r3_heldout_hypotheses.md` and `outputs/r3_diagnostics/predeclared_hypotheses.json` before running 6 held-out diagnostics.
- Added offline `scripts/analyze_r3_diagnostics.py`. TDD RED was the missing module; a subsequent focused RED exposed the controlled run/manifest ID mismatch and was fixed by joining controlled evidence on source/family provenance.
- Consolidation normalizes old IDs in memory and yields 45 unique runs, 65 inventory rows, 11 behavioral instances, 270 per-run operator rows, and 2,032 accepted-move DP rows. Raw JSON inputs remain unchanged.
- Generated `metadata.json`, 7 diagnostic/analysis CSV tables, `analysis_summary.json`, 45 convergence CSVs, and 8 publication-style plots in both PDF and PNG.
- Wrote `docs/r3_diagnostics_report.md` with Q1-Q9, held-out confirmation, C1-C3 decisions, and the bounded R4 design recommendation.
- Fresh R3 focused verification: **12 passed in 0.13s**, 0 failed, 0 warnings.
- Fresh restricted core/R2 regression: **55 passed in 0.28s**, 0 failed, 0 warnings. Full suite was not run.
- Static audit: no provider/network/subprocess imports in the R3 implementation/analysis files; all 45 consolidated runs have `provider_used=False`, `generated_operator_used=False`, unique IDs, and no final path.
- R3 SHA-256: dataset protocol `0037A30B77997ED4031A9715AFCA7BBF5ACAC987AAFFB81591C8CBCF69B4683C`; DP evaluator `38832DA77524C00C4FBCD649D8001DCDD89F3B841A723507FF556709C47DBE4A`; diagnostic module `B8DB1071B905BCA95F7E98DB7D5A2A3FE016A0BE6E345B826F8369318625F4A0`; run script `8340DCEE912F192B1D6F297CB55C5E5A5FDB46A3212901929B45B7C075D9AF2D`; analysis script `EDC9BDC8AE120A3333A6382B4A0B029C8B588222634C09A5FE22C0AE7F5CDE00`; R3 diagnostic test `476FD1660CC0B1F4D95DA22F9D0B869EC6D5528994CFFED3DEB59D392744008D`; analysis test `1A4C2E7B74C0659FC424EB26B3A155A3FA795A34FCF3ADD96D1095201CB3D8FC`.
- Pilot/gate hashes remain unchanged: receipt `DC7C77094F2A5F42F4C3DFB55D4D9D37084CB6CFCFE1F6A93C7CB1475010D36D`; prevalidator `D353CB4EC89A7B2906CB8AA2EB57C5325E2336E1D56E2D5CC2521DF3FDA59371`; path validator `7AED6E24F1A58314F63F5FCBEE8A537111A75DE77CC46DA2CD689458A244912E`; integrity `D09170932E3C46045F4AE212E4EFDB126B394DD1F43FAC70C5B1171969F8B95E`; contracts `2902BB3CB8F3D78B9A5A764708672D7E35C3C73133FFA1DD6902E90707D1C873`.
- `OPTIMIZATION_DIAGNOSTICS_READY = TRUE`. Gate P2 remains OPEN. Real LLM/provider, generated/frozen operators, candidate execution, pilot/formal benchmark, final-test, ML predictor training, T6, and automatic R4 execution remain prohibited.

Stop after R3. The next recommendation is separately authorized `R4 - LLM Research Method Design`; do not execute it automatically.

### Phase R6 Pre-Real-Provider Experimental Readiness Review (authorized read-only)

- [x] Read R4 frozen method, threat matrix, comparison protocol, R5 mapping/docs/source/tests/outputs and relevant R3 metric definitions.
- [x] Run authorized fresh scoped verification only: R5 target 17 passed; R2/R3 focused regression 19 passed; combined scoped target 36 passed.
- [x] Complete static no-provider/no-untrusted-execution/no-final-test reachability scan for the R5 path.
- [x] Record independent findings and classify historical RED tests separately from current green regression.
- [ ] Repair six Required R6 findings under separate authorization.

Status: R6 complete as a read-only review with `Request changes` (0 Critical, 6 Required, 3 Consider). `REAL_PROVIDER_GENERATION_READY = FALSE`; `UNTRUSTED_EXECUTION_READY = FALSE`; Gate P2 remains OPEN; T6 and R6A remain unauthorized.
# 2026-09-30 - Phase R4 real-time literature verification and method freeze

- Adopted real-time verification as the default threat-matrix standard.
- Verified required anchors against formal publication metadata/pages, arXiv full text and official repositories where available. Added QUBE, Behaviour Space Analysis, ReVEL and RouteRepair as high-relevance threats.
- Unknown or inaccessible fields remain `UNKNOWN` or `NOT VERIFIED`; no novelty inference was added.
- Froze C1 exact-DP-grounded behavioral operator evolution as primary, C2 exact-DP-response complementary operator set as secondary, and C3 structured counterexample-guided revision as optional secondary ablation. All novelty remains `NOVELTY_UNVERIFIED`.
- Froze Option A lexicographic constrained selection: eligibility, quality floor, quality anchor, structural-regime coverage, exact-DP behavioral tie-break, fixed small set size. Reliability is a hard gate; no arbitrary weighted sum.
- Added ReVEL-like, EoH-S-like and RouteRepair-like threat comparisons and B0/L0/L1/L2/L3 main chain.
- Marked six R3 diagnostic held-out runs `diagnostic-heldout-consumed`; new selection-validation and confirmatory-heldout splits are required. Final-test remains locked.
- Wrote `docs/literature_gap_matrix.md`, `docs/research_method_vNext.md` and `docs/r4_experiment_comparison_protocol.md`. R4 status: `LLM_RESEARCH_METHOD_READY = TRUE`.
- Documentation-only freeze. Gate P2 remains OPEN; T6, real provider/candidate/pilot/benchmark/formal/final-test execution remain unauthorized. Next permitted action is separately authorized R5 mock/file research pipeline implementation.

## 2026-09-30 - Phase R5 mock/file research pipeline authorized

- R5 is explicitly authorized within the frozen R4 scope. Gate P2 remains OPEN; R6, T6, real provider, untrusted candidate execution, pilot, formal benchmark and final-test remain prohibited.
- Contract recovery found the legacy candidate path can load/execute Python source. R5 will therefore use a new trusted-fixture-only module and will not invoke the legacy source execution path.
- Added `docs/r5_contract_to_code_mapping.md`; implementation begins with tests-first RED coverage.
- Added `tests/test_r5_mock_pipeline.py` and ran the R5 target. Clean RED: collection stopped only because `r5_mock_pipeline` does not yet exist; no fixture, syntax or unrelated import failure occurred.
- Implemented the isolated `r5_mock_pipeline.py`, package exports, trusted fixture/mock/file providers, versioned profiles/feedback/archive, lineage/elite retention, lexicographic selection, P0-P2 deployment, C3 payloads, split guards, hierarchy/budget/yield artifacts and output writer.
- Fresh R5 target verification: `tests/test_r5_mock_pipeline.py` -> **17 passed**.
- Focused regression: non-RED operator-evolution tests plus dataset/R3 focused tests -> **28 passed**. No full suite was run.
- Fresh end-to-end mock verification: Scenarios A-D all `True`; 10 archive records, 10 hierarchy evaluation addresses, equal budgets, 12 output audit files under `outputs/r5_mock_pipeline/`.
- Static capability audit: R5 module has no dynamic import, `exec`, subprocess, network, candidate-loader/proxy or final-test capability. Output contract records `real_provider_used=false`, `untrusted_candidate_executed=false`, `pilot_executed=false`, `formal_experiment_executed=false`, `final_test_accessed=false`, `gate_p2=OPEN`, `t6_authorized=false`.
- R5 status: `MOCK_RESEARCH_PIPELINE_READY = TRUE`. Stop before R6; wait for separate authorization.

## Phase R5R Research Pipeline Provenance & Trust Repair

- [x] R5R-A RED -> GREEN: canonical R3 DP metric binding and intrinsic-only regime derivation.
- [x] R5R-B RED -> GREEN: parent ID/source-hash lineage, verified elite reuse, deterministic/persisted evaluation hierarchy.
- [x] R5R-C RED -> GREEN: trusted fixture registry, allowlist, SHA-256 and root confinement with dry-run-only reading.
- [x] Reconstruct archive, lineage, elite events, trial evaluations, aggregates and selection trace from fresh disk artifacts.
- [x] Run scoped verification: 26 R5/R5R, 19 R2/R3 focused and 32 core non-provider tests passed; compileall passed.
- [x] Confirm no real provider, untrusted execution, pilot, formal experiment, final-test or T6 path was used.

Status: `R5_REPAIR_READY_FOR_REVIEW = TRUE`. Stop before R6 re-review; `REAL_PROVIDER_GENERATION_READY` remains unmodified, Gate P2 OPEN, T6 NOT AUTHORIZED.
