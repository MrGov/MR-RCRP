# R4 Research Method vNext

Status: design freeze complete. `LLM_RESEARCH_METHOD_READY = TRUE`.

This document does not implement production mechanisms or authorize real providers, candidates, pilots, benchmarks, formal experiments, final-test or T6.
It also does not claim completion of any T4-to-T5 path-evidence adapter or integration contract.

## Contribution Hierarchy

**Primary: C1 - Exact-DP-Grounded Behavioral Operator Evolution.** The LLM is an offline designer/reviser of MR-RCRP destroy and repair operators. Exact Route-DP and deterministic evaluation provide all behavioral truth.

**Secondary mechanism: C2 - Exact-DP-Response Complementary Operator Set.** EoH-S already covers instance-performance complementarity / heuristic-set design. The only possible distinction is `quality/reliability constraints -> MR-RCRP structural-regime coverage -> exact Route-DP response complementarity`, marked `POTENTIAL_DIFFERENTIATION - NOVELTY_UNVERIFIED`.

**Optional enhancement: C3 - Structured Counterexample-Guided Revision.** Generic failure-aware targeted repair is NOT our novelty claim. RouteRepair is a highest-threat comparator. C3 is an optional secondary ablation limited to exact Route-DP structural counterexamples and assignment/bottleneck evidence.

## Role Split and Scope

LLM = offline program/repair proposal. ALNS = host optimizer. Route DP = exact inner evaluator for a fixed task sequence. Deterministic evaluator = feasibility, objective decomposition, state-chain and response instrumentation. The LLM never decides feasibility, replaces DP, solves final MR-RCRP, or receives final-test results.

Initial generation is restricted to destroy, repair, inter-route, bottleneck and assignment-changing logic. Existing deterministic ordering local search, acceptance, controller and Route-DP implementation remain fixed.

Each candidate preserves candidate ID, operator type, source hash/text, generation/seed, prompt version, parent IDs, validation status, runtime, timeout/fallback/contract status, split and exact evaluator budget. An elite remains only with source/hash and explicit child-parent linkage.

## Exact-DP Behavioral Profile

The deterministic evaluator computes: DP state-switch fraction; H/V mode switches; entry/exit changes; indirect DP cascade count/ratio; assignment changes; tasks moved out of bottlenecks; bottleneck relief; travel/coverage/turning response; route-cost/CV response; valid/error/timeout/fallback/contract rates. These are descriptors, not objectives. Makespan and feasibility remain truth criteria. LLM self-evaluation is not evidence.

`StructuredOperatorFeedback` is versioned and contains scalar quality/rank, reliability, structural regime context, assignment/bottleneck response, exact DP state/mode/entry-exit/cascade response, objective components and cost accounting.

## Feedback Ablation

F0 = scalar/rank only. F1 = scalar plus top/weak. F2 = scalar plus exact-DP behavior. F3 = F2 plus structured counterexamples. Primary comparison is F2 versus F0/F1; F3 is secondary.

## Option A: Lexicographic Constrained Selection

No arbitrary weighted sum is allowed.

1. **Eligibility gate:** exclude invalid, infeasible, timeout-heavy, fallback-heavy, contract-invalid and runtime-unacceptable candidates. Reliability is a hard prerequisite.
2. **Minimum quality floor:** freeze on a new `selection-validation` split, including a reliability condition, before confirmatory-heldout access.
3. **Best-quality anchor:** select aggregate-quality-best eligible candidate with deterministic ties.
4. **Maximum marginal structural-regime coverage:** greedily add the eligible candidate covering the most currently uncovered regimes using existing intrinsic features: `task_robot_ratio`, `heavy_task_ratio`, `spatial_dispersion`, H/V sensitivity and travel/coverage regime.
5. **Exact-DP behavioral complementarity tie-break:** only after Stage 4 tie/threshold resolution, use DP state-switch, cascade, H/V, entry/exit, bottleneck-relief and objective-component profiles.
6. **Fixed small set size:** stop at a pre-registered size in `[2,4]`, frozen on selection-validation.

Candidate metric designs must be visible:

- Binary regime coverage: auditable but ungraded.
- Normalized marginal coverage: graded but needs normalization and can overweight rare regimes.
- Profile-distance coverage: expressive but sensitive to scaling.

Recommended default: binary regime coverage at Stage 4, profile distance only as Stage 5 tie-break. The final choice is frozen on selection-validation and reported.

## C2 Boundary and C3

EoH-S = instance-performance complementarity / heuristic-set design. This proposal = quality/reliability-constrained operator set, MR-RCRP structural-regime coverage, then exact Route-DP response complementarity. This is only `POTENTIAL_DIFFERENTIATION - NOVELTY_UNVERIFIED`.

C3 may use deterministic exact-DP counterexamples with assignment/bottleneck, mode-switch or objective-component regression. Compare against generic failure labels and targeted repair. RouteRepair's generic failure-aware targeted repair is not claimed as ours.

## Deployment Policies

P0 single best; P1 uniform/random set choice; P2 deterministic structural selector; P3 lightweight adaptive selector/bandit as future secondary comparison. No online LLM selector is default. InstSpecHH and HeurAgenix are selector threats.

## Main Experiment Chain and Threat Comparisons

B0 = Manual ALNS; L0 = one-shot LLM generation; L1 = multi-round scalar/top-weak; L2 = exact-DP behavioral evolution; L3 = L2 plus exact-DP-response set. C3 is outside the minimal main chain.

Required direct comparisons: ReVEL-like generic performance-profile/behavior feedback; EoH-S-like instance-performance complementarity only; RouteRepair-like targeted failure repair. The protocol must distinguish generic structured feedback from exact-DP feedback, and instance-performance complementarity from exact-DP-response complementarity, under equal budgets. Full reproduction is not required.

## Splits, Statistics and Falsification

R3's six diagnostic runs are permanently `diagnostic-heldout-consumed`, usable only as development confirmation. New unseen `selection-validation` and `confirmatory-heldout` splits are mandatory: `evolution-development -> selection-validation -> confirmatory-heldout -> final-test lockbox`. Final-test is fully locked.

Equalize LLM calls, candidates, instance/family access, DP/ALNS budgets, solver seeds and deployment budget. Report calls, tokens, cost, wall-clock, syntax/contract/feasible/deployable yields; invalid/timeout/fallback remain in denominators. Statistical unit = independent evolution run, hierarchy `evolution_run -> generation -> candidate -> instance -> solver_seed`.

H-R4-1: F2 improves held-out quality/stability over F0/F1; falsified by no stable held-out difference. H-R4-2: L3 improves heterogeneous held-out performance over L2 single-best; falsified by single-best dominance or no benefit after cost. H-R4-3: exact-DP counterexamples improve yield/regime failure beyond generic repair; falsified if only cost increases.

## Readiness Boundary

R5 may later implement mock/file/scripted providers only. R4 freezes schemas, selection order, splits, comparisons and falsification conditions; it does not implement them. `LLM_RESEARCH_METHOD_READY = TRUE` does not close Gate P2 or authorize T6/R5 automatically.
