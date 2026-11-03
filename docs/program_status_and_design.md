# Program Status and Evidence Boundaries

This is the current factual status page. It describes the repository at the reviewed local HEAD and available records; it is not an authorization to run providers, experiments, or locked data. Historical reports and raw outputs are preserved as recorded.

**Current development scope (2026-11-03):** the authorized structural-population
batch supersedes the previous call/skip-only next step. Its method and original-
paper comparison are in `operator_evolution.md`; implementation is
`heuristics/structural_search.py`, with runner `experiments/structural_population.py`.
The batch uses explicit destroy-repair deployment actions, structural generation,
multiple parents, complete timed solve selection and a reserved post-freeze check.
The original four-instance cache recheck remains historical evidence, unchanged,
in `outputs/bounded_repair_search/cache_opportunity_001/analysis.json`.

**Historical run_001 report (2026-11-03; superseded for current selection):**
`outputs/structural_population/run_001/summary.json` records four rounds, 18
charged provider attempts, six development instances x two seeds, frozen source
identities, and a once-only post-freeze two-instance check. The deterministic
exact-state-chain reference plus three manual pairs improved 10/12 development
rows (mean 2.66%), but lost all four stage-check rows to manual ALNS (mean loss
10.36%). The best single generated member improved the development mean 2.61%,
slightly below the deterministic reference, and lost the stage-check mean by
12.76%. The best two-generated-member set improved development by 2.14% and lost
stage check by 10.67%; removal checks did not support complementarity.
Recommended deployment remains manual ALNS. A branch-growth integrity defect
was fixed and the affected member reevaluated; its pre-fix 63,478-second result
is preserved and excluded. The stage-check IDs had prior E14 descriptive use;
they are not independent validation. See `operator_evolution.md` for method,
paper comparison, accounting, claim limits and next priority.

**Corrected full-solve review (review_002, 2026-11-03):**
`outputs/structural_population/review_002/analysis.json` reevaluates the frozen
archive under one shared deadline/price budget and disjoint phase timing. No LLM
calls were made. On 12 development rows (six instances x seeds 23/29), original
manual ALNS is the baseline; fixed manual-pair deployment is -2.93% (3 wins,
9 losses); the native state-chain reference is +0.77% (7/5); best single
generated member `r4_c2` is +1.67% (8 wins, 2 losses, 2 ties); and the original
two-generated-member composition is +1.64% (8/4). Against the fixed manual-pair
control those conditions improve 3.40%, 4.25%, and 4.18%. The `r4_c2` versus
reference paired difference is mixed (5/5/2), so LLM increment remains
inconclusive. Removing `r2_c2` from the multi set gives +1.98%; removing
`r4_c2` gives -2.32%. This supports pair compatibility and a smaller development
composition, not a benefit from larger portfolios.

The two older stage-regression instances were already described in E14 and are
development regressions, not independent confirmation. On them, manual pairs
lose 0.84%; reference, `r4_c2` single and original multi improve 4.78%, 9.84%
and 7.13%, while the shrunk `r4_c2` composition improves 10.23%. The row-level
and seed-level outcomes and all stage costs are in `review_002/analysis.json`.

The corrected run exposed a late candidate timeout that previously surfaced as
a runtime error. It now maps a strategy timeout at the shared deadline to an
incomplete iteration, retaining the last legal solution without reward. Every
final review row is feasible with zero candidate errors; structural budget
stops range from 9 to 12 per 12-row condition. In the representative native vs
isolated reference check, both returned makespan 2299, while native/isolated
completed 438/114 iterations and charged 0.027/1.05 seconds to the strategy
phase. Across `r4_c2`'s 12 solves, strategy boundary time is 32.92 seconds of
the same 80-second scheduled budget, versus 15.83 seconds exact pricing. This is
measured boundary cost, not evidence that native execution wins after adding
artificial costs.

The abnormal pre-fix `r1_c3` result is confirmed in request 8's prompt feedback
and selected as `r2_c3`'s parent; its descendant and later population/composition
history are contaminated. The final `r4_c2` lineages/freeze are unaffected, and
current evaluations for the affected candidates were rerun. History remains
unchanged in `run_001`; failed first-pass review rows are preserved beside the
corrected rows in `review_002`.

**Current decision and sole next priority:** do not make another LLM request.
Keep original manual ALNS as the production fallback. For development, retain
the smaller `random_destroy/greedy_insertion`,
`bottleneck_route_destroy/regret_k_insertion`, and `r4_c2` pair set as the
current structural candidate; do not retain `r2_c2` in that composition. The
sole next action is to batch or reuse checked-executor inputs to reduce its
measured copy/process overhead without changing policy actions, then rerun a
matched complete-solve comparison on a newly predeclared development sample.
Continue LLM evolution only after that comparison shows repeatable practical
value beyond the native reference. No external strong-algorithm comparison or
generalization claim has been established.

## Implemented Solver

- The production loader reads the six-line instance format and requires `sweep_width sweep_speed travel_speed turning_time` on line 2.
- Each rectangle generates eight legal entry/mode states. `state_generator.py` implements sweep count, processing time, and parity-dependent exit corner.
- `CostMatrix` prices depot and between-task transfers as Manhattan distance divided by `travel_speed`.
- `RouteDPEvaluator` optimizes the state chain for a fixed ordered route; `MultiRobotSolutionEvaluator` enforces one route per robot and exactly-once task coverage, then returns makespan.
- B1 ALNS searches task assignment/order with manual and optional registered generated operators, simulated annealing, segment-reactive weights, local search, and task-scaled runtime configuration. The exact active controls depend on the experiment runner/config; do not treat B0, B1, E5 V1, V2, or later portfolio settings as interchangeable.
- The offline evolution subsystem has real LangChain/OpenAI-compatible provider integration, source validation/execution paths, candidate evaluation, feedback/revision, selection and source-hash records. This is not an online LLM solver.
- Four comparison algorithms (CDABC, RNSGA, SGA-TS, MRHDABC) are adapted implementations. Their Greedy and Exact search modes are distinct; the E13-Fix records document the fully greedy path and its smoke scope. Their literature fidelity and broad competitiveness have not been established by the small development comparisons.
- E8/E9 portfolio exploration found quality crossovers but no reliable overall PORT gain. E10 created a 21-instance single-scale structural set; E11 introduced the 336-instance structural benchmark with development/validation/test splits. The test split remains locked by protocol.

