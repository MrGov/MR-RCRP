"""Logging helpers."""
from __future__ import annotations

import logging
from typing import Optional


def configure_root_logger(level: int = logging.INFO) -> None:
    """Configure a simple root logger if not already configured."""

    if logging.getLogger().handlers:
        return
    logging.basicConfig(
        level=level,
        format="[%(asctime)s] %(levelname)s - %(name)s - %(message)s",
    )


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Retrieve a logger, ensuring default configuration exists."""

    configure_root_logger()
    return logging.getLogger(name)
