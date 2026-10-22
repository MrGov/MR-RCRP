"""Structured feedback builder for provider revision prompts."""
from __future__ import annotations

from typing import Dict, List

from .eligibility_policy import candidate_is_selection_eligible


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
