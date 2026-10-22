# Pilot Manifest Validator Specification

## 1. Purpose and authority

The future validator is the only planned entry point for turning raw pilot manifest bytes into a runner-eligible manifest reference. It validates `pilot_nonformal` artifacts only. This specification does not implement or execute the validator.

Successful validation proves conformity to the pilot contract at a recorded time. It does not authorize provider execution, candidate execution, deployment, formal use, or final-test access.

## 2. Inputs

The validator accepts explicit arguments only:

| Input | Type | Rule |
|---|---|---|
| `manifest_path` | absolute path | Single file under approved pilot control root; no glob/wildcard/directory |
| `approved_pilot_data_root` | absolute path | Current runtime configuration, not manifest metadata |
| `expected_manifest_hash` | SHA-256 string | Required; binds exact raw manifest bytes |
| `expected_pilot_family_matrix_hash` | SHA-256 string | Required current pilot policy evidence |
| `expected_pilot_split_rule_hash` | SHA-256 string | Required current pilot policy evidence |
| `validator_policy_version` | string | Required approved policy identifier |
| `validator_code_hash` | SHA-256 string | Required current implementation snapshot |
| `file_identity_policy` | enum | `required`, or explicitly approved `pilot_warning_only` |

No default directory scan, environment-derived final-test path, or manifest-discovered secondary manifest is permitted.

### 2.1 Bounded PIV-04/T5 receipt-assembly input

The Phase 6B-T5 receipt builder/verifier is a no-I/O slice of the future validator. Its future API receives explicit values only:

- `raw_manifest_bytes: bytes`;
- `manifest_obj: Mapping` / JSON object;
- `prevalidation_result`;
- `path_validation_result`;
- `validator_identity: string`.

It does not accept or read `manifest_path`, a data/final-test directory, an implicit glob, or any directory-discovery input. The caller supplies the bytes; acquiring them from a path and composing the full I/O validator remain later separately authorized work.

## 3. Output union

The output is exactly one of:

1. `pilot_manifest_validation_receipt` with `status=valid`; or
2. `pilot_manifest_rejection_receipt` with `status=rejected`.

Exceptions are converted into rejection receipts where the receipt can be written safely. Failure to produce a receipt keeps the manifest ineligible and returns a fail-closed process status.

## 4. Validation order

Validation uses the following fixed order:

1. read exact manifest bytes with strict UTF-8;
2. verify raw-byte `expected_manifest_hash`;
3. parse one JSON document with duplicate-key rejection;
4. validate fixed schema and `additionalProperties=false`;
5. enforce `manifest_scope=pilot_nonformal`, `matrix_scope=pilot`, and literal `artifact_promotion_allowed=false`;
6. reject any formal/final-test field, value, path, reference, or secondary-manifest instruction;
7. verify pilot matrix and split-rule hashes against runtime expected values;
8. canonicalize records using the protocol's RFC 8785/JCS representation and verify canonical ordering/manifest identity;
9. normalize and validate every instance path;
10. verify raw instance-file hashes;
11. reject duplicate identities, content, paths, or file identities;
12. produce no-final-test/no-glob evidence and the final receipt.

Later checks do not run after an earlier fail-closed rejection, but all safe-to-compute reasons from the current stage may be recorded.

## 5. Hash rules

- Algorithm is SHA-256, lowercase hexadecimal.
- In a PIV-04 validation receipt, `manifest_hash` binds the exact `raw_manifest_bytes` supplied to the receipt builder/verifier: `manifest_hash = SHA-256(raw_manifest_bytes)`.
- If `raw_manifest_bytes_hash` is present, it is an explicit explanatory alias for the raw-byte domain and must equal `manifest_hash` exactly. It is not an independently selectable hash.
- `manifest_object_hash` binds the parsed `manifest_obj` using the recorded RFC 8785/JCS-compatible canonicalization algorithm/version. It is the object-domain value used by pure-object prevalidation.
- `canonical_manifest_hash` is a legacy v1 receipt name. A reconciled receipt version must use `manifest_object_hash`; if a compatibility alias is retained during migration, it must equal `manifest_object_hash` and must never be used as the raw-byte `manifest_hash`.
- A canonical object hash must never be written to `manifest_hash` or `raw_manifest_bytes_hash`, and a raw-byte hash must never be written to `manifest_object_hash`.
- The artifact-header `manifest_hash` defined by `manifest_spec.md` has its own self-hash domain. It must not be copied into the PIV-04 receipt `manifest_hash`; the receipt recomputes raw bytes and object-domain hashes from its explicit inputs.
- `file_hash` binds exact raw instance-file bytes.
- `pilot_family_matrix_hash` and `pilot_split_assignment_rule_hash` must match current runtime-approved expected values; artifact self-claims do not establish authority.
- The receipt binds raw/object manifest hashes, canonicalization algorithm/version, prevalidation/path result identities and statuses, validator policy/code identity, and every accepted instance ID/file hash pair available from the supplied evidence.
- The builder/verifier must parse `raw_manifest_bytes` as one strict JSON object and compare it with `manifest_obj`. Invalid JSON, duplicate-key ambiguity, parsed/object mismatch, unavailable canonicalization, or a mismatch with `prevalidation_result.manifest_object_hash` is a rejection. If path evidence carries a manifest/object binding, it must match the same `manifest_object_hash`.
- Any mismatch is a rejection, never a warning.

