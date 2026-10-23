# MRTA Rectangular Coverage Research Framework

## Project Overview
This repository now contains both:
- a stable baseline solver pipeline
- a research-stage ALNS framework with problem-specific operators and pluggable advisor interfaces

The target problem is multi-robot rectangular coverage routing (MR-RCRP): robots start at depot `(0, 0)`, cover assigned rectangles, and return to depot, minimizing makespan.

## Installation
1. Python 3.11+
2. Optional virtual env
3. Install deps:
```bash
pip install -r requirements.txt
```

## Quick Start
Run with config:
```bash
PYTHONPATH=src python -m mrta_rect_coverage.main --config configs/default.yaml
```

Default config keeps baseline mode enabled. To run ALNS, set:
```yaml
solver:
  algorithm: alns
```

## Objective and feasibility contracts

The six-line instance format uses four values on line 2:

```text
sweep_width sweep_speed travel_speed turning_time
```

Coverage processing and travel are both measured in time:

- `processing_time = coverage_length / sweep_speed + turn_count * turning_time`
- `travel_time = ManhattanDistance / travel_speed`
- route time includes depot-to-first, inter-task, and last-to-depot travel time

Both speeds must be finite and positive. Legacy three-value line-2 inputs are
rejected because they do not state a travel speed.

`MultiRobotSolutionEvaluator.evaluate()` accepts only complete solutions with
exactly one route per robot and every known task assigned exactly once. Empty
robot routes are legal. ALNS destroy states use the separate
`evaluate_partial()` entry point, which permits missing tasks but still rejects
unknown or duplicate task IDs and incorrect route counts.

## Baseline and Deterministic Core
Current deterministic core includes:
- instance parsing/validation with filename rule `R{R}_T{T}_{rep}.txt`
- state generation (8 corner/mode candidates per task)
- DP route evaluation with cache keyed by `route_task_ids`
- richer route evaluation traces:
  - chosen state ids/states
  - entry/exit points
  - cumulative DP costs
  - transition costs
  - predecessor chain
- lower bounds:
  - `simple_average_processing_lb`
  - `processing_with_travel_lb`
  - `processing_with_connectivity_lb`
- stronger local-search neighborhoods:
  - inter-route relocate
  - intra-route swap
  - intra-route 2-opt
  - inter-route swap
  - bottleneck-focused relocate

## ALNS Research Solver
Implemented in [`src/mrta_rect_coverage/heuristics/alns_solver.py`](/d:/vs_code/20251217-yang/R_MRTA_01/mrta_rect_coverage/src/mrta_rect_coverage/heuristics/alns_solver.py).

### Destroy Operators
- `random_destroy`
- `bottleneck_route_destroy`
- `geometry_aware_destroy` (problem-specific)

### Repair Operators
- `greedy_insertion`
- `regret_k_insertion`
- `bottleneck_balancing_insertion`

All insertions evaluate candidate route insertions through route DP (`RouteDPEvaluator`) rather than fixed surrogate service times.
The private `dp_aware_insertion` compatibility method is an exact alias of
`greedy_insertion`; it is not registered as a selectable operator and is not an
independent contribution or ablation.

### Adaptive and Acceptance Components
- adaptive operator scoring/weights (usage + reward accumulation)
- acceptance modes:
  - `improvement_only`
  - `simulated_annealing`
- outputs:
  - best solution
  - best makespan
  - iteration history
  - operator usage stats

## Problem-Specific Research Components
1. Exact Route-DP evaluation is shared by all insertion operators.
2. Geometry-aware destroy prioritizes rectangle aspect ratio and sweep-time imbalance.
3. Bottleneck-focused refinement targets the critical route/makespan contributor.

## Advisor Layer (No Real API)
Advisor interface in [`src/mrta_rect_coverage/llm/advisor_interface.py`](/d:/vs_code/20251217-yang/R_MRTA_01/mrta_rect_coverage/src/mrta_rect_coverage/llm/advisor_interface.py):
- `suggest_operator(context)`
- `suggest_destroy_repair(context)`
- `suggest_search_phase(context)`

Context includes:
- best makespan
- per-route costs
- bottleneck route id
- recent improvement history
- operator performance summary

Implemented advisors:
- `MockAdvisor`
- `RuleBasedAdvisor`

ALNS supports:
- no advisor
- mock advisor
- rule-based advisor

## Visualization
- existing solution plot retained: [`plot_solution.py`](/d:/vs_code/20251217-yang/R_MRTA_01/mrta_rect_coverage/src/mrta_rect_coverage/visualization/plot_solution.py)
- new search plots:
  - convergence curve
  - operator usage histogram

