from __future__ import annotations

import re

from loguru import logger

from src.core.models import GeneratedCard, ProductInput, SpecItem

MISSING_VALUE = "данных нет"
MAX_TITLE_LEN = 70
MIN_DESC_LEN = 800
MAX_DESC_LEN = 1200
MIN_QUERIES = 3
MAX_QUERIES = 5

_MEASURE_RE = re.compile(
    r"\d+(?:[.,]\d+)?\s*"
    r"(?:МПа|кПа|Па|бар|мм|см|кВт|Вт|кВ|В|мА|А|кГц|МГц|Гц|кг|г|м|°C|°С|%)",
    re.IGNORECASE,
)
_SENTENCE_RE = re.compile(r"(?<=[.!?…])\s+")


def _norm_key(value: str) -> str:
    """Нормализовать ключ характеристики для сравнения."""
    return re.sub(r"[\s:：]+", "", value).strip().casefold().replace("ё", "е")


def _norm_text(value: str) -> str:
    """Нормализовать текст для сравнения технических значений."""
    value = value.casefold().replace("ё", "е")
    value = re.sub(r"[–—−]", "-", value)
    value = value.replace(",", ".")
    return re.sub(r"\s+", "", value)


def _unique(values: list[str]) -> list[str]:
    """Убрать дубликаты строк с сохранением исходного порядка."""
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _allowed_measurements(product: ProductInput) -> str:
    """Собрать все допустимые технические значения из входных данных."""
    parts = [product.name, product.manufacturer, product.description or ""]
    for key, value in product.specs.items():
        parts.extend((key, value))
    return _norm_text(" ".join(parts))


def _measurements(text: str) -> list[str]:
    """Извлечь из текста технические значения с единицами измерения."""
    return [match.group(0).strip() for match in _MEASURE_RE.finditer(text)]


def _unsupported_in_text(text: str, allowed: str) -> list[str]:
    """Найти в тексте значения, которых нет среди допустимых."""
    return [value for value in _measurements(text) if _norm_text(value) not in allowed]


def _card_texts(card: GeneratedCard) -> list[str]:
    """Собрать все текстовые поля карточки."""
    return [
        card.seo_title,
        card.seo_description,
        card.commercial_block,
        *card.search_queries,
        *(f"{spec.key} {spec.value}" for spec in card.key_specs),
    ]


def find_unsupported_measurements(
    card: GeneratedCard, product: ProductInput
) -> list[str]:
    """Найти технические значения, которых нет во входных данных."""
    allowed = _allowed_measurements(product)
    unsupported: set[str] = set()
    for text in _card_texts(card):
        unsupported.update(_unsupported_in_text(text, allowed))
    return sorted(unsupported)


def validate_card(card: GeneratedCard, product: ProductInput) -> list[str]:
    """Вернуть список нарушений требований к карточке."""
    issues: list[str] = []

    title_len = len(card.seo_title.strip())
    if not title_len:
        issues.append("seo_title пустой")
    elif title_len > MAX_TITLE_LEN:
        issues.append(
            f"seo_title длиннее {MAX_TITLE_LEN} символов (сейчас {title_len})"
        )

    desc_len = len(card.seo_description.strip())
    if not (MIN_DESC_LEN <= desc_len <= MAX_DESC_LEN):
        issues.append(
            f"seo_description должен быть {MIN_DESC_LEN}–{MAX_DESC_LEN} "
            f"символов (сейчас {desc_len})"
        )

    queries = [q for q in card.search_queries if q.strip()]
    if not (MIN_QUERIES <= len(queries) <= MAX_QUERIES):
        issues.append(
            f"search_queries должно быть от {MIN_QUERIES} до {MAX_QUERIES} "
            f"(сейчас {len(queries)})"
        )

    unsupported = find_unsupported_measurements(card, product)
    if unsupported:
        issues.append("выдуманные технические значения: " + ", ".join(unsupported))

    if not card.commercial_block.strip():
        issues.append("commercial_block пустой")

    return issues


