"""Narzędzia MCP wymagające pełnego AppContext (screen_capture)."""

from __future__ import annotations

import logging
from typing import Any, Dict

_logger = logging.getLogger(__name__)

_SCFAIL_ASSISTANT = (
    "Narzędzie screen_capture zwróciło błąd. W odpowiedzi użytkownikowi **wymień treść pola `error`** "
    "(parafraza OK, ale zachowaj konkret: pip install, klucze w YAML, GET /api/v1/status). "
    "**Zabronione:** ogólniki w stylu «nie mogę analizować ekranu» bez przekazania tych kroków. "
    "Nie twierdź, że «nie masz narzędzia zrzutu», jeśli błąd mówi o potoku wizji / OCR / VLM."
)


def _screen_capture_fail(payload: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(payload)
    out["ok"] = False
    out["assistant_instruction"] = _SCFAIL_ASSISTANT
    return out


_TOOL_SCREEN_CAPTURE = {
    "type": "function",
    "function": {
        "name": "screen_capture",
        "description": (
            "Wykonuje zrzut ekranu użytkownika i zwraca opis sceny oraz tekst OCR (gdy potok wizji jest włączony). "
            "Używaj przy pytaniach „co widzisz na ekranie”. "
            "Jeśli wynik JSON ma ok=true — **najpierw przeczytaj pole `summary`**, potem `description` i `ocr_text`. "
            "Opisz ekran po polsku na tej podstawie; nie twierdź, że nie widzisz ekranu. "
            "Gdy ok=false — w odpowiedzi **cytuj lub streść pole `error`**, nie zastępuj go ogólną wymówką."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "focus_cursor": {
                    "type": "boolean",
                    "description": "Gdy true — preferuj analizę pod kursor (heurystyka: silniejszy OCR).",
                },
                "prompt": {
                    "type": "string",
                    "description": "Opcjonalne pytanie do analizy obrazu (obecnie: kontekst opisowy).",
                },
                "monitor_index": {
                    "type": "integer",
                    "description": "Indeks monitora (0 = domyślny).",
                },
            },
        },
    },
}


def register_screen_capture_tool(ctx: Any) -> None:
    reg = ctx.tool_registry

    async def tool_screen_capture(
        focus_cursor: bool = False,
        prompt: str = "",
        monitor_index: int = 0,
        **_: Any,
    ) -> Dict[str, Any]:
        cap = getattr(ctx, "screen_capture", None)
        vp = getattr(ctx, "vision_pipeline", None)
        if cap is None:
            return _screen_capture_fail({"error": "screen_capture niedostępny (backend bez modułu capture)"})
        try:
            png = await cap.capture_png(monitor_index=int(monitor_index))
        except Exception as exc:
            return _screen_capture_fail({"error": str(exc)})
        if vp is None:
            return _screen_capture_fail(
                {
                    "error": (
                        "Potok wizji nie działa — brak działającego VLM i OCR. "
                        "Opcja A (OCR, zwykle najlżejsza): z korzenia repo, aktywny venv backendu — "
                        "`pip install -r requirements-vision.txt`, w config.yaml `ocr.enabled: true` "
                        "(przy problemach z CUDA ustaw `ocr.use_gpu: false`), restart uvicorn. "
                        "Opcja B: `vlm.enabled: true` + torch/transformers + Moondream (docs/ENV_SETUP.md). "
                        "Diagnostyka: GET /api/v1/status → vision_pipeline.available, ocr.engine_initialized, vlm.engine_initialized."
                    ),
                }
            )
        try:
            result = await vp.analyze_png(png)
        except Exception as exc:
            _logger.warning("screen_capture: analyze_png failed: %s", exc, exc_info=True)
            return _screen_capture_fail(
                {
                    "error": (
                        f"Zrzut ekranu wykonany ({len(png)} bajtów PNG), ale analiza obrazu (OCR/VLM) się nie powiodła: {exc}. "
                        "Sprawdź logi backendu i easyocr/torch."
                    ),
                }
            )

        description = (result.vlm_text or "").strip()
        ocr_text = (result.ocr_text or "").strip()
        ocr_ran = result.ocr_ran
        meta_note = ""
        if focus_cursor and not ocr_ran:
            meta_note = "focus_cursor: pełny crop pod kursor wymaga przyszłej integracji pyautogui."

        summary = (result.merged_context() or "").strip()
        if not summary:
            summary = (
                "Na zrzucie nie rozpoznano tekstu (OCR pusty). "
                "VLM jest wyłączony lub nie zwrócił opisu — użytkownik może opisać ekran słownie."
            )

        out: Dict[str, Any] = {
            "ok": True,
            "description": description or "(brak opisu VLM)",
            "ocr_text": ocr_text,
            "ocr_ran": ocr_ran,
            "summary": summary,
            "cursor_focused": bool(focus_cursor),
        }
        if prompt and str(prompt).strip():
            out["user_question_echo"] = str(prompt).strip()
        if meta_note:
            out["note"] = meta_note

        _logger.info(
            "screen_capture ok: png=%sB ocr_ran=%s ocr_len=%s vlm_len=%s",
            len(png),
            ocr_ran,
            len(ocr_text),
            len(description),
        )
        return out

    reg.register("screen_capture", _TOOL_SCREEN_CAPTURE, tool_screen_capture, replace=True)


def register_context_dependent_mcp_tools(ctx: Any) -> None:
    """Po zbudowaniu AppContext — narzędzia zależne od capture/VLM.

    `screen_capture` musi być zarejestrowane także gdy `mcp.enabled: false` (tylko wyłącza web_search itd.).
    """
    register_screen_capture_tool(ctx)


__all__ = ["register_context_dependent_mcp_tools", "register_screen_capture_tool", "_TOOL_SCREEN_CAPTURE"]
