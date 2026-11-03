from __future__ import annotations

import asyncio
from typing import AsyncIterator

from loguru import logger

from src.core.exceptions import LLMError
from src.core.models import GeneratedCard, ProductInput
from src.services.llm_client import UnifiedLLMClient
from src.services.prompts import SYSTEM_PROMPT, build_user_prompt
from src.utils.json_parser import parse_llm_json
from src.utils.product_card import (
    normalize_card_limits,
    post_validate_card,
    validate_card,
)

MAX_ATTEMPTS = 3


def _build_fix_prompt(issues: list[str]) -> str:
    """Сообщение модели с перечнем нарушений для повторной генерации."""
    problems = "\n".join(f"- {issue}" for issue in issues)
    return (
        "Предыдущий вариант карточки не соответствует требованиям:\n"
        f"{problems}\n\n"
        "Сгенерируй карточку заново, исправив все нарушения. "
        "Используй только данные из исходного запроса, не добавляй "
        "характеристики, которых нет во входных данных. "
        "Верни только валидный JSON."
    )


class ProductCardService:
    """Сервис генерации карточек товаров."""

    def __init__(self, llm: UnifiedLLMClient) -> None:
        """Создать сервис с указанным LLM-клиентом."""
        self.llm = llm

    async def generate_card(self, product: ProductInput) -> GeneratedCard:
        """Сгенерировать карточку одного товара."""
        user_prompt = build_user_prompt(product.model_dump())

        card: GeneratedCard | None = None
        issues: list[str] = []

        for attempt in range(1, MAX_ATTEMPTS + 1):
            messages = [{"role": "user", "content": user_prompt}]
            if issues:
                messages.append({"role": "user", "content": _build_fix_prompt(issues)})

            response = await self.llm.chat(
                messages=messages,
                system=SYSTEM_PROMPT,
                temperature=0.2,
                max_tokens=2000,
            )

            data = parse_llm_json(response.text)
            card = post_validate_card(GeneratedCard(**data), product)
            issues = validate_card(card, product)

            if not issues:
                return card

            logger.warning(
                "Попытка {}/{}: карточка не прошла проверку: {}",
                attempt,
                MAX_ATTEMPTS,
                "; ".join(issues),
            )

        logger.warning(
            "Не удалось выполнить все требования за {} попытки: {}. "
            "Применяем детерминированную нормализацию.",
            MAX_ATTEMPTS,
            "; ".join(issues),
        )
        assert card is not None
        return normalize_card_limits(card, product)

    async def generate_card_stream(self, product: ProductInput) -> AsyncIterator[str]:
        """Потоково сгенерировать карточку товара (сырые токены LLM)."""
        user_prompt = build_user_prompt(product.model_dump())
        messages = [{"role": "user", "content": user_prompt}]

        logger.debug("Старт потоковой генерации для товара '{}'", product.name)
        async for chunk in self.llm.stream(
            messages=messages,
            system=SYSTEM_PROMPT,
            temperature=0.2,
            max_tokens=2000,
        ):
            yield chunk
        logger.debug("Потоковая генерация для товара '{}' завершена", product.name)

    async def generate_cards_batch(
        self, products: list[ProductInput]
    ) -> list[GeneratedCard]:
        """Сгенерировать карточки для нескольких товаров параллельно."""
        results = await asyncio.gather(
            *[self.generate_card(p) for p in products],
            return_exceptions=True,
        )

        out: list[GeneratedCard] = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                logger.error("Товар #{} ({}): {}", i, products[i].name, r)
                raise LLMError(f"Ошибка генерации для товара #{i}: {r}")
            out.append(r)
        return out
