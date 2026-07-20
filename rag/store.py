"""Vector storage behind one interface: `upsert(chunks)` / `search(vector, top_k)`.

Two backends:

- `PgVectorStore` — the real target: pgvector extension inside the shared
  HELLFIRE Postgres instance (see migrations/0001_rag_schema.sql). Storage
  and cosine search are cheap (index scans, not model inference), so this
  is fine on the same droplet already running TETA+PI's pgvector-backed
  Postgres and HELLFIRE's own internal-db — see README.md "Vector DB
  decision" for why Qdrant (a whole extra service) was passed over.
- `LocalVectorStore` — in-memory numpy cosine search, same interface. Used
  for dev/testing where no Postgres is reachable (this sandbox has neither
  docker nor a deployed HELLFIRE Postgres instance yet). Not for production
  use: no persistence, no concurrent access.

Keep both behind `Store` so retrieval.py and the CLI don't care which one
is wired up.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class EmbeddedChunk:
    source: str
    heading: str
    text: str
    embedding: list[float]


@dataclass
class SearchResult:
    source: str
    heading: str
    text: str
    score: float


class Store(Protocol):
    def upsert(self, chunks: list[EmbeddedChunk]) -> None: ...
    def search(self, query_vector: list[float], top_k: int = 5) -> list[SearchResult]: ...
    def count(self) -> int: ...


class LocalVectorStore:
    def __init__(self) -> None:
        self._chunks: list[EmbeddedChunk] = []

    def upsert(self, chunks: list[EmbeddedChunk]) -> None:
        self._chunks.extend(chunks)

    def search(self, query_vector: list[float], top_k: int = 5) -> list[SearchResult]:
        import numpy as np

        if not self._chunks:
            return []

        q = np.array(query_vector)
        q_norm = np.linalg.norm(q) or 1.0
        scored = []
        for chunk in self._chunks:
            v = np.array(chunk.embedding)
            sim = float(np.dot(q, v) / (q_norm * (np.linalg.norm(v) or 1.0)))
            scored.append((sim, chunk))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [
            SearchResult(source=c.source, heading=c.heading, text=c.text, score=score)
            for score, c in scored[:top_k]
        ]

    def count(self) -> int:
        return len(self._chunks)


class PgVectorStore:
    """pgvector-backed store. Requires the `rag` schema from
    migrations/0001_rag_schema.sql to already exist on the target Postgres.
    """

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def upsert(self, chunks: list[EmbeddedChunk]) -> None:
        import psycopg
        from pgvector.psycopg import register_vector

        with psycopg.connect(self.dsn) as conn:
            register_vector(conn)
            with conn.cursor() as cur:
                for chunk in chunks:
                    cur.execute(
                        """
                        INSERT INTO rag.chunks (source, heading, text, embedding)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (chunk.source, chunk.heading, chunk.text, chunk.embedding),
                    )
            conn.commit()

    def search(self, query_vector: list[float], top_k: int = 5) -> list[SearchResult]:
        import psycopg
        from pgvector.psycopg import register_vector

        with psycopg.connect(self.dsn) as conn:
            register_vector(conn)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT source, heading, text, 1 - (embedding <=> %s) AS score
                    FROM rag.chunks
                    ORDER BY embedding <=> %s
                    LIMIT %s
                    """,
                    (query_vector, query_vector, top_k),
                )
                rows = cur.fetchall()
        return [SearchResult(source=r[0], heading=r[1], text=r[2], score=r[3]) for r in rows]

    def count(self) -> int:
        import psycopg

        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM rag.chunks")
                return cur.fetchone()[0]
