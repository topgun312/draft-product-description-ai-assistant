from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse, StreamingResponse
from loguru import logger

from src.api.deps import get_product_card_service
from src.core.exceptions import (
    InvalidLLMResponseError,
    LLMError,
    LLMUnavailableError,
)
from src.core.models import GeneratedCard, ProductInput
from src.services.product_card import ProductCardService
from src.utils.markdown import card_to_markdown

router = APIRouter(prefix="/generate", tags=["generate"])

_STREAM_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def _map_llm_exception(e: Exception) -> HTTPException:
    """Единый маппинг LLM-исключений в HTTPException."""
    if isinstance(e, LLMUnavailableError):
        return HTTPException(status_code=503, detail=str(e))
    if isinstance(e, (InvalidLLMResponseError, LLMError)):
        return HTTPException(status_code=502, detail=str(e))
    return HTTPException(status_code=500, detail="Внутренняя ошибка сервиса")


@router.post("", response_model=GeneratedCard)
async def generate(
    product: ProductInput,
    service: ProductCardService = Depends(get_product_card_service),
) -> GeneratedCard:
    """Сгенерировать карточку одного товара (JSON)."""
    try:
        return await service.generate_card(product)
    except Exception as e:
        raise _map_llm_exception(e) from e


@router.post("/batch", response_model=list[GeneratedCard])
async def generate_batch(
    products: list[ProductInput],
    service: ProductCardService = Depends(get_product_card_service),
) -> list[GeneratedCard]:
    """Сгенерировать карточки нескольких товаров параллельно."""
    if not products:
        raise HTTPException(status_code=400, detail="Пустой список товаров")
    try:
        return await service.generate_cards_batch(products)
    except Exception as e:
        raise _map_llm_exception(e) from e


@router.post("/markdown", response_class=PlainTextResponse)
async def generate_markdown(
    product: ProductInput,
    service: ProductCardService = Depends(get_product_card_service),
) -> str:
    """Сгенерировать карточку одного товара (Markdown)."""
    try:
        card = await service.generate_card(product)
    except Exception as e:
        raise _map_llm_exception(e) from e
    return card_to_markdown(card)


@router.post("/stream")
async def generate_stream(
    product: ProductInput,
    service: ProductCardService = Depends(get_product_card_service),
) -> StreamingResponse:
    """Потоково сгенерировать карточку товара.

    Ответ отдаётся как `text/plain`: фрагменты JSON идут по мере генерации,
    а при склейке образуют итоговый JSON карточки.
    """
    logger.info("Запрос потоковой генерации: '{}'", product.name)

    async def source() -> AsyncIterator[str]:
        try:
            async for chunk in service.generate_card_stream(product):
                yield chunk
        except Exception as e:
            logger.error("Ошибка потоковой генерации '{}': {}", product.name, e)
            raise

    return StreamingResponse(
        source(),
        media_type="text/plain; charset=utf-8",
        headers=_STREAM_HEADERS,
    )
