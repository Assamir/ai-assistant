"""Testy jednostkowe narzędzi agentowych (System A)."""

import pytest

from backend.mcp.agent_tools import make_agent_tools


@pytest.fixture
def state():
    return {}


@pytest.fixture
def tools(state):
    return make_agent_tools(None, state)


@pytest.mark.asyncio
async def test_plan_create(tools, state):
    _, handler = tools["plan_create"]
    result = await handler(
        goal="Znaleźć najlepszy build ADC",
        steps=["Sprawdź tier listę", "Porównaj buildy", "Wybierz najlepszy"],
    )
    assert result["ok"] is True
    assert result["total"] == 3
    assert len(state["agent_plan"]) == 3
    assert state["agent_goal"] == "Znaleźć najlepszy build ADC"


@pytest.mark.asyncio
async def test_plan_get_empty(tools, state):
    _, handler = tools["plan_get"]
    result = await handler()
    assert result["ok"] is True
    assert result["steps"] == []
    assert result["total"] == 0


@pytest.mark.asyncio
async def test_plan_create_then_get(tools, state):
    _, create = tools["plan_create"]
    _, get = tools["plan_get"]

    await create(goal="Test", steps=["Krok A", "Krok B"])
    result = await get()
    assert result["total"] == 2
    assert result["done_count"] == 0


@pytest.mark.asyncio
async def test_task_start(tools, state):
    _, create = tools["plan_create"]
    _, start = tools["task_start"]

    await create(goal="Test", steps=["Krok A", "Krok B"])
    result = await start(step_index=0)
    assert result["ok"] is True
    assert state["agent_plan"][0]["status"] == "in_progress"


@pytest.mark.asyncio
async def test_task_done(tools, state):
    _, create = tools["plan_create"]
    _, done = tools["task_done"]

    await create(goal="Test", steps=["Krok A", "Krok B"])
    result = await done(step_index=0, result="Znaleziono Ashe na S-tier")
    assert result["ok"] is True
    assert state["agent_plan"][0]["status"] == "done"
    assert "Ashe" in state["agent_plan"][0]["result"]


@pytest.mark.asyncio
async def test_task_start_out_of_bounds(tools, state):
    _, create = tools["plan_create"]
    _, start = tools["task_start"]

    await create(goal="Test", steps=["Krok A"])
    result = await start(step_index=99)
    assert result["ok"] is False


@pytest.mark.asyncio
async def test_task_revise(tools, state):
    _, create = tools["plan_create"]
    _, done = tools["task_done"]
    _, revise = tools["task_revise"]

    await create(goal="Test", steps=["Krok A", "Krok B", "Krok C"])
    await done(step_index=0, result="OK")
    result = await revise(reason="Zmiana planu", new_steps=["Nowy krok 1", "Nowy krok 2"])
    assert result["ok"] is True
    assert result["revised_from_step"] == 1


@pytest.mark.asyncio
async def test_work_evaluate(tools, state):
    _, evaluate = tools["work_evaluate"]
    result = await evaluate(goal="Test", summary="Wszystko OK", quality_score=0.9)
    assert result["ok"] is True
    assert result["quality_score"] == 0.9
    assert state["agent_quality_score"] == 0.9
    assert "osiągnięty" in result["verdict"]


@pytest.mark.asyncio
async def test_work_evaluate_low(tools, state):
    _, evaluate = tools["work_evaluate"]
    result = await evaluate(goal="Test", summary="Częściowo OK", quality_score=0.4)
    assert "niepełny" in result["verdict"]


@pytest.mark.asyncio
async def test_note_save_and_get(tools, state):
    _, save = tools["note_save"]
    _, get = tools["notes_get"]

    await save(content="Znalazłem patch 14.10")
    await save(content="API Riot niestabilne")
    result = await get()
    assert result["ok"] is True
    assert result["count"] == 2
    assert "patch 14.10" in result["notes"][0]


@pytest.mark.asyncio
async def test_evaluate_clamps_score(tools, state):
    _, evaluate = tools["work_evaluate"]
    await evaluate(goal="x", summary="y", quality_score=2.5)
    assert state["agent_quality_score"] == 1.0

    await evaluate(goal="x", summary="y", quality_score=-0.5)
    assert state["agent_quality_score"] == 0.0