## Problem-State Repair Portfolio Prototype

`experiments/operator_portfolio_evolution.py` is a runnable offline replay prototype. It holds destroy operators, initialization, acceptance, and priced local search fixed; captures early/middle/late baseline ALNS states; and evaluates hash-bound E17 repair artifacts on identical partial routes and removed tasks. Candidate effects are recorded before and after one fixed Route-DP-priced local-search pass. A state-coverage selector retains a single anchor and adds a repair only when it contributes a new state with post-local-search gain; it can leave slots empty. Short ALNS insertion/replacement checks compare the selected set, one champion, score-based top two, and the manual repair pool. Pair-level search gains are not apportioned to either member.

Run record `outputs/operator_portfolio_evolution/run_007/portfolio_evolution.json` used 12 hash- and raw-response-matched E17 repair sources, 36 paired repair cases on `development/BASE/R2_T10_0`, one separate stage-end check on `development/HV-GEOM/R2_T10_0`, 12 iterations per ALNS check, and one seed. All 12 candidates passed execution/feasibility checks. The state selector retained one repair (`7d89728c...`); its observed positive post-local-search gain was 13 model-time units in the early BASE state, while its middle and late BASE state gains were zero. It rejected the second score-ranked repair as redundant on the sampled state vectors. This supports behavior-based duplicate rejection on these cases, not a general complementarity gain.

The development short search gave makespans 1293 for the champion, 1293 for the state-selected set, and 1292 for score top-two; the manual pool gave 1292. Thus this run does not show a search gain from the complementary selection rule. On the separately reserved stage-end instance, the champion and state-selected set gave 1308, while score top-two gave 1401. The two development inputs are small variants from one R2/T10 family, the stage-end check is a single instance, and each result uses one seed; these are exploratory observations only. The replay loader chose score top-two from development short-search results, but the held-aside stage-end outcome exposes a material transfer loss. This is evidence against loading a larger pool based on a 1-unit development difference. The replay's actual two repair members were `repair_r001_001` (`7d89728c...`, from `generated_operators/e17/F2_dataset/rep0/round_001/repair_r001_001.py`) and `repair_r000_000` (`9d961afc...`, from `generated_operators/e17/F2_dataset/rep0/round_000/repair_r000_000.py`); their parent generate/revise raw-response files are listed in the run artifact.

The hand-written spatial-sort constructor's initial makespan was 1496 on BASE and 1407 on HV-GEOM; the new exact-DP insertion constructor produced 1365 and 1323, at 0.0044 seconds construction-plus-setup for each versus 0.0027/0.0036 seconds for spatial sort. This two-case initializer check is too small to establish a general improvement, but it justifies retaining `dp_greedy` as a low-cost comparison option. It is not part of the evolved repair portfolio. Existing priced neighborhoods already include bottleneck relocate, general relocate, intra-route swap, 2-opt, and inter-route swap. ALNS retains separate current and best solutions; SA uses nonnegative makespan difference, positive temperature floor, and accepts equal/improving moves directly. Segment updates preserve a weight floor, and the prototype's `operator_minimum_uses=1` gives each registered operator one call before roulette selection. Shared 8/3/1 iteration reward remains a co-selection statistic, not a causal repair-only effect; candidate pre/post local-search paired results are the operator-level evidence here.

For run_007, no LLM request was made: that replay used a zero call/token budget and exhausted its historical archive. Its suggested follow-up budget was only a proposal and is superseded by the bounded preparation and cost review recorded below. No test/lockbox data were accessed.

### Bounded Revision-Loop Preparation (run_012)

The current runner now admits up to two valid, behaviorally distinct repairs to short ALNS even when they do not pass the state-coverage gain threshold. Distinctness is measured from same-case pre/post-local-search makespan and per-robot Route-DP cost vectors; a candidate must remain feasible, stay below its measured execution-time cap, and avoid being dominated after the shared local-search pass. It is a diagnostic shortlist, not a deployment guarantee. Each comparison is a repair addition to the existing manual pool and selected repair; destroy, initialization, acceptance, and priced local search remain fixed.

`outputs/operator_portfolio_evolution/run_012/portfolio_evolution.json` evaluates 12 hash/raw-response-matched historical E17 repairs on six fixed states from `development/BASE/R2_T10_0` and `development/HV-GEOM/R2_T10_0` (72 paired cases). The baseline repair routes are taken from each actual ALNS iteration record. Both baseline and candidate receive the same one-pass priced local search on copies of their repaired solutions. Records include Route-DP state IDs, entry/exit points, transition costs, per-robot costs, candidate execution time, local-search time, DP calls/cache misses, prompt hash, and lineage. The ALNS check uses the same one-second wall-clock budget per group; each group gets a minimum call per registered repair, then independent roulette and the existing segment-reactive 8/3/1 reward update. Initial repair weights are all `1.0`. Rewards, accepted calls, global-best improvements, calls, and execution times are recorded by member; iteration reward is shared with the selected destroy/repair pair and is not treated as causal repair credit.

Two candidates entered the behavior-difference short list: `8816e7de...` and `026306bf...`. Both gave mean makespan `1346.5` after equal-wall-budget ALNS, versus `1300.5` for the single champion and the state-selected set; score top-two was `1339.5`. They were therefore rejected from deployment in run_012, which retained generated repair `7d89728c...` plus the three manual repairs. This supports admission of distinct behavior without demanding a higher single-operator average, but argues against incremental value for these two candidates under this budget. The record includes `development/SPATIAL/R2_T10_0` (makespan `1794`, 35 iterations, no fallback). SPATIAL was consumed in repeated preparation replays and is a development regression instance, not independent validation.

That replay made no new model request and preserved a Route-DP-grounded prompt. Its zero-budget preparation state and proposed 1,800-token output allowance are historical and superseded by the explicitly authorized batch below. The historical E17 response is not a new revision.

