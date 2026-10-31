"""Deployment replay of the Proposed arm under two frozen operator sets.

Arm ``E11`` is the operator identity frozen by E11 (Destroy from E5, Repair from
E7). Arm ``E18`` is the E17 F2_dataset evidence-driven identity packaged by
``e18_freeze_dp_evidence``. Everything else is held fixed: same four development
instances, same seeds, same ``task_count``-second budget, same constructor, pools,
parameters and RNG seeding, alternating arm order to spread machine drift.

The five literature baselines are *not* re-run here. Their recorded makespans are
read from ``outputs/e12_literature_baselines/runs`` so that each arm is compared
against one immutable baseline table. This keeps the comparison honest about what
changes (the two generated operators) and what does not (the baselines).
"""

from __future__ import annotations

import argparse
from importlib import import_module
import json
from pathlib import Path
from statistics import mean
import subprocess
from time import perf_counter
from typing import Any, Dict, List, Sequence, Tuple

from .e3_alns import ROOT, write_json
from .e5_destroy_repair import digest, read
from .e8_repair_portfolio import portfolio_solver
from .e10b_structural_dp_analysis import evaluator_for
from .e11_structural_benchmark import load_entry
from ..core.models import MultiRobotSolution

E12_RUNS = ROOT / "outputs/e12_literature_baselines/runs"
E11_FREEZE = ROOT / "outputs/e11_structural_benchmark/algorithm_freeze.json"
E18_FREEZE = ROOT / "outputs/e18_freeze_dp_evidence/algorithm_freeze.json"
DEFAULT_OUTPUT = ROOT / "outputs/e19_deployment_freezes"
ARMS = ("E11", "E18")
BASELINES = ("B1", "CDABC", "RNSGA", "SGA-TS", "MRHDABC")
SAMPLES = (
    "development/BASE/R2_T10_0",
    "development/HV-GEOM/R2_T20_0",
    "development/BOTTLENECK/R4_T40_0",
    "development/TRAVEL-HIGH/R8_T80_0",
)
SEEDS = (0, 1)
IDENTITY_FIELDS = ("source_path", "source_hash", "operator_id", "generation")


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


def _catalog_index() -> Dict[str, Dict[str, Any]]:
    from .e11_structural_benchmark import catalog

    return {entry["instance_id"]: entry for entry in catalog()["entries"]}


def entries() -> List[Dict[str, Any]]:
    index = _catalog_index()
    rows = [index[name] for name in SAMPLES]
    if any(row["split"] != "development" for row in rows):
        raise SystemExit("development instances only")
    return rows


def freeze_identities(arm: str) -> Dict[str, Dict[str, Any]]:
    path = E11_FREEZE if arm == "E11" else E18_FREEZE
    freeze = read(path)
    if freeze.get("recommended_proposed") != "AUX":
        raise SystemExit(f"{path} is not an AUX freeze")
    identities = {key: dict(freeze["operators"][key]) for key in ("destroy", "main", "aux")}
    for key, entry in identities.items():
        for field in IDENTITY_FIELDS:
            if field not in entry:
                raise SystemExit(f"{arm} operators.{key} missing {field}")
        source = Path(entry["source_path"])
        if not source.is_absolute():
            source = ROOT / source
        if digest(source) != entry["source_hash"]:
            raise SystemExit(f"{arm} operators.{key} source hash mismatch")
        entry["source_path"] = str(source)
    return identities


def proposed_solver(instance, seed: int, identities: Dict[str, Dict[str, Any]]):
    selected = dict(destroy=identities["destroy"], repair=identities["main"])
    return portfolio_solver(instance, seed, selected, identities["aux"], "AUX")


