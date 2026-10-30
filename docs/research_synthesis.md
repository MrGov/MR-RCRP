# 研究内容、方法与问题梳理

本文件把仓库里已经实现、已经跑过的东西整理成一条可写论文的主线，并标出目前证据能支撑到哪一步、哪些地方还站不住。所有性能数字都来自 `outputs/` 下的真实记录，属于 development/exploratory 级别，不是 confirmatory 结论。

> 说明：用户提供的 GitHub 地址 `https://github.com/15628112531/MRTA_Rectangular_Coverage` 当前返回 HTTP 404，用户页与 GitHub API 亦为 404，站内搜索 "MRTA rectangular coverage" 命中 0 条。本梳理以本地工作区 `mrta_rect_coverage/` 为唯一事实来源。

## 1. 一句话定位

研究对象不是"用 LLM 直接解 MR-RCRP"，而是**用 LLM 离线设计 ALNS 的破坏/修复算子，并用精确 Route-DP 产生的行为证据驱动多轮修订与冻结部署**。求解阶段完全不调用 LLM；LLM 只产出可执行源码，真值由确定性评价器给出。

这条主线的可辩护点有两个：一是**可验证性**（每个候选都要过哈希、AST、接口契约、可行性、超时与回退门），二是**反馈的语义密度**（反馈不是"分数多少"，而是状态链层面的结构证据）。风险点同样明确：多轮修订相对 one-shot 的增益尚未在等预算下证明，且样本量只够做案例。

## 2. 问题与建模

**MR-RCRP（多机器人矩形覆盖路径问题）**：给定平面上 n 个互不重叠的矩形任务区、R 台同构机器人、原点处的仓库，要求给每台机器人分配一条覆盖全部矩形、每个矩形恰好覆盖一次的任务序列，最小化最大完工时间（makespan）。

单任务的状态空间是 8 个：4 个进入角 × 2 种扫描模式（H/V）。扫描模式的加工时间为

```
H: p = ceil(h / w) * width / v_sweep + (ceil(h / w) - 1) * t_turn
V: p = ceil(w / w) * height / v_sweep + (ceil(w / w) - 1) * t_turn
```

出口角由进入角与扫描次数的奇偶性唯一确定（H/V 各有一套奇偶映射，见 `AGENTS.md` 与 `core/state_generator.py`），因此"进入角"是唯一的状态选择变量。跨任务与仓库的移动时间统一为 Manhattan 距离除以 `travel_speed`。

这个建模的两个后果决定了后面所有算法设计：第一，**固定任务序列下的状态链是可以用 DP 精确求解的**，所以内层评价没有近似误差；第二，**序列层是组合爆炸**，所以外层只能启发式搜索。方法链就是围绕这个"内层精确、外层启发式"的分离建立的。

## 3. 方法链

整体是四层结构，每层的职责边界都很清楚。

**第一层：精确内层评价。** `core/dp_evaluator.py` 对给定任务序列做分层 DP：每个任务一层，8 个状态，层间 8×8 转移，末尾加返仓成本，复杂度 O(n·64)。`core/cost_matrix.py` 预计算 (8n+1)×(8n+1) 的全状态转移矩阵。`core/solution_evaluator.py` 把 R 条路线组装成解：强制恰好 R 条路线、每个任务恰好出现一次、空路线合法，返回 per-robot 成本与 makespan。这一层是全部行为的真值来源。

**第二层：ALNS 宿主搜索。** `heuristics/alns_solver.py`。`spatial_sort` 构造初始解；每轮按自适应权重抽一对破坏/修复算子，破坏比例 0.25，修复后跑一次更强的局部搜索，SA 接受（初温按 1% 变差、接受概率 0.5 校准，按时间进度降温，末端温度比 0.01），分段权重更新（segment 20，reaction 0.2），奖励 8/3/1 分别对应全局最优/改进接受/仅接受。这层是 B1 配置，也是所有生成算子的部署环境。搜索循环、奖励、接受、降温、局部搜索在全部实验中未改动。

**第三层：离线 LLM 算子演化。** `llm/operator_evolution/`。流程是：生成候选源码 → 加载与静态校验 → 有界子进程执行 → 在固定父解上做配对评价 → 产出结构化反馈 → 下一轮修订 → 精英保留 → 冻结。真实执行记录在 E2/E5/E7：provider 为 gpt-5.6-sol，temperature 0.7，每次请求返回 2 个候选，E5 做了 1 轮破坏算子修订（2 个父代 → 2 个子代），E7 做了 1 轮修复算子修订。

**第四层：冻结与部署。** `freezing.py` + `eligibility_policy.py` + `alns_solver._register_frozen_operators`。冻结时会固定候选 ID、源码哈希、代数、父代链、参数与数据集版本（见 `outputs/e11_structural_benchmark/algorithm_freeze.json`）。部署时按哈希重新校验源码，用 `register_development_destroy/repair` 注入到算子池，走统一的 wrapper、权重表和统计。

