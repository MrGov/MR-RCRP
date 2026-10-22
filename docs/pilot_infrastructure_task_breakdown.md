# Pilot Infrastructure Task Breakdown

## 1. Planning status

This document decomposes future work only. Task checkboxes below are intentionally open. Closing a task requires separate implementation authorization, TDD evidence, and review. Gate P2 remains open.

## 2. Task dependency map

`PIM-* manifest contract → PIV-* validator → PIF-* fixtures → PIR-* runner → PIO-* observability/accounting → PCT-* candidate fixtures → PEV-* Gate P2 evidence`

No downstream component may recreate or weaken an upstream eligibility, scope, path, hash, or accounting decision.

## 3. A — Pilot manifest validator

### PIV-01: strict schema and scope validation

- **Purpose:** accept only a canonical pilot manifest with `manifest_scope=pilot_nonformal`, `matrix_scope=pilot`, literal `artifact_promotion_allowed=false`, fixed JSON types, and no unknown fields.
- **Inputs:** raw manifest bytes, approved pilot data root, approved pilot matrix/rule evidence, runtime validator identity.
- **Outputs:** canonical validation receipt or structured rejection receipt; never a partially trusted manifest.
- **Fail closed:** missing/wrong-type/unknown fields; formal scope; any final-test field; promotion allowed or ambiguous.
- **Future tests:** valid minimal manifest plus table-driven missing, wrong-type, unknown-field, and forbidden-scope cases.
- **Gate P2 evidence:** validator implementation/test receipt and rejection receipts.

### PIV-02: scoped hash verification

- Validate manifest hash, `pilot_family_matrix_hash`, `pilot_split_assignment_rule_hash`, record `file_hash`, and canonical record ordering.
- Recompute hashes from the same canonical bytes used for validation.
- Reject mismatch, unsupported algorithm, duplicate identity, or noncanonical serialization.

### PIV-03: path and duplicate boundary

- Resolve paths under an approved pilot root without parent traversal.
- Reject symlinks, aliases, paths outside the root, duplicate `instance_id`, duplicate `file_hash`, duplicate canonical path, and duplicate file identity when supported.
- If reliable file-identity inspection is unsupported, emit explicit evidence. It may be a documented pilot warning only; it cannot become formal evidence.

### PIV-04: validation receipts

- Produce validation receipt IDs as SHA-256 of RFC 8785 canonical receipt bodies excluding the ID and signature fields; bind explicit raw manifest bytes, the parsed manifest object, validator code snapshot, policy version, prevalidation/path evidence objects, and outcome.
- Hash domains are disjoint: receipt `manifest_hash = SHA-256(raw_manifest_bytes)`; optional `raw_manifest_bytes_hash`, when present, is an explanatory alias and must equal `manifest_hash`; `manifest_object_hash` is the canonical JSON object hash under the recorded canonicalization algorithm/version. Neither domain may be written into the other's field.
- The bounded T5 receipt slice accepts caller-supplied `raw_manifest_bytes: bytes` and `manifest_obj` only. It must not accept/read a manifest path, directory, glob, discovered input, or final-test location. Full path/raw-byte acquisition remains a later separately authorized I/O integration.
- Parse the supplied bytes with strict JSON rules and fail closed when parsing fails, canonical object hashing is unavailable, or the parsed object differs from `manifest_obj`. Bind `prevalidation_result.manifest_object_hash` and any path-result manifest/object evidence to the same `manifest_object_hash`.
- Receipt status is exactly `valid` or `rejected`. Even `valid` remains inert: `execution_authorized=false`, `gate_p2_closed=false`, no runner/scheduled/provider/candidate/pilot result fields, and no formal/final-test readiness claim.
- Preserve all rejection reasons; do not collapse distinct failures.
- This reconciled receipt contract requires a new receipt schema/version before production use. Existing v1 schema/integrity code is not silently reinterpreted; any production migration requires separate TDD authorization.

## 4. B — Pilot manifest fixture/generator

### PIF-01: pilot-only identity generator

- Generate only `pilot_nonformal` / `pilot` artifacts from approved `pilot_smoke`, `pilot_train`, or `pilot_dev` inputs. These labels are pilot-local and are not formal train/dev splits.
- Never create/read/infer final-test families, manifests, paths, hashes, or performance.
- Derive deterministic pilot IDs and hashes from the approved pilot-only matrix/rule.

### PIF-02: non-promotion metadata

- Set literal `artifact_promotion_allowed=false`, pilot identity version, and null formal source reference.
- Produce a pilot-artifact exclusion receipt for future formal preflight.
- Do not provide any function that relabels or exports a pilot artifact as formal.

### PIF-03: invalid manifest fixtures

- Prepare deterministic fixtures for wrong scope/type/hash, duplicate ID/file/path, traversal/symlink/alias, promotion attempt, glob input, and final-test reference.
- Fixtures remain planning/test artifacts and cannot be used as formal instances.

## 5. C — Manifest-only runner

### PIR-01: exact manifest entry point

