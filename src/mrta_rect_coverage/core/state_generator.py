"""Generation of candidate coverage states for tasks."""
from __future__ import annotations

import math
from typing import Dict, List

from .enums import Corner, SweepMode
from .models import Instance, State, TaskRegion


def generate_states_for_task(
    task: TaskRegion,
    speed: float,
    sweep_width: float,
    turning_time: float,
    starting_state_id: int = 0,
) -> List[State]:
    """Generate the eight corner/mode states for a given task."""

    states: List[State] = []
    next_state_id = starting_state_id
    for corner in Corner:
        for mode in SweepMode:
            n_sweeps = _compute_n_sweeps(task, mode, sweep_width)
            exit_corner = _determine_exit_corner(mode, corner, n_sweeps)
            processing_time = _compute_processing_time(
                task, mode, n_sweeps, speed, turning_time
            )
            entry_point = task.corner_point(corner)
            exit_point = task.corner_point(exit_corner)
            next_state_id += 1
            states.append(
                State(
                    state_id=next_state_id,
                    task_id=task.task_id,
                    entry_corner=corner,
                    sweep_mode=mode,
                    exit_corner=exit_corner,
                    processing_time=processing_time,
                    entry_point=entry_point,
                    exit_point=exit_point,
                    n_sweeps=n_sweeps,
                )
            )
    return states


def generate_all_states(instance: Instance) -> Dict[int, List[State]]:
    """Generate states for all tasks in an instance."""

    states_by_task: Dict[int, List[State]] = {}
    state_id = 0
    for task in instance.tasks:
        task_states = generate_states_for_task(
            task,
            speed=instance.sweep_speed,
            sweep_width=instance.sweep_width,
            turning_time=instance.turning_time,
            starting_state_id=state_id,
        )
        states_by_task[task.task_id] = task_states
        state_id = task_states[-1].state_id
    return states_by_task


def _compute_n_sweeps(task: TaskRegion, mode: SweepMode, sweep_width: float) -> int:
    if sweep_width <= 0:
        raise ValueError("sweep_width must be positive")
    if mode == SweepMode.H:
        return max(1, math.ceil(task.height / sweep_width))
    return max(1, math.ceil(task.width / sweep_width))


def _compute_processing_time(
    task: TaskRegion,
    mode: SweepMode,
    n_sweeps: int,
    speed: float,
    turning_time: float,
) -> float:
    if speed <= 0:
        raise ValueError("speed must be positive")
    travel_distance = task.width if mode == SweepMode.H else task.height
    sweep_time = (n_sweeps * travel_distance) / speed
    turn_time = (n_sweeps - 1) * turning_time if n_sweeps > 1 else 0.0
    return sweep_time + turn_time


def _determine_exit_corner(mode: SweepMode, entry: Corner, n_sweeps: int) -> Corner:
    is_odd = n_sweeps % 2 == 1
    if mode == SweepMode.H:
        if is_odd:
            mapping = {
                Corner.LB: Corner.RT,
                Corner.RB: Corner.LT,
                Corner.LT: Corner.RB,
                Corner.RT: Corner.LB,
            }
        else:
            mapping = {
                Corner.LB: Corner.LT,
                Corner.RB: Corner.RT,
                Corner.LT: Corner.LB,
                Corner.RT: Corner.RB,
            }
    else:  # SweepMode.V
        if is_odd:
            mapping = {
                Corner.LB: Corner.RT,
                Corner.LT: Corner.RB,
                Corner.RB: Corner.LT,
                Corner.RT: Corner.LB,
            }
        else:
            mapping = {
                Corner.LB: Corner.RB,
                Corner.LT: Corner.RT,
                Corner.RB: Corner.LB,
                Corner.RT: Corner.LT,
            }
    return mapping[entry]
