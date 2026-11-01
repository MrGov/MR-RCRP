# Data Directory

Read this file before selecting or adding instances. The production loader is `src/mrta_rect_coverage/core/instance_loader.py`; files use six nonempty lines and the filename form `R{robots}_T{tasks}_{replicate}.txt`. Dataset-qualified manifest identity and relative path are required because scenario labels and basenames repeat across datasets.

## Available Sets and Roles

| Dataset | Contents | Current role / caution |
|---|---:|---|
| `structural_benchmark_v1/` | 336 instances: development 84, validation 84, test 168 | Cross-scale, seven-structure benchmark. Development is for method work; validation has been used by E11 selection and is not untouched confirmation. Test is locked. Use the manifest identity/path and verify its SHA-256. |
| `e10_structural_development/` | 21 instances, seven structures, all R4/T40 | Controlled single-scale mechanism data. Not interchangeable with structural benchmark instances. |
| root `R*_T*_*.txt` | 8 retained legacy instances | Smoke and historical-run compatibility. Evolution defaults that glob these files unless an explicit manifest-backed input is supplied; do not treat it as a fresh paper split. |
| `r2_sanity/` | 6 manifest-backed instances, two per split | Parser/provenance sanity artifacts, not paper-scale evidence. Its diagnostic-heldout records have been consumed. |
| `MR_RCRP_Structural_Benchmark_v1/` and zip | generator/provenance material | Retained benchmark source material; not solver input in place of the installed dataset. |

The retained root files are `R2_T6_0`, `R2_T10_0`, `R2_T20_0`, `R2_T20_3`, `R4_T40_0`, `R4_T60_8`, `R8_T80_0`, and `R8_T100_5`. Their early generation provenance is author-reported; they are not the output of a currently recorded generator version.

## Access and Identity Rules

- Never join or deduplicate by basename alone. Use dataset version plus `instance_id`, manifest relative path, and file hash.
- For structured benchmark runs, resolve manifest-listed relative paths and verify the listed hash before loading. The project loader also checks filename/content dimensions and physical parameters.
- Do not glob across splits. `structural_benchmark_v1/test/` stays locked; do not inspect its instance text during development.
- Keep `e10_structural_development`, structural benchmark development/validation/test, root legacy data, and `r2_sanity` as separate identity domains.
- Do not relabel consumed R2 diagnostic-heldout material as fresh confirmation.

## Known Access Caveat

The evolution loop's legacy default `benchmark_instance_glob = "data/R*_T*_*.txt"` resolves to the eight root legacy instances. New development work must pass an explicit development input list or manifest-backed path and record the resolved identities. Historical E1–E9 results used their recorded inputs and are not automatically comparable to later structural benchmark results.

Data files, manifests, and hashes were not modified during the documentation consolidation.
