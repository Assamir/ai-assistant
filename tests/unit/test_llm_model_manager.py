"""LLMModelManager — mock hf_hub_download i list_repo_files."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.ai.llm_models_catalog import INITIAL_MODELS, ModelEntry, parse_model_id
from backend.services.llm_model_manager import LLMModelManager


def _build_mgr(tmp_path: Path) -> LLMModelManager:
    return LLMModelManager(
        cache_dir=tmp_path / "cache",
        custom_yaml_path=tmp_path / "custom.yaml",
    )


def test_parse_model_id_two_parts():
    repo, file = parse_model_id("owner/repo")
    assert repo == "owner/repo"
    assert file is None


def test_parse_model_id_three_parts():
    repo, file = parse_model_id("owner/repo/model-Q4_K_M.gguf")
    assert repo == "owner/repo"
    assert file == "model-Q4_K_M.gguf"


def test_parse_model_id_invalid():
    with pytest.raises(ValueError):
        parse_model_id("invalid")


def test_initial_models_are_loaded(tmp_path: Path):
    mgr = _build_mgr(tmp_path)
    catalog = mgr.list_catalog()
    ids = [m.model_id for m in catalog]
    assert "unsloth/gemma-3n-E4B-it-GGUF" in ids
    assert "unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF" in ids


def test_add_and_remove_custom_model(tmp_path: Path):
    mgr = _build_mgr(tmp_path)
    entry = ModelEntry(
        model_id="TheBloke/Mistral-7B-Instruct-v0.2-GGUF",
        display_name="Mistral 7B",
        default_quant="Q5_K_M",
        is_custom=True,
    )
    mgr.add_custom_model(entry)
    custom = mgr.list_custom()
    assert any(e.model_id == entry.model_id for e in custom)
    catalog = mgr.list_catalog()
    assert any(e.model_id == entry.model_id for e in catalog)

    removed = mgr.remove_custom_model(entry.model_id)
    assert removed is True
    assert not any(e.model_id == entry.model_id for e in mgr.list_custom())


def test_ensure_downloaded_idempotent_when_file_exists(tmp_path: Path, monkeypatch):
    mgr = _build_mgr(tmp_path)
    # Symuluj pobrany plik w cache
    repo = "owner/repo"
    file = "model-Q4_K_M.gguf"
    target = mgr._model_cache_dir(repo) / file
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"FAKE_GGUF" * 100)

    # hf_hub_download nie powinien zostać wywołany
    called = {"hit": False}

    def fake_hf(*args, **kwargs):
        called["hit"] = True
        raise AssertionError("hf_hub_download nie powinien być wywołany")

    monkeypatch.setattr("huggingface_hub.hf_hub_download", fake_hf)
    result = mgr.ensure_downloaded_sync(f"{repo}/{file}")
    assert result.local_path.endswith(file)
    assert called["hit"] is False


def test_ensure_downloaded_picks_quant_when_no_file(tmp_path: Path, monkeypatch):
    mgr = _build_mgr(tmp_path)
    fake_files = ["README.md", "model-Q4_K_M.gguf", "model-Q8_0.gguf"]
    downloaded_to = tmp_path / "downloaded.gguf"
    downloaded_to.write_bytes(b"x" * 50)

    def fake_list(repo_id, **kwargs):
        assert repo_id == "owner/repo"
        return fake_files

    def fake_hf(*, repo_id, filename, local_dir, **kwargs):
        assert filename == "model-Q4_K_M.gguf"
        target = Path(local_dir) / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"GGUF" * 25)
        return str(target)

    monkeypatch.setattr("huggingface_hub.list_repo_files", fake_list)
    monkeypatch.setattr("huggingface_hub.hf_hub_download", fake_hf)

    result = mgr.ensure_downloaded_sync("owner/repo", preferred_quant="Q4_K_M")
    assert result.quant == "Q4_K_M"
    assert "model-Q4_K_M.gguf" in result.local_path


def test_is_downloaded_returns_none_when_missing(tmp_path: Path):
    mgr = _build_mgr(tmp_path)
    assert mgr.is_downloaded("owner/repo", file="nope.gguf") is None


def test_remove_downloaded_clears_cache(tmp_path: Path):
    mgr = _build_mgr(tmp_path)
    target = mgr._model_cache_dir("owner/repo") / "model.gguf"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"x")
    assert mgr.remove_downloaded("owner/repo") is True
    assert not target.parent.exists()
    # idempotent
    assert mgr.remove_downloaded("owner/repo") is False
