"""Prompt templates for offline operator generation and revision.

This module preserves the original API used by :mod:`evolution_loop`.
Internally it delegates to the richer templates in :mod:`llm.prompts`
when the ``use_rich_prompts`` flag is set, falling back to the original
compact prompts for backward compatibility.
"""
from __future__ import annotations

from typing import Dict, List

# Rich prompt module (always importable, no external deps)
from ..prompts.operator_generation import build_generation_prompt as _rich_gen
from ..prompts.operator_revision import build_revision_prompt as _rich_rev

# Module-level flag: set to True to use the structured LLM prompts.
# The evolution loop sets this when a real LLM provider is active.
use_rich_prompts: bool = False


def build_initial_generation_prompt(*, operator_type: str, round_id: int) -> str:
    if use_rich_prompts:
        return _rich_gen(operator_type=operator_type, round_id=round_id)
    return _compact_generation_prompt(operator_type=operator_type, round_id=round_id)


def build_revision_prompt(
    *,
    operator_type: str,
    round_id: int,
    previous_summary: Dict[str, object],
    top_operators: List[Dict[str, object]],
    weak_operators: List[Dict[str, object]],
    n: int = 3,
) -> str:
    if use_rich_prompts:
        return _rich_rev(
            operator_type=operator_type,
            round_id=round_id,
            previous_summary=previous_summary,
            top_operators=top_operators,
            weak_operators=weak_operators,
            n=n,
        )
    return _compact_revision_prompt(
        operator_type=operator_type,
        round_id=round_id,
        previous_summary=previous_summary,
        top_operators=top_operators,
        weak_operators=weak_operators,
    )


# ------------------------------------------------------------------
# Original compact prompts (preserved for mock/file providers)
# ------------------------------------------------------------------

def _compact_generation_prompt(*, operator_type: str, round_id: int) -> str:
    return (
        f"[Operator Evolution]\n"
        f"Round: {round_id}\n"
        f"Operator Type: {operator_type}\n"
        "Problem: Multi-robot rectangular coverage routing minimizing makespan.\n"
        "You must output only a Python function body compatible with fixed template.\n"
        "Allowed context: per-route costs, bottleneck route id, task geometry stats.\n"
        "Forbidden: API/network/file access, random protocol changes, new dependencies.\n"
        "Required signature:\n"
        "repair(partial_solution, unassigned_tasks, context, rng) -> RepairResult\n"
        "destroy(solution, context, rng) -> DestroyResult\n"
        "Design goal: create MRTA-rectangle-specific operators, not generic VRP operators.\n"
        "Repair focus: DP-aware insertion, bottleneck-balancing, geometry-aware insertion, H/V-gap-aware insertion, critical-route-sensitive repair.\n"
        "Destroy focus: bottleneck-route destroy, geometry-aware destroy, long-rectangle-sensitive destroy, H/V-gap-sensitive destroy.\n"
    )


def _compact_revision_prompt(
    *,
    operator_type: str,
    round_id: int,
    previous_summary: Dict[str, object],
    top_operators: List[Dict[str, object]],
    weak_operators: List[Dict[str, object]],
) -> str:
    return (
        f"[Operator Evolution Revision]\n"
        f"Round: {round_id}\n"
        f"Operator Type: {operator_type}\n"
        f"Previous summary: {previous_summary}\n"
        f"Top operators: {top_operators}\n"
        f"Weak operators: {weak_operators}\n"
        "Improve success_rate and avg_relative_improvement while reducing invalid/error rate.\n"
        "Keep fixed function signature and return types.\n"
        "Generate problem-specific logic for rectangular coverage, not generic routing.\n"
    )
