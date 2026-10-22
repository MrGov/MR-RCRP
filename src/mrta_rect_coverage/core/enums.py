"""Enumerations for MRTA rectangular coverage problem."""
from __future__ import annotations

from enum import Enum, auto


class Corner(str, Enum):
    """Entry or exit corner of a rectangular task."""

    LB = "LB"
    LT = "LT"
    RB = "RB"
    RT = "RT"


class SweepMode(str, Enum):
    """Coverage sweep mode within a task."""

    H = "H"
    V = "V"
