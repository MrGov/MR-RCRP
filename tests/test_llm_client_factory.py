"""Tests for LLM client factory (no real network calls)."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from mrta_rect_coverage.llm.runtime.config import LLMRuntimeConfig


def test_build_raises_without_api_key() -> None:
    from mrta_rect_coverage.llm.runtime.client_factory import build_langchain_chat_model

    cfg = LLMRuntimeConfig(api_key="")
    with pytest.raises(ValueError, match="OPERATOR_LLM_API_KEY"):
        build_langchain_chat_model(cfg)


def test_build_raises_without_langchain_installed() -> None:
    """Simulate langchain-openai not being installed."""
    import builtins
    real_import = builtins.__import__

    def mock_import(name: str, *args, **kwargs):
        if name == "langchain_openai":
            raise ImportError("No module named 'langchain_openai'")
        return real_import(name, *args, **kwargs)

    cfg = LLMRuntimeConfig(api_key="sk-test")
    with patch("builtins.__import__", side_effect=mock_import):
        with pytest.raises(ImportError, match="langchain-openai"):
            from mrta_rect_coverage.llm.runtime.client_factory import build_langchain_chat_model
            build_langchain_chat_model(cfg)


def test_build_passes_correct_kwargs() -> None:
    """Mock ChatOpenAI to verify kwargs are forwarded correctly."""
    mock_cls = MagicMock()
    mock_instance = MagicMock()
    mock_cls.return_value = mock_instance

    cfg = LLMRuntimeConfig(
        api_key="sk-test-key",
        model="gpt-4o-mini",
        temperature=0.5,
        timeout=90,
        max_retries=3,
        base_url="https://api.example.com/v1",
    )

    with patch.dict("sys.modules", {"langchain_openai": MagicMock(ChatOpenAI=mock_cls)}):
        from mrta_rect_coverage.llm.runtime import client_factory
        # Force re-execution of the factory with our mock
        import importlib
        importlib.reload(client_factory)
        result = client_factory.build_langchain_chat_model(cfg)

    mock_cls.assert_called_once()
    call_kwargs = mock_cls.call_args[1]
    assert call_kwargs["model"] == "gpt-4o-mini"
    assert call_kwargs["temperature"] == 0.5
    assert call_kwargs["api_key"] == "sk-test-key"
    assert call_kwargs["max_retries"] == 3
    assert call_kwargs["request_timeout"] == 90
    assert call_kwargs["base_url"] == "https://api.example.com/v1"


def test_build_omits_base_url_when_empty() -> None:
    """When base_url is empty, it should not be passed to ChatOpenAI."""
    mock_cls = MagicMock()
    mock_cls.return_value = MagicMock()

    cfg = LLMRuntimeConfig(api_key="sk-test-key", base_url="")

    with patch.dict("sys.modules", {"langchain_openai": MagicMock(ChatOpenAI=mock_cls)}):
        from mrta_rect_coverage.llm.runtime import client_factory
        import importlib
        importlib.reload(client_factory)
        client_factory.build_langchain_chat_model(cfg)

    call_kwargs = mock_cls.call_args[1]
    assert "base_url" not in call_kwargs


def test_build_explicitly_uses_responses_api() -> None:
    mock_cls = MagicMock()
    mock_cls.return_value = MagicMock()
    cfg = LLMRuntimeConfig(api_key="sk-test-key")
    with patch.dict("sys.modules", {"langchain_openai": MagicMock(ChatOpenAI=mock_cls)}):
        from mrta_rect_coverage.llm.runtime import client_factory
        import importlib
        importlib.reload(client_factory)
        client_factory.build_langchain_chat_model(cfg)
    kwargs = mock_cls.call_args[1]
    assert kwargs["use_responses_api"] is True
    assert kwargs["output_version"] == "responses/v1"
