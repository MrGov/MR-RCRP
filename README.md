# MR-RCRP Research Solver

This repository studies an LLM-assisted evolutionary-computation method for multi-robot rectangular coverage scheduling. The LLM generates or revises ALNS operators offline; ALNS searches task assignments and visit orders; Exact Route-DP selects coverage states and evaluates fixed routes. The objective is makespan under the model documented in [`docs/modeling_decisions.md`](docs/modeling_decisions.md).

## Run

From this project directory with Python 3.11+ and dependencies installed:

```powershell
$env:PYTHONPATH='src'
python -m mrta_rect_coverage.main --config configs/default.yaml
```

`configs/default.yaml` runs the configured B1 ALNS solver on its development/smoke instance and writes visualization output beneath `outputs/`. For an explicit E12 literature-comparison development run, see the command and fixed sample description in [`docs/experiment_protocol.md`](docs/experiment_protocol.md). Do not use that command with test split inputs.

The current structural-population experiment is described in
[`docs/operator_evolution.md`](docs/operator_evolution.md). Its bounded real-call
entry point is:

```powershell
$env:PYTHONPATH='src'
python -m mrta_rect_coverage.experiments.structural_population --config configs/structural_population.json
```

An existing output directory is refused unless `--resume` is explicit. Resume
uses recorded requests and completed evaluations; it does not retry uncertain
provider calls. `configs/structural_population.json` freezes the current batch's
data, budgets and 32-request ceiling. Frozen deployment can be replayed without
model calls using `python -m mrta_rect_coverage.experiments.structural_deploy --help`.

## Documentation

Start with [`docs/README.md`](docs/README.md), then read:

1. [`docs/research_positioning.md`](docs/research_positioning.md) for the single current research objective and claim boundaries.
2. [`docs/program_status_and_design.md`](docs/program_status_and_design.md) for implementation facts, experiment evidence and unresolved checks.
3. [`docs/modeling_decisions.md`](docs/modeling_decisions.md) for the mathematical model.
4. [`docs/experiment_protocol.md`](docs/experiment_protocol.md) and [`data/README.md`](data/README.md) before interpreting or running experiments.

`AGENTS.md` gives repository-wide engineering guidance. Historical plans, reports, and raw experiment outputs remain available for provenance; their status is indexed in `docs/README.md`.
