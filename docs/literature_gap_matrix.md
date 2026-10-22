# R4 Literature Threat Matrix

Status: real-time verification completed. All novelty fields remain `NOVELTY_UNVERIFIED`.

Evidence uses the latest formal publication where available, otherwise latest arXiv full text or an author repository. Repository notes are not final evidence. `UNKNOWN` and `NOT VERIFIED` are retained when the source does not establish a field.

## Anchor Evidence

| Work / source location | Explicitly implemented evidence | R4 threat |
|---|---|---|
| FunSearch, Nature 625 (2024), DOI `10.1038/s41586-023-06924-6`; `google-deepmind/funsearch/implementation/programs_database.py` | Evaluator-scored executable programs, islands, score-weighted sampling, score-signature clusters, weak-island reset and elite founder copy | Direct evaluator-guided program evolution; no exact Route-DP feedback verified |
| EoH, PMLR 235:32201-32223 (2024), `proceedings.mlr.press/v235/liu24bs.html`, Sec. 3.1-3.4 pp. 3-4 | Thought plus code, population, E1/E2/M1/M2/M3 prompts, average fitness over instance set | Scalar/multi-round feedback baseline |
| ReEvo, NeurIPS 37 (2024), DOI `10.52202/079017-1381`, arXiv v3 Sec. 4 pp. 3-5 | Pairwise relative-performance reflection, accumulated long-term reflection, crossover and elitist mutation | Direct reflection threat; no exact DP response |
| LLaMEA, IEEE TEVC (2025), DOI `10.1109/TEVC.2024.3497793`, arXiv v4 Algorithm 1 pp. 3-5 | Complete algorithm code, runtime/error feedback, `(1+1)` or `(1,1)` evolution, best-so-far retention, fixed evaluation budget | One-shot and scalar/runtime feedback baseline |
| MCTS-AHD, arXiv `2501.08603v3`, Sec. 3 pp. 3-5 and official repository link p. 1 | Heuristic plus description in MCTS tree, UCT, progressive widening, mutation/crossover/path reasoning, underperformer retention | Search-organization threat |
| HSEvo, AAAI 2025, DOI `10.1609/aaai.v39i25.34898`, Sec. 3-4 pp. 3-5 | Code snippets, SWDI/CDI, flash reflection, random parent pairs, elitist mutation and Harmony Search; token/evaluation settings Table 1 p. 5 | Generic diversity/behavior threat |
| EoH-S, AAAI 2026, DOI `10.1609/aaai.v40i43.41038`, pp. 2-4 | Instance-performance vectors, Manhattan complementarity, complementary-aware search and greedy delta-CPI set construction; train/test and Nmax Table 1 p. 5 | Highest direct C2 threat; instance-performance complementarity is not our novelty |
| InstSpecHH, arXiv `2506.00490v3`, Sec. III-IV pp. 4-6 | Feature subclasses, subclass-specific evolution, neighbor search, online LLM/NN selector; query/time table p. 2 | Instance-conditioning and selector threat |
| HeurAgenix, arXiv `2506.15196v2`, Sec. 2.1/3.1 pp. 3-6; `microsoft/HeurAgenix` | Contrastive trajectory perturbation, critical-operation evidence, LLM evolution strategy, state-dependent selector, Devo/Dval | Contrastive feedback and selector threat |
| HiFo-Prompt, arXiv `2508.13333v2`, accepted-at-ICLR-2026 record, Sec. 3 pp. 2-5 | Insight Pool, Foresight Navigator, stagnation/diversity regimes, elite insight retention and utility credit | Persistent knowledge/control threat |
| LLM-Assisted Automatic Memetic Algorithm for LHJSV, IEEE TEVC (2026), DOI `10.1109/TEVC.2025.3556186`; DOI/Semantic Scholar abstract | LLM-assisted memetic algorithm, problem-decomposition prompts and feasible algorithm generation; other fields `NOT VERIFIED` | Lower direct threat; no unreported detail inferred |
| QUBE, arXiv `2412.20694v4`, Sec. 3-4 pp. 3-6 | Quality-uncertainty parent selection, identical-output clusters, island reset | Exploration/exploitation threat |
| Behaviour Space Analysis, arXiv `2507.03605v1`, Sec. 3 pp. 5-6 and conclusion p. 16 | Exploration/exploitation/convergence/stagnation metrics, code-evolution graphs and behavior trajectory networks; feedback integration explicitly future work p. 16 | Generic behavior-analysis threat |
| ReVEL, arXiv `2604.04940v3`, Sec. 3 pp. 4-7 | Normalized instance-performance profiles, CodeBLEU similarity, similarity/diversity groups, structured multi-turn feedback and elite Top-K | Highest generic structured-feedback threat |
| RouteRepair, arXiv `2609.11452v1`, Sec. 3.1-3.4 pp. 4-7 | Instance loss vectors, failure/strength/protection sets, diagnosis, targeted fixed-backbone repair and matched parent-child validation | Highest C3 threat; generic failure-aware repair is NOT our novelty |

## Field Reconciliation

| Field | Verified literature status | R4 treatment |
|---|---|---|
| Feedback | Scalar, rank, pairwise reflection, instance vectors, behavior grouping and failure sets are explicit | Only exact Route-DP response is potential differentiation |
| Representation | Programs, functions, thought+code, complete algorithms and fixed-backbone components are explicit | MR-RCRP destroy/repair representation alone is not a differentiation claim |
| Lineage/elite | Parent use and elitism are explicit in several anchors; durable auditable IDs often `UNKNOWN` | Require parent IDs and source-hash retention; no novelty claim |
| Behavior descriptors | HSEvo, Behaviour Space Analysis and ReVEL use generic descriptors | Use deterministic Route-DP state/mode/entry-exit/cascade/bottleneck descriptors |
| Complementarity | EoH-S explicitly implements instance-performance set design | Differentiate only by MR-RCRP regimes plus exact DP response; `POTENTIAL_DIFFERENTIATION - NOVELTY_UNVERIFIED` |
| Instance conditioning | InstSpecHH and HeurAgenix explicit | Constrained selection stage only; no novelty claim |
| Failure feedback | RouteRepair explicit | C3 optional; exact-DP structural counterexamples only |
| Deployment selector | InstSpecHH and HeurAgenix explicit; EoH-S deployment rule `NOT VERIFIED` | Deterministic structural selector; no online LLM default |
| Generalization | LLaMEA, EoH-S, InstSpecHH and Behaviour Space use train/test or unseen regimes | R3 diagnostic held-out is consumed; new validation/confirmatory splits required |
| Cost | Several anchors report query/evaluation budgets; comparable token accounting often incomplete | Equal calls, candidates, solver budgets, tokens and invalid/timeout costs required |

## Frozen Interpretation

`POTENTIAL_DIFFERENTIATION - NOVELTY_UNVERIFIED`: exact deterministic Route-DP response (state-switch fraction, H/V mode switches, entry/exit changes, indirect DP cascade, bottleneck relief, travel/coverage/turning response) used as structured feedback for offline MR-RCRP operator evolution.

All novelty claims remain `NOVELTY_UNVERIFIED`; no positive priority or benchmark claim is made.