def solve_proposed(entry, seed: int, identities: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    instance = load_entry(entry)
    budget = float(instance.task_count)
    started = perf_counter()
    solver = proposed_solver(instance, seed, identities)
    setup_seconds = perf_counter() - started
    if setup_seconds >= budget:
        raise TimeoutError("initialization exhausted total budget")
    solver.config.max_runtime_seconds = budget - setup_seconds
    result = solver.solve()
    total = perf_counter() - started
    verification = evaluator_for(instance).evaluate(MultiRobotSolution(result.best_solution.routes))
    if abs(verification.makespan - result.best_evaluation.makespan) > 1e-8:
        raise ValueError("independent verification mismatch")
    return dict(
        instance_id=entry["instance_id"],
        scenario=entry["scenario"],
        tasks=instance.task_count,
        robots=instance.robot_count,
        seed=seed,
        method="Proposed",
        makespan=result.best_evaluation.makespan,
        initial_makespan=result.initial_makespan,
        runtime_seconds=total,
        initialization_seconds=setup_seconds,
        iterations=result.iterations_completed,
        route_dp_calls=result.route_dp_calls,
        fallback_count=len(result.fallback_events),
        budget_seconds=budget,
        budget_overrun_seconds=max(0.0, total - budget),
        pools=dict(destroy=list(solver.destroy_ops), repair=list(solver.repair_ops)),
        best_routes=result.best_solution.routes,
    )


def baseline_makespans() -> Dict[Tuple[str, int, str], float]:
    table: Dict[Tuple[str, int, str], float] = {}
    for entry in entries():
        instance_id = entry["instance_id"]
        for seed in SEEDS:
            for method in BASELINES:
                path = E12_RUNS / instance_id / f"{method}_s{seed}.json"
                if not path.exists():
                    raise SystemExit(f"E12 baseline record missing: {path}")
                table[(instance_id, seed, method)] = float(read(path)["result"]["makespan"])
    return table


def stage_run(
    output: Path = DEFAULT_OUTPUT,
    *,
    instances: Path | None = None,
    seeds: Sequence[int] = SEEDS,
    arms: Sequence[str] = ARMS,
) -> Dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    rows: List[Dict[str, Any]] = []
    identities = {arm: freeze_identities(arm) for arm in arms}
    selected = entries()
    if instances is not None:
        names = json.loads(Path(instances).read_text(encoding="utf-8-sig"))
        index = _catalog_index()
        selected = [index[name] for name in names]
    for position, entry in enumerate(selected):
        for seed in seeds:
            order = list(arms)
            if (position + int(seed)) % 2:
                order.reverse()
            for arm in order:
                row = solve_proposed(entry, int(seed), identities[arm])
                row["arm"] = arm
                record = dict(result={k: v for k, v in row.items() if k != "best_routes"},
                              entry=entry, best_routes=row["best_routes"])
                write_json(
                    output / "runs" / arm / entry["instance_id"] / f"Proposed_s{int(seed)}.json",
                    record,
                )
                rows.append(row)
                print(
                    f"{arm} {entry['instance_id']} s{int(seed)}: {row['makespan']:.3f}, "
                    f"{row['runtime_seconds']:.2f}s, {row['iterations']} cycles, "
                    f"fallback={row['fallback_count']}",
                    flush=True,
                )
    config = dict(
        stage="E19 deployment replay: frozen operator identity",
        git_head=_git_head(),
        arms={arm: {key: identities[arm][key] for key in ("destroy", "main", "aux")} for arm in arms},
        e11_freeze_sha256=digest(E11_FREEZE),
        e18_freeze_sha256=digest(E18_FREEZE),
        instances=[entry["instance_id"] for entry in selected],
        seeds=[int(seed) for seed in seeds],
        budget="task_count seconds including state/matrix construction and candidate imports",
        order="serial; arms alternate per (instance index + seed) parity to spread machine drift",
        baselines="read from outputs/e12_literature_baselines/runs; not re-run",
        llm_calls=0,
        test_accessed=False,
        validation_accessed=False,
    )
    write_json(output / "experiment_config.json", config)
    return dict(rows=len(rows), config=config)


def stage_analyze(output: Path = DEFAULT_OUTPUT) -> Dict[str, Any]:
    config = read(output / "experiment_config.json")
    table = baseline_makespans()
    rows: List[Dict[str, Any]] = []
    for arm in config["arms"]:
        for instance_id in config["instances"]:
            for seed in config["seeds"]:
                record = read(output / "runs" / arm / instance_id / f"Proposed_s{seed}.json")
                row = dict(record["result"])
                row["arm"] = arm
                rows.append(row)
    pairs: List[Dict[str, Any]] = []
    for instance_id in config["instances"]:
        for seed in config["seeds"]:
            by_arm = {
                arm: next(
                    row for row in rows
                    if row["arm"] == arm and row["instance_id"] == instance_id and row["seed"] == seed
                )
                for arm in config["arms"]
            }
            pair = dict(instance_id=instance_id, seed=seed)
            for arm in config["arms"]:
                for method in BASELINES:
                    ref = table[(instance_id, seed, method)]
                    pair[f"gain_{arm}_vs_{method}"] = 100.0 * (1.0 - by_arm[arm]["makespan"] / ref)
            if "E11" in by_arm and "E18" in by_arm:
                pair["delta_e18_minus_e11_pct"] = 100.0 * (
                    1.0 - by_arm["E18"]["makespan"] / by_arm["E11"]["makespan"]
                )
            pairs.append(pair)
    summary: Dict[str, Any] = dict(arms=config["arms"], pairs=len(pairs))
    for arm in config["arms"]:
        summary[f"mean_makespan_{arm}"] = mean(
            row["makespan"] for row in rows if row["arm"] == arm
        )
        for method in BASELINES:
            gains = [p[f"gain_{arm}_vs_{method}"] for p in pairs]
            summary[f"mean_gain_{arm}_vs_{method}_pct"] = mean(gains)
            summary[f"wins_{arm}_vs_{method}"] = sum(1 for g in gains if g > 1e-9)
            summary[f"ties_{arm}_vs_{method}"] = sum(1 for g in gains if abs(g) <= 1e-9)
            summary[f"losses_{arm}_vs_{method}"] = sum(1 for g in gains if g < -1e-9)
    if all("delta_e18_minus_e11_pct" in pair for pair in pairs):
        deltas = [pair["delta_e18_minus_e11_pct"] for pair in pairs]
        summary["delta_e18_minus_e11_mean_pct"] = mean(deltas)
        summary["delta_e18_minus_e11_median_pct"] = sorted(deltas)[len(deltas) // 2]
        summary["e18_better"] = sum(1 for d in deltas if d > 1e-9)
        summary["e18_worse"] = sum(1 for d in deltas if d < -1e-9)
        summary["e18_tied"] = sum(1 for d in deltas if abs(d) <= 1e-9)
    write_json(output / "pairs.json", pairs)
    write_json(output / "summary.json", summary)
    write_json(output / "runs.json", [{k: v for k, v in row.items() if k != "best_routes"} for row in rows])
    lines = ["# E19 deployment replay: frozen operator identity", ""]
    lines += [f"- git head: `{config['git_head']}`", f"- instances: {len(config['instances'])}",
              f"- seeds: {config['seeds']}", f"- arms: {config['arms']}", "",
              "| Arm | Mean makespan | " + " | ".join(f"gain vs {m}" for m in BASELINES) + " |",
              "| --- | ---: | " + " | ".join("---:" for _ in BASELINES) + " |"]
    for arm in config["arms"]:
        cells = [f"{summary[f'mean_gain_{arm}_vs_{m}_pct']:+.3f}% ({summary[f'wins_{arm}_vs_{m}']}/"
                 f"{summary[f'ties_{arm}_vs_{m}']}/{summary[f'losses_{arm}_vs_{m}']})" for m in BASELINES]
        lines.append(f"| {arm} | {summary[f'mean_makespan_{arm}']:.3f} | " + " | ".join(cells) + " |")
    if "delta_e18_minus_e11_mean_pct" in summary:
        lines += ["", "## Paired E18 vs E11 (same instance, seed, budget)",
                  f"- mean `{summary['delta_e18_minus_e11_mean_pct']:+.3f}%` "
                  f"(positive = E18 better), median `{summary['delta_e18_minus_e11_median_pct']:+.3f}%`",
                  f"- E18 better/worse/tied: {summary['e18_better']}/{summary['e18_worse']}/{summary['e18_tied']}"]
    lines += ["", "Descriptive only: one operator pair per arm, four development instances, two seeds, "
                  "no repetition-level interval. Baselines are the immutable E12 records."]
    (output / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("run", "analyze"), required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--instances", type=Path, default=None)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(SEEDS))
    parser.add_argument("--arms", nargs="+", default=list(ARMS), choices=list(ARMS))
    args = parser.parse_args()
    if args.stage == "run":
        result = stage_run(args.output, instances=args.instances, seeds=args.seeds, arms=args.arms)
        print(json.dumps(result, indent=1, ensure_ascii=False))
    else:
        print(json.dumps(stage_analyze(args.output), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
