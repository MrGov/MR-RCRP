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

The config samples early/middle/stagnation states from two manifest-qualified development instances (BASE and HV-GEOM), checks 12 historical E17 repair artifacts on 72 paired states, and sends at most two outcome-distinct candidates to short ALNS. Each ALNS group has a one-second wall-clock budget, one-use exploration for every registered repair, fixed priced local search and the same acceptance policy. After development selection is frozen, the chosen method runs once on a third development instance (SPATIAL); this is held out from this run's feedback/selection, not independent of prior project development. The exact-DP initializer comparison is kept separate from operator evolution. The runner validates source and manifest hashes and refuses to overwrite an existing output directory. Provider calls remain disabled (`max_calls=0`, `max_tokens=0`); the current output is `outputs/operator_portfolio_evolution/run_012/portfolio_evolution.json`. It records prompt and source hashes, paired DP state-chain evidence, calls/acceptance/improvements/time per repair, LLM accounting, and stop reason. The output-selection rule rejected both behavior-shortlisted candidates and kept one generated repair.

To change the output directory before rerunning, edit `output_dir` in the JSON config and choose a new path. Each run refuses to overwrite its output. Do not enable provider calls without explicit call and spend authorization. For a future two-call revision, the prepared budget is at most 15,600 estimated tokens (one child per call, at most 1,800 output tokens per call, no retries); the configured endpoint's USD pricing is not verified, so this is not a dollar-cost cap.

## Focused Tests

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/test_instance_loader.py tests/test_baseline_solver.py tests/test_dp_evaluator.py tests/test_alns_solver.py -q
```

For a change, run the directly related test modules and state the exact verification scope. Do not use this historical command as a substitute for tests required by a broader change.

## Historical Environment Notes

Earlier versions of this runbook named `C:\Anaconda\python.exe` and a workspace under `C:\VScode\...`; those are personal-machine examples, not portable requirements. The E13-Fix smoke notes used `G:\Anaconda\envs\mrta_env\python.exe` on one workstation. These paths were not verified on other machines.

Smoke inputs are not paper-grade performance evidence. Follow [`../data/README.md`](../data/README.md) and [`experiment_protocol.md`](experiment_protocol.md) for split and comparison rules. Final-test access remains governed by [`final_test_lockbox_protocol.md`](final_test_lockbox_protocol.md); this runbook does not authorize it.
