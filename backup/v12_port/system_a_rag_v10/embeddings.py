"""Gemini embeddings wrapper for RAG v10."""

from __future__ import annotations

import time
from pathlib import Path

import google.generativeai as genai
from langchain_core.embeddings import Embeddings

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
import config


class GeminiEmbeddings(Embeddings):
    """Embeddings wrapper backed by Google Generative AI embeddings."""

    def __init__(self, model: str = "models/gemini-embedding-001", batch_size: int = 16):
        if not config.GOOGLE_API_KEY:
            raise RuntimeError("GOOGLE_API_KEY is not set")
        genai.configure(api_key=config.GOOGLE_API_KEY)
        self.model = model
        self.batch_size = batch_size

    def _extract_vectors(self, response) -> list[list[float]]:
        if isinstance(response, dict):
            if "embedding" in response:
                item = response["embedding"]
                if isinstance(item, dict) and "values" in item:
                    return [item["values"]]
                if isinstance(item, list):
                    if item and isinstance(item[0], list):
                        return item
                    return [item]
            if "embeddings" in response:
                vectors = []
                for item in response["embeddings"]:
                    if isinstance(item, dict) and "values" in item:
                        vectors.append(item["values"])
                    elif isinstance(item, dict) and "embedding" in item:
                        inner = item["embedding"]
                        vectors.append(inner.get("values", inner) if isinstance(inner, dict) else inner)
                    else:
                        vectors.append(item)
                return vectors

        raise RuntimeError(f"Unexpected embedding response format: {type(response).__name__}")

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        last_error = None
        for attempt in range(3):
            try:
                response = genai.embed_content(
                    model=self.model,
                    content=texts,
                )
                return self._extract_vectors(response)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                wait_sec = 30 if ("429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc)) else 10
                if attempt < 2:
                    time.sleep(wait_sec)
                    continue
                raise RuntimeError(f"Gemini embedding failed: {exc}") from exc
        raise RuntimeError(f"Gemini embedding failed: {last_error}")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start:start + self.batch_size]
            vectors.extend(self._embed_batch(batch))
            if start + self.batch_size < len(texts):
                time.sleep(1)
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self._embed_batch([text])[0]
