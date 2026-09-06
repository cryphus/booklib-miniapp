from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.errors import NotFoundError

router = APIRouter(prefix="/legal", tags=["legal"])

DRAFT_NOTICE = (
    "Черновик. Итоговый юридический текст будет добавлен перед публичным релизом."
)

# Draft wording taken from the product design. It is served with is_placeholder=True so
# the client always labels it as a draft: it is not a finished legal document, and no
# additional legally binding text is generated here.
PRIVACY = """1. Какие данные мы храним
Remarka хранит книги, цитаты и заметки, которые вы добавили, а также идентификатор вашего Telegram-аккаунта для входа.

2. Где хранятся данные
Данные размещаются на серверах Remarka. Telegram используется только как способ авторизации и не получает содержимое вашей библиотеки.

3. AI-обработка
Для ответа на ваш вопрос AI использует только сохранённые вами записи. Ответ всегда сопровождается списком источников.

4. Удаление данных
Вы можете удалить отдельные записи или весь аккаунт. Удаление аккаунта необратимо."""

TERMS = """1. Использование сервиса
Remarka — личный сервис для сохранения цитат и заметок. Вы отвечаете за содержимое, которое добавляете в библиотеку.

2. Права на контент
Сохранённые вами материалы остаются вашими. Мы не публикуем их и не передаём третьим лицам.

3. Premium и оплата
Premium оплачивается через Telegram Stars. Стоимость и лимиты могут меняться, о чём мы сообщим заранее.

4. Ограничения
Запрещено использовать сервис для нарушения закона или прав других людей."""

DOCUMENTS = {
    "privacy": {
        "title": "Политика конфиденциальности",
        "content": PRIVACY,
        "updated_at": "1 сентября 2026",
    },
    "terms": {
        "title": "Пользовательское соглашение",
        "content": TERMS,
        "updated_at": "Версия 1.0",
    },
}


class LegalDocument(BaseModel):
    slug: str
    title: str
    updated_at: str | None = None
    is_placeholder: bool
    content: str


def _document(slug: str) -> LegalDocument:
    data = DOCUMENTS.get(slug)
    if data is None:
        raise NotFoundError("Document not found", code="DOCUMENT_NOT_FOUND")
    return LegalDocument(
        slug=slug,
        title=data["title"],
        updated_at=data["updated_at"],
        is_placeholder=True,
        content=data["content"],
    )


@router.get("/privacy", response_model=LegalDocument)
async def privacy_policy() -> LegalDocument:
    return _document("privacy")


@router.get("/terms", response_model=LegalDocument)
async def terms_of_service() -> LegalDocument:
    return _document("terms")
