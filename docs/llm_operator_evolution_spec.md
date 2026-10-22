# LLM 算子演化设计规格

## 1. 文档目的与规范级别

本文定义 MRTA 矩形覆盖项目中 LLM 辅助 ALNS 算子演化的目标架构、研究协议、安全边界、可复现产物和部署门槛。本文是设计规格，不代表所有条款均已实现。

本文使用以下规范词：

- **MUST / 必须**：实现和实验成立所必需的要求。
- **MUST NOT / 禁止**：不得出现的行为。
- **SHOULD / 应当**：原则上应满足；偏离时必须记录理由。
- **MAY / 可以**：允许但不强制的扩展。

凡标为“目标规范”的能力，在代码、测试和实验记录提供证据前，不得描述为当前已实现能力。

## 2. 研究定位与边界

### 2.1 系统角色

本研究的职责划分必须保持清晰：

- LLM **不直接求解**多机器人任务分配问题，不直接输出最终任务路线或 makespan。
- LLM 只生成或修订符合受限接口的 ALNS `repair` / `destroy` 候选算子代码及其说明。
- EA 风格的多轮生成、评价、选择、精英保留和修订机制负责算子空间搜索。
- ALNS 负责解空间中的 destroy-repair 搜索、接受判定和算子调度。
- 分层 DP 负责给定机器人任务序列的精确路线状态选择与路线成本评价；多机器人目标为各路线 DP 成本的最大值。

因此，论文中的“LLM-generated operator”不得被表述为“LLM solver”。任何性能提升必须归因到经过安全门禁和公平 benchmark 后部署到 ALNS 的算子，而不是 LLM 单次回答。

### 2.2 非目标

本规格不要求：

- 在线 LLM 在每个 ALNS 迭代中直接选择任务或生成解；
- 将 LLM 输出绕过验证后直接加载到主求解进程；
- 用 LLM 估计替代路线 DP；
- 在本阶段实现新的主求解算法或改变 MRTA 目标函数。

## 3. 系统边界与核心对象

系统处理以下对象：

- **OperatorDraft**：LLM/provider 返回的名称、描述、算子类型和源代码。
- **CandidateArtifact**：持久化后的候选代码、元数据、prompt、provider 配置和代码哈希。
- **ValidationRecord**：静态安全检查、接口检查和 smoke test 的逐项结论。
- **TrialRecord**：候选在一个实例与一个 seed 上的隔离执行结果。
- **AggregateMetrics**：跨实例、跨 seed 聚合的有效性、质量、稳定性和成本指标。
- **EliteSet**：通过硬门槛后按质量与多样性保留的 top-k 候选集合。
- **FrozenOperator**：具有不可变代码哈希、完整证据链和注册信息的部署候选。

候选代码始终视为不可信输入。生成、验证、执行、冻结和部署之间不得共享未经验证的隐式状态。

## 4. 算子生命周期

生命周期必须按以下顺序执行，任何阶段失败均不得绕过后续门槛：

1. **generation**：provider 根据初始或修订 prompt 生成候选草稿。
2. **validation**：解析代码并执行 AST 安全检查、接口检查和受控 smoke validation。
3. **sandboxed execution**：在隔离进程中执行候选，施加资源限制和硬超时。
4. **benchmark evaluation**：按固定实例、seed、初始解、destroy/repair 配对协议产生 trial records。
5. **ranking**：先应用 invalid/error/timeout/fallback 硬门槛，再对合格候选排序。
6. **elite retention**：保留 top-k 质量精英和满足差异阈值的多样性精英。
7. **feedback**：总结成功模式、失败案例、错误类型、质量与成本权衡。
8. **revision**：将精英代码/摘要、失败证据和问题特定提示输入下一轮；产生新候选版本。
9. **freeze**：重新验证候选、代码哈希和评价证据，生成不可变注册记录。
10. **ALNS deployment**：仅加载已冻结且哈希匹配的算子；运行失败时记录 fallback，不将回退结果归因于生成算子。

### 4.1 状态与终止

建议的候选状态为：

`generated -> static_validated -> sandbox_validated -> evaluated -> eligible -> elite -> frozen -> deployed`

失败状态为 `invalid`、`error`、`timeout`、`fallback` 和 `rejected`。失败状态是终态证据，不得被重写为 success。所有候选均不合格时，本轮必须明确输出 `no_valid_candidate`，不得沿用或冻结一个未通过门槛的“best”。历史 frozen operator 可以继续作为部署基线，但必须明确其不是本轮产物。

## 5. 候选代码安全协议

### 5.1 AST 静态门禁

