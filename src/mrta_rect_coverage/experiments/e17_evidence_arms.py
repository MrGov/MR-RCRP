"""E17: does Exact Route-DP evidence change what the LLM designs?

Two arms, identical in everything except the revision/generation prompt content:

``F1_scalar``
    Legacy behaviour: the LLM sees only the scalar/ranking feedback payload
    (``build_feedback_payload``) plus its own previous candidates.
``F2_dataset``
    The same prompt **plus** the F2_state_v2 dataset evidence payload: regime
    labels, cost structure, scale note, and position-level mode-gap notes that
    come out of the Exact Route-DP instrument (``e14``).

The endpoint is the operator quality the arm produces, measured by the existing
candidate evaluator: for each arm and repetition the best ``destroy`` and the best
``repair`` candidate over all rounds, ranked by ``avg_relative_improvement``.

This is a *mechanism* comparison, not a deployment claim: nothing here freezes or
deploys an operator. Repetitions are independent LLM samples (the provider samples
at a fixed temperature), so the two arms are not paired by seed; with the default
three repetitions this script reports spread, not a p-value.

Usage::

    $env:PYTHONPATH='src'
    python -m mrta_rect_coverage.experiments.e17_evidence_arms --stage run
    python -m mrta_rect_coverage.experiments.e17_evidence_arms --stage analyze
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from ..llm.operator_evolution.evolution_loop import EvolutionLoopConfig
from .operator_evolution_runner import run_operator_evolution

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = ROOT / "outputs/e17_evidence_arms"
DEFAULT_INSTANCES = "configs/instances_v1_dev_14.json"
DEFAULT_EVIDENCE_GLOB = "outputs/e14_state_regret_instrument/alns/*.json"

ARMS = ("F1_scalar", "F2_dataset")
ROUND_COUNT = 2
REPAIR_CANDIDATES = 2
DESTROY_CANDIDATES = 2
SEEDS = (0,)
TIMEOUT_MS = 2000.0
EVIDENCE_BUDGET_BYTES = 2500


def _arm_config(
    *,
    arm: str,
    repetition: int,
    output_root: Path,
    instances: str,
    evidence_glob: str,
) -> EvolutionLoopConfig:
    return EvolutionLoopConfig(
        project_root=ROOT,
        generated_dir=Path(f"generated_operators/e17/{arm}/rep{repetition}"),
        output_dir=output_root / arm / f"rep{repetition}",
        round_count=ROUND_COUNT,
        repair_candidates_per_round=REPAIR_CANDIDATES,
        destroy_candidates_per_round=DESTROY_CANDIDATES,
        benchmark_instance_list=instances,
        evidence_report_glob=evidence_glob if arm == "F2_dataset" else "",
        evidence_budget_bytes=EVIDENCE_BUDGET_BYTES,
        seeds=SEEDS,
        timeout_ms=TIMEOUT_MS,
        top_k_to_keep=2,
        operator_types_to_evolve=("repair", "destroy"),
        provider_name="langchain_openai_compatible",
        use_rich_prompts=True,
        allow_unsafe_candidate_execution=True,
    )


def _metric_rows(run_dir: Path) -> List[dict]:
    rows: List[dict] = []
    for path in sorted(run_dir.glob("round_*_metrics.csv")):
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                row["_source"] = path.name
                rows.append(row)
    return rows


def _best_by_type(rows: Iterable[dict]) -> Dict[str, Optional[dict]]:
    best: Dict[str, Optional[dict]] = {"destroy": None, "repair": None}
    for row in rows:
        operator_type = row.get("operator_type")
        if operator_type not in best:
            continue
        try:
            value = float(row["avg_relative_improvement"])
        except (KeyError, TypeError, ValueError):
            continue
        current = best[operator_type]
        if current is None or value > float(current["avg_relative_improvement"]):
            best[operator_type] = row
    return best


def _summarise_run(run_dir: Path, *, arm: str, repetition: int) -> dict:
    rows = _metric_rows(run_dir)
    best = _best_by_type(rows)
    payload: dict = {
        "arm": arm,
        "repetition": repetition,
        "run_dir": str(run_dir.relative_to(ROOT)),
        "candidate_count": len(rows),
    }
    for operator_type in ("destroy", "repair"):
        row = best[operator_type]
        if row is None:
            payload[operator_type] = None
            continue
        payload[operator_type] = {
            "operator_id": row.get("operator_id"),
            "avg_relative_improvement": float(row["avg_relative_improvement"]),
            "avg_makespan_delta": float(row.get("avg_makespan_delta") or 0.0),
            "success_rate": float(row.get("success_rate") or 0.0),
            "execution_status": row.get("execution_status"),
            "round_id": int(float(row.get("round_id") or 0)),
        }
    evidence_path = run_dir / "evidence.json"
    if evidence_path.is_file():
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        payload["evidence"] = {
            "feedback_mode": evidence.get("feedback_mode"),
            "byte_size": evidence.get("byte_size"),
            "instance_count": evidence.get("instance_count"),
            "position_note_count": len(evidence.get("position_notes") or []),
        }
    else:
        payload["evidence"] = None
    return payload


def stage_run(
    output: Path,
    *,
    repetitions: int,
    instances: str,
    evidence_glob: str,
) -> None:
    if repetitions < 1:
        raise SystemExit("--repetitions must be >= 1")
    output.mkdir(parents=True, exist_ok=True)
    runs: List[dict] = []
    started = time.time()
    for repetition in range(repetitions):
        # Alternate arm order so a slow machine drift cannot favour one arm.
        order = ARMS if repetition % 2 == 0 else tuple(reversed(ARMS))
        for arm in order:
            run_dir = output / arm / f"rep{repetition}"
            if run_dir.exists():
                print(f"skip existing {arm} rep{repetition}")
                runs.append(_summarise_run(run_dir, arm=arm, repetition=repetition))
                continue
            print(f"[{time.time() - started:7.1f}s] running {arm} rep{repetition}", flush=True)
            config = _arm_config(
                arm=arm,
                repetition=repetition,
                output_root=output,
                instances=instances,
                evidence_glob=evidence_glob,
            )
            run_operator_evolution(project_root=ROOT, config=config, freeze_best=False)
            runs.append(_summarise_run(run_dir, arm=arm, repetition=repetition))
            (output / "runs.json").write_text(
                json.dumps(runs, indent=2, ensure_ascii=False), encoding="utf-8"
            )
    print(f"done in {time.time() - started:.1f}s")


def _arm_values(runs: Sequence[dict], arm: str, operator_type: str) -> List[float]:
    values: List[float] = []
    for run in runs:
        if run["arm"] != arm:
            continue
        entry = run.get(operator_type)
        if entry is not None:
            values.append(float(entry["avg_relative_improvement"]))
    return values


def _describe(values: Sequence[float]) -> dict:
    if not values:
        return {"n": 0}
    return {
        "n": len(values),
        "median": statistics.median(values),
        "mean": statistics.fmean(values),
        "min": min(values),
        "max": max(values),
        "values": list(values),
    }


def stage_analyze(output: Path) -> None:
    runs_path = output / "runs.json"
    if not runs_path.is_file():
        raise SystemExit(f"missing {runs_path}; run --stage run first")
    runs = json.loads(runs_path.read_text(encoding="utf-8"))
    summary: dict = {"arms": {}, "repetitions": len({r["repetition"] for r in runs})}
    for arm in ARMS:
        summary["arms"][arm] = {
            operator_type: _describe(_arm_values(runs, arm, operator_type))
            for operator_type in ("destroy", "repair")
        }
    # Per-repetition paired difference (arms are independent samples, so this is a
    # descriptive contrast only).
    by_rep: Dict[int, Dict[str, dict]] = {}
    for run in runs:
        by_rep.setdefault(int(run["repetition"]), {})[run["arm"]] = run
    deltas: dict = {}
    for operator_type in ("destroy", "repair"):
        values = []
        for repetition, arms in sorted(by_rep.items()):
            left = arms.get("F1_scalar", {}).get(operator_type)
            right = arms.get("F2_dataset", {}).get(operator_type)
            if left and right:
                values.append(
                    float(right["avg_relative_improvement"])
                    - float(left["avg_relative_improvement"])
                )
        deltas[operator_type] = {"per_repetition": values, "median": statistics.median(values) if values else None}
    summary["delta_f2_minus_f1"] = deltas
    summary["runs"] = len(runs)
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (output / "REPORT.md").write_text(_render_report(summary, runs), encoding="utf-8")
    print(json.dumps(summary["arms"], indent=2))


def _fmt(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{value:+.4f}"


def _render_report(summary: dict, runs: Sequence[dict]) -> str:
    lines = [
        "# E17 — Exact Route-DP evidence vs scalar feedback (operator quality)",
        "",
        "## Protocol",
        "",
        f"- repetitions per arm: {summary['repetitions']} (independent LLM samples)",
        f"- rounds per run: {ROUND_COUNT}, candidates per round: "
        f"{REPAIR_CANDIDATES} repair + {DESTROY_CANDIDATES} destroy",
        f"- instances: `{DEFAULT_INSTANCES}` (v1 development, 7 families x 2 scales)",
        f"- candidate evaluation: seeds {list(SEEDS)}, timeout {TIMEOUT_MS:.0f} ms",
        "- arms differ only in the prompt evidence block; `F1_scalar` keeps the "
        "legacy scalar/ranking feedback, `F2_dataset` adds the F2_state_v2 panel payload",
        "- endpoint: best candidate per operator type per run, by "
        "`avg_relative_improvement` (candidates never deployed here)",
        "",
        "## Arm medians (avg_relative_improvement)",
        "",
        "| arm | destroy median | destroy range | repair median | repair range |",
        "| --- | --- | --- | --- | --- |",
    ]
    for arm in ARMS:
        destroy = summary["arms"][arm]["destroy"]
        repair = summary["arms"][arm]["repair"]
        lines.append(
            "| {arm} | {dm} | {dr} | {rm} | {rr} |".format(
                arm=arm,
                dm=_fmt(destroy.get("median")),
                dr=(
                    f"{destroy['min']:+.4f} … {destroy['max']:+.4f}"
                    if destroy.get("n")
                    else "n/a"
                ),
                rm=_fmt(repair.get("median")),
                rr=(
                    f"{repair['min']:+.4f} … {repair['max']:+.4f}"
                    if repair.get("n")
                    else "n/a"
                ),
            )
        )
    lines += ["", "## Per-repetition difference (F2 − F1)", ""]
    for operator_type in ("destroy", "repair"):
        entry = summary["delta_f2_minus_f1"][operator_type]
        values = ", ".join(_fmt(v) for v in entry["per_repetition"]) or "n/a"
        lines.append(f"- {operator_type}: median {_fmt(entry['median'])}; per rep {values}")
    lines += [
        "",
        "## Per-run detail",
        "",
        "| arm | rep | best destroy | succ | round | best repair | succ |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for run in sorted(runs, key=lambda r: (r["arm"], r["repetition"])):
        destroy = run.get("destroy") or {}
        repair = run.get("repair") or {}
        lines.append(
            "| {arm} | {rep} | {d} | {ds} | {dr} | {r} | {rs} |".format(
                arm=run["arm"],
                rep=run["repetition"],
                d=_fmt(destroy.get("avg_relative_improvement")),
                ds=f"{destroy.get('success_rate', 0):.2f}" if destroy else "n/a",
                dr=destroy.get("round_id", "n/a"),
                r=_fmt(repair.get("avg_relative_improvement")),
                rs=f"{repair.get('success_rate', 0):.2f}" if repair else "n/a",
            )
        )
    lines += [
        "",
        "## What this can and cannot show",
        "",
        "The arms are independent LLM samples at a fixed temperature, not paired by",
        "seed, so the per-repetition differences above are descriptive. With a handful",
        "of repetitions the report bounds the spread; a confirmatory claim needs the",
        "pre-registered repetition count and the bootstrap CI from",
        "`docs/statistical_analysis_plan.md`.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("run", "analyze"), required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--instances", type=str, default=DEFAULT_INSTANCES)
    parser.add_argument("--evidence-glob", type=str, default=DEFAULT_EVIDENCE_GLOB)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    if args.stage == "run":
        stage_run(
            output,
            repetitions=args.repetitions,
            instances=args.instances,
            evidence_glob=args.evidence_glob,
        )
    else:
        stage_analyze(output)


if __name__ == "__main__":
    sys.exit(main())