## Benchmark and Ablation
Batch benchmark runner:
[`src/mrta_rect_coverage/experiments/benchmark_runner.py`](/d:/vs_code/20251217-yang/R_MRTA_01/mrta_rect_coverage/src/mrta_rect_coverage/experiments/benchmark_runner.py)

Ablation modes:
- `baseline`
- `baseline_stronger_ls`
- `alns`
- `alns_advisor`

`alns_dp_aware` is deliberately rejected: the former repair was only a greedy
compatibility alias, so treating it as an independent benchmark mode would make
the ablation scientifically invalid.

Example usage in Python:
```python
from pathlib import Path
from mrta_rect_coverage.experiments.benchmark_runner import run_batch_benchmark

run_batch_benchmark(
    data_dir=Path("data"),
    output_csv=Path("outputs") / "benchmark_results.csv",
    modes=["baseline", "baseline_stronger_ls", "alns", "alns_advisor"],
)
```

## Config Highlights
New config fields in [`src/mrta_rect_coverage/config.py`](/d:/vs_code/20251217-yang/R_MRTA_01/mrta_rect_coverage/src/mrta_rect_coverage/config.py):
- `solver.algorithm`: `baseline | alns`
- `solver.local_search.use_stronger`
- `solver.alns.iterations`
- `solver.alns.acceptance`
- `solver.alns.destroy_fraction`
- `solver.alns.use_dp_aware_insertion`: deprecated compatibility field; `true` is rejected
- `solver.alns.advisor_mode`: `none | mock | rule_based`

## Test Suite
Run tests:
```bash
pytest -q
```

## R2 Data Protocol

The deterministic paper-data protocol is implemented in
`src/mrta_rect_coverage/experiments/dataset_protocol.py`. It generates only
the small sanity set under `data/r2_sanity/` and records SHA-256-verified,
split-scoped manifests under `manifests/`. Access is manifest-driven and does
not glob `data/`; the manifests contain no solver outcomes. See
`docs/dataset_protocol.md`, `docs/instance_families.md`, and
`docs/final_test_protocol.md`. R2 does not run formal benchmarks, provider or
candidate execution, operator evolution, tuning, or final-test solver runs.

The suite covers baseline components and new research modules (cache, lower bound, ALNS, advisor, stronger local search, benchmark runner).

## Offline Operator Evolution (Repair-first)

A new subsystem is available at `src/mrta_rect_coverage/llm/operator_evolution/`.

Key points:
- Main target: evolve **repair operators** in a closed offline loop.
- Secondary target: lightweight destroy operator evolution.
- Not included: initialization operator generation, online LLM control, hard SDK bindings.

Workflow:
1. generate candidates (via `mock`, `file`, or `langchain_openai_compatible` provider)
2. controlled load + validation (import/signature/smoke)
3. benchmark evaluation on fixed small instances and seeds
4. metrics aggregation + structured feedback
5. next-round revision
6. freeze best operators and plug into ALNS

### Providers

| Provider | Description |
|----------|-------------|
| `mock` | Deterministic templates, no external API |
| `file` | Writes prompts to files, reads manually produced candidates |
| `langchain_openai_compatible` | Calls a real LLM via LangChain ChatOpenAI (any OpenAI-compatible endpoint) |

### Quick start (mock)
```bash
python -m src.mrta_rect_coverage.experiments.operator_evolution_runner --provider mock --rounds 2 --freeze-best
```

### Using a real LLM (LangChain provider)

> **Safety warning:** generated Python is untrusted. The local execution boundary is a
> `timeout_only` subprocess, not a capability sandbox. Before permitting execution,
> review the generated source, use an isolated account/host with no secrets or network
> privileges, verify the recorded hash, and explicitly acknowledge the residual risk.
> Without that acknowledgement, real-provider candidates are statically validated but
> blocked before smoke testing, benchmarking, selection, or freezing.

1. Install optional dependencies:
```bash
pip install mrta-rect-coverage[llm]
# or: pip install python-dotenv langchain-openai
```

2. Configure environment:
```bash
cp .env.example .env
# Edit .env with your API key and endpoint
```

3. Run evolution:
```bash
python -m src.mrta_rect_coverage.experiments.operator_evolution_runner \
    --provider langchain_openai_compatible --rounds 3 --freeze-best
```

Supported endpoints include OpenAI, DeepSeek, Ollama, and Azure OpenAI. See [.env.example](.env.example) and [docs/operator_evolution.md](docs/operator_evolution.md) for details.

### ALNS integration

ALNS can load frozen operators via config fields under `solver.alns`:
- `frozen_operator_registry_path`
- `use_frozen_repair`
- `use_frozen_destroy`

### E3 search control profiles

