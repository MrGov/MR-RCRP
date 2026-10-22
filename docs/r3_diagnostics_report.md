# R3 MR-RCRP Optimization Diagnostics

## A. Status

`OPTIMIZATION_DIAGNOSTICS_READY = TRUE`

R3 is complete for its bounded diagnostic purpose. The evidence is descriptive and
small-sample; it is sufficient to choose an R4 research direction, not to make a
paper-level performance or generalization claim.

## B. Current Instance Inventory

Track A contains 61 root-level, non-final instances accepted by the production
filename parser and loader. No family provenance is available, so no family or
regime label is inferred for these files.

| Robots | Tasks | Replicates |
|---:|---:|---:|
| 2 | 6 | 1 |
| 2 | 10 | 10 |
| 2 | 20 | 10 |
| 4 | 40 | 10 |
| 4 | 60 | 10 |
| 8 | 80 | 10 |
| 8 | 100 | 10 |

Track B adds two controlled development families and two controlled held-out
families, one instance per family. The R2 final split was not opened or executed.

## C. Track A / Track B

- Track A: 7 representative `replicate_id=0` instances, 29 runs. It supports
  scale, workload, attribution, route-balance, and DP-response diagnostics.
- Track B development: `F_DEV_BALANCED` (R2/T10) and `F_DEV_CLUSTERED`
  (R2/T20), 10 runs. Labels come only from the R2 generator manifest.
- Track B held-out: `F_HOLD_DEPOT_NEAR` and `F_HOLD_DISPERSED` (both R4/T20),
  6 runs. These were accessed only after H1-H3 were frozen.
- Total: 45 ALNS runs over 11 behavioral instances. The consolidated inventory
  retains all 65 non-final Track A/Track B input rows.

Legacy Track A and Track B development run IDs omitted source/family provenance.
Consolidation rebuilds every ID as
`{source_track}-{family_id or instance_id}-seed-{seed}-{config_hash[:12]}`.
All 45 normalized IDs are unique; raw JSON files are not rewritten.

## D. Diagnostic Budget / Seeds

- Manual built-in ALNS only: 3 built-in destroy and 3 built-in repair operators.
- 100 iterations, destroy fraction 0.25, simulated annealing.
- Stronger local search: one step per ALNS iteration.
- Seeds 0-4 for T <= 40 development runs; seeds 0-2 for T >= 60 and held-out.
- No advisor, provider, generated/frozen operator, or external candidate.

The 100-iteration budget was selected after 50/100/200 development probes based
on runtime, time-to-best, and convergence flattening rather than final objective.

## E. Scale Findings

Track A mean relative improvement ranged from 0.0965 (T6) to 0.3554 (T100).
It was not monotone: T60 and T80 were about 0.2783 and 0.2752, while T40 and
T100 were about 0.3537 and 0.3554. Runtime and DP work increased sharply:
mean 100-iteration runtime rose from 0.028 seconds at T6 to 42.0 seconds at T100,
and mean DP calls rose from about 12,101 to 1.69 million. T80 produced more DP
calls than T100 in this sample, so task count alone does not determine workload.

## F. Route Balance / Bottleneck Findings

Across the nine development behavioral instances, mean route-cost CV fell from
0.0769 initially to 0.0080 at the best solution. Initial CV had only a moderate
descriptive association with relative improvement (Spearman rho 0.40), while
positive bottleneck relief and relative improvement were strongly associated
(rho 0.967). Baseline makespan was more strongly associated with scale and
processing/travel pressure than with initial CV.

Conclusion: bottleneck relief is a central improvement mechanism, but absolute
difficulty is not reducible to initial route imbalance; scale and accumulated
travel/coverage load remain major factors.

## G. Assignment vs Ordering vs Local Search

Positive gains are summed only over accepted moves. Repair gain is measured
before local search, and local-search gain is reported separately. These are
cumulative transient gains, not an additive decomposition of final makespan.

Across development runs:

- assignment-changing repair gain: 15,014.24;
- ordering-only repair gain: 367.27;
- local-search gain: 9,723.24.

