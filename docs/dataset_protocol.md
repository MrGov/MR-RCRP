# R2 Dataset Protocol

Status: paper-data protocol draft validated by a small sanity dataset. This document does not authorize solver benchmarking, LLM use, pilot execution, or final-test execution.

## Current instance contract

The production loader consumes exactly six non-empty text lines:

1. `n_tasks n_robots`
2. `sweep_width sweep_speed travel_speed turning_time`
3. all `x_left` values
4. all `x_right` values
5. all `y_bottom` values
6. all `y_top` values

Files use `R{robots}_T{tasks}_{replicate}.txt`; the depot is `(0, 0)`, task IDs are input order, coordinates are model units, and all speeds/times use the model time unit. `instance_schema_version` is recorded in manifests as `mr-rcrp-instance-v2`; it is not inserted into the legacy-compatible six-line file.

## Versions and generator

- Dataset: `r2-sanity-v1` for this validation artifact.
- Generator: `mr-rcrp-deterministic-generator-v1`.
- Seed: SHA-256 of `dataset_version`, `family_id`, and `replicate_id`, truncated to the first 8 bytes as an unsigned integer. Generation does not use global random state and is independent of family iteration order.
- Geometry policy: non-overlapping rectangles, positive widths/heights, finite positive speeds, and non-negative finite turning time. Existing smoke files remain separate smoke inputs.
- Output is round-tripped through `load_instance` before being accepted. Existing files are never overwritten unless the caller explicitly requests overwrite.

## Family taxonomy and sanity matrix

Family labels are fixed before any solver outcome and use robot/task counts, load ratio, rectangle aspect regime, spatial placement, service/travel parameters, and H/V sensitivity. See `docs/instance_families.md` for the frozen six-family sanity matrix.

The complete future paper design should cross size (`T=10,20,40,80`), robots (`R=2,4,6`), low/medium/high task-to-robot load, square/elongated/mixed geometry, uniform/clustered/depot-near/dispersed spatial regimes, travel/balanced/coverage service regimes, and low/mixed/high H/V sensitivity. These axes are a plan, not executed evidence.

## Intrinsic features

`extract_intrinsic_features()` computes only instance-derived values: task/robot counts and ratio, coordinate spans, centroid/depot distance, dispersion, rectangle width/height and aspect summaries, H/V processing summaries, H/V gaps, speeds, turning time, and travel/coverage pressure proxies. It does not call a solver, benchmark runner, ALNS, DP evaluator, provider, or candidate executor. Family labels must never be defined from solver results.

## Splits and contamination

`development`, `held-out`, and `final` are disjoint split assignments at family level. Development is the only future method-development input; held-out is confirmatory generalization input; final is a frozen lockbox. The sanity set has two representative families and one replicate per split. No final artifact is exposed through development access.

All formal access must be manifest-driven. The loader reads only listed relative paths, confines them under the dataset root, verifies SHA-256 bytes, checks filename/content metadata through the production loader, and rejects unknown manifest fields, duplicate IDs, split mismatches, missing files, and hash mismatches. It never performs a `data/R*_T*_*.txt` glob.

Each manifest entry contains dataset/schema/generator versions, instance/family/split/replicate identity, generation seed, model parameters, regime labels, relative file path, file SHA-256, and generation-config SHA-256. It intentionally contains no baseline result, ALNS result, makespan, LLM score, ranking, or solver outcome.

## Sanity artifact locations

The generated validation artifacts are:

- `data/r2_sanity/development/` and `manifests/r2-sanity-v1_development.json`
- `data/r2_sanity/held-out/` and `manifests/r2-sanity-v1_held-out.json`
- `data/r2_sanity/final/` and `manifests/r2-sanity-v1_final.json`

There are two files in each split (six total). They validate generation, parsing, hashing, and split isolation only; they are not benchmark results.

## Full paper dataset plan

After separate authorization, freeze a complete family matrix before generating files. A concrete planning envelope is 12 development families x 10 replicates (120), 6 held-out families x 10 replicates (60), and 6 final families x 20 replicates (120), for 300 planned instances; the actual count must be confirmed by runtime and precision/power planning, not by the sanity set. Any regenerated family, split rule, objective version, or generation rule receives a new dataset version and cannot overwrite an existing manifest.

R2 stops before formal baseline-vs-ALNS comparison, significance testing, convergence studies, operator evolution, tuning, and final-test solver execution. The next permitted phase after review is R3 Optimization Diagnostics only.

## E10 structural development extension

The restrictions above describe historical R2. E10 adds a separate authorized
development dataset, reusing `FamilySpec`, `generate_instance`, hash seeds,
center/non-overlap helpers, TXT writing and `extract_intrinsic_features` in the
same module. Optional `structural_scenario` dispatches the paired design; the
legacy generator path and its configuration hashes stay stable.

`data/e10_structural_development/` contains seven scenario directories, each with
`R4_T40_0/1/2.txt`. Use scenario-qualified IDs or relative paths: basenames repeat.
All 21 entries in `manifest.json` are development and record BASE pairing, seeds,
physical parameters, homogeneous status and config/file/geometry hashes. Schema
`mr-rcrp-structural-development-manifest-v1` and dataset
`e10-structural-development-v1` are separate from the strict R2-only manifest loader.
The generator version is `mr-rcrp-paired-structural-v1`.

```powershell
$env:PYTHONPATH='src'
& 'G:\Anaconda\envs\mrta_env\python.exe' -m mrta_rect_coverage.experiments.dataset_protocol --structural-output data/e10_structural_development
& 'G:\Anaconda\envs\mrta_env\python.exe' -m mrta_rect_coverage.experiments.dataset_protocol --validate-structural data/e10_structural_development --validation-output outputs/e10_structural_development --smoke
```

Generation refuses an existing nonempty directory. Reproduce into a fresh path
and compare TXT hashes. Validation checks all 21 loader/hash/pair/non-overlap
contracts, reproduces bytes, generates 6,720 states, and uses Exact-DP to evaluate
one fixed complete round-robin solution per instance. `--smoke` adds only three
two-second manual B1 runs (BASE/HV-GEOM/SWEEP-NARROW replicate 0, seed 0), purely
for feasibility. Generation itself never invokes optimization.

Intrinsic features now also report unoriented aspect, H/V sweeps and parity,
H/V processing distributions, preferred turning share, workload CV/top-decile
share, nearest-neighbor distance and centroid travel/processing proxies. No solver
outcomes define labels or tune rules. Definitions and actual accompanying changes
are in the generated `STRUCTURE_REPORT.md`; each feature has mean/min/max in
`structure_summary.csv`, and per-replicate checks are in `structure_checks.json`.

The 60 original regular instances, smoke input and `r2_sanity` stay unchanged.
No held-out/final/lockbox data were inputs. Future confirmation requires freezing
this design before creating a new dataset version and independent seed namespace.
