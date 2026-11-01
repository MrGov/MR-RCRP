# Repository Guidance

## Research Objective

The project studies: **LLM-assisted evolutionary-computation methods for the multi-robot rectangular coverage scheduling problem, where entry/exit coverage states are coupled with task assignment and visit order, with each claimed innovation supported by verifiable evidence.**

Problem solving and the LLM-assisted evolution mechanism are the research center. Exact Route-DP, incremental pricing, local-search acceleration, candidate execution, audit, and logging are supporting components. Their engineering progress does not redefine the research objective.

The current implementation is an offline LLM operator-generation/revision pipeline, ALNS search over assignments and task order, and exact state optimization for fixed routes. The LLM proposes operators; it does not produce final solutions or replace the evaluator. Distinguish implemented mechanisms from candidates under study. DP-evidence feedback, decision-audit feedback, and complementary operator portfolios are hypotheses, not predetermined contributions or exclusive future directions.

## Model and Feasibility

- Homogeneous robots start and finish at the common depot `(0, 0)`.
- Every rectangular task is assigned to exactly one robot and covered exactly once.
- A task has four entry corners and horizontal/vertical sweep modes; sweep parity determines its exit corner.
- Inter-task travel uses Manhattan distance and `travel_speed`; coverage and turning costs follow `modeling_decisions.md`.
- The objective is minimum makespan, the maximum complete robot-route time.
- Preserve correct model, evaluator, ALNS, and Route-DP behavior. Change recurrence or objective only under an explicit task that requires it.

## Engineering Practice

- Read the current code and authoritative docs before changing behavior; local code and recorded evidence take precedence over old plans.
- Prefer narrow changes that reuse existing interfaces. Do not infer support from a design document alone.
- Keep LLM candidates, operator identities, datasets, manifests, frozen configs, and experiment records immutable unless explicitly authorized.
- Use development data for iteration. Respect manifest identities and split boundaries; never treat a consumed diagnostic split as fresh confirmation.
- Preserve negative, failed, timeout, fallback, and inconclusive results in their original scope.
- Add focused tests for behavioral changes and report exactly what was and was not verified.
- Do not run paid providers, final-test data, large experiments, or publish/commit changes unless the user authorizes that work.

## Documentation Authority

Read `README.md`, then `docs/README.md`. Current research claims are governed by `docs/research_positioning.md`, current implementation/evidence by `docs/program_status_and_design.md`, model by `docs/modeling_decisions.md`, experiment principles by `docs/experiment_protocol.md`, and dataset scope by `data/README.md`. Archived plans and experiment reports are historical evidence, not default implementation instructions.
