"""CACHE-T / MCP-T — rozszerzone przypadki z dokumentacji (T7)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from backend.config.schema import MCPConfig
from backend.db.repositories import MCPCacheRepository
from backend.mcp import web_search as web_search_mod
from backend.mcp.registry import ToolRegistry, build_default_tool_registry


@pytest.mark.asyncio
async def test_cache_t02_invalidate_refetch(monkeypatch, migrated_db_path):
    responses = [
        {"AbstractText": "first", "RelatedTopics": [], "Heading": "", "AbstractURL": ""},
        {"AbstractText": "second", "RelatedTopics": [], "Heading": "", "AbstractURL": ""},
    ]
    calls = [0]

    async def fake_fetch(_params):  # type: ignore[no-untyped-def]
        i = calls[0]
        calls[0] += 1
        return responses[i]

    monkeypatch.setattr(web_search_mod, "_ddg_fetch", fake_fetch)

    reg = build_default_tool_registry(db_path=migrated_db_path, mcp_cfg=MCPConfig(enabled=True))
    a = await reg.invoke("web_search", {"query": "PoE2"}, system_state={"online": True})
    await MCPCacheRepository(migrated_db_path).invalidate_all()
    b = await reg.invoke("web_search", {"query": "PoE2"}, system_state={"online": True})
    assert a["abstract"] == "first"
    assert b["abstract"] == "second"


@pytest.mark.asyncio
async def test_cache_t03_parallel_identical_single_fetch(monkeypatch, migrated_db_path):
    calls: list[int] = []

    async def fake_fetch(_params):  # type: ignore[no-untyped-def]
        calls.append(1)
        await asyncio.sleep(0.04)
        return {"AbstractText": "one", "RelatedTopics": [], "Heading": "", "AbstractURL": ""}

    monkeypatch.setattr(web_search_mod, "_ddg_fetch", fake_fetch)

    reg = build_default_tool_registry(db_path=migrated_db_path, mcp_cfg=MCPConfig(enabled=True))

    async def run() -> object:
        return await reg.invoke("web_search", {"query": "dup"}, system_state={"online": True})

    out = await asyncio.gather(run(), run(), run())
    assert out[0] == out[1] == out[2]
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_mcp_t03_rate_limited_strict(monkeypatch, migrated_db_path):
    async def fake_fetch(_params):  # type: ignore[no-untyped-def]
        return {"AbstractText": "x", "RelatedTopics": [], "Heading": "", "AbstractURL": ""}

    monkeypatch.setattr(web_search_mod, "_ddg_fetch", fake_fetch)

    reg = ToolRegistry(
        db_path=migrated_db_path,
        cache_ttl_seconds=3600,
        web_search_calls_per_minute=2,
    )
    from backend.mcp.web_search import _TOOL_WEB_SEARCH, tool_web_search

    reg.register("web_search", _TOOL_WEB_SEARCH, tool_web_search)
    st = {"online": True}
    r0 = await reg.invoke("web_search", {"query": "a0"}, system_state=st)
    r1 = await reg.invoke("web_search", {"query": "a1"}, system_state=st)
    r2 = await reg.invoke("web_search", {"query": "a2"}, system_state=st)
    assert r0.get("ok") is True
    assert r1.get("ok") is True
    assert r2.get("error") == "rate_limited"


@pytest.mark.asyncio
async def test_mcp_t04_offline_web_search():
    reg = build_default_tool_registry(mcp_cfg=MCPConfig(enabled=True))
    r = await reg.invoke("web_search", {"query": "x"}, system_state={"online": False})
    assert r.get("error") == "offline"


@pytest.mark.asyncio
async def test_generate_document_writes_under_content_root(tmp_path, migrated_db_path):
    reg = build_default_tool_registry(
        db_path=migrated_db_path,
        mcp_cfg=MCPConfig(enabled=True),
        content_root=str(tmp_path),
    )
    res = await reg.invoke(
        "generate_document",
        {"topic": "Test", "format": "md", "content": "# Hello", "filename_hint": "hint"},
    )
    assert res.get("ok") is True
    p = Path(str(res["file_path"]))
    assert p.is_relative_to(tmp_path)
    assert "documents" in p.parts
    assert p.read_text(encoding="utf-8").startswith("# Hello")


@pytest.mark.asyncio
async def test_mcp_t08_calculator_expression():
    reg = build_default_tool_registry()
    r = await reg.invoke("calculator", {"expression": "(450+78)*1.35"})
    assert r.get("ok") is True
    assert r.get("result") == pytest.approx(712.8, rel=1e-9)


@pytest.mark.asyncio
async def test_mcp_t09_calculator_no_import():
    reg = build_default_tool_registry()
    r = await reg.invoke("calculator", {"expression": "__import__('os').listdir('.')"})
    assert r.get("ok") is False