Assignment gain exceeded ordering gain at every Track A scale and in both held-out
families. Local search was nevertheless substantial and dominated attribution in
some smaller families, notably Track A T10 and both controlled development cases.
The defensible answer is: assignment is the primary aggregate improvement layer,
local search is a major second source, and repair-level ordering is minor.

## H. Objective Decomposition

Track A mean best-solution shares were approximately 0.318 travel, 0.578 coverage
traversal, and 0.104 turning. Controlled families span a wider range:

- `F_DEV_BALANCED`: 0.609 travel / 0.370 coverage / 0.021 turning;
- `F_DEV_CLUSTERED`: 0.249 / 0.698 / 0.053;
- `F_HOLD_DEPOT_NEAR`: 0.502 / 0.464 / 0.034;
- `F_HOLD_DISPERSED`: 0.956 / 0.042 / 0.002.

The component mix changes alongside operator behavior, but four controlled
families are insufficient to isolate a causal component-share effect.

## I. Operator Behavior

Operator ranking uses two explicit metrics:

- attribution plots: positive accepted pre-local-search repair gain per use;
- frozen H3: positive accepted total objective gain per use, exactly as
  predeclared.

Both metrics give the same top destroy operator in all four controlled families:
random destroy in both development families and geometry-aware destroy in both
held-out families. Pre-LS gain per use changed from random/geometry
0.539/0.000 and 1.868/0.169 in development to 1.047/2.420 and 5.794/8.341 in
held-out. This is evidence of structural complementarity, not a universal ranking
or an isolated causal operator effect because destroy and repair are paired.

## J. DP Workload

Route-DP compute time accounted for about 75% of development runtime on average.
The share was only 13.6% for T6, but about 86-94% for Track A T20-T100. Cache hit
rates ranged from roughly 0.68 to 0.99, while call counts reached 1.7-1.9 million
at T80/T100. Route DP is therefore the dominant measured computational bottleneck
at medium and large diagnostic scales, but not at the smallest scale.

## K. DP State Switching

Mean accepted-move state-switch fraction was 0.293 over the nine development
instances and ranged from 0.064 to 0.508 by instance. Destroy operators also
showed different DP responses in development: mean switch fractions were 0.190
for random, 0.122 for geometry-aware, and 0.262 for bottleneck-route destroy.
Coverage-state response is therefore non-trivial and operator-associated.

## L. DP Cascade

Mean accepted-move cascade ratio was 0.168 over development instances, with
instance means from 0.056 to 0.220. Development destroy-operator means ranged
from 0.077 to 0.160. Outer assignment/order changes therefore regularly trigger
state changes in tasks that were not directly removed, confirming material
outer-search/inner-DP coupling.

## M. Feature Relationships

All correlations below are development-only, descriptive Spearman coefficients
over nine behavioral instances. They are not significance tests.

- Relative H/V gap vs state-switch fraction: 0.45.
- Relative H/V gap vs cascade ratio: 0.083.
- Isolated state variability vs state-switch fraction: 0.367.
- Heavy-task ratio vs initial route-cost CV: 0.20.
- Task count vs relative improvement: 0.924.
- Spatial dispersion vs relative improvement: 0.917.
- Spatial dispersion vs longest-stagnation fraction: -0.883.

The large scale-related correlations are strongly confounded by the small,
structured sample. H/V sensitivity is at most a partial predictor of DP response.

## N. Q1-Q9 Answers

1. **Q1:** Assignment-changing repair is the largest aggregate source; local
   search is also substantial and sometimes dominant; ordering-only repair is
   consistently small.
2. **Q2:** Bottleneck relief explains much of improvement, but absolute difficulty
   also tracks scale and accumulated processing/travel pressure.
3. **Q3:** Scale, spatial dispersion, pairwise distance, and coverage/travel
   pressure have the strongest descriptive associations with baseline makespan
   and improvement. These variables co-vary and are not independently identified.
