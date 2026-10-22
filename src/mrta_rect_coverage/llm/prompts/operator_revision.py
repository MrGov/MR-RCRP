"""Prompt templates for operator candidate revision based on feedback."""
from __future__ import annotations

import json
from typing import Dict, List

from . import common


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
