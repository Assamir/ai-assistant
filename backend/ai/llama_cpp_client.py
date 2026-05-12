"""Klient LLM oparty na embedded llama-cpp-python (provider=`local`).

Model GGUF ładowany w procesie backendu, bez LM Studio. Chat template oraz
specjalne tokeny czytane z metadata GGUF (`tokenizer.chat_template`) — żaden
manualny preset nie jest wymagany.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

from backend.ai._openai_parsing import _try_parse_inline_tool_calls
from backend.ai.llm_client import ChatCompletionResult
from backend.config.schema import LLMConfig, LocalLLMConfig
from backend.core.interfaces import BaseLLMClient

_logger = logging.getLogger(__name__)

# Factory: opcjonalna fabryka do iniekcji w testach (sygnatura: () -> Llama-like).
LlamaFactory = Callable[[], Any]


class LlamaCppLocalClient(BaseLLMClient):
    """Adapter `BaseLLMClient` korzystający z biblioteki llama-cpp-python."""

    def __init__(
        self,
        llm_config: LLMConfig,
        *,
        model_path: str,
        llama_factory: Optional[LlamaFactory] = None,
    ) -> None:
        self._cfg = llm_config
        self._local: LocalLLMConfig = llm_config.local
        self._model_path = model_path
        self._llama_factory = llama_factory
        self._llm: Any = None
        self._init_lock = asyncio.Lock()

    # ---------- lifecycle ----------

    async def aclose(self) -> None:
        """Llama nie ma async close; oddajemy obiekt GC. Wywoływane przy hot-reload providera."""
        self._llm = None

    async def apply_llm_config(self, llm_config: LLMConfig, *, model_path: Optional[str] = None) -> None:
        """Hot-reload. Jeśli zmienia się model_path lub parametry — odbuduj engine."""
        new_path = model_path or self._model_path
        params_changed = (
            llm_config.local.n_gpu_layers != self._local.n_gpu_layers
            or llm_config.local.n_ctx != self._local.n_ctx
            or llm_config.local.n_batch != self._local.n_batch
        )
        path_changed = new_path != self._model_path
        self._cfg = llm_config
        self._local = llm_config.local
        self._model_path = new_path
        if params_changed or path_changed:
            self._llm = None  # następne wywołanie odpali _ensure_loaded

    # ---------- engine ----------

    def _build_llama(self) -> Any:
        """Tworzy obiekt Llama. Wyciągnięte żeby łatwo było zmockować w testach."""
        if self._llama_factory is not None:
            return self._llama_factory()
        try:
            from llama_cpp import Llama
        except ImportError as exc:
            raise RuntimeError(
                "llama-cpp-python nie jest zainstalowany. "
                "Zainstaluj: pip install llama-cpp-python "
                "(z CUDA: użyj prebuilt wheel z https://abetlen.github.io/llama-cpp-python/)."
            ) from exc
        _logger.info(
            "Ładowanie GGUF: %s (n_gpu_layers=%s, n_ctx=%s)",
            self._model_path, self._local.n_gpu_layers, self._local.n_ctx,
        )
        return Llama(
            model_path=self._model_path,
            n_gpu_layers=self._local.n_gpu_layers,
            n_ctx=self._local.n_ctx,
            n_batch=self._local.n_batch,
            verbose=False,
            # chat_format=None — llama-cpp-python sam czyta tokenizer.chat_template z GGUF
        )

    async def _ensure_loaded(self) -> Any:
        if self._llm is not None:
            return self._llm
        async with self._init_lock:
            if self._llm is not None:
                return self._llm
            loop = asyncio.get_running_loop()
            self._llm = await loop.run_in_executor(None, self._build_llama)
            return self._llm

    # ---------- chat_completion (non-stream) ----------

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        *,
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: Optional[int] = None,
    ) -> ChatCompletionResult:
        llm = await self._ensure_loaded()
        kwargs: Dict[str, Any] = {
            "messages": messages,
            "temperature": self._cfg.temperature,
            "max_tokens": int(max_tokens) if max_tokens is not None else int(self._cfg.max_tokens),
            "stream": False,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(None, lambda: llm.create_chat_completion(**kwargs))

        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        content = msg.get("content")
        content_str = content if isinstance(content, str) else ""
        tool_calls = msg.get("tool_calls")
        tc_list: Optional[List[Dict[str, Any]]] = (
            tool_calls if isinstance(tool_calls, list) and tool_calls else None
        )
        # Fallback: niektóre GGUF wypisują tool calls jako tekst (np. Hermes/Qwen)
        if tc_list is None and content_str:
            cleaned, parsed = _try_parse_inline_tool_calls(content_str)
            if parsed:
                tc_list = parsed
                content_str = cleaned

        finish_reason = choice.get("finish_reason")
        return ChatCompletionResult(
            content=content_str,
            finish_reason=finish_reason if isinstance(finish_reason, str) else None,
            tool_calls=tc_list,
            raw=data,
        )

    # ---------- generate_response (high-level) ----------

    async def generate_response(
        self,
        prompt: str,
        history: Optional[List[Dict[str, Any]]] = None,
        *,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        msgs: List[Dict[str, Any]] = []
        if history:
            for item in history:
                role = item.get("role")
                content = item.get("content")
                if isinstance(role, str) and content is not None:
                    msgs.append({"role": role, "content": content})
        msgs.append({"role": "user", "content": prompt})
        result = await self.chat_completion(msgs, tools=tools)
        return result.content

    # ---------- stream_response ----------

    async def stream_response(
        self,
        prompt: str,
        history: Optional[List[Dict[str, Any]]] = None,
        *,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncIterator[str]:
        llm = await self._ensure_loaded()
        msgs: List[Dict[str, Any]] = []
        if history:
            for item in history:
                role = item.get("role")
                content = item.get("content")
                if isinstance(role, str) and content is not None:
                    msgs.append({"role": role, "content": content})
        msgs.append({"role": "user", "content": prompt})

        kwargs: Dict[str, Any] = {
            "messages": msgs,
            "temperature": self._cfg.temperature,
            "max_tokens": int(self._cfg.max_tokens),
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        # llama_cpp.Llama.create_chat_completion(stream=True) zwraca SYNC generator.
        # Pomost: czytamy w wątku roboczym, pchamy chunki do asyncio.Queue.
        queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def _worker() -> None:
            try:
                for chunk in llm.create_chat_completion(**kwargs):
                    choices = chunk.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    piece = delta.get("content")
                    if piece:
                        asyncio.run_coroutine_threadsafe(queue.put(piece), loop)
            except Exception:
                _logger.exception("llama-cpp stream worker error")
            finally:
                asyncio.run_coroutine_threadsafe(queue.put(None), loop)

        threading.Thread(target=_worker, daemon=True).start()

        while True:
            item = await queue.get()
            if item is None:
                break
            yield item


__all__ = ["LlamaCppLocalClient", "LlamaFactory"]