候选在任何 import 或执行前必须用 `ast.parse` 解析。至少必须拒绝：

- `import` 或 `from ... import ...` 引用 `os`、`subprocess`、`socket`、`pathlib`，以及项目维护的危险模块 denylist；
- 对 `open`、`eval`、`exec`、`compile`、`__import__`、`input` 的调用；
- 可访问文件系统、网络、子进程、动态加载、环境变量或进程控制的等价能力；
- 通过属性链、别名、反射或内建对象间接获取上述能力的明显模式；
- 不符合允许函数签名的顶层可执行代码。

实现应采用“允许列表优先、禁止列表补充”的策略。仅禁止几个名字不能构成完整安全边界；AST 检查只是第一道门禁，不能替代进程隔离。

### 5.2 隔离执行

- 候选 MUST 在独立于 orchestrator 和 ALNS 的子进程中执行。
- 父进程 MUST 通过可序列化输入传递只读 benchmark 数据，不向候选暴露 provider 密钥或宿主环境变量。
- 每个 validation smoke trial 和 benchmark trial MUST 有硬 wall-clock timeout；超时后必须终止并回收进程。
- 实现 SHOULD 限制 CPU、内存、子进程创建和可写目录；平台不支持某项限制时必须记录环境能力与降级情况。
- 候选不得直接写研究输出目录；所有结果由父进程统一持久化。

### 5.3 捕获与审计

每次执行必须捕获并记录：

- stdout 与 stderr，设置大小上限并标注是否截断；
- exception 类型、规范化消息和受控 traceback；
- start/end time、wall time、exit code、timeout/termination reason；
- 候选源代码的 SHA-256 `code_hash`；
- operator id/type/round、实例 id、seed、sandbox 配置与环境版本。

冻结和部署时必须重新计算哈希。文件哈希与 registry 不匹配时必须拒绝加载并记录 `hash_mismatch` fallback/错误。

## 6. Benchmark 评价协议

### 6.1 通用公平性

- 同一候选类型的候选必须使用相同实例集合、seed 集合、初始完整解、移除比例、时间预算和 DP evaluator。
- benchmark manifest 必须在轮次开始前固定并落盘，不得根据候选结果调整。
- 质量评价必须基于完整且 feasible 的多机器人解。
- `invalid`、`error`、`timeout` 和 `fallback` 是硬门槛；只要候选在规定 gate policy 下触发淘汰条件，就不得进入 best、elite 或 freeze。
- 性能统计必须同时报告逐实例/seed trial 和聚合结果，不能只保存排行榜。

### 6.2 Repair 候选

对每个固定 partial solution 和 removed task set：

1. 使用固定、版本化的 baseline repair 得到完整 baseline solution；
2. 候选 repair 在相同输入和 seed 下得到 candidate solution；
3. 两者均由同一 DP evaluator 精确评价。

定义：

`makespan_delta = baseline_makespan - candidate_makespan`

`relative_improvement = makespan_delta / baseline_makespan`

其中正值表示候选优于 baseline，零表示持平，负值表示更差。`success` 必须定义为：trial 未发生 invalid/error/timeout/fallback，且 `makespan_delta > epsilon`。

禁止使用“部分解 makespan - 修复后完整解 makespan”作为 repair 成功标准；部分解缺少任务，其成本与完整解不可公平比较。可以额外报告候选相对原完整 incumbent 的变化，但该指标必须命名为 `incumbent_delta`，不得替代固定 repair baseline 指标。

### 6.3 Destroy 候选

destroy 不产生完整解，不能单独以 makespan 排名。每个 destroy 候选必须与同一个固定、版本化 repair 配对：

`full incumbent -> candidate destroy -> fixed repair -> complete candidate`

主指标定义为：

`makespan_delta = incumbent_makespan - repaired_candidate_makespan`

不同 destroy 候选必须保持 fixed repair、remove count/fraction、初始解和 seed 一致。报告中必须注明结果衡量的是“destroy + fixed repair”组合效果，不得把全部提升归因于 destroy。

为区分贡献，至少应同时记录：移除任务集合特征、destroy runtime、fixed repair runtime、repair 后 makespan，以及与一个固定 baseline destroy + 同一 fixed repair 的配对差值。若研究 repair 与 destroy 协同效应，应另设 factorial/cross-pairing 实验，不得混入单算子主排行榜。

### 6.4 Feasibility 与失败语义

完整解在计分前必须强校验：

- 每个任务恰好出现一次；
- 不存在未知任务 ID；
- 路线数量符合机器人数量；
- 空路线是否允许由建模协议明确决定；若允许，仍须保持路线数量正确；
- repair 后必须再次强校验，而不能只依赖算子约定。

