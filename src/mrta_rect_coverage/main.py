"""Command-line entry point for MRTA baseline and research solvers."""
from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_config
from .core.cost_matrix import CostMatrix
from .core.instance_loader import load_instance
from .core.lower_bounds import (
    processing_with_connectivity_lb,
    processing_with_travel_lb,
    simple_average_processing_lb,
)
from .core.state_generator import generate_all_states
from .heuristics.alns_solver import ALNSConfig, solve_with_alns
from .heuristics.baseline_solver import baseline_solve
from .llm.mock_advisor import MockAdvisor
from .llm.rule_based_advisor import RuleBasedAdvisor
from .visualization.plot_search import plot_convergence_curve, plot_operator_usage_histogram
from .visualization.plot_solution import plot_solution


def _build_advisor(mode: str):
    key = mode.strip().lower()
    if key == "none":
        return None
    if key == "mock":
        return MockAdvisor()
    if key == "rule_based":
        return RuleBasedAdvisor()
    raise ValueError(f"Unknown advisor mode: {mode}")


def main() -> None:
    """Run the selected solver using configuration from YAML."""

    parser = argparse.ArgumentParser(description="MRTA rectangular coverage")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to the YAML configuration file.",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    instance = load_instance(config.instance_path)

    states_by_task = generate_all_states(instance)
    cost_matrix = CostMatrix(
        instance.depot, states_by_task, travel_speed=instance.travel_speed
    )
    simple_lb = simple_average_processing_lb(instance, states_by_task)
    travel_lb = processing_with_travel_lb(instance, states_by_task, cost_matrix)
    connect_lb = processing_with_connectivity_lb(instance, states_by_task, cost_matrix)

    print(f"Instance: {instance.name}")
    print(f"Robots: {instance.robot_count}")
    print(f"Tasks: {instance.task_count}")
    print(f"Simple lower bound: {simple_lb:.2f}")
    print(f"Travel lower bound: {travel_lb:.2f}")
    print(f"Connectivity lower bound: {connect_lb:.2f}")

    if config.algorithm.strip().lower() == "alns":
        advisor = _build_advisor(config.advisor_mode)
        result = solve_with_alns(
            instance,
            constructor=config.constructor,
            config=ALNSConfig(
                iterations=config.alns_iterations,
                acceptance=config.alns_acceptance,
                destroy_fraction=config.alns_destroy_fraction,
                use_dp_aware_insertion=config.alns_use_dp_aware_insertion,
                frozen_operator_registry_path=(config.alns_frozen_operator_registry_path or None),
                use_frozen_repair=config.alns_use_frozen_repair,
                use_frozen_destroy=config.alns_use_frozen_destroy,
            ),
            advisor=advisor,
        )
        solution = result.best_solution
        evaluation = result.best_evaluation
        convergence_path = plot_convergence_curve(
            result.iteration_history,
            config.visualization_output_dir,
            filename=f"{instance.name}_convergence.png",
            dpi=config.visualization_dpi,
        )
        usage_path = plot_operator_usage_histogram(
            result.operator_usage_stats,
            config.visualization_output_dir,
            filename=f"{instance.name}_operators.png",
            dpi=config.visualization_dpi,
        )
        print(f"ALNS iterations: {config.alns_iterations}")
        print(f"Advisor mode: {config.advisor_mode}")
        print(f"Saved convergence plot to: {convergence_path}")
        print(f"Saved operator plot to: {usage_path}")
    else:
        solution, evaluation = baseline_solve(
            instance,
            constructor=config.constructor,
            enable_local_search=config.local_search_enabled,
            max_iterations=config.local_search_max_iterations,
            use_stronger_local_search=config.local_search_use_stronger,
        )

    for idx, (route, cost) in enumerate(zip(solution.routes, evaluation.per_robot_costs), start=1):
        print(f"Robot {idx} route: {route}")
        print(f"Robot {idx} cost: {cost:.2f}")
    print(f"Makespan: {evaluation.makespan:.2f}")

    image_path = plot_solution(
        instance,
        evaluation,
        states_by_task,
        output_dir=config.visualization_output_dir,
        dpi=config.visualization_dpi,
    )
    print(f"Saved solution plot to: {image_path}")


if __name__ == "__main__":
    main()