`ALNSConfig()` preserves B0: cumulative mean rewards, improvement-only acceptance,
and 200 iterations. `ALNSConfig.enhanced()` selects B1: segment reaction weights
and simulated annealing. Both use the same operators, rewards, local search,
feasibility checks, and Exact Route-DP. Existing generated repair interfaces are unchanged.
The CLI's `configs/default.yaml` now selects B1 and one second per task;
`configs/e3_b0.yaml` preserves the B0 controls for matched-time comparisons.
Existing programmatic callers of `ALNSConfig()` retain their earlier behavior.

B1 updates used operators every 20 iterations with
`w = max(0.1, (1 - 0.2) * w + 0.2 * segment_reward / segment_uses)`;
unused operators retain their weights. Lifetime usage/reward statistics remain available.
Its initial temperature is `T0 = -0.01 * initial_makespan / log(0.5)`:
a 1% worsening initially has 50% acceptance probability. The temperature decreases
geometrically to `0.01 * T0` over budget progress. Global best is retained independently
of the accepted current solution.

For task-scaled runtime use `iterations=None, max_runtime_seconds=instance.task_count`.
The optional iteration and runtime bounds stop at the first reached. Runtime includes
initial evaluation and all search work, but excludes solver construction. Bounds are
checked between complete iterations, so an iteration can overrun the deadline;
actual elapsed time is returned. Results and history include completed iterations,
elapsed seconds, and Route-DP calls (including bounded generated repair calls).

Run from the project directory in PowerShell with the existing environment:

```powershell
$env:PYTHONPATH='src'
& 'G:\Anaconda\envs\mrta_env\python.exe' -m mrta_rect_coverage.main --config configs/e3_b1.yaml
& 'G:\Anaconda\envs\mrta_env\python.exe' -m mrta_rect_coverage.main --config configs/e3_b0.yaml
& 'G:\Anaconda\envs\mrta_env\python.exe' -m mrta_rect_coverage.experiments.e3_alns --output outputs/e3_alns_rerun
```

The E3 development comparison fixes four existing instances (10/20/40/80 tasks,
2/4/8 robots), seeds 0 and 1, the spatial-sort constructor, and one second per task.
Each run saves its exact configuration, initial/best routes, feasibility-checked
makespan, actual runtime/overrun, DP calls/cache misses, and convergence history.
Use a fresh output directory to preserve earlier results. This experiment does not
call an LLM. `--smoke-only` separately checks an existing E2-R repair under B1.

### E4-A decision-oriented DP feedback

`select_decision_knowledge` in `llm/operator_evolution/feedback_builder.py` selects
parent-specific failure evidence for bottleneck transfer, coverage/turning geometry,
and route-state response. It uses canonical evaluator measurements, source references,
code anchors, and an improving contrast case. Rules select by decision relevance and
unique-instance support, without treating state switches or cascade as penalties.
`build_f2d_feedback` and the existing parent revision prompt consume this payload.
The repair contract still supplies no evaluator; generated code uses heuristic hints,
while the external Exact Route-DP determines feasibility and makespan.

The small E4 runner reuses frozen B1 and existing bounded candidate loading:

```powershell
$env:PYTHONPATH='src'
& 'G:\Anaconda\envs\mrta_env\python.exe' -m mrta_rect_coverage.experiments.e4_decision_feedback --stage compatibility
& 'G:\Anaconda\envs\mrta_env\python.exe' -m mrta_rect_coverage.experiments.e4_decision_feedback --stage evolve --condition F2-D
& 'G:\Anaconda\envs\mrta_env\python.exe' -m mrta_rect_coverage.experiments.e4_decision_feedback --stage evolve --condition F1
& 'G:\Anaconda\envs\mrta_env\python.exe' -m mrta_rect_coverage.experiments.e4_decision_feedback --stage evolve --condition F2
& 'G:\Anaconda\envs\mrta_env\python.exe' -m mrta_rect_coverage.experiments.e4_decision_feedback --stage evaluate
& 'G:\Anaconda\envs\mrta_env\python.exe' -m mrta_rect_coverage.experiments.e4_decision_feedback --stage short
& 'G:\Anaconda\envs\mrta_env\python.exe' -m mrta_rect_coverage.experiments.e4_decision_feedback --stage analyze
```

`evolve` calls the provider only when a saved response is absent. The other stages
run offline. Existing responses and per-run results are resumed. Add `--output` to
use a separate experiment directory; a fresh evolution directory incurs new calls.
E4 actual prompts, raw responses, sources/hashes, development selection, metrics,
convergence and interpretation are in `outputs/e4a_decision_feedback/REPORT.md`.
The saved F2-D prompt predates an interface wording clarification; its exact sent
text is preserved and results are not attributed to the unsent clarified version.
