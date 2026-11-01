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

To change the output directory before rerunning, edit `output_dir` in the JSON config and choose a new path. The replay's zero LLM budget applies to that historical replay only. SPATIAL has been consumed in preparation runs and must be treated as development regression data.

## Authorized Gap Revision Batch

The 2026-11-01 authorized batch is complete in `outputs/operator_gap_revision/batch_001`. It made two real requests to the existing configured `gpt-5.6-sol`, produced two feasible children in one parent/child lineage, used 114,787 provider-reported tokens, and selected manual-only deployment. No paid call is needed to load and execute the saved choice:

```powershell
$env:PYTHONPATH='src'
python -m mrta_rect_coverage.experiments.operator_gap_revision --deploy-result outputs/operator_gap_revision/batch_001/results.json --deployment-output outputs/operator_gap_revision/batch_001/user_replay_001.json
```

Use a fresh output filename; existing files are refused. This replays the two recorded development instances with seeds 23/29 and a one-second solve budget, checks hashes/split identity, and records actual loaded members and calls. It is a development regression, not independent validation. On the current workstation, use `& 'G:\Anaconda\envs\mrta_env\python.exe'` in place of `python` if the PATH resolves to WindowsApps.

The original real-call command was:

```powershell
python -m mrta_rect_coverage.experiments.operator_gap_revision --config configs/operator_gap_revision.json
```

Its output directory already exists and the command now fails closed before making requests. Do not automatically open another paid batch. A separately authorized future batch needs a fresh output directory. The current config predeclares two generations, one candidate each, maximum 16 requests including failures, at most one engineering repair per candidate, 8,000 output tokens/request, no automatic retries, fixed evaluation and deployment rules. Provider/model/credentials come from the existing runtime configuration and are not printed. Dollar cost is recorded as unknown when unavailable. Each request saves its prompt, raw response, exact code, metadata and parent diff; `requests.json` is persisted before invocation. Historical outputs are not reused as new calls or new scores.

The final request-budget, shortlist, local-search consistency and provider configuration checks are:

```powershell
python -m pytest tests/test_operator_gap_revision.py tests/test_operator_portfolio_mechanism.py tests/test_llm_runtime_config.py tests/test_llm_client_factory.py -q
```

The complete suite passed 425 tests during the batch; the final targeted suite passed 21 tests, including an added failed-evaluation serialization regression. The saved `final_deployment.json` is a zero-call smoke replay of the selected manual pool; it does not revise selection. `cost_probe.py/json` preserve a separate post-selection executor-cost diagnostic. After noticing test-process overlap with part of the original deployment window, `timing_recheck.py/json` reran every group once after tests stopped; all four means and the manual-only selection were unchanged. These diagnostics made no provider calls and are not independent evaluations.

## Resident Executor / Replacement Recheck (No LLM Calls)

The existing lineage has been checked with both executor modes and only the five requested compositions. The completed output is `outputs/operator_gap_revision/executor_recheck_001`. To repeat the small study without overwriting it:

```powershell
$env:PYTHONPATH='src'
python -m mrta_rect_coverage.experiments.operator_gap_recheck --config configs/operator_gap_recheck.json --output outputs/operator_gap_revision/executor_recheck_002
```

This command never builds or invokes a model. It verifies the three frozen source identities, replays the six existing development states, compares original/resident execution at 40 fixed iterations, then calibrates one time budget from startup/loading/call costs and freezes it before timed comparisons. The completed run froze 2.4 seconds. Do not run tests or other heavy jobs concurrently with calibration/timing. Both modes retain subprocess validation and output checks; resident mode is permitted only for the explicitly reviewed hashes. Cold startup occurs inside solve, and full validation/loading/cleanup is included separately in end-to-end time. Budget overrun is recorded.

The recheck selected manual-only. Reloading its saved choice uses the corrected deployment entry point and makes no model calls:

```powershell
python -m mrta_rect_coverage.experiments.operator_gap_revision --deploy-result outputs/operator_gap_revision/executor_recheck_001/results.json --deployment-output outputs/operator_gap_revision/executor_recheck_001/user_replay_001.json
```

Use a fresh output filename. This is a replay of consumed development inputs, not an independent check. `summary.json` contains compact fixed/time results; `results.json` retains member statistics, workload and traces; `calibration.json` freezes the cost-derived budget. `next_prompt.txt` is an unsent 23,242-character sample with one true parent source and three deterministically selected cases. Its `current_composition` is the actual manual-only winner; the evolution parent is separately child 2. The actual old requests and sources remain untouched.

Required focused verification (32 tests passed for this change):

```powershell
python -m pytest tests/test_gap_deployment_revision.py tests/test_executor_equivalence.py tests/test_e13_persistent_execution.py tests/test_operator_gap_revision.py tests/test_operator_portfolio_mechanism.py -q
```

