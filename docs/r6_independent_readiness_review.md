# R6 Independent Readiness Review

Status: `Request changes`.

Scope: read-only review of the R4 frozen method, literature threat matrix, R5
mapping, trusted mock pipeline, tests, outputs, relevant R3 definitions and
execution boundaries. No production code, tests, provider, candidate, pilot,
benchmark, formal experiment or final-test path was changed or run.

## Fresh verification

- `tests/test_r5_mock_pipeline.py`: 17 passed.
- R2/R3 focused regression (`test_dataset_protocol.py`, `test_r3_analysis.py`,
  `test_r3_diagnostics.py`): 19 passed.
- Combined scoped target: 36 passed.
- Full suite: not run. Historical `*_red.py` tests remain intentional frozen
  capability-gate tests; the prior broad run recorded 10 failures and was not
  rewritten for a green result.
- Static R5 boundary scan: no dynamic import, `exec`, subprocess, network,
  legacy candidate-loader/proxy or final-test capability in the R5 module or
  its scoped tests.

## Findings

### Required 1 - Exact-DP profile is not computed or bound to R3 definitions

`r5_mock_pipeline.py` accepts behavior metrics as fixture metadata and derives
fixture values from a scalar quality value. It does not compute or validate the
R3 `state_chain_diff` contract (`state_changed_fraction`, `mode_switch_fraction`,
entry/exit counts, indirect-task cascade and its denominator) from an exact
Route-DP result. The R5 field `hv_mode_switch_fraction` is not shown to be the
R3 `mode_switch_fraction` definition. The current evidence therefore proves
schema presence only, not exact-DP metric compatibility.

### Required 2 - Structural-regime coverage is caller-supplied, not intrinsic

`select_complementary_set()` consumes `candidate.structural_regimes` directly.
`derive_structural_regimes()` exists, but is not called by candidate creation,
archive insertion or selection. Trusted fixtures provide arbitrary labels such
as `travel:balanced`, while their profile context contains only two intrinsic
features. A candidate can therefore claim regimes unrelated to its approved
instance features and win Stage 4.

### Required 3 - Lineage/source-hash binding is not verifiable

The archive verifies that parent IDs exist, but does not verify parent source
hashes, candidate source content, or a canonical parent-to-child hash preimage.
The mock provider hashes the parent's previous hash plus generation, while no
source text or source hash domain is persisted. This is an identity convention,
not true source-hash lineage binding required by R4/R6.

### Required 4 - Elite retention is recorded but not reused

`run_mock_pipeline()` records the best ID in `_elites`, but the next generation
is produced by regenerating the complete fixture list. No elite is injected
into parent selection, no retained source/hash is carried as an explicit elite
record, and no artifact proves reuse. The current Scenario B assertion only
checks that an elite ID exists and that some child has a parent.

### Required 5 - Persisted artifacts cannot reconstruct the full hierarchy

The in-memory ledger records `EvaluationAddress` values, but `_write_outputs()`
only writes budget entries to `evolution_runs.jsonl` and budget CSV/JSON. It
does not persist evaluation addresses. The emitted artifacts therefore cannot
reconstruct the required `evolution_run -> generation -> candidate -> instance
-> solver_seed` hierarchy or audit candidate/evaluation denominators.

### Required 6 - Trusted fixture allowlist is not enforced by the file provider

`TrustedFixtureFileProvider` validates a JSON shape and `dry_run=True`, but
accepts any fixture ID/operator type/source hash supplied by the manifest. It
does not compare entries against a registered trusted-fixture allowlist or
verify the declared hash against an approved fixture registry. No unsafe Python
execution is reachable from this module, so this is not currently Critical;
however the trusted-fixture boundary is not enforceable as specified for a
future provider-facing path.

## Non-blocking considerations

- `docs/r5_contract_to_code_mapping.md` still says implementation is “in
  progress” although R5 is complete; this is documentation drift.
- `build_structured_feedback(..., mode="F3")` embeds a C2 counterexample
  payload. The C3 schema builder itself exists and is tested, but the mode
  distinction should be made explicit before any future real-provider stage.
- `BudgetLedger.assert_equal_budget()` checks equality among recorded entries,
  but no independent F0/F1/F2/F3 run comparison is produced by R5.

## Gate decision

- Critical: 0
- Required: 6
- Consider: 3
- Verdict: **Request changes**
- `REAL_PROVIDER_GENERATION_READY = FALSE`
- `UNTRUSTED_EXECUTION_READY = FALSE`
- Gate P2: OPEN
- T6: NOT AUTHORIZED
- R6A: not recommended until the Required findings are repaired and reviewed.

R5 remains a valid trusted-fixture plumbing demonstration, but it is not yet
evidence that the frozen R4 mechanism is ready for a real-provider
generation-only pilot. No claims of LLM effectiveness, DP-feedback benefit,
complementary-set benefit, generalization, novelty or SOTA are permitted.