### Authorized Gap Revision Batch (2026-11-01)

`experiments/operator_gap_revision.py` and `configs/operator_gap_revision.json` executed the real feedback → prompt → response → source → paired evaluation → admission/rejection → ALNS path. Immutable evidence is in `outputs/operator_gap_revision/batch_001/`: `requests.json`, each request's prompt/raw response/source/parent diff, `results.json`, `cost_probe.json`, and `final_deployment.json`. The existing compatible provider and `gpt-5.6-sol` were used without changing credentials or endpoint. Client retries were zero and temperature omitted, disabling the provider's temperature-error retry. A request was journaled before invocation; both requests succeeded with no fixes/retries. Provider-reported usage was **106,174 input + 8,613 output = 114,787 tokens**; dollar cost is unknown. The batch took 129.24 seconds, including 90.25 seconds waiting for the two model responses. The 8,000-token per-request output allowance avoided truncation. The configured two-generation, one-child-per-generation batch ended at its predeclared limit, well within the user's maximum 3 generations / 16 requests; no new batch was started.

The true lineage is `7d89728c...` (historical E17 source) → `d31db788...` (request 1) → `ebea0de0...` (request 2). Both new candidates were executable and feasible on all six paired states. The first replaced center-distance scoring with local sweep-parity entry/exit compatibility, but did not fix the BASE early latent-bottleneck loss and degraded HV-GEOM middle by 72 after local search. Request 2 received these actual results and the deployment mean; its hypothesis targeted the static load penalty. It introduced dynamically updated route burden and cross-route regret task ordering. On HV-GEOM middle, repaired makespan changed from **1476 to 1315**, and post-local-search makespan from **1386 to 1314**. Task 8 moved off the costly route. This recovered the historical anchor's performance rather than establishing a new post-local-search advantage. On BASE middle, repair improved **1343 → 1292**, but both became **1292** after the fixed local-search pass. BASE early remained two units worse than the paired manual route. Entry/exit and transition records are fixed-route DP evidence, not a claim of exact joint marginal repair value.

All groups used spatial-sort initialization, identical one-pass priced local search, enhanced ALNS simulated annealing, two fixed seeds (23/29), and a nominal one-second solve budget on each of BASE and HV-GEOM. Destroy pool: `random_destroy`, `bottleneck_route_destroy`, `geometry_aware_destroy`. Manual repairs: `greedy_insertion`, `regret_k_insertion`, `bottleneck_balancing_insertion`. Every initial weight was 1; minimum use was 1, followed by independent adaptive roulette; segment length 4, reaction 0.2, weight floor 0.1, shared pair rewards 8/3/1. Full configs, per-destroy and per-repair calls, acceptance, current/best improvement, time, fallbacks, and histories are saved. The short-list gate allowed both children despite no improved mean post-local-search gain. Behavioral difference earned a trial only; retention required lower matched development mean, feasibility, no fallback, and actual calls to every generated member. Manual-only was eligible for the final choice.

| Deployment group | Mean makespan (4 runs) | New member calls / accepted / best improvements | Total solve seconds |
|---|---:|---:|---:|
| Three manual repairs | 1300.00 | — | 4.002 |
| Manual + historical anchor | 1313.00 | — | 4.120 |
| Manual + anchor + generation 1 | 1323.50 | 11 / 6 / 2 | 4.170 |
| Manual + anchor + generation 2 | 1300.25 | 10 / 9 / 3 | 4.246 |

All runs were feasible with zero fallbacks. Improvements and acceptance above are shared destroy/repair-iteration outcomes, not causal repair credits. The second addition improved over the anchor group on these development runs but did not beat manual-only. Final batch deployment therefore contains the three manual repairs and **zero generated repairs**; all historical/new sources remain archived. `--deploy-result` reloads this actual selection without provider calls; its consumed-development replay returned `[1292,1292,1308,1308]` and did not change selection.

Generated paired execution averaged 162–165 ms versus 0.7–0.9 ms for manual repair. A post-selection cost probe on the first predetermined state measured about 163–165 ms total for each generated operator but only 0.43/0.70/0.91 ms from post-import invocation through IPC return. Most observed cost is the per-call executor boundary, not arithmetic inside these candidates. The probe did not change selection. A correctness-test process overlapped part of the original second-generation deployment window, so after all tests stopped, **all four groups** were rerun exactly once with unchanged instances, seeds, nominal budgets, candidates, and selection rule. `timing_recheck.py/json` preserves that complete recheck: means were again **1300 / 1313 / 1323.5 / 1300.25**, with the same manual-only choice. Original measurements were not overwritten. One-second runs remain small development observations with iteration-boundary overshoot, not a robust general ranking. No unused independent development instance was established, so no independent validation is claimed. No final/test/lockbox instance was loaded.

**Decision: modify before further evolution.** Feedback produced traceable behavior changes and repaired a parent failure, but did not establish incremental post-local-search coverage or superiority to the manual pool. The gate did not block either candidate; quality/redundancy after local search and execution-cost/portfolio interaction are the observed limitations. The sole next priority is to investigate safe reuse of the isolated candidate execution process and then recheck these already-generated members under the same wall-clock budget, without more LLM generation. This would test the measured deployment-cost confound; it is not evidence that removing it will make the method win. Focused request-budget/deployment tests and the full suite were run (425 tests passed before the final replay CLI addition); the final focused verification is recorded in the runbook.

### Resident Executor and Replacement Recheck (2026-11-01)

The batch_001 follow-up above is now complete. `operator_gap_revision.py` reuses the existing `PersistentCandidateProxy` through a managed, explicitly reviewed source-hash gate, while preserving original per-call processes as a control. The three reviewed sources have only permitted imports and a top-level repair function; caches/routes are local, random draws use the supplied RNG, and no imported modules are modified. Every resident call still reads and checks the source hash, applies the AST policy, creates a fresh candidate namespace, enforces import/execution timeouts, bounds output, and validates the returned repair/coverage. Failure discards the worker. `ExitStack`/`finally` closes all workers on normal completion, exception, and early exit. No candidate executes in the parent process; this remains timeout-only isolation rather than an OS security sandbox.

