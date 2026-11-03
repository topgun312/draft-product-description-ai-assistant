from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from src.api.deps import get_llm_client, get_settings
from src.api.routers import generate, health
from src.core.logging import setup_logging
from src.services.llm_checks import check_ollama_alive

_settings = get_settings()
setup_logging(level=_settings.log_level, log_file=_settings.log_file)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управлять жизненным циклом приложения и логировать состояние провайдеров."""
    settings = get_settings()
    logger.info(
        "Старт. Провайдер по умолчанию: {} / модель: {}",
        settings.default_provider,
        settings.default_model,
    )
    logger.info("Доступные провайдеры: {}", settings.validate_keys())

    provider = settings.default_provider
    alive = await check_ollama_alive(settings.ollama_base_url)
    if not alive:
        logger.warning(
            "Провайдер '{}' НЕ отвечает. Для ollama: запустите `ollama serve`.",
            provider,
        )
    else:
        logger.info("Провайдер '{}' доступен", provider)

    yield

    get_llm_client().print_usage()


app = FastAPI(
    title="Генератор карточек товаров с помощью ИИ",
    description=(
        "Сервис формирования черновиков карточек товаров на основе "
        "входных данных и выбранной LLM."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(generate.router)
