# E12 literature baselines — adapted implementations

All four solvers minimize the same Exact Route-DP makespan and return complete
`MultiRobotSolution` routes. They have independent search loops. `common.py`
contains evaluation bookkeeping, elementary moves, construction and permutation
utilities only. It does not contain ALNS or a shared population search loop.
Every complete candidate is validated by the existing solution evaluator.
Makespan is always primary; total route duration only breaks exact ties.

| Source / inspected sections | Retained mechanisms | MR-RCRP adaptation / approximation |
|---|---|---|
| CDABC, Guo et al., Knowledge-Based Systems 289 (2024) 111474, §4.1–4.7, Procedures 1–10, PDF pp.4–7 | Dominant work/travel and processing-time seeds; random population; load-dependent shuffled insertion/exchange strategies; tournament critical onlookers; two collaborative followers per source; follower-guided scouts; independent global elite | Agricultural work replaced by minimum H/V state processing time. All costs are Exact-DP. Bounded first/best insertion steps replace repeated neighborhood exhaustion. Population 12 rather than original 130; `rcal=0`, scout limit 50. |
| RNSGA, Chen et al., IEEE T-ITS 26(8), 2025, §IV, Algorithm 1, Figs.3–7, PDF pp.5–8 | Cluster/nearest-task initialization; ISA discrete route GA with success-adaptive PMX/order/subtour crossover; endpoint-block MTC→LTC balancing; PBOM N1/MTC,N2/LTC,N3/random using spatial/load ranks; genetic permutation/breakpoint allocation; diverse elite archive | Original Algorithms 2–7 are in supplementary §S-II, absent from supplied PDF. Main-text descriptions guide approximate subroutines. L1 Lloyd clustering substitutes unspecified clustering. One route/robot; capacity-induced trips removed. Route duration substitutes energy only in neighbor ranking. No energy objective or Pareto claims. |
| SGA-TS, Seo & Lee, Robotics and Autonomous Systems 205 (2026) 105664, §4, Algorithms 2–3, Table 5, PDF pp.6–11 | One greedy seed plus random chromosomes; inverse-makespan roulette; fixed-half crossover with duplicate repair and inherited route counts; swap/reverse/count mutations; deterministic path-aware TaskShift; 5% elite preservation | JPS cells replaced by shortest-Manhattan-corridor proximity to actual DP exit/entry route segments, including depot return; corridor excess ≤2×sweep_width. Only current-bottleneck tasks may move to lower-load receivers at encountered segment positions. Because coverage service costs vary, an additional Exact-DP nonworsening/tie-duration guard is used. This is a material, explicit adaptation. |
| MRHDABC, supplied ABC-Bi.pdf, §4.1–4.6, Algorithms 1–7, Fig.4, PDF pp.13–20 | MRNEH seed; ~¼ MRNEHIG, ~¼ IG, remainder random; six SR/MR insert/exchange/cross neighborhoods; ordinary employed search; binary tournament critical onlookers; multi-operator scouts; random/guided restart; critical route load balance | Homogeneous robots; no permissions/capacity/multiple-trip constraints. Intrinsic angular task groups substitute farming regions. The paper does not give an explicit MR priority formula: use normalized minimum H/V work plus depot travel with 10% perturbation. MRNEH chooses among three least-loaded robots. Original reference parameters PS=80, λ=150, β=5; use PS=12 for the same small wall-time budget, retain λ=150 and β=5. |

Common initial population size is 12 to allow effective search under the shared
`max_time=task_count` budget with Python Exact-DP. This is a development starting
configuration, not a claim of reproducing the authors' calibrated parameters.
SGA mutation/TaskShift probabilities and elite fraction are each 0.05. RNSGA ISA
depth is 8. The time clock includes state/matrix setup, population construction
and online search; termination is checked inside stages and between atomic moves.
All algorithms retain an independent global incumbent. Fixed-generation runs are
used to test deterministic replay; timed runs naturally complete different numbers
of evaluations as machine load varies.

The exact supplied PDFs and implementation files are hashed in the E12 output
configuration. No author-code reproduction, original-domain result reproduction,
or formal performance claim is implied by this adapted implementation.

## E13 evaluation and time control

The E12 descriptions above describe the default `evaluation_mode='exact'`.
Every solver also accepts `SearchConfig(evaluation_mode='greedy')`. All route
ranking, insertion and ISA calls use the configured evaluator. TaskShift uses
the corresponding evaluator's actual legal entry/exit states. Greedy selects
each state by incoming Manhattan travel plus processing time, and includes the
return to depot when choosing the final task's state. It never optimizes a DP
state chain during search.

Both modes independently re-evaluate only the search-selected incumbent using
Exact Route-DP after search. `best_evaluation` is this final exact result;
`search_makespan` and `history` use the configured search costs. No exact recheck
is used to reselect a historical greedy candidate. `runtime_seconds` is setup
plus search, `final_recheck_seconds` is independent verification, and
`total_runtime_seconds` includes both. Search and final DP counters are separate.

The shared deadline exception unwinds nested search before another route
evaluation can start, retaining the last complete feasible incumbent. One
mandatory complete spatial-sort bootstrap ensures a result even for a budget
smaller than setup; that exceptional overrun is explicitly reported. A single
route evaluation already in progress may finish. Each literature solver retains
its independent population and search logic. E13 measurements and reproduction
commands are under `outputs/e13_evaluation_efficiency/`; E12 results are retained.
