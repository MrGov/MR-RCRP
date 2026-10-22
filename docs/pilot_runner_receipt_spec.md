# Pilot Runner Receipt Specification

## 1. Purpose

The future runner receipt is the machine-auditable record of what an approved pilot runner intended to do, which exact manifest and validation evidence it accepted, which scheduled runs it allocated, which provider class it selected, which outputs it was allowed to write, and how it terminated.

This document defines the receipt only. It does not implement a runner, invoke a provider, execute a candidate, or close Gate P2.

## 2. Receipt states

`status` is one of:

- `preflight_rejected`: no scheduled provider/candidate work may start;
- `preflight_validated`: inert pre-Gate checks passed, but execution is not authorized or scheduled;
- `scheduled`: preflight passed and scheduled-run IDs were allocated;
- `running`: an authorized future run started;
- `completed`: every scheduled run reached a structured terminal state and accounting reconciled;
- `completed_with_failures`: accounting reconciled but one or more scheduled runs failed/blocked;
- `aborted`: execution stopped under a defined stop condition and all known runs were retained;
- `receipt_incomplete`: receipt integrity failed; no positive Gate P2 evidence may be claimed.

Narrative notes cannot override a status or missing evidence.

## 3. Required receipt fields

All fields below are required; nullable fields must still be present with JSON `null`.

### 3.1 Requested audit fields

These fields preserve the normalized raw request even when it is rejected:

| Field | JSON type | Rule |
|---|---|---|
| `requested_provider` | string | Exact requested runtime adapter/config label; never authorization |
| `requested_provider_kind` | enum string | `mock`, `file`, `real`, or `unknown` |
| `artifact_claimed_provider` | string or null | Untrusted artifact claim, audit-only |
| `requested_input_mode` | enum string | `manifest_file`, `single_file`, `directory_glob`, `implicit_default_glob`, or `unknown` |
| `requested_manifest_scope` | string or null | Raw normalized requested/observed scope, including forbidden values |
| `requested_paths` | array of strings | Normalized audit paths; no path is accepted merely by appearing here |
| `requested_command_intent` | string | Audit description only; never executed as a shell command |

### 3.2 Accepted decision fields

| Field | JSON type | Rule |
|---|---|---|
| `accepted_provider` | enum string or null | `mock`, `file`, or null |
| `accepted_input_mode` | enum string or null | `manifest_file` or null |
| `accepted_manifest_scope` | enum string or null | `pilot_nonformal` or null |
| `accepted_execution` | boolean | True only with valid Gate P2 and explicit pilot authorization evidence |
| `rejection_reason` | enum string or null | `real_provider_forbidden`, `unknown_provider`, `uncontrolled_glob_forbidden`, `final_test_scope_forbidden`, `provider_claim_mismatch`, `manifest_scope_forbidden`, `validation_receipt_invalid`, `runtime_authorization_denied`, or null |
| `gate_p2_authorization_id` | string or null | Current runtime authorization receipt; artifact metadata cannot populate it |

### 3.3 Receipt, manifest, scheduling, and evidence fields

| Field | JSON type | Rule |
|---|---|---|
| `receipt_schema_version` | string | Non-empty exact supported version |
| `runner_receipt_id` | string | Derived exactly by Section 7; no self-reference |
| `status` | enum string | One of Section 2 |
| `manifest_hash` | string or null | Exact raw pilot manifest bytes SHA-256; null when not safely available |
| `raw_manifest_bytes_hash` | string or null | Optional explicit alias; when present it must equal `manifest_hash` |
| `manifest_object_hash` | string or null | Canonical parsed manifest-object SHA-256 under the bound algorithm/version |
| `canonical_manifest_hash` | string or null | Legacy compatibility alias only; if retained it must equal `manifest_object_hash` |
| `matrix_scope` | enum string or null | `pilot` or null |
| `objective_version` | string or null | Approved pilot objective or null on early rejection |
| `code_snapshot_hash` | string | Runner plus policy/schema snapshot identity |
| `validation_receipt_id` | string or null | Bound valid manifest receipt ID or null |
| `validation_receipt_hash` | string or null | Exact receipt bytes/hash binding or null |
| `scheduled_run_ids` | array of unique strings | Empty for rejected/validated-only receipts; complete preallocated schedule otherwise |
| `output_paths` | array of objects | Canonical allowlisted pilot outputs; empty before acceptance |
| `failure_summaries` | array of objects | Counts and denominators; never omitted |
| `accounting_summary_id` | string or null | Required for terminal scheduled executions |
| `no_real_llm_evidence` | object | Exact schema in Section 6.1 |
| `no_final_test_input_evidence` | object | Exact schema in Section 6.2 |
| `no_uncontrolled_glob_evidence` | object | Exact schema in Section 6.3 |
| `manifest_only_evidence` | object | Exact schema in Section 6.4 |
| `scope_evidence` | object | Exact schema in Section 6.5 |
| `started_at` | string or null | UTC RFC 3339; null if execution did not start |
| `ended_at` | string | UTC RFC 3339 receipt termination time |
| `wall_time_ms` | number | Finite non-negative |
| `reviewer_notes` | string | May be empty; cannot change machine decision |
| `non_formal_evidence` | boolean | Literal true |

