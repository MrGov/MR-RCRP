"""Structured feedback builder for provider revision prompts."""
from __future__ import annotations

import json
from typing import Dict, List, Optional

from .eligibility_policy import candidate_is_selection_eligible
from .regime_labeler import (
    informative_positions,
    label_regime,
    report_makespan,
    route_cost_shares,
)


def build_pair_feedback(parent_row, *, destroy_identity, source_reference):
    """E7: link observed removal, restoration and external DP response.

    Select contrasting cases by decision outcome, never by largest state change.
    Sources index real evaluator trials; absence is explicit, not a zero metric.
    """
    metrics = ("dp_state_switch_fraction", "hv_mode_switch_fraction",
        "entry_corner_switch_fraction", "exit_corner_switch_fraction", "dp_cascade_count",
        "dp_cascade_ratio", "bottleneck_relief", "travel_change", "coverage_change", "turning_change")
    valid = [(i,t) for i,t in enumerate(parent_row["trials"]) if t.get("feasible")]
    losses = sorted([(i,t) for i,t in valid if t.get("parent_relative_improvement", t.get("relative_improvement",0)) < -1e-9],
                    key=lambda p: p[1].get("parent_relative_improvement",p[1].get("relative_improvement",0)))
    gains = sorted([(i,t) for i,t in valid if t.get("parent_relative_improvement", t.get("relative_improvement",0)) > 1e-9],
                   key=lambda p: -p[1].get("parent_relative_improvement",p[1].get("relative_improvement",0)))
    transfers = [(i,t) for i,t in losses if set(t.get("bottleneck_after",[])) - set(t.get("bottleneck_before",[]))]
    selected, seen = [], set()
    for category, pool in (("degradation",losses),("improvement",gains),("bottleneck_transfer",transfers)):
        for i,t in pool:
            if i in seen:
                if category == "bottleneck_transfer":
                    next(x for x in selected if x["trial_index"] == i)["also_bottleneck_transfer"] = True
                continue
            obs = dict(t)
            behavior = t.get("parent_to_candidate_behavior")
            obs["parent_to_candidate_behavior"] = {k: behavior.get(k,"unavailable") if isinstance(behavior,dict) else "unavailable" for k in metrics}
            selected.append(dict(category=category, trial_index=i,
                source=f"{source_reference}#/trials/{i}", observation=obs))
            seen.add(i)
            break
    if not selected and valid:
        i,t = valid[0]
        selected.append(dict(category="tie",trial_index=i,source=f"{source_reference}#/trials/{i}",observation=t))
    return dict(feedback_mode="E7-pair-aware", fixed_destroy=destroy_identity,
        parent_repair_hash=parent_row["source_hash"],
        summary=dict(executed=len(parent_row["trials"]),feasible=len(valid),
            improved=len(gains),degraded=len(losses),bottleneck_transfer_losses=len(transfers),
            mean_final_makespan=sum(t["candidate_makespan"] for _,t in valid)/len(valid) if valid else None),
        representative_cases=selected,
        unavailable_outcomes=[k for k,pool in (("degradation",losses),("improvement",gains),("bottleneck_transfer_loss",transfers)) if not pool],
        revision_directions=("Adapt restoration to the fixed destroy's released edge bundles, not generic random removals. "
            "Use removed_task_moves and full route sequences to inspect where slack was consumed and a new bottleneck appeared. "
            "Revise robot choice and insertion position jointly with incremental workload estimates anchored in measured partial route costs. "
            "The parent uses area-scaled work and Euclidean center detours; consider real H/V sweep/turning workload and Manhattan/depot features as approximations. "
            "Update projected loads after each insertion; avoid blindly protecting the original bottleneck once other routes become critical. "
            "Choose your own repair strategy; retain successful behavior. State/cascade changes are not objectives or penalties."),
        limitations=("All evidence is external complete-solution evaluator output. Associations are not causal proof; "
            "aggregate travel/coverage/turning deltas are totals across robots, not critical-route deltas. "
            "Final positions do not expose chronological insertion steps or intermediate estimated loads (unavailable). "
            "No per-insertion counterfactual DP evaluation is provided. Feasibility and full Exact-DP makespan decide quality."))