def post_validate_card(card: GeneratedCard, product: ProductInput) -> GeneratedCard:
    """Привести карточку в соответствие с входными данными."""
    input_specs = {_norm_key(key): (key, value) for key, value in product.specs.items()}
    field_values = {
        _norm_key("Производитель"): ("Производитель", product.manufacturer),
        _norm_key("Название"): ("Название", product.name),
        _norm_key("Наименование"): ("Наименование", product.name),
        _norm_key("Модель"): ("Модель", product.name),
    }
    known_specs = {**field_values, **input_specs}
    seen_keys: set[str] = set()
    cleaned: list[SpecItem] = []

    for spec in card.key_specs:
        key = _norm_key(spec.key)
        if key in known_specs:
            canonical_key, canonical_value = known_specs[key]
            if spec.value.strip() != canonical_value.strip():
                logger.warning(
                    "Модель исказила значение '{}': '{}' -> '{}'",
                    spec.key,
                    spec.value,
                    canonical_value,
                )
                spec.value = canonical_value
            if key in seen_keys:
                continue
            spec.key = canonical_key
            cleaned.append(spec)
            seen_keys.add(key)
        else:
            if spec.value.strip() != MISSING_VALUE:
                logger.warning(
                    "Модель выдумала характеристику '{}' — заменяем на '{}'",
                    spec.key,
                    MISSING_VALUE,
                )
                spec.value = MISSING_VALUE
            if key in seen_keys:
                continue
            cleaned.append(spec)
            seen_keys.add(key)
            if spec.key not in card.missing_fields:
                card.missing_fields.append(spec.key)

    for key, (canonical_key, canonical_value) in input_specs.items():
        if key not in seen_keys:
            cleaned.append(SpecItem(key=canonical_key, value=canonical_value))
            seen_keys.add(key)

    card.key_specs = cleaned
    card.missing_fields = _unique(
        [
            field.strip()
            for field in card.missing_fields
            if field.strip()
            and field.strip().casefold()
            not in {MISSING_VALUE, "нет данных", "n/a", "-"}
        ]
    )
    return card


def _ensure_period(text: str) -> str:
    """Добавить точку в конце текста при необходимости."""
    text = text.strip()
    if text and text[-1] not in ".!?…":
        text += "."
    return text


def _strip_unsupported_sentences(text: str, allowed: str) -> str:
    """Удалить предложения с техническими значениями не из входных данных."""
    sentences = _SENTENCE_RE.split(text.strip())
    kept = [
        sentence
        for sentence in sentences
        if sentence.strip() and not _unsupported_in_text(sentence, allowed)
    ]
    return " ".join(kept).strip()


def _truncate_title(title: str, limit: int = MAX_TITLE_LEN) -> str:
    """Обрезать заголовок до лимита по границе слова."""
    title = title.strip()
    if len(title) <= limit:
        return title
    cut = title[:limit]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(" ,.;:-") or title[:limit]


def _truncate_description(text: str, limit: int = MAX_DESC_LEN) -> str:
    """Обрезать описание до лимита, по возможности по границе предложения."""
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    match = re.match(r"^.*[.!?…](?=\s|$)", cut, re.DOTALL)
    if match and len(match.group(0)) >= MIN_DESC_LEN:
        return match.group(0).strip()
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(" ,;:-")


