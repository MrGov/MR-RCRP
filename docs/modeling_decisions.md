# MR-RCRP 建模口径决策

## 1. 文档状态与适用边界

- **状态：** 已批准（2026-08-06），R1 实现完成（2026-09-28）。
- **正式主口径：** 候选 B——统一时间单位，并使用独立的 `travel_speed`。
- **解释边界：** 目标值是 Manhattan travel、constant speed、无 collision/congestion、无 acceleration/deceleration、无 charging/refueling 假设下的 **estimated completion time**，不是实际机器人系统的完整物理执行时间。
- **Sensitivity：** `travel_speed = sweep_speed` 只作为次要 sensitivity，不是主口径或默认迁移值。
- **当前实现口径：** 候选 B——实例显式提供 `sweep_speed` 与 `travel_speed`，三类 transition 均为 `ManhattanDistance / travel_speed`。
- **实验门禁：** R1 只关闭核心模型正确性问题；它不授权 benchmark、pilot、provider、final-test 或论文级结果生成。

本文件记录决策及 R1 实现状态；实现完成仍不使真实 LLM 或任何实验获得授权。

## 2. 当前代码事实

一个任务是轴对齐矩形。每个任务生成 4 个入口角 × 2 个 sweep mode，共 8 个状态。对状态 `s`，当前内部覆盖时间为：

`processing_time(s) = n_sweeps(s) * traversal_length(s) / sweep_speed + (n_sweeps(s) - 1) * turning_time`。

固定任务序列由 route DP 在各任务的 8 个状态间选择最低时间状态链。当前路线时间是：

`route_cost = depot_to_first + Σ processing_time + Σ inter_task_transition + last_to_depot`。

其中 depot→first、task→task 和 last→depot 三类 travel 项均由 `CostMatrix` 计算 `ManhattanDistance / travel_speed`。多机器人目标为：

`minimize max_r route_cost(r)`。

当前实例第二行为 `sweep_width sweep_speed travel_speed turning_time`；旧三参数格式 fail closed。现有两个 smoke 实例显式设置两个 speed 均为 `1.0`。

## 3. 候选 A：Prototype legacy metric（未选为正式口径）

### 3.1 定义

- 矩形内部：`length / speed + turn cost`；
- 矩形之间：Manhattan distance；
- 解释一：混合“内部时间 + 外部距离”的启发式代价；
- 解释二：隐含 `travel_speed = 1 distance-unit/time-unit`，且坐标距离已经使用与 `turning_time` 一致的时间标度。

### 3.2 评价

| 维度 | 评价 |
|---|---|
| 与当前代码一致性 | 历史口径；R1 后不再是当前实现。 |
| 与 MR-RCRP 定义一致性 | 仅在显式固定 `travel_speed=1` 或把 Manhattan distance 定义为已归一化时间时一致；一般 `speed != 1` 时量纲不清。 |
| 对测试和既有结果 | 不改变当前测试数值；现有结果仍只能按该 prototype 定义解释。 |
| 论文可解释性 | 较弱。审稿人可能无法判断速度改变为何只影响覆盖而不影响转移。 |
| 是否重跑实验 | 保持口径本身不要求重跑，但此前没有论文级实验，且不得把 prototype 结果升级为物理时间证据。 |
| final paper 适合度 | 不推荐作为主口径；可作为兼容性或敏感性对照。 |

### 3.3 允许范围

在候选 B 实现前，两个旧 `speed=1` 实例只用于 smoke/debug。该历史许可已由 R1 的显式双速度 schema 取代。

候选 A 仅用于兼容现有代码和 smoke/debug 历史，不是 formal experiment modeling decision。代码迁移完成后，A 口径的结果、operator ranking 与 frozen artifact 必须保留 legacy objective 标签，不能与 B 的结果合并。

## 4. 正式口径 B：统一时间单位

### 4.1 定义

将所有路线成本统一为时间：

`travel_time(p, q) = ManhattanDistance(p, q) / travel_speed`

`processing_time(s) = coverage_length(s) / sweep_speed + turn_count(s) * turning_time`

`route_time = travel_time(depot, first) + Σ processing_time + Σ travel_time(exit_i, entry_{i+1}) + travel_time(last, depot)`。

坐标、扫掠宽度和矩形尺寸使用同一距离单位；`sweep_speed` 与 `travel_speed` 使用该距离单位/时间单位；`turning_time` 使用同一时间单位。二者都必须是有限正数，`turning_time` 必须有限且非负。

该目标的正式解释受以下假设约束：

- 任务间采用 Manhattan/rectilinear travel；
- coverage 与 travel 分别以固定 `sweep_speed`、`travel_speed` 运动；
- 不建模机器人间 collision、congestion 或互相等待；
- 不建模 acceleration/deceleration；
- 不建模 charging、refueling 或能量约束；
- 除已计入的 coverage turning time 外，不额外建模转向动力学。

因此论文和结果表必须称其为“上述简化运动模型下的 estimated completion time”，不能称为实际机器人系统的完整物理执行时间。

### 4.2 共用速度与独立速度

有两个可实现子方案：

1. **共用速度：** `travel_speed = sweep_speed = speed`。格式变更最小，但假设机器人覆盖与空载转移速度相同。
2. **独立速度：** 保留/重命名现有值为 `sweep_speed`，新增 `travel_speed`。假设更透明，也允许在 sensitivity analysis 中分别改变两类速度。

**正式采用独立 `travel_speed`。** `travel_speed = sweep_speed` 仅作为预注册 sensitivity；不得作为正式主口径，也不能由未记录的运行时默认值悄然注入。

### 4.3 评价

