"""Invariants for the E18 freeze bundle and the E19 deployment replay.

The interesting failure modes here are silent: a bundle whose declared hash does
not match the file it points at, a freeze that quietly stops being an AUX freeze,
or a replay arm that reads the wrong operator slot. Each test pins one of them.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mrta_rect_coverage.experiments import e18_freeze_dp_evidence as e18
from mrta_rect_coverage.experiments import e19_deployment_freezes as e19
from mrta_rect_coverage.experiments.e3_alns import ROOT


def _candidate(operator_id: str, rel: float, status: str = "success", round_id: int = 0) -> dict:
    return dict(
        operator_id=operator_id,
        round_id=round_id,
        avg_relative_improvement=rel,
        avg_makespan_delta=1.0,
        success_rate=1.0,
        execution_status=status,
    )


def _runs(*, destroy, repair, arm: str = "F2_dataset"):
    rows = []
    for repetition, (d_rec, r_rec) in enumerate(zip(destroy, repair)):
        rows.append(dict(arm=arm, repetition=repetition, destroy=d_rec, repair=r_rec))
    return rows


def test_select_winner_takes_highest_relative_improvement():
    runs = _runs(
        destroy=[_candidate("d0", 0.10), _candidate("d1", 0.25, round_id=1)],
        repair=[_candidate("r0", 0.02), _candidate("r1", 0.01)],
    )
    repetition, record, pool = e18.select_winner(runs, "F2_dataset", "destroy")
    assert record["operator_id"] == "d1"
    assert repetition == 1
    assert pool == [0.25, 0.10]


def test_select_winner_skips_failed_candidates():
    runs = _runs(
        destroy=[_candidate("d0", 0.90, status="contract_error"), _candidate("d1", 0.20)],
        repair=[_candidate("r0", 0.02), _candidate("r1", 0.01)],
    )
    _, record, pool = e18.select_winner(runs, "F2_dataset", "destroy")
    assert record["operator_id"] == "d1"
    assert pool == [0.20]


def test_select_winner_rejects_empty_arm():
    with pytest.raises(SystemExit):
        e18.select_winner([], "F2_dataset", "destroy")


def test_candidate_source_missing_file_is_loud(monkeypatch, tmp_path):
    monkeypatch.setattr(e18, "GENERATED_ROOT", tmp_path)
    with pytest.raises(SystemExit):
        e18.candidate_source("F2_dataset", 0, dict(operator_id="d0", round_id=0))


@pytest.mark.skipif(
    not (ROOT / "outputs/e18_freeze_dp_evidence/algorithm_freeze.json").exists(),
    reason="E18 bundle not built",
)
def test_committed_bundle_verifies():
    assert e18.stage_verify(e18.DEFAULT_OUTPUT)["problems"] == []


@pytest.mark.skipif(
    not (ROOT / "outputs/e18_freeze_dp_evidence/algorithm_freeze.json").exists(),
    reason="E18 bundle not built",
)
def test_bundle_is_aux_and_slot_split_is_explicit():
    freeze = json.loads((e18.DEFAULT_OUTPUT / "algorithm_freeze.json").read_text(encoding="utf-8"))
    assert freeze["recommended_proposed"] == "AUX"
    assert freeze["deployed_repair"] == freeze["operators"]["aux"]
    assert freeze["deployed_destroy"] == freeze["operators"]["destroy"]
    # The inherited slot must stay byte-identical to the E8 decision.
    inherited = e18.read(e18.E8_SELECTION)
    assert freeze["operators"]["main"]["source_hash"] == inherited["main"]["source_hash"]


@pytest.mark.skipif(
    not (ROOT / "outputs/e11_structural_benchmark/algorithm_freeze.json").exists(),
    reason="E11 freeze absent",
)
def test_freeze_identities_resolve_both_arms():
    for arm in e19.ARMS:
        identities = e19.freeze_identities(arm)
        assert set(identities) == {"destroy", "main", "aux"}
        for entry in identities.values():
            assert Path(entry["source_path"]).exists()


def test_freeze_identities_rejects_hash_mismatch(monkeypatch, tmp_path):
    if not (ROOT / "outputs/e11_structural_benchmark/algorithm_freeze.json").exists():
        pytest.skip("E11 freeze absent")
    freeze = json.loads(e19.E11_FREEZE.read_text(encoding="utf-8"))
    freeze["operators"]["destroy"]["source_hash"] = "0" * 64
    fake = tmp_path / "algorithm_freeze.json"
    fake.write_text(json.dumps(freeze), encoding="utf-8")
    monkeypatch.setattr(e19, "E11_FREEZE", fake)
    with pytest.raises(SystemExit):
        e19.freeze_identities("E11")


def test_arms_and_samples_are_declared_consistently():
    assert e19.ARMS == ("E11", "E18")
    assert len(e19.SAMPLES) == 4 and e19.SEEDS == (0, 1)
    assert "Proposed" not in e19.BASELINES