- Accept one already validated pilot manifest reference plus its validation receipt.
- Do not accept directory, glob, wildcard, recursive discovery, or implicit default data path.
- Verify receipt binding again before scheduling work.

### PIR-02: pre-execution fail-closed preflight

- Reject scope/hash/objective mismatch, stale receipt, final-test field, formal scope, path/identity change, or uncontrolled discovery before provider invocation.
- Create a runner rejection receipt even when no run is scheduled.

### PIR-03: scheduled-run allocation

- Preallocate deterministic `scheduled_run_id` values for the approved method/operator-type schedule before provider invocation or generation.
- Preserve never-started, blocked, failed, and completed scheduled runs in accounting.

### PIR-04: runner receipt and no-leak proofs

- Preserve raw requested provider/input/scope/path intent separately from nullable accepted provider/input/scope/execution decisions.
- Bind exact manifest, code snapshot, runtime provider adapter, scheduled-run IDs, output allowlist, and status using a non-self-referential canonical receipt ID.
- Require schema-validated `no_real_llm_evidence`, `no_final_test_input_evidence`, `no_uncontrolled_glob_evidence`, `manifest_only_evidence`, and `scope_evidence` objects.

## 6. D — Scheduled-run accounting

### PIO-01: run/operator-type records

- Record `scheduled_run_id`, `evolution_run_id`, `method_condition`, provider, operator type, scopes, objective, run/operator-type statuses, deployment/freeze outcomes, deployable count, runtime authorization, and accounting category.
- `not_evolved` means not scheduled; `no_valid_operator` means scheduled with no eligible result. They are mutually exclusive.

### PIO-02: scheduled-run completeness

- Reconcile planned IDs against emitted run/operator-type records.
- Missing records fail accounting closure; they are not silently dropped.
- Report scheduled, started, candidate-producing, deployable, blocked, failed, and closed counts with explicit denominators.

## 7. E — Failure-zero accounting

### PIO-03: localized evaluation-cell mapping

- Map timeout, invalid solution, fallback, execution/deployment block, missing result, evaluator/runtime error, and no attributable generated result to zero generated relative improvement when they are localized generated-method cell failures.
- Retain original failure and attribution fields beside the policy value.

### PIO-04: integrity decision boundary

- Map objective/input/scope/hash/lockbox/baseline-pairing integrity violations to `batch_inconclusive`, never cell zero.
- Apply decision precedence before any numeric analysis value is created.

### PIO-05: aggregation and supplementary view

- Include every preregistered pilot replicate/seed cell in the policy aggregation.
- Exclude fallback makespan from generated attribution.
- Mark complete-case valid-cell output supplementary-only.

## 8. F — Mock/file candidate fixtures

### PCT-01: legal repair and destroy

- Deterministic, AST-valid, contract-valid, feasible operators with stable source hashes.
- Passing validation is not deployment authority.

### PCT-02: invalid returns

- Duplicate tasks, missing tasks, malformed routes/removed tasks, wrong task-ID types, and inconsistent destroy outputs.
- Expected structured contract/feasibility failure with no selection/freeze/reward.

### PCT-03: unsafe AST sources

- Cover forbidden imports/calls/reflection and ensure rejection before smoke test/import/benchmark.

### PCT-04: timeout source

- Deterministic long-running candidate intended only for a later authorized isolated timeout test.
- It must never be executed during Phase 6B planning.

### PCT-05: deployment-blocked frozen artifact

- Complete artifact evidence but missing current runtime deployment authorization.
- Expected deployment rejection, optional built-in fallback, and zero generated attribution/reward.

### PCT-06: provider-request rejection fixtures

- Prepare inert requests for real-provider config/adapter, unknown alias, artifact-claims-mock/runtime-real mismatch, and artifact-claims-real/runtime-mock-or-file deployment.
- Every fixture proves rejection or deployment block before provider invocation and records required evidence objects; no fixture contains credentials, endpoint access, or callable network code.

## 9. G — Pilot review artifacts

### PEV-01: evidence bundle layout

Plan a read-only bundle containing:

- manifest validation and rejection receipts;
- runner success/rejection receipts;
- scheduled-run registry and reconciliation report;
- candidate and evaluation-cell records;
- failure, fallback, deployment, and attribution summaries;
- code/schema/config/fixture hashes;
- no-final-test and no-glob proofs;
- pilot closeout and pilot-artifact exclusion receipt.

### PEV-02: review traceability

- Map every Gate P2 checkbox to one or more exact receipt IDs and test IDs.
- An absent, stale, malformed, or unverifiable receipt leaves the checkbox open.
- No checkbox is closed by a narrative assertion alone.

## 10. Future authorization slices

Recommended separately reviewable slices are:

1. schemas + validator RED tests;
2. validator GREEN + negative receipts;
3. pilot fixtures + runner RED tests;
4. runner GREEN + no-glob/no-final-test receipts;
5. observability/accounting RED tests;
6. accounting GREEN + replay/reconciliation;
7. candidate boundary fixtures and focused tests;
8. independent implementation review and Gate P2 evidence assembly.

Each slice requires explicit authorization. None is authorized or completed by this document.
