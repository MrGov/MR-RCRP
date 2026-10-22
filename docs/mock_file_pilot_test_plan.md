# Mock/File Pilot Test Plan

## 1. Planning-only status

These are future tests. None is implemented or executed in Phase 6B. No provider, candidate, benchmark, or pilot is run by this plan.

To avoid circular Gate P2 authorization, each scenario has two possible evidence tiers:

- **Pre-Gate component evidence:** uses inert fixtures, injected stored provider responses, or controlled executor-status doubles. It may test schemas, policies, orchestration, receipts, and accounting without invoking a provider or executing candidate code.
- **Post-Gate pilot evidence:** may invoke only the specifically authorized mock/file adapter or candidate boundary after Gate P2 is independently closed. It cannot be used as a prerequisite to justify its own authorization.

All tests use `pilot_nonformal` data only and must not create/read/infer final-test artifacts.

## 2. Common assertions

Every future test asserts:

- exact manifest-only input and bound validation/runner receipts;
- preassigned `scheduled_run_id` where a run is scheduled;
- run/operator-type, candidate, and cell records stay at their proper levels;
- missing/wrong-type safety evidence fails closed;
- invalid/unsafe/blocked/timeout/fallback results do not become generated success, reward, best, or frozen deployment;
- original statuses remain beside any failure-zero analysis value;
- outputs are `pilot_nonformal` and `non_formal_evidence=true`.

## 3. Planned scenario matrix

### T01 — Mock provider happy path

- **Purpose:** verify the complete legal lifecycle and receipt joins without making a performance claim.
- **Setup:** pre-Gate, inject a deterministic stored mock response containing one legal repair and one legal destroy; post-Gate variant may invoke the approved mock adapter.
- **Expected fields:** valid validator/runner receipts; scheduled run; `execution_status=execution_success`, `contract_status=contract_valid`, `feasibility_status=feasible_solution`, an explicit optimization status, eligibility decisions, freeze/deployment records, no fallback, and attributable success only when actually attributable.
- **Expected behavior:** pre-Gate orchestration test passes without provider/candidate execution; post-Gate path may reach structured completion. Makespan superiority is not asserted.
- **Gate P2 support:** fixture readiness, receipt joins, manifest-only runner, observability completeness.

### T02 — Mock provider all invalid / `no_valid_operator`

- **Purpose:** ensure scheduled evolution with no eligible candidate is not silently replaced by a template/fallback best.
- **Setup:** inject deterministic candidate-result fixtures whose candidates are all validation/contract invalid.
- **Expected fields:** run/operator-type `no_valid_operator=true`, `not_evolved=false`, deployable count zero; candidate-specific failures; no selection/freeze/reward; scheduled-run retained.
- **Expected behavior:** structured terminal scheduled failure; no generated operator deployed.
- **Gate P2 support:** fail-closed eligibility, no-valid semantics, scheduled-run accounting.

### T03 — File provider legal candidate

- **Purpose:** validate source/hash/AST/contract pipeline and deployment authorization separation.
- **Setup:** pre-Gate static fixture validation plus injected execution-success/contract-valid status; actual file-adapter/candidate execution only post-Gate.
- **Expected fields:** stable code hash, validation success, effective sandbox/runtime evidence, `execution_success`, `contract_valid`, `feasible_solution`, explicit `optimization_status`, selection/freeze eligibility, and deployment eligibility based solely on the current runtime gate.
- **Expected behavior:** static pre-Gate checks pass; no claim that validation grants deployment authority.
- **Gate P2 support:** legal fixture readiness, validator/executor boundary wiring, deployment-gate separation.

### T04 — File provider invalid candidate

- **Purpose:** verify malformed/duplicate/missing-task returns become structured invalid outcomes.
- **Setup:** deterministic stored return fixtures for duplicate task, missing task, malformed routes/removed tasks, and wrong task-ID type; execution result can be injected pre-Gate.
- **Expected fields:** validation may succeed and executable fixtures record `execution_status=execution_success`; `contract_status` independently records malformed/missing/duplicate/wrong-type/contract violation, while structurally valid but infeasible output records a feasibility failure such as `invalid_solution`; optimization is `not_evaluable`; no selection/freeze/deployment/reward/generated success.
- **Expected behavior:** no uncaught exception and no valid-candidate promotion.
- **Gate P2 support:** contract/feasibility boundary and non-attribution evidence.

### T05 — File provider unsafe candidate

- **Purpose:** prove dangerous source is rejected before import/smoke/benchmark.
- **Setup:** static source fixtures covering forbidden imports/calls/reflection; static validation is allowed as pre-Gate component evidence, but source is never executed.
- **Expected fields:** code hash, `validation_status=validation_failed`, `execution_status=validation_blocked`, contract/feasibility `not_evaluated`, optimization `not_evaluable`, structural diagnostic `unsafe_pattern_blocked`, all downstream eligibility false, and a rejection receipt.
- **Expected behavior:** no executor/provider/candidate call occurs.
- **Gate P2 support:** AST/static gate and rejection-receipt evidence.

