# Gate P2 Pilot-Execution Plan

## 1. Authority boundary

Gate P2 is the future authorization gate for actually running a mock/file pilot. This document plans Gate P2; it does not close it.

- Gate P1 permits planning only.
- Gate P2 is required before mock/file provider execution, candidate smoke tests, benchmarks, or pilot runs.
- Gate B remains separately required for formal experiments.
- Phase 7 remains separately required for real LLM/provider use.
- Gate P2 never permits final-test access or formal evidence claims.

Current lifecycle authority is:

1. Phase 6A planning has passed independent review.
2. Gate P1 authorizes planning work only.
3. Phase 6B implementation planning has received Required revisions and the Phase 6B-R protocol repair is awaiting independent planning review.
4. If Phase 6B-R review passes, the next possible action is a separately authorized implementation task, not pilot execution.
5. Implementation task authorization does not close Gate P2 and does not authorize provider/candidate execution.
6. Gate P2 remains open until the machine-auditable implementation/test/review evidence below is complete and separately approved.
7. Gate B remains independent, incomplete, and required for every formal experiment.

## 2. Required Gate P2 evidence

Every item must have machine-readable or reviewable evidence before pilot execution.

### 2.1 Pilot data identity

- [ ] Pilot-only family matrix is frozen before any pilot instance generation.
- [ ] Pilot-only split rule is frozen before any pilot instance generation.
- [ ] Canonical `pilot_family_matrix_hash` and `pilot_split_assignment_rule_hash` are recorded.
- [ ] Pilot manifests are `manifest_scope=pilot_nonformal`, `matrix_scope=pilot`, and `artifact_promotion_allowed=false`.
- [ ] All pilot artifacts are labeled non-formal and have a planned exclusion receipt.

### 2.2 Manifest and runner boundary

- [ ] Pilot manifest schema and fail-closed validator are implemented, tested, and represented by hash-verifiable receipts.
- [ ] Manifest-only pilot runner has an explicit execution path.
- [ ] Runner verifies exact allowlist and actual-input equality.
- [ ] Uncontrolled glob/discovery cannot supply pilot inputs.
- [ ] Runner rejects formal scopes and `formal_final_test`.
- [ ] Missing/wrong-type/unknown fields, hash mismatch, unsafe paths, aliases, duplicate bytes/IDs, and invalid scope fail closed.

### 2.3 Final-test isolation

- [ ] Pilot workspace contains no final-test manifest, files, hashes, family matrix, family IDs, or performance data, or access controls make them unavailable.
- [ ] Pilot configuration/parser rejects final-test fields and paths.
- [ ] Review confirms no prompt, fixture, provider input, report, or receipt can infer final-test composition.

### 2.4 Provider and fixture approval

- [ ] Mock-provider deterministic batch plan is approved.
- [ ] File-provider legal candidate is approved.
- [ ] File-provider invalid/contract-violation candidates are approved.
- [ ] File-provider unsafe candidates and their non-execution expectations are approved.
- [ ] Frozen generated deployment-blocked fixture is approved.
- [ ] No fixture calls a real provider or relies on final-test data.

### 2.5 Eligibility and attribution

- [ ] Unified execution/benchmark/selection/freeze/deployment eligibility policy is used by the planned path.
- [ ] Invalid, unsafe, timeout, blocked, fallback, and missing-evidence candidates fail closed.
- [ ] `no_valid_operator` and `not_evolved` are distinct.
- [ ] Runtime deployment authorization is current-runtime evidence, not artifact self-claim.
- [ ] Fallback cannot produce generated success or generated reward.
- [ ] Joint attribution ambiguity is explicitly recorded and unrewarded.

### 2.6 Accounting and observability

- [ ] `scheduled_run_id` is created before candidate generation.
- [ ] Scheduled failures remain in run accounting.
- [ ] Failure-zero policy fields and original failure states are both recorded.
- [ ] Candidate, execution, freeze, deployment, fallback, attribution, cell, and run fields satisfy the observability plan.
- [ ] Pilot reports are labeled non-formal and prohibit paper performance claims.

### 2.7 Verification and review

- [ ] Relevant pytest suite is separately authorized and passes at the future pre-execution review; Phase 6A/6B planning does not run it.
- [ ] Manifest/runner/fixture/observability implementation review has no Critical or Required findings.
- [ ] Gate P2 receives explicit execution authorization after evidence review.
- [ ] Real LLM/provider remains disabled.
- [ ] Formal, large-scale, and final-test execution remains disabled.

## 3. Gate outcome states

| Outcome | Meaning | Authorized next action |
|---|---|---|
| `planning_only` | Phase 6A planning passed; Phase 6B specification/review or implementation evidence remains incomplete | Repair/review Phase 6B, or after approval request a separate implementation task authorization only |
| `implementation_task_authorized` | One bounded implementation task is explicitly authorized; Gate P2 evidence remains incomplete | Implement/test only that task; no provider/candidate/pilot execution |
| `gate_p2_blocked` | One or more required evidence items fail or are absent | Fix/review; no pilot execution |
| `gate_p2_ready_for_review` | Evidence assembled, but no authorization yet | Independent Gate P2 review |
| `gate_p2_authorized_mock_file_only` | Review passes and explicit authorization is recorded | Execute only the approved pilot cases |
| `pilot_suspended` | Isolation, integrity, or attribution violation occurs | Stop pilot and audit; do not promote results |

