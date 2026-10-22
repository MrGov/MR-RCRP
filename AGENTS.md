# AGENTS.md

## Project status

This repository already contains a partially implemented baseline solver for a multi-robot rectangular coverage routing problem.

Do not restart the project from scratch.
Treat the current repository contents as the single source of truth.

Before making changes:
1. Inspect the current repository structure
2. Read README.md
3. Read all files under src/mrta_rect_coverage/
4. Read tests/
5. Run tests if possible
6. Summarize what is already implemented and what is missing

## Main objective of current stage

The current goal is NOT to build advanced metaheuristics or online LLM integration.

The current goal is to complete and stabilize the baseline implementation so that the project can:
- load txt instances correctly
- generate task states correctly
- compute transition costs correctly
- evaluate a fixed route with layered DP
- evaluate a multi-robot solution with makespan
- build a simple baseline solution
- run a simple local search
- run the demo entrypoint successfully
- pass tests

## Instance format

Instance files are txt files with names like:
- R2_T10_0.txt
- R2_T10_1.txt

Meaning:
- R2 = 2 robots
- T10 = 10 tasks
- final integer = repetition id

File content format:
1. n_tasks n_robots
2. sweep_width sweep_speed travel_speed turning_time
3. x_left values
4. x_right values
5. y_bottom values
6. y_top values

The filename metadata must match the file content.

Default assumptions:
- depot = (0, 0)
- task ids start from 1 in input order

## Core modeling rules

Each task produces 8 states:
- 4 entry corners × 2 sweep modes

H-mode:
- n_sweeps = ceil(height / sweep_width)
- processing_time = n_sweeps * width / sweep_speed + (n_sweeps - 1) * turning_time

V-mode:
- n_sweeps = ceil(width / sweep_width)
- processing_time = n_sweeps * height / sweep_speed + (n_sweeps - 1) * turning_time

All depot/task and task/task transitions use:
- travel_time = ManhattanDistance / travel_speed

Both speeds must be explicit, finite, and positive. The legacy three-value
second line is rejected rather than assigned an implicit travel speed.

## Solution feasibility boundary

- Complete evaluation requires exactly one route per robot.
- Every instance task must appear exactly once; unknown, missing, and duplicate IDs fail closed.
- Empty robot routes are legal.
- ALNS destroy states use the explicit partial evaluator, which allows missing tasks only.
- All insertion operators score candidates through exact Route DP.
- `dp_aware_insertion` is a compatibility alias of greedy insertion, not an independent operator or ablation.

## Exit-corner parity mapping

### H-mode
If n_sweeps is odd:
- LB -> RT
- RB -> LT
- LT -> RB
- RT -> LB

If n_sweeps is even:
- LB -> LT
- RB -> RT
- LT -> LB
- RT -> RB

### V-mode
If n_sweeps is odd:
- LB -> RT
- LT -> RB
- RB -> LT
- RT -> LB

If n_sweeps is even:
- LB -> RB
- LT -> RT
- RB -> LB
- RT -> LT

## Development priorities

Priority order:
1. Fix broken imports / module wiring
2. Verify instance loader and filename parsing
3. Verify state generation and parity mapping
4. Verify DP evaluator
5. Verify solution evaluator
6. Verify baseline constructors / local search / baseline solver
7. Verify visualization and main demo
8. Update tests and README if needed

## Rules for modifying code

- Do not rewrite correct modules unnecessarily
- Prefer minimal fixes over broad refactors
- Reuse existing code whenever possible
- If behavior changes, update tests accordingly
- Keep dependencies lightweight
- Do not add real LLM API integration
- Do not add OR-Tools, Gurobi, numba, C++, or cython at this stage

## Definition of done

A task is only done if:
1. code is implemented
2. imports work
3. related tests pass
4. main demo still runs
5. documentation is updated if behavior changed
