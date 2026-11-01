# Runtime Runbook

## Environment

Use Python 3.11 or newer in the project environment. Run commands from the `mrta_rect_coverage/` project root and set `PYTHONPATH=src`. Commands below use `python` from the active environment; a machine-specific absolute interpreter path is not part of the project contract.

## Main Solver

```powershell
$env:PYTHONPATH='src'
python -m mrta_rect_coverage.main --config configs/default.yaml
```

The configured instance and output paths are relative to the project root. The default config selects ALNS/B1. Inspect `configs/default.yaml` before running if local edits changed it.

## Problem-State Repair Portfolio Replay

Run the small offline candidate replay and matched short ALNS checks:

```powershell
$env:PYTHONPATH='src'
python -m mrta_rect_coverage.experiments.operator_portfolio_evolution --config configs/operator_portfolio_evolution.json
```

The config uses one manifest-qualified development instance for state-based selection and a second for a one-pass stage-end check. It is fixed at 12 baseline trace iterations, 12 candidate repair sources, 36 paired repair evaluations, two repair slots, one short ALNS seed, and 12 deployment iterations. It also compares `spatial_sort` with the exact-DP insertion constructor; this initializer check is kept separate from the operator comparison. The runner validates source and manifest hashes and refuses to overwrite an existing output directory. The current config has `llm.enabled=false`, `max_calls=0`, and `max_tokens=0`; it replays previously recorded E17 artifacts only. The completed run is `outputs/operator_portfolio_evolution/run_007/portfolio_evolution.json`; the current config defaults to a fresh `run_008` output and writes candidate hashes, paired outcomes, structural revision prompt, initialization and group-selection results, operator calls/rewards/acceptance/improvements/timing/fallbacks, LLM accounting, and stop reason.

To change the output directory before rerunning, edit `output_dir` in the JSON config and choose a new path. Do not enable provider calls without an explicitly authorized call/token budget. The stage-end entry is reported separately and does not influence candidate or deployment selection.

## Focused Tests

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/test_instance_loader.py tests/test_baseline_solver.py tests/test_dp_evaluator.py tests/test_alns_solver.py -q
```

For a change, run the directly related test modules and state the exact verification scope. Do not use this historical command as a substitute for tests required by a broader change.

## Historical Environment Notes

Earlier versions of this runbook named `C:\Anaconda\python.exe` and a workspace under `C:\VScode\...`; those are personal-machine examples, not portable requirements. The E13-Fix smoke notes used `G:\Anaconda\envs\mrta_env\python.exe` on one workstation. These paths were not verified on other machines.

Smoke inputs are not paper-grade performance evidence. Follow [`../data/README.md`](../data/README.md) and [`experiment_protocol.md`](experiment_protocol.md) for split and comparison rules. Final-test access remains governed by [`final_test_lockbox_protocol.md`](final_test_lockbox_protocol.md); this runbook does not authorize it.
