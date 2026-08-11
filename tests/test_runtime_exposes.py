"""Регистрация runtime Eel API из overlay."""

from __future__ import annotations

from pathlib import Path

from backend.db import DrugRepository
from backend import runtime_exposes


def test_initialize_registers_parse_treatment(tmp_path: Path, monkeypatch):
    runtime_exposes._REGISTERED = False
    exposed = {}

    class DummyEel:
        @staticmethod
        def expose(fn):
            exposed[fn.__name__] = fn
            return fn

    monkeypatch.setitem(__import__("sys").modules, "eel", DummyEel)

    repo = DrugRepository(tmp_path / "app.db")
    repo.initialize()

    assert "parse_treatment" in exposed
    result = exposed["parse_treatment"]("Эсциталопрам 10 мг утром")
    assert result["ok"] is True
    assert result["drugs"][0]["mnn"] == "Escitalopram"
