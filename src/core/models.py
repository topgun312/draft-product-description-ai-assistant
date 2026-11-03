from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ProductInput(BaseModel):
    """Входные данные товара."""

    name: str
    manufacturer: str
    specs: dict[str, str] = Field(default_factory=dict)
    description: Optional[str] = ""

    @field_validator("name", "manufacturer")
    @classmethod
    def _not_empty(cls, v: str) -> str:
        """Проверить, что обязательное строковое поле не пустое."""
        if not v.strip():
            raise ValueError("Поле не может быть пустым")
        return v.strip()


class SpecItem(BaseModel):
    """Одна характеристика в карточке товара."""

    key: str
    value: str


class GeneratedCard(BaseModel):
    """Сгенерированная карточка товара."""

    seo_title: str
    seo_description: str
    key_specs: list[SpecItem]
    search_queries: list[str]
    commercial_block: str
    missing_fields: list[str] = Field(default_factory=list)
