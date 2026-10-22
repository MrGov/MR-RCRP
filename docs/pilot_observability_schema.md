# Pilot Observability Schema

## 1. Status and storage model

This is a planned schema, not an implemented database or log. A future pilot will use append-only JSONL records plus canonical closeout summaries. Every record carries:

- `schema_version`: non-empty string;
- `record_type`: exact enum;
- `record_id`: deterministic or collision-resistant non-empty string;
- `created_at`: UTC RFC 3339 timestamp;
- `pilot_manifest_hash`: lowercase SHA-256 hex;
- `non_formal_evidence`: literal `true`.

Unknown fields, missing required fields, wrong JSON types, non-finite numbers, and invalid enum values fail closed. Null is allowed only where explicitly stated.

The three record levels have different owners. Run/operator-type summaries must not be copied into candidate rows, and evaluation-cell keys must be explicit rather than recoverable only by parsing `cell_id`.

## 2. Run/operator-type record

`record_type = run_operator_type`

| Field | JSON type | Required | Rule |
|---|---|---:|---|
| `scheduled_run_id` | string | yes | Allocated before provider/generation activity |
| `evolution_run_id` | string | yes | Independent pilot evolution-run identity |
| `method_condition` | string | yes | Preregistered/mock validation condition |
| `provider` | string | yes | Runtime adapter selected by current config |
| `operator_type` | enum string | yes | `repair` or `destroy` |
| `manifest_scope` | enum string | yes | Exact `pilot_nonformal` |
| `matrix_scope` | enum string | yes | Exact `pilot` |
| `objective_version` | string | yes | Explicit prototype smoke or objective-v2 systems-pilot label |
| `run_status` | enum string | yes | `scheduled`, `started`, `blocked`, `failed`, `completed`, `closed` |
| `operator_type_status` | enum string | yes | `not_evolved`, `no_valid_operator`, `eligible_operator_available`, `freeze_failed`, `deployment_blocked`, `deployed`, `failed` |
| `no_valid_operator` | boolean | yes | True only when scheduled/evolved but no eligible candidate remains |
| `not_evolved` | boolean | yes | True only when operator type was not scheduled; mutually exclusive with `no_valid_operator` |
| `deployment_blocked` | boolean | yes | Run/operator-type deployment result |
| `freeze_failed` | boolean | yes | Run/operator-type freeze result |
| `deployable_operator_count` | integer | yes | Non-negative; zero is explicit |
| `runtime_authorization_status` | enum string | yes | `not_required`, `missing`, `invalid`, `denied`, `authorized` |
| `runtime_authorization_source` | string or null | yes | Current runtime evidence only; null unless applicable |
| `accounting_category` | enum string | yes | `scheduled_success`, `scheduled_failure`, `not_evolved`, `deployment_blocked`, `batch_inconclusive` |
| `closed_at` | string or null | yes | UTC RFC 3339 when closed |

Invariants:

- `no_valid_operator` and `not_evolved` cannot both be true.
- `not_evolved=true` implies zero candidate records for that operator type and does not mean failure.
- `no_valid_operator=true` implies at least one scheduled evolution attempt or a structured pre-candidate failure attributable to that scheduled attempt.
- A positive deployable count requires referenced eligible, non-fallback frozen operator records.

## 3. Candidate record

`record_type = candidate`

