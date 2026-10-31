"""Deterministic regime labelling for state-evidence reports.

The labeller turns one e14 report (a plain dict, as written to
``outputs/e14_state_regret_instrument``) into a structural label plus the
measurements that triggered it. It is deliberately a pure dict -> dict
function: no I/O, no randomness, no core/experiment imports, no LLM calls.

Thresholds are frozen by ``docs/p2_feedback_design.md`` (section 7). They were
chosen on the 846-position E14 measurement, not fitted per report, so they must
not be tuned inside this module.

Sanity (not a research claim): on the 21 real parent reports the label agrees
with the instance family prefix at 100% - ``E10_HV-GEOM`` is the only family
that reaches ``mode_sensitive``.
"""
from __future__ import annotations

from typing import Dict, List, Optional

# Frozen thresholds (docs/p2_feedback_design.md section 3 / section 7).
REGIME_THRESHOLDS = {
    "mode_sensitive_gap_ratio": 0.01,
    "mode_sensitive_position_share": 0.25,
    "balance_dominated_load_excess_ratio": 0.15,
    "turn_heavy_turning_share": 0.06,
    "transfer_dominated_transfer_share": 0.75,
}

REGIMES = (
    "mode_sensitive",
    "balance_dominated",
    "turn_heavy",
    "transfer_dominated",
    "mixed",
    "unknown",
)

_EPS = 1e-12


def report_makespan(report: dict) -> Optional[float]:
    """Return the report makespan, or ``None`` when it is missing/non-positive."""
    makespan = report.get("makespan")
    if makespan is None:
        objective = report.get("objective") or {}
        makespan = objective.get("makespan")
    if makespan is None:
        return None
    try:
        value = float(makespan)
    except (TypeError, ValueError):
        return None
    if value <= _EPS:
        return None
    return value


def informative_positions(report: dict) -> List[dict]:
    """Return only positions carrying a decision signal, in report order.

    Each entry is ``{"route_id", "route_position", <original position fields>}``.
    A position is included only when ``informative`` is exactly true; ties are
    not informative by construction and are therefore excluded.
    """
    selected: List[dict] = []
    for route in report.get("routes") or []:
        route_id = route.get("route_id")
        for index, position in enumerate(route.get("regret_table") or []):
            if position.get("informative") is not True:
                continue
            row = dict(position)
            row.setdefault("route_id", route_id)
            row.setdefault("route_position", index)
            selected.append(row)
    return selected


def has_regret_table(report: dict) -> bool:
    """True when at least one route carries a regret table."""
    return any(route.get("regret_table") for route in report.get("routes") or [])


def route_cost_shares(report: dict) -> dict:
    """Mean transfer/turning/coverage share over routes, computed from cost splits."""
    splits = [
        route.get("cost_split")
        for route in report.get("routes") or []
        if isinstance(route.get("cost_split"), dict)
    ]

    def _mean(key: str) -> Optional[float]:
        values = [float(split[key]) for split in splits if split.get(key) is not None]
        if not values:
            return None
        return sum(values) / len(values)

    return {
        "route_count": len(splits),
        "mean_transfer_share": _mean("transfer_share"),
        "mean_coverage_share": _mean("coverage_share"),
        "mean_turning_share": _mean("turning_share"),
    }


def large_gap_share(report: dict) -> dict:
    """Share of informative positions whose |mode_gap| reaches 1% of makespan."""
    makespan = report_makespan(report)
    positions = informative_positions(report)
    threshold_ratio = REGIME_THRESHOLDS["mode_sensitive_gap_ratio"]
    if makespan is None or not positions:
        return {
            "availability": "unavailable",
            "reason": (
                "makespan unavailable" if makespan is None else "no informative positions"
            ),
            "informative_count": len(positions),
        }
    large = 0
    for position in positions:
        gap = position.get("mode_gap")
        if gap is None:
            continue
        if abs(float(gap)) >= threshold_ratio * makespan:
            large += 1
    return {
        "availability": "ok",
        "informative_count": len(positions),
        "large_gap_position_count": large,
        "share": large / len(positions),
        "gap_ratio_threshold": threshold_ratio,
    }


