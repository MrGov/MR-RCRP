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


def build_initial_generation_prompt(
    *,
    operator_type: str,
    round_id: int,
    evidence: Dict[str, object] | None = None,
) -> str:
    """Build the round-0 generation prompt.

    ``evidence`` is optional: supplying it lets the very first design round see the
    DP behavioural evidence, which is the whole point ofOption A (one-shot, evidence-
    driven design). Omitting it keeps the legacy ``F1_scalar`` / ``L0`` behaviour
    byte-identical.
    """
    if use_rich_prompts:
        base = _rich_gen(operator_type=operator_type, round_id=round_id)
    else:
        base = _compact_generation_prompt(operator_type=operator_type, round_id=round_id)
    if evidence is None:
        return base
    return base + "\n" + _render_evidence_sections(evidence)


def build_revision_prompt(
    *,
    operator_type: str,
    round_id: int,
    previous_summary: Dict[str, object],
    top_operators: List[Dict[str, object]],
    weak_operators: List[Dict[str, object]],
    n: int = 3,
    evidence: Dict[str, object] | None = None,
) -> str:
    """Build the revision prompt.

    ``evidence`` is an optional P2 payload (``F2_state_v2`` or
    ``F2_contrastive_v2``). When omitted the returned string is byte-identical
    to the pre-P2 implementation, so the ``F1_scalar`` baseline is unaffected.
    Evidence is appended as fixed STRUCTURE / CONTRAST / LIMITS blocks.
    """
    if use_rich_prompts:
        base = _rich_rev(
            operator_type=operator_type,
            round_id=round_id,
            previous_summary=previous_summary,
            top_operators=top_operators,
            weak_operators=weak_operators,
            n=n,
        )
    else:
        base = _compact_revision_prompt(
            operator_type=operator_type,
            round_id=round_id,
            previous_summary=previous_summary,
            top_operators=top_operators,
            weak_operators=weak_operators,
        )
    if evidence is None:
        return base
    return base + "\n" + _render_evidence_sections(evidence)


# ------------------------------------------------------------------
# P2: deterministic evidence rendering (no provider, no I/O)
# ------------------------------------------------------------------

def _fmt(value, digits: int = 1) -> str:
    if value is None:
        return "unavailable"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "unavailable"
    return f"{number:.{digits}f}"


def _fmt_pct(value) -> str:
    if value is None:
        return "unavailable"
    try:
        return f"{float(value):.2%}"
    except (TypeError, ValueError):
        return "unavailable"


