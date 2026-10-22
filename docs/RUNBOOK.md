# Core Runtime and R1 Scientific Correctness Runbook

## Environment

- Windows PowerShell
- Python executable: `C:\Anaconda\python.exe`
- Pytest executable: `C:\Anaconda\Scripts\pytest.exe`
- Set `PYTHONPATH=src` from the Python project root.

## Project and invocation

- Workspace root: `C:\VScode\20251217-yang\R_MRTA_01-copy`
- Python project root: `C:\VScode\20251217-yang\R_MRTA_01-copy\mrta_rect_coverage`
- Package: `mrta_rect_coverage`
- Canonical CLI: `C:\Anaconda\python.exe -m mrta_rect_coverage.main --config <config>`

Run commands from the Python project root:

```powershell
$env:PYTHONPATH='src'
C:\Anaconda\python.exe -m mrta_rect_coverage.main --config configs/runtime_smoke_baseline.yaml
C:\Anaconda\python.exe -m mrta_rect_coverage.main --config configs/runtime_smoke_alns.yaml
C:\Anaconda\python.exe -m mrta_rect_coverage.main --config configs/runtime_smoke_baseline_t10.yaml
C:\Anaconda\python.exe -m mrta_rect_coverage.main --config configs/runtime_smoke_alns_t10.yaml
```

## Inputs and outputs

- `data/R2_T6_0.txt`: 2 robots, 6 tasks, sweep width 2.0, sweep speed 1.0, travel speed 1.0, turning time 0.5.
- `data/R2_T10_0.txt`: 2 robots, 10 tasks, sweep width 3.0, sweep speed 1.0, travel speed 1.0, turning time 5.0.
- Smoke configs use built-in operators, `advisor_mode: none`, no frozen/generated operators, and 20 ALNS iterations.
- Outputs are written to `outputs/r0_smoke/`.

## Verification target

The authorized core test target is:

```powershell
C:\Anaconda\Scripts\pytest.exe tests/test_instance_loader.py tests/test_baseline_solver.py tests/test_dp_evaluator.py tests/test_alns_solver.py -q
```

R1 scientific-correctness contracts are covered by
`tests/test_scientific_correctness.py`. Complete-solution evaluation requires
the exact task universe; ALNS partial states use `evaluate_partial()`.

R0 validity checks require two routes, the exact task universe once each, finite Route-DP costs, finite makespan, and `makespan == max(route_costs)`. Baseline and ALNS T6 runs use seed 0 and are reproducible for routes, per-route costs, and makespan.

## Known limitations and boundaries

- These are runtime smoke instances, not paper-grade benchmark evidence.
- Both smoke inputs explicitly set `sweep_speed == travel_speed == 1.0`, so their R0 objective values remain unchanged after the R1 unit correction.
- `dp_aware_insertion` is not a selectable repair or benchmark mode; all real insertion operators already use exact Route DP.
- A pre-existing Matplotlib warning is emitted by `visualization/plot_solution.py:118`: legend handles for `Annotation` instances are unsupported. It does not change solver outputs.
- R0 uses no real LLM/provider, generated candidate, pilot, benchmark, formal experiment, large-scale experiment, or final-test data.
- Gate P2 remains OPEN. T6 remains NOT AUTHORIZED.
- R0 completion does not authorize R1; the next permitted recommendation is `R1 - Scientific Correctness`.

## R2 sanity data protocol

`src/mrta_rect_coverage/experiments/dataset_protocol.py` provides the
deterministic generator, intrinsic feature extractor, and split-scoped
manifest loader. The checked-in sanity artifacts live under
`data/r2_sanity/` with manifests in `manifests/`. They are parser/provenance
validation inputs only, not formal benchmark data. Do not replace manifest
access with a `data/R*_T*_*.txt` glob.
