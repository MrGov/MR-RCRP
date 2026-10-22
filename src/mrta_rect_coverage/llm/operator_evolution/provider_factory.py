"""Factory for building operator evolution providers by name."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from .provider_interface import OperatorEvolutionProvider

logger = logging.getLogger(__name__)

# Canonical provider names
PROVIDER_MOCK = "mock"
PROVIDER_FILE = "file"
PROVIDER_LANGCHAIN = "langchain_openai_compatible"


def build_provider(
    provider_name: str,
    *,
    exchange_dir: Optional[Path] = None,
    raw_response_dir: Optional[Path] = None,
) -> OperatorEvolutionProvider:
    """Construct a provider instance by name.

    Args:
        provider_name: One of ``"mock"``, ``"file"``, or
            ``"langchain_openai_compatible"``.
        exchange_dir: Required for the ``"file"`` provider.
        raw_response_dir: Optional directory for saving raw LLM responses
            (used by the ``"langchain_openai_compatible"`` provider).

    Returns:
        An :class:`OperatorEvolutionProvider` implementation.

    Raises:
        ValueError: If the provider name is unknown or required args are missing.
    """
    if provider_name == PROVIDER_MOCK:
        from .mock_provider import MockOperatorEvolutionProvider
        logger.info("Using MockOperatorEvolutionProvider")
        return MockOperatorEvolutionProvider()

    if provider_name == PROVIDER_FILE:
        if exchange_dir is None:
            raise ValueError("exchange_dir is required for the file provider")
        from .file_provider import FileOperatorEvolutionProvider
        logger.info("Using FileOperatorEvolutionProvider (exchange_dir=%s)", exchange_dir)
        return FileOperatorEvolutionProvider(exchange_dir=exchange_dir)

    if provider_name == PROVIDER_LANGCHAIN:
        from ..runtime.config import load_from_env
        from ..runtime.client_factory import build_langchain_chat_model
        from .langchain_provider import LangChainOperatorEvolutionProvider

        runtime_cfg = load_from_env()
        chat_model = build_langchain_chat_model(runtime_cfg)
        logger.info(
            "Using LangChainOperatorEvolutionProvider (model=%s, base_url=%s)",
            runtime_cfg.model,
            runtime_cfg.base_url or "(default)",
        )
        return LangChainOperatorEvolutionProvider(
            chat_model=chat_model,
            raw_response_dir=raw_response_dir,
            requested_temperature=runtime_cfg.temperature,
        )

    raise ValueError(
        f"Unknown provider: {provider_name!r}. "
        f"Choose from: {PROVIDER_MOCK!r}, {PROVIDER_FILE!r}, {PROVIDER_LANGCHAIN!r}"
    )
