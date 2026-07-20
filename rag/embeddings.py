"""Embedding backends behind one interface: `embed_texts(texts) -> list[vector]`.

Default is a local, self-hosted ONNX model via fastembed — no API key, no
network call at query time, nothing leaves the machine. That's the strongest
DSGVO story available and it's what Stage 1 dogfooding runs on (see
eval/dogfood_stage1.py).

`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384 dims,
~220MB, ONNX/CPU, no PyTorch) was picked over larger multilingual models for
size — it needs to plausibly fit the shared droplet (1 vCPU / ~1.9GB RAM,
session 02) alongside everything else already running there. If the model
turns out too heavy once actually deployed (measure resident RAM, not just
disk size), fall back to MistralEmbedder below rather than growing this one:
Mistral is an EU/French company, so routing embedding calls through its API
keeps the DSGVO story intact even though it means text leaves the box.
"""

from __future__ import annotations

import os
from typing import Protocol

DEFAULT_LOCAL_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIM = 384


class Embedder(Protocol):
    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


class LocalEmbedder:
    """Self-hosted, offline embeddings via fastembed (ONNX runtime, no torch)."""

    def __init__(self, model_name: str = DEFAULT_LOCAL_MODEL) -> None:
        from fastembed import TextEmbedding  # lazy import — optional dependency

        self._model = TextEmbedding(model_name=model_name)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [vec.tolist() for vec in self._model.embed(texts)]


class MistralEmbedder:
    """Hosted fallback for boxes too small to run local inference.

    Mistral AI (Paris, France) rather than a US provider — keeps embedding
    calls inside an EU-domiciled data processor, consistent with the
    DSGVO-hard-requirement constraint even when embeddings can't be
    self-hosted on the shared droplet.
    """

    def __init__(self, api_key: str | None = None, model: str = "mistral-embed") -> None:
        self.api_key = api_key or os.environ.get("MISTRAL_API_KEY")
        if not self.api_key:
            raise RuntimeError("MISTRAL_API_KEY is not set. Export it or pass api_key= explicitly.")
        self.model = model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        from mistralai import Mistral  # lazy import — optional dependency

        client = Mistral(api_key=self.api_key)
        response = client.embeddings.create(model=self.model, inputs=texts)
        return [item.embedding for item in response.data]