`outputs/operator_gap_revision/executor_recheck_001/` contains the zero-LLM recheck. Thirty-two focused tests passed, including actual batch_001 parent/children (not just historical E5/E7 candidates), repeat A/B/A calls with input/RNG isolation, source drift, lineage identity checks, runtime errors, derived timeout/invalid-output fixtures, and cleanup on interrupted/failed solver exits. The research run additionally compared the five prescribed groups on two consumed development instances and seeds 23/29: **40 iterations per solve, no time deadline**, under both original and resident execution. All 20 paired solves had identical selections, acceptance/temperature histories, repaired/refined routes, final routes, DP counts/cache misses, and insertion-pricing counters. All paired-state Route-DP chains were identical too. Across groups, work differed: manual used 1,288 route-DP calls and 12,034 insertion prices across four fixed solves; child 2 used 1,190 and 11,228; history+child 2 used 1,184 and 9,886. Equal iteration counts are not equal computational work.

Calibration ran once on the first predetermined development state without using objective results. Resident validation/loading (including the preserved cold-process smoke) cost 169–182 ms/member; first worker startup cost 150–151 ms; subsequent calls averaged 2.41/3.83/3.83 ms for history/child 1/child 2, versus 163–169 ms with the original executor. The predeclared cost formula rounded the solve budget to **2.4 seconds**, saved to `calibration.json` before timed comparisons. Actual solves started cold: worker startup is inside the solve deadline; validation/loading and cleanup are outside that deadline but included in reported end-to-end time. No tests or other agent heavy workloads ran concurrently with calibration or the timed experiments.

| Group (each includes the three manual repairs) | Fixed 40-iteration mean, both executors | Resident 2.4-second mean | Resident iterations, sum over four runs | Generated calls, sum | End-to-end seconds, sum |
|---|---:|---:|---:|---:|---:|
| Manual only | 1300.00 | **1300.00** | 15,682 | — | 9.612 |
| Historical repair | 1300.50 | 1300.50 | 7,989 | 1,889 | 10.299 |
| Child 1 replacement | 1300.50 | 1300.50 | 6,161 | 1,498 | 10.295 |
| Child 2 replacement | 1301.75 | 1300.25 | 5,567 | 1,515 | 10.337 |
| Historical + child 2 | 1300.25 | 1300.25 | 4,674 | 791 + 1,035 | 10.964 |

All runs were feasible, had zero fallbacks, and closed their workers. The largest measured solve-deadline overrun was **3.971 ms**; 2.4 seconds is a nominal deadline checked between iterations, not a strict upper bound. Full startup/load/call timing, every manual/generated member's calls/acceptance/improvements, DP work and traces are in `results.json`. The unchanged public controls are spatial-sort initialization, one-pass priced local search, enhanced simulated annealing, the same destroy/manual pools, initial weights 1, minimum-use exploration 1, and the same segment update/reward policy. Resident execution is an engineering correction, not an algorithmic contribution.

Selection and feedback now distinguish (1) the evolution parent and its evaluated lineage, (2) the actual deployment winner, and (3) the proposed replacement/addition. A feasible candidate receives a replacement trial without requiring a new post-local-search state win; behavior novelty can additionally justify a bounded addition trial. The prescribed recheck considered only manual, history, child 1, child 2, and history+child 2. The actual best deployment remains **manual-only**; the evolution parent remains child 2 `ebea0de0...`. Thus `current_composition.generated_members` is correctly empty, not hard-coded to the historical operator.

The next prompt is saved, not sent: `next_prompt.txt`, `next_feedback.json`, and `prompt_lengths.json`. It includes the actual child-2 source once, aggregate comparisons, and exactly three cases selected by fixed rules: worst post-local-search result (BASE early), largest raw lineage change (HV-GEOM middle), and strongest remaining gain (HV-GEOM early). Complete local traces are referenced by stable case IDs and JSON pointers; only relevant task ports, neighboring tasks, route orders/costs and bottlenecks are excerpted. Length is **23,242 characters / 23,252 UTF-8 bytes**, versus 110,353 / 113,363 characters in the two actual old requests (about 79% fewer characters, not a measured token or dollar saving). Negative evidence is retained. No model request was made.

**Research judgment: C within this development batch.** Neither replacement nor addition beats the actual manual winner; no generated group wins any of the four timed instance/seed blocks. Child 2's post-local-search vector is exactly the historical vector `[-2,0,0,55,1,0]`; child 1 loses 72 on HV-GEOM middle. The current revision target has not added demonstrated search capability, even after removing the dominant process-start cost. This is not a general rejection of LLM evolution or a claim that these tiny instances prove superiority/inferiority.

The sole next priority is a small reachability check of **joint two-task insertion with a shared local entry/exit-state choice** before further generation. Code evidence: child 2's `insertion_hint` independently minimizes predecessor exits and successor entries; cross-route regret still commits tasks sequentially. Trace evidence: BASE early remains 1417 after local search versus manual 1415, with task 9 using state 72 rather than 67 and task 6 state 41 rather than 46. These associations motivate, but do not prove, the shared-state hypothesis. Check whether a bounded joint placement can produce a post-local-search outcome absent from the current manual/historical choices on the existing states; if not, do not deepen this lineage. The saved prompt is a concrete unsent sample for that hypothesis, not authorization to resume generation. No unused independent development data or final/lockbox was accessed.

### Bounded Exact Repair Search with Evolved Pair Ranking (2026-11-01)

The resident-executor recheck is complete; this batch changes the generated object's capability boundary. `heuristics/bounded_repair_search.py` owns exact insertion pricing and depth-two branch construction. The new isolated interface is `rank_pairs(features, rng) -> list[str]`, a permutation of supplied pair IDs. It ranks which **two task pairs** receive expansion, once per repair. Generated code receives batch features, never a solver or pricing object. `candidate_security.py`, the original worker and existing resident worker support this narrow type; hash checking, timeouts, fresh namespaces, bounded output and cleanup remain. Strategy imports are restricted to `math`, with imported-object attribute mutation rejected. `ALNSSolver.register_bounded_repair` registers the trusted kernel in the existing adaptive pool. No initialization, acceptance, global local-search or Route-DP recurrence changed.