No state in this table authorizes a real provider, formal experiment, large-scale run, or final-test access.

## 4. Planned stop conditions

Future pilot execution must stop and retain evidence if:

- any final-test artifact becomes present or accessible;
- the runner falls back to glob/discovery;
- manifest scope/hash/identity validation cannot be completed;
- an unsafe candidate reaches execution;
- a fallback is attributed as generated success/reward;
- scheduled failures are dropped;
- pilot artifacts are proposed for formal promotion;
- an unapproved provider or runtime authorization path is used.

Stopping is an integrity outcome, not a performance result.

## 5. Current status

Current Gate P2 status is `planning_only`. Phase 6A planning has passed, and the Phase 6B-R protocol repair is awaiting independent implementation-planning review. None of the checkboxes above is closed by writing or revising these documents. If that review reports no Critical/Required findings, the next possible action is a separate, bounded implementation task authorization. It is not Gate P2 closure and does not authorize provider invocation, candidate execution, or pilot execution.

## 6. Phase 6B machine-auditable closure evidence plan

Phase 6B planning is now authorized, but this section remains a future closure checklist. Every item is open. Narrative completion claims cannot substitute for receipts, test evidence, hashes, or independent review.

### 7.1 Approved planning and implemented boundaries

- [ ] Phase 6B implementation plan has passed independent planning review with no Critical/Required findings.
- [ ] Strict pilot manifest validator is implemented through TDD and independently reviewed.
- [ ] Pilot-only manifest fixture/generator is implemented through TDD and cannot create or infer final-test artifacts.
- [ ] Manifest-only pilot runner is implemented through TDD and fails closed on absent/stale validation evidence.
- [ ] Uncontrolled glob, directory discovery, implicit default input, and secondary-manifest fallback are rejected by tests.
- [ ] Pilot runner rejects formal/final-test scopes before provider, candidate, scheduling, or file access.
- [ ] Real and unknown provider requests plus both artifact/runtime provider-mismatch directions are rejected or deployment-blocked before invocation/import/call.
- [ ] Pilot artifact promotion/relabel/copy/link/alias/reuse attempts are rejected.

### 7.2 Candidate and accounting readiness

- [ ] Legal repair/destroy, invalid return, unsafe AST, timeout-status, deployment-blocked frozen, and fallback-attribution fixtures are prepared with deterministic hashes.
- [ ] Three-level observability schema is implemented: run/operator-type, candidate, and evaluation-cell records.
- [ ] Scheduled-run IDs are allocated before provider/generation activity and reconcile to terminal records.
- [ ] Failure-zero, batch-inconclusive, fallback non-attribution, and supplementary complete-case rules are implemented and tested.
- [ ] `not_evolved` and `no_valid_operator` remain mutually exclusive and are stored at run/operator-type level.

### 7.3 Required receipt bundle

- [ ] Valid pilot manifest validation receipt is generated and hash-verifiable.
- [ ] Rejection receipts cover schema/type, scope, hash, path, duplicate, promotion, glob, and synthetic final-test-scope cases.
- [ ] Runner preflight receipt binds the exact validation receipt, manifest, code snapshot, objective, provider allowlist, scheduled IDs, and output allowlist.
- [ ] Required evidence objects `no_real_llm_evidence`, `no_final_test_input_evidence`, `no_uncontrolled_glob_evidence`, `manifest_only_evidence`, and `scope_evidence` are implemented, schema-validated, hash-bound, and tested.
- [ ] Scheduled-run reconciliation, failure, fallback, deployment, attribution, and accounting summaries are generated and replayable without provider/candidate execution.
- [ ] Pilot closeout and pilot-artifact exclusion receipts are generated.

### 7.4 Verification and authorization

- [ ] Pre-Gate component evidence uses inert fixtures or injected statuses and does not invoke a provider or execute candidate code.
- [ ] Focused and full regression tests pass under a separately authorized implementation phase.
- [ ] Implementation review reports no Critical or Required findings.
- [ ] Evidence IDs/hashes are mapped one-to-one to all Gate P2 checklist items.
- [ ] A separate Gate P2 review approves the evidence.
- [ ] Explicit pilot execution authorization is provided after Gate P2 review.

Actual mock/file provider or candidate execution is **post-Gate evidence** and cannot be used circularly to authorize the initial gate. Gate P2 still does not authorize real providers, formal experiments, large-scale execution, or final-test access.

Gate P2 closure evidence must include implemented-and-tested manifest validator receipts, runner receipts, rejection receipts, all five required evidence objects, reviewed mock/file/provider-boundary cases, and an implementation review with no Critical/Required findings. Until then pilot execution remains forbidden. Gate B remains separately incomplete.

Planned evidence contracts are defined in:

- `docs/phase6b_implementation_plan.md`;
- `docs/pilot_infrastructure_task_breakdown.md`;
- `docs/pilot_observability_schema.md`;
- `docs/pilot_manifest_validator_spec.md`;
- `docs/pilot_runner_receipt_spec.md`;
- `docs/mock_file_pilot_test_plan.md`.

Writing or approving those planning documents does not close any checkbox above.
