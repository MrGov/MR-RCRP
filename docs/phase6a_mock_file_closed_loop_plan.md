# Phase 6A Mock/File Closed-Loop Planning

## 1. Status and authority

Phase 6A is a **planning-entry phase only**. It designs a future mock/file-provider pilot but does not execute one.

- Phase 6A does not run mock, file, or real providers.
- Pilot execution requires a separate Gate P2 review and explicit authorization.
- Formal experiments require Gate B; Gate P1 or Gate P2 cannot close Gate B.
- Real LLM use requires a later Phase 7 preflight, explicit risk acknowledgement, and runtime authorization.
- No Phase 6A artifact or planned pilot result may be used as paper performance evidence.
- Phase 6A does not create, read, hash, locate, or infer final-test matrices, manifests, files, identities, hashes, features, or performance.

The only authorized output is an executable design for a later `pilot_nonformal` mock/file closed loop.

## 2. Planning objectives

The future pilot is intended to answer structural questions, not optimization-performance questions:

1. Can provider output be persisted with stable candidate/run identities?
2. Do validation and execution gates produce distinct, auditable states?
3. Are ineligible candidates excluded from benchmark, selection, freeze, deployment, feedback, and reward?
4. Can an eligible frozen artifact be deployed only through the required runtime authorization boundary?
5. Are fallback and generated-operator attribution separated?
6. Are failed scheduled runs retained under the preregistered accounting policy?
7. Can every result be traced to a pilot manifest, candidate code hash, execution receipt, and deployment decision?

The pilot must not rank methods for a paper, tune a formal portfolio, or produce a final-test claim.

## 3. Planned closed-loop sequence

The future execution path is frozen conceptually as:

1. Load an approved `pilot_nonformal` manifest through a manifest-only runner.
2. Create a `scheduled_run_id` before candidate generation; a failure before generation still produces a run record.
3. Obtain candidates from mock or file provider fixtures and persist source, metadata, lineage, and code hash.
4. Run source-read and AST/security validation.
5. Apply the unified execution eligibility gate before smoke test or benchmark.
6. Execute eligible candidates through the existing timeout-limited subprocess boundary; it is not a capability sandbox.
7. Validate repair/destroy contracts and feasibility.
8. Benchmark only eligible, successfully executed, valid candidates against the fixed evaluation protocol.
9. Apply fail-closed selection and freezing.
10. Apply the generated-frozen deployment authorization gate before registration.
11. Execute an authorized deployment path or record structured fallback without generated success/reward attribution.
12. Emit candidate-, deployment-, cell-, and scheduled-run-level observability records.
13. Apply failure-zero accounting only as the planned pilot policy estimand, while separately reporting failure/fallback/deployment rates.

No stage may silently skip to a later stage. Every early exit must retain the scheduled run and a structured failure reason.

## 4. Provider-specific scope

### 4.1 Mock provider

The mock path plans deterministic candidate batches that exercise successful and failed lifecycle branches. It validates orchestration, state transitions, evidence completeness, and accounting. It does not stand in for real-LLM quality.

### 4.2 File provider

The file path plans auditable source fixtures for:

- legal and feasible candidates;
- executable but contract-invalid candidates;
- AST/security-invalid candidates that must never execute;
- generated frozen artifacts blocked by missing runtime deployment authorization.

Fixtures are pilot-only test inputs. They must never be promoted into a formal operator portfolio.

## 5. Planned artifact flow

| Artifact | Producer | Required consumer | Forbidden use |
|---|---|---|---|
| Pilot family matrix and split rule | Future pilot setup | Pilot manifest validator | Formal manifest or lockbox |
| `pilot_nonformal` manifest | Future pilot setup | Pilot manifest-only runner | Formal runner input |
| Candidate source and metadata | Mock/file provider | Validator and execution gate | Direct unvalidated import |
| Validation/execution receipt | Boundary modules | Benchmark/selection eligibility | Success inference from missing fields |
| Frozen artifact record | Freezing stage | Deployment gate | Deployment authorization evidence |
| Runtime deployment authorization | Current runtime policy | Frozen deployment gate | Artifact self-authorization |
| Candidate/cell/run result rows | All stages | Pilot accounting/report | Paper performance evidence |
| Pilot-artifact exclusion receipt | Pilot closeout | Future formal joint preflight | Final-test information channel |

## 6. Planned failure handling

- Source-read, validation, execution, feasibility, optimization, structural, freeze, and deployment statuses remain separate axes.
- `invalid_solution`, `timeout`, `execution_blocked`, unsafe validation, fallback, and missing authorization cannot enter best/freeze/reward paths.
- `not_evolved` means an operator type was not scheduled for evolution; `no_valid_operator` means it was scheduled but produced no eligible candidate.
- Fallback can preserve solver robustness but cannot be attributed as generated success or generated reward.
- Every scheduled failure run remains in scheduled-run accounting.
- The future pilot records failure-zero values only according to the frozen policy mapping; it does not reinterpret zero as physical performance.

## 7. Exit from Phase 6A planning

Phase 6A planning is ready for review when the five Phase 6A documents:

- define one consistent pilot identity and manifest scope;
- define mock/file cases and expected lifecycle states;
- define required observability fields and accounting categories;
- list Gate P2 evidence requirements;
- enumerate Phase 6B infrastructure tasks without implementing them;
- retain all real-provider, pilot-execution, formal-experiment, large-scale, and final-test prohibitions.

Approval of this plan permits only the next separately authorized planning/review step. It does not automatically enter Phase 6B or execute a pilot.
