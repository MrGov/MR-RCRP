from __future__ import annotations

from types import SimpleNamespace

import importlib


MODULE = "mrta_rect_coverage.experiments.pilot_path_validator"


def _validator():
    return importlib.import_module(MODULE)


def _stat(*, birthtime: int = 100, ctime: int = 200, inode: int = 7):
    return SimpleNamespace(
        st_dev=3,
        st_ino=inode,
        st_size=11,
        st_mtime_ns=400,
        st_birthtime_ns=birthtime,
        st_ctime_ns=ctime,
    )


def test_non_windows_prefers_ctime_for_stable_snapshot(monkeypatch) -> None:
    validator = _validator()
    monkeypatch.setattr(
        validator,
        "os",
        SimpleNamespace(name="posix"),
    )

    snapshot = validator._snapshot_from_stat(_stat(birthtime=100, ctime=200))

    assert snapshot == (3, 7, 11, 400, 200)


def test_non_windows_metadata_only_ctime_mutation_changes_snapshot(
    monkeypatch,
) -> None:
    validator = _validator()
    monkeypatch.setattr(
        validator,
        "os",
        SimpleNamespace(name="darwin"),
    )

    before = validator._snapshot_from_stat(_stat(birthtime=100, ctime=200))
    after = validator._snapshot_from_stat(_stat(birthtime=100, ctime=201))

    assert before != after


def test_windows_prefers_birthtime_and_falls_back_to_ctime(monkeypatch) -> None:
    validator = _validator()
    monkeypatch.setattr(
        validator,
        "os",
        SimpleNamespace(name="nt"),
    )

    with_birthtime = validator._snapshot_from_stat(
        _stat(birthtime=100, ctime=200)
    )
    without_birthtime = validator._snapshot_from_stat(
        SimpleNamespace(
            st_dev=3,
            st_ino=7,
            st_size=11,
            st_mtime_ns=400,
            st_ctime_ns=200,
        )
    )

    assert with_birthtime == (3, 7, 11, 400, 100)
    assert without_birthtime == (3, 7, 11, 400, 200)


def test_hardlink_identity_remains_independent_of_timestamps() -> None:
    validator = _validator()
    first = validator._identity_from_stat(_stat(birthtime=100, ctime=200, inode=7))
    same_file = validator._identity_from_stat(
        _stat(birthtime=101, ctime=201, inode=7)
    )
    different_file = validator._identity_from_stat(
        _stat(birthtime=100, ctime=200, inode=8)
    )

    assert first == same_file == (3, 7)
    assert different_file != first
