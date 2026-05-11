"""web_search + MCPCache w ToolRegistry."""

from __future__ import annotations

import pytest

from backend.config.schema import MCPConfig
from backend.mcp import web_search as web_search_mod
from backend.mcp.registry import build_default_tool_registry


@pytest.mark.asyncio
async def test_web_search_mocked_ddg(monkeypatch, migrated_db_path):
    monkeypatch.setattr(web_search_mod, "_sync_ddgs_text_results", lambda q, max_results=10: [])

    async def fake_fetch(params):  # type: ignore[no-untyped-def]
        assert "q" in params
        return {
            "AbstractText": "Test wiki",
            "Heading": "H",
            "AbstractURL": "https://example.com",
            "RelatedTopics": [{"Text": "First hit"}],
            "Answer": "",
        }

    monkeypatch.setattr(web_search_mod, "_ddg_instant_fetch", fake_fetch)

    reg = build_default_tool_registry(db_path=migrated_db_path, mcp_cfg=MCPConfig(enabled=True))
    res = await reg.invoke("web_search", {"query": "pillar of eternity"})
    assert res["ok"] is True
    assert res["abstract"] == "Test wiki"


@pytest.mark.asyncio
async def test_web_search_cache_second_call(monkeypatch, migrated_db_path):
    monkeypatch.setattr(web_search_mod, "_sync_ddgs_text_results", lambda q, max_results=10: [])

    bodies = [
        {"AbstractText": "once", "RelatedTopics": [], "Heading": "", "AbstractURL": ""},
        {"AbstractText": "twice", "RelatedTopics": [], "Heading": "", "AbstractURL": ""},
    ]
    fetched: list[bool] = []

    async def fake_fetch(_params):  # type: ignore[no-untyped-def]
        fetched.append(True)
        return bodies[len(fetched) - 1]

    monkeypatch.setattr(web_search_mod, "_ddg_instant_fetch", fake_fetch)

    reg = build_default_tool_registry(db_path=migrated_db_path, mcp_cfg=MCPConfig(enabled=True))
    a = await reg.invoke("web_search", {"query": "same"})
    b = await reg.invoke("web_search", {"query": "same"})
    assert a == b
    assert a["abstract"] == "once"
    assert len(fetched) == 1


@pytest.mark.asyncio
async def test_web_search_always_registered_even_when_mcp_disabled():
    reg = build_default_tool_registry(mcp_cfg=MCPConfig(enabled=False))
    names = sorted(t["function"]["name"] for t in reg.openai_tools())
    assert "web_search" in names


@pytest.mark.asyncio
async def test_web_search_ddgs_when_instant_empty(monkeypatch, migrated_db_path):
    async def empty_instant(_params):  # type: ignore[no-untyped-def]
        return {}

    monkeypatch.setattr(web_search_mod, "_ddg_instant_fetch", empty_instant)
    monkeypatch.setattr(
        web_search_mod,
        "_sync_ddgs_text_results",
        lambda q, max_results=10: [
            {"title": "PoE2 News", "url": "https://example.com/news", "snippet": "Latest league announcement."}
        ],
    )

    reg = build_default_tool_registry(db_path=migrated_db_path, mcp_cfg=MCPConfig(enabled=True))
    res = await reg.invoke("web_search", {"query": "path of exile 2"})
    assert res.get("ok") is True
    assert "Latest league" in res.get("abstract", "")
    assert res.get("results") and res["results"][0]["url"] == "https://example.com/news"


@pytest.mark.asyncio
async def test_tools_enabled_whitelist_keeps_web_tools(migrated_db_path):
    """Lista tools_enabled nie usuwa web_search / web_scraper (rdzeń produktu)."""
    reg = build_default_tool_registry(
        db_path=migrated_db_path,
        mcp_cfg=MCPConfig(enabled=True, tools_enabled=["calculator"]),
    )
    names = {t["function"]["name"] for t in reg.openai_tools()}
    assert "web_search" in names
    assert "web_scraper" in names
    assert "calculator" in names
