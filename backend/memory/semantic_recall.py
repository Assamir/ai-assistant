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

    def __init__(
        self,
        *,
        persist_directory: str | None = None,
        max_conversations: int = 10_000,
        collection_prefix: str = "",
    ) -> None:
        self._mode: str = "chroma"
        self._conv_docs: List[str] = []
        self._conv_metas: List[Mapping[str, Any]] = []
        self._conv_ingest_seq: int = 0
        self._kb_docs: List[str] = []
        self._kb_metas: List[Mapping[str, Any]] = []
        self._ingest_seq: int = 0
        self._max_conversations: int = max(0, int(max_conversations))
        self._conv: Any = None
        self._kb: Any = None
        _pfx = f"{collection_prefix}_" if collection_prefix else ""
        try:
            import chromadb  # type: ignore[import-untyped]

            if persist_directory:
                self._client = chromadb.PersistentClient(path=persist_directory)
            else:
                self._client = chromadb.EphemeralClient()

            self._conv = self._client.get_or_create_collection(
                name=f"{_pfx}conversations",
                metadata={"hnsw:space": "cosine"},
            )
            self._kb = self._client.get_or_create_collection(
                name=f"{_pfx}knowledge_base",
                metadata={"hnsw:space": "cosine"},
            )
        except Exception:
            self._mode = "memory"
            self._client = None
            self._conv = None
            self._kb = None
            self._kb_metas = []

    @property
    def conversations(self) -> Any:
        return self._conv

    @property
    def knowledge_base(self) -> Any:
        return self._kb

    def add_conversation_chunks(
        self,
        *,
        ids: Sequence[str],
        documents: Sequence[str],
        metadatas: Sequence[Mapping[str, Any]] | None = None,
    ) -> None:
        if self._mode == "memory":
            for i, d in enumerate(documents):
                self._conv_ingest_seq += 1
                m: dict[str, Any] = dict(metadatas[i]) if metadatas is not None and i < len(metadatas) else {}
                m["ingest_seq"] = self._conv_ingest_seq
                self._conv_docs.append(str(d))
                self._conv_metas.append(m)
            if self._max_conversations > 0:
                self.prune_conversations(self._max_conversations)
            return
        embs = [_hash_embedding(d) for d in documents]
        meta_list: list[dict[str, Any]] = []
        for i in range(len(documents)):
            self._conv_ingest_seq += 1
            m = dict(metadatas[i]) if metadatas is not None and i < len(metadatas) else {}
            m["ingest_seq"] = self._conv_ingest_seq
            meta_list.append(m)
        self._conv.add(ids=list(ids), documents=list(documents), embeddings=embs, metadatas=meta_list)
        if self._max_conversations > 0:
            self.prune_conversations(self._max_conversations)

    def add_knowledge_chunks(
        self,
        *,
        ids: Sequence[str],
        documents: Sequence[str],
        metadatas: Sequence[Mapping[str, Any]] | None = None,
    ) -> None:
        if self._mode == "memory":
            for i, d in enumerate(documents):
                self._ingest_seq += 1
                m: dict[str, Any] = dict(metadatas[i]) if metadatas is not None and i < len(metadatas) else {}
                m["ingest_seq"] = self._ingest_seq
                self._kb_docs.append(str(d))
                self._kb_metas.append(m)
            return
        embs = [_hash_embedding(d) for d in documents]
        meta_list: list[dict[str, Any]] = []
        for i in range(len(documents)):
            self._ingest_seq += 1
            m = dict(metadatas[i]) if metadatas is not None and i < len(metadatas) else {}
            m["ingest_seq"] = self._ingest_seq
            meta_list.append(m)
        self._kb.add(ids=list(ids), documents=list(documents), embeddings=embs, metadatas=meta_list)

    def remove_knowledge_chunks_where(self, where: Mapping[str, Any]) -> int:
        """Usuwa chunki ``knowledge_base``, których metadane spełniają równościowo wszystkie pary z ``where``."""

        def _meta_ok(m: Mapping[str, Any] | None) -> bool:
            if not m:
                return False
            return all(m.get(k) == v for k, v in where.items())

        if self._mode == "memory":
            new_docs: list[str] = []
            new_metas: list[Mapping[str, Any]] = []
            removed = 0
            for d, m in zip(self._kb_docs, self._kb_metas):
                if _meta_ok(m):
                    removed += 1
                    continue
                new_docs.append(d)
                new_metas.append(m)
            self._kb_docs = new_docs
            self._kb_metas = new_metas
            return removed
        data = self._kb.get(where=dict(where))
        ids = data.get("ids") or []
        if not ids:
            return 0
        self._kb.delete(ids=ids)
        return len(ids)

    def prune_knowledge_base(self, max_documents: int) -> None:
        """FIFO po ``ingest_seq`` / kolejności listy — utrzymuje co najwyżej ``max_documents`` chunków."""
        if max_documents < 0:
            return
        if self._mode == "memory":
            overflow = len(self._kb_docs) - max_documents
            if overflow > 0:
                del self._kb_docs[0:overflow]
                del self._kb_metas[0:overflow]
            return
        data = self._kb.get(include=["metadatas"])
        ids = data.get("ids") or []
        if len(ids) <= max_documents:
            return
        metas_raw = data.get("metadatas") or []
        indexed: list[tuple[int, str]] = []
        for i, doc_id in enumerate(ids):
            m = metas_raw[i] if i < len(metas_raw) else None
            seq = 0
            if isinstance(m, dict):
                try:
                    seq = int(m.get("ingest_seq") or 0)
                except (TypeError, ValueError):
                    seq = 0
            indexed.append((seq, doc_id))
        indexed.sort(key=lambda x: x[0])
        to_drop = len(ids) - max_documents
        drop_ids = [doc_id for _, doc_id in indexed[:to_drop]]
        if drop_ids:
            self._kb.delete(ids=drop_ids)

    def prune_conversations(self, max_documents: int) -> None:
        """FIFO po ``ingest_seq`` — utrzymuje co najwyżej ``max_documents`` chunków w conversations."""
        if max_documents < 0:
            return
        if self._mode == "memory":
            overflow = len(self._conv_docs) - max_documents
            if overflow > 0:
                del self._conv_docs[0:overflow]
                del self._conv_metas[0:overflow]
            return
        data = self._conv.get(include=["metadatas"])
        ids = data.get("ids") or []
        if len(ids) <= max_documents:
            return
        metas_raw = data.get("metadatas") or []
        indexed: list[tuple[int, str]] = []
        for i, doc_id in enumerate(ids):
            m = metas_raw[i] if i < len(metas_raw) else None
            seq = 0
            if isinstance(m, dict):
                try:
                    seq = int(m.get("ingest_seq") or 0)
                except (TypeError, ValueError):
                    seq = 0
            indexed.append((seq, doc_id))
        indexed.sort(key=lambda x: x[0])
        to_drop = len(ids) - max_documents
        drop_ids = [doc_id for _, doc_id in indexed[:to_drop]]
        if drop_ids:
            self._conv.delete(ids=drop_ids)

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
