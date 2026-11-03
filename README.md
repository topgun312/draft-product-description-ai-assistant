# Генератор карточек товаров с помощью ИИ

Сервис на FastAPI, который принимает данные товара в JSON, отправляет их в выбранную
LLM (Ollama, OpenAI или Anthropic) и возвращает черновик карточки товара: SEO-заголовок,
SEO-описание, ключевые характеристики, поисковые запросы и коммерческий блок.

Сервис проверяет ответ модели по требованиям ТЗ: длины SEO-полей, количество запросов,
наличие обязательных блоков и отсутствие технических значений, которых не было во
входных данных. При нарушениях выполняется повторная генерация, затем детерминированная
нормализация.

## Возможности

- `POST /generate` — карточка одного товара в JSON.
- `POST /generate/batch` — карточки нескольких товаров параллельно.
- `POST /generate/markdown` — карточка одного товара в Markdown.
- `POST /generate/stream` — потоковая выдача ответа модели (`text/plain`).
- `GET /health` — проверка работы сервиса и доступных провайдеров.
- Поддержка Ollama (по умолчанию), OpenAI и Anthropic.
- Защита от выдуманных характеристик: значения сверяются с входными данными,
  отсутствующие характеристики помечаются как `данных нет`.
- Понятные HTTP-ошибки: `422` — некорректный вход, `502` — ошибка LLM,
  `503` — провайдер недоступен.

