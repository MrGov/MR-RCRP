# MR-RCRP 结构化跨规模算例 v1

本数据集依据公开仓库 `MrGov/MR-RCRP` 的 E10 结构化设计思想，以及提交 `2c7b14aea4943126e1dcceb0e54d9fd5c1c61274` 中的六行 TXT 格式与 `instance_loader.py` 约定独立生成。

**用途**：后续 ALNS/LLM-ALNS 参数调节与跨规模比较。不是已由求解器验证性能的“高难度算例挑选集合”，也不保证任何方法胜出。

## 规模与数量

六组 R2_T10、R2_T20、R4_T40、R4_T60、R8_T80、R8_T100；七种情景：
BASE、HV-GEOM、SPATIAL、BOTTLENECK、TURN-HIGH、TRAVEL-HIGH、SWEEP-NARROW。

每组规模×场景：development 2 个、validation 2 个、test 4 个。共 84 / 84 / 168，合计 336 个实例。相同 split/规模/replicate 下的七种场景基于共同随机种子，有明确配对关系；不同 split 使用不同 seed 命名空间。

目录示例：`development/HV-GEOM/R4_T40_0.txt`。**文件名会在不同场景和 split 重复，程序读取时必须使用相对路径或 manifest 的 instance_id，不可仅以文件名去重。**

## 算例定义与参数

模型仍然同构：所有机器人在同一实例中共享服务速度、行驶速度、扫描宽度和固定转弯时间，depot=(0,0)。不引入最小转弯半径或机器人异构性。

基准参数 `(sweep_width,sweep_speed,travel_speed,turning_time)=(3,1,1,5)`。

- BASE：正方形地块边长从 12/15/18 中取值，随机非重叠分布。
- HV-GEOM：同一地块面积和中心不变，宽高比例调整为 9:1 或 1:9，允许周长和进出角点变化。
- SPATIAL：面积与地块尺寸不变，中心 `x` 坐标乘 2，空间分布和 depot 距离会共同变化。
- BOTTLENECK：约 10% 重任务，其余较轻；目标是总 `min(H,V)` 覆盖工作量接近 BASE（小样本受扫描次数取整影响，容许 5% 误差）。
- TURN-HIGH：几何不变，仅 `turning_time=10`。
- TRAVEL-HIGH：几何不变，仅 `travel_speed=0.5`。
- SWEEP-NARROW：几何不变，仅 `sweep_width=2`。

场景名称及指标均由生成规则与固有特征决定，没有参考任何算法的优化成绩。`intrinsic_features.csv` 为静态结构特征，不是 Exact Route-DP 的实际状态链或完整路径成本。

## 与 E10 数据集的关系

这是一套**独立的新版本**，使用相似的结构思想，但**不是 E10-A 的字节级复现**。采用不同的 dataset version、规模适配的平面尺度和新种子；不得混称 E10 数据。正式引入前，请在现有仓库使用生产 `load_instance`、`state_generator` 与 `RouteDPEvaluator` 检查几组数据，并记录检查结果。

## 使用

将 `structural_benchmark_v1/` 文件夹放到项目 `data/` 下，得到：

`data/structural_benchmark_v1/manifest.json`

现有 loader 可直接读取六行 TXT：

```python
from mrta_rect_coverage.core.instance_loader import load_instance
instance = load_instance('data/structural_benchmark_v1/development/HV-GEOM/R4_T40_0.txt')
```

请在仓库的 Python 环境里测试。

根目录的 `generate_benchmark.py` 为自包含可复现脚本：

```powershell
python generate_benchmark.py --validate --output data/structural_benchmark_v1
# 如需重新生成：输出至一个新的空目录，不覆盖已冻结的数据
python generate_benchmark.py --output data/structural_benchmark_reproduce
```

`manifest.json` 含相对路径、split、参数、随机种子、配对 ID 和每个 TXT 文件的 SHA256；`intrinsic_features.csv` 与 `structure_summary.json` 给出静态结构指标。

## 实验使用规则（重要）

- development：调参、LLM 算子迭代、初始比较。
- validation：确定拟采用的最终算法配置；不要反复根据 validation 成绩调整大量版本。
- test：算法/参数冻结后再运行，用于最终性能评价，**不可根据 test 结果继续修改算法再在同一 test 上宣称独立验证**。
- E10 的 21 个已使用开发实例不可伪装成新测试集。原 60 个常规算例可另作历史参照，并可对外报告。
- 所有算法在同一实例使用相同运行预算、求解种子、硬件/环境与目标函数。输出所有合法测试实例，不得按结果好坏筛选。
- 由于不同情景共享基础几何，统计时应把配对场景关系考虑进去，不应把每个情景实例都视为完全独立的随机几何样本。
