"""Retrieval-augmented answer generation: prompt template + LLM call.

The LLMClient here is intentionally a near-duplicate of office-agent's
office_agent/llm.py (same lazy-import-anthropic, no-key-no-import shape).
Duplicated rather than imported because the dependency direction is
rag-01 -> nothing, office-agent -> rag-01 (this module is the infra layer;
see office_agent/knowledge_base/index.py's own docstring about swapping to
rag-01 once this pipeline stabilizes). Once office-agent switches its
generation step over to this retrieval pipeline, it can drop its own
llm.py and import this one instead of the two drifting independently.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

from rag.retrieval import RetrievedChunk

DEFAULT_MODEL = "claude-sonnet-5"

SYSTEM_PROMPT = (
    "You are HELLFIRE AI Solutions' internal knowledge assistant. Answer only "
    "from the provided context chunks. If the context doesn't contain the "
    "answer, say so explicitly instead of guessing. Cite the source file for "
    "every claim in square brackets, e.g. [business-model.md]. Answer in the "
    "same language as the question."
)


def build_prompt(query: str, chunks: list[RetrievedChunk]) -> str:
    context = "\n\n".join(f"[{c.source}]\n{c.text}" for c in chunks)
    return f"Context:\n{context}\n\nQuestion: {query}"


class LLMClient(Protocol):
    def complete(self, system: str, prompt: str) -> str: ...


@dataclass
class AnthropicClient:
    model: str = DEFAULT_MODEL
    api_key: str | None = None

    def __post_init__(self) -> None:
        self.api_key = self.api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Export it or pass api_key= explicitly "
                "before generating answers."
            )

    def complete(self, system: str, prompt: str) -> str:
        import anthropic  # lazy import — optional dependency

        client = anthropic.Anthropic(api_key=self.api_key)
        response = client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in response.content if block.type == "text")


def answer(query: str, chunks: list[RetrievedChunk], llm: LLMClient) -> str:
    return llm.complete(SYSTEM_PROMPT, build_prompt(query, chunks))
