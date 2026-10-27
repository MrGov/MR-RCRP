This directory stores MR-RCRP instance files in the 6-line text format described in the project README.

Naming convention: R{robot_count}_T{task_count}_{rep_id}.txt
Example: R2_T6_0.txt

The top-level 60 regular main instances and the R2_T6_0 smoke input are retained.
`r2_sanity/` is the earlier, separate split-based dataset.

`e10_structural_development/` adds 21 development-only R4/T40 instances: seven
paired scenarios x three repeats. Scenario subdirectories keep the loader naming
contract; use the manifest's scenario-qualified identity, not basename alone.
See its `manifest.json`, `structure_features.csv`, `structure_summary.csv`,
`structure_checks.json` and `STRUCTURE_REPORT.md`. Do not mix this mechanism dataset
with the original scale dataset or treat it as held-out confirmation.

`structural_benchmark_v1/` is the separately supplied cross-scale benchmark,
version `mr-rcrp-structural-crossscale-v1`: 336 instances, with 84 development,
84 validation and 168 test entries. Read its manifest `instance_id` and `path`;
basenames repeat across splits and scenarios. E11 uses the original loader and
frozen solvers. Its runner intentionally refuses test TXT access at this stage.
The E10 structural development set remains a separate historical dataset.
The uploaded archive and its README/generator remain under
`MR_RCRP_Structural_Benchmark_v1.zip` and `MR_RCRP_Structural_Benchmark_v1/`.