4. **Q4:** Operator ranking changes across controlled structures, but current
   evidence does not isolate travel/coverage/turning share as the causal driver.
5. **Q5:** The development association between H/V gap and switching is moderate,
   but held-out switching contradicts the predicted direction. The relationship
   is mixed rather than robustly monotone.
6. **Q6:** Yes. Non-zero cascade is recurrent and averages 0.168 in development.
7. **Q7:** Yes, provisionally. Random destroy leads in controlled development and
   geometry-aware destroy leads in both held-out families.
8. **Q8:** Longer stagnation is concentrated in smaller/lower-dispersion cases;
   the pattern is systematic in this sample but partly a scale/budget effect.
9. **Q9:** Yes at medium/large scale: measured DP compute dominates runtime. It is
   not the primary bottleneck at T6.

## O. Held-Out Confirmation

H1-H3 were frozen in `docs/r3_heldout_hypotheses.md` and
`outputs/r3_diagnostics/predeclared_hypotheses.json` before held-out access.

- **H1: mixed/partial.** Higher H/V gap increased cascade (0.1624 to 0.2254)
  but decreased state switching (0.4923 to 0.2699), contradicting half of H1.
- **H2: supported.** Mean assignment/ordering gains were 114.22/6.45 for
  `F_HOLD_DEPOT_NEAR` and 494.57/70.69 for `F_HOLD_DISPERSED`.
- **H3: supported.** Geometry-aware destroy led both held-out families under
  the frozen objective-gain metric, whereas random destroy led both controlled
  development families.

No threshold, metric, hypothesis, or budget was changed after held-out access.

## P. LLM Hypothesis Gate

### C1: DP-Grounded Behavioral Operator Evolution

`SUPPORTED`

Evidence: non-trivial switching and cascade, plus meaningful destroy-operator
differences in inner-DP response. R4 should condition operator proposals on
DP-derived behavioral signals rather than use only outer route geometry.

### C2: Complementarity-Aware Operator Set

`SUPPORTED`

Evidence: controlled development and held-out families have different top destroy
operators under both the frozen H3 metric and the LS-separated attribution metric.

### C3: Counterexample / Failure-Guided Revision

`PARTIALLY SUPPORTED`

Evidence: stagnation is concentrated in small/low-dispersion cases and several
operators show stable regime-specific weakness. The sample is too small and R3
contains no generated-code failures, so a full counterexample-learning claim is
not yet supported.

## Q. Recommended R4 Direction

Design, but do not yet implement, a DP-grounded complementarity-aware operator
method. The primary mechanism should combine C1 and C2: use route imbalance,
objective composition, DP switch/cascade response, and recent operator behavior
to propose a small complementary operator set. C3 should be a bounded revision
mechanism driven by explicit stagnation and failed bottleneck relief, not an
unconstrained code-generation loop.

## R. Files Changed

R3 added or modified diagnostic instrumentation, intrinsic features, tests,
offline run/consolidation scripts, raw and consolidated artifacts, plots, this
report, and the three planning records. Exact paths and SHA-256 values are recorded
in `progress.md`; raw-input hashes are embedded in `metadata.json`.

## S. Tests / Runs

- Clean RED: missing `r3_diagnostics` module during initial instrumentation TDD.
- R3 instrumentation tests: 8 passed before consolidation work.
- Analysis RED: missing analysis module; later one focused RED caught the
  controlled manifest/run identity mismatch.
- Final R3 focused tests: 12 passed, 0 failed, 0 warnings.
- Restricted core/R2 regression: 55 passed, 0 failed, 0 warnings.
- Diagnostic runs: 29 Track A + 10 Track B development + 6 held-out = 45.
- Full suite was not run.

## T. Gate Audit

- real LLM = NO
- provider = NO
- generated/frozen operator = NO
- candidate execution = NO
- pilot/formal benchmark = NO
- final-test = NO
- ML predictor training = NO
- Gate P2 = OPEN
- T6 = NOT AUTHORIZED

## U. Next Recommendation

`R4 - LLM Research Method Design`

Do not execute R4 without separate authorization.
