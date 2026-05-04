"""SemanticRecall — Chroma (3.11–3.13) lub prosty fallback w pamięci (np. Python 3.14 bez Chroma)."""

from __future__ import annotations

import hashlib
import math
from typing import Any, List, Mapping, Sequence

_EMBED_DIM = 64


def _hash_embedding(text: str) -> List[float]:
    raw = hashlib.sha256(text.encode("utf-8")).digest()
    vec: list[float] = []
    for i in range(_EMBED_DIM):
        b0 = raw[i % len(raw)]
        b1 = raw[(i + 1) % len(raw)]
        n = (b0 << 8) | b1
        vec.append((n / 65535.0) * 2.0 - 1.0)
    nrm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / nrm for x in vec]


def _recall_memory_order(documents: List[str], query: str, k: int) -> List[str]:
    if not documents:
        return []
    ql = query.strip().lower()
    if not ql:
        return list(documents)[:k]
    scored: list[tuple[int, int, str]] = []
    for i, d in enumerate(documents):
        dl = d.lower()
        pri = 0 if ql in dl else 1
        overlap = len(set(ql.split()) & set(dl.split())) if ql.split() else 0
        scored.append((pri, -overlap, d))
    scored.sort(key=lambda t: (t[0], t[1]))
    out: list[str] = []
    for _, _, d in scored:
        if d not in out:
            out.append(d)
        if len(out) >= k:
            break
    return out


class SemanticRecall:
    """Dwie kolekcje: `conversations`, `knowledge_base` (DOK-11)."""

    def __init__(self, *, persist_directory: str | None = None) -> None:
        self._mode: str = "chroma"
        self._conv_docs: List[str] = []
        self._kb_docs: List[str] = []
        self._conv: Any = None
        self._kb: Any = None
        try:
            import chromadb  # type: ignore[import-untyped]

            if persist_directory:
                self._client = chromadb.PersistentClient(path=persist_directory)
            else:
                self._client = chromadb.EphemeralClient()

            self._conv = self._client.get_or_create_collection(
                name="conversations",
                metadata={"hnsw:space": "cosine"},
            )
            self._kb = self._client.get_or_create_collection(
                name="knowledge_base",
                metadata={"hnsw:space": "cosine"},
            )
        except Exception:
            self._mode = "memory"
            self._client = None
            self._conv = None
            self._kb = None

    @property
    def conversations(self) -> Any:
        return self._conv

    @property
    def knowledge_base(self) -> Any:
        return self._kb

    def add_conversation_chunks(self, *, ids: Sequence[str], documents: Sequence[str]) -> None:
        if self._mode == "memory":
            self._conv_docs.extend(str(d) for d in documents)
            return
        embs = [_hash_embedding(d) for d in documents]
        self._conv.add(ids=list(ids), documents=list(documents), embeddings=embs)

    def add_knowledge_chunks(
        self,
        *,
        ids: Sequence[str],
        documents: Sequence[str],
        metadatas: Sequence[Mapping[str, Any]] | None = None,
    ) -> None:
        if self._mode == "memory":
            self._kb_docs.extend(str(d) for d in documents)
            return
        embs = [_hash_embedding(d) for d in documents]
        kwargs: dict[str, Any] = {"ids": list(ids), "documents": list(documents), "embeddings": embs}
        if metadatas is not None:
            kwargs["metadatas"] = list(metadatas)
        self._kb.add(**kwargs)

    def recall_conversations(self, query: str, k: int = 4) -> List[str]:
        if self._mode == "memory":
            return _recall_memory_order(self._conv_docs, query, max(1, k))
        qe = _hash_embedding(query)
        r = self._conv.query(query_embeddings=[qe], n_results=max(1, k))
        docs = r.get("documents") or []
        if docs and isinstance(docs[0], list):
            return [d for d in docs[0] if isinstance(d, str)]
        return []

    def recall_knowledge(self, query: str, k: int = 4) -> List[str]:
        if self._mode == "memory":
            return _recall_memory_order(self._kb_docs, query, max(1, k))
        qe = _hash_embedding(query)
        r = self._kb.query(query_embeddings=[qe], n_results=max(1, k))
        docs = r.get("documents") or []
        if docs and isinstance(docs[0], list):
            return [d for d in docs[0] if isinstance(d, str)]
        return []


__all__ = ["SemanticRecall", "_hash_embedding"]
