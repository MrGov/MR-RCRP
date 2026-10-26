"""Shared prompt fragments for operator evolution."""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Problem description
# ---------------------------------------------------------------------------

PROBLEM_DESCRIPTION = """\
Problem: Multi-Robot Task Allocation for Rectangular Coverage Routing (MR-RCRP).
- Multiple robots start at depot (0,0), each covers a subset of rectangular regions \
via sweep patterns (horizontal or vertical), then returns to depot.
- Objective: minimise makespan (maximum completion time across all robots).
- Each rectangle has 4 entry corners x 2 sweep modes = 8 processing states; \
the DP evaluator picks the optimal state chain for any fixed task sequence.
"""

# ---------------------------------------------------------------------------
# Constraints & forbidden actions
# ---------------------------------------------------------------------------

CONSTRAINTS = """\
Constraints:
- You MUST use the exact function signature provided below.
- You MUST return the specified dataclass (RepairResult / DestroyResult).
- You MUST NOT import external packages beyond the standard library.
- You MUST NOT perform file I/O, network calls, or subprocess invocations.
- You MUST NOT modify the random protocol (do not call random.seed or reset rng).
- You MUST NOT add new dependencies.
- You MUST NOT change the function name.
"""

# ---------------------------------------------------------------------------
# Output format instructions
# ---------------------------------------------------------------------------

OUTPUT_FORMAT_JSON = """\
Output format: Return a JSON array. Each element is an object with keys:
  "name"        : str  — short descriptive name (snake_case)
  "description" : str  — one-line explanation of the heuristic strategy
  "code"        : str  — complete Python source code (including imports)

Example:
```json
[
  {
    "name": "bottleneck_balance_repair",
    "description": "Insert tasks into non-bottleneck routes first, balancing load.",
    "code": "from __future__ import annotations\\n..."
  }
]
```
"""

# ---------------------------------------------------------------------------
# Repair-specific guidance
# ---------------------------------------------------------------------------

REPAIR_SIGNATURE = """\
Required signature:
```python
def repair(partial_solution, unassigned_tasks, context, rng) -> RepairResult:
    \"\"\"
    Args:
        partial_solution: MultiRobotSolution with .routes (List[List[int]])
        unassigned_tasks: List[int] — task IDs not yet assigned
        context: RepairContext with fields:
            .instance        — Instance (tasks, robot_count, depot)
            .per_robot_costs — List[float] current route costs
            .route_costs_makespan — float current makespan
            .bottleneck_route_id  — int index of the slowest route
        rng: random.Random instance for stochastic decisions
    Returns:
        RepairResult(solution=MultiRobotSolution(routes=...), note="...")
    \"\"\"
```
"""

REPAIR_CONTRACT_GUIDANCE = """\
Authoritative E1 repair interface (this overrides any broad heuristic suggestion):
- Signature: repair(partial_solution, unassigned_tasks, context, rng) -> RepairResult.
- Import the project classes exactly as shown in the example below. Do not define replacements.
- partial_solution.routes is List[List[int]]; unassigned_tasks contains task IDs.
- context.instance has tasks (List[TaskRegion]), robot_count and depot;
  use context.instance.robot_count if the number of robots is needed.
- TaskRegion has task_id, x_left, y_bottom, x_right, y_top, width, height.
- Task IDs are not guaranteed to be list indexes; match by task.task_id.
- context also has per_robot_costs, route_costs_makespan, bottleneck_route_id.
- context does not provide a route evaluator, DP evaluator or cost function.
- Do not calculate a substitute makespan objective or reimplement Route-DP.
- Preserve each existing task exactly once; insert every unassigned task exactly once.
- Return RepairResult(solution=MultiRobotSolution(routes=routes), note="...").
- Allowed imports for this example: the two project imports below. If needed, use
  harmless standard-library math/collections only; never import sys.
- Never use getattr, hasattr, setattr, dynamic imports, reflection, interface
  probing, file/network/process access, or a standalone script.
- The output must load directly through the existing candidate loader and evaluator.

Minimal valid example adapted from the existing project repair fixture:
```python
from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import RepairResult

def repair(partial_solution, unassigned_tasks, context, rng):
    routes = [list(route) for route in partial_solution.routes]
    robot_order = list(range(len(routes)))
    if 0 <= context.bottleneck_route_id < len(routes):
        robot_order.remove(context.bottleneck_route_id)
        robot_order.append(context.bottleneck_route_id)
    for task_id in unassigned_tasks:
        target_robot = min(robot_order, key=lambda r: len(routes[r]))
        routes[target_robot].append(task_id)
    return RepairResult(solution=MultiRobotSolution(routes=routes), note="repair")
```
Generate a distinct strategy, not a copy of this example.
"""

