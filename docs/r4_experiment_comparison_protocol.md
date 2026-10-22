# R4 Experiment Comparison Protocol

Design only; no execution authorization.

## Main Chain

| ID | Condition | Purpose |
|---|---|---|
| B0 | Manual ALNS | non-LLM reference |
| L0 | One-shot LLM operator generation | generation baseline |
| L1 | Multi-round scalar/top-weak feedback | generic evolutionary feedback baseline |
| L2 | Exact-DP-grounded behavioral evolution | primary C1 condition |
| L3 | L2 plus exact-DP-response complementary operator set | secondary C2 mechanism |

C3 counterexample feedback is a secondary ablation, not part of the minimal main chain.

## Direct Threat Comparisons

1. **Generic performance-profile / behavior feedback (ReVEL-like):** use structured instance-performance and generic behavior fields without exact Route-DP response.
2. **Instance-performance complementarity only (EoH-S-like):** use instance-wise performance vectors/CPI-style set construction without DP response or MR-RCRP DP descriptors.
3. **Targeted failure repair (RouteRepair-like):** use generic failure labels and targeted fixed-backbone repair, then compare with exact Route-DP structural counterexamples and assignment/bottleneck evidence.

The first comparison distinguishes generic structured feedback from exact-DP-grounded feedback. The second distinguishes instance-performance complementarity from exact-DP-response complementarity. The third tests incremental value of exact-DP counterexamples rather than claiming generic failure-aware repair.

## Fairness Contract

Every condition freezes maximum LLM calls, generated-candidate evaluations, train/dev family access, Route-DP/ALNS budgets, solver seeds, deployment set size and independent evolution-run repetitions. Report calls, tokens, cost, wall-clock, candidate validity yields, timeout/fallback costs and Route-DP evaluation counts. Invalid, timeout and fallback candidates remain in the denominator.

The statistical unit is an independent evolution run, with hierarchy `evolution_run -> generation -> candidate -> instance -> solver_seed`.

## Contamination Rule

The six R3 diagnostic runs are `diagnostic-heldout-consumed` and may only be reported as development confirmation. They cannot be used for future selection or confirmatory claims. New unseen `selection-validation` and `confirmatory-heldout` splits must be generated before method selection. Final-test remains fully locked.

## Stop Conditions

No provider, candidate, pilot, benchmark, formal, final-test or T6 execution is authorized by this document. R5 requires separate authorization and must begin with mock/file/scripted providers only.