def label_regime(report: dict) -> dict:
    """Return ``{"regime": str, "evidence": {...}}`` for one e14 report.

    Rules are evaluated in a fixed order and the first hit wins, so the labels
    stay mutually exclusive:

    1. ``mode_sensitive``      - >=25% of informative positions reach a 1% mode gap
    2. ``balance_dominated``   - load_excess / makespan >= 0.15
    3. ``turn_heavy``          - mean turning share >= 0.06
    4. ``transfer_dominated``  - mean transfer share >= 0.75
    5. ``mixed``               - none of the above

    A rule whose input is missing is skipped (never treated as zero) and its
    evidence entry is marked ``unavailable``.
    """
    makespan = report_makespan(report)
    if makespan is None:
        return {
            "regime": "unknown",
            "evidence": {
                "availability": "unavailable",
                "reason": "report has no positive makespan",
            },
        }

    evidence: Dict[str, object] = {}
    shares = route_cost_shares(report)

    gap_evidence = large_gap_share(report)
    evidence["mode_sensitive"] = gap_evidence
    if gap_evidence["availability"] == "ok":
        if gap_evidence["share"] >= REGIME_THRESHOLDS["mode_sensitive_position_share"]:
            return {
                "regime": "mode_sensitive",
                "evidence": {
                    "regime": "mode_sensitive",
                    "threshold": REGIME_THRESHOLDS["mode_sensitive_position_share"],
                    "share": gap_evidence["share"],
                    "large_gap_position_count": gap_evidence["large_gap_position_count"],
                    "informative_count": gap_evidence["informative_count"],
                    "gap_ratio_threshold": gap_evidence["gap_ratio_threshold"],
                    "rule": (
                        "share(|mode_gap| >= 1% makespan among informative positions) "
                        ">= 0.25"
                    ),
                },
            }
    elif not has_regret_table(report):
        evidence["mode_sensitive"] = {
            "availability": "unavailable",
            "reason": "report has no regret table (include_regret=False)",
        }

    load_excess = report.get("route_load_excess")
    if load_excess is None:
        objective = report.get("objective") or {}
        load_excess = objective.get("load_excess")
    if load_excess is not None:
        ratio = float(load_excess) / makespan
        evidence["balance_dominated"] = {
            "availability": "ok",
            "load_excess": float(load_excess),
            "makespan": makespan,
            "ratio": ratio,
        }
        if ratio >= REGIME_THRESHOLDS["balance_dominated_load_excess_ratio"]:
            return {
                "regime": "balance_dominated",
                "evidence": {
                    "regime": "balance_dominated",
                    "threshold": REGIME_THRESHOLDS[
                        "balance_dominated_load_excess_ratio"
                    ],
                    "load_excess": float(load_excess),
                    "makespan": makespan,
                    "ratio": ratio,
                    "rule": "load_excess / makespan >= 0.15",
                },
            }
    else:
        evidence["balance_dominated"] = {
            "availability": "unavailable",
            "reason": "report has no route_load_excess",
        }

    turning_share = shares["mean_turning_share"]
    if turning_share is not None:
        evidence["turn_heavy"] = {
            "availability": "ok",
            "mean_turning_share": turning_share,
        }
        if turning_share >= REGIME_THRESHOLDS["turn_heavy_turning_share"]:
            return {
                "regime": "turn_heavy",
                "evidence": {
                    "regime": "turn_heavy",
                    "threshold": REGIME_THRESHOLDS["turn_heavy_turning_share"],
                    "mean_turning_share": turning_share,
                    "rule": "mean(turning / route total) >= 0.06",
                },
            }
    else:
        evidence["turn_heavy"] = {
            "availability": "unavailable",
            "reason": "no route cost splits",
        }

    transfer_share = shares["mean_transfer_share"]
    if transfer_share is not None:
        evidence["transfer_dominated"] = {
            "availability": "ok",
            "mean_transfer_share": transfer_share,
        }
        if transfer_share >= REGIME_THRESHOLDS["transfer_dominated_transfer_share"]:
            return {
                "regime": "transfer_dominated",
                "evidence": {
                    "regime": "transfer_dominated",
                    "threshold": REGIME_THRESHOLDS["transfer_dominated_transfer_share"],
                    "mean_transfer_share": transfer_share,
                    "rule": "mean(transfer / route total) >= 0.75",
                },
            }
    else:
        evidence["transfer_dominated"] = {
            "availability": "unavailable",
            "reason": "no route cost splits",
        }

    return {
        "regime": "mixed",
        "evidence": {
            "regime": "mixed",
            "candidates": evidence,
            "rule": "no single structural dominance reached its frozen threshold",
        },
    }
