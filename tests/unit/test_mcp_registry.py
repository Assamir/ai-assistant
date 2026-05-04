"""Narzędzia MCP bazowe — get_current_time / calculator."""

from __future__ import annotations

import pytest


from backend.mcp.registry import ToolRegistry, build_default_tool_registry


@pytest.mark.asyncio
async def test_get_current_time_invoke():
    reg = build_default_tool_registry()
    out = await reg.invoke("get_current_time", {"timezone": ""})
    assert "iso_local" in out or "iso" in str(out).lower()
    body = out if isinstance(out, dict) else {}

    assert isinstance(body, dict)




@pytest.mark.asyncio
async def test_calculator_ok():
    reg = build_default_tool_registry()
    res = await reg.invoke("calculator", {"expression": "2+2*3"})
    assert isinstance(res, dict)
    assert res.get("ok") is True
    assert res.get("result") == 8



@pytest.mark.asyncio
async def test_calculator_error():
    reg = build_default_tool_registry()
    res = await reg.invoke("calculator", {"expression": "1/0"})
    assert isinstance(res, dict)
    assert res.get("ok") is False


@pytest.mark.asyncio


async def test_openai_tool_dispatch_shape():
    reg = build_default_tool_registry()
    blob = {
        "id": "call-1",
        "type": "function",
        "function": {"name": "calculator", 'arguments': '{"expression": "40*0.1"}'},
    }
    msg = await reg.invoke_openai_tool_call(blob)
    assert msg["role"] == "tool"
    assert msg["tool_call_id"] == "call-1"


@pytest.mark.asyncio
async def test_unknown_tool_keyerror():
    reg = ToolRegistry()


    with pytest.raises(KeyError):

        await reg.invoke("nope", {})