| Field | JSON type | Required | Rule |
|---|---|---:|---|
| `candidate_id` | string | yes | Stable within generation lineage |
| `scheduled_run_id` | string | yes | Foreign key to run/operator-type record |
| `operator_type` | enum string | yes | `repair` or `destroy` |
| `claimed_source_provider` | string | yes | Audit-only artifact claim; never authorization |
| `code_hash` | string | yes | SHA-256 of exact validated/executed source bytes |
| `validation_status` | enum string | yes | `not_run`, `source_read_failed`, `validation_failed`, `success` |
| `execution_status` | enum string | yes | `not_attempted`, `execution_blocked`, `validation_blocked`, `deployment_blocked`, `runtime_error`, `timeout`, `execution_success` |
| `contract_status` | enum string | yes | `not_evaluated`, `contract_valid`, `malformed_return`, `missing_tasks`, `duplicate_tasks`, `wrong_type`, `contract_violation` |
| `feasibility_status` | enum string | yes | `not_evaluated`, `feasible_solution`, `invalid_solution`, `infeasible_assignment`, `geometry_violation`, `coverage_violation` |
| `optimization_status` | enum string | yes | `not_evaluable`, `improved_over_baseline`, `tied_baseline`, `worsened_vs_baseline`, `no_improvement` |
| `structural_diagnostics` | array of unique enum strings | yes | Exact values from `none`, `degenerate_operator`, `ignores_context`, `always_fallback`, `duplicate_behavior`, `excessive_complexity`, `unsafe_pattern_blocked`; `none` must appear alone |
| `failure_type` | string | yes | Derived summary or literal `none`; cannot replace or override the five status axes |
| `safe_to_execute` | boolean | yes | Current policy result; artifact self-claim is insufficient |
| `requires_human_risk_ack` | boolean | yes | Candidate risk requirement, separate from runtime acknowledgement |
| `effective_sandbox_level` | string | yes | Trusted runtime value; current boundary is `timeout_only` |
| `executor_identity` | string | yes | Runtime executor evidence; not artifact authority |
| `fallback_used` | boolean | yes | Candidate/deployment path used a built-in fallback |
| `fallback_reason` | string or null | yes | Required non-empty string when fallback is true |
| `timeout_ms` | number | yes | Finite positive value |
| `runtime_ms` | number | yes | Finite, non-negative |
| `wall_time_ms` | number | yes | Finite, non-negative |
| `exit_code` | integer or null | yes | Null only if no child process was started |
| `stdout_truncated` | boolean | yes | Independent capture flag |
| `stderr_truncated` | boolean | yes | Independent capture flag |
| `selection_eligible` | boolean | yes | Fail-closed policy result |
| `freeze_eligible` | boolean | yes | Fail-closed policy result |
| `deployment_eligible` | boolean | yes | Current deployment gate result |
| `generated_success_attributed` | boolean | yes | False for invalid/blocked/timeout/fallback/unattributed outcomes |
| `reward_attributed` | boolean | yes | Requires attributable generated success |

Candidate rows must **not** contain `no_valid_operator`, `not_evolved`, deployable portfolio counts, or run-level deployment summaries. Those facts are derived and stored at the run/operator-type level.

Candidate-axis invariants:

- `execution_status=execution_success` says only that the allowed code invocation returned control without runtime error/timeout. It does not imply `contract_valid`.
- `contract_status=contract_valid` does not imply `feasibility_status=feasible_solution`.
- `feasibility_status=feasible_solution` does not imply optimization improvement; `optimization_status` remains an independent axis.
- `invalid_solution` belongs only to `feasibility_status`, never to `execution_status`.
- Static/AST/security rejection uses `validation_status=validation_failed`, `execution_status=validation_blocked`, contract/feasibility `not_evaluated`, optimization `not_evaluable`, and may add `unsafe_pattern_blocked`.
- Runtime error or timeout implies contract/feasibility `not_evaluated` unless a separately completed contract check is explicitly referenced; optimization is `not_evaluable`.
- `no_improvement` is the registered aggregate label for tied-or-worsened outcomes and must not be counted as an additional independent observation beside its underlying outcome.
- Any inconsistency among axes makes the candidate record invalid and ineligible for selection, freezing, deployment, success attribution, or reward.

## 4. Evaluation-cell record

`record_type = evaluation_cell`

