# Phase 6B Implementation Planning

## 1. Authority and scope

Phase 6B is **implementation planning only**. It converts the approved Phase 6A closed-loop design into small, reviewable, testable, and separately authorizable engineering work packages.

Phase 6B:

- does not implement or modify production or test code;
- does not close Gate P2;
- does not execute mock, file, or real providers;
- does not execute a pilot, benchmark, solver, or experiment;
- does not create, read, hash, locate, or infer final-test manifests, files, family matrices, identities, features, or performance;
- does not produce paper performance evidence.

Its outputs are engineering task specifications for a later, separately authorized implementation phase. Approval of these documents permits planning review only; it does not authorize implementation or Phase 6C.

## 2. Planned engineering outcome

A future implementation, if separately authorized, will provide a pilot-only, fail-closed, manifest-driven mock/file closed loop with:

1. strict `pilot_nonformal` manifest validation;
2. pilot-only fixture and manifest generation;
3. a manifest-only runner with no uncontrolled discovery or glob fallback;
4. preassigned scheduled-run accounting;
5. separate run/operator-type, candidate, and evaluation-cell records;
6. localized failure-zero accounting without fallback attribution;
7. deterministic legal, invalid, unsafe, timeout, and deployment-blocked fixtures;
8. machine-auditable validation, rejection, runner, accounting, and isolation receipts;
9. an evidence package for an independent Gate P2 review.

None of these capabilities is claimed as implemented in Phase 6B.

Receipt implementations must preserve requested audit data separately from accepted decisions, require named evidence objects, and derive receipt IDs from RFC 8785 canonical bodies excluding the ID/signature fields. Real/unknown provider requests and provider-claim/runtime mismatches are explicit fail-closed negative paths.

## 3. Work-package sequence

| Order | Work package | Planning output | Future authorization boundary |
|---:|---|---|---|
| 1 | Schema foundations | Canonical pilot manifest and three-level observability contracts | Schema implementation and schema tests |
| 2 | Validator boundary | Input/output, hashing, path, duplicate, scope, and receipt rules | Validator implementation through TDD |
| 3 | Pilot-only fixture generation | Deterministic identities, hashes, non-promotion metadata, negative fixtures | Fixture/generator implementation through TDD |
| 4 | Manifest-only runner | Exact allowlist, preflight, scheduled runs, no-glob/no-final-test proofs | Runner implementation through TDD |
| 5 | Accounting and observability | Append-only events, run/candidate/cell rows, failure-zero and batch-inconclusive rules | Storage/accounting implementation through TDD |
| 6 | Mock/file boundary fixtures | Legal, invalid, unsafe, timeout, deployment-blocked and fallback cases | Fixture code only; no provider execution until Gate P2 |
| 7 | Receipt and replay checks | Validation/runner/rejection/accounting receipts and deterministic replay plan | Receipt implementation and read-only replay tests |
| 8 | Gate P2 evidence assembly | Traceability matrix from evidence to Gate P2 checklist | Independent review; no execution authorization implied |

Dependencies are one-way: runner work depends on manifest validation; accounting depends on scheduled-run identity; deployment evidence depends on eligibility and receipt schemas. A later implementation review must reject shortcuts that bypass these dependencies.

## 4. Design invariants

### 4.1 Pilot/formal isolation

- Pilot inputs use `manifest_scope=pilot_nonformal` and `matrix_scope=pilot` only.
- Pilot matrix and split-rule hashes are pilot-scoped.
- `artifact_promotion_allowed` is literal `false`.
- Pilot artifacts cannot be promoted, relabeled, copied, linked, aliased, or reused as formal artifacts.
- Formal scopes, especially `formal_final_test`, are rejected before provider or candidate activity.
- No future pilot record may contain final-test identifiers, paths, hashes, family information, or derived information.

### 4.2 Fail-closed execution

- Missing, malformed, wrong-type, inconsistent, or unverifiable evidence rejects the affected action.
- There is no uncontrolled glob, directory scan, or fallback input discovery.
- Artifact claims never create runtime execution or deployment authority.
- Unsafe, invalid, timeout, blocked, fallback, or unattributed results cannot be selected, frozen, rewarded, or counted as generated success.

### 4.3 Research accounting

- A `scheduled_run_id` is allocated before provider invocation or candidate generation.
- A scheduled failure remains in accounting.
- Localized generated-method evaluation failure maps to zero improvement only under the frozen policy estimand and retains its original status.
- Batch/input/manifest integrity contamination is `batch_inconclusive`, not a cell zero.
- Fallback output is never attributed as generated-method improvement.
- Complete-case valid-cell analysis is supplementary only.

## 5. Future implementation checkpoints

Every work package must later follow RED → GREEN → focused regression → full regression → independent review. Phase 6B defines those checks but performs none of them.

Minimum checkpoints are:

1. schema examples and negative examples reviewed;
2. failure-state and denominator semantics reviewed;
3. RED tests observed failing for the intended reason;
4. minimal implementation authorized and completed;
5. focused tests and full suite pass;
6. receipts generated from mock/file-only evidence;
7. no Critical/Required review findings;
8. explicit Gate P2 review and separate execution authorization.

## 6. Planned artifacts

- `docs/pilot_infrastructure_task_breakdown.md`
- `docs/pilot_observability_schema.md`
- `docs/pilot_manifest_validator_spec.md`
- `docs/pilot_runner_receipt_spec.md`
- `docs/mock_file_pilot_test_plan.md`
- updated Gate P2 evidence references in `docs/pilot_execution_gate_plan.md`

Future implementation artifacts and proposed code paths are described only as plans. They do not exist merely because they are named here.

## 7. Phase 6B exit criteria

Phase 6B planning is complete only when:

- every infrastructure task has purpose, dependency, output, failure behavior, acceptance evidence, and Gate P2 mapping;
- the three record levels and their ownership are unambiguous;
- validator and runner receipts have canonical, fail-closed contracts;
- all 17 required mock/file/provider-boundary test scenarios have expected receipts and accounting outcomes;
- Gate P2 future evidence is listed without marking it complete;
- an independent Phase 6B planning review finds no Critical or Required issue.

Completion does not authorize implementation, provider invocation, pilot execution, formal work, or final-test access.
