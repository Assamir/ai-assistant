"""KnowledgeIngester — skan katalogu, chunking, zapis do ``SemanticRecall.knowledge_base`` (T8)."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Collection, Iterable

from backend.memory.semantic_recall import SemanticRecall

_logger = logging.getLogger(__name__)

_DEFAULT_SKIP = frozenset(
    {".git", "__pycache__", "node_modules", ".venv", "venv", ".pytest_cache", ".mypy_cache"}
)
_DEFAULT_EXT = frozenset({".md", ".markdown", ".txt"})


def chunk_text(text: str, *, max_chars: int, overlap: int) -> list[str]:
    """Łączy akapity (``\\n\\n``) w chunki do ``max_chars``; długie akapity dzieli ze ``overlap``."""
    raw = text.strip()
    if not raw:
        return []
    mc = max(1, int(max_chars))
    ov = max(0, min(int(overlap), mc // 2))
    step = max(1, mc - ov)
    paragraphs = [p.strip() for p in raw.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [raw]
    chunks: list[str] = []
    buf = ""
    for p in paragraphs:
        if len(p) > mc:
            if buf:
                chunks.append(buf)
                buf = ""
            start = 0
            while start < len(p):
                chunks.append(p[start : start + mc])
                start += step
            continue
        cand = f"{buf}\n\n{p}" if buf else p
        if len(cand) <= mc:
            buf = cand
            continue
        if buf:
            chunks.append(buf)
        buf = p
    if buf:
        chunks.append(buf)
    return chunks


def _path_touches_skipped(path: Path, skip_names: Collection[str]) -> bool:
    return any(part in skip_names for part in path.parts)


@dataclass
class KnowledgeIngester:
    recall: SemanticRecall
    chunk_size: int = 1200
    chunk_overlap: int = 200
    max_total_chunks: int = 8_000
    extensions: frozenset[str] = field(default_factory=lambda: frozenset(_DEFAULT_EXT))
    skip_dir_names: frozenset[str] = field(default_factory=lambda: frozenset(_DEFAULT_SKIP))

    def ingest_directory(self, root: str | Path, *, relative_to: str | Path | None = None) -> int:
        root_p = Path(root).resolve()
        base = Path(relative_to).resolve() if relative_to is not None else root_p
        total = 0
        for path in self._iter_eligible_files(root_p):
            total += self.ingest_file(path, base=base)
        self.recall.prune_knowledge_base(self.max_total_chunks)
        return total

    def ingest_file(self, path: Path, *, base: Path) -> int:
        path = path.resolve()
        try:
            rel = path.relative_to(base)
        except ValueError:
            rel = Path(path.name)
        rel_s = str(rel).replace("\\", "/")
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            _logger.debug("ingest skip %s: %s", path, exc)
            return 0
        self.recall.remove_knowledge_chunks_where({"source_path": rel_s})
        parts = chunk_text(text, max_chars=self.chunk_size, overlap=self.chunk_overlap)
        if not parts:
            return 0
        ids = [f"kb:{rel_s}:{i}" for i in range(len(parts))]
        metas = [{"source_path": rel_s, "chunk_index": i} for i in range(len(parts))]
        self.recall.add_knowledge_chunks(ids=ids, documents=parts, metadatas=metas)
        return len(parts)

    def _iter_eligible_files(self, root: Path) -> Iterable[Path]:
        if root.is_file():
            if _path_touches_skipped(root, self.skip_dir_names):
                return
            if root.suffix.lower() in self.extensions:
                yield root
            return
        if not root.is_dir():
            return
        for p in root.rglob("*"):
            if p.is_dir():
                continue
            if _path_touches_skipped(p, self.skip_dir_names):
                continue
            if p.suffix.lower() not in self.extensions:
                continue
            yield p


class KnowledgeDirectoryWatcher:
    """Watcher (watchdog): po zmianie pliku — ponowny ``ingest_directory`` z debounce."""

    def __init__(
        self,
        ingester: KnowledgeIngester,
        directory: str | Path,
        *,
        debounce_seconds: float = 1.0,
    ) -> None:
        self._ingester = ingester
        self._directory = Path(directory).resolve()
        self._debounce = float(debounce_seconds)
        self._observer: object | None = None
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def _run_ingest(self) -> None:
        try:
            n = self._ingester.ingest_directory(self._directory)
            _logger.info("knowledge ingest (%s): %s chunks", self._directory, n)
        except Exception as exc:  # pragma: no cover — log i dalej
            _logger.warning("knowledge ingest failed: %s", exc)

    def _schedule(self) -> None:
        with self._lock:
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(self._debounce, self._run_ingest)
            self._timer.daemon = True
            self._timer.start()

    def start(self) -> None:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer

        root = self._directory

        class _Handler(FileSystemEventHandler):
            def __init__(self, outer: KnowledgeDirectoryWatcher) -> None:
                self._outer = outer

            def on_any_event(self, event):  # type: ignore[no-untyped-def]
                if event.is_directory:
                    return
                p = str(getattr(event, "src_path", "") or "").lower()
                if any(x in p for x in (".git", "__pycache__", "node_modules")):
                    return
                self._outer._schedule()

        obs = Observer()
        obs.schedule(_Handler(self), str(root), recursive=True)
        obs.start()
        self._observer = obs

    def stop(self) -> None:
        if self._observer is not None:
            self._observer.stop()  # type: ignore[union-attr]
            self._observer.join(timeout=5.0)  # type: ignore[union-attr]
            self._observer = None
        with self._lock:
            if self._timer:
                self._timer.cancel()
                self._timer = None


__all__ = ["KnowledgeIngester", "KnowledgeDirectoryWatcher", "chunk_text"]
