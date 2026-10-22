"""Runtime configuration for LLM providers, loaded from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LLMRuntimeConfig:
    """Immutable configuration for an OpenAI-compatible LLM endpoint.

    All fields can be populated from environment variables via
    :func:`load_from_env`, or constructed directly for testing.
    """

    provider: str = "mock"
    api_key: str = ""
    base_url: str = ""
    model: str = "gpt-4o"
    temperature: float = 0.7
    timeout: int = 120
    max_retries: int = 2


def load_from_env() -> LLMRuntimeConfig:
    """Build :class:`LLMRuntimeConfig` from ``OPERATOR_LLM_*`` env vars.

    Calls ``load_dotenv()`` so a ``.env`` file in the working directory
    (or any parent) is picked up automatically.
    """
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        _load_local_dotenv()

    return LLMRuntimeConfig(
        provider=os.getenv("OPERATOR_LLM_PROVIDER", "mock"),
        api_key=os.getenv("OPERATOR_LLM_API_KEY", ""),
        base_url=os.getenv("OPERATOR_LLM_BASE_URL", ""),
        model=os.getenv("OPERATOR_LLM_MODEL", "gpt-4o"),
        temperature=float(os.getenv("OPERATOR_LLM_TEMPERATURE", "0.7")),
        timeout=int(os.getenv("OPERATOR_LLM_TIMEOUT", "120")),
        max_retries=int(os.getenv("OPERATOR_LLM_MAX_RETRIES", "2")),
    )


def _load_local_dotenv() -> None:
    """Small dependency-free fallback for the project's local ``.env`` file."""
    current = Path.cwd().resolve()
    candidates = (current, *current.parents)
    for directory in candidates:
        path = directory / ".env"
        if not path.is_file():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            name = name.strip()
            value = value.strip().strip('"').strip("'")
            if name and name not in os.environ:
                os.environ[name] = value
        return