## 6. Path normalization and identity

For each record, the future validator must:

1. reject NUL, wildcard, URI, drive-relative, and parent-traversal forms;
2. resolve against the explicit approved pilot root;
3. require the canonical resolved path to remain under that root;
4. reject symlinks/reparse aliases and any path whose resolution changes during validation;
5. open/read the exact resolved file and bind its content hash;
6. record canonical path and file identity when supported;
7. reject duplicate canonical paths, hashes, or file identities.

The manifest's `family_id` or `instance_id` cannot override exact-file duplicate detection.

## 7. Duplicate handling

The following are fail-closed across all records in the pilot manifest:

- duplicate JSON keys;
- duplicate `instance_id`;
- duplicate `file_hash`, even with different family/instance IDs;
- duplicate canonical resolved path;
- duplicate file identity/hardlink when supported;
- duplicate generation identity that resolves to identical content;
- noncanonical record ordering where canonical ordering is required.

The validator never keeps the first duplicate, silently deduplicates, or renames a record.

## 8. Unsupported file-identity behavior

If the platform cannot reliably inspect file identity/hardlinks:

- record `file_identity_check=support_unavailable` and the platform reason;
- require strong content-hash and canonical-path checks;
- permit continuation only when current pilot policy explicitly sets `pilot_warning_only`;
- mark the receipt `formal_evidence_eligible=false`;
- never reuse this exception for formal execution. Formal policy remains fail closed unless a separate preregistered formal exemption exists.

## 9. Pilot/formal and final-test rejection

Reject before any provider activity when:

- `manifest_scope` is missing, wrong-type, or anything other than `pilot_nonformal`;
- `matrix_scope` is missing, wrong-type, or anything other than `pilot`;
- a record/header refers to `formal_train`, `formal_dev`, or `formal_final_test`;
- `artifact_promotion_allowed` is absent, non-boolean, or not literal false;
- formal identity/source fields are populated contrary to the pilot schema;
- any final-test manifest/path/hash/family/lockbox/performance field or reference appears;
- configuration requests glob/discovery or a secondary manifest.

## 10. No-final-test and no-glob evidence

The receipt records what was checked, not an impossible global claim. Evidence includes:

- validator input contained exactly one pilot manifest path;
- manifest/config schema contains no final-test or secondary-manifest fields;
- every accepted path belongs to the approved pilot root and allowlist;
- no wildcard, directory scan, or discovery API was requested;
- no formal/final-test scope was parsed or accepted;
- final-test resources were neither inputs nor outputs of validation.

This evidence is called `no_final_test_input_proof`, not proof that no final-test artifact exists anywhere on the host.

## 11. Receipt schema

Common required fields:

- `receipt_schema_version`;
- `receipt_type`;
- `validation_receipt_id`;
- `status`;
- `manifest_path_input_hash` or redacted stable path identifier;
- `manifest_hash`, meaning only SHA-256 of explicit raw manifest bytes;
- `raw_manifest_bytes_hash`, if present, equal to `manifest_hash`;
- `manifest_object_hash` or null only when raw bytes cannot be parsed/canonicalized;
- `canonicalization_algorithm` and `canonicalization_version`;
- `prevalidation_result_id`, `prevalidation_status`, `path_validation_result_id`, and `path_validation_status`;
- `manifest_scope` and `matrix_scope` or null if unavailable;
- `pilot_family_matrix_hash` and `pilot_split_assignment_rule_hash` or null;
- `validator_policy_version` and `validator_code_hash`;
- `approved_pilot_data_root_id`;
- `checks_performed` and `checks_not_reached`;
- `rejection_reasons` array;
- `accepted_record_count`;
- `file_identity_check` and reason;
- `no_final_test_input_proof` evidence object;
- `no_uncontrolled_glob_proof` evidence object;
- `formal_evidence_eligible=false`;
- `execution_authorized=false` and `gate_p2_closed=false`;
- `started_at`, `ended_at`, and finite non-negative `wall_time_ms`.

The reconciled PIV-04 receipt status enum is exactly `valid` or `rejected`. `validation_valid`, `validation_rejected`, runner preflight states, and scheduled/running/completed/executed states are forbidden. `valid` requires both prevalidation and path validation to be valid and every raw/object/evidence binding to agree. Otherwise the receipt is `rejected` and preserves source-qualified rejection reasons.

This is an inert validation receipt, not a runner or execution receipt. It must not contain `runner_receipt_id`, `scheduled_run_id`, provider invocation results, candidate/pilot execution results, or any formal/final-test readiness assertion.

### 11.1 Canonical validation receipt ID

The future implementation uses this exact, non-self-referential rule:

