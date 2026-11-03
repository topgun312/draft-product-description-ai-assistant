class AppError(Exception):
    """Базовое исключение приложения."""


class LLMError(AppError):
    """Ошибка при обращении к LLM."""


class LLMUnavailableError(LLMError):
    """Провайдер недоступен (нет ключа / сервер не запущен)."""


class InvalidLLMResponseError(LLMError):
    """LLM вернула ответ, который не удалось распарсить."""