def coverage_mode_knowledge(*, parent: dict, diagnosed_operator: dict,
                            source_reference: str) -> dict:
    """E4-B: one geometry/workload direction, grounded in saved evaluator trials."""
    evidence = []
    # One geometry/turning loss from the common parent, then the measured F2-D
    # bottleneck failure. These are pre-existing observations, not new trials.
    for label, row in (("common_parent", parent), ("F2-D", diagnosed_operator)):
        failures = [(i, t) for i, t in enumerate(row.get("trials", []))
                    if t.get("feasible") and t.get("relative_improvement", 0) < -1e-9
                    and isinstance(t.get("exact_dp_behavior"), dict)]
        if not failures:
            continue
        chosen = next(((i, t) for i, t in failures if t["instance_id"] == "R2_T10_0" and t["solver_seed"] == 0), failures[0])
        i, trial = chosen
        evidence.append(dict(operator=label, source_hash=row["source_hash"],
            source=f"{source_reference}#operator={label}/{row['operator_id']}/trials/{i}",
            observation={k: trial[k] for k in (
                "instance_id", "solver_seed", "baseline_makespan", "candidate_makespan",
                "baseline_route_costs", "candidate_route_costs", "relative_improvement",
                "reassigned_task_count", "exact_dp_behavior") if k in trial}))
    return dict(
        research_direction="Coverage-mode-aware workload estimation",
        available_attributes=dict(
            context=["instance", "per_robot_costs", "route_costs_makespan", "bottleneck_route_id"],
            instance=["tasks", "robot_count", "depot", "sweep_width", "sweep_speed", "travel_speed", "turning_time"],
            task=["task_id", "x_left", "x_right", "y_bottom", "y_top", "width", "height"]),
        formulas=dict(
            H="n_H = ceil(task.height / context.instance.sweep_width); P_H = n_H * task.width / context.instance.sweep_speed + (n_H - 1) * context.instance.turning_time",
            V="n_V = ceil(task.width / context.instance.sweep_width); P_V = n_V * task.height / context.instance.sweep_speed + (n_V - 1) * context.instance.turning_time",
            workload="min(P_H, P_V) and abs(P_H-P_V) are possible processing hints; actual mode depends on surrounding transitions. Area is not processing time. Supplied partial-route costs already contain processing and depot travel: do not count existing tasks twice or fit processing scale to total route cost.",
            parity="Corners LB=(x_left,y_bottom), RB=(x_right,y_bottom), LT=(x_left,y_top), RT=(x_right,y_top). For H or V with odd n_sweeps: LB->RT, RB->LT, LT->RB, RT->LB. Even H: LB->LT, RB->RT, LT->LB, RT->RB. Even V: LB->RB, RB->LB, LT->RT, RT->LT. Entry, mode and exit are coupled; independently minimizing incoming and outgoing edges may be inconsistent.",
            travel="t(a,b) = (abs(a.x-b.x)+abs(a.y-b.y))/context.instance.travel_speed. For a proxy insertion between prev and next, account for t(prev,task)+t(task,next)-t(prev,next); use context.instance.depot at both route boundaries. An empty-route proxy includes outbound and return travel. A centroid/boundary/local-state hint is approximate, not the complete Route-DP value."),
        evidence=evidence,
        decision_mapping=[
            "Revise workload estimation and bottleneck projection, not just task annotations. Connect n_H/n_V, traversal and turning costs to task priority or the prospective added workload used in insertion choices.",
            "Maintain prospective route-load hints after each inserted task; compare the projected maximum across all robots, including the currently critical robot. A lower total travel can still create a worse maximum route.",
            "Use the parity knowledge to avoid incompatible local entry/exit assumptions if using corner hints. Mode/corner changes and cascade are diagnostics, not penalties; there is no arbitrary H/V switching surcharge in the model.",
            "Choose your own bounded insertion strategy. You may use processing minima, mode gaps or local consistent state hints without rebuilding Route-DP. Do not implement the DP recurrence or assume an evaluator in RepairContext. Returned sequences are evaluated externally by Exact Route-DP; feasibility and makespan are final criteria."],
        evidence_limits="Observed complete-repair associations, not causal attribution to individual insertions. Coverage/turning/travel changes are totals over all robots, not necessarily the bottleneck. Do not fabricate DP metrics.")


