# HELLFIRE AI Solutions — RAG 01

Module 3. Infrastructure module that Office Agent and future sector agents are built on.

**Dogfooding → template:** a universal RAG pipeline (vector DB, chunking strategy, retrieval + generation prompt template) that plugs into any client's private data corpus.

**Status:** Etap 1 (RAG over our own documentation) — done, retrieval quality tested. Etap 2 (pipeline ready to plug in a client corpus) — base version ready, production deploy not yet done (depends on the internal-db decision, see below).

## Vector DB decision: pgvector, not Qdrant

**Chosen:** pgvector (extension on the shared Postgres), self-hosted, on the same droplet (fra1/Frankfurt, session 02).

**Why:**
1. TETA+PI already runs `pgvector/pgvector:pg16` in production on this exact droplet (`tetapi-postgres`) — the technology is already proven-compatible, not a new risk.
2. `internal-db` (session 04) already committed to the "schema-per-concern in one Postgres, not a separate DB/service per need" pattern specifically because of the RAM constraint (1 vCPU / ~1.9GB, shared with TETA+PI) — see `internal-db/docs/SCHEMA.md`. Qdrant as a standalone service would break that already-agreed pattern and add a full second process to an already-tight box.
3. One less — not two — vector/DB stack for all of HELLFIRE.

**Why not managed:** self-hosted on the already-audited EU droplet closes DSGVO data residency with no extra vendor/DPA and no recurring cost. A managed EU vector DB (Qdrant Cloud EU, etc.) remains an option if/when RAG load outgrows this droplet.

**Consequence for internal-db (needs coordination, not done by this session):** the Postgres image in `internal-db/docker-compose.yml` needs bumping from `postgres:16-alpine` to `pgvector/pgvector:pg16` (drop-in, the same image already in prod for TETA+PI). Migration `rag-01/migrations/0001_rag_schema.sql` is designed for this same shared Postgres instance (a new `rag` schema, alongside `crm`/`marketing`), not a separate database.

## Embeddings decision: self-hosted local model by default

`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` via `fastembed` (ONNX, no PyTorch, ~220MB, 384 dims) — no data ever leaves the machine, the strongest possible DSGVO position. Multilingual support (UA+EN) verified with real queries below.

If the model turns out too heavy in production on the droplet (1 vCPU / ~1.9GB RAM — need to measure resident RAM, not just disk size) — fallback: `rag.embeddings.MistralEmbedder` (Mistral AI, an EU company — keeps the DSGVO position even if text goes out over the API).

Generation (synthesizing an answer from retrieved chunks) — separate, via the Anthropic API (`rag/generation.py`), the same pattern already adopted in office-agent.

## Hosting

The same droplet as the rest of HELLFIRE (fra1/Frankfurt, `hellfire_net`, `hellfire` deploy user) — EU data residency already satisfied by session 02's infrastructure. No second droplet was needed (STATE.md previously flagged rag-01 as a candidate for "heavy module, likely needs a second droplet") — precisely because the heavy computation (embedding inference) can be pushed to the Mistral API, and what stays self-hosted (pgvector storage + search) is light.

## Chunking

First split by Markdown headings (so a chunk stays on one topic), then by paragraph for headingless blocks longer than 1500 characters. PDF (no headings) goes straight to paragraph splitting. The same `RawChunk(source, heading, text)` interface already used by `office-agent`'s BM25 stub (`office_agent/knowledge_base/ingest.py`) — deliberately, so office-agent can plug in this pipeline without changing its own `ingest -> chunks -> search` contract.

## Etap 1 — dogfooding results (2026-07-20/21)

Corpus: `office-agent/samples/docs/` (business-model.md, module-catalog.md, teta-pi-relationship.md) — real HELLFIRE/TETA+PI documentation, already used by office-agent. A dedicated Data Room or Pitch Deck for HELLFIRE itself doesn't exist yet (the company is at the session-03 stage — no site yet); PDF ingestion was additionally run locally (not committed, confidential content) against TETA+PI's real pitch deck (`PI_PitchDeck_EN.pdf`) — pypdf cleanly extracted text into 8 chunks, the path confirmed working.

Run: `python eval/dogfood_stage1.py` (no API keys — local embedder only).

**Result: 4/6 real queries (UA+EN mix) — exact chunk answer ranked first; 2/6 — exact chunk either missed the top-3 or ranked second.**

Specific finding: pure semantic (dense) retrieval sometimes underweights short, lexically precise negation sentences ("never hourly," "built first because X") in favor of broader topically similar chunks. For example the query "can a contractor be billed hourly" surfaced the "Pricing shape" section (topically close) rather than the "Sales and delivery constraints" section, which literally says "never billed hourly."

**Conclusion for Etap 2:** don't replace office-agent's BM25 with dense retrieval — combine them (hybrid: BM25 + embeddings, or rerank). office-agent already has a working `BM25Index` — adding a dense pipeline on top gives better recall on both query types than either alone.

## Local run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[pg,llm,dev]"

# storage (dev): local pgvector in Docker
cp .env.example .env
docker compose up -d
psql "$RAG_DATABASE_URL" -f migrations/0001_rag_schema.sql

rag ingest path/to/docs
rag query "your question"

# without Postgres/Docker — Stage 1 dogfood test with an in-memory store:
python eval/dogfood_stage1.py
```

## Structure

- `rag/ingest.py` — chunking (md/txt/pdf).
- `rag/embeddings.py` — `LocalEmbedder` (default), `MistralEmbedder` (fallback).
- `rag/store.py` — `PgVectorStore` (production) and `LocalVectorStore` (dev/test), one interface.
- `rag/retrieval.py` — index + retrieve.
- `rag/generation.py` — prompt template + Anthropic-based synthesis.
- `rag/cli.py` — `rag ingest` / `rag query`.
- `migrations/0001_rag_schema.sql` — `rag` schema in the shared HELLFIRE Postgres instance.
- `eval/dogfood_stage1.py` — Etap 1 test.
- `tests/` — pytest.

**License:** MIT.