Unknown fields, wrong types, duplicate scheduled IDs, non-finite numbers, absent evidence objects, and inconsistent state/timestamp/decision combinations make the receipt unverifiable.

## 4. Requested-to-accepted decision rules

The runner persists requested audit fields before any provider invocation or scheduling decision. It then applies this unique precedence:

1. Classify the current runtime provider adapter/config into `mock`, `file`, `real`, or `unknown`; artifact claims cannot change this classification.
2. If the current runtime provider is `real` while `artifact_claimed_provider` says mock/file, reject with `provider_claim_mismatch` before invocation. If a frozen artifact claims a real provider while the current runtime permits only mock/file and supplies no separate generated-artifact deployment authority, record `runtime_authorization_denied` and `deployment_blocked`; fallback is permitted only with isolated attribution. Other identity conflicts also use `provider_claim_mismatch`. These directional rules are unique and artifact claims never upgrade authority.
3. Otherwise reject `real` with `real_provider_forbidden` and `unknown` with `unknown_provider` before scheduling/invocation.
4. Reject `directory_glob`, `implicit_default_glob`, `single_file`, or `unknown` as runner inputs; the only accepted input mode is `manifest_file`. Glob variants use `uncontrolled_glob_forbidden`.
5. Reject `formal_final_test` with `final_test_scope_forbidden`; reject every other non-pilot scope with `manifest_scope_forbidden`.
6. Only a valid bound manifest receipt may set accepted provider/input/scope values.
7. `accepted_execution=true` additionally requires a current valid `gate_p2_authorization_id` and explicit pilot execution authorization. Pre-Gate component evidence must use `status=preflight_validated`, `accepted_execution=false`, and no scheduled execution.

Rejected receipts keep requested values, set every unavailable accepted value to null, set `accepted_execution=false`, record exactly one primary `rejection_reason`, and may retain secondary diagnostics separately.

## 5. Preflight binding

Before scheduling future work, the runner must:

1. persist the requested audit fields and provider/input classification;
2. reject provider claim mismatch, real/unknown provider, uncontrolled input mode, and forbidden scope according to Section 4;
3. read the single explicit manifest and validation receipt by explicit paths/IDs;
4. recompute raw manifest bytes and canonical manifest-object hashes in their separate domains, require any `raw_manifest_bytes_hash` alias to equal `manifest_hash`, and verify the receipt's canonical ID;
5. verify validator policy/code bindings and `status=valid`;
6. recheck pilot scopes, objective version, current file/path/hash identities, and non-promotion metadata;
7. prove inputs came from the exact manifest allowlist, not glob/discovery;
8. verify no final-test or formal resource is among accepted inputs;
9. for pre-Gate evidence, stop at `preflight_validated` without provider/candidate invocation;
10. only with Gate P2 plus explicit execution authorization, allocate the full scheduled-run set before provider/generation activity and persist a `scheduled` receipt.

A stale, missing, malformed, mismatched, or rejected validation receipt causes `preflight_rejected`.

## 6. Required evidence object schemas

### 6.1 No-real-provider evidence

`no_real_llm_evidence` contains exactly:

