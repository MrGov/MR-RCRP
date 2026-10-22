"""Factory for building LangChain ChatOpenAI instances."""
from __future__ import annotations

import inspect
from typing import TYPE_CHECKING

from .config import LLMRuntimeConfig

if TYPE_CHECKING:
    from langchain_openai import ChatOpenAI


def build_langchain_chat_model(config: LLMRuntimeConfig) -> ChatOpenAI:
    """Construct a :class:`ChatOpenAI` from runtime config.

    Supports any OpenAI-compatible endpoint via ``config.base_url``.

    Raises:
        ImportError: If ``langchain-openai`` is not installed.
        ValueError: If ``api_key`` is empty.
    """
    if not config.api_key:
        raise ValueError(
            "OPERATOR_LLM_API_KEY is required. "
            "Set it in .env or as an environment variable."
        )

    try:
        from langchain_openai import ChatOpenAI as _ChatOpenAI
    except ImportError as exc:
        raise ImportError(
            "langchain-openai is required for the LangChain provider. "
            "Install it with: pip install langchain-openai"
        ) from exc

    kwargs: dict = {
        "model": config.model,
        "temperature": config.temperature,
        "api_key": config.api_key,
        "max_retries": config.max_retries,
        "request_timeout": config.timeout,
        "use_responses_api": True,
    }
    signature = inspect.signature(_ChatOpenAI)
    accepts_kwargs = any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    )
    if "use_responses_api" not in signature.parameters and not accepts_kwargs:
        raise RuntimeError("installed langchain-openai does not support Responses API")
    if "output_version" in signature.parameters or accepts_kwargs:
        kwargs["output_version"] = "responses/v1"
    if config.base_url:
        kwargs["base_url"] = config.base_url

    return _ChatOpenAI(**kwargs)
