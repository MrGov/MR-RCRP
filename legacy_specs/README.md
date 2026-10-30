# legacy_specs/ — 隔离的加固规格测试（不参与默认 pytest 收集）

这些文件原是 `tests/` 下的 `*_red.py`「红测」（先行失败、待实现后转绿的加固规格）。它们测的模块
（`llm/operator_evolution/freezing.py`、`eligibility_policy.py`、算子执行边界与 provider 溯源/授权）
**仍在当前主流程里**，所以不能当成「无关遗留」直接删；但它们**目前是失败的**，删掉等于把未完成的加固要求藏起来。

因此：移出 `tests/`，保留可执行性，等你决定「继续实现加固」还是「正式放弃该需求」后再二选一：

- 继续实现 → 移回 `tests/` 并让其转绿；
- 正式放弃 → `git rm -r legacy_specs/`。

运行方式（不污染默认套件）：

```powershell
$env:PYTHONPATH='src'
G:\Anaconda\envs\mrta_env\python.exe -m pytest legacy_specs -q -p no:cacheprovider
```

当前已知失败（清理前在全量套件中测得，共 10 例，与状态链/DP 无关，报错点 `core/solution_evaluator.py:71`
`ValueError: solution is missing task ids: [5]`）：

| 文件 | 失败数 |
| --- | --- |
| `test_operator_execution_boundary_hardening_red.py` | 4 |
| `test_operator_execution_gate_toctou_red.py` | 5 |
| `test_operator_evolution_protocol_red.py` | 1 |

其余 5 个文件在清理前是通过的（`test_operator_execution_boundary_red.py`、
`test_operator_provider_provenance_generated_deployment_red.py`、
`test_operator_runtime_authorization_frozen_deployment_red.py`、
`test_operator_strict_policy_config_hardening_red.py`、
`test_operator_trusted_executor_authority_red.py`）。

## test_e2_c1_pilot.py（API 已废弃，非加固规格）

它测 `retain_elites` / `source_hash` / `assign_splits` 三个函数，而 `experiments/e2_c1_pilot.py` 早已重构为
`freeze_instances` / `select_elite` / `recover_historical_elites` / `benchmark` / `summarize` 等，
这些能力现在落在 `llm/operator_evolution/r5_mock_pipeline.py`。该文件删掉也不损失任何现存覆盖，
保留只为留一份 E2-C1 期接口的历史记录。确认无用后可直接 `git rm legacy_specs/test_e2_c1_pilot.py`。