当前三个冻结算子：

| 角色 | 来源 | SHA256 前缀 | 结构 |
|---|---|---|---|
| D\* | E5 Round1 | `87622377ab2d` | 按路线真实代价算 critical pressure，构造相邻边的 credit bundle，逐次消耗 credit 并抑制同路线重复集中 |
| R\* | E2-R L2 | `cd1db2a1994b` | 缩放面积工作量、欧氏质心插入 detour、大任务优先、实测路线松弛 |
| R_aux | E7 Round2 | `b7f682eebb57` | min(H,V) 扫描加工时间（含转弯）、Manhattan 质心 detour、动态 regret 排序、投影瓶颈更新 |

`R_aux` 与 `R_*` 的差异不是"谁更强"，而是**失效模式不同**：前者偏最小工作量与插入优先级，后者偏面积负载与松弛度量。这正是 E8 用它做互补组合的动机。

## 4. 可验证性协议

这部分是工程贡献，也是审稿人最可能追问的地方。

**执行隔离。** 生成代码不在主进程里 import 执行。`candidate_execution.py` 每次调用 spawn 一个子进程：子进程校验源码 SHA256 → AST 校验 → 编译 → 执行模块 → 取函数 → 回 `ready` → 父进程传参 → 子进程调用 → 通过 Pipe 回传结果与有界日志 → 退出。导入超时与调用超时分开，超时即 terminate + join。执行器身份标记为 `timeout_only_subprocess_v1`，即**只有进程隔离与硬超时，没有 OS capability sandbox**，这条必须在论文里如实写明。

**Fail-closed。** 修复算子返回的解必须通过可行性检查（任务集合、路线条数、划分完整），否则丢弃并按 fallback 记一次 `_greedy_insertion`；破坏算子返回的移除集合必须满足数量与划分约束，否则退回 `_random_destroy`。回退事件进入 `fallback_events`，回退轮的奖励不计入该算子的信用（双生成算子同时回退时标记为归因不可分）。

**四轴结果分类。** `docs/research_hypotheses.md` 固定了 execution status → feasibility → optimization 的优先级与各自分母：执行率除以全部 scheduled trials，可行率除以 execution_success，优化率除以 executed+valid。这个规则的意义是防止把"跑通了"说成"变好了"。

**评价保真度可切换。** E13 给四种文献对比算法加了 `SearchConfig.evaluation_mode ∈ {exact, greedy}`。Greedy 模式逐任务选"入边 Manhattan 移动 + 加工时间"最小的合法状态，最后一个任务把返仓成本计入；Greedy 全程不构造 Route-DP，最终结果直接保留搜索最优解的实际状态链与真实成本，只做合法性/算术校验，不重新优化。Exact 模式保留搜索后独立 DP 复核。这给了"精度—成本"一个可测量的一维旋钮。

**截止时间语义。** 四种文献算法在每次路线评价前检查 deadline，超时抛 `SearchDeadline` 并展开嵌套栈，保留最后一个完整可行解；单次评价允许跑完。B1/Proposed 保留原有的"迭代边界停止"语义，超时量被测量并记录，不裁剪。

**加速路径（vNext）。** `persistent_candidate_execution.py` 的 `PersistentCandidateProxy` 用常驻 worker 复用可信导入，每次调用仍新建候选命名空间、每调用重验哈希、超时杀进程、失败丢弃 worker。生成算子单次调用从约 227 ms 降到 5.79 ms（10 任务）、255 ms 降到 53.10 ms（80 任务）。

## 5. 已有证据

| 实验 | 设置 | 关键结果 |
|---|---|---|
| E5 | 4 实例 × 2 seeds，B1 3×3 vs 4×4 | D\* 在固定父解上 +9.63%（8/8 可行）；完整 ALNS B1+D+R 比 B1 +1.78%（4/2/2）；10 任务例退化 |
| E7 | 1 轮真实修复修订 | 两个子代均未通过预注册的短 ALNS 质量门槛，R\* 保留；负结果如实记录 |
| E8 | 20 个历史候选统一评价 + 短 ALNS | V1 1541.625 → AUX 1523.875（+0.832%，4/1/3）；PORT 1542.125（−0.253%） |
| E9 | 复用 E8 + 8 次 PORT-ALL | PORT-ALL +0.463%；机制诊断为池替换与采样概率混杂，停止 C2 调参 |
| E11 | 7 dev + 3 validation 实例，seeds 0/1，60 次完整求解 | dev：B1 3834.742 / V1 3715.977 / AUX 3649.514；validation：2994.981 / 2875.182 / 2803.992；AUX 对 B1 +3.11%（dev）、+4.32%（val） |
| E12 | 4 实例 × 2 seeds × 6 方法 | Proposed 3270.954，CDABC 3254.271（最低），RNSGA 3266.089，B1 3303.588；Proposed 对 B1 +0.40%（3/0/5） |
| E13 | 4 实例 × 2 seeds × 11 方法 = 88 次 | Greedy 对 Exact 配对：CDABC −0.96%、RNSGA +1.13%、SGA-TS +0.80%、MRHDABC −0.06%；vNext 3234.350 对 original 3275.956（+1.365%，5/2/1），迭代 703.1 vs 92.6 |
| E13-Fix | 2 实例 × 2 seeds × 8 配置，1 秒预算 | 16 次 Greedy 在禁用 RouteDPEvaluator 构造与调用的条件下完成，DP 调用与复核时间均为 0 |

