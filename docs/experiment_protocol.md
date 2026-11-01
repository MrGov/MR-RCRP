# Experiment Protocol

This document sets current principles for interpretable development and future confirmation. It does not define a mandatory legacy experiment matrix or authorize provider use, a new experiment, or opening locked test data.

## Current Data Roles

- Use `structural_benchmark_v1/development` for method development and exploratory comparisons.
- Use `structural_benchmark_v1/validation` only for a predeclared selection/freeze decision; after that use, do not describe it as untouched confirmation.
- Keep `structural_benchmark_v1/test` locked until an explicitly approved final-test protocol is ready. Do not inspect its instance contents as part of documentation or method iteration.
- Treat E10's 21 instances as a controlled single-scale mechanism set, not as interchangeable with the cross-scale benchmark.
- Treat root legacy instances and R2 sanity artifacts according to `data/README.md`; R3 diagnostic-heldout observations are already consumed.

Manifest identity, relative path, dataset version, split, and file hash govern data access. Basename alone is not an instance identity. A comparison must use the same objective, evaluator mode, initial-solution rule, search controls, stopping budget, and solver-seed blocks unless the condition explicitly studies one of these differences.

## Method and Evidence Separation

The central question is the verifiable increment from LLM-assisted operator evolution in a strong MR-RCRP solver. Keep these evidence levels separate:

1. Candidate source validity and execution feasibility.
2. Fixed partial-solution repair/destroy benchmark quality.
3. Complete ALNS makespan, runtime, convergence, and fallback outcomes.
4. Independent-instance/family generalization and confirmatory inference.

An improvement at one level does not establish improvement at a later level. DP state changes, audit scores, operator-use frequency, and iteration throughput are diagnostics; they are not automatically quality gains or causal explanations.

## Fair Comparisons

Before a comparison, record method/source hashes, dataset and manifest identity, split, evaluation mode, ALNS configuration, operator-pool membership, initial-solution constructor, stopping budget, seeds, and runtime environment. Pair methods on identical instances and solver seeds where applicable. Report actual runtime, completed iterations, evaluator calls/cache misses, and convergence where available.

Count invalid candidates, errors, timeouts, fallbacks, and non-evaluable runs. Preserve the full scheduled denominator and retain unsuccessful outcomes. Do not add budget to a weak branch, change the evaluator, or revise selection rules after seeing comparative outcomes.

Candidate evaluation and deployment evaluation use different estimands. A fixed-repair improvement is not a complete-search improvement. A larger portfolio changes selection opportunities and is not by itself evidence of complementarity. Operator identity and any inherited frozen source must be verified from the run record rather than inferred from a method label.

## Statistical Claims

Development results are exploratory unless a separately frozen protocol establishes otherwise. Do not treat candidates, iterations, instances nested under a single generated artifact, or solver seeds as independent evolution repetitions. For confirmatory claims, freeze the analysis population, primary estimand, paired design, independent experimental units, failure handling, multiplicity plan, confidence interval method, and practical threshold before accessing the final-test split. Use the current [`statistical_analysis_plan.md`](statistical_analysis_plan.md) as a technical reference, while checking that its design matches the actual method and available data; its proposed hypotheses are not automatically current project commitments.

The minimal useful comparison should establish: (a) solver/evaluator correctness, (b) LLM candidate contribution against a strong non-LLM solver, (c) the incremental value of the claimed evolution/feedback mechanism against an appropriate LLM control, and (d) generalization on untouched instances. Additional portfolio, feedback-tier, or engineering ablations are optional and should be run only when needed to test a specific claim.

## Current Development Entry Points

From the project root, the current code supports:

```powershell
$env:PYTHONPATH='src'
python -m mrta_rect_coverage.main --config configs/default.yaml
python -m mrta_rect_coverage.experiments.e12_comparison --stage run
python -m mrta_rect_coverage.experiments.e12_comparison --stage analyze
```

The E12 default sample is four manifest-qualified development instances and seeds `0,1`; it is a small initial comparison, not a final benchmark. Its code includes B1, four adapted literature algorithms, and the E11-frozen Proposed/AUX path. E13 adds exact/greedy comparison-algorithm modes. Check the runner's current CLI and frozen-hash checks before reproducing historical experiments. Write new outputs to a new directory; never overwrite the historical records.

Historical E/R experiment reports, configuration, and exact commands remain the authority for what was actually run. Current code may differ from the revision used for a report. In particular, see `program_status_and_design.md` before interpreting E24/E25 mechanism results.
