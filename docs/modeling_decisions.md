# MR-RCRP Modeling Decisions

## Problem

There are `R` homogeneous robots and `n` axis-aligned rectangular tasks. All robots start at and return to the common depot `(0, 0)`. Each task is assigned to exactly one robot and occurs exactly once in the complete solution. A robot route is an ordered sequence of task IDs; empty routes are allowed.

Each task has four legal entry corners and two sweep modes (`H`, `V`), giving eight states. For state `s`, the exit corner is determined by its entry corner, sweep mode, and sweep-count parity. The rules are implemented in `core/state_generator.py`.

## Cost Model

For task `i`, width `w_i`, height `h_i`, sweep width `delta`, sweep speed `v_s`, and turning time `tau`:

```text
N_i(H) = max(1, ceil(h_i / delta))
N_i(V) = max(1, ceil(w_i / delta))
P_i(H) = N_i(H) * w_i / v_s + (N_i(H) - 1) * tau
P_i(V) = N_i(V) * h_i / v_s + (N_i(V) - 1) * tau
```

Travel between depot/task states uses Manhattan distance divided by the instance's `travel_speed`. For route `r=(i_1,...,i_k)` with selected states `s_j`:

```text
C_r = depot_to_entry(s_1)
      + sum_j P_{i_j}(s_j)
      + sum_{j=1}^{k-1} travel(exit(s_j), entry(s_{j+1}))
      + travel(exit(s_k), depot)
M = max_r C_r
```

The objective is to minimize `M`. `RouteDPEvaluator` finds the least-cost legal state chain for a fixed task sequence; it does not optimize task assignment or order. The outer ALNS or comparison algorithm performs that search.

## Units and Assumptions

The loader expects six nonempty lines. Line 1 is `n_tasks n_robots`; line 2 is `sweep_width sweep_speed travel_speed turning_time`; lines 3–6 list all left, right, bottom, and top coordinates. Speeds must be finite and positive; turning time must be finite and nonnegative; rectangles must have positive width and height.

Coordinates and sweep width share a distance unit. `sweep_speed` and `travel_speed` use distance/time; turning time and route costs use time. The metric represents estimated completion time under Manhattan travel, constant speeds, no collision or congestion, no acceleration, and no charging model. It is not a full physical robot execution model.

## Feasibility and Evaluation

Complete solutions have exactly one route per robot, contain every known task exactly once, and contain no unknown task IDs. A partial ALNS solution may omit tasks only through the explicit partial-evaluation path. For each complete route the evaluator selects one legal state per task and includes outbound, inter-task, and return travel. The complete objective is the maximum route cost.

Do not substitute geometric proxies, greedy state choices, or per-task costs for the canonical exact evaluation unless a comparison condition explicitly defines such a mode and reports its own selected states and objective. Any such result is not numerically interchangeable with exact-mode results.

The modeling contract does not assert rectangles are nonoverlapping unless a particular dataset protocol says so. Homogeneity applies within each instance; parameters may differ between instances.
