from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BASE_DIR = Path(__file__).resolve().parent.parent.parent


class LLMSettings(BaseSettings):
    """Настройки LLM-провайдеров и приложения."""

    model_config = SettingsConfigDict(
        env_file=_BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None

    default_provider: str = "ollama"
    default_model: str = "llama3.2"
    max_tokens: int = 2048
    request_timeout: int = 120

    ollama_base_url: str = "http://localhost:11434"

    log_level: str = "INFO"
    log_file: str | None = None

    @field_validator("default_provider")
    @classmethod
    def _check_provider(cls, v: str) -> str:
        """Проверить, что провайдер по умолчанию допустим."""
        allowed = {"openai", "anthropic", "ollama"}
        if v not in allowed:
            raise ValueError(f"default_provider должен быть одним из {allowed}")
        return v

    def get_key(self, provider: str) -> str:
        """Вернуть API-ключ для указанного провайдера."""
        if provider == "ollama":
            return "ollama"
        key_map = {
            "openai": self.openai_api_key,
            "anthropic": self.anthropic_api_key,
        }
        secret = key_map.get(provider)
        if secret is None:
            raise ValueError(f"API-ключ для '{provider}' не настроен")
        return secret.get_secret_value()

    def validate_keys(self) -> list[str]:
        """Вернуть список провайдеров, для которых настроены ключи."""
        available: list[str] = []
        if self.openai_api_key:
            available.append("openai")
        if self.anthropic_api_key:
            available.append("anthropic")
        available.append("ollama")
        return available


settings = LLMSettings()