def select_decision_knowledge(rows: List[dict], *, parent_id: str, parent_source: str,
                              source_reference: str) -> dict:
    """Select parent-specific failure mechanisms, rather than largest DP changes.

    Rules indicate associations to inspect, never causal attribution. Count unique
    instances so deterministic duplicate seeds cannot dominate the issue choice.
    No new DP metrics: evidence contains original canonical fields verbatim.
    """
    parent = next(row for row in rows if row["operator_id"] == parent_id)
    buckets = {key: [] for key in ("bottleneck_transfer", "coverage_geometry", "route_dp_response")}
    failures = []
    for index, trial in enumerate(parent.get("trials", [])):
        if not trial.get("feasible") or not isinstance(trial.get("exact_dp_behavior"), dict):
            continue
        if trial.get("relative_improvement", 0) >= -1e-9:
            continue
        failures.append((index, trial))
        dp = trial["exact_dp_behavior"]
        before, after = trial.get("baseline_route_costs", []), trial.get("candidate_route_costs", [])
        old_critical = {i for i, cost in enumerate(before) if abs(cost - max(before)) < 1e-9}
        new_critical = {i for i, cost in enumerate(after) if abs(cost - max(after)) < 1e-9}
        if before and after and old_critical.isdisjoint(new_critical) and trial.get("reassigned_task_count", 0) > 0:
            buckets["bottleneck_transfer"].append((index, trial))
        if dp.get("hv_mode_switch_fraction", 0) > 0 and dp.get("coverage_change", 0) + dp.get("turning_change", 0) > 0:
            buckets["coverage_geometry"].append((index, trial))
        if dp.get("travel_change", 0) > 0 and (dp.get("entry_corner_switch_fraction", 0) > 0 or dp.get("exit_corner_switch_fraction", 0) > 0 or dp.get("dp_cascade_ratio", 0) > 0):
            buckets["route_dp_response"].append((index, trial))
    counts = {key: len({trial["instance_id"] for _, trial in items}) for key, items in buckets.items()}
    # Prevalence first; equal support prioritizes makespan load transfer, then geometry.
    supported = [key for key in buckets if counts[key]]
    primary = max(supported, key=lambda key: counts[key]) if supported else "insufficient_evidence"
    directions = {
        "bottleneck_transfer": "Replace static exclusion of context.bottleneck_route_id and task-count-first route choice with refreshed prospective load hints. Update estimated added work after every insertion; compare all robots including the former bottleneck. The contract supplies no evaluator: do not call or reimplement DP, or present load estimates as exact costs. The external Exact-DP evaluator remains the final makespan judge.",
        "coverage_geometry": "Replace area-only task priority with H/V processing-aware priority: compute sweep counts from rectangle geometry, sweep_width, sweep_speed and turning_time. Use processing estimates as heuristic hints only; keep state selection and final makespan evaluation in the external Exact-DP evaluator.",
        "route_dp_response": "Centroid Euclidean deltas omit corner transitions and the depot return. Use Manhattan geometry including both depot edges and rectangle boundaries as insertion hints. The contract supplies no evaluator: do not invoke or reimplement DP. Do not penalize cascade or state changes themselves; external Exact-DP evaluates the returned sequences and final makespan.",
        "insufficient_evidence": "No supported failure mechanism. Preserve the parent and request further measured trials; do not invent a DP-based defect.",
    }
    evidence = []
    seen = set()
    for issue in ([primary] + [key for key in supported if key != primary]) if supported else []:
        # One representative per issue, stable identity ordering, not metric magnitude.
        items = sorted(buckets[issue], key=lambda item: (item[1]["instance_id"], item[1]["solver_seed"]))
        available = [item for item in items if item[1]["instance_id"] not in seen]
        if not available:
            for item in evidence:
                if item["observation"]["instance_id"] in {trial["instance_id"] for _, trial in items}:
                    item.setdefault("related_revision_directions", {})[issue] = directions[issue]
                    break
            continue
        index, trial = available[0]
        seen.add(trial["instance_id"])
        evidence.append(dict(issue=issue, source=f"{source_reference}#operator={parent_id}/trials/{index}",
                             observation={key: trial[key] for key in (
                                 "instance_id", "solver_seed", "baseline_makespan", "candidate_makespan",
                                 "relative_improvement", "baseline_route_costs", "candidate_route_costs",
                                 "reassigned_task_count", "exact_dp_behavior") if key in trial},
                             revision_direction=directions[issue]))
    # A successful response with high state activity guards against a cascade penalty.
    improved = [(i, t) for i, t in enumerate(parent.get("trials", [])) if t.get("feasible") and t.get("relative_improvement", 0) > 1e-9 and isinstance(t.get("exact_dp_behavior"), dict)]
    contrast = None
    if improved:
        i, trial = sorted(improved, key=lambda pair: (pair[1]["instance_id"], pair[1]["solver_seed"]))[0]
        contrast = dict(source=f"{source_reference}#operator={parent_id}/trials/{i}",
                        instance_id=trial["instance_id"], solver_seed=trial["solver_seed"],
                        relative_improvement=trial["relative_improvement"], exact_dp_behavior=trial["exact_dp_behavior"],
                        interpretation="State changes also accompany improvements; cascade is not a penalty or causal explanation.")
    anchors = [dict(line=i, text=line.strip()) for i, line in enumerate(parent_source.splitlines(), 1)
               if any(token in line for token in ("bottleneck_route_id", "len(routes[", "context.per_robot_costs", "math.hypot", ".width *", "best_delta"))]
    return dict(primary_issue=primary, supporting_unique_failure_instances=counts,
                selection_rule="parent-only feasible failures; unique-instance support then bottleneck/geometry/response priority; representative by stable identity",
                feasible_failure_trial_count=len(failures), evidence=evidence,
                contrasting_improvement=contrast, parent_code_anchors=anchors,
                primary_revision_direction=directions[primary],
                limitations="Associations between complete repaired solutions and fixed greedy baseline; no per-insertion causal trace. Total cost components are not bottleneck-route components. Do not fabricate measurements. Feasibility and exact makespan remain final criteria.")