### T06 — File provider timeout candidate

- **Purpose:** verify timeout status propagation and exclusion without running a long candidate before Gate P2.
- **Setup:** pre-Gate inject a controlled executor receipt with timeout status; post-Gate variant may execute the approved deterministic timeout fixture inside the authorized timeout-limited subprocess.
- **Expected fields:** `execution_status=timeout`, contract/feasibility `not_evaluated`, optimization `not_evaluable`, finite timing/timeout fields, captured/truncation/exit evidence as applicable, and no benchmark/best/freeze/deployment/reward.
- **Expected behavior:** pre-Gate orchestration consumes the injected status; actual timeout execution is post-Gate only.
- **Gate P2 support:** timeout plumbing and fail-closed downstream eligibility.

### T07 — Frozen deployment without runtime authorization

- **Purpose:** prove artifact metadata cannot authorize generated frozen deployment.
- **Setup:** frozen fixture with otherwise complete metadata/hash but no current runtime deployment authorization; do not execute candidate.
- **Expected fields:** deployment blocked, missing-runtime-authorization reason, fallback flag/reason if built-in fallback selected, generated success/reward false, no registered generated proxy.
- **Expected behavior:** structured fallback or rejection without solver initialization failure.
- **Gate P2 support:** runtime deployment gate and frozen-artifact boundary.

### T08 — Fallback attribution isolation

- **Purpose:** ensure built-in fallback output is not reported or rewarded as generated-operator success.
- **Setup:** injected repair-fallback, destroy-fallback, and joint ambiguous-attribution fixtures.
- **Expected fields:** `fallback_used=true`, non-empty reason, generated success/reward false for fallback component; joint ambiguity marked explicitly; cell policy value and raw fallback status separate.
- **Expected behavior:** fallback can preserve robustness but cannot enter generated top/best/freeze/reward semantics.
- **Gate P2 support:** research attribution validity and fallback observability.

### T09 — Scheduled-run accounting

- **Purpose:** prove all planned runs survive early failure and closeout reconciliation.
- **Setup:** schedule success, source-read failure, validation failure, no-valid, freeze failure, deployment block, and never-started/aborted fixtures.
- **Expected fields:** unique preallocated IDs, one terminal run/operator-type record per scheduled key, explicit counts/denominators, missing closeout detected.
- **Expected behavior:** no complete-case deletion or silent skip; `not_evolved` distinguished from scheduled failure.
- **Gate P2 support:** scheduled-run registry and closeout/replay evidence.

### T10 — Failure-zero cell mapping

- **Purpose:** enforce the unique localized-failure policy while keeping integrity contamination separate.
- **Setup:** injected cells for valid attributable result, timeout, invalid, fallback, deployment block, missing result, evaluator error, plus a manifest/hash integrity violation.
- **Expected fields:** localized failures use `cell_failure_mapping=failure_zero_policy`, value zero, primary inclusion true, raw failure retained; integrity violation uses `batch_inconclusive`, null value, primary inclusion false.
- **Expected behavior:** no cell-level complete-case deletion; fallback baseline result not attributed; supplementary eligibility independent of primary inclusion.
- **Gate P2 support:** accounting correctness, denominator stability, contamination boundary.

### T11 — Manifest-only runner rejects glob

- **Purpose:** prove uncontrolled file discovery cannot supply inputs.
- **Setup:** directory, wildcard, recursive-glob, omitted-manifest, and implicit-default input intents.
- **Expected fields:** runner `preflight_rejected`, no scheduled IDs, `no_uncontrolled_glob_evidence.glob_detected=true`, `decision=reject`, rejection reason and receipt, provider not invoked.
- **Expected behavior:** fail before scheduling/provider/candidate work; no fallback discovery.
- **Gate P2 support:** no-glob rejection and runner receipt evidence.

### T12 — Pilot runner rejects `formal_final_test`

- **Purpose:** prove pilot entry points reject formal/final-test scope before any access or execution.
- **Setup:** synthetic manifest header fixture with `manifest_scope=formal_final_test`; it contains no real final-test path, file, hash, family, or performance.
- **Expected fields:** validator/runner rejection receipt, no accepted records/scheduled IDs, final-test-scope rejection reason, no provider activity.
- **Expected behavior:** fail closed at scope validation. The synthetic header is not a final-test manifest and must not reference final-test data.
- **Gate P2 support:** no-final-test input boundary and scope rejection.

### T13 — Pilot artifact cannot be promoted to formal

