"""Offline operator evolution interfaces and context protocols."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Protocol, Sequence

from ...core.models import Instance, MultiRobotSolution, SolutionEvaluation


@dataclass
class RepairContext:
    """Context visible to candidate repair operators."""

    instance: Instance
    per_robot_costs: List[float]
    route_costs_makespan: float
    bottleneck_route_id: int


@dataclass
class DestroyContext:
    """Context visible to candidate destroy operators."""

    instance: Instance
    per_robot_costs: List[float]
    route_costs_makespan: float
    remove_count: int


@dataclass
class RepairResult:
    """Return payload of a candidate repair operator."""

    solution: MultiRobotSolution
    note: str = ""


@dataclass
class DestroyResult:
    """Return payload of a candidate destroy operator."""

    partial_solution: MultiRobotSolution
    removed_tasks: List[int]
    note: str = ""


@dataclass
class EvolutionHarnessContext:
    """Runtime dependencies passed to generated operators through wrapper context."""

    project_root: Path
    route_evaluator_name: str


class RepairOperatorFn(Protocol):
    def __call__(
        self,
        partial_solution: MultiRobotSolution,
        unassigned_tasks: Sequence[int],
        context: RepairContext,
        rng,
    ) -> RepairResult:
        ...


class DestroyOperatorFn(Protocol):
    def __call__(
        self,
        solution: MultiRobotSolution,
        context: DestroyContext,
        rng,
    ) -> DestroyResult:
        ...


class OperatorProvider(Protocol):
    """Provider API for candidate generation or revision."""

    def generate_operator_candidates(self, prompt: str, n: int, operator_type: str):
        ...

    def revise_operator_candidates(
        self,
        prompt: str,
        previous_results: Dict[str, object],
        n: int,
        operator_type: str,
    ):
        ...