| Field | JSON type | Required | Rule |
|---|---|---:|---|
| `cell_id` | string | yes | Unique record identity, not the sole source of hierarchy keys |
| `evolution_run_id` | string | yes | Explicit hierarchy key |
| `scheduled_run_id` | string | yes | Explicit hierarchy key |
| `method_condition` | string | yes | Explicit hierarchy key |
| `family_id` | string | yes | Pilot family only |
| `instance_id` | string | yes | Exact pilot manifest record |
| `instance_replicate` | integer | yes | Non-negative preregistered replicate index |
| `solver_seed` | integer | yes | Preregistered seed |
| `operator_set_id` | string | yes | Frozen set/portfolio evaluated |
| `candidate_id` | string or null | yes | Use for attributable single candidate; null for portfolio-only attribution |
| `portfolio_id` | string or null | yes | At least one of candidate/portfolio IDs must be non-null |
| `baseline_result_id` | string | yes | Exact paired baseline result |
| `generated_result_status` | string | yes | Original generated result state |
| `baseline_result_status` | string | yes | Must be valid for a localized policy value |
| `relative_improvement` | number or null | yes | `(baseline - generated) / baseline`; positive is better; observed value requires finite baseline makespan `> 0`; null for batch-inconclusive |
| `cell_failure_mapping` | enum string | yes | `observed_generated_value`, `failure_zero_policy`, `batch_inconclusive` |
| `fallback_used` | boolean | yes | Never attributed as generated result |
| `attributed_generated_success` | boolean | yes | True only for valid attributable generated execution |
| `included_in_primary_analysis` | boolean | yes | True for observed or policy-zero cells; false for batch-inconclusive |
| `supplementary_complete_case_eligible` | boolean | yes | Does not affect primary inclusion |
| `failure_type` | string | yes | Original localized or integrity failure label |

### 4.1 Failure mapping precedence

1. Validate objective, manifest, input, split, hash, lockbox scope, and baseline pairing integrity.
2. Any integrity violation produces `batch_inconclusive`, `relative_improvement=null`, and `included_in_primary_analysis=false` for the contaminated batch. It is not a cell zero.
3. Otherwise, a valid attributable generated result uses the observed relative improvement.
4. Otherwise, localized timeout, invalid solution, fallback, execution/deployment block, missing result, evaluator/runtime error, or no attributable generated result uses `failure_zero_policy` with `relative_improvement=0` and remains in primary accounting.

Failure-zero is a policy estimand, not a physical penalty. The original status, failure type, fallback flag, and attribution status remain visible.

## 5. Append-only lifecycle event record

`record_type = lifecycle_event` is the only transient-state stream. It records `event_type`, `scheduled_run_id`, optional `candidate_id`/`cell_id`, monotonic `event_sequence`, timestamp, status, reason, and referenced receipt IDs.

Expected sequence includes scheduling, provider result, source persistence/read, validation, execution gate, execution, contract check, benchmark, selection, freeze, deployment gate, attribution/fallback, cell accounting, and run closeout. Skipped stages require an explicit `not_reached` event and reason.

The `run_operator_type` record in Section 2 is a terminal closeout summary, not a mutable lifecycle row. Its final persisted `run_status` must be `blocked`, `failed`, `completed`, or `closed`; `scheduled` and `started` may appear only in lifecycle events or an explicitly marked nonterminal projection that cannot satisfy closeout reconciliation.

## 6. Summary records and denominators

Pilot summaries must separately report:

- scheduled-run closure rate: closed scheduled runs / all scheduled runs;
- valid deployable portfolio rate: runs with a valid deployable portfolio / all scheduled evolution runs;
- cell failure rate: localized failure-zero cells / all preregistered non-contaminated cells;
- family evaluable rate: families with their complete preregistered cell grid / all scheduled non-contaminated families;
- fallback rate: fallback-used attempts / all relevant execution/deployment attempts;
- attributed generated success rate: attributable generated-success cells / all preregistered non-contaminated generated-method cells.

Numerators and denominators must be emitted, not only rates.

## 7. Integrity and replay

- Records are immutable and append-only; correction creates a superseding record with reason and predecessor ID.
- Closeout verifies foreign keys, one run/operator-type summary per scheduled key, unique candidate/cell IDs, complete scheduled-run reconciliation, and receipt/hash bindings.
- Replay recomputes derived statuses and summaries without provider or candidate execution.
- All outputs remain `pilot_nonformal`, `non_formal_evidence=true`, and cannot support paper performance claims.