def build_feedback_payload(rows: List[dict], *, top_k: int = 2) -> Dict[str, object]:
    if top_k < 1:
        raise ValueError("top_k must be at least 1")
    eligible_rows = [row for row in rows if candidate_is_selection_eligible(row)]
    ordered = sorted(eligible_rows, key=lambda r: (r.get("avg_relative_improvement", 0.0), r.get("success_rate", 0.0)), reverse=True)
    top = ordered[:top_k]
    weak = ordered[-top_k:] if ordered else []
    summary = {
        "count": len(rows),
        "eligible_count": len(eligible_rows),
        "best_avg_relative_improvement": top[0]["avg_relative_improvement"] if top else 0.0,
        "best_success_rate": top[0]["success_rate"] if top else 0.0,
        "failure_type_breakdown": _failure_type_breakdown(rows),
    }
    return {
        "summary": summary,
        "top_operators": top,
        "weak_operators": weak,
    }


def _failure_type_breakdown(rows: List[dict]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in rows:
        failure_type = str(row.get("failure_type", "unknown"))
        counts[failure_type] = counts.get(failure_type, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# P2: state-evidence feedback (docs/task_P2_state_feedback.md)
#
# Everything below is a read-only projection of an already written e14 report.
# No Route-DP call, no counterfactual replay, no LLM call happens here.
# ---------------------------------------------------------------------------

#: E5 forbidden metrics: state-change counts are tie-break artefacts, not losses.
FORBIDDEN_FIELDS = (
    "state_switch_fraction",
    "hv_mode_switch_fraction",
    "entry_corner_switch_fraction",
    "exit_corner_switch_fraction",
    "dp_cascade_count",
    "dp_cascade_ratio",
    "state_edit_distance",
    "mean_regret",
    "avg_regret",
)

#: Fixed degenerate-evidence sentence (docs/p2_feedback_design.md, rule 9).
DEGENERACY_LIMITATION = (
    "state evidence is degenerate at {tied_fraction} of positions in this parent "
    "set; only {informative_fraction} carry a decision signal"
)

_FEEDBACK_LIMITATIONS = (
    "All evidence is a read-only projection of one Exact Route-DP report; no new "
    "DP or counterfactual evaluation was run to produce this feedback.",
    "Position-level regrets refer to one fixed parent task sequence; they do not "
    "characterise other sequences produced by the operator.",
    "Tied positions are excluded from position notes and reported only as an "
    "aggregate fraction; tie-broken state choices carry no evidence.",
    "Feasibility and the full Exact-DP makespan remain the only quality criteria.",
)

_CONTRAST_LIMITATIONS = (
    "Complete-solution difference on one shared input and seed; not a per-insertion "
    "causal trace.",
    "Component deltas are totals across all robots, not critical-route deltas.",
)

_POSITION_NOTE_LIMIT = 5
_CASE_BYTE_LIMIT = 800
_EPS = 1e-9


def _payload_size(payload: dict) -> int:
    return len(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8"))


def assert_no_forbidden_fields(payload) -> None:
    """Raise ``ValueError`` when any E5 forbidden metric name appears.

    Applies to the P2 payloads only. Pre-existing E7 feedback legitimately
    carries these names in its own semantics.
    """
    forbidden = tuple(name.lower() for name in FORBIDDEN_FIELDS)

    def _walk(node, path: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                lowered = str(key).lower()
                for name in forbidden:
                    if name in lowered:
                        raise ValueError(
                            f"forbidden E5 field {key!r} at {path or '<root>'}"
                        )
                _walk(value, f"{path}/{key}" if path else str(key))
        elif isinstance(node, (list, tuple)):
            for index, value in enumerate(node):
                _walk(value, f"{path}/{index}")

    _walk(payload, "")


def summarize_degeneracy(report: dict) -> dict:
    """Summarise how degenerate the state layer is for one report.

    Counts come straight from ``report["state_degeneracy"]`` (computed once by
    the instrument); this function only adds fractions, the fixed limitation
    sentence, and provenance. Missing degeneracy is reported as unavailable and
    is never replaced by zeros.
    """
    degeneracy = report.get("state_degeneracy")
    if not isinstance(degeneracy, dict) or not degeneracy.get("position_count"):
        return {
            "position_count": None,
            "tied_position_count": None,
            "all_equal_position_count": None,
            "informative_position_count": None,
            "tied_position_fraction": None,
            "all_equal_position_fraction": None,
            "informative_position_fraction": None,
            "mode_gap_abs_median": None,
            "mode_gap_abs_max": None,
            "mode_preference_counts": None,
            "limitation_line": "state evidence unavailable: no degeneracy summary",
            "source": "#/state_degeneracy",
            "availability": "unavailable",
            "reason": "report carries no state_degeneracy",
        }

    def _fraction(count_key: str) -> Optional[float]:
        count = degeneracy.get(count_key)
        total = degeneracy.get("position_count")
        if count is None or not total:
            return None
        return float(count) / float(total)

    tied_fraction = _fraction("tied_position_count")
    informative_fraction = _fraction("informative_position_count")
    if tied_fraction is None or informative_fraction is None:
        limitation_line = "state evidence unavailable: incomplete degeneracy summary"
    else:
        limitation_line = DEGENERACY_LIMITATION.format(
            tied_fraction=f"{tied_fraction:.1%}",
            informative_fraction=f"{informative_fraction:.1%}",
        )
    return {
        "position_count": degeneracy.get("position_count"),
        "tied_position_count": degeneracy.get("tied_position_count"),
        "all_equal_position_count": degeneracy.get("all_equal_position_count"),
        "informative_position_count": degeneracy.get("informative_position_count"),
        "tied_position_fraction": tied_fraction,
        "all_equal_position_fraction": _fraction("all_equal_position_count"),
        "informative_position_fraction": informative_fraction,
        "mode_gap_abs_median": degeneracy.get("mode_gap_abs_median"),
        "mode_gap_abs_max": degeneracy.get("mode_gap_abs_max"),
        "mode_preference_counts": dict(degeneracy.get("mode_preference_counts") or {}),
        "limitation_line": limitation_line,
        "source": "#/state_degeneracy",
        "availability": "ok",
    }


def _cost_structure(report: dict) -> dict:
    """E1: route cost structure, the headline evidence."""
    makespan = report_makespan(report)
    objective = report.get("objective") or {}
    route_costs = [float(cost) for cost in report.get("per_robot_costs") or []]
    load_excess = report.get("route_load_excess")
    if load_excess is None:
        load_excess = objective.get("load_excess")
    shares = route_cost_shares(report)
    near = (
        [
            index
            for index, cost in enumerate(route_costs)
            if cost >= 0.95 * makespan
        ]
        if makespan
        else []
    )
    return {
        "makespan": makespan,
        "per_robot_costs": route_costs,
        "load_excess": None if load_excess is None else float(load_excess),
        "load_excess_ratio": (
            None
            if load_excess is None or not makespan
            else float(load_excess) / makespan
        ),
        "bottleneck_routes": list(report.get("bottleneck_routes") or []),
        "near_bottleneck_routes": near,
        "transfer_share": shares["mean_transfer_share"],
        "coverage_share": shares["mean_coverage_share"],
        "turning_share": shares["mean_turning_share"],
        "source": "#/objective",
        "availability": "ok" if makespan is not None else "unavailable",
    }


def _position_notes(report: dict, makespan: Optional[float]) -> List[dict]:
    """E4: at most five informative, non-tied positions, largest gap first."""
    rows = [row for row in informative_positions(report) if row.get("tied_state_count") == 1]
    if not makespan:
        return []
    scored = []
    for row in rows:
        if row.get("mode_gap") is None:
            continue
        gap = abs(float(row["mode_gap"]))
        scored.append((gap / makespan, row))
    scored.sort(key=lambda item: (-item[0], item[1].get("route_id") or 0,
                                  item[1].get("route_position") or 0))
    notes = []
    for ratio, row in scored[:_POSITION_NOTE_LIMIT]:
        route_id = row.get("route_id")
        position = row.get("position", row.get("route_position"))
        notes.append(
            {
                "task_id": row.get("task_id"),
                "position": position,
                "route_id": route_id,
                "chosen_state_id": row.get("chosen_state_id"),
                "mode_preference": row.get("mode_preference"),
                "mode_gap": float(row["mode_gap"]),
                "tied_state_count": row.get("tied_state_count"),
                "gap_ratio_of_makespan": ratio,
                "source": (
                    f"#/routes/{route_id}/regret_table/{row.get('route_position')}"
                ),
            }
        )
    return notes


def build_state_regret_feedback(
    report: dict, *, budget_bytes: int = 2500, contrast: Optional[dict] = None
) -> dict:
    """Build the ``F2_state_v2`` payload (E1 + E2 + E3 + E4 aggregate).

    Degradation when over budget, in this exact order and no other: drop position
    notes, then the mode-preference histogram, then trim the regime evidence.
    ``cost_structure``, ``limitations`` and ``degeneracy.limitation_line`` are
    never truncated.
    """
    if budget_bytes < 1:
        raise ValueError("budget_bytes must be at least 1")
    makespan = report_makespan(report)
    regime = label_regime(report)
    degeneracy = summarize_degeneracy(report)
    unavailable = []

    if regime["regime"] == "unknown":
        unavailable.append("regime: no positive makespan in report")
    if degeneracy["availability"] != "ok":
        unavailable.append("degeneracy: report carries no state_degeneracy")
    cost_structure = _cost_structure(report)
    if cost_structure["availability"] != "ok":
        unavailable.append("cost_structure: makespan unavailable")

    limitations = list(_FEEDBACK_LIMITATIONS)
    if degeneracy["availability"] == "ok":
        limitations.append(degeneracy["limitation_line"])

    payload = {
        "feedback_mode": "F2_state_v2",
        "budget_bytes": budget_bytes,
        "regime": {"regime": regime["regime"], "evidence": regime["evidence"]},
        "cost_structure": cost_structure,
        "degeneracy": degeneracy,
        "position_notes": _position_notes(report, makespan),
        "contrast": (
            {
                key: value
                for key, value in (contrast or {}).items()
                if key not in {"byte_size", "budget_bytes", "feedback_mode"}
            }
            if contrast
            else {"availability": "unavailable", "reason": "no paired report supplied"}
        ),
        "limitations": limitations,
        "unavailable_evidence": unavailable,
        "byte_size": 0,
    }
    if not payload["position_notes"]:
        unavailable.append("position_notes: no informative non-tied position")

    def _size(value: dict) -> int:
        probe = dict(value)
        probe["byte_size"] = 0
        return _payload_size(probe)

    payload["byte_size"] = _size(payload)
    while payload["byte_size"] > budget_bytes and payload["position_notes"]:
        payload["position_notes"].pop()
        payload["byte_size"] = _size(payload)
    if payload["byte_size"] > budget_bytes and degeneracy.get("mode_preference_counts"):
        payload["degeneracy"] = dict(payload["degeneracy"])
        payload["degeneracy"]["mode_preference_counts"] = None
        payload["byte_size"] = _size(payload)
    if payload["byte_size"] > budget_bytes:
        payload["regime"] = {
            "regime": regime["regime"],
            "evidence": {
                key: regime["evidence"].get(key)
                for key in ("regime", "threshold", "share", "ratio",
                            "mean_turning_share", "mean_transfer_share", "rule")
                if key in regime["evidence"]
            },
        }
        payload["byte_size"] = _size(payload)
    if payload["byte_size"] > budget_bytes:
        raise ValueError(
            f"F2_state_v2 payload cannot fit {budget_bytes} bytes "
            f"({payload['byte_size']} after degradation)"
        )

    assert_no_forbidden_fields(payload)
    return payload


def build_paired_contrast(
    parent_report: dict, child_report: dict, *, budget_bytes: int = 4000
) -> dict:
    """Build the ``F2_contrastive_v2`` single-case payload.

    The two reports must share ``input_id``, ``fixed_destroy_hash`` and
    ``solver_seed``; otherwise the comparison is not paired and this raises.
    """
    if budget_bytes < 1:
        raise ValueError("budget_bytes must be at least 1")
    parent_key = (
        parent_report.get("input_id"),
        parent_report.get("fixed_destroy_hash"),
        parent_report.get("solver_seed"),
    )
    child_key = (
        child_report.get("input_id"),
        child_report.get("fixed_destroy_hash"),
        child_report.get("solver_seed"),
    )
    if parent_key != child_key:
        raise ValueError(
            "contrast requires a paired input: (input_id, fixed_destroy_hash, "
            f"solver_seed) differ: parent={parent_key} child={child_key}"
        )
    if parent_key[0] is None:
        raise ValueError("contrast requires an input_id on both reports")

    parent_makespan = report_makespan(parent_report)
    child_makespan = report_makespan(child_report)
    if parent_makespan is None or child_makespan is None:
        raise ValueError("contrast requires a positive makespan on both reports")

    parent_objective = parent_report.get("objective") or {}
    child_objective = child_report.get("objective") or {}
    delta_makespan = child_makespan - parent_makespan
    delta_transfer = float(child_objective.get("mean_transfer", 0.0)) - float(
        parent_objective.get("mean_transfer", 0.0)
    )
    delta_processing = float(child_objective.get("mean_processing", 0.0)) - float(
        parent_objective.get("mean_processing", 0.0)
    )
    parent_excess = parent_report.get("route_load_excess")
    child_excess = child_report.get("route_load_excess")
    delta_load_excess = float(child_excess or 0.0) - float(parent_excess or 0.0)

    if delta_makespan < -_EPS:
        verdict = "improved"
    elif delta_makespan > _EPS:
        verdict = "degraded"
    else:
        verdict = "tie"

    observations = []
    if delta_transfer < -_EPS:
        observations.append("transfer_down")
    if delta_load_excess < -_EPS:
        observations.append("balance_improved")
    if delta_processing < -_EPS:
        observations.append("processing_down")
    if not observations:
        observations.append("mixed")

    payload = {
        "feedback_mode": "F2_contrastive_v2",
        "budget_bytes": budget_bytes,
        "input_id": parent_key[0],
        "fixed_destroy_hash": parent_key[1],
        "solver_seed": parent_key[2],
        "delta_makespan": delta_makespan,
        "delta_makespan_ratio": delta_makespan / parent_makespan,
        "delta_mean_transfer": delta_transfer,
        "delta_mean_processing": delta_processing,
        "delta_load_excess": delta_load_excess,
        "verdict": verdict,
        "observations": observations,
        "parent_regime": label_regime(parent_report)["regime"],
        "child_regime": label_regime(child_report)["regime"],
        "bottleneck_shift": {
            "parent": list(parent_report.get("bottleneck_routes") or []),
            "child": list(child_report.get("bottleneck_routes") or []),
        },
        "limitations": list(_CONTRAST_LIMITATIONS),
        "byte_size": 0,
    }

    def _size(value: dict) -> int:
        probe = dict(value)
        probe["byte_size"] = 0
        return _payload_size(probe)

    payload["byte_size"] = _size(payload)
    if payload["byte_size"] > _CASE_BYTE_LIMIT:
        payload["observations"] = []
        payload["byte_size"] = _size(payload)
    if payload["byte_size"] > _CASE_BYTE_LIMIT:
        raise ValueError(
            "F2_contrastive_v2 single case exceeds "
            f"{_CASE_BYTE_LIMIT} bytes ({payload['byte_size']})"
        )
    if payload["byte_size"] > budget_bytes:
        raise ValueError(
            f"F2_contrastive_v2 case exceeds budget {budget_bytes} "
            f"({payload['byte_size']})"
        )

    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False).lower()
    for phrase in ("caused by", "due to", "because"):
        if phrase in serialized:
            raise ValueError(f"contrast payload must not assert causation: {phrase!r}")
    assert_no_forbidden_fields(payload)
    return payload


_DATASET_LIMITATION = (
    "Evidence aggregates a fixed instance panel solved by one deterministic reference "
    "solver; it describes where state choice can matter, not what any candidate operator did."
)


def build_dataset_evidence(
    reports: List[dict], *, budget_bytes: int = 2500, max_notes: int = 5
) -> dict:
    """Dataset-level ``F2_state_v2`` evidence (E1 + E3 + E4), one payload per run.

    Candidate-agnostic by construction: every field comes from instance structure
    and the reference solution, so it never mixes in a candidate's own outcome.
    Scale is reported explicitly because the state lever shrinks with ``n_tasks``.
    """
    if not reports:
        raise ValueError("build_dataset_evidence requires at least one report")
    if budget_bytes < 1:
        raise ValueError("budget_bytes must be at least 1")

    regime_counts: Dict[str, int] = {}
    transfer: List[float] = []
    coverage: List[float] = []
    turning: List[float] = []
    load_ratio: List[float] = []
    degenerate: List[float] = []
    notes: List[dict] = []
    unavailable: List[str] = []

    for report in reports:
        makespan = report_makespan(report)
        label = str((report.get("instance") or {}).get("name") or report.get("instance_id") or "?")
        regime = label_regime(report)
        regime_counts[regime["regime"]] = regime_counts.get(regime["regime"], 0) + 1
        if regime["regime"] == "unknown":
            unavailable.append(f"{label}: unknown regime (no positive makespan)")
        shares = route_cost_shares(report)
        if shares["mean_transfer_share"] is not None:
            transfer.append(shares["mean_transfer_share"])
            coverage.append(shares["mean_coverage_share"])
            turning.append(shares["mean_turning_share"])
        if makespan:
            excess = report.get("route_load_excess")
            if excess is not None:
                load_ratio.append(excess / makespan)
        degeneracy = summarize_degeneracy(report)
        if degeneracy["availability"] == "ok":
            if degeneracy["position_count"]:
                degenerate.append(degeneracy["tied_position_count"] / degeneracy["position_count"])
        else:
            unavailable.append(f"{label}: no state_degeneracy block")
        if makespan:
            for note in _position_notes(report, makespan)[:max_notes]:
                note = dict(note)
                note["instance"] = label
                note["n_tasks"] = (report.get("instance") or {}).get("task_count")
                notes.append(note)

    notes.sort(key=lambda note: note.get("gap_ratio", 0.0), reverse=True)

    def _mean(values: List[float]) -> Optional[float]:
        return sum(values) / len(values) if values else None

    dominant = max(regime_counts, key=regime_counts.get) if regime_counts else "unknown"
    mean_tied = _mean(degenerate)
    dataset_limitation_line = (
        DEGENERACY_LIMITATION.format(
            tied_fraction=f"{mean_tied:.1%}",
            informative_fraction=f"{1.0 - mean_tied:.1%}",
        )
        if mean_tied is not None
        else "state evidence unavailable: no degeneracy summary in any report"
    )
    payload = {
        "feedback_mode": "F2_state_v2_dataset",
        "budget_bytes": budget_bytes,
        "instance_count": len(reports),
        "regime_counts": dict(sorted(regime_counts.items())),
        "dominant_regime": dominant,
        "cost_structure": {
            "availability": "ok" if transfer else "unavailable",
            "mean_transfer_share": _mean(transfer),
            "mean_coverage_share": _mean(coverage),
            "mean_turning_share": _mean(turning),
            "mean_load_excess_ratio": _mean(load_ratio),
        },
        "scale_note": {
            "n_tasks_range": [
                min((report.get("instance") or {}).get("task_count") or 0 for report in reports),
                max((report.get("instance") or {}).get("task_count") or 0 for report in reports),
            ],
            "rule": "state choice matters mostly on small instances and HV-GEOM geometry; "
                    "check n_tasks before targeting state-level behaviour",
        },
        "degeneracy": {
            "availability": "ok" if degenerate else "unavailable",
            "mean_tied_position_fraction": mean_tied,
            "limitation_line": dataset_limitation_line,
        },
        "position_notes": notes[:max_notes],
        "unavailable": sorted(set(unavailable)),
        "limitations": [
            "Evidence is a read-only aggregation of Exact Route-DP reports over a fixed "
            "instance panel; no new DP or counterfactual evaluation was run to produce it.",
            "Position regrets refer to the task sequences the panel solutions happened to "
            "contain; they do not characterise other sequences an operator may produce.",
            "Tied positions are excluded from position notes and reported only as an "
            "aggregate fraction; tie-broken state choices carry no evidence.",
            "Feasibility and the full Exact-DP makespan remain the only quality criteria.",
            _DATASET_LIMITATION,
        ],
    }

    payload["byte_size"] = 0
    while True:
        # The reported size must cover the payload that actually ships: the byte count
        # is recomputed with its own digits in place, which converges in two passes
        # because the field itself grows by at most two characters.
        for _ in range(4):
            measured = _payload_size(payload)
            if payload["byte_size"] == measured:
                break
            payload["byte_size"] = measured
        if _payload_size(payload) <= budget_bytes:
            break
        payload["byte_size"] = 0
        if payload["position_notes"]:
            payload["position_notes"].pop()
            continue
        if payload["regime_counts"]:
            payload["regime_counts"] = {}
            payload["dominant_regime"] = dominant
            continue
        raise ValueError(
            f"F2_state_v2 dataset payload cannot fit {budget_bytes} bytes "
            f"({_payload_size(payload)} after degradation)"
        )
    assert_no_forbidden_fields(payload)
    return payload
