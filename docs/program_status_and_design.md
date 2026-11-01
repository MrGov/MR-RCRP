# Program Status and Evidence Boundaries

This is the current factual status page. It describes the repository at the reviewed local HEAD and available records; it is not an authorization to run providers, experiments, or locked data. Historical reports and raw outputs are preserved as recorded.

## Implemented Solver

- The production loader reads the six-line instance format and requires `sweep_width sweep_speed travel_speed turning_time` on line 2.
- Each rectangle generates eight legal entry/mode states. `state_generator.py` implements sweep count, processing time, and parity-dependent exit corner.
- `CostMatrix` prices depot and between-task transfers as Manhattan distance divided by `travel_speed`.
- `RouteDPEvaluator` optimizes the state chain for a fixed ordered route; `MultiRobotSolutionEvaluator` enforces one route per robot and exactly-once task coverage, then returns makespan.
- B1 ALNS searches task assignment/order with manual and optional registered generated operators, simulated annealing, segment-reactive weights, local search, and task-scaled runtime configuration. The exact active controls depend on the experiment runner/config; do not treat B0, B1, E5 V1, V2, or later portfolio settings as interchangeable.
- The offline evolution subsystem has real LangChain/OpenAI-compatible provider integration, source validation/execution paths, candidate evaluation, feedback/revision, selection and source-hash records. This is not an online LLM solver.
- Four comparison algorithms (CDABC, RNSGA, SGA-TS, MRHDABC) are adapted implementations. Their Greedy and Exact search modes are distinct; the E13-Fix records document the fully greedy path and its smoke scope. Their literature fidelity and broad competitiveness have not been established by the small development comparisons.
- E8/E9 portfolio exploration found quality crossovers but no reliable overall PORT gain. E10 created a 21-instance single-scale structural set; E11 introduced the 336-instance structural benchmark with development/validation/test splits. The test split remains locked by protocol.

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
