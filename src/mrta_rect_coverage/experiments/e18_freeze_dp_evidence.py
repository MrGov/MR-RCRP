"""Freeze the E17 F2_dataset evidence-driven operators as the deployed identity.

E11 froze the E5/E7 operators. E17 then showed that the same LLM, prompted with
the exact Route-DP dataset panel instead of a scalar score, produced stronger
Destroy/Repair candidates in every repetition. This module packages the winning
E17 F2 candidates as a *separate*, fully hashed freeze bundle so that the
deployment comparison can be replayed without touching the E11 or E8 artefacts
(E12 validates those byte-for-byte).

Nothing here re-evaluates an operator: the numbers are read from
``outputs/e17_evidence_arms/runs.json`` and the sources are hashed from
``generated_operators/e17/``. The bundle is development-selected only; no
validation or test instance is touched.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Any, Dict, List, Sequence, Tuple

from .e3_alns import ROOT, write_json
from .e5_destroy_repair import digest, read
from .e11_structural_benchmark import byte_hash

E17_RUNS = ROOT / "outputs/e17_evidence_arms/runs.json"
E11_FREEZE = ROOT / "outputs/e11_structural_benchmark/algorithm_freeze.json"
E11_CONFIG = ROOT / "outputs/e11_structural_benchmark/experiment_config.json"
E8_SELECTION = ROOT / "outputs/e8_repair_portfolio/selection_decision.json"
GENERATED_ROOT = ROOT / "generated_operators/e17"
DEFAULT_OUTPUT = ROOT / "outputs/e18_freeze_dp_evidence"
DEFAULT_ARM = "F2_dataset"
OPERATOR_TYPES = ("destroy", "repair")
IDENTITY_FIELDS = ("source_path", "source_hash", "operator_id", "generation")
SELECTION_RULE = (
    "Within the E17 F2_dataset arm, take the candidate with the highest "
    "avg_relative_improvement among execution_status=='success', ties broken by "
    "the lower repetition index. No parameter tuning, no re-evaluation, no "
    "validation or test access. E11 'main' identity is inherited unchanged so "
    "that the repair pool keeps its declared slot layout."
)
SCOPE = (
    "development-selected freeze for the deployment comparison; supersedes the "
    "E11 freeze only for the Proposed arm. The E11/E8 artefacts stay untouched "
    "and remain the reference for every historical E11/E12/E13 record."
)


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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_runs(path: Path = E17_RUNS) -> List[Dict[str, Any]]:
    if not path.exists():
        raise SystemExit(f"E17 runs missing: {path} (run e17 --stage run first)")
    runs = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(runs, list) or not runs:
        raise SystemExit(f"E17 runs malformed: {path}")
    return runs


def candidate_source(arm: str, repetition: int, record: Dict[str, Any]) -> Path:
    operator_id = str(record["operator_id"])
    path = (
        GENERATED_ROOT
        / arm
        / f"rep{int(repetition)}"
        / f"round_{int(record['round_id']):03d}"
        / f"{operator_id}.py"
    )
    if not path.exists():
        raise SystemExit(f"generated operator source missing: {path}")
    return path


def select_winner(
    runs: Sequence[Dict[str, Any]], arm: str, operator_type: str
) -> Tuple[int, Dict[str, Any], List[float]]:
    if operator_type not in OPERATOR_TYPES:
        raise ValueError(operator_type)
    rows = [r for r in runs if r.get("arm") == arm]
    if not rows:
        raise SystemExit(f"no E17 runs for arm {arm}")
    scored: List[Tuple[float, int, Dict[str, Any]]] = []
    for run in rows:
        record = run.get(operator_type) or {}
        if record.get("execution_status") != "success":
            continue
        scored.append((float(record["avg_relative_improvement"]), int(run["repetition"]), record))
    if not scored:
        raise SystemExit(f"no successful {operator_type} candidate in arm {arm}")
    best = max(scored, key=lambda item: (item[0], -item[1]))
    pool = sorted((value for value, _, _ in scored), reverse=True)
    return best[1], best[2], pool


def _identity(path: Path, operator_id: str, generation: str) -> Dict[str, Any]:
    return dict(
        source_path=str(path.relative_to(ROOT)).replace("\\", "/"),
        source_hash=digest(path),
        operator_id=operator_id,
        generation=generation,
    )


def build_identities(
    runs: Sequence[Dict[str, Any]], *, arm: str = DEFAULT_ARM
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
    inherited = read(E8_SELECTION)
    for key in ("destroy", "main", "aux"):
        if key not in inherited:
            raise SystemExit(f"{E8_SELECTION} missing operator slot {key}")
    main = {field: inherited["main"][field] for field in IDENTITY_FIELDS}
    if digest(ROOT / main["source_path"]) != main["source_hash"]:
        raise SystemExit("E11 main operator source changed; cannot inherit it")

    # E11 slot names: destroy / main / aux. The generated repair candidate takes
    # the aux slot, exactly where E11 placed the E7 repair.
    slots = {"destroy": "destroy", "repair": "aux"}
    identities: Dict[str, Dict[str, Any]] = {"main": main}
    provenance: Dict[str, Any] = {}
    for operator_type in OPERATOR_TYPES:
        repetition, record, pool = select_winner(runs, arm, operator_type)
        path = candidate_source(arm, repetition, record)
        identities[slots[operator_type]] = _identity(
            path,
            str(record["operator_id"]),
            f"E17-{arm}-rep{repetition}-round{int(record['round_id'])}",
        )
        provenance[operator_type] = dict(
            arm=arm,
            repetition=repetition,
            round_id=int(record["round_id"]),
            operator_id=str(record["operator_id"]),
            avg_relative_improvement=float(record["avg_relative_improvement"]),
            avg_makespan_delta=record.get("avg_makespan_delta"),
            success_rate=record.get("success_rate"),
            candidate_pool_relative_improvements=pool,
            candidate_count=len(pool),
        )
    return identities, provenance


def stage_freeze(
    output: Path = DEFAULT_OUTPUT, *, arm: str = DEFAULT_ARM
) -> Dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    runs = load_runs()
    identities, provenance = build_identities(runs, arm=arm)

    e11_freeze = read(E11_FREEZE)
    for key in ("parameters", "pools", "selector", "seeds", "alpha_seconds_per_task",
                "initial_constructor", "dataset_version", "manifest_sha256"):
        if key not in e11_freeze:
            raise SystemExit(f"E11 freeze missing field {key}")
    for key, value in identities.items():
        if digest(ROOT / value["source_path"]) != value["source_hash"]:
            raise SystemExit(f"identity hash mismatch for {key}")

    freeze = dict(e11_freeze)
    freeze.update(
        recommended_proposed="AUX",
        operators=identities,
        deployed_destroy=identities["destroy"],
        deployed_repair=identities["aux"],
        selection_rule=SELECTION_RULE,
        scope=SCOPE,
        supersedes="outputs/e11_structural_benchmark/algorithm_freeze.json",
        evidence_source=dict(
            runs=str(E17_RUNS.relative_to(ROOT)).replace("\\", "/"),
            runs_sha256=byte_hash(E17_RUNS),
            arm=arm,
            repetitions=len([r for r in runs if r.get("arm") == arm]),
        ),
        freeze_provenance=provenance,
        created_at_utc=_now(),
        git_head=_git_head(),
        no_test_execution=True,
        no_validation_execution=True,
    )

    selection = dict(
        derived_from=SCOPE,
        arm=arm,
        operators=identities,
        provenance=provenance,
        created_at_utc=freeze["created_at_utc"],
        git_head=freeze["git_head"],
    )

    sources = [ROOT / identities[key]["source_path"] for key in ("destroy", "main", "aux")]
    config = dict(
        stage="E18 E17-evidence freeze",
        git_head=freeze["git_head"],
        operators=identities,
        e11_freeze=dict(
            path=str(E11_FREEZE.relative_to(ROOT)).replace("\\", "/"),
            sha256=byte_hash(E11_FREEZE),
        ),
        e11_experiment_config=dict(
            path=str(E11_CONFIG.relative_to(ROOT)).replace("\\", "/"),
            sha256=byte_hash(E11_CONFIG),
        ),
        e8_selection=dict(
            path=str(E8_SELECTION.relative_to(ROOT)).replace("\\", "/"),
            sha256=byte_hash(E8_SELECTION),
        ),
        e17_runs=dict(
            path=str(E17_RUNS.relative_to(ROOT)).replace("\\", "/"),
            sha256=byte_hash(E17_RUNS),
        ),
        frozen_hashes={str(path): byte_hash(path) for path in sources},
        selection_rule=SELECTION_RULE,
        scope=SCOPE,
        no_test_execution=True,
        no_validation_execution=True,
        created_at_utc=freeze["created_at_utc"],
    )

    write_json(output / "algorithm_freeze.json", freeze)
    write_json(output / "selection_decision.json", selection)
    write_json(output / "experiment_config.json", config)
    return dict(output=str(output), operators=identities, provenance=provenance)


def stage_verify(output: Path = DEFAULT_OUTPUT) -> Dict[str, Any]:
    freeze = read(output / "algorithm_freeze.json")
    selection = read(output / "selection_decision.json")
    config = read(output / "experiment_config.json")
    problems: List[str] = []

    for key in ("destroy", "main", "aux"):
        entry = freeze["operators"].get(key) or {}
        for field in IDENTITY_FIELDS:
            if field not in entry:
                problems.append(f"operators.{key} missing {field}")
        if entry:
            if digest(ROOT / entry["source_path"]) != entry["source_hash"]:
                problems.append(f"operators.{key} source hash mismatch")
        if entry != (selection["operators"].get(key) or {}):
            problems.append(f"selection_decision.{key} disagrees with freeze")
    if freeze.get("deployed_destroy") != freeze["operators"].get("destroy"):
        problems.append("deployed_destroy does not match operators.destroy")
    if freeze.get("deployed_repair") != freeze["operators"].get("aux"):
        problems.append("deployed_repair does not match operators.aux")
    if freeze.get("recommended_proposed") != "AUX":
        problems.append("recommended_proposed must stay AUX for E12")

    runs = load_runs()
    for operator_type in OPERATOR_TYPES:
        record = (freeze.get("freeze_provenance") or {}).get(operator_type) or {}
        if not record:
            problems.append(f"freeze_provenance missing {operator_type}")
            continue
        _, winner, pool = select_winner(runs, DEFAULT_ARM, operator_type)
        if str(record.get("operator_id")) != str(winner["operator_id"]):
            problems.append(f"provenance {operator_type} is not the E17 winner")
        if pool != record.get("candidate_pool_relative_improvements"):
            problems.append(f"provenance {operator_type} candidate pool drifted")

    for name in ("e11_freeze", "e11_experiment_config", "e8_selection", "e17_runs"):
        entry = config.get(name) or {}
        path = ROOT / str(entry.get("path", ""))
        if not entry or not path.exists():
            problems.append(f"experiment_config.{name} path missing")
        elif byte_hash(path) != entry.get("sha256"):
            problems.append(f"experiment_config.{name} sha256 drifted")
    for path_text, expected in (config.get("frozen_hashes") or {}).items():
        path = Path(path_text)
        if not path.exists() or byte_hash(path) != expected:
            problems.append(f"frozen source drifted: {path_text}")

    if problems:
        for problem in problems:
            print(f"problem: {problem}")
        raise SystemExit(1)
    return dict(problems=[], output=str(output))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("freeze", "verify"), required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--arm", default=DEFAULT_ARM)
    args = parser.parse_args()
    if args.stage == "freeze":
        result = stage_freeze(args.output, arm=args.arm)
        print(json.dumps(result["operators"], indent=1, ensure_ascii=False))
    else:
        print(json.dumps(stage_verify(args.output), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
