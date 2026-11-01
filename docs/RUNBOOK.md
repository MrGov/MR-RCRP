# Runtime Runbook

## Environment

Use Python 3.11 or newer in the project environment. Run commands from the `mrta_rect_coverage/` project root and set `PYTHONPATH=src`. Commands below use `python` from the active environment; a machine-specific absolute interpreter path is not part of the project contract.

## Main Solver

```powershell
$env:PYTHONPATH='src'
python -m mrta_rect_coverage.main --config configs/default.yaml
```

The configured instance and output paths are relative to the project root. The default config selects ALNS/B1. Inspect `configs/default.yaml` before running if local edits changed it.

## Focused Tests

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/test_instance_loader.py tests/test_baseline_solver.py tests/test_dp_evaluator.py tests/test_alns_solver.py -q
```

For a change, run the directly related test modules and state the exact verification scope. Do not use this historical command as a substitute for tests required by a broader change.

## Historical Environment Notes

Earlier versions of this runbook named `C:\Anaconda\python.exe` and a workspace under `C:\VScode\...`; those are personal-machine examples, not portable requirements. The E13-Fix smoke notes used `G:\Anaconda\envs\mrta_env\python.exe` on one workstation. These paths were not verified on other machines.

Smoke inputs are not paper-grade performance evidence. Follow [`../data/README.md`](../data/README.md) and [`experiment_protocol.md`](experiment_protocol.md) for split and comparison rules. Final-test access remains governed by [`final_test_lockbox_protocol.md`](final_test_lockbox_protocol.md); this runbook does not authorize it.
