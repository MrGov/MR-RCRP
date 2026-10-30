# Closed-Loop Observability Plan

## 1. Purpose

The future pilot must be auditable from scheduled run through candidate, execution, freeze, deployment, fallback, and accounting. This document plans fields and invariants only; it creates no schema implementation or pilot results.

## 2. Required identifiers and provenance

| Field | Planned meaning |
|---|---|
| `scheduled_run_id` | Preassigned run identity retained even if generation never succeeds |
| `provider` | Runtime provider adapter used by the scheduled run |
| `claimed_source_provider` | Untrusted artifact claim, audit-only |
| `runtime_authorization_status` | Current runtime decision, independent of artifact metadata |
| `runtime_authorization_source` | Current config/session/policy evidence source |
| `manifest_scope` | Must be `pilot_nonformal` for pilot |
| `matrix_scope` | Must be `pilot` for pilot |
| `pilot_manifest_id` / `pilot_manifest_hash` | Exact allowlist evidence |
| `pilot_family_matrix_hash` | Pilot-only matrix audit hash |
| `pilot_split_assignment_rule_hash` | Pilot-only split-rule audit hash |
| `objective_version` | Explicit prototype-smoke or objective-v2 systems-pilot version |
| `candidate_id` | Stable candidate identity within generation lineage |
| `code_hash` | SHA-256 of the source evaluated/executed |

## 3. Candidate and execution fields

Each candidate row must record at least:

- `validation_status`;
- `execution_status`;
- `failure_type`;
- `safe_to_execute` policy result;
- `requires_human_risk_ack` claim and current runtime acknowledgement separately;
- claimed, trusted, and effective sandbox level;
- executor identity/evidence;
- `fallback_used` and `fallback_reason`;
- `timeout_ms`, `runtime_ms`, and `wall_time_ms`;
- `exit_code`;
- captured `stdout`/`stderr` and independent truncation flags/limits;
- contract/feasibility status and subtype;
- benchmark eligibility and evaluation status;
- freeze eligibility and rejection reasons;
- deployment eligibility and rejection reasons;
- `generated_success_attributed`;
- `reward_attributed` and reward attribution reason;
- `no_valid_operator` and `not_evolved` as mutually exclusive state semantics where applicable.

Missing evidence must not inherit a success/default value. Unknown, absent, malformed, or wrong-type safety fields fail closed.

## 4. Lifecycle events

The planned event log uses append-only events keyed by `scheduled_run_id` and, when available, `candidate_id`:

1. `run_scheduled`;
2. `provider_invoked` / `provider_failed`;
3. `candidate_persisted` / `source_read_failed`;
4. `validation_completed`;
5. `execution_gate_decided`;
6. `execution_completed` / `timeout` / `runtime_error`;
7. `contract_check_completed`;
8. `benchmark_completed` / `benchmark_not_evaluable`;
9. `selection_decided`;
10. `freeze_decided`;
11. `deployment_gate_decided`;
12. `generated_execution_attributed` or `fallback_recorded`;
13. `cell_accounted`;
14. `run_closed`.

An omitted stage must be represented by an explicit `not_reached` reason, not inferred from absent rows.

## 5. Cell and scheduled-run accounting

Required accounting fields include:

- `cell_id` and its planned run/method/family/replicate/solver-seed components when a pilot evaluation grid is used;
- `cell_failure_mapping` (`observed_generated_value`, `failure_zero_policy`, or `batch_inconclusive` according to governing rules);
- `cell_analysis_value` plus a boolean showing whether it is a policy-imputed zero;
- `scheduled_run_accounting_category`;
- `run_deployable_portfolio_status`;
- `family_evaluable_status` where applicable;
- fallback, attributed-generated-success, and deployment-block rates with explicit denominators.

The pilot must preserve the distinction between:

- localized generated-result failure mapped by policy;
- batch/input/manifest integrity failure that makes the batch inconclusive;
- successful execution with no optimization improvement;
- fallback output that is not a generated result.

## 6. Attribution invariants

- `fallback_used=true` implies generated success attribution is false for the fallback component.
- An invalid, blocked, timeout, unsafe, source-hash-missing/mismatched, or deployment-blocked candidate has zero generated reward attribution.
- A joint destroy/repair trial with ambiguous contribution records `attribution_ambiguous` and does not reward either generated component unless attribution is independently valid under the governing rule.
- Artifact claims about provider, sandbox, safety, or risk acknowledgement are never runtime authority.
- `execution_success` does not imply feasible solution, benchmark improvement, freeze eligibility, deployment eligibility, or generated success.

## 7. Planned output artifacts

Future pilot output should include:

- scheduled-run registry;
- candidate JSONL/event log;
- validation/execution receipts;
- selection/freeze/deployment decisions;
- fallback and attribution report;
- cell/run accounting table;
- schema, code, config, manifest, and fixture hashes;
- pilot closeout and pilot-artifact exclusion receipt.

All outputs must be labeled `pilot_nonformal` and `non_formal_evidence=true`. They may support pipeline review and planning only, not a paper performance claim.
