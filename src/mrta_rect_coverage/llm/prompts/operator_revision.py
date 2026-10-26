"""Prompt templates for operator candidate revision based on feedback."""
from __future__ import annotations

import json
from typing import Dict, List

from . import common


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
        "For these released tasks and retained routes, how should robot selection, insertion position and workload "
        "projection change to restore a smaller feasible makespan? Revise this actual repair; do not generate or change "
        "the destroy. Do not fabricate metrics or call/reimplement DP. Do not merely copy formulas into unused code. "
        "Return up to two distinct child strategies with concise descriptions connecting code changes to evidence. "
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
