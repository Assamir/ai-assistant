"""web_scraper + SandboxValidator URL (MCP-T-05 częściowo; bez Playwright MCP-T-06)."""

from __future__ import annotations

import pytest

from backend.config.schema import MCPConfig
from backend.mcp import web_scraper as web_scraper_mod
from backend.mcp.registry import build_default_tool_registry
from backend.mcp.sandbox import SandboxValidator, SandboxViolation


def test_sandbox_validate_url_ok():
    v = SandboxValidator(".")
    assert v.validate_url("https://example.com/path") == "https://example.com/path"


def test_sandbox_validate_url_rejects_scheme():
    v = SandboxValidator(".")
    with pytest.raises(SandboxViolation):
        v.validate_url("file:///etc/passwd")


def test_sandbox_path_outside_root(tmp_path):
    root = tmp_path / "content"
    root.mkdir()
    v = SandboxValidator(str(root))
    with pytest.raises(SandboxViolation):
        v.validate_path("../../outside.txt")


@pytest.mark.asyncio
async def test_web_scraper_static_html_mocked(monkeypatch, migrated_db_path):
    html = (
        "<html><head><title>T</title></head><body>"
        "<p>Hello <b>PoE2</b> league</p><script>bad()</script></body></html>"
    )

    async def fake_get(_url: str) -> str:
        return html

    monkeypatch.setattr(web_scraper_mod, "_http_get_html", fake_get)

    reg = build_default_tool_registry(db_path=migrated_db_path, mcp_cfg=MCPConfig(enabled=True))
    res = await reg.invoke("web_scraper", {"url": "https://example.com/wiki"})
    assert res["ok"] is True
    assert "PoE2" in res["text"]
    assert "bad()" not in res["text"]


@pytest.mark.asyncio
async def test_web_scraper_cache_second_call(monkeypatch, migrated_db_path):
    calls: list[str] = []

    async def fake_get(url: str) -> str:
        calls.append(url)
        return "<html><body>once</body></html>"

    monkeypatch.setattr(web_scraper_mod, "_http_get_html", fake_get)

    reg = build_default_tool_registry(db_path=migrated_db_path, mcp_cfg=MCPConfig(enabled=True))
    u = "https://example.com/same"
    a = await reg.invoke("web_scraper", {"url": u})
    b = await reg.invoke("web_scraper", {"url": u})
    assert a == b
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_web_scraper_host_allowlist(monkeypatch, migrated_db_path):
    async def fake_get(_url: str) -> str:
        return "<html><body>secret content here long enough for tests minimum threshold one two three four five</body></html>"

    monkeypatch.setattr(web_scraper_mod, "_http_get_html", fake_get)

    reg = build_default_tool_registry(
        db_path=migrated_db_path,
        mcp_cfg=MCPConfig(enabled=True, scraper_allowed_hosts=["example.com"]),
    )
    ok = await reg.invoke("web_scraper", {"url": "https://example.com/a"})
    assert ok["ok"] is True

    bad = await reg.invoke("web_scraper", {"url": "https://other.test/a"})
    assert bad["ok"] is False
    assert bad.get("error") == "host_not_allowed"


@pytest.mark.asyncio
async def test_web_scraper_host_allowlist_www_normalized(monkeypatch, migrated_db_path):
    async def fake_get(_url: str) -> str:
        return "<html><body>x</body></html>" * 50

    monkeypatch.setattr(web_scraper_mod, "_http_get_html", fake_get)

    reg = build_default_tool_registry(
        db_path=migrated_db_path,
        mcp_cfg=MCPConfig(enabled=True, scraper_allowed_hosts=["maxroll.gg"]),
    )
    res = await reg.invoke("web_scraper", {"url": "https://www.maxroll.gg/poe2"})
    assert res["ok"] is True


@pytest.mark.asyncio
async def test_web_scraper_disabled_without_mcp():
    reg = build_default_tool_registry(mcp_cfg=MCPConfig(enabled=False))
    names = {t["function"]["name"] for t in reg.openai_tools()}
    assert "web_scraper" not in names