- `requested_provider`: string;
- `requested_provider_kind`: `mock`, `file`, `real`, or `unknown`;
- `accepted_provider`: `mock`, `file`, or null;
- `provider_adapter_identity`: string or null;
- `provider_allowlist`: array containing only approved runtime provider kinds;
- `decision`: `pass`, `reject`, or `not_reached`;
- `checked_at`: UTC RFC 3339 timestamp.

The adapter identity comes from current runtime construction, not artifact metadata. Provider config hashes used elsewhere must exclude secrets.

### 6.2 No-final-test-input evidence

`no_final_test_input_evidence` contains exactly:

- `manifests_loaded`: array of stable manifest identifiers;
- `manifest_scopes_loaded`: array of observed scope strings;
- `paths_scanned_or_loaded`: array of normalized invocation paths;
- `final_test_scope_present`: boolean;
- `decision`: `pass`, `reject`, or `not_reached`;
- `checked_at`: UTC RFC 3339 timestamp.

This is invocation-scoped input evidence, not a claim about the entire host filesystem.

### 6.3 No-uncontrolled-glob evidence

`no_uncontrolled_glob_evidence` contains exactly:

- `requested_input_mode`: the Section 3 enum;
- `accepted_input_mode`: `manifest_file` or null;
- `glob_detected`: boolean;
- `glob_pattern`: string or null;
- `decision`: `pass`, `reject`, or `not_reached`;
- `checked_at`: UTC RFC 3339 timestamp.

### 6.4 Manifest-only evidence

`manifest_only_evidence` contains exactly:

- `manifest_path`: normalized string or null;
- `manifest_hash`: exact raw manifest bytes SHA-256 string or null;
- `manifest_object_hash`: canonical parsed-object SHA-256 string or null;
- `validation_receipt_id`: string or null;
- `decision`: `pass`, `reject`, or `not_reached`;
- `checked_at`: UTC RFC 3339 timestamp.

### 6.5 Scope evidence

`scope_evidence` contains exactly:

- `manifest_scope`: string or null;
- `matrix_scope`: string or null;
- `pilot_nonformal_confirmed`: boolean;
- `formal_final_test_rejected`: boolean;
- `decision`: `pass`, `reject`, or `not_reached`;
- `checked_at`: UTC RFC 3339 timestamp.

Every evidence object is present on success and rejection receipts. Checks not safely reached use empty/null values plus `decision=not_reached`; they are never omitted or silently marked pass.

## 7. Canonical receipt ID derivation

The future implementation must use this exact rule:

1. Normalize every path according to the manifest path policy before serialization.
2. Form the complete receipt body, including all evidence objects.
3. Exclude `runner_receipt_id` and reserved signature fields `signature` and `signatures` from the hashed body.
4. Serialize the remaining JSON with RFC 8785/JCS using UTF-8; JCS deterministic object-member key ordering is the required sorted-key rule.
5. Set `runner_receipt_id` to lowercase hexadecimal `SHA-256(canonical_utf8_bytes)`.

The ID is not included in its own preimage. Changing any requested/accepted field, evidence object, timestamp, summary, or referenced ID changes the receipt ID. Verification recomputes this derivation and rejects mismatch.

## 8. Scheduled-run and output reconciliation

- Every `scheduled_run_id` must have exactly one run/operator-type closeout record.
- Missing closeout produces `receipt_incomplete` or `aborted`, not silent deletion.
- Output paths must be below the approved pilot output root and labeled `pilot_nonformal`.
- Unexpected output, formal scope, or unallowlisted path triggers stop/aborted status and a structured integrity failure.
- The terminal receipt references candidate, cell, failure, fallback, attribution, and accounting summary hashes.

## 9. Failure summaries

The receipt separately reports counts and denominators for:

- source-read failure;
- validation failure;
- execution blocked/risk acknowledgement required;
- runtime error and timeout;
- invalid solution/contract violation;
- freeze failure and deployment block;
- fallback use;
- no valid operator and not evolved;
- attributed generated success;
- localized failure-zero cells;
- batch-inconclusive integrity failures.

`not_evolved` is not counted as `no_valid_operator` or execution failure. Batch-inconclusive events are not converted to cell zero.

## 10. Example uncontrolled-glob rejection

