# Remarka

[![CI](https://github.com/cryphus/booklib-miniapp/actions/workflows/ci.yml/badge.svg)](https://github.com/cryphus/booklib-miniapp/actions/workflows/ci.yml)

Telegram Mini App для личной библиотеки: книги, цитаты, собственные мысли, теги, поиск
и AI-ассистент, который отвечает **только** на основании записей самого пользователя.

- [1. Что такое Remarka](#1-что-такое-remarka)
- [2. Архитектура](#2-архитектура)
- [3. Требования](#3-требования)
- [4. Переменные окружения](#4-переменные-окружения)
- [4a. Фронтенд](#4a-фронтенд)
- [5. Локальная разработка](#5-локальная-разработка)
- [6. Запуск через Docker](#6-запуск-через-docker)
- [6a. CI](#6a-ci)
- [7. Миграции базы данных](#7-миграции-базы-данных)
- [8. Настройка Telegram-бота](#8-настройка-telegram-бота)
- [9. Настройка Telegram Mini App](#9-настройка-telegram-mini-app)
- [10. Google Books](#10-google-books)
- [11. Open Library](#11-open-library)
- [12. AI-провайдер](#12-ai-провайдер)
- [13. Telegram Stars](#13-telegram-stars)
- [14. Заглушки платёжных провайдеров](#14-заглушки-платёжных-провайдеров)
- [15. Production checklist](#15-production-checklist)

---

## 1. Что такое Remarka

Пользователь добавляет книги (поиск по Google Books / Open Library или ручное создание),
сохраняет цитаты и собственные мысли, помечает их тегами и избранным, ищет по своей
библиотеке и задаёт вопросы AI. AI отвечает через RAG по личным записям и **обязан**
вернуть ссылки на конкретные записи-источники.

Telegram — только один из способов входа. Аккаунт живёт в нашей БД (`users` +
`user_identities`), поэтому позже к тому же `users.id` можно привязать email / Google /
Apple и выпустить нативные iOS/Android приложения.

## 2. Архитектура

```
Frontend (Telegram Mini App)
        │  REST /api/v1
        ▼
FastAPI  ──► api/v1/*        только валидация и HTTP
        ──► services/*       вся бизнес-логика
        ──► repositories/*   SQLAlchemy 2 (async)
        ▼
PostgreSQL 16 + pgvector + pg_trgm
```

Все внешние интеграции изолированы в `app/integrations/*` за интерфейсами:

| Интерфейс | Реализации |
|---|---|
| `BookProvider` | `GoogleBooksProvider`, `OpenLibraryProvider` (+ `BookSearchAggregator`) |
| `EmbeddingProvider` / `LLMProvider` | `OpenAICompatible*`, `Fake*` (тесты / офлайн) |
| `PaymentProvider` | `TelegramStarsPaymentProvider` (рабочий), `YooKassa` / `Platega` / `CryptoBot` (заглушки) |
| `StorageService` | `LocalStorageService` (Docker volume); S3/R2/MinIO подключаются без изменения бизнес-логики |
| `RateLimiterBackend` | `InMemoryRateLimiter`; интерфейс готов под Redis |

```
backend/
├── alembic/versions/0001_initial.py   схема + extensions vector, pg_trgm + индексы
├── app/
│   ├── core/          config, errors (единый формат), security (JWT), rate_limit, logging
│   ├── db/            base, session, типы (GUID / JSONB / pgvector с fallback)
│   ├── models/        users, books, entries, ai, billing
│   ├── schemas/       Pydantic DTO (вся валидация входа)
│   ├── repositories/  доступ к данным, каждый запрос ограничен user_id
│   ├── services/      auth, library, entry, tag, search, indexing, ai, billing, user
│   ├── integrations/  telegram, books, ai, payments
│   ├── api/v1/        роутеры
│   └── seed.py        dev-данные
└── tests/             83 теста (включая полный e2e-сценарий)
```

## 3. Требования

- Docker + Docker Compose (самый простой путь), **или**
- Python 3.12 и PostgreSQL 16 с расширениями `vector` и `pg_trgm`.

Node.js не нужен: фронтенд собирается без бандлера (см. [4a](#4a-фронтенд)).

## 4. Переменные окружения

Скопируйте `.env.example` в `.env` и заполните. Секретов в репозитории нет и быть не должно.

**Обязательные для полноценной работы:**

| Переменная | Зачем |
|---|---|
| `SECRET_KEY` | подпись session-токенов; в production приложение не стартует со значением по умолчанию |
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@host:5432/remarka` |
| `TELEGRAM_BOT_TOKEN` | проверка подписи initData **и** выставление счетов в Stars |
| `TELEGRAM_WEBHOOK_SECRET` | проверка входящих вебхуков (в production обязателен) |
| `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` | ответы AI |
| `EMBEDDING_API_KEY`, `EMBEDDING_BASE_URL`, `EMBEDDING_MODEL`, `EMBEDDING_DIM` | векторный индекс |
| `CORS_ORIGINS` | список разрешённых origin через запятую |

**Опциональные / с разумными значениями по умолчанию:** `GOOGLE_BOOKS_API_KEY` (поиск
работает и без ключа, но с более жёсткими квотами), `FREE_AI_REQUESTS_PER_MONTH=10`,
`PREMIUM_AI_REQUESTS_PER_MONTH=500`, `TELEGRAM_PREMIUM_PRICE_STARS`, `PREMIUM_PERIOD_DAYS`,
`UPLOAD_MAX_BYTES`, `AI_TOP_K`, `AI_MIN_RELEVANCE`, `AI_MAX_QUESTION_LENGTH`.

**Feature flags:** `ENABLE_TELEGRAM_STARS`, `ENABLE_YOOKASSA`, `ENABLE_PLATEGA`,
`ENABLE_CRYPTOBOT` — фронтенд узнаёт активные способы оплаты только из
`GET /api/v1/billing/providers`.

> `EMBEDDING_DIM` должен совпадать с размерностью модели (у `text-embedding-3-small` это
> 1536). Изменение размерности требует новой миграции колонки и переиндексации.

## 4a. Фронтенд

Источник истины — дизайн-канва `frontend/design/Remarka Mini App.dc.html`: 41 экран
в макете 390×844. Приложение реализует эти экраны один в один — цвета, радиусы, тени,
иконки и тексты взяты из канвы, а не придуманы заново.

**Стек: ES-модули без сборки.** В канве не было приложения — только статические артборды,
поэтому фреймворк выбирался с нуля. Дизайн — обычный HTML/CSS, приложение одностраничное
и мобильное, поэтому bundler не нужен: нет шага сборки, нет `node_modules`, отладка идёт
по тем же файлам, что лежат в репозитории.

```
frontend/
├── index.html              оболочка: шрифты, базовый CSS, telegram-web-app.js
├── devserver.py            статика для разработки с отключённым кэшем
├── Dockerfile, nginx.conf  прод-раздача
├── design/                 исходная канва (справочник по дизайну)
└── src/
    ├── app.js              bootstrap: Telegram → авторизация → роутер
    ├── router.js           hash-роутер, 18 маршрутов
    ├── store.js            реактивное состояние + кэш запросов с инвалидацией
    ├── api/
    │   ├── client.js       единый API-клиент (весь fetch только здесь)
    │   ├── telegram.js     ready/expand, тема, safe area, BackButton, haptics, openInvoice
    │   └── types.d.ts      TypeScript-типы всех DTO
    ├── ui/                 app.css (токены), dom.js, icons.js, components.js
    └── screens/            15 модулей, покрывающих все 41 экран макета
```

Экраны макета и их реализация:

| Экраны | Модуль |
|---|---|
| 01 Splash, 02 ошибка загрузки | `screens/splash.js`, `app.js` |
| 03–05 онбординг | `screens/onboarding.js` |
| 06–10, 13 библиотека и её состояния | `screens/library.js` |
| 11–12 поиск | `screens/search.js` |
| 14 добавление книги (каталог + вручную) | `screens/add-book.js` |
| 15–16 редактирование и удаление книги | `screens/edit-book.js` |
| 17–19 книга, меню записи, «+» | `screens/book.js` |
| 20–23 цитата, мысль, редактирование, теги | `screens/entry-form.js` |
| 24–26, 28–29 AI, источники, контекст, лимит | `screens/ai.js` |
| 27, 30 история диалогов | `screens/ai-history.js` |
| 31 профиль | `screens/profile.js` |
| 32–35 Premium | `screens/premium.js` |
| 36 настройки | `screens/settings.js` |
| 37–38 аккаунт и удаление | `screens/account.js` |
| 39 поддержка | `screens/support.js` |
| 40–41 документы | `screens/legal.js` |

Адрес API задаётся через `window.REMARKA_API_URL` (в Docker его подставляет
`config.js`) или `VITE_API_URL` при сборке образа; по умолчанию
`http://localhost:8000/api/v1`.

## 5. Локальная разработка

```bash
cd backend
python -m venv .venv && . .venv/Scripts/activate   # Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
cp ../.env.example ../.env
alembic upgrade head
python -m app.seed          # dev-данные: 6 книг с цитатами и заметками
uvicorn app.main:app --reload
```

Swagger: <http://localhost:8000/docs> (в production отключён).

**Вход без Telegram.** При `APP_ENV=development` доступен `POST /api/v1/auth/dev`:

```bash
curl -X POST http://localhost:8000/api/v1/auth/dev \
  -H 'Content-Type: application/json' \
  -d '{"telegram_id": 100500, "first_name": "Dev"}'
```

Роут **не регистрируется вообще**, если `APP_ENV=production` — подделать Telegram-пользователя
в проде нечем.

Фронтенд (отдельный терминал, Node не нужен):

```bash
cd frontend
python devserver.py 5173      # http://127.0.0.1:5173
```

Вне Telegram приложение само вызывает `POST /api/v1/auth/dev`, поэтому библиотеку
можно смотреть прямо в браузере.

Тесты и линт:

```bash
cd backend
pytest -q          # 83 теста, БД не нужна (SQLite in-memory + Fake AI-провайдеры)
ruff check app tests
alembic check      # миграция совпадает с моделями
```

`tests/test_e2e_flow.py` проходит весь пользовательский сценарий целиком: вход →
библиотека → книга → цитата и мысль → теги → поиск → AI с источниками → исчерпание
лимита → покупка Premium через Stars → история → настройки → удаление аккаунта.

## 6. Запуск через Docker

```bash
cp .env.example .env      # заполните TELEGRAM_BOT_TOKEN, LLM_*, EMBEDDING_*
docker compose up --build
```

Поднимаются `postgres` (образ `pgvector/pgvector:pg16`), `backend` (миграции применяются
на старте) и `frontend` (nginx раздаёт Mini App). Загруженные обложки лежат в томе
`uploads_data`.

Заполнить dev-данными:

```bash
docker compose exec backend python -m app.seed
```

## 6a. CI

`.github/workflows/ci.yml` гоняется на каждый push/PR в `master`:

| Job | Что проверяет |
|---|---|
| `lint` | `ruff check` по backend |
| `test-sqlite` | все 83 теста на in-memory SQLite (быстрый прогон) |
| `test-postgres` | `alembic upgrade head` + `alembic check` + тот же набор тестов, но против реального `pgvector/pgvector:pg16` — единственное место, где Postgres-специфичный код (тип `Vector`, JSONB, расширения `vector`/`pg_trgm`) действительно исполняется |
| `frontend-check` | синтаксис каждого ES-модуля (`node --check`) и граф импортов (`frontend/scripts/check_modules.py` — битые относительные пути, несуществующие именованные экспорты) |
| `docker-build` | оба `Dockerfile` (backend, frontend) реально собираются |
| `compose-smoke` | `docker compose up` поднимает backend + postgres и дожидается `200` на `/health` |

CD (автодеплой на сервер по мержу в `master`) пока не настроен — под него нужно выбрать
хостинг и завести секреты в GitHub (Settings → Secrets), сам workflow добавляется отдельно.

## 7. Миграции базы данных

Только Alembic, `create_all()` в проде не используется.

```bash
alembic upgrade head                            # применить
alembic revision --autogenerate -m "описание"   # создать новую
alembic downgrade -1                            # откатить
```

Миграция `0001_initial` создаёт расширения `vector` и `pg_trgm`, все таблицы, индексы по
`user_id` / `book_id` / `user_book_id` / `created_at` / ISBN / внешним id / Telegram
`provider_user_id`, GIN-триграммные индексы для поиска (включая русский текст) и HNSW-индекс
по `entry_embeddings.embedding` (`vector_cosine_ops`).

## 8. Настройка Telegram-бота

1. Создайте бота у [@BotFather](https://t.me/BotFather) → `TELEGRAM_BOT_TOKEN`,
   `TELEGRAM_BOT_USERNAME`.
2. Задайте вебхук с секретом (тем же, что в `TELEGRAM_WEBHOOK_SECRET`):

```bash
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -d "url=https://<ваш-домен>/api/v1/billing/webhooks/telegram" \
  -d "secret_token=<TELEGRAM_WEBHOOK_SECRET>" \
  -d 'allowed_updates=["message","pre_checkout_query"]'
```

`pre_checkout_query` **обязателен** — без него оплата не подтвердится.

## 9. Настройка Telegram Mini App

1. BotFather → `/newapp` → выберите бота, укажите HTTPS-URL фронтенда.
2. Фронтенд подключает `https://telegram.org/js/telegram-web-app.js`, вызывает
   `WebApp.ready()` / `WebApp.expand()` и отправляет **сырую** строку `WebApp.initData` в
   `POST /api/v1/auth/telegram` → получает `access_token` и дальше шлёт его в
   `Authorization: Bearer <token>`.
3. Backend сам проверяет HMAC-подпись initData ботовым токеном и её возраст; поля
   `telegram_id` / `username` / `is_premium`, присланные отдельно, не используются.

## 10. Google Books

`GOOGLE_BOOKS_API_KEY` — из Google Cloud Console (включите Books API). Основной источник
каталога. Поддерживает произвольный запрос, автора, название и ISBN (ISBN определяется
автоматически и уходит как `isbn:`), выбирается лучшая доступная обложка.

## 11. Open Library

Ключ не нужен. Используется только как fallback, когда Google вернул меньше
`BOOK_SEARCH_MIN_RESULTS` результатов; обложки берутся по `cover_i` или по ISBN.
Результаты обоих провайдеров нормализуются в один DTO и дедуплицируются.

## 12. AI-провайдер

Подойдёт любой OpenAI-совместимый API:

```env
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
EMBEDDING_BASE_URL=https://api.openai.com/v1
EMBEDDING_API_KEY=sk-...
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIM=1536
```

`AI_PROVIDER=fake` включает детерминированные локальные заглушки — удобно смотреть
приложение без ключей (ответы будут условными, но пайплайн RAG реальный).

Системный промпт и шаблоны документов для эмбеддингов вынесены в
`app/services/prompts.py`. Модель обязана вернуть `{"answer": ..., "source_ids": [...]}`;
backend дополнительно отбрасывает id, которых не было в переданном контексте.

## 13. Telegram Stars

Реализовано полностью: валюта `XTR`, уникальный payload, связь invoice ↔ наш `payments`,
обработка `pre_checkout_query` и `successful_payment`, идемпотентность, проверка суммы,
валюты и payload. Premium активируется только после подтверждённой оплаты.

```
POST /api/v1/billing/telegram-stars/create   → invoice_url
   → Telegram.WebApp.openInvoice(invoice_url)
   → Telegram шлёт pre_checkout_query   → backend проверяет payload/сумму и отвечает
   → Telegram шлёт successful_payment   → backend активирует Premium
GET  /api/v1/billing/status                  → фронтенд обновляет статус
```

Повторная доставка вебхука не создаёт вторую подписку; повторная покупка продлевает
существующую.

## 14. Заглушки платёжных провайдеров

`YooKassaPaymentProvider`, `PlategaPaymentProvider`, `CryptoBotPaymentProvider` реализуют
тот же интерфейс `PaymentProvider`, но `enabled = False` и на попытку оплаты возвращают
`PAYMENT_PROVIDER_NOT_CONFIGURED`. **Фиктивных успешных оплат нет.** Реальные адаптеры
дописываются в `app/integrations/payments/stubs.py` — единственные допустимые TODO в проекте
находятся там.

## 15. Production checklist

- [ ] `APP_ENV=production`, `SECRET_KEY` — длинная случайная строка (иначе приложение не стартует)
- [ ] `CORS_ORIGINS` — только домен Mini App
- [ ] `TELEGRAM_WEBHOOK_SECRET` задан и передан в `setWebhook`
- [ ] HTTPS + reverse proxy; `/docs` и `/openapi.json` уже отключены автоматически
- [ ] `alembic upgrade head` выполнен, extensions `vector` и `pg_trgm` доступны
- [ ] Хранилище переведено с локального тома на S3/R2/MinIO (реализовать `StorageService`)
- [ ] Rate limiting переведён на Redis (`RateLimiterBackend`) при более чем одном инстансе
- [ ] Заполнены реальные тексты Privacy Policy и Terms (`app/api/v1/legal.py` — заглушки)
- [ ] Настроены бэкапы БД и мониторинг
- [ ] Проверено, что `POST /api/v1/auth/dev` отсутствует в `/openapi.json`
