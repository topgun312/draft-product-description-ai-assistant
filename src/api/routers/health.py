from fastapi import APIRouter, Depends

from src.api.deps import get_settings
from src.core.settings import LLMSettings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(settings: LLMSettings = Depends(get_settings)) -> dict:
    """Проверить работоспособность сервиса и вернуть активные провайдеры."""
    return {
        "status": "ok",
        "default_provider": settings.default_provider,
        "default_model": settings.default_model,
        "available_providers": settings.validate_keys(),
    }
