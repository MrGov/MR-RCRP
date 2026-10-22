"""Hashing helpers for dictionary keys."""
from __future__ import annotations

from typing import Hashable, Tuple


def ordered_pair_key(a: Hashable, b: Hashable) -> Tuple[Hashable, Hashable]:
    """Return an ordered pair suitable as a dictionary key."""

    return (a, b)


def unordered_pair_key(a: Hashable, b: Hashable) -> Tuple[Hashable, Hashable]:
    """Return a stable unordered pair key."""

    return (a, b) if a <= b else (b, a)
