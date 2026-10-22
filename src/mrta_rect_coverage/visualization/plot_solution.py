"""Basic plotting utilities for solutions."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List

import matplotlib.pyplot as plt

from ..core.models import Instance, SolutionEvaluation, State


def plot_solution(
    instance: Instance,
    evaluation: SolutionEvaluation,
    states_by_task: Dict[int, Iterable[State]],
    output_dir: Path,
    dpi: int = 120,
    filename: str | None = None,
) -> Path:
    """Plot task rectangles and robot routes, saving to the outputs folder."""

    output_dir.mkdir(parents=True, exist_ok=True)
    image_name = filename or f"{instance.name}_solution.png"
    image_path = output_dir / image_name

    state_lookup: Dict[int, State] = {
        state.state_id: state for states in states_by_task.values() for state in states
    }
    task_lookup = {task.task_id: task for task in instance.tasks}

    fig, ax = plt.subplots(figsize=(8, 6), dpi=dpi)
    ax.set_title(f"Solution for {instance.name}")

    # Plot task rectangles and IDs
    for task in instance.tasks:
        width = task.width
        height = task.height
        rect = plt.Rectangle(
            (task.x_left, task.y_bottom),
            width,
            height,
            facecolor="#1f77b4",
            alpha=0.2,
            edgecolor="#1f77b4",
        )
        ax.add_patch(rect)
        ax.text(
            task.x_left + width * 0.5,
            task.y_bottom + height * 0.5,
            str(task.task_id),
            ha="center",
            va="center",
            fontsize=8,
            color="#0f3d69",
        )

    ax.scatter([instance.depot[0]], [instance.depot[1]], c="black", s=40, label="Depot")

    colors = plt.cm.tab10.colors
    for robot_index, route_eval in enumerate(evaluation.route_evaluations):
        color = colors[robot_index % len(colors)]
        label = f"Robot {robot_index + 1}"
        if robot_index < len(evaluation.per_robot_costs):
            label += f" (cost={evaluation.per_robot_costs[robot_index]:.2f})"

        # Draw arrows for transitions: depot -> entry, exit -> next entry, exit -> depot
        prev_point = instance.depot
        for state_id in route_eval.chosen_state_ids:
            state = state_lookup[state_id]

            # Transition arrow into the task entry
            ax.annotate(
                "",
                xy=state.entry_point,
                xytext=prev_point,
                arrowprops=dict(arrowstyle="->", color=color, linewidth=1.2),
            )

            # Mark entry and exit points without connecting them
            ax.scatter([state.entry_point[0]], [state.entry_point[1]], color=color, s=16)
            ax.scatter([state.exit_point[0]], [state.exit_point[1]], color=color, s=16)

            # Place sweep mode label offset from task center to avoid overlapping task id
            task = task_lookup.get(state.task_id)
            if task is not None:
                cx = (task.x_left + task.x_right) * 0.5
                cy = (task.y_bottom + task.y_top) * 0.5
                offset_x = max(0.4, task.width * 0.15)
                offset_y = max(0.4, task.height * 0.15)
                ax.text(
                    cx + offset_x,
                    cy + offset_y,
                    state.sweep_mode.value,
                    ha="center",
                    va="center",
                    fontsize=8,
                    fontweight="bold",
                    color=color,
                    bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.7, edgecolor="none"),
                )

            prev_point = state.exit_point

        # Return to depot
        ax.annotate(
            "",
            xy=instance.depot,
            xytext=prev_point,
            arrowprops=dict(arrowstyle="->", color=color, linewidth=1.2),
            label=label,
        )

        # Add a dummy line for legend color consistency
        ax.plot([], [], color=color, label=label)

    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.legend()
    ax.set_aspect("equal", adjustable="box")
    fig.tight_layout()
    fig.savefig(image_path)
    plt.close(fig)
    return image_path
