# Mock/File Provider Validation Plan

## 1. Purpose and limits

This is a future pilot design, not an executed validation. It uses no real LLM and makes no performance, quality, generalization, or cost claim.

The future validation must use only approved `pilot_nonformal` inputs after Gate P2. Every scenario begins with a scheduled-run record and ends with a structured run-accounting category, including early failures.

## 2. Common closed-loop assertions

Both mock and file providers must eventually demonstrate that:

1. candidate source, metadata, lineage, and code hash are persisted;
2. source-read, validation, execution, contract/feasibility, benchmark, selection, freeze, and deployment states are distinct;
3. execution eligibility is checked before smoke test/benchmark;
4. invalid, timeout, blocked, unsafe, fallback, or malformed candidates cannot enter best selection, freeze, or reward;
5. `not_evolved` and `no_valid_operator` have different meanings and output states;
6. freeze accepts only a candidate with complete positive eligibility evidence;
7. generated frozen deployment requires current runtime authorization rather than artifact claims;
8. fallback is observable and never counted as generated success or reward;
9. every scheduled run remains in accounting, including all-invalid/no-valid/deployment-blocked runs;
10. failure-zero mapping is recorded separately from the underlying failure type and is never presented as physical performance;
11. result rows contain the required reproducibility fields from `closed_loop_observability_plan.md`.

## 3. Mock provider plan

The mock provider should eventually emit deterministic candidate batches with fixed IDs and source hashes. Planned batches:

| Batch | Candidate outcomes | Expected closed-loop result |
|---|---|---|
| M1 success | One eligible valid operator plus dominated valid candidates | Eligible winner may reach freeze; complete evidence retained |
| M2 mixed failures | Validation failure, timeout, invalid solution, and one valid candidate | Only valid candidate may be selected; each failure keeps its own type |
| M3 all invalid | No eligible candidate | Explicit `no_valid_operator`; no fallback/template freeze |
| M4 not scheduled | Operator type intentionally absent from evolution schedule | `not_evolved`, not `no_valid_operator` |
| M5 deployment blocked | Eligible frozen artifact without current runtime deployment authorization | Structured deployment block and fallback; no generated success/reward |
| M6 fallback execution | Frozen generated operator import/runtime/contract failure | Built-in fallback may run, but attribution remains false/zero |

For every batch, the future pilot should compare expected and actual lifecycle transitions, not makespan superiority.

## 4. File provider candidate plan

### A. Legal candidate

Planned properties:

- correct operator interface and declared type;
- no forbidden import, call, reflection, or file/network/subprocess capability;
- stable source hash;
- valid return shape and feasible task assignment;
- complete runtime/eligibility metadata.

Expected path:

`source_read_success → validation_success → execution_eligible → execution_success → valid_solution → benchmark_evaluable → selection_eligible → freeze_eligible → deployment_gate`

Deployment still depends on current runtime authorization. Passing validation/freezing is not deployment authority.

### B. Executable but invalid candidate

Planned variants include duplicate tasks, missing tasks, malformed route/removed-task shapes, wrong task-ID type, or inconsistent destroy output.

Expected behavior:

- source and AST validation may succeed;
- execution may complete;
- contract/feasibility status becomes `invalid_solution` or a specific `contract_violation` subtype;
- candidate receives no best eligibility, freeze eligibility, generated reward, or generated success;
- scheduled-run accounting retains the outcome; if no valid candidate remains, use `no_valid_operator`.

### C. Unsafe candidate

Planned sources separately exercise `open`, `os`, `subprocess`, `socket`, `pathlib`, `FileIO`, `builtins`, `getattr`-based access, and prohibited dunder/reflection patterns.

Expected behavior:

- AST/security validation rejects the source;
- smoke test, benchmark, dynamic import, selection, freeze, and deployment are never reached;
- failure is `validation_failed` with an unsafe-pattern diagnostic, not `runtime_error` or `timeout`;
- source/code hash and validation evidence remain observable.

### D. Blocked generated frozen deployment

Planned artifact has otherwise complete validation/freeze evidence but lacks current runtime deployment authorization.

Expected behavior:

- artifact metadata cannot self-authorize deployment;
- registry/ALNS does not register a generated `CandidateProxy`;
- structured status is `missing_runtime_deployment_authorization` or equivalent;
- built-in fallback may be selected for robustness with `fallback_used=true` and a reason;
- generated success and reward attribution remain false/zero.

## 5. Expected eligibility matrix

| Case | Execute | Benchmark | Select | Freeze | Deploy generated | Generated reward |
|---|---:|---:|---:|---:|---:|---:|
| Legal + complete execution evidence | Yes | Yes | Yes | Yes | Only with runtime deployment authorization | Only for attributable generated success |
| Contract/feasibility invalid | Yes | No/invalid record only | No | No | No | No |
| AST/security unsafe | No | No | No | No | No | No |
| Timeout/runtime error | Attempted/failed | No valid benchmark | No | No | No | No |
| Execution blocked | No | No | No | No | No | No |
| Frozen deployment authorization missing | Earlier stages may pass | Earlier benchmark may exist | Earlier selection may exist | Earlier freeze may exist | No; fallback only | No |
| Fallback result | Built-in path only | Report separately | Never as generated best | Never as generated freeze | Built-in only | No generated reward |

## 6. Scheduled-run and failure-zero planning

The future pilot must precreate scheduled run IDs and retain:

- successful generated run;
- all-invalid/no-valid run;
- freeze failure;
- deployment-blocked run;
- fallback run;
- provider/source-read/validation/execution failure run.

Where the governing pilot accounting policy maps a generated-method evaluation cell to zero relative improvement, record both the zero policy value and the original failure/status fields. Do not delete failed cells/runs, substitute fallback makespan as generated improvement, or interpret zero as a physical penalty.

## 7. Review gate

Before execution, reviewers must approve fixture intent, expected state transitions, safety non-execution assertions, runtime authorization configuration, manifest scope, and result-row schema. Approval closes no Gate B or Phase 7 item.