## Требования

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (рекомендуется) или `venv` + `pip`
- Для локальной модели — установленный [Ollama](https://ollama.com/)
- Либо API-ключ OpenAI/Anthropic
- Docker и Docker Compose — опционально, для контейнерного запуска

## Установка

```bash
git clone <URL-репозитория>
cd draft-product-description-ai-assistant
```

### 1. Создать файл настроек

```bash
cp .env.example .env
```

Откройте `.env` и при необходимости измените провайдера, модель, таймаут и API-ключи.
Все переменные описаны в разделе [«Настройка»](#настройка).

### 2. Создать и активировать виртуальное окружение

Вариант с `uv` (рекомендуется):

```bash
uv sync
source .venv/bin/activate
```

Для Windows:

```powershell
.venv\Scripts\activate
```

Вариант с `venv` и `pip`:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install "fastapi[all]" anthropic openai loguru pydantic-settings
```

> `uv sync` сам создаёт `.venv`, но активировать окружение всё равно нужно, чтобы
> команда `uvicorn` была доступна без пути `.venv/bin/`.

Для проверок кода дополнительно установите `black` и `flake8` (они уже входят в
зависимости `uv sync`).

## Настройка

Все параметры задаются в файле `.env` в корне проекта. Файл добавлен в `.gitignore`,
API-ключи в коде не хранятся. После изменения `.env` перезапустите сервис.

| Переменная | По умолчанию | Описание |
|---|---|---|
| `DEFAULT_PROVIDER` | `ollama` | Провайдер: `ollama`, `openai` или `anthropic` |
| `DEFAULT_MODEL` | `llama3.2` | Модель по умолчанию |
| `MAX_TOKENS` | `2048` | Максимум токенов в ответе |
| `REQUEST_TIMEOUT` | `120` | Таймаут запроса к LLM, секунды |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Адрес Ollama |
| `LOG_LEVEL` | `INFO` | Уровень логирования loguru |
| `LOG_FILE` | — | Путь к файлу логов (ротация 10 MB, хранение 7 дней) |
| `OPENAI_API_KEY` | — | Ключ OpenAI (если используется) |
| `ANTHROPIC_API_KEY` | — | Ключ Anthropic (если используется) |

Пример `.env` для локальной Ollama:

```dotenv
DEFAULT_PROVIDER=ollama
DEFAULT_MODEL=llama3.2
MAX_TOKENS=2048
REQUEST_TIMEOUT=180

OLLAMA_BASE_URL=http://localhost:11434
```

Пример `.env` для OpenAI:

```dotenv
DEFAULT_PROVIDER=openai
DEFAULT_MODEL=gpt-4o-mini
MAX_TOKENS=2048
REQUEST_TIMEOUT=120

OPENAI_API_KEY=sk-...
```

> Для моделей 7B и больше увеличьте `REQUEST_TIMEOUT` до 180–300 секунд.
> В Docker адрес Ollama (`OLLAMA_BASE_URL`) автоматически заменяется на
> `http://ollama:11434` через `docker-compose.yml`.

## Запуск локально

1. Запустите Ollama и скачайте модель (если используете локальный провайдер):

   ```bash
   ollama serve
   ollama pull llama3.2
   ```

2. Активируйте виртуальное окружение (если ещё не активировано):

   ```bash
   source .venv/bin/activate
   ```

3. Запустите сервис:

   ```bash
   uvicorn src.main:app --reload --host 127.0.0.1 --port 8000
   ```

4. Проверьте, что сервис работает:

   ```bash
   curl http://127.0.0.1:8000/health
   ```

Swagger-документация доступна по адресу <http://127.0.0.1:8000/docs>.

## Запуск через Docker

В проекте есть `Dockerfile`, `docker-compose.yml` и `.dockerignore`. Compose поднимает
два сервиса: приложение на FastAPI и Ollama, а отдельный одноразовый контейнер
`ollama-pull` скачивает модель, указанную в `DEFAULT_MODEL`.

1. Создайте `.env` (если ещё не создан):

   ```bash
   cp .env.example .env
   ```

2. Соберите и запустите контейнеры:

   ```bash
   docker compose up --build
   ```

   При первом запуске скачивание модели может занять несколько минут.

3. Откройте приложение:

   - API и Swagger: <http://127.0.0.1:8000/docs>
   - Ollama: <http://127.0.0.1:11434>

4. Полезные команды:

   ```bash
   # логи приложения
   docker compose logs -f app

   # перезапуск после изменения кода
   docker compose up --build

   # остановка контейнеров
   docker compose down

   # остановка с удалением скачанных моделей
   docker compose down -v
   ```

Если нужно сменить модель, измените `DEFAULT_MODEL` в `.env` и перезапустите:

```bash
docker compose down
docker compose up --build
```

Для OpenAI или Anthropic укажите в `.env` соответствующие `DEFAULT_PROVIDER`,
`DEFAULT_MODEL` и API-ключ. Контейнер Ollama при этом можно не использовать, но
`docker compose up` всё равно его запустит — это не мешает работе приложения.

## Примеры запросов

Генерация одной карточки в JSON:

```bash
curl -X POST 'http://127.0.0.1:8000/generate' \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Манометр показывающий DM 02",
    "manufacturer": "Манотомь",
    "specs": {
      "диапазон измерений": "0–1,6 МПа",
      "класс точности": "1,5",
      "присоединение": "G1/2",
      "диаметр корпуса": "100 мм"
    },
    "description": "Прибор предназначен для измерения избыточного давления неагрессивных к медным сплавам сред."
  }'
```

Несколько товаров за один запрос:

```bash
curl -X POST 'http://127.0.0.1:8000/generate/batch' \
  -H 'Content-Type: application/json' \
  -d '[{ "name": "Манометр DM 02", "manufacturer": "Манотомь", "specs": {}, "description": "" }]'
```

Генерация в Markdown:

```bash
curl -X POST 'http://127.0.0.1:8000/generate/markdown' \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Манометр показывающий DM 02",
    "manufacturer": "Манотомь",
    "specs": {"диапазон измерений": "0–1,6 МПа"},
    "description": "Прибор предназначен для измерения избыточного давления."
  }'
```

Потоковая генерация:

```bash
curl -N -X POST 'http://127.0.0.1:8000/generate/stream' \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Манометр показывающий DM 02",
    "manufacturer": "Манотомь",
    "specs": {"диапазон измерений": "0–1,6 МПа"},
    "description": "Прибор предназначен для измерения избыточного давления."
  }'
```

Эндпоинт отдаёт `text/plain`: фрагменты JSON печатаются по мере генерации
моделью, а при склейке образуют ровно тот JSON, который возвращает `POST /generate`.
Никаких SSE-обёрток `data: ...` и финального дубликата карточки нет.

### Формат ответа

```json
{
  "seo_title": "Манометр показывающий DM 02 от Манотомь",
  "seo_description": "...",
  "key_specs": [{"key": "диапазон измерений", "value": "0–1,6 МПа"}],
  "search_queries": ["Манометр DM 02", "..."],
  "commercial_block": "...",
  "missing_fields": ["цена", "материал корпуса"]
}
```

### Коды ошибок

| Код | Причина |
|---|---|
| `400` | Пустой список товаров в batch-запросе |
| `422` | Некорректный JSON или пустые обязательные поля |
| `502` | LLM вернула ошибку или невалидный JSON |
| `503` | Провайдер недоступен или не настроен API-ключ |

## Структура проекта

```text
.
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── .env.example
├── pyproject.toml
├── uv.lock
├── README.md
├── IMPLEMENTATION.md
└── src/
    ├── main.py                 # точка входа FastAPI
    ├── api/
    │   ├── deps.py             # зависимости FastAPI
    │   └── routers/            # маршруты /generate и /health
    ├── core/
    │   ├── exceptions.py       # доменные исключения
    │   ├── models.py           # Pydantic-модели входа и результата
    │   └── settings.py         # настройки из .env
    ├── services/
    │   ├── llm_client.py       # единый клиент для LLM-провайдеров
    │   ├── llm_checks.py       # проверка доступности Ollama
    │   ├── prompts.py          # системный и пользовательский промпты
    │   └── product_card.py     # генерация с проверками и повторами
    └── utils/
        ├── json_parser.py      # извлечение JSON из ответа LLM
        ├── markdown.py         # экспорт карточки в Markdown
        └── product_card.py     # валидация и нормализация карточки
```

## Проверка качества кода

```bash
source .venv/bin/activate
black --check src
flake8 src
```

## Ограничения

- Качество текста зависит от выбранной модели. Небольшие модели (например, `llama3.2`)
  могут не добирать объём SEO-описания; сервис выполнит несколько попыток и затем
  детерминированно дополнит текст только данными из входных запросов.
- Для стабильного результата без повторов рекомендуется модель от 7B
  (`DEFAULT_MODEL=qwen2.5:7b`).
- Сервис не хранит историю запросов и не имеет авторизации — это демонстрационный
  черновик, а не production-решение.
