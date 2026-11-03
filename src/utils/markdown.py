from src.core.models import GeneratedCard


def card_to_markdown(card: GeneratedCard) -> str:
    """Сериализовать карточку в Markdown для копирования контент-менеджером."""
    specs = "\n".join(f"- **{s.key}**: {s.value}" for s in card.key_specs)
    queries = "\n".join(f"- {q}" for q in card.search_queries)
    missing = (
        "\n".join(f"- {m}" for m in card.missing_fields)
        if card.missing_fields
        else "_нет_"
    )

    return (
        f"# {card.seo_title}\n\n"
        f"## SEO-описание\n\n{card.seo_description}\n\n"
        f"## Характеристики\n\n{specs}\n\n"
        f"## Поисковые запросы\n\n{queries}\n\n"
        f"## Коммерческий блок\n\n{card.commercial_block}\n\n"
        f"## Требует уточнения\n\n{missing}\n"
    )