按规模拆开 E11 的 dev 结果，收益的分布比分项均值更能说明问题：R8_T100 上 AUX 对 B1 +9.45%，TRAVEL-HIGH +9.45%，TURN-HIGH +6.89%，BOTTLENECK +6.97%；而 R2_T10 −0.08%、R2_T20 −2.07%、R4_T40 +0.32%。**收益集中在大规模与旅行/转弯/瓶颈主导的 regime，小规模持平或轻微退化。**

## 6. 现在能支撑什么

**能支撑（Level 1–2，development 级）：**
1. 一条端到端可运行的离线算子演化流水线，含真实 LLM 请求、有界执行、可行性门、冻结与部署，且求解阶段零 LLM 调用。
2. 生成算子在完整 ALNS 中确实被选中并产生作用（E5 统计到 D 用 392 次、R 用 446 次、共同选择 132 次，零回退）。
3. 在 6 个规模档、7 种结构 regime 上，冻结算子组合相对人工 B1 有一致的正向配对均值（dev +3.11%、validation +4.32%）。
4. 部署层开销是结论的一阶混杂因素，且可以被工程手段消掉（E13 vNext 把迭代数提高 7.6 倍，配对均值再提升 1.37 个百分点）。

**不能支撑：**
1. 多轮修订优于 one-shot 或优于无反馈——没有等预算对照。
2. DP-aware 反馈的独立效应——F0/F1/F2/F3 与 H2 的 2×2 因子实验都没跑。
3. 行为互补 portfolio 优于同规模 top-k / single best——E8/E9 的池大小与采样概率混杂未拆分。
4. 统计显著性、泛化、SOTA——独立重复 n=1 个 evolution run，4 个实例 × 2 seeds 且 scale 与 scenario 混杂。
5. 跨问题族复用——明确禁止的表述。

## 7. 问题清单

按"对主张的杀伤力"排序。

### A 级：不解决就无法投稿

**A1 独立重复只有 1 个。** 项目自己规定独立重复单位是完整 evolution run，而真实 LLM 演化只做了 1 轮破坏修订 + 1 轮修复修订。H1a/H1b 要求以 scheduled runs 为总体做区间估计，n=1 时 CI 无法构造。目前所有数字只能定位成"单次演化的案例研究"。

**A2 缺少机制对照。** 论文的主主张是"多轮 + DP 证据反馈"有效，但现有实验只证明了"这组冻结算子比 B1 好"。要支持机制，至少需要：one-shot 生成、多轮无反馈、多轮 rank-only 反馈，四者在同等 LLM 调用数、候选数、benchmark 预算下比较。这是 H1/H2/H6 的核心，目前全部空缺。

**A3 小规模上收益为负且原因未隔离。** E5 里 10 任务例 B1 跑 15383 次迭代、生成配置只有 95 次，吞吐差 160 倍；E11/E12 里 T10/T20 也都是持平或退化。E13 证明这部分主要是部署开销，但 E11/E12 的结论仍建立在这个混杂之上。必须在论文中把"算子质量"与"部署成本"分开报告，否则"大规模有效"会被读成"小规模无效"。

### B 级：影响解释力

**B4 池替换与采样概率混杂。** E8 的 PORT 用 R_aux 顶掉人工 balancing，同时改变池大小与选择概率；E9 的 PORT-ALL 又改回五槽。三种配置之间无法归因。正确做法是固定池大小做替换，或固定成员做概率对照。

**B5 阈值是人工设定的。** E8 的筛选规则（均值退化 ≤2%、执行 ≤max(100ms,10×R\*)、硬父解 ≥0.5% 且至少两个实例、退化案例均值 ≥1%），E11 的 AUX 采纳规则（两个 split 都非负且失败率 ≤1%），都是研究者自由度。它们在看结果之前固定了，这点是加分项，但阈值本身缺少敏感性分析。