def _render_structure(evidence: Dict[str, object]) -> List[str]:
    if evidence.get("feedback_mode") == "F2_state_v2_dataset":
        return _render_dataset_structure(evidence)
    lines = ["[STRUCTURE]"]
    regime = evidence.get("regime")
    if isinstance(regime, dict):
        name = regime.get("regime", "unavailable")
        detail = regime.get("evidence") or {}
        why_bits = []
        if isinstance(detail, dict):
            if detail.get("share") is not None:
                why_bits.append(
                    f"{_fmt_pct(detail.get('share'))} of informative positions reach "
                    f"|mode_gap| >= {_fmt_pct(detail.get('gap_ratio_threshold'))} of makespan"
                )
            if detail.get("ratio") is not None:
                why_bits.append(
                    f"load_excess/makespan = {_fmt_pct(detail.get('ratio'))}"
                )
            if detail.get("mean_turning_share") is not None:
                why_bits.append(
                    f"mean turning share = {_fmt_pct(detail.get('mean_turning_share'))}"
                )
            if detail.get("mean_transfer_share") is not None:
                why_bits.append(
                    f"mean transfer share = {_fmt_pct(detail.get('mean_transfer_share'))}"
                )
            if detail.get("availability") == "unavailable":
                why_bits.append(f"unavailable: {detail.get('reason', 'missing input')}")
        suffix = f" ({'; '.join(why_bits)})" if why_bits else ""
        lines.append(f"regime: {name}{suffix}")
    elif evidence.get("parent_regime") is not None:
        lines.append(
            f"regime: parent {evidence.get('parent_regime')} -> "
            f"child {evidence.get('child_regime')}"
        )
    else:
        lines.append("regime: unavailable")

    cost = evidence.get("cost_structure")
    if isinstance(cost, dict) and cost.get("availability", "ok") == "ok":
        lines.append(
            "cost: makespan={ms} transfer={tr} coverage={cov} turning={turn} "
            "load_excess={exc} ({exc_ratio})".format(
                ms=_fmt(cost.get("makespan")),
                tr=_fmt_pct(cost.get("transfer_share")),
                cov=_fmt_pct(cost.get("coverage_share")),
                turn=_fmt_pct(cost.get("turning_share")),
                exc=_fmt(cost.get("load_excess")),
                exc_ratio=_fmt_pct(cost.get("load_excess_ratio")),
            )
        )
        lines.append(
            "bottleneck_routes: {} near_bottleneck: {}".format(
                cost.get("bottleneck_routes") or [],
                cost.get("near_bottleneck_routes") or [],
            )
        )
    elif isinstance(cost, dict):
        lines.append(f"cost: unavailable: {cost.get('reason', 'missing input')}")
    else:
        lines.append("cost: unavailable")

    notes = evidence.get("position_notes")
    if isinstance(notes, list) and notes:
        lines.append("position_notes (only informative, non-tied):")
        for note in notes:
            lines.append(
                "  - task {task} pos {pos} route {route} mode {mode} gap {gap} "
                "({ratio} of makespan)".format(
                    task=note.get("task_id"),
                    pos=note.get("position"),
                    route=note.get("route_id"),
                    mode=note.get("mode_preference"),
                    gap=_fmt(note.get("mode_gap")),
                    ratio=_fmt_pct(note.get("gap_ratio_of_makespan")),
                )
            )
    else:
        lines.append("position_notes: unavailable (no informative non-tied position)")

    degeneracy = evidence.get("degeneracy")
    if isinstance(degeneracy, dict):
        if degeneracy.get("availability") == "ok":
            lines.append(
                "degenerate positions: {tied} ({tied_frac}); informative: {inf} ({inf_frac})"
                .format(
                    tied=degeneracy.get("tied_position_count"),
                    tied_frac=_fmt_pct(degeneracy.get("tied_position_fraction")),
                    inf=degeneracy.get("informative_position_count"),
                    inf_frac=_fmt_pct(degeneracy.get("informative_position_fraction")),
                )
            )
        else:
            lines.append(
                f"degenerate positions: unavailable: {degeneracy.get('reason', 'missing')}"
            )
    return lines


def _render_dataset_structure(evidence: Dict[str, object]) -> List[str]:
    lines = ["[STRUCTURE]"]
    lines.append(
        "panel: {count} instances; dominant regime: {dominant}; regimes: {counts}".format(
            count=evidence.get("instance_count"),
            dominant=evidence.get("dominant_regime", "unavailable"),
            counts=evidence.get("regime_counts") or {},
        )
    )

    cost = evidence.get("cost_structure")
    if isinstance(cost, dict) and cost.get("availability", "ok") == "ok":
        lines.append(
            "cost shares (panel mean): transfer={tr} coverage={cov} turning={turn} "
            "load_excess/makespan={exc}".format(
                tr=_fmt_pct(cost.get("mean_transfer_share")),
                cov=_fmt_pct(cost.get("mean_coverage_share")),
                turn=_fmt_pct(cost.get("mean_turning_share")),
                exc=_fmt_pct(cost.get("mean_load_excess_ratio")),
            )
        )
    elif isinstance(cost, dict):
        lines.append(f"cost: unavailable: {cost.get('reason', 'missing input')}")
    else:
        lines.append("cost: unavailable")

    scale = evidence.get("scale_note")
    if isinstance(scale, dict):
        rng = scale.get("n_tasks_range")
        lines.append(
            "scale: n_tasks {} - {}".format(
                rng[0] if isinstance(rng, list) and rng else "?", 
                rng[-1] if isinstance(rng, list) and rng else "?",
            )
        )
        if scale.get("rule"):
            lines.append(f"scale rule: {scale.get('rule')}")

    notes = evidence.get("position_notes")
    if isinstance(notes, list) and notes:
        lines.append("position_notes (informative, non-tied, largest mode gap first):")
        for note in notes:
            lines.append(
                "  - {instance} (n={n}) task {task} pos {pos} route {route} mode {mode} "
                "gap {gap} ({ratio} of makespan)".format(
                    instance=note.get("instance", "?"),
                    n=note.get("n_tasks", "?"),
                    task=note.get("task_id"),
                    pos=note.get("position"),
                    route=note.get("route_id"),
                    mode=note.get("mode_preference"),
                    gap=_fmt(note.get("mode_gap")),
                    ratio=_fmt_pct(note.get("gap_ratio_of_makespan")),
                )
            )
    else:
        lines.append("position_notes: unavailable (no informative non-tied position)")

    degeneracy = evidence.get("degeneracy")
    if isinstance(degeneracy, dict) and degeneracy.get("availability") == "ok":
        lines.append(
            "degenerate positions (panel mean): {tied} tied; the rest carry a "
            "decision signal".format(
                tied=_fmt_pct(degeneracy.get("mean_tied_position_fraction"))
            )
        )
    return lines