```json
{
  "receipt_schema_version": "pilot-runner-v1",
  "runner_receipt_id": "sha256_of_canonical_body_excluding_id_and_signatures",
  "requested_provider": "mock",
  "requested_provider_kind": "mock",
  "artifact_claimed_provider": null,
  "requested_input_mode": "directory_glob",
  "requested_manifest_scope": null,
  "requested_paths": ["pilot-input/*.txt"],
  "requested_command_intent": "validate pilot glob",
  "accepted_provider": null,
  "accepted_input_mode": null,
  "accepted_manifest_scope": null,
  "accepted_execution": false,
  "rejection_reason": "uncontrolled_glob_forbidden",
  "gate_p2_authorization_id": null,
  "status": "preflight_rejected",
  "manifest_hash": null,
  "canonical_manifest_hash": null,
  "matrix_scope": null,
  "objective_version": null,
  "code_snapshot_hash": "sha256_placeholder",
  "validation_receipt_id": null,
  "validation_receipt_hash": null,
  "scheduled_run_ids": [],
  "output_paths": [],
  "failure_summaries": [{"failure_type": "uncontrolled_glob_rejected", "count": 1, "denominator": 1}],
  "accounting_summary_id": null,
  "no_real_llm_evidence": {
    "requested_provider": "mock", "requested_provider_kind": "mock", "accepted_provider": null,
    "provider_adapter_identity": "mock-adapter-v1", "provider_allowlist": ["mock", "file"],
    "decision": "pass", "checked_at": "2026-08-11T00:00:00Z"
  },
  "no_final_test_input_evidence": {
    "manifests_loaded": [], "manifest_scopes_loaded": [], "paths_scanned_or_loaded": [],
    "final_test_scope_present": false, "decision": "not_reached", "checked_at": "2026-08-11T00:00:00Z"
  },
  "no_uncontrolled_glob_evidence": {
    "requested_input_mode": "directory_glob", "accepted_input_mode": null,
    "glob_detected": true, "glob_pattern": "pilot-input/*.txt", "decision": "reject",
    "checked_at": "2026-08-11T00:00:00Z"
  },
  "manifest_only_evidence": {
    "manifest_path": null, "manifest_hash": null, "validation_receipt_id": null,
    "decision": "reject", "checked_at": "2026-08-11T00:00:00Z"
  },
  "scope_evidence": {
    "manifest_scope": null, "matrix_scope": null, "pilot_nonformal_confirmed": false,
    "formal_final_test_rejected": false, "decision": "not_reached", "checked_at": "2026-08-11T00:00:00Z"
  },
  "started_at": null,
  "ended_at": "2026-08-11T00:00:00Z",
  "wall_time_ms": 1.0,
  "reviewer_notes": "Illustrative placeholder only",
  "non_formal_evidence": true
}
```

The example is illustrative; placeholder hashes cannot validate.

## 11. Gate P2 machine-auditable evidence

“Demonstrably executable” is satisfied only by a reviewed evidence set, not prose:

- valid manifest validation receipt;
- rejection receipts for scope, hash, path, duplicate, glob, and final-test cases;
- runner preflight receipt bound to the validation receipt;
- scheduled-run allocation/reconciliation receipt from inert or injected pre-Gate checks;
- required no-real-LLM, no-final-test-input, no-glob, manifest-only, and scope evidence objects;
- schema/code/config/fixture hashes;
- test report IDs mapped to Gate P2 items;
- independent implementation review with no Critical/Required findings.

Actual provider or candidate execution is not required to prove preflight wiring and must not be performed before Gate P2 authorization. Post-Gate execution receipts are later pilot evidence, not prerequisites used circularly to open the initial gate.

### Validation-receipt hash-domain boundary

The runner must never reinterpret an object hash as receipt `manifest_hash`. For a reconciled PIV-04 receipt, `manifest_hash` is the raw bytes digest, optional `raw_manifest_bytes_hash` equals it, and `manifest_object_hash` is the canonical object digest. The runner rejects missing/mismatched domains, legacy ambiguity without an explicitly supported migration, parsed-object disagreement, and any receipt that claims execution authorization or Gate P2 closure. A valid validation receipt remains inert and is not itself permission to schedule or execute work.

## 12. Review boundary

A runner receipt can support Gate P2 only after its schema and implementation are tested and independently reviewed. Phase 6B merely defines the contract; all Gate P2 checkboxes remain open.