**B6 Greedy 与 Exact 的数值不可混用。** E13 的 88 次 Greedy 记录含最终 Exact 状态优化，E13-Fix 的完全 Greedy 记录不含，两者含义不同（前者接近精确最优，后者是贪心估计）。任何表格都必须标明该数字由哪个评价器产生。同时 Greedy 报出的 makespan 是所选状态链的真实成本，对同一序列而言 ≥ 精确最优，所以跨模式比较只能比较"搜索质量"，不能比较"解的质量"。

**B7 文献基线是改编实现。** 四个对比算法（CDABC、RNSGA、SGA-TS、MRHDABC）都是按论文描述重写并适配到 MR-RCRP 的，`ADAPTATIONS.md` 已逐条说明改动（种群 12 而非 130/80、容量约束移除、能量目标移除、MRNEH 优先级公式自拟等）。这是诚实做法，但不能声称复现了作者结果。E12 里 CDABC 均值最低，这个事实必须保留在论文里。

**B8 时间预算语义不统一。** 文献算法是严格 deadline（超时 ≤0.09 s），B1/Proposed 是迭代边界停止（E11 最大超时 7.03 s，E13 里 original 3.50 s、vNext 2.29 s）。等墙钟比较因此并不严格等预算。

### C 级：需要如实披露

**C9 隔离强度。** `timeout_only_subprocess_v1` 没有文件系统、网络或 CPU 的 capability 限制；vNext 的常驻 worker 进一步放弃了"每次调用重新解释器"。哈希 + AST 校验防的是意外与粗糙的恶意，不是针对性攻击。论文里只能声称"进程隔离 + 硬超时 + 源码绑定"，不能声称 sandbox。

**C10 可复现性。** 全部是墙钟预算，迭代数随机器负载浮动；记录过两次异常（一次 10892 s 的工具等待、一次 1302 s 的系统休眠），已归档并单次重跑。时间受限搜索本身不是逐位可复现的，只有固定代数运行才是。

**C11 样本设计混杂。** 7 个 dev 实例覆盖 6 个规模与 7 个 regime，但规模与 regime 一一绑定（每个规模只对应一个 regime），因此"按规模"与"按 regime"的分表都是描述性筛查，不是可分离的结构效应。

## 8. 下一步的最小实验集

按性价比排序，只列能直接改变论文可发表性的。

1. **等预算机制对照**（补 A2）：固定 1 个 evolution run 的算力，跑 one-shot / 多轮无反馈 / 多轮 rank-only / 多轮 DP 反馈四臂，在 E11 的 dev split 上评价。这一步决定主贡献是"演化有效"还是"DP 反馈有效"。
2. **补第二个独立 evolution run**（补 A1）：换 provider 种子或模型版本，得到 n=2，至少能报 run 间方差并说明稳定性；若资源不允许，就把全文改写成单案例 + 协议论文，并删掉一切统计语言。
3. **固定池大小的 portfolio 对照**（补 B4）：三个 4×4 池——仅 R\*、仅 R_aux、R\*+R_aux 各占两槽——比较组合效应，同时报告每槽使用率。
4. **评价模式分表**（补 B6）：所有质量结论用 Exact 报告，Greedy 只用于搜索成本/收敛分析，并在图注中写明"Greedy 曲线是估计值"。
5. **规模交叉点分析**：把 E11 的 6 个规模档画成相对增益曲线，明确给出"从多少任务开始稳定为正"，比报总均值有说服力。

## 9. 复现入口

```powershell
$env:PYTHONPATH='src'
# 文献基线
& 'G:\Anaconda\envs\mrta_env\python.exe' -m mrta_rect_coverage.experiments.e12_comparison --stage run
# 评价模式与 vNext
& 'G:\Anaconda\envs\mrta_env\python.exe' -m mrta_rect_coverage.experiments.e13_evaluation_efficiency --stage smoke
& 'G:\Anaconda\envs\mrta_env\python.exe' -m mrta_rect_coverage.experiments.e13_evaluation_efficiency --stage analyze
```

关键产物：`outputs/e11_structural_benchmark/{REPORT.md,algorithm_freeze.json,results.csv,paired_comparisons.csv}`、`outputs/e12_literature_baselines/REPORT.md`、`outputs/e13_evaluation_efficiency/`、`outputs/e13_fix_fully_greedy/REPORT.md`、`comparison_algorithms/ADAPTATIONS.md`。

理论文档：`docs/research_questions.md`（RQ1–RQ7）、`docs/research_hypotheses.md`（H1–H7 与分母规则）、`docs/research_method_vNext.md`（C1/C2/C3 与 Option A 选择序）、`docs/innovation_review.md`（四方向评分与审稿风险）、`docs/paper_contribution_plan.md`（章节结构与 claim ladder）。
