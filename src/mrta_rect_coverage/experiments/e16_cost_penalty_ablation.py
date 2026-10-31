"""E16: fixed-wall-clock A/B of the iteration-cost penalty (S vs S+cost).

This is a *scoping check*, not a confirmatory experiment: it decides whether the
P1 mechanism (`ALNSConfig.iteration_cost_penalty`) earns its place before P2 is
built on top of it.

Design
------
* Two arms, identical except for ``iteration_cost_penalty``:
  ``off`` ... B1 preset (``score_effective == score_raw``)
  ``on``  ... same preset with a calibrated ``iteration_cost_reference_seconds``
* Termination is a **fixed wall-clock budget** (``--budget-seconds``); a fixed
  iteration count would make the penalty meaningless by construction.
* Pairing: every (instance, seed) is run once per arm, and the arm order is
  alternated so machine drift does not favour one arm.

Pre-registered decision rule (fixed before looking at any number)
-----------------------------------------------------------------
Let ``delta_rel = (makespan_on - makespan_off) / makespan_off`` over pairs.

* ``KEEP``          : median delta_rel < 0 and bootstrap 95% CI upper bound < 0
* ``KEEP_WEAK``     : median delta_rel < 0 but the CI contains 0
* ``TURN_OFF``      : |median delta_rel| < 0.005 and the CI contains 0
* ``TURN_OFF_HURT`` : CI excludes 0 with median delta_rel > 0
* ``INCONCLUSIVE``  : otherwise

Usage:
    python -m mrta_rect_coverage.experiments.e16_cost_penalty_ablation --stage run
    python -m mrta_rect_coverage.experiments.e16_cost_penalty_ablation --stage analyze
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import statistics
import subprocess
import sys
from time import perf_counter

from ..core.instance_loader import load_instance
from ..heuristics.alns_solver import ALNSConfig, ALNSSolver

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = ROOT / "outputs/e16_cost_penalty_ablation"
STRUCTURAL_DATA = ROOT / "data/e10_structural_development"
CALIBRATION = ROOT / "outputs/e15_cost_penalty_calibration/calibration.json"

DEFAULT_INSTANCES = (
    "BASE:0",
    "BOTTLENECK:0",
    "HV-GEOM:0",
    "SPATIAL:0",
    "SWEEP-NARROW:0",
    "TRAVEL-HIGH:0",
    "TURN-HIGH:0",
    "BASE:1",
)
DEFAULT_SEEDS = (0, 1, 2)
DEFAULT_BUDGET_SECONDS = 3.0
BOOTSTRAP_RESAMPLES = 5000
BOOTSTRAP_SEED = 20261030
# Pre-registered thresholds; do not tune after seeing results.
NEUTRAL_MEDIAN_THRESHOLD = 0.005


def _git_head() -> str:
    for executable in ("git", r"C:\Program Files\Git\cmd\git.exe"):
        try:
            return subprocess.run(
                [executable, "rev-parse", "HEAD"], cwd=ROOT, check=True,
                capture_output=True, text=True
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            continue
    return "unavailable"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def read_reference_seconds() -> float:
    record = json.loads(CALIBRATION.read_text(encoding="utf-8"))
    reference = record["t_ref_seconds"]
    if not (reference > 0):
        raise SystemExit("calibration.json has a non-positive t_ref_seconds")
    return reference


def _instance_path(instance_id: str) -> Path:
    """``FAMILY:repeat`` -> ``data/e10_structural_development/FAMILY/R4_T40_<repeat>.txt``."""
    family, _, repeat = instance_id.partition(":")
    if not repeat:
        raise SystemExit(f"instance id must look like 'FAMILY:repeat', got {instance_id!r}")
    return STRUCTURAL_DATA / family / f"R4_T40_{repeat}.txt"


def _time_to_best(history: list[dict], best_makespan: float) -> float | None:
    for row in reversed(history):
        if row["best_makespan"] == best_makespan:
            return row["elapsed_seconds"]
    return None


def run_one(
    instance_id: str, seed: int, arm: str, *, budget_seconds: float,
    reference: float | None,
) -> dict:
    instance = load_instance(_instance_path(instance_id))
    config = ALNSConfig.enhanced(
        iterations=None,
        max_runtime_seconds=budget_seconds,
        random_seed=seed,
        iteration_cost_penalty=(arm == "on"),
        iteration_cost_reference_seconds=reference if arm == "on" else None,
    )
    started = perf_counter()
    result = ALNSSolver(instance, config=config).solve()
    wall = perf_counter() - started
    makespan = result.best_evaluation.makespan
    factors = [
        row["cost_penalty_factor"] for row in result.iteration_history
        if "cost_penalty_factor" in row
    ]
    damped = [factor for factor in factors if factor < 1.0]
    fallback_count = len(result.fallback_events)
    return {
        "instance_id": instance_id,
        "seed": seed,
        "arm": arm,
        "makespan": makespan,
        "initial_makespan": result.initial_makespan,
        "relative_improvement": (
            (result.initial_makespan - makespan) / result.initial_makespan
            if result.initial_makespan else 0.0
        ),
        "iterations_completed": result.iterations_completed,
        "runtime_seconds": result.runtime_seconds,
        "wall_seconds": wall,
        "termination_reason": result.termination_reason,
        "time_to_best_seconds": _time_to_best(result.iteration_history, makespan),
        "route_dp_calls": result.route_dp_calls,
        "fallback_count": fallback_count,
        "damped_iteration_fraction": (
            len(damped) / len(factors) if factors else 0.0
        ),
        "median_cost_penalty_factor": (
            statistics.median(factors) if factors else None
        ),
    }


def stage_run(
    output: Path, *, instances: tuple[str, ...], seeds: tuple[int, ...],
    budget_seconds: float, reference: float | None,
) -> dict:
    # Warm-up: pay import/JIT/cache costs outside the measured pairs.
    run_one(instances[0], seeds[0], "off", budget_seconds=budget_seconds,
            reference=None)

    rows: list[dict] = []
    order_log: list[dict] = []
    for index, instance_id in enumerate(instances):
        for seed in seeds:
            # Alternate which arm goes first to balance machine drift.
            arms = ("off", "on") if (index + seed) % 2 == 0 else ("on", "off")
            order_log.append(
                {"instance_id": instance_id, "seed": seed, "arm_order": list(arms)}
            )
            for arm in arms:
                rows.append(
                    run_one(instance_id, seed, arm,
                            budget_seconds=budget_seconds, reference=reference)
                )
            print(
                f"[{instance_id} seed={seed}] "
                + " / ".join(
                    f"{row['arm']}={row['makespan']:.1f}"
                    f"({row['iterations_completed']} it)"
                    for row in rows[-2:]
                ),
                flush=True,
            )

    record = {
        "created_at_utc": _utc_now(),
        "git_head": _git_head(),
        "python": sys.version.split()[0],
        "budget_seconds": budget_seconds,
        "reference_seconds": reference,
        "instances": list(instances),
        "seeds": list(seeds),
        "arms": ["off", "on"],
        "run_order": order_log,
        "rows": rows,
    }
    _write_json(output / "runs.json", record)
    return record


def _bootstrap_median_ci(values: list[float], *, seed: int = BOOTSTRAP_SEED,
                         resamples: int = BOOTSTRAP_RESAMPLES) -> tuple[float, float]:
    rng = random.Random(seed)
    n = len(values)
    medians = []
    for _ in range(resamples):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        medians.append(statistics.median(sample))
    medians.sort()
    low = medians[int(0.025 * resamples)]
    high = medians[int(0.975 * resamples) - 1]
    return low, high


def _verdict(differences: list[float]) -> dict:
    median = statistics.median(differences)
    low, high = _bootstrap_median_ci(differences)
    better = sum(1 for value in differences if value < 0)
    worse = sum(1 for value in differences if value > 0)
    ties = len(differences) - better - worse
    if low > 0:
        decision = "TURN_OFF_HURT"
    elif high < 0:
        decision = "KEEP"
    elif abs(median) < NEUTRAL_MEDIAN_THRESHOLD:
        decision = "TURN_OFF"
    elif median < 0:
        decision = "KEEP_WEAK"
    else:
        decision = "INCONCLUSIVE"
    return {
        "pair_count": len(differences),
        "median": median,
        "mean": statistics.mean(differences),
        "ci_low": low,
        "ci_high": high,
        "on_better": better,
        "on_worse": worse,
        "ties": ties,
        "decision": decision,
    }


def stage_analyze(output: Path) -> dict:
    record = json.loads((output / "runs.json").read_text(encoding="utf-8"))
    by_key: dict[tuple[str, int], dict[str, dict]] = {}
    for row in record["rows"]:
        by_key.setdefault((row["instance_id"], row["seed"]), {})[row["arm"]] = row

    pairs: list[dict] = []
    for (instance_id, seed), arms in sorted(by_key.items()):
        if "off" not in arms or "on" not in arms:
            continue
        off, on = arms["off"], arms["on"]
        pairs.append({
            "instance_id": instance_id,
            "seed": seed,
            "off_makespan": off["makespan"],
            "on_makespan": on["makespan"],
            "delta_abs": on["makespan"] - off["makespan"],
            "delta_rel": (on["makespan"] - off["makespan"]) / off["makespan"],
            "off_iterations": off["iterations_completed"],
            "on_iterations": on["iterations_completed"],
            "off_runtime_seconds": off["runtime_seconds"],
            "on_runtime_seconds": on["runtime_seconds"],
            "on_damped_iteration_fraction": on["damped_iteration_fraction"],
            "on_median_cost_penalty_factor": on["median_cost_penalty_factor"],
        })

    makespan_verdict = _verdict([pair["delta_rel"] for pair in pairs])
    iterations_verdict = _verdict(
        [(pair["on_iterations"] - pair["off_iterations"]) / pair["off_iterations"]
         for pair in pairs]
    )

    summary = {
        "created_at_utc": _utc_now(),
        "git_head": record["git_head"],
        "budget_seconds": record["budget_seconds"],
        "reference_seconds": record["reference_seconds"],
        "instance_count": len(record["instances"]),
        "seed_count": len(record["seeds"]),
        "pair_count": len(pairs),
        "making_span_verdict": makespan_verdict,
        "iterations_verdict": iterations_verdict,
        "median_iterations_off": statistics.median(
            [pair["off_iterations"] for pair in pairs]
        ) if pairs else None,
        "median_iterations_on": statistics.median(
            [pair["on_iterations"] for pair in pairs]
        ) if pairs else None,
        "median_damped_fraction_on": statistics.median(
            [pair["on_damped_iteration_fraction"] for pair in pairs]
        ) if pairs else None,
        "pre_registered_rule": {
            "neutral_median_threshold": NEUTRAL_MEDIAN_THRESHOLD,
            "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
            "bootstrap_seed": BOOTSTRAP_SEED,
            "KEEP": "median delta_rel < 0 and CI upper < 0",
            "KEEP_WEAK": "median delta_rel < 0, CI contains 0",
            "TURN_OFF": "|median| < 0.005 and CI contains 0",
            "TURN_OFF_HURT": "CI lower > 0",
            "INCONCLUSIVE": "otherwise",
        },
        "caveat": (
            "Scoping check only: wall-clock budgets vary with machine load, and "
            "this run is not a confirmatory test of any hypothesis."
        ),
    }
    _write_json(output / "pairs.json", pairs)
    _write_json(output / "summary.json", summary)
    (output / "REPORT.md").write_text(_report(summary, pairs), encoding="utf-8")
    print(json.dumps(summary["making_span_verdict"], indent=2, sort_keys=True))
    print("decision:", summary["making_span_verdict"]["decision"])
    return summary


def _report(summary: dict, pairs: list[dict]) -> str:
    verdict = summary["making_span_verdict"]
    lines = [
        "# E16 成本惩罚固定墙钟对照（S vs S+cost）",
        "",
        f"- 生成时间：{summary['created_at_utc']}（git HEAD `{summary['git_head']}`）",
        f"- 预算：每条运行 **{summary['budget_seconds']} s** 固定墙钟；"
        f"参考耗时 `t_ref = {summary['reference_seconds']:.3e} s`（e15 标定）",
        f"- 规模：{summary['instance_count']} 实例 × {summary['seed_count']} seed × 2 臂"
        f" = {summary['pair_count']} 配对",
        f"- 典型迭代数（中位）：off `{summary['median_iterations_off']}` / "
        f"on `{summary['median_iterations_on']}`",
        f"- 开启臂被折价迭代占比（中位）：`{summary['median_damped_fraction_on']}`",
        "",
        "## 判定",
        "",
        f"**{verdict['decision']}**",
        "",
        "| 指标 | 值 |",
        "| --- | --- |",
        f"| 配对 delta_rel 中位数 | `{verdict['median']:+.5f}` |",
        f"| 均值 | `{verdict['mean']:+.5f}` |",
        f"| bootstrap 95% CI | `[{verdict['ci_low']:+.5f}, {verdict['ci_high']:+.5f}]` |",
        f"| on 更好 / 更差 / 持平 | {verdict['on_better']} / {verdict['on_worse']} / {verdict['ties']} |",
        "",
        "> 预注册规则（看数字之前写死）：",
        "> KEEP = 中位数 < 0 且 CI 上界 < 0；KEEP_WEAK = 中位数 < 0 但 CI 含 0；",
        "> TURN_OFF = |中位数| < 0.005 且 CI 含 0；TURN_OFF_HURT = CI 下界 > 0。",
        "",
        "## 逐配对明细",
        "",
        "| 实例 | seed | off | on | delta_rel | off 迭代 | on 迭代 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for pair in pairs:
        lines.append(
            f"| {pair['instance_id']} | {pair['seed']} | "
            f"{pair['off_makespan']:.1f} | {pair['on_makespan']:.1f} | "
            f"`{pair['delta_rel']:+.5f}` | {pair['off_iterations']} | "
            f"{pair['on_iterations']} |"
        )
    lines += [
        "",
        "## 局限",
        "",
        "- 这是范围检查，不是确认性检验；固定墙钟预算随机器负载漂移。",
        "- 臂顺序按 (实例序号 + seed) 奇偶交替，只做漂移平衡，不做配对随机化。",
        "- 结论只用于决定 P1 开关是否进入 P2/P3，不作为任何假设的证据。",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("run", "analyze"), required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--budget-seconds", type=float, default=DEFAULT_BUDGET_SECONDS)
    parser.add_argument("--instances", nargs="+", default=list(DEFAULT_INSTANCES))
    parser.add_argument("--seeds", nargs="+", type=int, default=list(DEFAULT_SEEDS))
    args = parser.parse_args()
    output = args.output.resolve()
    if args.stage == "run":
        reference = read_reference_seconds()
        stage_run(output, instances=tuple(args.instances), seeds=tuple(args.seeds),
                  budget_seconds=args.budget_seconds, reference=reference)
    else:
        stage_analyze(output)


if __name__ == "__main__":
    main()
