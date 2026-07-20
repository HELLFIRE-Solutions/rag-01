# HELLFIRE AI Solutions — RAG 01

Модуль 3. Інфраструктурний модуль, на якому будуються Office Agent і майбутні sector-агенти.

**Dogfooding → шаблон:** універсальний RAG-pipeline (vector DB, chunking-стратегія, retrieval + generation prompt template), що підключається до будь-якого корпусу закритих даних клієнта.

**Статус:** Етап 1 (RAG над власною документацією) — зроблено, retrieval-якість протестована. Етап 2 (готовий до підключення клієнтського корпусу pipeline) — базова версія готова, продакшн-деплой ще не виконано (залежить від рішення по internal-db, див. нижче).

## Vector DB decision: pgvector, не Qdrant

**Обрано:** pgvector (extension у спільному Postgres), self-hosted, на тому ж дроплеті (fra1/Frankfurt, сесія 02).

**Чому:**
1. TETA+PI вже production-перевірив `pgvector/pgvector:pg16` на цьому самому дроплеті (`tetapi-postgres`) — технологія вже proven-compatible, не новий ризик.
2. `internal-db` (сесія 04) вже прийняв шаблон "schema-per-concern в одному Postgres, а не окрема БД/сервіс на кожну потребу" саме через обмеження RAM (1 vCPU / ~1.9GB, спільний з TETA+PI) — див. `internal-db/docs/SCHEMA.md`. Qdrant як окремий сервіс порушив би цей вже узгоджений патерн і додав би повноцінний другий процес на й так тісний бокс.
3. Один менше — не два — vector/DB stack на весь HELLFIRE.

**Чому не managed:** self-hosted на вже аудійованому EU-дроплеті закриває DSGVO data residency без додаткового vendor/DPA і без recurring cost. Managed EU vector DB (Qdrant Cloud EU тощо) лишається опцією, якщо/коли RAG-навантаження переросте цей дроплет.

**Наслідок для internal-db (потребує координації, не зроблено цією сесією):** образ Postgres в `internal-db/docker-compose.yml` треба підняти з `postgres:16-alpine` до `pgvector/pgvector:pg16` (drop-in, той самий образ вже в проді для TETA+PI). Міграція `rag-01/migrations/0001_rag_schema.sql` розрахована на цю саму спільну Postgres-інстанцію (нова схема `rag`, поруч із `crm`/`marketing`), не на окрему базу.

## Embeddings decision: self-hosted local model за замовчуванням

`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` через `fastembed` (ONNX, без PyTorch, ~220MB, 384 dims) — жодних даних не залишає машину, найсильніша DSGVO-позиція з можливих. Мультимовність (UA+EN) перевірена реальними запитами нижче.

Якщо на дроплеті (1 vCPU / ~1.9GB RAM) модель виявиться завеликою в проді (треба зміряти resident RAM, не тільки розмір на диску) — фолбек: `rag.embeddings.MistralEmbedder` (Mistral AI, Париж/ЄС-компанія — зберігає DSGVO-позицію навіть якщо текст іде назовні через API).

Generation (синтез відповіді з retrieved chunks) — окремо, через Anthropic API (`rag/generation.py`), той самий патерн, що вже прийнятий в office-agent.

## Hosting

Той самий дроплет, що й усе HELLFIRE (fra1/Frankfurt, `hellfire_net`, `hellfire` deploy-юзер) — EU data residency вже задоволена інфраструктурою сесії 02. Не знадобився другий дроплет (STATE.md раніше позначав rag-01 як кандидата на "важкий модуль, ймовірно другий дроплет") — саме тому, що ваговите обчислення (embedding inference) можна винести на Mistral API, а те, що лишається self-hosted (pgvector storage + search), легке.

## Chunking

Спершу спліт по Markdown-заголовках (щоб чанк тримався однієї теми), потім параграфами для безголовкових блоків довших за 1500 символів. PDF (без заголовків) одразу йде параграфами. Той самий інтерфейс `RawChunk(source, heading, text)`, що вже використовує `office-agent`'s BM25-заглушка (`office_agent/knowledge_base/ingest.py`), навмисно — щоб office-agent міг підключити цей pipeline без зміни власного `ingest -> chunks -> search` контракту.

## Етап 1 — результати dogfooding (2026-07-20/21)

Корпус: `office-agent/samples/docs/` (business-model.md, module-catalog.md, teta-pi-relationship.md) — реальна документація HELLFIRE/TETA+PI, вже використовувана office-agent. Окремого Data Room чи Pitch Deck для самого HELLFIRE ще не існує (компанія на стадії сесії 03 — сайту ще немає); PDF-ingestion додатково прогнано локально (не закомічено, конфіденційний контент) проти реального pitch deck TETA+PI (`PI_PitchDeck_EN.pdf`) — pypdf чисто витягнув текст на 8 чанків, шлях підтверджено робочим.

Запуск: `python eval/dogfood_stage1.py` (без API-ключів — тільки local embedder).

**Результат: 4/6 реальних запитів (UA+EN мікс) — точний чанк-відповідь на першому місці; 2/6 — точний чанк або не потрапив у top-3, або посів друге місце.**

Конкретна знахідка: чисто semantic (dense) retrieval іноді недооцінює короткі, лексично-точні речення-заперечення ("ніколи не погодинно", "будується першим тому що X") на користь ширших тематично схожих чанків. Наприклад запит "чи можна виставляти рахунок погодинно" підняв секцію "Pricing shape" (тематично близько), а не секцію "Sales and delivery constraints", де буквально написано "never billed hourly".

**Висновок для Етапу 2:** не замінювати office-agent's BM25 на dense retrieval — комбінувати (hybrid: BM25 + embedding, або rerank). office-agent вже має робочий `BM25Index` — плюс dense pipeline звідси дає кращий recall на обидва типи запитів, ніж будь-який з них окремо.

## Локальний запуск

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[pg,llm,dev]"

# storage (dev): локальний pgvector у Docker
cp .env.example .env
docker compose up -d
psql "$RAG_DATABASE_URL" -f migrations/0001_rag_schema.sql

rag ingest path/to/docs
rag query "твоє питання"

# без Postgres/Docker — Stage 1 dogfood-тест з in-memory store:
python eval/dogfood_stage1.py
```

## Структура

- `rag/ingest.py` — chunking (md/txt/pdf).
- `rag/embeddings.py` — `LocalEmbedder` (за замовчуванням), `MistralEmbedder` (fallback).
- `rag/store.py` — `PgVectorStore` (production) і `LocalVectorStore` (dev/test), один інтерфейс.
- `rag/retrieval.py` — index + retrieve.
- `rag/generation.py` — prompt template + Anthropic-based synthesis.
- `rag/cli.py` — `rag ingest` / `rag query`.
- `migrations/0001_rag_schema.sql` — схема `rag` у спільній HELLFIRE Postgres-інстанції.
- `eval/dogfood_stage1.py` — Етап 1 тест.
- `tests/` — pytest.

**Ліцензія:** MIT.
