"""Stage 1 dogfooding: RAG over HELLFIRE/TETA+PI's own documentation.

Corpus: office-agent/samples/docs/ (business-model.md, module-catalog.md,
teta-pi-relationship.md) — the real internal documentation already used as
office-agent's BM25 stopgap corpus (see office_agent/knowledge_base/index.py).
Reusing it rather than inventing a separate corpus is deliberate: it's real,
it's already public, and it lets office-agent's eventual switch from BM25 to
this pipeline be judged against the exact same documents.

Run: python eval/dogfood_stage1.py
Requires no API key and no network at query time (LocalEmbedder only) — the
generation step (rag.generation) is exercised separately and needs
ANTHROPIC_API_KEY, so it's opt-in via --generate.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from rag.embeddings import LocalEmbedder
from rag.retrieval import index_directory, retrieve
from rag.store import LocalVectorStore

CORPUS = Path(__file__).resolve().parent.parent.parent / "office-agent" / "samples" / "docs"

# Real questions Bob or a teammate would plausibly ask the internal KB.
# Ukrainian and English mixed on purpose — the actual working docs and
# internal chat are bilingual, and the embedding model needs to hold up
# across both.
QUERIES = [
    "Чи можна виставляти рахунок підряднику погодинно?",
    "What server region hosts HELLFIRE and does it satisfy DSGVO?",
    "Хто такий TETA+PI по відношенню до HELLFIRE?",
    "Which module is built first and why?",
    "Чи є self-serve підписка для клієнтів?",
    "What happens after a module is implemented for a client?",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", action="store_true", help="Also call the Anthropic API to synthesize an answer.")
    args = parser.parse_args()

    embedder = LocalEmbedder()
    store = LocalVectorStore()

    t0 = time.time()
    n = index_directory(str(CORPUS), embedder, store)
    print(f"Indexed {n} chunks from {CORPUS} in {time.time() - t0:.2f}s\n")

    for query in QUERIES:
        t0 = time.time()
        results = retrieve(query, embedder, store, top_k=3)
        elapsed = time.time() - t0
        print(f"Q: {query}  ({elapsed * 1000:.0f}ms)")
        for r in results:
            snippet = r.text.strip().replace("\n", " ")[:160]
            print(f"  [{r.score:.3f}] {r.source} :: {r.heading or '(no heading)'} — {snippet}")

        if args.generate:
            from rag.generation import AnthropicClient, answer

            print("  --- generated answer ---")
            print(" ", answer(query, results, AnthropicClient()).replace("\n", "\n  "))
        print()


if __name__ == "__main__":
    main()