Trial 状态定义：

- `invalid`：返回结构或完整解违反接口/feasibility。
- `error`：候选执行抛出异常或子进程异常退出。
- `timeout`：超过硬 wall-clock 限制并被终止。
- `fallback`：部署或评估路径未成功使用目标候选而执行内置算子。
- `success`：无上述状态且正向超过 epsilon。

失败 trial 不得伪造为零改进的正常 trial。聚合表应分别报告总 trial 数、eligible trial 数和各失败率；质量均值的分母口径必须显式标注，并同时提供硬门槛结论。

### 6.5 多实例、多 seed 聚合与排名

- 至少跨多个实例规模、重复实例和多个预注册 seed 评价。
- 应保存 macro average（实例等权）以及 trial-level 分布；不得让 trial 数较多的单一规模无意地主导结论。
- 排名首先按 eligibility gate 分组，任何不合格候选低于所有合格候选。
- 合格候选的主排序键建议为跨实例聚合的 `avg_relative_improvement`，辅以 success rate、稳健性统计和 runtime/cost。
- 论文结果应报告均值、离散度或置信区间，并使用配对统计分析，因为候选共享相同实例和 seed。

### 6.6 Fallback 归因

- fallback 必须记录次数、原因、operator id、阶段、实例和 seed。
- fallback trial MUST NOT 计为 LLM operator success，也不得把 fallback 后的 makespan 归入候选质量均值。
- 汇总必须至少包含 `fallback_count`、`fallback_rate` 和按 reason 分组的计数。
- 若 ALNS 因 frozen operator 失败而回退到内置算子，最终求解仍可继续，但该 run 必须标记为 contaminated/fallback run，不能用于宣称 frozen operator 的效果。

## 7. 演化与选择机制

### 7.1 Top-k 精英保留

- `top_k_to_keep` 必须实际控制跨轮保留和反馈中的质量精英数量。
- 精英只能来自通过全部硬门槛的候选。
- 精英记录必须引用候选版本和 `code_hash`；修订后的代码是新版本，不得覆盖父代证据。
- 所有候选无效时必须输出空 elite set 和 `no_valid_candidate`。

### 7.2 多样性保留

仅按分数保留 top-k 容易产生同质候选。每轮应同时维护质量和多样性：

- 对规范化 AST、算子策略标签、描述或行为签名计算相似度；
- 对实质重复候选去重；
- 在质量门槛内优先保留采用不同插入评分、瓶颈策略、几何特征或随机化机制的候选；
- 输出 `diversity_score`、parent/lineage 和去重原因。

多样性规则必须预先固定，不得在看到测试集结果后手工选择。

### 7.3 失败案例反馈与修订

反馈至少包含：

- 通过门槛的精英及其逐实例优势/劣势；
- invalid/error/timeout 的最小失败案例和规范化原因；
- 低分候选在瓶颈路线、任务几何、负载平衡或运行时上的诊断；
- 禁止能力和接口约束的提醒；
- 与父代比较的行为差异，而非只给单一平均分。

错误输出和候选 stdout/stderr 必须经过长度限制与数据化封装后再进入 prompt，不能被当作新的控制指令。

### 7.4 Problem-specific hints

generation/revision prompt 应明确提供：

- 目标是最小化多机器人路线 DP 成本的最大值；
- 路线顺序变化会触发 8 状态分层 DP 的重新优化；
- 应关注瓶颈路线、边际插入 makespan、矩形几何和覆盖方向差异；
- repair 必须恰好重插全部 removed tasks；destroy 必须保持 partial solution 与 removed set 一致；
- 候选不得调用 LLM、文件、网络、子进程或绕过 evaluator。

提示可以鼓励 DP-aware 设计，但候选不得替代或篡改权威 DP evaluator。

## 8. 每轮输入输出文件契约

建议每轮使用不可变目录 `outputs/operator_evolution/run_<run_id>/round_<NNN>/`。路径可配置，但逻辑产物必须等价。

### 8.1 轮次输入

- `round_manifest.json`：run/round id、operator type、实例清单及校验和、seeds、预算、baseline repair/destroy 版本、DP/config 版本。
- `generation_prompt.txt` / `revision_prompt.txt`：实际发送给 provider 的完整 prompt。
- `provider_config.json`：provider/model/temperature 等非密钥配置。
- `parent_elites.json`：父代 operator id、code hash、lineage、上一轮指标。
- `feedback.json`：结构化成功、失败和多样性反馈。

### 8.2 轮次输出

