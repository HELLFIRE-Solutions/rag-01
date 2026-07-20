-- Schema separation follows internal-db's pattern (schema-per-concern inside
-- one shared Postgres instance, not a dedicated database/service per module)
-- for the same reason internal-db adopted it: the shared droplet has ~1.9GB
-- RAM total, and a second Postgres process (or a whole separate vector DB
-- service like Qdrant) is a heavier footprint than one more schema in an
-- instance that's already running. See rag-01/README.md "Vector DB decision".
--
-- This migration targets the SAME Postgres instance as internal-db
-- (session 04), not a new one. It requires that instance's image be
-- pgvector/pgvector:pg16 instead of plain postgres:16-alpine — TETA+PI's
-- own tetapi-postgres container already runs pgvector/pgvector:pg16 on this
-- exact droplet, so the image is proven compatible here; internal-db's
-- docker-compose.yml just hasn't been bumped to it yet (flagged separately
-- to the Session Manager, not changed by this repo).
CREATE SCHEMA IF NOT EXISTS rag;
CREATE EXTENSION IF NOT EXISTS vector;

COMMENT ON SCHEMA rag IS 'RAG 01: chunked + embedded HELLFIRE/TETA+PI (and later, client) documents.';

-- 384 dims matches the default local embedder
-- (sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2, see
-- rag/embeddings.py). Changing embedding model/dims requires a new table or
-- a re-embed of every row -- vector columns are fixed-width.
CREATE TABLE IF NOT EXISTS rag.chunks (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    heading TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL,
    embedding vector(384) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- HNSW over IVFFlat: no separate "train" step needed and it stays accurate
-- as the corpus grows, which matters here because Stage 2's whole point is
-- accepting arbitrary client corpora of unknown size up front.
CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw_idx
    ON rag.chunks USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS chunks_source_idx ON rag.chunks (source);