Frozen limits in `configs/bounded_repair_search.json`: depth 2; a pool of at most six tasks chosen by exact singleton regret; at most two ranked pairs; both insertion orders; first beam width 3, second width 2; two distinct exact-partial-cost leaves per pair receive the same existing greedy completion; at most 36 materialized search-branch expansions and 4,096 insertion-slot prices per call. All robots and all positions are eligible, with no adjacency constraint. The greedy incumbent, singleton feature prices, second-step prices and greedy tails all consume this price budget. Each second insertion is priced on the actual route produced by the first; independent singleton costs are never summed as a joint objective. Insufficient optional-search budget returns the already feasible greedy incumbent. Inputs too large even to fund that common completion fail explicitly. The bounded kernel's slot counter is distinct from the pre-existing mixed `insertion_prices` instrumentation, which also counts some removal/replacement work.

Evidence is in `outputs/bounded_repair_search/run_001/`: frozen config/input/source identities, `cases.json`, `collection.json`, seven `paired_*.json` records, each real request's prompt/feedback/raw response/source/diff/lineage, `deployment_{iterations,time}.json`, `decision.json`, and `analysis.json`. The original six consumed R2/T10 states were retained. Before outcomes, two additional development inputs were fixed: `SPATIAL/R2_T20_0` (next larger spatial layout) and `BOTTLENECK/R4_T40_0` (four-robot bottleneck layout), replicate 0. Each supplied three rule-sampled early/middle/late states from a 24-iteration baseline trajectory with four tasks removed. All 12 cases were used for feedback and selection; no independent validation, test or lockbox access is claimed.

**Search capability:** deterministic reference pair ranking uses descending singleton-regret sum, then shared best-slot conflict. Compared with the best of the three manual repairs separately evaluated on each identical state, reference gains after the same one-pass local search were `[0,0,0,55,1,0,17,0,0,0,29.6497,0]`. This manual envelope is an offline diagnostic, not an online oracle. SPATIAL early supplies a concrete branch example: the winning order `[7,9]` retains the **third-ranked first insertion** and places the two tasks on different robots; its repair is 3636 versus greedy 3672, and post-LS is 3628 versus the best manual 3645. The benefit cannot be described solely as a different single-task greedy score. Extra three-pass LS was predeclared only for four early representatives: best manual/reference outcomes were BASE 1343/1343, HV-GEOM 1353/1315, SPATIAL 3555/3532, and BOTTLENECK 5108.827/5120.810. Thus some gains persist through additional existing LS, while the bottleneck early advantage disappears; the extra LS work and time are recorded and excluded from selection.

**True strategy lineage:** deterministic source `7709d3bf...` → real generation 1 `5e8a343b...` → real generation 2 `b55dac47...`. The existing configured `gpt-5.6-sol` made **2 actual requests**, consuming **67,651 input + 3,133 output = 70,784 tokens**, with 39.286 seconds of provider wall time. There were no retries, failures or engineering repairs; cost in dollars is unknown. Limits were two rounds, one candidate per round and at most six actual requests, with 6,000 output tokens per request, client retries zero and temperature omitted. Both candidates were executable and feasible on all cases. Recorded paired evaluation took 2.368 seconds and new trajectory collection 0.466 seconds, excluding development/editing time. The batch stopped after its two evaluated generations, without using the remaining request allowance.

Generation 1 adds an alternative-robot singleton-price penalty to the reference pair priorities. It changes the selected pair set on SPATIAL middle, but gives the **same repair and post-LS makespans on all 12 cases**. Generation 2 receives that actual result and repeated-completion evidence. It keeps the strongest first pair, then conditions the second choice on overlap with that first pair and slot conflict. It changes the selected set on three cases relative to its evaluated parent. Raw repair makespans remain identical; changed tie-quality route choices worsen post-LS by 3.7643 on BOTTLENECK early and 23.1891 on BOTTLENECK middle. Feedback therefore caused traceable policy and search behavior changes, but the paired evidence does not support incremental quality from the LLM.

Short ALNS comparisons use four instances × seeds 23/29, manual pool alone or the same pool plus one reference/generated kernel. Each group keeps spatial-sort initialization, enhanced SA, one-pass priced LS, destroy pool, initial weights 1, minimum-use exploration 1 and segment-4 independent adaptive roulette with existing shared 8/3/1 rewards. No pair-subset enumeration or forced portfolio enlargement was performed. Fixed 40 iterations and a separately predeclared nominal 2.4-second deadline provide different estimands; the latter includes cold worker startup and is checked between iterations. Native reference ranking has no IPC overhead, whereas generated ranking retains isolation. Fixed-iteration executor equivalence on the actual generated sources and a serialized reference control verifies that this execution boundary does not change decisions. Deployment retains the common default destroy fraction 0.25: the new R2/T20 and R4/T40 runs therefore remove 5 and 10 tasks, while their feedback states remove 4. This declared collection/deployment distribution difference, including longer greedy tails, limits transfer interpretation; it is not an uncontrolled between-group setting difference.

| Group (manual pool plus indicated member) | 40-iteration mean | 2.4-second mean | Fixed / timed kernel calls | Timed total iterations | Timed end-to-end seconds, 8 runs |
|---|---:|---:|---:|---:|---:|
| Manual only | 2347.238 | **2214.366** | 0 / 0 | 9215 | 19.496 |
| Deterministic reference | 2233.387 | 2243.327 | 109 / 1364 | 4574 | 19.542 |
| LLM generation 1 | **2225.800** | 2239.667 | 108 / 765 | 2397 | 19.538 |
| LLM generation 2 | 2236.418 | 2233.146 | 117 / 739 | 2274 | 19.580 |

All 64 solves were feasible, with zero strategy errors or repair fallbacks; every policy worker closed. Generation 1/2 made 873/856 actual isolated calls across both modes. Maximum observed per-kernel pricing was 2,409 slots, below 4,096; no run exhausted the search budget. Full per-member use, acceptance, best-improvement and time records are saved, so increased usage is not treated as complementarity. At fixed iterations, Route-DP calls were 3920 / 7536 / 7653 / 7876, respectively; equal iterations are not equal computation. Resident worker startup summed to about 1.30 seconds per generated timed group over eight solves, and per-call validation/import added 1.81 / 2.50 seconds. Maximum nominal-deadline overshoot was 98.57 ms. Setup/load/cleanup is included in the end-to-end columns; no tests ran concurrently with timing.

