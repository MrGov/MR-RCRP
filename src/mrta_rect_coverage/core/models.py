"""Core data models for the MRTA rectangular coverage problem."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .enums import Corner, SweepMode

Point = Tuple[float, float]


@dataclass
class TaskRegion:
    """Axis-aligned rectangular task region."""

    task_id: int
    x_left: float
    y_bottom: float
    x_right: float
    y_top: float

    @property
    def width(self) -> float:
        """Return the width of the rectangle."""

        return self.x_right - self.x_left

    @property
    def height(self) -> float:
        """Return the height of the rectangle."""

        return self.y_top - self.y_bottom

    def corner_point(self, corner: Corner) -> Point:
        """Return coordinates of a given corner."""

        if corner == Corner.LB:
            return (self.x_left, self.y_bottom)
        if corner == Corner.LT:
            return (self.x_left, self.y_top)
        if corner == Corner.RB:
            return (self.x_right, self.y_bottom)
        if corner == Corner.RT:
            return (self.x_right, self.y_top)
        raise ValueError(f"Unknown corner: {corner}")


@dataclass
class State:
    """Candidate coverage state for a task."""

    state_id: int
    task_id: int
    entry_corner: Corner
    sweep_mode: SweepMode
    exit_corner: Corner
    processing_time: float
    entry_point: Point
    exit_point: Point
    n_sweeps: int


@dataclass
class Instance:
    """Problem instance containing tasks and robot parameters."""

    name: str
    depot: Point
    robot_count: int
    sweep_speed: float
    travel_speed: float
    sweep_width: float
    turning_time: float
    tasks: List[TaskRegion]
    rep_id: Optional[int] = None

    @property
    def task_count(self) -> int:
        """Return number of tasks."""

        return len(self.tasks)

    @property
    def speed(self) -> float:
        """Return sweep speed through the legacy compatibility name."""

        return self.sweep_speed


@dataclass
class RouteEvaluation:
    """Evaluation details for a single robot route."""

    route_task_ids: List[int]
    chosen_state_ids: List[int]
    total_cost: float
    chosen_states: List[State] = field(default_factory=list)
    entry_points: List[Point] = field(default_factory=list)
    exit_points: List[Point] = field(default_factory=list)
    cumulative_costs: List[float] = field(default_factory=list)
    transition_costs: List[float] = field(default_factory=list)
    predecessor_state_ids: List[Optional[int]] = field(default_factory=list)


@dataclass
class MultiRobotSolution:
    """Multi-robot solution represented by per-robot task routes."""

    routes: List[List[int]] = field(default_factory=list)


@dataclass
class SolutionEvaluation:
    """Aggregated evaluation for a multi-robot solution."""

    per_robot_costs: List[float]
    route_evaluations: List[RouteEvaluation]
    makespan: float

