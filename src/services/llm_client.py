from __future__ import annotations

import time
from typing import AsyncIterator

import anthropic
import openai
from loguru import logger

from src.core.exceptions import LLMError, LLMUnavailableError
from src.core.settings import LLMSettings
from src.llm_utils import LLMResponse, UsageStats


class UnifiedLLMClient:
    """Единый клиент для работы с любым LLM-провайдером.

    Поддерживаются: Anthropic, OpenAI, Ollama.
    """

    def __init__(self, settings: LLMSettings) -> None:
        """Создать клиент с указанными настройками."""
        self.settings = settings
        self.usage = UsageStats()
        self._anthropic: anthropic.AsyncAnthropic | None = None
        self._openai: openai.AsyncOpenAI | None = None
        self._ollama: openai.AsyncOpenAI | None = None

    def _get_anthropic(self) -> anthropic.AsyncAnthropic:
        """Лениво создать клиент Anthropic."""
        if self._anthropic is None:
            self._anthropic = anthropic.AsyncAnthropic(
                api_key=self.settings.get_key("anthropic"),
                max_retries=3,
                timeout=float(self.settings.request_timeout),
            )
        return self._anthropic

    def _get_openai(self) -> openai.AsyncOpenAI:
        """Лениво создать клиент OpenAI."""
        if self._openai is None:
            self._openai = openai.AsyncOpenAI(
                api_key=self.settings.get_key("openai"),
                max_retries=3,
                timeout=float(self.settings.request_timeout),
            )
        return self._openai

    def _get_ollama(self) -> openai.AsyncOpenAI:
        """Лениво создать OpenAI-совместимый клиент Ollama."""
        if self._ollama is None:
            self._ollama = openai.AsyncOpenAI(
                api_key=self.settings.get_key("ollama"),
                base_url=f"{self.settings.ollama_base_url}/v1",
                max_retries=1,
                timeout=float(self.settings.request_timeout),
            )
        return self._ollama

    def _detect_provider(self, model: str) -> str:
        """Определить провайдера по названию модели."""

        if model.startswith("claude"):
            return "anthropic"
        elif (
            model.startswith("gpt") or model.startswith("o1") or model.startswith("o3")
        ):
            return "openai"
        elif (
            model.startswith("llama")
            or model.startswith("mistral")
            or model.startswith("qwen")
        ):
            return "ollama"
        return self.settings.default_provider

    def _resolve_provider(self, model: str, provider: str | None = None) -> str:
        """Вернуть явно заданный провайдер или определить его по модели."""
        return provider or self._detect_provider(model)

    def _ensure_provider_available(self, provider: str) -> None:
        """Проверить, что провайдер известен и для него настроен ключ."""
        if provider not in ("openai", "anthropic", "ollama"):
            raise LLMError(f"Неизвестный провайдер: {provider}")
        try:
            self.settings.get_key(provider)
        except ValueError as e:
            raise LLMUnavailableError(str(e)) from e

    def _normalize_error(self, exc: Exception, provider: str) -> LLMError:
        """Привести исключения SDK/сети к доменным ошибкам LLM."""
        if isinstance(
            exc,
            (
                openai.APIConnectionError,
                openai.APITimeoutError,
                anthropic.APIConnectionError,
                anthropic.APITimeoutError,
                ConnectionError,
                TimeoutError,
            ),
        ):
            return LLMUnavailableError(f"Провайдер '{provider}' недоступен: {exc}")
        if isinstance(exc, (openai.AuthenticationError, anthropic.AuthenticationError)):
            return LLMUnavailableError(
                f"Провайдер '{provider}' отклонил ключ API: {exc}"
            )
        if isinstance(exc, (openai.APIStatusError, anthropic.APIStatusError)):
            return LLMError(f"Провайдер '{provider}' вернул ошибку API: {exc}")
        if isinstance(exc, (openai.APIError, anthropic.APIError)):
            return LLMError(f"Ошибка API провайдера '{provider}': {exc}")
        if isinstance(exc, ValueError):
            return LLMUnavailableError(str(exc))
        return LLMError(f"Ошибка LLM (провайдер={provider}): {exc}")

    async def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Отправить запрос выбранному провайдеру."""
        model = model or self.settings.default_model
        max_tokens = max_tokens or self.settings.max_tokens
        provider = self._detect_provider(model)

        time_start = time.monotonic()
        try:
            if provider == "anthropic":
                response = await self._chat_anthropic(
                    messages, model, system, temperature, max_tokens
                )
            elif provider in ("openai", "ollama"):
                response = await self._chat_openai(
                    messages, model, system, temperature, max_tokens, provider
                )
            else:
                raise LLMError(f"Неизвестный провайдер: {provider}")

            self.usage.add(response)
            elapsed = time.monotonic() - time_start
            logger.debug(
                "Вызов LLM: провайдер={} модель={} токены={}/{} время={:.2f}с",
                provider,
                response.model,
                response.input_tokens,
                response.output_tokens,
                elapsed,
            )

            return response
        except LLMError as e:
            self.usage.errors += 1
            logger.error("Ошибка LLM (провайдер={} модель={}): {}", provider, model, e)
            raise
        except Exception as e:
            self.usage.errors += 1
            logger.error("Ошибка LLM (провайдер={} модель={}): {}", provider, model, e)
            raise self._normalize_error(e, provider) from e

    async def _chat_anthropic(
        self,
        messages: list[dict],
        model: str,
        system: str,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        """Выполнить запрос к Anthropic."""
        r = await self._get_anthropic().messages.create(
            model=model,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=messages,
        )
        return LLMResponse(
            text=r.content[0].text,
            model=r.model,
            input_tokens=r.usage.input_tokens,
            output_tokens=r.usage.output_tokens,
            finish_reason=r.stop_reason,
        )

    async def _chat_openai(
        self,
        messages: list[dict],
        model: str,
        system: str,
        temperature: float,
        max_tokens: int,
        provider: str,
    ) -> LLMResponse:
        """Выполнить запрос к OpenAI-совместимому API (OpenAI или Ollama)."""
        client = {
            "openai": self._get_openai,
            "ollama": self._get_ollama,
        }[provider]()

        full_messages = (
            [{"role": "system", "content": system}] + messages if system else messages
        )
        r = await client.chat.completions.create(
            model=model,
            messages=full_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return LLMResponse(
            text=r.choices[0].message.content or "",
            model=r.model,
            input_tokens=r.usage.prompt_tokens if r.usage else 0,
            output_tokens=r.usage.completion_tokens if r.usage else 0,
            finish_reason=r.choices[0].finish_reason,
        )

    async def stream(
        self,
        messages: list[dict],
        model: str | None = None,
        system: str = "",
        provider: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """Потоково получить токены ответа от выбранного провайдера."""
        model = model or self.settings.default_model
        provider = self._resolve_provider(model, provider)
        self._ensure_provider_available(provider)

        max_tokens = max_tokens or self.settings.max_tokens

        try:
            if provider == "anthropic":
                client = self._get_anthropic()
                async with client.messages.stream(
                    model=model,
                    system=system,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                ) as s:
                    async for chunk in s.text_stream:
                        yield chunk
            elif provider in ("openai", "ollama"):
                oai_client = {
                    "openai": self._get_openai,
                    "ollama": self._get_ollama,
                }[provider]()

                msgs = (
                    [{"role": "system", "content": system}] + messages
                    if system
                    else messages
                )
                stream = await oai_client.chat.completions.create(
                    model=model,
                    messages=msgs,
                    stream=True,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                async for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
            else:
                raise LLMError(f"Неизвестный провайдер: {provider}")
        except LLMError:
            self.usage.errors += 1
            raise
        except Exception as e:
            self.usage.errors += 1
            logger.error(
                "Ошибка LLM stream (провайдер={} модель={}): {}", provider, model, e
            )
            raise self._normalize_error(e, provider) from e

    def print_usage(self) -> None:
        """Залогировать накопленную статистику использования LLM."""
        logger.info("Использование LLM: {}", self.usage.report())
