"""Lightweight governance checks for the configuration contract (docs/CONFIGURATION.md)."""

from __future__ import annotations

from app.core.config import Settings

RELEVANT_ENV = [
    "MIMO_API_KEY",
    "MIMO_BASE_URL",
    "MIMO_API_BASE_URL",
    "MIMO_ASR_MODEL",
    "MIMO_TTS_MODEL",
    "MIMO_LLM_MODEL",
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_BASE_URL",
    "DEEPSEEK_API_BASE_URL",
    "DEEPSEEK_DEFAULT_MODEL",
    "DEEPSEEK_MODEL",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "OPENAI_API_BASE_URL",
    "OPENAI_DEFAULT_MODEL",
    "OPENAI_MODEL",
    "AI_CONNECT_TIMEOUT_SECONDS",
    "AI_REQUEST_TIMEOUT_SECONDS",
    "AI_MAX_RETRIES",
]


def _clean(monkeypatch) -> None:
    for name in RELEVANT_ENV:
        monkeypatch.delenv(name, raising=False)


def test_defaults_match_configuration_contract(monkeypatch) -> None:
    _clean(monkeypatch)
    settings = Settings(_env_file=None)
    assert settings.mimo_base_url == "https://token-plan-cn.xiaomimimo.com/v1"
    assert settings.mimo_asr_model == "mimo-v2.5-asr"
    assert settings.mimo_tts_model == "mimo-v2.5-tts"
    assert settings.mimo_llm_model == "mimo-v2.5"
    assert settings.deepseek_base_url == "https://api.deepseek.com"
    assert settings.deepseek_default_model == "deepseek-v4-pro"
    assert settings.openai_base_url == "https://api.openai.com/v1"
    assert settings.openai_default_model == "gpt-5"
    assert settings.ai_max_retries == 2


def test_canonical_env_names_are_mapped(monkeypatch) -> None:
    _clean(monkeypatch)
    monkeypatch.setenv("MIMO_BASE_URL", "https://example.mimo/v1")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://example.deepseek")
    monkeypatch.setenv("DEEPSEEK_DEFAULT_MODEL", "model-x")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.openai/v1")
    monkeypatch.setenv("OPENAI_DEFAULT_MODEL", "model-y")
    settings = Settings(_env_file=None)
    assert settings.mimo_base_url == "https://example.mimo/v1"
    assert settings.deepseek_base_url == "https://example.deepseek"
    assert settings.deepseek_default_model == "model-x"
    assert settings.openai_base_url == "https://example.openai/v1"
    assert settings.openai_default_model == "model-y"


def test_legacy_env_names_remain_supported(monkeypatch) -> None:
    _clean(monkeypatch)
    monkeypatch.setenv("MIMO_API_BASE_URL", "https://legacy.mimo/v1")
    monkeypatch.setenv("DEEPSEEK_API_BASE_URL", "https://legacy.deepseek")
    monkeypatch.setenv("DEEPSEEK_MODEL", "legacy-ds")
    monkeypatch.setenv("OPENAI_API_BASE_URL", "https://legacy.openai/v1")
    monkeypatch.setenv("OPENAI_MODEL", "legacy-oa")
    settings = Settings(_env_file=None)
    assert settings.mimo_base_url == "https://legacy.mimo/v1"
    assert settings.deepseek_base_url == "https://legacy.deepseek"
    assert settings.deepseek_default_model == "legacy-ds"
    assert settings.openai_base_url == "https://legacy.openai/v1"
    assert settings.openai_default_model == "legacy-oa"
