from rag.store import EmbeddedChunk, LocalVectorStore


def _chunk(source: str, vector: list[float]) -> EmbeddedChunk:
    return EmbeddedChunk(source=source, heading="", text=f"text for {source}", embedding=vector)


def test_search_ranks_by_cosine_similarity():
    store = LocalVectorStore()
    store.upsert(
        [
            _chunk("exact_match", [1.0, 0.0]),
            _chunk("orthogonal", [0.0, 1.0]),
            _chunk("opposite", [-1.0, 0.0]),
        ]
    )

    results = store.search([1.0, 0.0], top_k=3)

    assert [r.source for r in results] == ["exact_match", "orthogonal", "opposite"]
    assert results[0].score > 0.99
    assert results[2].score < -0.99


def test_search_respects_top_k():
    store = LocalVectorStore()
    store.upsert([_chunk(f"doc{i}", [1.0, float(i)]) for i in range(10)])

    results = store.search([1.0, 0.0], top_k=3)

    assert len(results) == 3


def test_empty_store_returns_no_results():
    store = LocalVectorStore()
    assert store.search([1.0, 0.0]) == []
    assert store.count() == 0