| 维度 | 评价 |
|---|---|
| 与当前代码一致性 | R1 已实现 processing/travel 统一时间、独立速度和严格实例格式。 |
| 与 MR-RCRP 定义一致性 | 最强。makespan 可解释为已声明简化运动模型下的 estimated completion time，但不是完整真实系统执行时间。 |
| 对测试和既有结果 | cost matrix、DP、lower bounds、solution、baseline/ALNS 与 operator benchmark 的期望值可能改变；需要系统迁移测试。 |
| 论文可解释性 | 最清晰，可分别报告 sweep/travel/turning 对总时间的贡献与敏感性。 |
| 是否重跑实验 | 是。目标函数改变后，所有性能、排名、frozen selection、portfolio 与 baseline 结果均须重跑；旧结果不得混入。 |
| final paper 适合度 | **推荐。** 适合作为正式主口径。 |

### 4.4 R1 实现影响面

批准后的核心迁移已在 R1 实施：

- `core.models.Instance`：区分 `sweep_speed` 与 `travel_speed`，或以兼容字段明确二者关系；
- `core.instance_loader` 与实例 schema：版本化读取 travel speed，验证有限正数，定义旧六行格式迁移规则；
- `core.cost_matrix`：三类 Manhattan distance 均除以 `travel_speed`；构造器必须显式获得速度，不能默认 `1`；
- route DP、solution evaluator 与 lower bounds：确认所有输入成本均为时间，更新 trace/字段命名和数学说明；
- config/runner：通过显式实例文件记录两种速度及参数来源；
- tests：新增 `travel_speed != 1` 的解析与三类 transition 回归，并重跑 core solver 与 smoke；
- README、`AGENTS.md`、配置说明与数据说明：同步公式、单位和迁移规则；
- 结果治理：作废旧 objective version 下的性能比较、候选排名与 frozen artifacts，并在新口径下重跑正式实验。

迁移合同要求实例 schema 显式提供独立 `travel_speed`；所有 depot/任务间 transition cost 为 `Manhattan distance / travel_speed`。R1 已同步 README、`AGENTS.md`、tests、实例格式和 smoke 解释。正式论文实验仍需独立的 R2 数据协议授权。

## 5. 候选 C：Alternative but not selected

### 5.1 定义

不声称 makespan 是物理时间，而定义版本化无量纲代价。例如：

`state_cost = w_cover * normalized_coverage_length + w_turn * normalized_turn_count`

`travel_cost = w_travel * normalized_Manhattan_distance`

`route_cost = Σ state_cost + Σ travel_cost`，目标仍为最小化最大 route cost。

归一化常数必须在看 final test 前固定，可来自实例生成范围或 train-only statistics；不得用每个 final-test instance 自适应缩放后改变跨实例可比性。所有权重、尺度、版本和 sensitivity grid 必须写入 manifest。

### 5.2 评价

| 维度 | 评价 |
|---|---|
| 与当前代码一致性 | 需要显式权重/归一化层；当前实现没有对应 schema。 |
| 与 MR-RCRP 定义一致性 | 可作为抽象优化目标，但不再是直接物理完成时间。 |
| 对测试和既有结果 | 大范围改变成本与排序，需要新测试并重跑全部实验。 |
| 论文可解释性 | 若论文关注通用 weighted objective 可接受；若强调实际机器人完成时间，则弱于 B，且权重选择易受质疑。 |
| 是否重跑实验 | 是；权重或 normalization version 变化都必须重跑。 |
| final paper 适合度 | 可作敏感性/扩展，不推荐作默认主口径。 |

候选 C 是可研究的 alternative objective，但本项目本轮未选择它作为正式实验口径。除非未来建立新的 objective version、重新审批并重跑全部实验，否则不得把 C 的加权代价与 B 的 estimated completion time 混合报告。

## 6. 比较与正式决策

| 口径 | 代码改动 | 物理解释 | 结果兼容 | 正式论文推荐 |
|---|---:|---:|---:|---:|
| A：prototype / implicit speed=1 | 无 | 低到中 | 保留当前数值 | 否，仅 smoke/兼容对照 |
| B：统一时间 + independent travel speed | 中 | 高 | 需要全量重跑 | **是** |
| C：归一化加权代价 | 中到高 | 低（明确为代价） | 需要全量重跑 | 可作扩展/敏感性 |

**Phase 5A-S 正式决策：采用 B，并使用独立 `travel_speed` 作为正式实验主口径。** Manhattan metric 仍是环境运动假设；如果机器人实际上可沿欧氏最短路移动，需要另立建模决策。本决策不把 Manhattan、恒速或无交互假设伪装成完整真实机器人动力学。

以下是 R1 前的历史门禁：

1. 当时实现继续按 A 记录，显式假设 `travel_speed=1`；
2. 当前两个实例只用于 smoke/demo；
3. 不生成论文主结果、不冻结正式 operators、不打开 final-test lockbox；
4. 不允许把 A 与 B/C 的 makespan、相对改善或 operator ranking 放入同一分析。

R1 后，核心实现采用 B；任何历史 A 结果或 frozen artifact 仍不得与 B 结果合并。当前 smoke 数据显式使用 `travel_speed=1`，因此只用于回归时保持原数值，不构成论文级性能证据。

## 7. 批准后的验收条件

- objective model 有稳定版本号及单位说明；
- 实例/配置显式记录两个速度或明确的共享关系；
- 非 `1` travel speed 的单元与集成测试通过；
- cost trace 中 processing、turning 与 travel 分量可审计；
- README、AGENTS、schema、generator 与实验 manifest 口径一致；
- 旧结果和 frozen artifacts 被标记为旧 objective version，不可误部署；
- 正式 benchmark 只使用新生成并按协议冻结的实例。
