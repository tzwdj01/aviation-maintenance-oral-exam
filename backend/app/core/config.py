from functools import lru_cache

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    database_url: str = "sqlite:///./aviation_oral_exam.db"
    api_v1_prefix: str = "/api/v1"
    enable_dev_provider_test: bool = False

    # Canonical env names per docs/CONFIGURATION.md; legacy names remain supported as aliases.
    mimo_base_url: str | None = Field(
        default="https://token-plan-cn.xiaomimimo.com/v1",
        validation_alias=AliasChoices("MIMO_BASE_URL", "MIMO_API_BASE_URL"),
    )
    mimo_api_key: SecretStr | None = None
    mimo_asr_model: str = "mimo-v2.5-asr"
    mimo_tts_model: str = "mimo-v2.5-tts"
    mimo_voicedesign_enabled: bool = False
    mimo_voiceclone_enabled: bool = False
    mimo_asr_language: str = "auto"
    mimo_tts_voice: str = "mimo_default"
    mimo_tts_style_prompt: str = "请使用清晰、自然、专业的中文口试考官语气。"
    speech_render_profile_version: str = "render-v1"
    mimo_llm_model: str = "mimo-v2.5"

    # Media / audio artifacts (docs/CONFIGURATION.md §1)
    media_storage_dir: str = "./media"
    media_max_size_bytes: int = Field(default=20 * 1024 * 1024, gt=0)
    media_allowed_mime_types: list[str] = Field(
        default_factory=lambda: ["audio/wav", "audio/mpeg", "audio/mp3"]
    )
    media_max_duration_seconds: int = Field(default=120, gt=0)
    media_access_url_ttl_seconds: int = Field(default=3600, gt=0)
    media_url_secret: SecretStr | None = None

    deepseek_base_url: str = Field(
        default="https://api.deepseek.com",
        validation_alias=AliasChoices("DEEPSEEK_BASE_URL", "DEEPSEEK_API_BASE_URL"),
    )
    deepseek_api_key: SecretStr | None = None
    deepseek_default_model: str = Field(
        default="deepseek-v4-pro", validation_alias=AliasChoices("DEEPSEEK_DEFAULT_MODEL", "DEEPSEEK_MODEL")
    )
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        validation_alias=AliasChoices("OPENAI_BASE_URL", "OPENAI_API_BASE_URL"),
    )
    openai_api_key: SecretStr | None = None
    openai_default_model: str = Field(
        default="gpt-5", validation_alias=AliasChoices("OPENAI_DEFAULT_MODEL", "OPENAI_MODEL")
    )

    ai_connect_timeout_seconds: float = Field(default=10, gt=0)
    ai_request_timeout_seconds: float = Field(default=60, gt=0)
    ai_max_retries: int = Field(default=2, ge=0, le=5)


@lru_cache
def get_settings() -> Settings:
    return Settings()