def _padding_blocks(product: ProductInput, card: GeneratedCard) -> list[str]:
    """Собрать блоки текста для добора описания только из входных данных."""
    name = product.name
    manufacturer = product.manufacturer
    blocks: list[str] = []

    if product.description and product.description.strip():
        blocks.extend(
            _ensure_period(part)
            for part in _SENTENCE_RE.split(product.description.strip())
            if part.strip()
        )

    specs = list(product.specs.items())
    if specs:
        summary = ", ".join(f"{key} — {value}" for key, value in specs)
        blocks.append(f"Ключевые характеристики модели «{name}»: {summary}.")
        blocks.append(
            f"В технических характеристиках модели «{name}» указаны: {summary}."
        )
        for key, value in specs:
            blocks.append(f"Параметр «{key}» для модели «{name}» указан как {value}.")
            blocks.append(
                f"Модель «{name}» характеризуется параметром «{key}»: {value}."
            )
            blocks.append(
                f"Среди характеристик модели «{name}» — "
                f"«{key}» со значением {value}."
            )

    if card.commercial_block.strip():
        blocks.append(_ensure_period(card.commercial_block))

    if manufacturer:
        blocks.append(f"Производитель модели «{name}» — {manufacturer}.")
        blocks.append(f"Модель «{name}» выпускается производителем {manufacturer}.")

    if card.missing_fields:
        blocks.append("Требуют уточнения: " + ", ".join(card.missing_fields) + ".")
        blocks.append(
            "Для полного описания не хватает данных: "
            + ", ".join(card.missing_fields)
            + "."
        )

    blocks.append(
        f"В карточке товара «{name}» приведены характеристики, "
        "необходимые для подбора оборудования."
    )
    blocks.append(
        f"Описание модели «{name}» включает сведения о назначении "
        "и технических параметрах."
    )

    return blocks


def _pad_description(text: str, product: ProductInput, card: GeneratedCard) -> str:
    """Добрать описание до минимальной длины блоками из входных данных."""
    text = text.strip()
    if len(text) >= MIN_DESC_LEN:
        return text

    blocks = _padding_blocks(product, card)
    max_reuse = 2
    text_norm = _norm_text(text)
    counts: dict[str, int] = {
        _norm_text(block): max_reuse
        for block in blocks
        if _norm_text(block) in text_norm
    }
    index = 0
    limit = len(blocks) * max_reuse if blocks else 0
    attempts = 0
    while len(text) < MIN_DESC_LEN and attempts < limit:
        attempts += 1
        block = blocks[index % len(blocks)]
        index += 1
        normalized = _norm_text(block)
        used_count = counts.get(normalized, 0)
        if used_count >= max_reuse:
            continue
        counts[normalized] = used_count + 1
        text = f"{text} {block}".strip() if text else block

    return text


def _ensure_queries(queries: list[str], product: ProductInput) -> list[str]:
    """Довести количество поисковых запросов до минимального значения."""
    queries = _unique([query.strip() for query in queries if query.strip()])
    candidates = [
        product.name,
        f"{product.name} {product.manufacturer}",
        f"{product.manufacturer} {product.name}",
        f"{product.name} характеристики",
    ]
    for candidate in candidates:
        if len(queries) >= MIN_QUERIES:
            break
        if candidate and candidate not in queries:
            queries.append(candidate)
    return queries[:MAX_QUERIES]


def normalize_card_limits(card: GeneratedCard, product: ProductInput) -> GeneratedCard:
    """Детерминированно привести карточку к лимитам ТЗ."""
    allowed = _allowed_measurements(product)

    card.seo_title = _truncate_title(
        _strip_unsupported_sentences(card.seo_title, allowed)
    )
    if not card.seo_title:
        card.seo_title = _truncate_title(product.name)

    card.seo_description = _strip_unsupported_sentences(card.seo_description, allowed)
    card.commercial_block = _strip_unsupported_sentences(card.commercial_block, allowed)
    if not card.commercial_block.strip():
        description = (product.description or "").strip()
        if description:
            card.commercial_block = _ensure_period(
                f"{product.name} от {product.manufacturer}: {description}"
            )
        else:
            card.commercial_block = _ensure_period(
                f"{product.name} — модель производителя {product.manufacturer}"
            )
    card.search_queries = [
        query
        for query in card.search_queries
        if query.strip() and not _unsupported_in_text(query, allowed)
    ]

    card.seo_description = _pad_description(card.seo_description, product, card)
    card.seo_description = _truncate_description(card.seo_description)

    card.search_queries = _ensure_queries(card.search_queries, product)

    return card
