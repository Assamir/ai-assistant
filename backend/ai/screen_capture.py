"""Zrzuty ekranu (DXcam → pyautogui) — T5 dzień 1; mock dla testów."""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import re
import sys
from typing import Literal, Optional

from backend.config.schema import MonitorInfo
from backend.core.interfaces import BaseScreenCapture

logger = logging.getLogger(__name__)

# 1×1 PNG — bez zewnętrznych bibliotek (MockScreenCapture).
MINIMAL_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


class ScreenCaptureError(RuntimeError):
    """Błąd pojedynczego zrzutu lub konfiguracji monitora."""


class ScreenCaptureUnavailable(ScreenCaptureError):
    """Brak zainstalowanych backendów (dxcam / pyautogui + Pillow)."""


_DXCAM_LINE_RE = re.compile(
    r"Device\[(\d+)\]\s+Output\[(\d+)\]:\s+Res:\((\d+),\s*(\d+)\).*Primary:(True|False)"
)


def parse_dxcam_output_info(text: str) -> list[MonitorInfo]:
    """Parsuje `dxcam.output_info()` → lista `MonitorInfo` z liniowym `index`."""
    monitors: list[MonitorInfo] = []
    for line in text.splitlines():
        m = _DXCAM_LINE_RE.search(line.strip())
        if not m:
            continue
        device_idx = int(m.group(1))
        output_idx = int(m.group(2))
        width, height = int(m.group(3)), int(m.group(4))
        is_primary = m.group(5) == "True"
        monitors.append(
            MonitorInfo(
                index=len(monitors),
                device_idx=device_idx,
                output_idx=output_idx,
                width=width,
                height=height,
                is_primary=is_primary,
                label=f"Device {device_idx} · Output {output_idx}",
            )
        )
    return monitors


def _pyautogui_available() -> bool:
    try:
        import pyautogui  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError:
        return False
    return True


def _dxcam_probe_primary_dimensions() -> Optional[tuple[int, int]]:
    try:
        import dxcam
    except ImportError:
        return None
    cam = dxcam.create(output_idx=0, output_color="RGB")
    try:
        frame = cam.grab(new_frame_only=False)
        if frame is None:
            return None
        height, width = frame.shape[:2]
        return width, height
    except Exception:
        return None
    finally:
        try:
            cam.release()
        except Exception:
            pass


def _detect_best_backend() -> Optional[Literal["dxcam", "pyautogui"]]:
    if sys.platform == "win32":
        try:
            import dxcam
        except ImportError:
            dxcam = None  # type: ignore[assignment]
        if dxcam is not None:
            try:
                raw = dxcam.output_info()
                text = str(raw or "")
                parsed = parse_dxcam_output_info(text)
                if parsed:
                    return "dxcam"
                dims = _dxcam_probe_primary_dimensions()
                if dims is not None:
                    return "dxcam"
            except Exception:
                logger.debug("DXcam detection failed; trying pyautogui if available.", exc_info=True)
    if _pyautogui_available():
        return "pyautogui"
    return None


def _list_monitors_dxcam_sync() -> list[MonitorInfo]:
    import dxcam

    text = str(dxcam.output_info() or "")
    monitors = parse_dxcam_output_info(text)
    if monitors:
        return monitors
    dims = _dxcam_probe_primary_dimensions()
    if dims is None:
        raise ScreenCaptureError("DXcam: nie udało się odczytać listy monitorów ani pojedynczej klatki.")
    w, h = dims
    return [
        MonitorInfo(
            index=0,
            device_idx=0,
            output_idx=0,
            width=w,
            height=h,
            is_primary=True,
            label="Output 0 (probe)",
        )
    ]


def _list_monitors_pyautogui_sync() -> list[MonitorInfo]:
    import pyautogui

    w, h = pyautogui.size()
    return [
        MonitorInfo(
            index=0,
            device_idx=0,
            output_idx=0,
            width=int(w),
            height=int(h),
            is_primary=True,
            label="primary",
        )
    ]


def _capture_dxcam_png_sync(mon: MonitorInfo) -> bytes:
    import dxcam
    from PIL import Image

    cam = dxcam.create(
        device_idx=mon.device_idx,
        output_idx=mon.output_idx,
        output_color="RGB",
    )
    try:
        frame = cam.grab(new_frame_only=False)
        if frame is None:
            raise ScreenCaptureError("DXcam zwrócił None (brak klatki).")
        img = Image.fromarray(frame)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    finally:
        try:
            cam.release()
        except Exception:
            pass


def _capture_pyautogui_png_sync(monitor_index: int) -> bytes:
    if monitor_index != 0:
        raise ScreenCaptureError("pyautogui: obsługiwany jest wyłącznie monitor_index=0.")
    import pyautogui

    img = pyautogui.screenshot()
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class DesktopScreenCapture(BaseScreenCapture):
    """DXcam (Windows) z fallbackiem do pyautogui; wywołania sync w wątku."""

    def __init__(self) -> None:
        self._backend: Optional[Literal["dxcam", "pyautogui"]] = None

    def _ensure_backend(self) -> Literal["dxcam", "pyautogui"]:
        if self._backend is None:
            b = _detect_best_backend()
            if b is None:
                raise ScreenCaptureUnavailable(
                    "Brak backendu zrzutu ekranu. Na Windows: pip install dxcam. "
                    "Alternatywa: pip install pyautogui pillow."
                )
            self._backend = b
        return self._backend

    def _list_monitors_sync(self) -> list[MonitorInfo]:
        b = self._ensure_backend()
        if b == "dxcam":
            return _list_monitors_dxcam_sync()
        return _list_monitors_pyautogui_sync()

    def _capture_png_sync(self, monitor_index: int) -> bytes:
        self._ensure_backend()
        monitors = self._list_monitors_sync()
        if monitor_index < 0 or monitor_index >= len(monitors):
            raise ScreenCaptureError(
                f"monitor_index={monitor_index} poza zakresem (0..{max(0, len(monitors) - 1)})"
            )
        mon = monitors[monitor_index]
        if self._backend == "dxcam":
            return _capture_dxcam_png_sync(mon)
        return _capture_pyautogui_png_sync(monitor_index)

    async def list_monitors(self) -> list[MonitorInfo]:
        return await asyncio.to_thread(self._list_monitors_sync)

    async def capture_png(self, *, monitor_index: int = 0) -> bytes:
        return await asyncio.to_thread(self._capture_png_sync, monitor_index)


class MockScreenCapture(BaseScreenCapture):
    """Statyczna klatka / lista monitorów — strategia testów z planszej części dokumentacji."""

    def __init__(
        self,
        *,
        png_payload: Optional[bytes] = None,
        monitors: Optional[list[MonitorInfo]] = None,
    ) -> None:
        self._png = png_payload if png_payload is not None else MINIMAL_PNG_BYTES
        self._monitors = monitors or [
            MonitorInfo(index=0, width=1920, height=1080, is_primary=True, label="mock")
        ]

    async def list_monitors(self) -> list[MonitorInfo]:
        return list(self._monitors)

    async def capture_png(self, *, monitor_index: int = 0) -> bytes:
        if monitor_index < 0 or monitor_index >= len(self._monitors):
            raise ScreenCaptureError(
                f"monitor_index={monitor_index} poza zakresem (0..{len(self._monitors) - 1})"
            )
        return self._png


__all__ = [
    "MINIMAL_PNG_BYTES",
    "DesktopScreenCapture",
    "MockScreenCapture",
    "ScreenCaptureError",
    "ScreenCaptureUnavailable",
    "parse_dxcam_output_info",
]