1. Normalize receipt paths according to Section 6.
2. Form the complete validation or rejection receipt, including both evidence objects.
3. Exclude `validation_receipt_id` and reserved signature fields `signature` and `signatures` from the hash preimage.
4. Serialize the remaining JSON using RFC 8785/JCS and UTF-8; JCS deterministic object-member key ordering is the required sorted-key rule.
5. Set `validation_receipt_id` to lowercase hexadecimal `SHA-256(canonical_utf8_bytes)`.

Changing any validation outcome, evidence object, check list, timestamp, accepted record binding, or policy/code hash changes the receipt ID. Verification recomputes the same body and rejects mismatches. The receipt ID is never included in its own preimage.

The preimage also includes the distinct raw/object manifest hashes, canonicalization identity, prevalidation/path result identities and statuses, inert gate fields, and all rejection reasons. Reserved `signature`/`signatures` fields remain excluded. A receipt version using the reconciled hash domains must not reuse the legacy v1 schema identifier without a separately reviewed schema migration.

Unknown/missing/wrong-type fields make the receipt unverifiable.

## 12. Legacy v1 example valid pilot receipt

This example documents the currently implemented legacy v1 field set only. It is not a reconciled T5/PIV-04 receipt example and cannot define the new raw-byte/object hash domains.

```json
{
  "receipt_schema_version": "pilot-validator-v1",
  "receipt_type": "pilot_manifest_validation_receipt",
  "validation_receipt_id": "sha256_of_canonical_body_excluding_id_and_signatures",
  "status": "valid",
  "manifest_path_input_hash": "sha256_placeholder",
  "manifest_hash": "sha256_placeholder",
  "canonical_manifest_hash": "sha256_placeholder",
  "manifest_scope": "pilot_nonformal",
  "matrix_scope": "pilot",
  "pilot_family_matrix_hash": "sha256_placeholder",
  "pilot_split_assignment_rule_hash": "sha256_placeholder",
  "validator_policy_version": "pilot-validator-policy-v1",
  "validator_code_hash": "sha256_placeholder",
  "approved_pilot_data_root_id": "pilot-root-v1",
  "checks_performed": ["schema", "scope", "hash", "path", "duplicate", "no_final_test", "no_glob"],
  "checks_not_reached": [],
  "rejection_reasons": [],
  "accepted_record_count": 2,
  "file_identity_check": "supported_pass",
  "file_identity_reason": null,
  "no_final_test_input_proof": {"status": "pass", "scope": "validator_inputs_and_accepted_paths"},
  "no_uncontrolled_glob_proof": {"status": "pass", "input_kind": "single_manifest"},
  "formal_evidence_eligible": false,
  "started_at": "2026-08-11T00:00:00Z",
  "ended_at": "2026-08-11T00:00:00Z",
  "wall_time_ms": 1.0
}
```

Placeholders are illustrative and cannot pass real validation.

The examples above/below predate the reconciled T5 hash-domain contract and illustrate the legacy v1 field set only. Future T5 RED tests target a new receipt version with `manifest_hash` as raw bytes, `manifest_object_hash` as canonical object hash, and the inert/evidence-binding fields specified in Sections 2.1, 5, and 11; legacy examples must not be used to reinterpret either hash domain.

## 13. Legacy v1 example rejection receipt

```json
{
  "receipt_schema_version": "pilot-validator-v1",
  "receipt_type": "pilot_manifest_rejection_receipt",
  "validation_receipt_id": "sha256_of_canonical_body_excluding_id_and_signatures",
  "status": "rejected",
  "manifest_path_input_hash": "sha256_placeholder",
  "manifest_hash": "sha256_placeholder",
  "canonical_manifest_hash": null,
  "manifest_scope": "formal_final_test",
  "matrix_scope": "formal",
  "pilot_family_matrix_hash": null,
  "pilot_split_assignment_rule_hash": null,
  "validator_policy_version": "pilot-validator-policy-v1",
  "validator_code_hash": "sha256_placeholder",
  "approved_pilot_data_root_id": "pilot-root-v1",
  "checks_performed": ["schema", "scope"],
  "checks_not_reached": ["path", "file_hash", "duplicate"],
  "rejection_reasons": ["forbidden_manifest_scope", "formal_final_test_rejected"],
  "accepted_record_count": 0,
  "file_identity_check": "not_reached",
  "file_identity_reason": "scope_rejected",
  "no_final_test_input_proof": {"status": "fail", "reason": "final_test_scope_present"},
  "no_uncontrolled_glob_proof": {"status": "not_reached"},
  "formal_evidence_eligible": false,
  "started_at": "2026-08-11T00:00:00Z",
  "ended_at": "2026-08-11T00:00:00Z",
  "wall_time_ms": 1.0
}
```

## 14. Future acceptance evidence

Implementation acceptance later requires RED/GREEN tests for every rejection class, deterministic receipt replay, validator code/schema hashes, and independent review. A valid receipt remains insufficient to close Gate P2 without the runner, observability, fixture, and review evidence defined elsewhere.
