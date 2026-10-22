"""Mock provider returning deterministic candidate drafts."""
from __future__ import annotations

from typing import Dict, List

from .provider_interface import OperatorEvolutionProvider
from .schemas import GeneratedOperatorDraft


def _repair_template(operator_id: str, name: str, description: str) -> str:
    return f'''from __future__ import annotations

from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import RepairResult


def repair(partial_solution, unassigned_tasks, context, rng):
    routes = [list(route) for route in partial_solution.routes]
    # Problem-specific bias: prefer inserting into non-bottleneck routes first.
    robot_order = list(range(len(routes)))
    if 0 <= context.bottleneck_route_id < len(routes):
        robot_order.remove(context.bottleneck_route_id)
        robot_order.append(context.bottleneck_route_id)

    for task_id in unassigned_tasks:
        target_robot = min(robot_order, key=lambda r: len(routes[r])) if routes else 0
        routes[target_robot].append(task_id)
    return RepairResult(solution=MultiRobotSolution(routes=routes), note="{description}")
'''


def _destroy_template(operator_id: str, name: str, description: str) -> str:
    return f'''from __future__ import annotations

from mrta_rect_coverage.core.models import MultiRobotSolution
from mrta_rect_coverage.llm.operator_evolution.protocols import DestroyResult


def destroy(solution, context, rng):
    routes = [list(route) for route in solution.routes]
    all_tasks = [task for route in routes for task in route]
    remove_count = min(max(1, context.remove_count), len(all_tasks)) if all_tasks else 0
    removed = all_tasks[:remove_count]
    removed_set = set(removed)
    new_routes = [[task for task in route if task not in removed_set] for route in routes]
    return DestroyResult(partial_solution=MultiRobotSolution(routes=new_routes), removed_tasks=removed, note="{description}")
'''


class MockOperatorEvolutionProvider(OperatorEvolutionProvider):
    """Generate deterministic template-based operators for smoke and CI tests."""

    def generate_operator_candidates(
        self,
        prompt: str,
        n: int,
        operator_type: str,
        round_id: int,
    ) -> List[GeneratedOperatorDraft]:
        return self._build(operator_type, n, round_id, source="mock")

    def revise_operator_candidates(
        self,
        prompt: str,
        previous_results: Dict[str, object],
        n: int,
        operator_type: str,
        round_id: int,
    ) -> List[GeneratedOperatorDraft]:
        return self._build(operator_type, n, round_id, source="mock")

    def _build(self, operator_type: str, n: int, round_id: int, source: str) -> List[GeneratedOperatorDraft]:
        drafts: List[GeneratedOperatorDraft] = []
        for idx in range(n):
            operator_id = f"{operator_type}_r{round_id:03d}_{idx:03d}"
            name = f"{operator_type}_candidate_{idx}"
            description = "template candidate"
            if operator_type == "repair":
                code = _repair_template(operator_id, name, description)
            elif operator_type == "destroy":
                code = _destroy_template(operator_id, name, description)
            else:
                raise ValueError(f"Unsupported operator_type: {operator_type}")
            drafts.append(
                GeneratedOperatorDraft(
                    operator_id=operator_id,
                    operator_type=operator_type,
                    round_id=round_id,
                    name=name,
                    description=description,
                    source=source,
                    code=code,
                    module_filename=f"{operator_id}.py",
                )
            )
        return drafts
