import httpx
from loguru import logger


async def check_ollama_alive(base_url: str, timeout: float = 2.0) -> bool:
    """Проверить, отвечает ли Ollama по указанному base_url."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as http:
            r = await http.get(f"{base_url}/api/tags")
            return r.status_code == 200
    except httpx.HTTPError as e:
        logger.debug("Проверка доступности Ollama не удалась: {}", e)
        return False
