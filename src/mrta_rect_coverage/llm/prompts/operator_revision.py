"""Prompt templates for operator candidate revision based on feedback."""
from __future__ import annotations

import json
from typing import Dict, List

from . import common


def build_compact_gap_revision_prompt(*, parent, feedback, target):
    """One source, one aggregate table, at most three externally linked cases."""
    import hashlib
    from pathlib import Path
    source = Path(parent["source_path"]).read_text(encoding="utf-8")
    if hashlib.sha256(source.encode()).hexdigest() != parent["source_hash"]:
        raise ValueError("parent repair source hash changed")
    return (
        f"Offline repair revision; parent SHA-256 {parent['source_hash']}.\n"
        f"Actual parent source (once):\n```python\n{source}\n```\n"
        f"{common.PROBLEM_DESCRIPTION}\n{common.CONSTRAINTS}\n{common.REPAIR_SIGNATURE}\n"
        "Return RepairResult from mrta_rect_coverage.llm.operator_evolution.protocols and "
        "MultiRobotSolution from mrta_rect_coverage.core.models. Preserve exactly-once coverage. "
        "Context exposes only instance, per_robot_costs, route_costs_makespan, bottleneck_route_id; "
        "there is no evaluator or DP callable. Instance has sweep_width/sweep_speed/travel_speed/turning_time; "
        "tasks have task_id/x_left/y_bottom/x_right/y_top/width/height. Use only supplied rng. "
        "No global state, module mutation, IO, reflection, subprocesses or reimplementation of Route-DP. "
        "Use bounded local work; current measured execution costs and failure cases are evidence, not targets to fabricate.\n"
        "Development feedback (complete raw traces are linked locally):\n"
        + json.dumps(feedback, ensure_ascii=False, separators=(",", ":")) + "\n"
        + f"Revision target: {target}\n"
        "First state one falsifiable revision_hypothesis linking an observed failure to a concrete behavior change. "
        "Return exactly one JSON-array element with revision_hypothesis, name, description and complete code. "
        "Do not claim offline traces are available online or include untested performance claims.\n"
    )


def build_paired_repair_revision_prompt(*, parent, feedback, n=2):
    """One parent-grounded repair revision conditioned on a frozen destroy."""
    import hashlib
    from pathlib import Path
    source = Path(parent["source_path"]).read_text(encoding="utf-8")
    if hashlib.sha256(source.encode()).hexdigest() != parent["source_hash"]:
        raise ValueError("parent repair source hash changed")
    return (f"E7 paired cooperative repair revision. Requested candidates: {n}\n"
        f"Parent ID: {parent['operator_id']}\nParent source SHA-256: {parent['source_hash']}\n"
        f"Actual parent source:\n```python\n{source}\n```\n"
        f"{common.PROBLEM_DESCRIPTION}\n{common.CONSTRAINTS}\n{common.REPAIR_SIGNATURE}\n"
        f"{common.REPAIR_CONTRACT_GUIDANCE}\n"
        "No evaluator or internal DP state chain is available in RepairContext. Only instance, per_robot_costs, "
        "route_costs_makespan and bottleneck_route_id are exposed. Instance also exposes sweep_width, sweep_speed, "
        "travel_speed and turning_time. Depot is instance.depot[0], instance.depot[1].\n"
        "Real processing features: nH=max(1,ceil(height/sweep_width)); nV=max(1,ceil(width/sweep_width)); "
        "pH=nH*width/sweep_speed+(nH-1)*turning_time; pV=nV*height/sweep_speed+(nV-1)*turning_time. "
        "Entry corner, mode and sweep-count parity determine exit corner. Manhattan distance/travel_speed gives transfer time; "
        "include depot departure and return when estimating insertion. H/V minima and geometric hints are approximate "
        "workload features, never substitutes for Route-DP. There is no separate mode-switch penalty.\n"
        "Measured frozen-pair feedback (associations, not proven causes):\n"
        + json.dumps(feedback, sort_keys=True) + "\n"
        "First formulate one falsifiable revision_hypothesis naming the observed state pattern, the code behavior to "
        "change, and the expected paired pre/post-local-search Route-DP outcome. Then implement that hypothesis in "
        "this parent repair. Do not generate or change the destroy. Do not fabricate metrics or call/reimplement DP. "
        "Do not claim the recorded fixed-route DP chain is an online feature available through RepairContext. "
        "Do not merely copy formulas into unused code. Return exactly one child in the JSON array, with keys "
        "revision_hypothesis, name, description, and complete code; the description must link the behavior change "
        "to the supplied evidence. "
        "No fixed manual repair algorithm is mandated. Preserve existing tasks and insert all removed tasks exactly once.\n"
        f"{common.OUTPUT_FORMAT_JSON}\n")


