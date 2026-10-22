# R5 Trusted Mock/File Research Pipeline

R5 implements the frozen R4 plumbing over structured trusted fixtures. It does
not execute provider-generated Python and does not invoke the legacy candidate
loader/proxy path.

## Boundary

- Provider mode is deterministic fixture metadata only.
- File mode accepts one explicit JSON fixture manifest and requires `dry_run=True`.
- No dynamic import, `exec`, subprocess, network, pilot, benchmark, formal run,
  final-test access or T6 path is available through this pipeline.
- Gate P2 remains `OPEN`.

## Contracts

`OperatorBehaviorProfile` records exact-DP response, assignment/bottleneck,
objective decomposition, reliability and cost fields. `StructuredOperatorFeedback`
supports F0 scalar/rank, F1 top/weak, F2 exact-DP behavior and F3 structured
counterexamples. `OperatorArchive` retains source hashes, real parent IDs,
selection-validation split, eligibility reasons and explicit elites.

C2 selection is lexicographic: eligibility, quality floor, quality anchor,
structural-regime marginal coverage, normalized exact-DP response distance, then
fixed `K` in `[1,4]`. No weighted-sum objective is used.

## Verification

The scoped test file is `tests/test_r5_mock_pipeline.py`. The end-to-end output
is written only when explicitly requested to `outputs/r5_mock_pipeline/` and
contains JSON/JSONL/CSV audit artifacts, feedback payloads and selection trace.

R5 evidence supports only: “the frozen research pipeline operates end-to-end
under trusted mock/file fixtures.” It does not support effectiveness,
generalization, novelty, SOTA or final-test claims.
