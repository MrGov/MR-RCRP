"""Decision-level audit of destroy and repair moves, priced exactly.

Why this exists
---------------
The ALNS credit assignment (``8/3/1`` rewards feeding segment weights) scores an
operator by *outcome*: did this iteration improve the makespan?  That signal is
carried through simulated annealing acceptance, the destroy/repair coupling, and
the seed, so a single operator call is close to pure noise.  Selection therefore
cannot tell a myopic insertion from a balance-aware one, and offline LLM revision
gets the same diluted signal.

This module measures the *decision* instead.  Given the state an operator had to
act on, every quantity below is exact -- it comes from the same forward/backward
Route-DP tables the evaluator uses -- and it never touches the search: the audit
only reads the pricer, it cannot change an accepted solution.

Two objectives, on purpose
--------------------------
On this problem the makespan is ``max_r`` route cost, while the summed route cost
is a different objective.  A repair operator that inserts into the cheapest
route minimises the sum, but that is exactly the wrong move when the cheap route
is already the bottleneck.  So each decision is priced against both:

* ``best_sum_route``      - the route minimising ``cost(r) + price(t, r)``
* ``best_makespan_route`` - the route minimising ``max(cost(r) + price(t, r),
  max_{r' != r} cost(r'))``

Registering which one an operator actually serves is the whole point: a profile
of ``sum``/``makespan`` hit rates separates a myopic operator from a
load-balancing one, which no makespan delta can do.

Cost
----
For one repair call with ``k`` removed tasks over ``R`` routes this is ``R``
table builds (each already cached by the pricer) plus ``k * R`` slot prices of
``O(64)``.  On a 4-route, 10-task destroy that is well under a millisecond.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from ..core.incremental_route import RouteIncrementalEvaluator

# Prices that differ by less than this are the same decision.  The tables are
# exact to floating point, so the tolerance only absorbs summation order.
DECISION_TOLERANCE = 1e-9


@dataclass(frozen=True)
class DestroyDecision:
    """How good the removal set was, measured by exact in-route savings."""

    removed: Tuple[int, ...]
    removed_savings: Tuple[float, ...]
    top_k: Tuple[int, ...]
    top_k_savings: Tuple[float, ...]
    precision: float
    saving_capture: float
    total_tasks: int

    @property
    def is_random_level(self) -> bool:
        """True when the removal set is no better than a uniform draw."""
        expected = len(self.removed) / self.total_tasks if self.total_tasks else 0.0
        return self.precision <= expected + DECISION_TOLERANCE


@dataclass(frozen=True)
class RepairDecision:
    """One removed task and the placement the operator actually chose."""

    task_id: int
    assigned_route: int
    sum_optimal_route: int
    makespan_optimal_route: int
    price_assigned: float
    price_best_sum: float
    makespan_assigned: float
    makespan_best: float

    @property
    def sum_regret(self) -> float:
        return self.price_assigned - self.price_best_sum

    @property
    def makespan_regret(self) -> float:
        return self.makespan_assigned - self.makespan_best

    @property
    def is_sum_optimal(self) -> bool:
        return self.sum_regret <= DECISION_TOLERANCE

    @property
    def is_makespan_optimal(self) -> bool:
        return self.makespan_regret <= DECISION_TOLERANCE


@dataclass
class RepairDecisionAudit:
    """Aggregate decision profile of one repair call."""

    decisions: List[RepairDecision] = field(default_factory=list)
    makespan_scale: float = 1.0

    def _profile(self, items: Sequence[RepairDecision]) -> Dict[str, float]:
        count = len(items)
        if count == 0:
            return {"calls": 0}
        sum_hits = sum(item.is_sum_optimal for item in items)
        ms_hits = sum(item.is_makespan_optimal for item in items)
        both = sum(item.is_sum_optimal and item.is_makespan_optimal for item in items)
        neither = count - sum_hits - ms_hits + both
        return {
            "calls": count,
            "sum_optimal": sum_hits,
            "makespan_optimal": ms_hits,
            "both_optimal": both,
            "neither_optimal": neither,
            "sum_hit_rate": sum_hits / count,
            "makespan_hit_rate": ms_hits / count,
            "both_hit_rate": both / count,
            "neither_rate": neither / count,
            "mean_sum_regret": sum(item.sum_regret for item in items) / count,
            "max_sum_regret": max(item.sum_regret for item in items),
            "mean_makespan_regret": sum(item.makespan_regret for item in items) / count,
            "max_makespan_regret": max(item.makespan_regret for item in items),
            "mean_sum_regret_ratio": sum(item.sum_regret for item in items)
            / count / max(self.makespan_scale, DECISION_TOLERANCE),
            "mean_makespan_regret_ratio": sum(item.makespan_regret for item in items)
            / count / max(self.makespan_scale, DECISION_TOLERANCE),
        }

    def summary(self, **extra: object) -> Dict[str, object]:
        payload: Dict[str, object] = dict(self._profile(self.decisions))
        payload["scale"] = self.makespan_scale
        payload.update(extra)
        return payload

    def myopic_only(self) -> List[RepairDecision]:
        """Decisions that served the summed cost and ignored the bottleneck."""
        return [item for item in self.decisions
                if item.is_sum_optimal and not item.is_makespan_optimal]

    def balance_aware(self) -> List[RepairDecision]:
        """Decisions that served the makespan while giving up summed cost."""
        return [item for item in self.decisions
                if item.is_makespan_optimal and not item.is_sum_optimal]


def _route_costs(routes: Sequence[Sequence[int]],
                 pricer: RouteIncrementalEvaluator) -> List[float]:
    return [pricer.route_cost(route) for route in routes]


def audit_destroy(
    routes: Sequence[Sequence[int]],
    removed: Iterable[int],
    pricer: RouteIncrementalEvaluator,
    *,
    task_route_index: Optional[Dict[int, Tuple[int, int]]] = None,
) -> DestroyDecision:
    """Score a removal set by the exact cost it releases in its own route.

    ``saving(t) = cost(route) - cost(route without t)`` is the honest value of
    removing ``t`` alone: on this problem it is the only in-route quantity that
    does not depend on where ``t`` is inserted next.  The best possible removal
    set of the same size is the ``k`` tasks with the largest saving, so
    ``precision`` is the fraction of the chosen tasks that were actually in that
    set and ``saving_capture`` is the fraction of the available saving captured.
    """

    removed = tuple(removed)
    if not removed:
        return DestroyDecision((), (), (), (), 0.0, 0.0, 0)

    index = task_route_index or {
        task_id: (route_index, position)
        for route_index, route in enumerate(routes)
        for position, task_id in enumerate(route)
    }
    missing = [task_id for task_id in removed if task_id not in index]
    if missing:
        raise ValueError(f"removed tasks not present in any route: {missing}")

    savings: Dict[int, float] = {}
    for task_id in index:
        route_index, position = index[task_id]
        route = routes[route_index]
        savings[task_id] = pricer.route_cost(route) - pricer.route_cost_without(route, position)

    ordered = sorted(index, key=lambda task_id: (-savings[task_id], task_id))
    top_k = tuple(ordered[: len(removed)])
    chosen = sum(savings[task_id] for task_id in removed)
    best = sum(savings[task_id] for task_id in top_k)
    hits = len(set(removed) & set(top_k))
    return DestroyDecision(
        removed=removed,
        removed_savings=tuple(savings[task_id] for task_id in removed),
        top_k=top_k,
        top_k_savings=tuple(savings[task_id] for task_id in top_k),
        precision=hits / len(removed),
        saving_capture=0.0 if best <= DECISION_TOLERANCE else chosen / best,
        total_tasks=len(index),
    )


def audit_repair(
    partial_routes: Sequence[Sequence[int]],
    partial_costs: Sequence[float],
    removed: Iterable[int],
    repaired_routes: Sequence[Sequence[int]],
    pricer: RouteIncrementalEvaluator,
) -> RepairDecisionAudit:
    """Score every placement against the best single-step placement, both objectives.

    ``price(t, r)`` is the exact increase of ``cost(r)`` when ``t`` is inserted at
    the best position of ``r`` (the position itself is chosen optimally, so this
    measures the *route* decision, not the slot order).  The best route for the
    summed cost ignores the other routes; the best route for the makespan also
    accounts for whether ``r`` is the bottleneck.
    """

    removed = tuple(removed)
    routes = [list(route) for route in partial_routes]
    costs = [float(cost) for cost in partial_costs]
    assigned = {
        task_id: route_index
        for route_index, route in enumerate(repaired_routes)
        for task_id in route
    }
    audit = RepairDecisionAudit(makespan_scale=max(costs) if costs else 1.0)

    for task_id in removed:
        if task_id not in assigned:
            raise ValueError(f"removed task {task_id} is missing from the repaired solution")
        # ``insertion_costs`` returns the *total* cost of the enlarged route, so the
        # decision price is that minus the route's current cost.
        prices = [min(pricer.insertion_costs(route, task_id)) - pricer.route_cost(route)
                  for route in routes]
        projected = [costs[route_index] + prices[route_index]
                     for route_index in range(len(routes))]
        best_sum_route = min(range(len(prices)),
                             key=lambda route_index: (prices[route_index], route_index))
        # Only one route grows, so the resulting makespan is that route's
        # projected cost unless some *untouched* route is already larger.  The
        # untouched routes keep their current cost; adding their own insertion
        # price would pretend the task was placed in every route at once.
        makespans = []
        for route_index in range(len(routes)):
            others = [costs[other] for other in range(len(routes))
                      if other != route_index]
            makespans.append(max(projected[route_index], max(others, default=0.0)))
        best_makespan_route = min(range(len(makespans)),
                                  key=lambda route_index: (makespans[route_index], route_index))
        chosen = assigned[task_id]
        audit.decisions.append(RepairDecision(
            task_id=task_id,
            assigned_route=chosen,
            sum_optimal_route=best_sum_route,
            makespan_optimal_route=best_makespan_route,
            price_assigned=prices[chosen],
            price_best_sum=prices[best_sum_route],
            makespan_assigned=makespans[chosen],
            makespan_best=makespans[best_makespan_route],
        ))
    return audit


class DecisionAuditRecorder:
    """Per-operator accumulator for the two audits.

    Designed to be attached to a running solver: ``record_destroy`` and
    ``record_repair`` are called once per iteration and only read the pricer.
    Leaving it out must not change any decision -- it holds no reference to the
    solver and returns nothing that the search consumes.
    """

    def __init__(self) -> None:
        self.destroy: Dict[str, List[Dict[str, object]]] = {}
        self.repair: Dict[str, List[Dict[str, object]]] = {}

    def record_destroy(self, operator: str, audit: DestroyDecision) -> None:
        self.destroy.setdefault(operator, []).append(dict(
            tasks=len(audit.removed),
            precision=audit.precision,
            saving_capture=audit.saving_capture,
            total_tasks=audit.total_tasks,
            random_level=audit.is_random_level,
        ))

    def record_repair(self, operator: str, audit: RepairDecisionAudit) -> None:
        self.repair.setdefault(operator, []).append(audit.summary())

    @staticmethod
    def _aggregate(rows: List[Dict[str, object]]) -> Dict[str, object]:
        if not rows:
            return {"calls": 0}

        def mean_of(key: str) -> Optional[float]:
            values = [float(row[key]) for row in rows if row.get(key) is not None]
            return None if not values else sum(values) / len(values)

        keys = sorted({key for row in rows for key in row})
        aggregate: Dict[str, object] = {"calls": len(rows)}
        for key in keys:
            if key in {"calls", "total_tasks", "tasks", "scale"}:
                continue
            mean = mean_of(key)
            if mean is not None:
                aggregate[f"mean_{key}"] = mean
                aggregate[f"max_{key}"] = max(float(row[key]) for row in rows
                                              if row.get(key) is not None)
        return aggregate

    def summary(self) -> Dict[str, object]:
        return {
            "destroy": {name: self._aggregate(rows) for name, rows in self.destroy.items()},
            "repair": {name: self._aggregate(rows) for name, rows in self.repair.items()},
            "destroy_calls": sum(len(rows) for rows in self.destroy.values()),
            "repair_calls": sum(len(rows) for rows in self.repair.values()),
        }
