"""generate_document — zapis MD/HTML w `{content_root}/documents` (sandbox)."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from backend.mcp.sandbox import SandboxValidator, SandboxViolation

try:
    import markdown as _md_lib

    def _md_to_html(text: str) -> str:
        html = _md_lib.markdown(
            text,
            extensions=["tables", "fenced_code", "nl2br"],
        )
        # convert <pre><code class="language-mermaid">…</code></pre>
        # to <div class="mermaid">…</div> so mermaid.js renders it
        html = re.sub(
            r'<pre><code class="language-mermaid">(.*?)</code></pre>',
            lambda m: f'<div class="mermaid">{m.group(1)}</div>',
            html,
            flags=re.DOTALL,
        )
        return html

except ImportError:
    def _md_to_html(text: str) -> str:
        escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return f"<pre style='white-space:pre-wrap'>{escaped}</pre>"


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<title>{{TITLE}}</title>
<style>
  body { background:#1a1a2e; color:#e0e0e0; font-family:system-ui,sans-serif;
         max-width:900px; margin:0 auto; padding:2rem; line-height:1.6; }
  h1,h2,h3 { color:#a78bfa; }
  table { border-collapse:collapse; width:100%; margin:1rem 0; }
  th,td { border:1px solid #3f3f5f; padding:0.5rem 1rem; text-align:left; }
  th { background:#2d2d4e; }
  code { background:#2d2d4e; padding:0.1em 0.4em; border-radius:4px; }
  pre code { background:transparent; padding:0; }
  pre { background:#2d2d4e; padding:1rem; border-radius:6px; overflow-x:auto; }
  blockquote { border-left:3px solid #a78bfa; margin:0; padding-left:1rem; color:#b8b0d0; }
  .mermaid { background:#2d2d4e; border-radius:6px; padding:1rem; margin:1rem 0; }
  @media print { body { background:white; color:black; } }
</style>
</head>
<body>
{{CONTENT}}
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>mermaid.initialize({ startOnLoad: true, theme: 'dark' });</script>
</body>
</html>"""

_TOOL_GENERATE_DOCUMENT = {
    "type": "function",
    "function": {
        "name": "generate_document",
        "description": (
            "Zapisuje treść jako plik Markdown lub HTML w katalogu documents pod content_root. "
            "Używaj do raportów, porównań buildów, długich zestawień zamiast czytać je na głos."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Tytuł / temat dokumentu (krótki)."},
                "format": {
                    "type": "string",
                    "enum": ["md", "html"],
                    "description": "md = surowy markdown, html = szablon z nagłówkiem.",
                },
                "content": {"type": "string", "description": "Treść dokumentu."},
                "filename_hint": {
                    "type": "string",
                    "description": "Opcjonalny fragment nazwy pliku (slug); unikalność zapewnia timestamp.",
                },
            },
            "required": ["topic", "format", "content"],
        },
    },
}


def make_tool_generate_document(content_root: str):
    root = (content_root or ".").strip() or "."
    sandbox = SandboxValidator(root)

    def tool_generate_document(
        topic: str | None = None,
        content: str | None = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        fmt_raw = kwargs.get("format")
        fmt = fmt_raw if isinstance(fmt_raw, str) and fmt_raw in ("md", "html") else "md"
        hint_raw = kwargs.get("filename_hint")
        hint = hint_raw.strip() if isinstance(hint_raw, str) else ""
        t = topic.strip() if isinstance(topic, str) else ""
        if not t:
            return {"ok": False, "error": "pusty topic"}
        body = content if isinstance(content, str) else ""
        slug_base = hint if hint else re.sub(r"[^\w]+", "_", t.lower(), flags=re.UNICODE).strip("_")[:40]
        slug = slug_base or "doc"
        timestamp = datetime.now().strftime("%Y-%m-%d-%H.%M")
        filename = f"document_{slug}_{timestamp}.{fmt}"
        try:
            relative_dir = "documents"
            docs_parent = sandbox.validate_path(relative_dir)
        except SandboxViolation as exc:
            return {"ok": False, "error": str(exc)}
        docs_parent.mkdir(parents=True, exist_ok=True)
        relative_file = f"{relative_dir}/{filename}"
        try:
            out_path = sandbox.validate_path(relative_file)
        except SandboxViolation as exc:
            return {"ok": False, "error": str(exc)}
        if fmt == "html":
            html_body = _md_to_html(body)
            full_content = HTML_TEMPLATE.replace("{{CONTENT}}", html_body).replace("{{TITLE}}", t)
        else:
            full_content = body
        try:
            Path(out_path).write_text(full_content, encoding="utf-8")
        except OSError as exc:
            return {"ok": False, "error": str(exc)}
        st = Path(out_path).stat()
        return {
            "ok": True,
            "file_path": str(out_path),
            "filename": filename,
            "file_size": st.st_size,
            "format": fmt,
        }

    return tool_generate_document


__all__ = ["HTML_TEMPLATE", "_TOOL_GENERATE_DOCUMENT", "make_tool_generate_document"]
