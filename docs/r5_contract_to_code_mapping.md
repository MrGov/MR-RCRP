# R5 Contract-to-Code Mapping

Status: R5 implemented; R5R provenance/trust repair complete and awaiting independent R6 re-review.

R5 uses a new trusted-fixture-only pipeline. The existing `candidate_loader.py`,
`CandidateProxy`, and legacy file provider remain outside the R5 execution path
because they support Python source loading/execution. R5 fixture providers return
references and structured metadata only.

| R4 concept | Current implementation / evidence | Missing R5 implementation | Target |
|---|---|---|---|
| `OperatorBehaviorProfile` | R3 exposes related functions in `experiments/r3_diagnostics.py`; legacy `metrics.py` only has scalar summaries | Versioned typed profile with exact-DP, assignment/bottleneck, objective, reliability and cost fields | `llm/operator_evolution/r5_mock_pipeline.py` |
| `StructuredOperatorFeedback` | `feedback_builder.py` emits scalar top/weak rows | Versioned F0/F1/F2/F3 payloads with explicit evidence isolation | `r5_mock_pipeline.py` |
| Feedback modes | Legacy loop always uses one scalar/top-weak payload | Deterministic mode switch with DP evidence only in F2/F3 and counterexamples only in F3 | `r5_mock_pipeline.py` |
| Lineage / elite retention | Legacy rows have round metadata; no trusted archive lineage contract | Parent binding, generation IDs and persistent elite records | `r5_mock_pipeline.py` |
| `OperatorArchive` | Legacy JSON/CSV round outputs are not a versioned archive | Stable IDs, source hashes, profile, reliability, regime and eligibility state | `r5_mock_pipeline.py` |
| Eligibility / quality floor | `eligibility_policy.py` targets generated-artifact execution | R5 pure metadata gate for invalid/infeasible/timeout/fallback/contract/runtime and split quality floor | `r5_mock_pipeline.py` |
| Lexicographic C2 selection | `evolution_loop.py` selects scalar best only | Six-stage Option A selection, K=1..4, structural coverage then DP tie-break | `r5_mock_pipeline.py` |
| Selection trace | No stage-by-stage audit trace | Deterministic rejection/selection trace | `r5_mock_pipeline.py` |
| Deployment P0/P1/P2 | Existing freezing is artifact/deployment oriented | Research-ready single-best, uniform/random and structural selector over trusted records | `r5_mock_pipeline.py` |
| C3 counterexample | No R5 structured failure schema | Typed failure axis/payload with C0-C3 variants | `r5_mock_pipeline.py` |
| Split discipline | R2 manifest loader is split-scoped but current sanity splits include consumed R3 held-out | New explicit evolution-development/selection-validation/confirmatory-heldout manifests; final-test excluded | `r5_mock_pipeline.py` and R5 tests |
| Budget ledger | Legacy loop records partial runtime/evaluation fields | Versioned equal-budget ledger with run/generation hierarchy | `r5_mock_pipeline.py` |
| Yield metrics | Legacy evaluator returns per-candidate rows | syntax/contract/feasible/deployable/quality-conditioned yields | `r5_mock_pipeline.py` |
| Mock provider | Existing provider emits Python source drafts | Trusted fixture references keyed by generation/parent/mode | `r5_mock_pipeline.py` |
| File provider | Existing provider reads `.py` files and may feed source execution | Trusted JSON fixture manifest or dry-run parser; no dynamic import | `r5_mock_pipeline.py` |

R5 does not modify the core model, Route-DP recurrence, objective semantics,
solution-feasibility contract, pilot infrastructure, or final-test data.