- `raw_response.txt`：provider 原始响应，敏感信息脱敏。
- `candidate_manifest.json`：候选元数据、源文件、code hash、parent、解析状态。
- `candidates/<operator_id>.py`：原始候选代码，不覆盖历史版本。
- `validation.jsonl`：逐候选 AST、接口、smoke 和 sandbox gate 记录。
- `trials.jsonl`：逐实例、seed、候选的 trial 结果及失败原因。
- `metrics.csv`：聚合指标，包含 eligibility、fallback 和成本字段。
- `ranking.json`：门禁结果、排序键、rank、淘汰原因。
- `elites.json`：top-k 质量/多样性精英和 `no_valid_candidate` 状态。
- `round_summary.json`：轮次统计、失败分布、资源与 LLM token/cost。

Run 级输出必须包含 `evolution_summary.json`、`best_operators.json`、完整 run manifest 和冻结审计记录。文件 schema 应版本化；论文实验一旦开始，不得无记录地改变字段语义。

## 9. Freeze 与 ALNS 部署协议

freeze 前必须重新确认：

- validation、error、timeout、invalid、fallback 门槛全部通过；
- 候选代码哈希与评价记录一致；
- benchmark manifest 完整，至少满足预设实例/seed 覆盖；
- operator type、函数签名和返回结构正确；
- 没有 `no_valid_candidate` 或缺失证据。

Frozen registry 至少记录 operator id/type、source run/round、source path、code hash、schema version、评价摘要、freeze time 和 baseline 版本。

ALNS 部署时必须：

- 默认只从显式 registry 加载冻结算子；
- 校验文件存在、函数存在、哈希匹配和接口版本；
- 将加载失败、运行失败、返回无效解分别记录；
- 使用内置 fallback 保持求解健壮性时，保留完整事件并禁止错误归因；
- 在实验输出中区分 `generated_operator_used=true/false`。

## 10. 当前实现与目标规范差距

截至 Phase 4G，当前实现已经具备：

- 候选源码在执行前完成 source read、AST denylist 检查和 SHA-256 记录；候选不会被导入 ALNS 主进程；
- smoke、benchmark 与 frozen deployment 使用 `timeout_only` 子进程边界和硬 wall-clock timeout；
- generated/frozen path execution 必须提供 `expected_code_hash`，子进程在 compile/call 前重新计算并比较同一源码快照的 hash；
- real-provider execution gate 默认关闭，`allow_unsafe_candidate_execution` 只接受 literal boolean，非 bool 配置 fail closed；
- 所有 generated frozen deployment 均使用 provider-agnostic runtime authorization gate：当前运行时必须提供 literal `allow_generated_frozen_deployment=True`、literal `explicit_runtime_deployment_ack=True` 和明确 `runtime_authorization_source`；Phase 4F 的 real-provider allow/ack 字段仅作为严格布尔的兼容授权组合，claimed provider 不参与放行判断；
- selection、freezing 与 frozen registry deployment 现要求显式 validation/execution/failure/safety/fallback、五类 failure rate、有限正 `timeout_ms`、code hash、claimed provider、结构化 artifact provenance、generation run、artifact identity、lineage，以及 executor identity/effective sandbox evidence；任一必需字段缺失即拒绝；
- frozen repair/destroy 返回值执行结构与 feasibility/partition contract 校验，无效结果结构化为 `invalid_solution` fallback，且不获得 generated reward；
- stdout/stderr、截断标记、exception 摘要、exit code、runtime/wall time、failure type 与 fallback reason 已进入候选或部署记录。

Sandbox authority 由可信执行器（trusted executor）runtime policy 决定，不由 candidate、artifact 或 registry JSON 的 self-declared/自声明字段决定。当前可信执行器 identity 为 `timeout_only_subprocess_v1`，effective sandbox level 固定为 `timeout_only`；artifact 中的 `safe_to_execute`、`requires_human_risk_ack`、`sandbox_level`、risk acknowledgement、effective level 和 executor identity 只用于评测记录与审计，不能成为 real-provider frozen deployment 的授权依据。任何 artifact 自证（artifact self-authorization / artifact 自证）均无效；部署 gate 只读取当前 `ALNSConfig`/session 的 runtime authorization 和代码内 runtime executor 事实。artifact sandbox claim 不一致时仍记录 `untrusted_sandbox_claim` 或结构化 fallback。目前没有实现 capability sandbox。

