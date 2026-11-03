from functools import lru_cache

from src.core.settings import LLMSettings, settings
from src.services.llm_client import UnifiedLLMClient
from src.services.product_card import ProductCardService


@lru_cache
def get_settings() -> LLMSettings:
    """Синглтон настроек."""
    return settings


@lru_cache
def get_llm_client() -> UnifiedLLMClient:
    """Синглтон LLM-клиента."""
    return UnifiedLLMClient(get_settings())


def get_product_card_service() -> ProductCardService:
    """Сервис генерации карточек."""
    return ProductCardService(get_llm_client())
