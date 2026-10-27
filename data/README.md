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