The aggregate hides a material structure difference. Timed SPATIAL seed results are manual `[3058,3120]`, reference `[3006,3017]`, and both generated policies `[3006,3061]`. On BOTTLENECK they are manual `[3027.048,3309.884]`, reference `[3255.721,3466.895]`, generation 1 `[3421.866,3227.473]`, generation 2 `[3405.086,3192.085]`. Generated improvements on one seed do not establish a stable LLM increment. The predeclared retention rule required a generated policy to improve both manual and reference timed means by at least one model-time unit; neither passed. Actual deployment remains the three manual repairs, with **no generated member**. Both sources remain archived and runnable through the new kernel.

**Historical decision, superseded 2026-11-03:** the previous bounded pair-search lineage proposed cached slot pricing as its next probe. The structural-population batch instead found an unbounded reconstruction-branch growth defect; the host now enforces the declared beam cap. The current next priority and evidence are recorded in the completed structural batch section and `operator_evolution.md`.

Focused verification passed **76 tests**, recorded in `verification.txt`. It covers exact joint routes against full Route-DP, budget enforcement, task coverage, input/RNG isolation, invalid IDs, timeout/runtime/source-drift cleanup, parser compatibility, actual generated-source cold/resident equivalence, fixed-iteration ALNS trace equivalence, and existing ALNS/executor regressions. All four local actual-candidate tests executed, with no artifact-related skips. No historical experiment system was rerun. `execution_notes.json` preserves the initial logging-only failure and subsequent test/reporting corrections; the algorithm, cases and budgets were unchanged during evaluation.

### Shared Pricing Cache and Pair-Ranking Opportunity Check (2026-11-01)

`incremental_route.py::insertion_costs` now reuses `insertion_cost_at` for each slot, in its original order. The same public implementation serves manual repair, bounded search and local search. `insertion_costs_uncached` retains the old vector evaluation using the same recurrence/table cache as a test reference. Price keys retain operation, route tuple, task ID and position; each evaluator owns its own immutable instance-specific matrix/states and caches. Existing capacities remain 256 route tables and 50,000 insertion/replacement price entries, with generational eviction; explicit cache clearing drops entries, not cumulative counters. No Route-DP recurrence or tie rule changed.

New instrumentation separates `insertion_requests`, `insertion_cache_hits`, `insertion_computations`, `table_builds`, `table_build_seconds` and `insertion_compute_seconds`. The insertion-only identity is requests = hits + computations; legacy `insertion_prices`/`price_cache_hits` remain mixed-operation counters and must not be relabeled as insertion-only work. `SearchBudget` still charges every logical slot, including hits. The six-task/two-pair pool, width 3/2, two completions per pair, 36 expansions and 4,096 logical prices were not enlarged.

**Semantic verification:** 36 paired cache/uncached controls (12 states × reference and two saved policies) preserve full ranking, selected pairs, materialized branches, retained/completed leaves, returned routes, makespan, post-LS results and logical requests. Four additional 12-iteration, no-deadline controls preserve solver traces. All 32 optimized 40-iteration deployment runs also match saved pre-cache trajectories/results. Actual computations and elapsed time are deliberately not required to match. Across the reference's 12 paired states including the same one-pass LS, requests stay **7,285**; hits rise **502 → 4,010**, actual insertions fall **6,783 → 3,275** (51.7%), table builds stay **360**, and measured insertion-compute time falls **0.1220 → 0.0590 seconds**. The generated controls show similar reductions; this is engineering reuse of exact work, not a new search capability.

**One frozen deployment recheck:** same four development instances, seeds 23/29, 40 iterations or nominal 2.4 seconds. Initialization, acceptance, LS, destroy pool, repair weights/exploration/rewards and search budgets are unchanged. All groups use the optimized shared pricer; generated policies still run in the checked resident executor. No tests or heavy agent jobs ran alongside timed solves. Each non-manual group contains the same three manual repairs plus exactly one indicated kernel, with no addition-subset sweep.

The table gives paired two-seed means; parentheses are differences from manual on the same instance (negative is better). These are consumed development inputs, not an independent check or a significance result.

| Fixed 40 iterations | Manual | Reference | Existing LLM 1 | Existing LLM 2 |
|---|---:|---:|---:|---:|
| BASE R2/T10 | 1292.000 | 1292.500 (+0.500) | 1292.500 (+0.500) | 1292.500 (+0.500) |
| HV-GEOM R2/T10 | 1308.000 | 1308.000 (0) | 1308.000 (0) | 1308.000 (0) |
| SPATIAL R2/T20 | 3148.500 | 3070.000 (−78.500) | 3073.500 (−75.000) | 3059.500 (−89.000) |
| BOTTLENECK R4/T40 | 3640.450 | 3263.049 (−377.402) | 3229.202 (−411.249) | 3285.672 (−354.779) |
| Eight-run mean | 2347.238 | 2233.387 | 2225.800 | 2236.418 |

| Nominal 2.4 seconds | Manual | Reference | Existing LLM 1 | Existing LLM 2 |
|---|---:|---:|---:|---:|
| BASE R2/T10 | 1292.000 | 1292.000 (0) | 1292.500 (+0.500) | 1292.500 (+0.500) |
| HV-GEOM R2/T10 | 1308.000 | 1308.000 (0) | 1308.000 (0) | 1308.000 (0) |
| SPATIAL R2/T20 | 3062.500 | 3036.500 (−26.000; −0.849%) | 3044.000 (−18.500; −0.604%) | 3033.500 (−29.000; −0.947%) |
| BOTTLENECK R4/T40 | 2880.225 | 2942.842 (+62.617; +2.174%) | 2963.985 (+83.760; +2.908%) | 3007.631 (+127.406; +4.423%) |
| Eight-run mean | **2135.681** | 2144.835 | 2152.121 | 2160.408 |

