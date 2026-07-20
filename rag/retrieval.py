"""Glue: index a directory into a Store, and retrieve chunks for a query."""

from __future__ import annotations

from dataclasses import dataclass

from rag.embeddings import Embedder
from rag.ingest import ingest_directory
from rag.store import EmbeddedChunk, SearchResult, Store


@dataclass
class RetrievedChunk:
    source: str
    heading: str
    text: str
    score: float


def index_directory(root: str, embedder: Embedder, store: Store, batch_size: int = 64) -> int:
    raw_chunks = ingest_directory(root)
    for start in range(0, len(raw_chunks), batch_size):
        batch = raw_chunks[start : start + batch_size]
        vectors = embedder.embed_texts([c.text for c in batch])
        store.upsert(
            [
                EmbeddedChunk(source=c.source, heading=c.heading, text=c.text, embedding=v)
                for c, v in zip(batch, vectors)
            ]
        )
    return len(raw_chunks)


def retrieve(query: str, embedder: Embedder, store: Store, top_k: int = 5) -> list[RetrievedChunk]:
    query_vector = embedder.embed_texts([query])[0]
    results: list[SearchResult] = store.search(query_vector, top_k=top_k)
    return [
        RetrievedChunk(source=r.source, heading=r.heading, text=r.text, score=r.score)
        for r in results
    ]