def _render_contrast(evidence: Dict[str, object]) -> List[str]:
    lines = ["[CONTRAST]"]
    contrast = evidence.get("contrast")
    case = contrast if isinstance(contrast, dict) else evidence
    if isinstance(case, dict) and case.get("availability") == "unavailable":
        lines.append(f"unavailable: {case.get('reason', 'no paired report supplied')}")
        return lines
    if not isinstance(case, dict) or case.get("verdict") is None:
        lines.append("unavailable: no paired report supplied")
        return lines
    lines.append(
        "input {input_id}: makespan {dm} ({dmr}) transfer {dt} processing {dp} "
        "load_excess {de} verdict {verdict}".format(
            input_id=case.get("input_id"),
            dm=_fmt(case.get("delta_makespan")),
            dmr=_fmt_pct(case.get("delta_makespan_ratio")),
            dt=_fmt(case.get("delta_mean_transfer")),
            dp=_fmt(case.get("delta_mean_processing")),
            de=_fmt(case.get("delta_load_excess")),
            verdict=case.get("verdict"),
        )
    )
    observations = case.get("observations")
    if observations:
        lines.append("observations: {}".format(", ".join(str(o) for o in observations)))
    shift = case.get("bottleneck_shift")
    if isinstance(shift, dict):
        lines.append(
            "bottleneck_shift: parent {} -> child {}".format(
                shift.get("parent") or [], shift.get("child") or []
            )
        )
    return lines


def _render_limits(evidence: Dict[str, object]) -> List[str]:
    lines = ["[LIMITS]"]
    degeneracy = evidence.get("degeneracy")
    # In dataset mode [STRUCTURE] already reports the panel tied fraction, so the
    # per-report limitation sentence would be a duplicate.
    if evidence.get("feedback_mode") == "F2_state_v2_dataset":
        pass
    elif isinstance(degeneracy, dict) and degeneracy.get("limitation_line"):
        lines.append(str(degeneracy["limitation_line"]))
    else:
        lines.append("state evidence degeneracy: unavailable")
    limitations = evidence.get("limitations")
    if isinstance(limitations, (list, tuple)):
        for entry in limitations:
            lines.append(f"- {entry}")
    else:
        lines.append("- limitations: unavailable")
    unavailable = evidence.get("unavailable_evidence")
    if isinstance(unavailable, (list, tuple)) and unavailable:
        lines.append("unavailable_evidence: {}".format("; ".join(str(u) for u in unavailable)))
    return lines


def _render_evidence_sections(evidence: Dict[str, object]) -> str:
    """Render STRUCTURE / CONTRAST / LIMITS in fixed order and wording."""
    if not isinstance(evidence, dict):
        raise ValueError("evidence must be a dict")
    lines: List[str] = []
    lines.extend(_render_structure(evidence))
    lines.extend(_render_contrast(evidence))
    lines.extend(_render_limits(evidence))
    return "\n".join(lines)


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