Individual seed results, percent/absolute differences, member calls/acceptances/improvements/shared rewards, actual DP/pricing work and source hashes are in `analysis.json` and raw `recheck/deployment_*.json`. Fixed iteration counts are not equal computation: reference uses 189,038 logical insertions and 7,536 full DP calls, versus manual 132,051 and 3,920 across eight runs. Timed iteration totals are manual/reference/LLM1/LLM2 **48,224 / 21,185 / 10,191 / 8,652**. Compared with the saved pre-cache timed run these are larger, but time-progress cooling means timed trajectories need not have identical prefixes; no controlled timing-speedup factor or monotonic quality claim is inferred from that comparison.

Timed kernel calls are **6,156 / 2,994 / 2,548** for reference/LLM1/LLM2; full per-member statistics remain available, so selection frequency is not labeled complementarity. Generated cold startup remains inside the solve budget: cumulative startup is **1.257 / 1.239 seconds** across eight runs; validation/loading outside solve is **0.0067 / 0.0097 seconds**, while per-call validation/import inside solve totals **3.291 / 4.478 seconds**. Mean subsequent isolated call latency is **1.311 / 1.989 ms**. End-to-end totals, including setup/loading/startup/cleanup, are manual/reference/LLM1/LLM2 **19.373 / 19.489 / 19.391 / 19.484 seconds**. The deadline is checked between iterations; maximum observed overshoot is **161.168 ms**, not a strict 2.4-second execution cap. All 64 solves are feasible, with no strategy errors/fallbacks, all workers closed and maximum kernel use 2,409 logical prices, below the unchanged cap.

**Ranking opportunity, before any new generation:** replaying the 12 states changes full rankings / selected sets / completed routes / post-LS makespans by **3 / 1 / 0 / 0** for reference → LLM1, and **5 / 3 / 2 / 2** for LLM1 → LLM2. The latter two objective changes are regressions, not gains. Both policies are called once before expansion. LLM2's second-ranked pair depends on the first-ranked pair's identity/features, **not** on the observed result of searching that pair.

The old timed records contain 2,868 kernel calls, of which **2,609 (91.0%) have only one eligible pair**. The fixed-iteration records have 177/334 such calls. The cached timed recheck has 10,918/11,698 (93.3%). There are no zero-candidate calls, multi-pair calls where the whole pool is searched, or budget-truncated prefixes in these records. These call-weighted percentages are dominated by throughput on small instances. One pair removes ranking freedom; it does not prove two-step branching is useless.

Before new outcomes, `diagnostic_states.json` fixed: first SPATIAL paired state with ranking choice, first BOTTLENECK paired state with choice, and first reference BOTTLENECK seed-23 deployment call with six pooled tasks. The diagnostic forces each existing pair through one-pair runs with the same per-pair beams, two retained leaves, incumbent/tail completion and one-pass LS. It examines **6 + 6 + 15 = 27 pairs**, not all subsets or all task pairs in the full instance. It consumes **30,033 repair-slot requests / 11,846 actual insertion computations**, plus separately logged LS work; summed enumeration LS time is 0.222 seconds and the whole diagnostic including normal-policy controls takes 2.122 seconds. This extra offline enumeration is excluded from deployment scores and never presented as a global optimum or improvement ceiling.

| Preselected state | Pair count | Distinct returned full routes | Reference post-LS | Best diagnosed post-LS | Diagnosed post-LS range |
|---|---:|---:|---:|---:|---:|
| SPATIAL early | 6 | 3 | 3628.000 | 3628.000 | 3628–3645 |
| BOTTLENECK early | 6 | 5 | 5144.355 | 5144.355 | 5144.355–5148.120 |
| BOTTLENECK first six-task-pool deployment call | 15 | 3 | 4109.292 | 4109.292 | 4109.292–4109.292 |

This is not evidence that every pair produces the same route. Retained-partial → distinct tail-completed-route counts are **12 → 6**, **12 → 11**, and **30 → 29**, respectively. The first state exhibits some tail coalescence; it cannot explain the largest state. There all 30 retained leaves use first-rank-zero insertion into robot 0 and leave robot 2's existing route `[33,40,4,16,34,2,5,11]` unchanged, at **4116.1534**. Of 180 expanded joint branches, 59 change that route, but none survives the exact-partial-objective leaf screen. The retained leaves already have identical makespan before tail completion. Tail completions mostly differ yet do not beat the greedy incumbent; all returned solutions reach 4109.292 after the same LS. This locates the observed insensitivity before the tail, in the retained action set's lack of influence on the binding route. It does **not** show that excluded tasks, pruned branches or a different completion would be valueless; those alternatives were not evaluated.

**Decision:** cache optimization is supported; two-step search retains useful evidence on SPATIAL, but its tested BOTTLENECK fixed-iteration advantage still does not survive equal time. LLM pair ranking adds no demonstrated independent benefit. No diagnostic state exposes a better post-LS pair missed by the reference, so the predefined revision gate is false: **0 new model requests, 0 new tokens, 0 new candidates**. Both existing LLM policies remain archived; neither is deployed. Actual deployment stays `greedy_insertion`, `regret_k_insertion`, `bottleneck_balancing_insertion`.

Stop this ranking lineage. The **single next priority** is a state-based **call/skip decision for optional two-step search**, motivated by retained insertions that cannot influence the current binding route and by the structure-dependent cost/benefit. Its proposed inputs are existing exact singleton/route-cost evidence and measured cost, not instance names; no rule is implemented or claimed validated yet. Do not simultaneously widen the pool, change first-step beams or evolve tail completion. Failure of the present ranking decision does not reject two-step search.

Focused verification passed **62 tests** in 5.98 seconds (`verification_final.txt`), including all saved-candidate tests without skips. `verification.txt` preserves a reporting-module syntax error discovered during final test collection; it was corrected before rerunning, with no change to search/pricing decisions or completed experiments. `analysis.json` is produced by a read-only `summarize` stage and contains source/artifact hashes. Historical outputs remain unchanged; no new development inputs, final/lockbox files, model calls, commit or push were used.

## Evidence Map

