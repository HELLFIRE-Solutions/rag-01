from __future__ import annotations

import argparse
import os
import sys

from rag.embeddings import LocalEmbedder
from rag.retrieval import index_directory, retrieve
from rag.store import PgVectorStore


def _store():
    dsn = os.environ.get("RAG_DATABASE_URL")
    if not dsn:
        raise RuntimeError("RAG_DATABASE_URL is not set (postgresql://user:pass@host:port/db).")
    return PgVectorStore(dsn)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="rag")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest_p = sub.add_parser("ingest", help="Chunk, embed, and index a directory of documents.")
    ingest_p.add_argument("path")

    query_p = sub.add_parser("query", help="Retrieve top-k chunks for a question.")
    query_p.add_argument("text")
    query_p.add_argument("--top-k", type=int, default=5)

    args = parser.parse_args(argv)
    embedder = LocalEmbedder()
    store = _store()

    if args.command == "ingest":
        n = index_directory(args.path, embedder, store)
        print(f"Indexed {n} chunks from {args.path}", file=sys.stderr)
    elif args.command == "query":
        results = retrieve(args.text, embedder, store, top_k=args.top_k)
        for r in results:
            print(f"[{r.score:.3f}] {r.source} :: {r.heading or '(no heading)'}")
            print(r.text[:300])
            print()


if __name__ == "__main__":
    main()
