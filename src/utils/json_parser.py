from __future__ import annotations

import json
import re
from typing import Any

from loguru import logger

from src.core.exceptions import InvalidLLMResponseError

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def extract_json(raw: str) -> str:
    """Достать JSON-блок из ответа модели."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        raw = raw.strip()

    match = _JSON_BLOCK_RE.search(raw)
    if match:
        return match.group(0)
    return raw


def parse_llm_json(raw: str) -> dict[str, Any]:
    """Распарсить JSON-ответ LLM в dict. Кидает InvalidLLMResponseError."""
    cleaned = extract_json(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error(
            "Невалидный JSON от LLM: {}\nСырой ответ (первые 500 символов): {}",
            e,
            raw[:500],
        )
        raise InvalidLLMResponseError(f"LLM вернула невалидный JSON: {e}") from e