| Record | What it supports | Limit |
|---|---|---|
| E11/E12 | Development/validation screening and a small initial literature comparison; E11 freezes AUX as the Proposed candidate under its stated rule. | Screening sample is small; this does not provide confirmatory or test-set evidence. |
| E14 | Descriptive state-regret and route-cost instrumentation on its recorded reports. | Informative-position share is not an upper bound on possible algorithm improvement and is not an algorithm gain. |
| E16, E22, E23, E25 | Negative/inconclusive evidence for their specific cost-penalty, cost-aware selection, transfer-gain destroy, and decision-credit interventions. | Does not rule out every search-control or feedback design. |
| E17 | Small-sample candidate-quality comparison of `F1_scalar` and `F2_dataset`. | Candidate evaluation is not end-to-end deployment; repetitions and pairing limit inference. |
| E18 | Provenance, selection rule, and hashes for its separately frozen operator package. | Does not make E8/E11 identities equivalent to E18. |
| E19 | Mixed, small deployment differences between its compared frozen packages. | Eight pairs do not establish a reliable deployment benefit. |
| E20 | Headroom of the tested solutions under the tested neighborhoods. | Does not establish absence of all possible search-structure improvements. |
| E24 | Priced local search reduced measured local-search time and increased iteration throughput in its recorded setup; report retains its small A/B result. | The current runner does not explicitly disable `priced_local_search` in the `off` arm; see checks below. Do not treat its A/B result as a clean isolated ablation until this is resolved. |
| E25 | Decision-audit profiles under the tested fixed solutions/neighborhoods and a negative/inconclusive decision-credit comparison. | Repair audit does not replay the actual sequential insertion process/actual slot; its counters have narrower meaning than complete operator-decision optimality. |

These records are exploratory unless their own protocol and independent sample design support a stronger designation. No result should be silently discarded or promoted by changing its historical label.

## Verified Issues and Documentation Corrections

Statuses below were checked against the current tracked code at HEAD `101576fdf6d09313a932decbef48a4bc08a8e4e9`. They are documentation findings only; no source correction or re-experiment was made.

| Question | Status | Evidence and scope |
|---|---|---|
| E24 `off` arm explicitly disables `priced_local_search`? | **Still present** | `experiments/e24_priced_local_search_ablation.py::_solver` passes `{'priced_local_search': True}` only for `on` and passes `None` for `off`; `ALNSConfig.priced_local_search` defaults to `True` in `heuristics/alns_solver.py`. Thus both current arms can have it enabled. This threatens attribution of E24's on/off contrast; the historical output remains unchanged. |
| E25 repair audit replays the actual insertion sequence and prices the selected slot? | **Still present** | `heuristics/decision_audit.py::audit_repair` computes every removed task's best slot independently against the same partial routes/costs, infers assigned robot from the final repaired routes, and compares route choices. It does not replay the repair's sequential states or score the actual slot. Its hit/regret fields are per-task route-choice diagnostics under that approximation. |
| Destroy single-task marginal-saving top-k equals the jointly optimal removal set? | **Still present as a metric limitation** | `audit_destroy` computes each task's individual removal saving and ranks those values. For a fixed route, interactions among jointly removed tasks mean top-k individual savings need not minimize remaining route cost or maximize joint released cost. The metric is a single-task ranking reference, not a joint-removal optimum. |
| E25 `neither_rate` equals Pareto-dominated rate? | **Still present as a terminology risk** | `RepairDecisionAudit.summary()` counts decisions that hit neither the summed-route-cost optimum nor the projected makespan-optimal route. The report calls this “dominated placements”; this is not a full Pareto-front calculation over multiple objectives. Do not call it Pareto dominance. |
| E25 summary fields match recorder fields? | **Cannot confirm a mismatch; current names align** | `DecisionAuditRecorder._aggregate` emits `mean_makespan_hit_rate`, `mean_sum_hit_rate`, `mean_both_hit_rate`, `mean_neither_rate`, and regret means. `e25_decision_audit_ablation.py::_aggregate_audit` reads those same keys. Verify any concern against the exact historical output/version before asserting a mismatch. |
| E24/E25 used the E18 freeze identities? | **Still present as an identity distinction** | E11 `identities()` reads `outputs/e8_repair_portfolio/selection_decision.json`; E18 has a separate package under `outputs/e18_freeze_dp_evidence/`. E24/E25 call the E11 loader, so their deployed operator identity is the E11/E8 selection path, not automatically the E18 package. Inspect each run's recorded hashes before any cross-report comparison. |
| Bootstrap interval is for the reported median or mean? | **Still present as a reporting mismatch risk** | E24/E25 `_bootstrap` resamples raw paired deltas and computes `mean`; summaries separately report both `median_delta_rel` and `mean_delta_rel`, while report text may label the interval alongside the median. The interval estimates a resampled mean, not a median CI, and raw trial resampling does not implement the two-way run/family cluster procedure specified for confirmatory work. |
| Docs say destroy ignores bottlenecks and greedy repair ignores makespan? | **Claim is contradicted by code** | `ALNSSolver._geometry_aware_destroy` gives the current bottleneck route a 1.5 weight; `_bottleneck_route_destroy` selects the current bottleneck route; `_best_insertion_for_task(... objective="makespan")` compares projected makespan. Any blanket contrary claim in historical prose is stale. |

The open code concerns above are not fixed here. In particular, do not update historical output tables to simulate corrected runs. A future correction needs a separately scoped code task and, where attribution changes, a new output directory and rerun.

## Data and Split Status

`data/README.md` is authoritative for available sets and their use. In brief: `structural_benchmark_v1` has 84 development, 84 validation, and 168 locked test instances; E10 has 21 controlled single-scale development instances; the root set is an eight-instance legacy/smoke set; and R2 sanity artifacts have their own manifests. Same basenames can identify different files; join with dataset-qualified manifest identity/path/hash. R3 diagnostic-heldout use remains consumed and cannot serve as fresh confirmation.

The present documentation-only pass did not open test instance contents, run the final test, verify every instance hash, inspect all raw experiment records, or re-evaluate reported numerical summaries. See the source records for their original scope and reproduction details.
