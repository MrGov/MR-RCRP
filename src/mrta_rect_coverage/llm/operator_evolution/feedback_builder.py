"""Structured feedback builder for provider revision prompts."""
from __future__ import annotations

from typing import Dict, List

from .eligibility_policy import candidate_is_selection_eligible


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
