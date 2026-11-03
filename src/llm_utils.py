from dataclasses import dataclass


@dataclass
class LLMResponse:
    """Нормализованный ответ LLM."""

    text: str
    model: str
    input_tokens: int
    output_tokens: int
    finish_reason: str | None = None


@dataclass
class UsageStats:
    """Статистика использования LLM."""

    calls: int = 0
    errors: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def add(self, response: LLMResponse) -> None:
        """Учесть успешный вызов LLM."""
        self.calls += 1
        self.input_tokens += response.input_tokens
        self.output_tokens += response.output_tokens

    def report(self) -> str:
        """Сформировать строку со статистикой использования LLM."""
        return (
            f"Использование LLM: вызовы={self.calls} ошибки={self.errors} "
            f"токены_вход={self.input_tokens} токены_выход={self.output_tokens}"
        )