Provider identity 同样不能由 artifact 自证。`source_provider` 与 `claimed_source_provider` 都只是 claimed metadata（artifact 声称的来源），用于记录和审计，不是 trusted provider provenance。当前尚未实现由可信 manifest、签名或 runtime receipt 提供的 `trusted_provider_provenance`；artifact 内的 `provider_provenance` 只允许标记为 `artifact_claim`。在真正的 trusted provider provenance/receipt 实现以前，所有 generated frozen artifact——无论声称来自 mock、file、manual、rule-based 或真实 LLM——都必须取得当前 runtime authorization 才能部署。

`executor_identity`、`effective_sandbox_level` 与 `runtime_authorization_source` 是当前进程提供的普通运行时证据，不是不可伪造的 capability token。它们用于 fail-closed policy 与审计，但不能替代 OS/container capability isolation、签名 provenance receipt 或外部信任根。

当前执行边界仍是 `timeout_only`，不是完整 capability sandbox。真实 provider 的生成期执行默认阻止；所有 generated frozen deployment 默认阻止并独立需要当前 deployment runtime authorization。显式风险确认只授权在该弱边界中执行，不会提升隔离强度。尚未解决的安全风险包括 CPU、内存、文件系统、网络、环境变量和后代进程树的能力隔离；在获得更强 OS/container 隔离前，真实 LLM 生成代码只可在显式人工风险确认后的受控环境中使用。

仍未满足的研究与复现目标包括：

- feedback 的 top/weak pool、显式 elite lineage、多样性保留和候选去重仍需形成完整协议实现；
- fallback 尚缺 run 级聚合、污染标记和逐 trial 环境 manifest；
- 当前轮次产物尚未完整覆盖 versioned schema、jsonl trial、provider/environment manifest 与论文级成本审计。

这些剩余差距必须继续通过独立 TDD 和复审任务关闭，不得在论文实验中用文档声明替代工程证据。

## 11. 论文贡献候选与验证要求

### Contribution 1：DP-aware ALNS 框架

候选表述：面向多机器人矩形覆盖任务分配，提出以分层 DP 精确评价固定任务序列、以 ALNS 搜索任务分配与排序的框架。

需要验证：与确定性 baseline、普通局部搜索和非问题特定 ALNS 的公平比较；证明所谓 DP-aware 变体具有真实且唯一的算法差异。

### Contribution 2：LLM-generated operator evolution

候选表述：LLM 生成/修订受限 repair/destroy 代码，基于多实例、多 seed 的 EA 式闭环进行选择、精英保留与迭代改进。

需要验证：内置算子、单轮生成、无反馈、多轮 revision、无 elite、无 diversity、mock/file/真实 LLM 等消融；报告泛化到未参与演化的测试实例。

### Contribution 3：Safety-gated evaluation and freezing protocol

候选表述：为生成式搜索算子建立静态门禁、隔离执行、硬超时、公平评价、证据化冻结与 fallback 归因协议。

需要验证：危险代码拒绝率、误拒/漏检测试、timeout/异常/无效解注入、hash tamper、registry/load/runtime failure 和 fallback 污染检测。

### Contribution 4：消融与成本分析

候选表述：系统分析 DP-aware hints、repair-first、destroy 配对、反馈、top-k、多样性、安全门禁对质量、稳定性与成本的影响。

至少报告：LLM 调用数、输入/输出 token、货币成本、候选有效率、wall time、sandbox overhead、每个有效/冻结算子的成本，以及最终 ALNS 质量/运行时收益。成本结论必须包含失败候选和重试成本，不能只统计成功调用。

## 12. 下一阶段主线与验收顺序

后续工作按以下主线推进：

1. **Baseline 稳定化**：统一成本单位、feasibility 强校验、配置与文档口径，确保 DP 和基础求解可复现。
2. **ALNS 研究**：建立真正可区分的内置/DP-aware 算子、扩展实例和多 seed 统计基线。
3. **LLM 离线算子演化论文**：实现安全执行边界、显式 elite/diversity/lineage、冻结审计，再运行真实 LLM 和论文级实验。

在第一、二主线没有形成稳定 benchmark 前，不应把真实 LLM 大规模实验作为优先事项。

## 13. 规格验收标准

实现方只有在以下证据均存在时，才能声称符合本规格：

- AST 危险能力测试、隔离/硬超时测试和审计字段测试通过；
- repair/destroy 公平性、方向、hard gate、no-valid-candidate 和 fallback 归因测试通过；
- `top_k_to_keep`、diversity、lineage 和逐轮文件契约有自动化测试；
- freeze/deploy 的 hash、feasibility、registry 和 fallback 故障注入测试通过；
- 小规模 mock 闭环可重复运行且输出 schema 完整；
- 真实 LLM 实验另行授权，且不得用于替代上述确定性测试。
