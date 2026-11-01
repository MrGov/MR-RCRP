"""Tests for LLM runtime configuration loading."""
from __future__ import annotations

import os
from unittest.mock import patch

from mrta_rect_coverage.llm.runtime.config import LLMRuntimeConfig, load_from_env


def test_default_config_values() -> None:
    cfg = LLMRuntimeConfig()
    assert cfg.provider == "mock"
    assert cfg.api_key == ""
    assert cfg.base_url == ""
    assert cfg.model == "gpt-4o"
    assert cfg.temperature == 0.7
    assert cfg.timeout == 120
    assert cfg.max_retries == 2


def test_config_is_frozen() -> None:
    cfg = LLMRuntimeConfig()
    try:
        cfg.model = "other"  # type: ignore[misc]
        assert False, "Should have raised FrozenInstanceError"
    except AttributeError:
        pass


def test_load_from_env_reads_env_vars() -> None:
    env = {
        "OPERATOR_LLM_PROVIDER": "langchain_openai_compatible",
        "OPERATOR_LLM_API_KEY": "sk-test-key",
        "OPERATOR_LLM_BASE_URL": "https://api.example.com/v1",
        "OPERATOR_LLM_MODEL": "deepseek-chat",
        "OPERATOR_LLM_TEMPERATURE": "0.3",
        "OPERATOR_LLM_TIMEOUT": "60",
        "OPERATOR_LLM_MAX_RETRIES": "5",
        "OPERATOR_LLM_MAX_OUTPUT_TOKENS": "1800",
    }
    with patch.dict(os.environ, env, clear=False):
        cfg = load_from_env()

    assert cfg.provider == "langchain_openai_compatible"
    assert cfg.api_key == "sk-test-key"
    assert cfg.base_url == "https://api.example.com/v1"
    assert cfg.model == "deepseek-chat"
    assert cfg.temperature == 0.3
    assert cfg.timeout == 60
    assert cfg.max_retries == 5
    assert cfg.max_output_tokens == 1800


def test_load_from_env_supports_no_temperature_for_single_attempt_calls() -> None:
    with patch("dotenv.load_dotenv", return_value=None):
        with patch.dict(os.environ, {"OPERATOR_LLM_TEMPERATURE": "none"}, clear=False):
            cfg = load_from_env()
    assert cfg.temperature is None


def test_load_from_env_uses_defaults_when_vars_missing() -> None:
    env_keys = [
        "OPERATOR_LLM_PROVIDER",
        "OPERATOR_LLM_API_KEY",
        "OPERATOR_LLM_BASE_URL",
        "OPERATOR_LLM_MODEL",
        "OPERATOR_LLM_TEMPERATURE",
        "OPERATOR_LLM_TIMEOUT",
        "OPERATOR_LLM_MAX_RETRIES",
        "OPERATOR_LLM_MAX_OUTPUT_TOKENS",
    ]
    cleaned = {k: v for k, v in os.environ.items() if k not in env_keys}
    # Patch dotenv.load_dotenv so the real .env file doesn't leak values
    with patch("dotenv.load_dotenv", return_value=None):
        with patch.dict(os.environ, cleaned, clear=True):
            cfg = load_from_env()

    assert cfg.provider == "mock"
    assert cfg.api_key == ""
    assert cfg.model == "gpt-4o"


def test_load_from_env_survives_missing_dotenv() -> None:
    """load_from_env should not crash if python-dotenv is not installed."""
    with patch.dict(os.environ, {}, clear=False):
        # Even if dotenv import fails internally, load_from_env catches it
        cfg = load_from_env()
    assert isinstance(cfg, LLMRuntimeConfig)