REPAIR_HEURISTIC_DIRECTIONS = """\
Heuristic directions for repair operators (MRTA-rectangle-specific):
1. Route-balancing insertion: use the supplied per-robot costs as a hint; \
the project evaluator (not candidate code) computes the exact DP route cost.
2. Bottleneck-balancing: avoid inserting into the bottleneck route; prefer routes \
with the most slack (makespan - route_cost).
3. Geometry-aware insertion: prefer inserting a task next to tasks with similar \
aspect ratio or nearby centroids to reduce inter-task travel.
4. H/V-gap-aware insertion: group tasks that share horizontal or vertical sweep \
alignment to reduce sweep-direction switching overhead.
5. Critical-route-sensitive repair: avoid new assignments to the bottleneck \
route while preserving all existing tasks.
"""

# ---------------------------------------------------------------------------
# Destroy-specific guidance
# ---------------------------------------------------------------------------

DESTROY_SIGNATURE = """\
Required signature:
```python
def destroy(solution, context, rng) -> DestroyResult:
    \"\"\"
    Args:
        solution: MultiRobotSolution with .routes (List[List[int]])
        context: DestroyContext with fields:
            .instance        — Instance (tasks, robot_count, depot)
            .per_robot_costs — List[float] current route costs
            .route_costs_makespan — float current makespan
            .remove_count    — int number of tasks to remove
        rng: random.Random instance for stochastic decisions
    Returns:
        DestroyResult(
            partial_solution=MultiRobotSolution(routes=...),
            removed_tasks=[...],
            note="..."
        )
    \"\"\"
```
"""

DESTROY_HEURISTIC_DIRECTIONS = """\
Contract: use only DestroyContext.instance, per_robot_costs, route_costs_makespan,
and remove_count. No evaluator, bottleneck_route_id or internal DP state chain is
exposed. Derive critical routes from per_robot_costs. Instance exposes tasks,
robot_count, depot, sweep_width, sweep_speed, travel_speed and turning_time;
tasks expose task_id, x_left, x_right, y_bottom, y_top, width and height.
Import MultiRobotSolution from mrta_rect_coverage.core.models and DestroyResult
from mrta_rect_coverage.llm.operator_evolution.protocols.
Remove exactly min(context.remove_count, instance.task_count) distinct tasks.
Preserve robot membership and relative order of retained tasks. Do not mutate
the input. Return a consistent partition of original tasks, no additions.
Optimize the final feasible makespan after repair, not partial makespan alone.
H/V processing or Manhattan geometry are approximate selection features;
state switching has no separate penalty and Exact Route-DP remains external.

Heuristic directions for destroy operators (MRTA-rectangle-specific):
1. Bottleneck-route destroy: remove tasks from the slowest route to create \
rebalancing opportunities.
2. Geometry-aware destroy: remove tasks whose rectangles are outliers in \
position or aspect ratio within their current route.
3. Long-rectangle-sensitive destroy: target tasks with extreme aspect ratios \
that dominate processing time.
4. H/V-gap-sensitive destroy: remove tasks that cause large sweep-direction \
mismatches with their neighbours.
"""
