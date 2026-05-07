"""Potok VLM + warunkowy OCR (słowa kluczowe w opisie VLM). T5 dzień 3."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from backend.config.schema import OCRConfig
from backend.core.interfaces import BaseOCREngine, BaseVLMAnalyzer

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VisionFrameResult:
    """Wynik analizy jednej klatki (PNG)."""

    vlm_text: str
    ocr_text: str
    ocr_ran: bool

    def merged_context(self) -> str:
        """Tekst dla promptu LLM — VLM + opcjonalny blok OCR."""
        v = self.vlm_text.strip()
        o = self.ocr_text.strip()
        if not o:
            return v
        if not v:
            return f"[OCR]\n{o}"
        return f"{v}\n\n[OCR]\n{o}"


class DualVisionPipeline:
    """Najpierw VLM (jeśli jest), potem OCR wg `ocr.trigger_keywords`."""

    def __init__(
        self,
        *,
        vlm_engine: Optional[BaseVLMAnalyzer],
        ocr_engine: Optional[BaseOCREngine],
        ocr_config: OCRConfig,
    ) -> None:
        self._vlm = vlm_engine
        self._ocr = ocr_engine
        self._ocr_cfg = ocr_config

    def _should_run_ocr(self, vlm_text: str) -> bool:
        if self._ocr is None or not self._ocr_cfg.enabled:
            return False
        keywords = list(self._ocr_cfg.trigger_keywords)
        if self._vlm is None:
            return True
        if not keywords:
            return True
        hay = vlm_text.lower()
        return any(kw in hay for kw in keywords)

    async def analyze_png(self, image_data: bytes) -> VisionFrameResult:
        vlm_part = ""
        vlm_exc: Optional[Exception] = None
        if self._vlm is not None:
            try:
                vlm_part = await self._vlm.analyze_image(image_data) or ""
            except Exception as exc:
                vlm_exc = exc
                _logger.warning("VLM analyze_image failed — kontynuuję z OCR / pustym opisem", exc_info=True)
                vlm_part = ""

        ocr_part = ""
        ran = False
        ocr_exc: Optional[Exception] = None
        want_ocr = self._should_run_ocr(vlm_part)
        if self._ocr is not None and self._ocr_cfg.enabled and not want_ocr and vlm_exc is not None:
            want_ocr = True

        if want_ocr and self._ocr is not None:
            try:
                ocr_part = await self._ocr.extract_text(image_data)
                ran = True
            except Exception as exc:
                ocr_exc = exc
                _logger.warning("OCR extract_text failed — zwracam ewentualny wynik VLM", exc_info=True)
                ocr_part = ""
                ran = False

        if (vlm_part.strip() or (ocr_part or "").strip()):
            return VisionFrameResult(vlm_text=vlm_part, ocr_text=ocr_part, ocr_ran=ran)

        errors: list[str] = []
        if vlm_exc is not None:
            errors.append(f"VLM: {vlm_exc}")
        if ocr_exc is not None:
            errors.append(f"OCR: {ocr_exc}")
        if errors:
            raise RuntimeError("; ".join(errors)) from (vlm_exc if vlm_exc is not None else ocr_exc)
        raise RuntimeError("Analiza obrazu nie zwróciła treści (pusty wynik VLM i OCR).")


__all__ = ["DualVisionPipeline", "VisionFrameResult"]
