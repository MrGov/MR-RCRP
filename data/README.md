# Data directory — authoritative map (updated 2026-10-30)

Instance files use the six-line text format parsed by
`src/mrta_rect_coverage/core/instance_loader.py`. Naming convention:
`R{robot_count}_T{task_count}_{rep_id}.txt`.

Read this file before adding a dataset. Two datasets with the same family names
(`BASE`, `HV-GEOM`, ...) are **not** interchangeable: scenario labels repeat
across datasets while the instance bytes differ. Always join on a
dataset-qualified identity (`dataset_version` + `instance_id`, or the manifest
`path`), never on basename alone.

## What is here, and what each set is for

| Dataset | Instances | Role | Used by |
| --- | --- | --- | --- |
| `structural_benchmark_v1/` | 336 (7 scenarios x 3 splits) | **Authoritative cross-scale benchmark.** `development` 84, `validation` 84, `test` 168. Its manifest + intrinsic features are the identity record. | `e11_structural_benchmark.py` (development + validation), `e12_comparison.py` (4 development instances), future confirmation |
| `e10_structural_development/` | 21 (7 scenarios x 3 repeats, all R4/T40) | **Controlled single-scale mechanism set.** Task and robot counts are constant, so scenario effects are not confounded with scale. Development only. | `e10b_structural_dp_analysis.py`, `e14_state_regret_instrument.py`, `e15_cost_penalty_calibration.py`, `e16_cost_penalty_ablation.py` |
| root `R*_T*_*.txt` | 8 | **Legacy scale/smoke set.** The exact instances every recorded `e1`–`e9` run used, plus the shipped config defaults. Frozen; do not extend. | `configs/*.yaml`, `config.py` default, `e3_alns.py`, `e4_decision_feedback.py`, `e7_cooperative_evolution.py`, `e14` smoke, `e15` probe |
| `r2_sanity/` | 6 (2 per split) | **Parser/provenance sanity artifacts** declared by `manifests/r2-sanity-v1_*.json`. Not paper-scale. Its `held-out/` is permanently diagnostic-only (already consumed by R3). | `dataset_protocol.py` (`build_sanity_dataset`), E1/E1R records |
| `MR_RCRP_Structural_Benchmark_v1/` + `.zip` | generator + README, archive | **Provenance of `structural_benchmark_v1/`.** Immutable; kept so the benchmark can be regenerated and compared byte-for-byte. | documentation only |

The 8 retained root instances are:

```
R2_T6_0  R2_T10_0  R2_T20_0  R2_T20_3
R4_T40_0  R4_T60_8  R8_T80_0  R8_T100_5
```

Every other root instance (53 files) was referenced by no experiment, config,
test, or manifest, and was removed on 2026-10-30 so that new work cannot silently
sample an unreferenced population. They remain recoverable from git history
(`git checkout <rev> -- data/`).

## Known caveat: the evolution loop's default glob

`llm/operator_evolution/evolution_loop.py` defaults to
`benchmark_instance_glob = "data/R*_T*_*.txt"`. That glob now resolves to the
**8 legacy root instances**, not to a paper-grade set. Any new operator-evolution
run must set `benchmark_instance_glob` explicitly to a manifest-backed dataset
(recommended: `data/structural_benchmark_v1/development/`, loaded through its
manifest so scenario-qualified ids are preserved). Do not read a new run's
numbers as comparable with `e4`/`e5`/`e7`/`e8`, which used the legacy root set.

## Splits

`structural_benchmark_v1/test/` (168 instances) is a locked split; the `e11`/`e12`
runners refuse to open its TXT files at this stage. Opening them requires a
separately approved final-test authorization (see `docs/final_test_protocol.md`).
`data/r2_sanity/final/` is **not** a locked test split and must never be
relabelled as one.