- **Purpose:** enforce permanent non-promotion across metadata, copy/link/alias, and runner scope boundaries.
- **Setup:** synthetic attempts to change scope, set promotion true, populate formal source reference, reuse pilot identity/hash/path, or pass pilot artifact to a formal-entry validation double.
- **Expected fields:** structured promotion/identity rejection receipts; artifact remains pilot-only; no scheduled provider/candidate work.
- **Expected behavior:** every attempt fails closed; no relabel/copy/link helper succeeds.
- **Gate P2 support:** pilot/formal lifecycle isolation and exclusion-receipt readiness.

### T14 — Real-provider config requested

- **Purpose:** prove a real-provider runtime request cannot reach scheduling, adapter invocation, candidate generation, or network/API access.
- **Setup:** inert runner request naming a known real-provider adapter; no credentials, endpoint, network client, or provider callable is installed or invoked.
- **Requested fields:** `requested_provider` is the requested real adapter label, `requested_provider_kind=real`, `requested_input_mode=manifest_file`, and `artifact_claimed_provider=null`.
- **Expected receipt fields:** `accepted_provider=null`, `accepted_execution=false`, `rejection_reason=real_provider_forbidden`, empty scheduled IDs, and `no_real_llm_evidence.decision=reject` with the runtime adapter identity/classification.
- **Expected rejection point:** provider classification, before manifest scheduling and before provider invocation.
- **No-invocation proof:** injected adapter-call counter remains zero; event log contains no `provider_invoked`; receipt has no scheduled run or candidate ID.
- **Gate P2 support:** real-provider disablement, provider allowlist, no-real-LLM evidence object.

### T15 — Unknown provider alias

- **Purpose:** ensure misspelled, aliased, unregistered, or unsupported provider labels fail closed rather than falling back to mock/file.
- **Setup:** inert request using an unregistered provider alias with no callable attached.
- **Requested fields:** raw alias in `requested_provider`, `requested_provider_kind=unknown`, and otherwise valid pilot manifest intent.
- **Expected receipt fields:** `accepted_provider=null`, `accepted_execution=false`, `rejection_reason=unknown_provider`, `no_real_llm_evidence.decision=reject`, and empty scheduled/candidate IDs.
- **Expected rejection point:** provider classification, before manifest scheduling/invocation.
- **No-invocation proof:** provider registry lookup records no accepted adapter; invocation counter/event count is zero.
- **Gate P2 support:** unknown-provider fail-closed behavior and structured rejection receipt.

### T16 — Artifact claims mock/file while runtime provider is real

- **Purpose:** prove untrusted artifact metadata cannot disguise a real runtime adapter.
- **Setup:** artifact audit metadata claims `mock` or `file`; current inert runtime configuration classifies the requested adapter as real. No real adapter callable, credentials, or network access is supplied.
- **Requested fields:** `requested_provider_kind=real`, conflicting `artifact_claimed_provider=mock` or `file`, and manifest-only input intent.
- **Expected receipt fields:** `accepted_provider=null`, `accepted_execution=false`, `rejection_reason=provider_claim_mismatch`, `no_real_llm_evidence.decision=reject`, no generated-success/reward attribution.
- **Expected rejection point:** provider-claim consistency gate, before scheduling/invocation.
- **No-invocation proof:** zero adapter-call count, no provider/candidate lifecycle event, empty scheduled IDs.
- **Gate P2 support:** artifact/runtime provenance separation and real-provider non-invocation.

### T17 — Artifact claims real while runtime permits only mock/file

- **Purpose:** ensure a generated/frozen artifact's real-provider claim cannot obtain deployment authority from a mock/file runtime or artifact metadata.
- **Setup:** hash-valid inert frozen artifact claims a real provider; current runtime allowlist contains only mock/file and has no separate generated-artifact deployment authorization.
- **Requested fields:** current runtime `requested_provider_kind=mock` or `file`, `artifact_claimed_provider` names a real provider, and deployment intent references the inert frozen artifact.
- **Expected receipt fields:** current adapter may remain identified for audit, but `accepted_execution=false`, deployment is blocked, primary reason is `runtime_authorization_denied`, fallback is allowed only with `fallback_used=true` and isolated attribution, and generated success/reward remain false.
- **Expected rejection point:** frozen deployment authorization gate, before importing/calling the artifact.
- **No-invocation proof:** frozen proxy/import/call counters remain zero; only a deployment-block/fallback event may appear.
- **Gate P2 support:** current-runtime deployment authority, provider-claim non-authority, fallback non-attribution.

## 4. Traceability and execution order

Future implementation must assign each of T01–T17 a stable test ID, schema/policy version, fixture hash, expected receipt IDs, and Gate P2 checklist reference. The order is:

1. write RED component tests using inert/injected inputs;
2. observe intended failures;
3. implement minimum component behavior under separate authorization;
4. run focused and regression tests;
5. perform independent implementation review;
6. assemble pre-Gate evidence and review Gate P2;
7. only after explicit Gate P2 authorization, run the post-Gate mock/file pilot variants.

No test result from these scenarios supports method performance, generalization, cost superiority, formal evidence, or final-test claims.
