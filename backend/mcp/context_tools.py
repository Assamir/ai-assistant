"""Narzędzia MCP wymagające pełnego AppContext (screen_capture)."""

from __future__ import annotations

from typing import Any, Dict

_TOOL_SCREEN_CAPTURE = {
    "type": "function",
    "function": {
        "name": "screen_capture",
        "description": (
            "Robi zrzut ekranu i zwraca opis (VLM) oraz opcjonalnie OCR z potoku wizji. "
            "Używaj przy pytaniach „co widzisz na ekranie”."
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
            return {"ok": False, "error": "screen_capture niedostępny"}
        try:
            png = await cap.capture_png(monitor_index=int(monitor_index))
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        description = ""
        ocr_text = ""
        ocr_ran = False
        if vp is not None:
            try:
                result = await vp.analyze_png(png)
                description = (result.vlm_text or "").strip()
                ocr_text = (result.ocr_text or "").strip()
                ocr_ran = result.ocr_ran
            except Exception as exc:
                description = f"(błąd wizji: {exc})"
        elif prompt:
            description = "(vision_pipeline wyłączony — brak opisu VLM)"
        meta_note = ""
        if focus_cursor and not ocr_ran:
            meta_note = "focus_cursor: pełny crop pod kursor wymaga przyszłej integracji pyautogui."
        out: Dict[str, Any] = {
            "ok": True,
            "description": description or "(brak opisu)",
            "ocr_text": ocr_text,
            "cursor_focused": bool(focus_cursor),
        }
        if meta_note:
            out["note"] = meta_note
        return out

    reg.register("screen_capture", _TOOL_SCREEN_CAPTURE, tool_screen_capture, replace=True)


def register_context_dependent_mcp_tools(ctx: Any) -> None:
    """Po zbudowaniu AppContext — narzędzia zależne od capture/VLM."""
    if not ctx.config.mcp.enabled:
        return
    register_screen_capture_tool(ctx)


__all__ = ["register_context_dependent_mcp_tools", "register_screen_capture_tool", "_TOOL_SCREEN_CAPTURE"]
