"""All AI prompt text lives here so it can be tuned without touching business logic."""

from __future__ import annotations

SYSTEM_PROMPT = """Ты — Remarka AI, помощник по личной библиотеке пользователя.

Правила, которые нельзя нарушать:
1. Ты отвечаешь ТОЛЬКО на основании материалов, переданных тебе в блоке КОНТЕКСТ.
2. Не утверждай, что пользователь сохранял информацию, которой нет в контексте.
3. Если контекста недостаточно — прямо скажи, что в библиотеке не найдено достаточно информации.
4. Не придумывай цитаты и не меняй смысл существующих цитат.
5. Каждый содержательный вывод должен опираться на один или несколько переданных источников.
6. Отвечай на языке вопроса пользователя, естественно и по делу, без воды.

Формат ответа — строго JSON без markdown-обёртки:
{"answer": "текст ответа", "source_ids": ["<id источника>", ...]}

В source_ids можно указывать ТОЛЬКО те id, которые встречаются в блоке КОНТЕКСТ.
Если подходящих источников нет — верни пустой список и скажи об этом в answer."""

NOT_ENOUGH_CONTEXT_ANSWER = (
    "В вашей библиотеке пока не нашлось записей, которые отвечали бы на этот вопрос. "
    "Попробуйте переформулировать вопрос или добавить больше цитат и заметок."
)


def build_embedding_document(
    *,
    entry_type: str,
    book_title: str | None,
    authors: list[str],
    chapter: str | None,
    page: str | None,
    tags: list[str],
    content: str,
    personal_note: str | None,
) -> str:
    """The text that gets embedded. Book/chapter/tags are included so that retrieval
    can match on them, not just on the body of the entry."""
    lines: list[str] = []
    if book_title:
        lines.append(f"Книга: {book_title}")
    if authors:
        lines.append(f"Автор: {', '.join(authors)}")
    if chapter:
        lines.append(f"Глава: {chapter}")
    if page:
        lines.append(f"Страница: {page}")
    if tags:
        lines.append(f"Теги: {', '.join(tags)}")

    if entry_type == "quote":
        lines.append("")
        lines.append("Цитата:")
        lines.append(content)
        if personal_note:
            lines.append("")
            lines.append("Моя заметка:")
            lines.append(personal_note)
    else:
        lines.append("")
        lines.append("Моя мысль:")
        lines.append(content)

    return "\n".join(lines).strip()


def build_context_block(sources: list[dict]) -> str:
    """Renders retrieved entries for the LLM. The [source:<uuid>] marker is what the
    model must cite, and the backend re-checks every id it returns."""
    blocks: list[str] = []
    for item in sources:
        header = f"[source:{item['entry_id']}]"
        meta: list[str] = []
        if item.get("book_title"):
            meta.append(f"Книга: {item['book_title']}")
        if item.get("authors"):
            meta.append(f"Автор: {', '.join(item['authors'])}")
        if item.get("chapter"):
            meta.append(f"Глава: {item['chapter']}")
        if item.get("page"):
            meta.append(f"Страница: {item['page']}")
        if item.get("tags"):
            meta.append(f"Теги: {', '.join(item['tags'])}")
        kind = "Цитата" if item.get("entry_type") == "quote" else "Мысль пользователя"
        body = item.get("content", "")
        note = item.get("personal_note")
        block = f"{header}\n" + "\n".join(meta)
        block += f"\n{kind}:\n{body}"
        if note:
            block += f"\nЗаметка пользователя:\n{note}"
        blocks.append(block)
    return "\n\n---\n\n".join(blocks)


def build_user_prompt(question: str, context_block: str, history: list[str] | None = None) -> str:
    parts: list[str] = []
    if history:
        parts.append("ПРЕДЫДУЩИЙ ДИАЛОГ:\n" + "\n".join(history))
    parts.append("КОНТЕКСТ (записи из личной библиотеки пользователя):\n\n" + context_block)
    parts.append(f"ВОПРОС ПОЛЬЗОВАТЕЛЯ:\n{question}")
    return "\n\n".join(parts)


def build_conversation_title(question: str, max_length: int = 60) -> str:
    title = " ".join(question.strip().split())
    if len(title) <= max_length:
        return title
    return title[: max_length - 1].rstrip() + "…"