def build_repair_revision_prompt(
    *,
    round_id: int,
    previous_summary: Dict[str, object],
    top_operators: List[Dict[str, object]],
    weak_operators: List[Dict[str, object]],
    n: int = 3,
) -> str:
    """Build a structured prompt for revising repair operator candidates."""
    return (
        f"[Operator Evolution — Revision]\n"
        f"Round: {round_id}\n"
        f"Operator Type: repair\n"
        f"Requested candidates: {n}\n\n"
        f"{common.PROBLEM_DESCRIPTION}\n"
        f"{common.CONSTRAINTS}\n"
        f"{common.REPAIR_SIGNATURE}\n"
        f"{common.REPAIR_CONTRACT_GUIDANCE}\n"
        f"{common.REPAIR_HEURISTIC_DIRECTIONS}\n\n"
        "--- Previous Round Feedback ---\n"
        f"Summary: {json.dumps(previous_summary, indent=2, default=str)}\n\n"
        f"Top operators:\n{json.dumps(top_operators, indent=2, default=str)}\n\n"
        f"Weak operators:\n{json.dumps(weak_operators, indent=2, default=str)}\n\n"
        "--- Revision Instructions ---\n"
        "Improve success_rate and avg_relative_improvement while reducing "
        "invalid/error rate.\n"
        "Learn from top operators: keep what works, fix what fails.\n"
        "Avoid repeating the same mistakes as weak operators.\n"
        "Keep the fixed function signature and return types.\n\n"
        f"{common.OUTPUT_FORMAT_JSON}\n"
    )


def build_destroy_revision_prompt(
    *,
    round_id: int,
    previous_summary: Dict[str, object],
    top_operators: List[Dict[str, object]],
    weak_operators: List[Dict[str, object]],
    n: int = 1,
) -> str:
    """Build a structured prompt for revising destroy operator candidates."""
    return (
        f"[Operator Evolution — Revision]\n"
        f"Round: {round_id}\n"
        f"Operator Type: destroy\n"
        f"Requested candidates: {n}\n\n"
        f"{common.PROBLEM_DESCRIPTION}\n"
        f"{common.CONSTRAINTS}\n"
        f"{common.DESTROY_SIGNATURE}\n"
        f"{common.DESTROY_HEURISTIC_DIRECTIONS}\n\n"
        "--- Previous Round Feedback ---\n"
        f"Summary: {json.dumps(previous_summary, indent=2, default=str)}\n\n"
        f"Top operators:\n{json.dumps(top_operators, indent=2, default=str)}\n\n"
        f"Weak operators:\n{json.dumps(weak_operators, indent=2, default=str)}\n\n"
        "--- Revision Instructions ---\n"
        "Improve success_rate and avg_relative_improvement while reducing "
        "invalid/error rate.\n"
        "Learn from top operators: keep what works, fix what fails.\n"
        "Avoid repeating the same mistakes as weak operators.\n"
        "Keep the fixed function signature and return types.\n\n"
        f"{common.OUTPUT_FORMAT_JSON}\n"
    )


def build_revision_prompt(
    *,
    operator_type: str,
    round_id: int,
    previous_summary: Dict[str, object],
    top_operators: List[Dict[str, object]],
    weak_operators: List[Dict[str, object]],
    n: int = 3,
) -> str:
    """Dispatch to the appropriate revision prompt builder."""
    if operator_type == "repair":
        return build_repair_revision_prompt(
            round_id=round_id,
            previous_summary=previous_summary,
            top_operators=top_operators,
            weak_operators=weak_operators,
            n=n,
        )
    elif operator_type == "destroy":
        return build_destroy_revision_prompt(
            round_id=round_id,
            previous_summary=previous_summary,
            top_operators=top_operators,
            weak_operators=weak_operators,
            n=n,
        )
    else:
        raise ValueError(f"Unknown operator_type: {operator_type}")
