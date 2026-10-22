"""Prompt templates for initial operator candidate generation."""
from __future__ import annotations

from . import common


def build_repair_generation_prompt(*, round_id: int, n: int = 3) -> str:
    """Build a structured prompt for generating repair operator candidates."""
    return (
        f"[Operator Evolution — Initial Generation]\n"
        f"Round: {round_id}\n"
        f"Operator Type: repair\n"
        f"Requested candidates: {n}\n\n"
        f"{common.PROBLEM_DESCRIPTION}\n"
        f"{common.CONSTRAINTS}\n"
        f"{common.REPAIR_SIGNATURE}\n"
        f"{common.REPAIR_CONTRACT_GUIDANCE}\n"
        f"{common.REPAIR_HEURISTIC_DIRECTIONS}\n"
        f"{common.OUTPUT_FORMAT_JSON}\n"
        "Generate diverse, problem-specific repair operators. "
        "Each candidate should use a DIFFERENT heuristic strategy.\n"
    )


def build_destroy_generation_prompt(*, round_id: int, n: int = 1) -> str:
    """Build a structured prompt for generating destroy operator candidates."""
    return (
        f"[Operator Evolution — Initial Generation]\n"
        f"Round: {round_id}\n"
        f"Operator Type: destroy\n"
        f"Requested candidates: {n}\n\n"
        f"{common.PROBLEM_DESCRIPTION}\n"
        f"{common.CONSTRAINTS}\n"
        f"{common.DESTROY_SIGNATURE}\n"
        f"{common.DESTROY_HEURISTIC_DIRECTIONS}\n"
        f"{common.OUTPUT_FORMAT_JSON}\n"
        "Generate diverse, problem-specific destroy operators. "
        "Each candidate should use a DIFFERENT heuristic strategy.\n"
    )


def build_generation_prompt(*, operator_type: str, round_id: int, n: int = 3) -> str:
    """Dispatch to the appropriate generation prompt builder."""
    if operator_type == "repair":
        return build_repair_generation_prompt(round_id=round_id, n=n)
    elif operator_type == "destroy":
        return build_destroy_generation_prompt(round_id=round_id, n=n)
    else:
        raise ValueError(f"Unknown operator_type: {operator_type}")
