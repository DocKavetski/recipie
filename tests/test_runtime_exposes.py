"""Регистрация runtime Eel API из overlay."""

from __future__ import annotations

from pathlib import Path

from backend.db import DrugRepository
from backend import runtime_exposes
from backend.tabletka_enrich import TabletkaEnrichment, TabletkaVariant


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
    assert "get_archived_drugs" in exposed
    assert "add_drug_from_tabletka" in exposed
    assert "upsert_custom_drug" in exposed
    assert "delete_custom_drug" in exposed
    result = exposed["parse_treatment"]("Эсциталопрам 10 мг утром")
    assert result["ok"] is True
    assert result["drugs"][0]["mnn"] == "Escitalopram"
    archived = exposed["get_archived_drugs"]()
    assert any(item["mnn"] == "Vilazodone" for item in archived)


def test_runtime_expose_add_drug_from_tabletka(tmp_path: Path, monkeypatch):
    runtime_exposes._REGISTERED = False
    exposed = {}

    class DummyEel:
        @staticmethod
        def expose(fn):
            exposed[fn.__name__] = fn
            return fn

    monkeypatch.setitem(__import__("sys").modules, "eel", DummyEel)

    fake = TabletkaEnrichment(
        query="Тестоприл",
        mnn_id="99999",
        mnn_text="Тестоприл",
        variants=[
            TabletkaVariant(
                trade_name="Тестоприл-Торг",
                form_raw="таблетки 50мг N30",
                drug_form="Tab.",
                dosage="50 мг",
                packaging="N30",
                dispense_qty=30,
            ),
        ],
        form_options=["Tab."],
        dosage_options=["50 мг"],
        form_dosage_map={"Tab.": ["50 мг"]},
        trade_names=["Тестоприл-Торг"],
        trade_details={},
        default_form="Tab.",
        default_dosage="50 мг",
        default_packaging="N30",
        message="ok",
    )
    monkeypatch.setattr(
        "backend.custom_drug_add.enrich_by_russian_name",
        lambda _q: fake,
    )

    repo = DrugRepository(tmp_path / "app.db")
    repo.initialize()
    saved = exposed["add_drug_from_tabletka"]("Тестоприл")
    assert saved["russian_name"] == "Тестоприл"
    assert any(d["mnn"] == "Testopril" and d.get("is_custom") for d in repo.list_drugs())
    assert exposed["delete_custom_drug"]("Testopril")["deleted"] is True
