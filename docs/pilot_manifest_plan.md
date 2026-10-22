# Pilot-Only Manifest Plan

## 1. Status

This document plans a future pilot manifest. It does not create a matrix, manifest, fixture, instance, or hash and does not authorize pilot execution.

The pilot manifest contract is independent from the formal train/dev/final-test manifest lifecycle.

## 2. Required scope and identity

Every future pilot manifest must declare:

| Field | Planned value or rule |
|---|---|
| `manifest_scope` | Exact enum `pilot_nonformal` |
| `matrix_scope` | Exact enum `pilot` |
| `family_matrix_hash` | Hash of the pilot-only matrix; exposed in pilot receipts as `pilot_family_matrix_hash` |
| `split_assignment_rule_hash` | Hash of the pilot-only split rule; exposed as `pilot_split_assignment_rule_hash` |
| `artifact_promotion_allowed` | Literal `false` |
| `formal_identity_version` | Pilot-schema sentinel such as `not_applicable`, never a trusted formal identity |
| `objective_version` | Explicitly `objective_v1_prototype` for smoke or `objective_v2_formal` for a future objective-v2 systems pilot |
| `lockbox_status` | Non-final value such as `not_applicable`; never a final-test lockbox claim |

The canonical manifest fields remain `family_matrix_hash` and `split_assignment_rule_hash`; the two `pilot_*` names are mandatory audit aliases in the pilot receipt, not independently computed hashes.

## 3. Pilot-only matrix and split rule

Before any future pilot instance generation:

1. Freeze a pilot-only family matrix that contains only approved smoke/train/dev pilot families.
2. Freeze a pilot-only split assignment rule.
3. Canonicalize both artifacts and compute their hashes.
4. Record generator/schema versions, generation seeds, exclusions, and replacement rules.
5. Prohibit any final-test field, family, path, identity, hash, or derived feature.

The pilot matrix is not a partial view of the complete formal matrix. It is a separate non-formal artifact.

## 4. Non-promotion contract

Pilot artifacts must not be:

- promoted or relabeled as formal train/dev/final-test artifacts;
- copied, hard-linked, soft-linked, aliased, or moved into formal manifests;
- reused under a new filename while preserving identical bytes or file identity;
- reused through pilot family IDs, instance IDs, generation identity, source reference, or manifest hash;
- cited as formal evidence.

If a future formal protocol uses conceptually similar parameters, it must freeze a complete formal matrix first, regenerate instances under a new formal identity, and pass the formal pilot-artifact exclusion check.

## 5. Planned runner rules

The future pilot runner must:

- accept only `manifest_scope=pilot_nonformal` with `matrix_scope=pilot`;
- verify pilot-scoped matrix/rule hashes before reading instances;
- use an exact manifest allowlist and reject uncontrolled glob/discovery;
- reject missing, duplicate, aliased, symlinked, hard-linked, path-traversing, or hash-mismatched inputs according to the pilot policy;
- reject `formal_train`, `formal_dev`, and especially `formal_final_test` manifests;
- reject configuration fields that point to or describe final-test artifacts;
- emit an actual-input manifest and pilot preflight receipt.

The future formal runner must reject every `pilot_nonformal` artifact and any identity/hash/path/file-identity match in the pilot-artifact exclusion receipt.

## 6. Planned receipts

### 6.1 Pilot preflight receipt

The receipt should bind:

- pilot manifest IDs and three explicit hash domains: raw receipt `manifest_hash`, optional equal alias `raw_manifest_bytes_hash`, and canonical parsed-object `manifest_object_hash`; the manifest artifact header self-hash remains a separate artifact-domain value;
- `pilot_family_matrix_hash` and `pilot_split_assignment_rule_hash`;
- schema/policy versions;
- exact allowlist and actual-input-set check;
- duplicate/path/file-identity capability checks;
- non-formal status and receipt hash.

The bounded T5 receipt builder receives caller-supplied `raw_manifest_bytes`, `manifest_obj`, prevalidation/path results, and validator identity. It does not receive or read a path, directory, glob, discovered input, or final-test resource. It verifies raw-byte/object consistency and remains inert with `execution_authorized=false` and `gate_p2_closed=false`; full I/O validation and runner scheduling are later separately authorized tasks.

### 6.2 Pilot-artifact exclusion receipt

At future pilot closeout, retain an immutable denylist receipt containing pilot:

- family and instance IDs;
- source and file hashes;
- canonical paths and available file identities;
- generation identities;
- manifest, family-matrix, and split-rule hashes.

It contains no final-test information and is consumed only by a future formal preflight.

## 7. Planned invalid-manifest cases

Future validation fixtures should cover wrong/missing scope, non-boolean promotion flag, mismatched pilot hashes, duplicate IDs/files, unsafe paths, uncontrolled glob, formal manifest passed to pilot runner, and any final-test field or path in pilot configuration. All must fail closed before provider or candidate execution.

## 8. Non-blocking specification refinements

- Explicitly enumerate pilot `family_matrix_hash` and `split_assignment_rule_hash` in the formal leakage-rejection list, alongside file/manifest hashes.
- Label Gate P1 checkboxes as **permitted planning scope after entry**, not prerequisites that must already be completed before planning begins.

These are documentation refinements for later review; this plan does not modify the governing protocol or close Gate P2.