The focused suite includes both new children, repeated-call isolation, fixed-iteration solver traces, hash drift, timeout, invalid output, runtime failure and exception/early-exit cleanup. The full historical experiment system was not rerun. Execution acceleration alone is not evidence of improved operator quality; see the current status page for the C decision and its narrow development scope.

## Bounded Repair Strategy Prototype (Completed Development Batch)

`configs/bounded_repair_search.json` defines the new two-step host search and isolated pair-ranking experiment. `outputs/bounded_repair_search/run_001/analysis.json` is the compact result, `decision.json` contains the manual-only deployment decision, and `request_01/` → `request_02/` contains the real evaluated parent/child chain. Both candidates use the same host pricing/branching/completion kernel as the deterministic reference. This batch made two calls and is complete; do not automatically open another paid batch.

Commands below are the exact staged workflow. From the project directory, use the working local interpreter (the PATH `python` can be a WindowsApps stub):

```powershell
$env:PYTHONPATH='src'
& G:\Anaconda\envs\mrta_env\python.exe -m mrta_rect_coverage.experiments.bounded_repair_strategy --stage capability
& G:\Anaconda\envs\mrta_env\python.exe -m mrta_rect_coverage.experiments.bounded_repair_strategy --stage request --round 1
& G:\Anaconda\envs\mrta_env\python.exe -m mrta_rect_coverage.experiments.bounded_repair_strategy --stage evaluate --round 1
& G:\Anaconda\envs\mrta_env\python.exe -m mrta_rect_coverage.experiments.bounded_repair_strategy --stage request --round 2
& G:\Anaconda\envs\mrta_env\python.exe -m mrta_rect_coverage.experiments.bounded_repair_strategy --stage evaluate --round 2
& G:\Anaconda\envs\mrta_env\python.exe -m mrta_rect_coverage.experiments.bounded_repair_strategy --stage deploy
```

The existing output names are immutable: these commands now refuse to overwrite completed stages. `capability-evaluate` can finish an interrupted prepared capability run from its saved cases without resampling; it also refuses to overwrite a completed capability decision. Only `request` invokes the configured provider. A new run requires an explicitly chosen fresh `output_dir` in a copied config passed with `--config`; do not reuse historical responses as new calls. Requests are charged before invocation; the six-request ceiling includes failures, retries are disabled, and this driver requests one candidate in each of two rounds. No automatic model repair is performed. Deployment checks four prescribed groups on four development inputs and two seeds, at 40 iterations and 2.4 seconds; do not run tests or other heavy tasks concurrently.

The following **small local verification command is directly runnable now**, uses the saved candidates, makes no model requests and writes no historical results:

```powershell
& G:\Anaconda\envs\mrta_env\python.exe -m pytest tests/test_bounded_repair_search.py tests/test_bounded_strategy_candidates.py tests/test_langchain_provider_parsing.py tests/test_executor_equivalence.py tests/test_alns_solver.py tests/test_alns_search_control.py tests/test_e13_persistent_execution.py tests/test_gap_deployment_revision.py tests/test_operator_gap_revision.py -q
```

The recorded command passed **76 tests**. Actual-candidate tests are explicitly skipped if this local output batch is absent; all four were present and executed here. Runtime artifacts include explicit source hashes, original/resident checks, individual member calls and rewards, full per-state joint branches, feasible completed solutions, DP work, pricing work and initialization/worker startup costs. `analysis.json` clarifies that the old global `insertion_prices` statistic is a mixed operation counter; use `kernel_price_requests` for the new kernel's enforced insertion-slot budget. `summary.json` is retained as the initial extraction; its global `price_requests` label is qualified by this clarification and the corrected field in `analysis.json`.

For direct solver use, instantiate `BoundedRepairSearch(solver)` and call `solver.register_bounded_repair(kernel, name="bounded_reference")`. For an archived LLM strategy, use `with StrategyExecutor(candidate_path, expected_hash=recorded_hash) as policy`, construct the same kernel with `ranker=policy`, register it and solve inside the context. Never import generated candidate code into the main process. The selected default from this batch remains manual-only; explicit registration is an experiment opt-in. See the current status page for the negative/mixed LLM result and the single next cost hypothesis.

## Focused Tests

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/test_instance_loader.py tests/test_baseline_solver.py tests/test_dp_evaluator.py tests/test_alns_solver.py -q
```

For a change, run the directly related test modules and state the exact verification scope. Do not use this historical command as a substitute for tests required by a broader change.

## Historical Environment Notes

Earlier versions of this runbook named `C:\Anaconda\python.exe` and a workspace under `C:\VScode\...`; those are personal-machine examples, not portable requirements. The E13-Fix smoke notes used `G:\Anaconda\envs\mrta_env\python.exe` on one workstation. These paths were not verified on other machines.

Smoke inputs are not paper-grade performance evidence. Follow [`../data/README.md`](../data/README.md) and [`experiment_protocol.md`](experiment_protocol.md) for split and comparison rules. Final-test access remains governed by [`final_test_lockbox_protocol.md`](final_test_lockbox_protocol.md); this runbook does not authorize it.
