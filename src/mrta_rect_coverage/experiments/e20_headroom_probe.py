"""Headroom probe: how much makespan is left for an exact bottleneck descent?

Before any change to the solver, this asks the only question that decides whether
the bottleneck lever is real: take solutions that were already recorded by the
existing methods, apply an *exact* redesign of the binding constraint (relocate a
task off the critical robot / swap two tasks between robots, each candidate route
priced by a full Route-DP over its 8 states), and measure how far the makespan
falls.

If nothing falls, the lever is empty and the design premise dies. If a lot falls,
then every recorded method -- ours included -- was leaving that room on the table.

Nothing is solved from scratch here: this is a deterministic post-processing pass
over saved routes, so the result is a property of the saved solutions, not of any
new search.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from statistics import mean, median
import subprocess
from time import perf_counter
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .e3_alns import ROOT, write_json
from .e5_destroy_repair import read
from .e11_structural_benchmark import byte_hash, catalog, load_entry
from ..core.cost_matrix import CostMatrix
from ..core.dp_evaluator import RouteDPEvaluator
from ..core.state_generator import generate_all_states

E12_RUNS = ROOT / "outputs/e12_literature_baselines/runs"
E19_RUNS = ROOT / "outputs/e19_deployment_freezes/runs"
DEFAULT_OUTPUT = ROOT / "outputs/e20_headroom_probe"
METHODS = ("B1", "CDABC", "RNSGA", "SGA-TS", "MRHDABC", "Proposed")
SEEDS = (0, 1)
TOL = 1e-9


def _git_head() -> str:
    for command in (["git"], [r"C:\Program Files\Git\cmd\git.exe"]):
        try:
            out = subprocess.check_output(
                command + ["rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip()
        except (OSError, subprocess.CalledProcessError):
            continue
        if out:
            return out
    return "unavailable"


def evaluator_for(instance) -> RouteDPEvaluator:
    states = generate_all_states(instance)
    matrix = CostMatrix(
        instance.depot, states, travel_speed=instance.travel_speed
    )
    return RouteDPEvaluator(matrix, states)


class RoutePricer:
    """Exact route cost with a tiny memo keyed by the route tuple."""

    def __init__(self, evaluator: RouteDPEvaluator):
        self.evaluator = evaluator
        self.calls = 0
        self.memo: Dict[Tuple[int, ...], float] = {}

    def cost(self, route: Sequence[int]) -> float:
        key = tuple(route)
        cached = self.memo.get(key)
        if cached is not None:
            return cached
        self.calls += 1
        value = 0.0 if not key else self.evaluator.evaluate_route(list(key)).total_cost
        self.memo[key] = value
        return value


def _objective(costs: Sequence[float]) -> Tuple[float, float]:
    return max(costs), float(sum(costs))


def _better(candidate: Tuple[float, float], incumbent: Tuple[float, float]) -> bool:
    if candidate[0] < incumbent[0] - TOL:
        return True
    return abs(candidate[0] - incumbent[0]) <= TOL and candidate[1] < incumbent[1] - TOL


def descend(
    routes: List[List[int]],
    pricer: RoutePricer,
    *,
    max_passes: int = 12,
    max_pricings: int = 2_000_000,
    max_seconds: float = 300.0,
) -> Dict[str, Any]:
    """Exact best-improvement descent on relocate + pairwise swap of the critical route.

    Every candidate route is priced by the full 8-state Route-DP, so an accepted
    move is an exact improvement of the true makespan, not of a proxy.
    """
    routes = [list(route) for route in routes]
    costs = [pricer.cost(route) for route in routes]
    start_max, start_sum = _objective(costs)
    passes = 0
    applied = {"relocate": 0, "swap": 0}
    exhausted = False
    started = perf_counter()
    while passes < max_passes:
        if perf_counter() - started > max_seconds or pricer.calls > max_pricings:
            exhausted = True
            break
        passes += 1
        incumbent = (max(costs), sum(costs))
        best: Optional[Tuple[Tuple[float, float], str, Any]] = None
        critical = max(range(len(routes)), key=lambda index: costs[index])
        crit_route = routes[critical]
        # M1: relocate one task off the critical route.
        for position, task in enumerate(crit_route):
            reduced = crit_route[:position] + crit_route[position + 1 :]
            reduced_cost = pricer.cost(reduced)
            for target, route in enumerate(routes):
                if target == critical:
                    continue
                for insertion in range(len(route) + 1):
                    grown = route[:insertion] + [task] + route[insertion:]
                    grown_cost = pricer.cost(grown)
                    trial = list(costs)
                    trial[critical] = reduced_cost
                    trial[target] = grown_cost
                    score = _objective(trial)
                    if _better(score, incumbent) and (best is None or _better(score, best[0])):
                        best = (score, "relocate", (critical, reduced, target, grown))
                if perf_counter() - started > max_seconds or pricer.calls > max_pricings:
                    break
            if perf_counter() - started > max_seconds or pricer.calls > max_pricings:
                break
        # M2: swap one task between the critical route and another route.
        if not exhausted and best is None:
            for position, task in enumerate(crit_route):
                crit_base = crit_route[:position] + crit_route[position + 1 :]
                for target, route in enumerate(routes):
                    if target == critical:
                        continue
                    for other_position, other_task in enumerate(route):
                        new_crit = list(crit_base)
                        new_target = route[:other_position] + route[other_position + 1 :]
                        crit_options = [
                            new_crit[:p] + [other_task] + new_crit[p:]
                            for p in range(len(new_crit) + 1)
                        ]
                        target_options = [
                            new_target[:q] + [task] + new_target[q:]
                            for q in range(len(new_target) + 1)
                        ]
                        best_crit_route = min(crit_options, key=pricer.cost)
                        best_crit = pricer.cost(best_crit_route)
                        best_target_route = min(target_options, key=pricer.cost)
                        best_target = pricer.cost(best_target_route)
                        trial = list(costs)
                        trial[critical] = best_crit
                        trial[target] = best_target
                        score = _objective(trial)
                        if _better(score, incumbent) and (best is None or _better(score, best[0])):
                            best = (
                                score,
                                "swap",
                                (critical, best_crit_route, target, best_target_route),
                            )
                    if perf_counter() - started > max_seconds or pricer.calls > max_pricings:
                        break
                if perf_counter() - started > max_seconds or pricer.calls > max_pricings:
                    break
        if best is None:
            break
        _, kind, (critical_index, new_critical, target_index, new_target) = best
        routes[critical_index] = new_critical
        routes[target_index] = new_target
        costs[critical_index] = pricer.cost(new_critical)
        costs[target_index] = pricer.cost(new_target)
        applied[kind] += 1
    else:
        exhausted = True
    final_max, final_sum = _objective(costs)
    return dict(
        routes=routes,
        costs=costs,
        start_makespan=start_max,
        final_makespan=final_max,
        start_sum=start_sum,
        final_sum=final_sum,
        passes=passes,
        applied=applied,
        route_dp_calls=pricer.calls,
        time_limited=exhausted,
    )


def _instance_ids() -> Dict[str, Dict[str, Any]]:
    return {entry["instance_id"]: entry for entry in catalog()["entries"]}


def collect_records() -> List[Dict[str, Any]]:
    index = _instance_ids()
    records: List[Dict[str, Any]] = []
    for instance_id, entry in index.items():
        for seed in SEEDS:
            for method in METHODS:
                path = E12_RUNS / instance_id / f"{method}_s{seed}.json"
                if not path.exists():
                    continue
                record = read(path)
                records.append(
                    dict(
                        source="e12",
                        instance_id=instance_id,
                        entry=entry,
                        seed=seed,
                        method=method,
                        routes=[list(route) for route in record["best_routes"]],
                        recorded_makespan=float(record["result"]["makespan"]),
                    )
                )
    for arm in ("E11", "E18"):
        arm_root = E19_RUNS / arm
        if not arm_root.exists():
            continue
        for path in sorted(arm_root.rglob("Proposed_s*.json")):
            parts = path.relative_to(arm_root).parts
            if len(parts) != 4:
                continue
            split, scenario, instance_name, _ = parts
            instance_id = f"{split}/{scenario}/{instance_name}"
            entry = index.get(instance_id)
            if entry is None:
                continue
            seed = int(path.stem.split("_s", 1)[1])
            record = read(path)
            records.append(
                dict(
                    source="e19",
                    instance_id=instance_id,
                    entry=entry,
                    seed=seed,
                    method=f"Proposed-{arm}",
                    routes=[list(route) for route in record["best_routes"]],
                    recorded_makespan=float(record["result"]["makespan"]),
                )
            )
    records.sort(key=lambda item: (item["instance_id"], item["method"], item["seed"]))
    return records


def stage_probe(
    output: Path = DEFAULT_OUTPUT,
    *,
    max_passes: int = 12,
    max_seconds: float = 300.0,
    limit: Optional[int] = None,
    instance_filter: str = "",
) -> Dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    records = collect_records()
    if instance_filter:
        records = [r for r in records if instance_filter in r["instance_id"]]
    if limit:
        records = records[:limit]
    if not records:
        raise SystemExit("no recorded solutions found; run e12/e19 first")
    rows: List[Dict[str, Any]] = []
    started = perf_counter()
    for record in records:
        instance = load_entry(record["entry"])
        pricer = RoutePricer(evaluator_for(instance))
        result = descend(
            record["routes"], pricer, max_passes=max_passes, max_seconds=max_seconds
        )
        consistency = abs(result["start_makespan"] - record["recorded_makespan"])
        drop = 100.0 * (1.0 - result["final_makespan"] / result["start_makespan"])
        rows.append(
            dict(
                source=record["source"],
                instance_id=record["instance_id"],
                scenario=record["entry"]["scenario"],
                tasks=instance.task_count,
                robots=instance.robot_count,
                seed=record["seed"],
                method=record["method"],
                recorded_makespan=record["recorded_makespan"],
                start_makespan=result["start_makespan"],
                final_makespan=result["final_makespan"],
                drop_pct=drop,
                passes=result["passes"],
                applied=result["applied"],
                route_dp_calls=result["route_dp_calls"],
                time_limited=result["time_limited"],
                makespan_match=consistency <= 1e-6,
                routes_after=result["routes"],
            )
        )
        print(
            f"{record['method']:<16} {record['instance_id'].split('/', 1)[-1]:<26} s{record['seed']} "
            f"{result['start_makespan']:9.2f} -> {result['final_makespan']:9.2f} ({drop:+.3f}%) "
            f"{result['applied']['relocate']}r/{result['applied']['swap']}s "
            f"{result['route_dp_calls']}dp",
            flush=True,
        )
    elapsed = perf_counter() - started
    summary: Dict[str, Any] = dict(records=len(rows), elapsed_seconds=elapsed)
    by_method: Dict[str, Dict[str, Any]] = {}
    for method in sorted({row["method"] for row in rows}):
        subset = [row for row in rows if row["method"] == method]
        drops = [row["drop_pct"] for row in subset]
        by_method[method] = dict(
            records=len(subset),
            mean_drop_pct=mean(drops),
            median_drop_pct=median(drops),
            min_drop_pct=min(drops),
            max_drop_pct=max(drops),
            improved=sum(1 for value in drops if value > 0.01),
            mean_moves=mean(row["applied"]["relocate"] + row["applied"]["swap"] for row in subset),
            time_limited=sum(1 for row in subset if row["time_limited"]),
        )
    summary["by_method"] = by_method
    all_drops = [row["drop_pct"] for row in rows]
    summary["overall"] = dict(
        mean_drop_pct=mean(all_drops),
        median_drop_pct=median(all_drops),
        improved_fraction=sum(1 for value in all_drops if value > 0.01) / len(all_drops),
        makespan_mismatch=sum(1 for row in rows if not row["makespan_match"]),
    )
    by_tasks: Dict[str, Dict[str, float]] = {}
    for bucket in sorted({row["tasks"] for row in rows}):
        subset = [row["drop_pct"] for row in rows if row["tasks"] == bucket]
        by_tasks[str(bucket)] = dict(
            records=len(subset), mean_drop_pct=mean(subset), median_drop_pct=median(subset)
        )
    summary["by_tasks"] = by_tasks
    summary["config"] = dict(
        git_head=_git_head(),
        created_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        max_passes=max_passes,
        neighborhood="exact relocate off the critical route + exact pairwise cross-route swap; "
        "each candidate route priced by the full 8-state Route-DP",
        instances=len({row["instance_id"] for row in rows}),
        e19_proposed_sha256=byte_hash(E19_RUNS / "E18" / "experiment_config.json")
        if (E19_RUNS / "E18" / "experiment_config.json").exists()
        else "absent",
        note="deterministic post-processing of saved solutions; no search from scratch",
    )
    write_json(output / "headroom.json", dict(rows=rows, summary=summary))
    (output / "REPORT.md").write_text(render(summary, rows), encoding="utf-8")
    return summary


def render(summary: Dict[str, Any], rows: Sequence[Dict[str, Any]]) -> str:
    lines = ["# E20 headroom probe — exact bottleneck descent on recorded solutions", ""]
    lines += [
        f"- git head: `{summary['config']['git_head']}`",
        f"- records: {summary['records']} over {summary['config']['instances']} instances · "
        f"elapsed: {summary['elapsed_seconds']:.1f} s",
        "- neighborhood: exact relocate off the critical robot + exact pairwise cross-route swap,",
        "  every candidate route priced by the full 8-state Route-DP",
        "",
        "## By method",
        "",
        "| Method | n | mean drop | median drop | min | max | improved | mean moves | capped |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for method, stats in summary["by_method"].items():
        lines.append(
            f"| {method} | {stats['records']} | {stats['mean_drop_pct']:+.3f}% | "
            f"{stats['median_drop_pct']:+.3f}% | {stats['min_drop_pct']:+.3f}% | "
            f"{stats['max_drop_pct']:+.3f}% | {stats['improved']}/{stats['records']} | "
            f"{stats['mean_moves']:.1f} | {stats['time_limited']} |"
        )
    overall = summary["overall"]
    lines += [
        "",
        f"Overall: mean {overall['mean_drop_pct']:+.3f}%, median {overall['median_drop_pct']:+.3f}%, "
        f"improved {overall['improved_fraction']:.0%} of records, "
        f"makespan mismatches {overall['makespan_mismatch']}.",
        "",
        "## By task count",
        "",
        "| tasks | n | mean drop | median drop |",
        "| ---: | ---: | ---: | ---: |",
    ]
    for bucket, stats in summary["by_tasks"].items():
        lines.append(
            f"| {bucket} | {stats['records']} | {stats['mean_drop_pct']:+.3f}% | "
            f"{stats['median_drop_pct']:+.3f}% |"
        )
    lines += [
        "",
        "## Per record",
        "",
        "| Method | Instance | seed | recorded | after descent | drop | moves |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        moves = row["applied"]
        lines.append(
            f"| {row['method']} | {row['instance_id'].split('/', 1)[-1]} | {row['seed']} | "
            f"{row['start_makespan']:.2f} | {row['final_makespan']:.2f} | {row['drop_pct']:+.3f}% | "
            f"{moves['relocate']}r/{moves['swap']}s |"
        )
    lines += [
        "",
        "Reading: a positive drop means the recorded solution had room that an exact "
        "bottleneck move could take. This is a property of the saved solutions, not of a rerun.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("probe",), required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-passes", type=int, default=12)
    parser.add_argument("--max-seconds", type=float, default=300.0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--instance-filter", default="")
    args = parser.parse_args()
    summary = stage_probe(
        args.output,
        max_passes=args.max_passes,
        max_seconds=args.max_seconds,
        limit=args.limit,
        instance_filter=args.instance_filter,
    )
    print(
        json.dumps(
            {
                key: summary[key]
                for key in ("records", "overall", "by_tasks", "elapsed_seconds")
            },
            indent=1,
        )
    )


if __name__ == "__main__":
    main()
