"""Read-only state-chain and state-regret instrumentation for fixed routes.

The regret table is recomputed locally from CostMatrix and State. This module
does not invoke or mutate RouteDPEvaluator and never changes its cache.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import inf
from statistics import mean
from typing import Dict, Iterable, List, Tuple

from .cost_matrix import CostMatrix
from .models import (
    Instance,
    MultiRobotSolution,
    RouteEvaluation,
    SolutionEvaluation,
    State,
    TaskRegion,
)

REGRET_TOL = 1e-9
DEFAULT_NEAR_TIE_TOL = 0.0
REPORT_TOL = 1e-6


@dataclass(frozen=True)
class StateOption:
    state_id: int
    entry_corner: str
    sweep_mode: str
    exit_corner: str
    n_sweeps: int
    processing_time: float
    prefix_cost: float
    suffix_cost: float
    q_cost: float
    regret: float

    def to_dict(self) -> dict:
        return {
            "state_id": self.state_id,
            "entry_corner": self.entry_corner,
            "sweep_mode": self.sweep_mode,
            "exit_corner": self.exit_corner,
            "n_sweeps": self.n_sweeps,
            "processing_time": self.processing_time,
            "prefix_cost": self.prefix_cost,
            "suffix_cost": self.suffix_cost,
            "q_cost": self.q_cost,
            "regret": self.regret,
        }


@dataclass(frozen=True)
class PositionRegret:
    position: int
    task_id: int
    chosen_state_id: int
    chosen_rank: int
    min_alternative_regret: float
    near_tie_count: int
    options: Tuple[StateOption, ...]

    def to_dict(self) -> dict:
        return {
            "position": self.position,
            "task_id": self.task_id,
            "chosen_state_id": self.chosen_state_id,
            "chosen_rank": self.chosen_rank,
            "min_alternative_regret": self.min_alternative_regret,
            "near_tie_count": self.near_tie_count,
            "options": [option.to_dict() for option in self.options],
        }


@dataclass(frozen=True)
class RouteRegretReport:
    route_task_ids: Tuple[int, ...]
    route_optimal_cost: float
    evaluator_total_cost: float
    positions: Tuple[PositionRegret, ...]

    def to_dict(self) -> dict:
        return {
            "route_task_ids": list(self.route_task_ids),
            "route_optimal_cost": self.route_optimal_cost,
            "evaluator_total_cost": self.evaluator_total_cost,
            "positions": [position.to_dict() for position in self.positions],
        }


def _enum_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


def route_regret_report(
    route_evaluation: RouteEvaluation,
    *,
    states_by_task: Dict[int, Iterable[State]],
    cost_matrix: CostMatrix,
    near_tie_tol: float = DEFAULT_NEAR_TIE_TOL,
) -> RouteRegretReport:
    """Compute exact per-position state regrets for one fixed task sequence."""
    if near_tie_tol < 0:
        raise ValueError("near_tie_tol must be non-negative")
    route = list(route_evaluation.route_task_ids)
    if not route:
        if abs(route_evaluation.total_cost) > REPORT_TOL:
            raise ValueError("empty route has nonzero evaluator cost")
        if route_evaluation.chosen_state_ids or route_evaluation.chosen_states:
            raise ValueError("empty route has a non-empty chosen state chain")
        return RouteRegretReport((), 0.0, route_evaluation.total_cost, ())

    seen: set[int] = set()
    for task_id in route:
        if task_id in seen:
            raise ValueError(f"duplicate task_id {task_id} in route")
        seen.add(task_id)
        if task_id not in states_by_task:
            raise ValueError(f"unknown task_id {task_id}: missing states")
    layers = [list(states_by_task[task_id]) for task_id in route]
    for task_id, layer in zip(route, layers):
        if not layer:
            raise ValueError(f"task_id {task_id} has no states")
        state_ids = [state.state_id for state in layer]
        if len(state_ids) != len(set(state_ids)):
            raise ValueError(f"task_id {task_id} has duplicate state ids")
        if any(state.task_id != task_id for state in layer):
            raise ValueError(f"states_by_task contains a state with wrong task_id {task_id}")
    if len(route_evaluation.chosen_state_ids) != len(route):
        raise ValueError("chosen state count does not match route task count")

    # F includes the current task's processing cost.
    forward: List[dict[int, float]] = []
    for position, layer in enumerate(layers):
        current: dict[int, float] = {}
        for state in layer:
            if position == 0:
                current[state.state_id] = (
                    cost_matrix.depot_to_state(state.state_id) + state.processing_time
                )
            else:
                current[state.state_id] = min(
                    forward[position - 1][previous.state_id]
                    + cost_matrix.transition(previous.state_id, state.state_id)
                    for previous in layers[position - 1]
                ) + state.processing_time
        forward.append(current)

    # B starts after the current task, so its processing cost is excluded.
    backward: List[dict[int, float]] = [dict() for _ in layers]
    for position in range(len(layers) - 1, -1, -1):
        for state in layers[position]:
            if position == len(layers) - 1:
                backward[position][state.state_id] = cost_matrix.state_to_depot(
                    state.state_id
                )
            else:
                backward[position][state.state_id] = min(
                    cost_matrix.transition(state.state_id, following.state_id)
                    + following.processing_time
                    + backward[position + 1][following.state_id]
                    for following in layers[position + 1]
                )

    route_optimal_cost = min(
        prefix_cost + cost_matrix.state_to_depot(state_id)
        for state_id, prefix_cost in forward[-1].items()
    )
    if abs(route_optimal_cost - route_evaluation.total_cost) > REPORT_TOL:
        raise ValueError(
            "independent route optimum disagrees with evaluator: "
            f"route={route}, local={route_optimal_cost}, "
            f"evaluator={route_evaluation.total_cost}"
        )

    positions: list[PositionRegret] = []
    for position, layer in enumerate(layers):
        options = tuple(
            sorted(
                (
                    StateOption(
                        state_id=state.state_id,
                        entry_corner=_enum_value(state.entry_corner),
                        sweep_mode=_enum_value(state.sweep_mode),
                        exit_corner=_enum_value(state.exit_corner),
                        n_sweeps=state.n_sweeps,
                        processing_time=state.processing_time,
                        prefix_cost=forward[position][state.state_id],
                        suffix_cost=backward[position][state.state_id],
                        q_cost=(
                            forward[position][state.state_id]
                            + backward[position][state.state_id]
                        ),
                        regret=(
                            forward[position][state.state_id]
                            + backward[position][state.state_id]
                            - route_optimal_cost
                        ),
                    )
                    for state in layer
                ),
                key=lambda option: (option.q_cost, option.state_id),
            )
        )
        minimum_q = min(option.q_cost for option in options)
        if abs(minimum_q - route_optimal_cost) > REGRET_TOL:
            raise ValueError(
                f"position {position} task_id {route[position]} has min Q "
                f"{minimum_q}, expected route optimum {route_optimal_cost}"
            )
        chosen_state_id = route_evaluation.chosen_state_ids[position]
        chosen_option = next(
            (option for option in options if option.state_id == chosen_state_id), None
        )
        if chosen_option is None:
            raise ValueError(
                f"chosen state {chosen_state_id} is unavailable for task_id {route[position]}"
            )
        if abs(chosen_option.q_cost - route_optimal_cost) > REGRET_TOL:
            raise ValueError(
                f"chosen state {chosen_state_id} at position {position} is not on an optimal chain"
            )
        if any(option.regret < -REGRET_TOL for option in options):
            raise ValueError(f"negative state regret at position {position}")
        chosen_key = (chosen_option.q_cost, chosen_option.state_id)
        chosen_rank = 1 + sum(
            (option.q_cost, option.state_id) < chosen_key for option in options
        )
        alternatives = [option for option in options if option.state_id != chosen_state_id]
        positions.append(
            PositionRegret(
                position=position,
                task_id=route[position],
                chosen_state_id=chosen_state_id,
                chosen_rank=chosen_rank,
                min_alternative_regret=min(
                    (option.regret for option in alternatives), default=inf
                ),
                near_tie_count=sum(
                    option.regret <= near_tie_tol for option in alternatives
                ),
                options=options,
            )
        )

    return RouteRegretReport(
        tuple(route), route_optimal_cost, route_evaluation.total_cost, tuple(positions)
    )


def route_cost_split(
    route_evaluation: RouteEvaluation,
    *,
    instance: Instance,
    task_by_id: Dict[int, TaskRegion],
) -> dict:
    """Split fixed route cost into sweep coverage, turns, and transfer."""
    if len(route_evaluation.chosen_states) != len(route_evaluation.route_task_ids):
        raise ValueError(f"state count does not match route {route_evaluation.route_task_ids}")
    if route_evaluation.chosen_state_ids != [
        state.state_id for state in route_evaluation.chosen_states
    ]:
        raise ValueError(f"state IDs disagree with chosen states for route {route_evaluation.route_task_ids}")
    if route_evaluation.route_task_ids and len(route_evaluation.transition_costs) != len(
        route_evaluation.route_task_ids
    ) + 1:
        raise ValueError(f"transition count does not match route {route_evaluation.route_task_ids}")
    if not route_evaluation.route_task_ids and route_evaluation.transition_costs:
        raise ValueError("empty route has transfer costs")

    coverage = 0.0
    turning = 0.0
    for state in route_evaluation.chosen_states:
        task = task_by_id.get(state.task_id)
        if task is None:
            raise ValueError(f"unknown task_id {state.task_id} in evaluated route")
        mode = _enum_value(state.sweep_mode)
        if mode not in {"H", "V"}:
            raise ValueError(f"unknown sweep mode {mode} for task_id {state.task_id}")
        length = task.width if mode == "H" else task.height
        coverage += state.n_sweeps * length / instance.sweep_speed
        turning += max(0, state.n_sweeps - 1) * instance.turning_time
    transfer = sum(route_evaluation.transition_costs)
    total = route_evaluation.total_cost
    if abs(coverage + turning + transfer - total) > REPORT_TOL:
        raise ValueError(
            "route cost split disagrees with evaluator: "
            f"route={route_evaluation.route_task_ids}, coverage={coverage}, "
            f"turning={turning}, transfer={transfer}, total={total}"
        )
    denominator = total if total else 1.0
    return {
        "coverage": coverage,
        "turning": turning,
        "transfer": transfer,
        "total": total,
        "coverage_share": coverage / denominator if total else 0.0,
        "turning_share": turning / denominator if total else 0.0,
        "transfer_share": transfer / denominator if total else 0.0,
    }


def state_chain_rows(route_evaluation: RouteEvaluation, *, route_id: int) -> List[dict]:
    """Return selected state-chain rows without invoking route evaluation."""
    if len(route_evaluation.chosen_states) != len(route_evaluation.route_task_ids):
        raise ValueError(f"state count does not match route_id {route_id}")
    rows = []
    for position, state in enumerate(route_evaluation.chosen_states):
        if state.task_id != route_evaluation.route_task_ids[position]:
            raise ValueError(f"task mismatch at route_id {route_id}, position {position}")
        rows.append(
            {
                "task_id": state.task_id,
                "route_id": route_id,
                "position": position,
                "state_id": state.state_id,
                "entry": _enum_value(state.entry_corner),
                "mode": _enum_value(state.sweep_mode),
                "exit": _enum_value(state.exit_corner),
                "n_sweeps": state.n_sweeps,
                "processing_time": state.processing_time,
            }
        )
    return rows


def solution_state_report(
    instance: Instance,
    solution: MultiRobotSolution,
    evaluation: SolutionEvaluation,
    *,
    states_by_task: Dict[int, Iterable[State]],
    cost_matrix: CostMatrix,
    solution_hash: str | None = None,
    near_tie_tol: float = DEFAULT_NEAR_TIE_TOL,
    include_regret: bool = True,
) -> dict:
    """Build a JSON-serializable state report for a complete evaluated solution."""
    if len(solution.routes) != instance.robot_count:
        raise ValueError("solution route count does not equal instance robot count")
    task_ids = [task_id for route in solution.routes for task_id in route]
    expected_ids = {task.task_id for task in instance.tasks}
    if len(task_ids) != len(set(task_ids)):
        raise ValueError("solution contains duplicate task IDs")
    if set(task_ids) != expected_ids:
        raise ValueError("solution task IDs do not match instance tasks")
    if len(evaluation.route_evaluations) != instance.robot_count:
        raise ValueError("evaluation route count does not equal instance robot count")
    if len(evaluation.per_robot_costs) != instance.robot_count:
        raise ValueError("per-robot cost count does not equal instance robot count")
    if any(
        evaluated.route_task_ids != solution.routes[route_id]
        for route_id, evaluated in enumerate(evaluation.route_evaluations)
    ):
        raise ValueError("evaluation task routes disagree with solution")
    route_costs = [route.total_cost for route in evaluation.route_evaluations]
    if any(abs(a - b) > REPORT_TOL for a, b in zip(route_costs, evaluation.per_robot_costs)):
        raise ValueError("per-robot costs disagree with route evaluations")
    makespan = max(route_costs, default=0.0)
    if abs(makespan - evaluation.makespan) > REPORT_TOL:
        raise ValueError("makespan disagrees with route evaluations")

    task_by_id = {task.task_id: task for task in instance.tasks}
    routes = []
    cost_splits = []
    for route_id, route_evaluation in enumerate(evaluation.route_evaluations):
        split = route_cost_split(route_evaluation, instance=instance, task_by_id=task_by_id)
        cost_splits.append(split)
        route_record = {
            "route_id": route_id,
            "task_order": list(route_evaluation.route_task_ids),
            "cost_split": split,
            "state_chain": state_chain_rows(route_evaluation, route_id=route_id),
        }
        if include_regret:
            regret = route_regret_report(
                route_evaluation,
                states_by_task=states_by_task,
                cost_matrix=cost_matrix,
                near_tie_tol=near_tie_tol,
            )
            route_record["regret_table"] = [
                position.to_dict() for position in regret.positions
            ]
        routes.append(route_record)

    mean_processing = mean(split["coverage"] + split["turning"] for split in cost_splits)
    mean_transfer = mean(split["transfer"] for split in cost_splits)
    mean_cost = mean(route_costs)
    load_excess = max(route_costs, default=0.0) - mean_cost
    if abs(mean_processing + mean_transfer + load_excess - makespan) > REPORT_TOL:
        raise ValueError("global objective decomposition disagrees with makespan")
    return {
        "instance": {
            "name": instance.name,
            "task_count": instance.task_count,
            "robot_count": instance.robot_count,
            "sweep_width": instance.sweep_width,
            "sweep_speed": instance.sweep_speed,
            "travel_speed": instance.travel_speed,
            "turning_time": instance.turning_time,
            "depot": list(instance.depot),
        },
        "solution_hash": solution_hash,
        "makespan": makespan,
        "per_robot_costs": route_costs,
        "route_load_excess": load_excess,
        "bottleneck_routes": [
            route_id
            for route_id, cost in enumerate(route_costs)
            if abs(cost - makespan) <= REPORT_TOL
        ],
        "objective": {
            "mean_processing": mean_processing,
            "mean_transfer": mean_transfer,
            "load_excess": load_excess,
            "makespan": makespan,
        },
        "near_tie_tol": near_tie_tol,
        "routes": routes,
    }


def assert_report_consistent(report: dict, *, tol: float = REPORT_TOL) -> None:
    """Independently validate report identities and regret-table invariants."""
    objective = report.get("objective")
    if objective is None:
        raise ValueError("report is missing objective")
    objective_sum = (
        objective.get("mean_processing", 0.0)
        + objective.get("mean_transfer", 0.0)
        + objective.get("load_excess", 0.0)
    )
    if abs(objective_sum - objective.get("makespan", inf)) > tol:
        raise ValueError("objective decomposition disagrees with makespan")
    if abs(report.get("makespan", inf) - objective.get("makespan", -inf)) > tol:
        raise ValueError("top-level makespan disagrees with objective")
    for route in report.get("routes", []):
        route_id = route.get("route_id", "?")
        split = route.get("cost_split")
        if split is None or abs(
            split.get("coverage", 0.0)
            + split.get("turning", 0.0)
            + split.get("transfer", 0.0)
            - split.get("total", inf)
        ) > tol:
            raise ValueError(f"cost split identity failed for route_id {route_id}")
        for position in route.get("regret_table", []):
            position_id = position.get("position", "?")
            options = position.get("options", [])
            if not options:
                raise ValueError(f"empty regret options at route_id {route_id}, position {position_id}")
            min_regret = min(option["regret"] for option in options)
            if abs(min_regret) > REGRET_TOL:
                raise ValueError(
                    f"minimum regret is not zero at route_id {route_id}, position {position_id}"
                )
            if position.get("chosen_rank", 0) < 1:
                raise ValueError(f"invalid chosen_rank at route_id {route_id}, position {position_id}")
            if position.get("min_alternative_regret", -inf) < -REGRET_TOL:
                raise ValueError(
                    f"negative alternative regret at route_id {route_id}, position {position_id}"
                )
