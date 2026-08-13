"""Добавление препарата по МНН через tabletka."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.custom_drug_add import (
    add_custom_drug_from_tabletka,
    build_mnn_key,
    payload_from_tabletka_query,
)
from backend.db import DrugRepository
from backend.tabletka_enrich import TabletkaEnrichment, TabletkaVariant


def _fake_enrichment() -> TabletkaEnrichment:
    return TabletkaEnrichment(
        query="Тестоприл",
        mnn_id="99999",
        mnn_text="Тестоприл",
        variants=[
            TabletkaVariant(
                trade_name="Тестоприл-Торг",
                form_raw="таблетки 100мг N28",
                drug_form="Tab.",
                dosage="100 мг",
                packaging="N28",
                dispense_qty=28,
            ),
            TabletkaVariant(
                trade_name="Тестоприл-Торг",
                form_raw="таблетки 50мг N30",
                drug_form="Tab.",
                dosage="50 мг",
                packaging="N30",
                dispense_qty=30,
            ),
            TabletkaVariant(
                trade_name="Тестик",
                form_raw="таблетки 50мг N28",
                drug_form="Tab.",
                dosage="50 мг",
                packaging="N28",
                dispense_qty=28,
            ),
        ],
        form_options=["Tab."],
        dosage_options=["50 мг", "100 мг"],
        form_dosage_map={"Tab.": ["50 мг", "100 мг"]},
        trade_names=["Тестоприл-Торг", "Тестик"],
        trade_details={},
        default_form="Tab.",
        default_dosage="50 мг",
        default_packaging="N30",
        message="Найдено позиций: 3",
    )


def test_build_mnn_key_latin_and_russian():
    assert build_mnn_key("Sertraline") == "Sertraline"
    assert build_mnn_key("сертралин") == "Sertralin"


def test_payload_from_tabletka_query_uses_enrichment():
    payload = payload_from_tabletka_query("Тестоприл", enricher=lambda _q: _fake_enrichment())
    assert payload["russian_name"] == "Тестоприл"
    assert payload["mnn"] == "Testopril"
    assert "Тестоприл-Торг" in payload["trade_names"]
    assert payload["trade_details"]["Тестоприл-Торг"]["100 мг"]["packaging"] == "N28"
    assert "50 мг" in payload["dosage_options"]


def test_payload_raises_when_empty():
    empty = TabletkaEnrichment(query="xxx", message="Не найдено")
    with pytest.raises(ValueError, match="Не найдено"):
        payload_from_tabletka_query("xxx", enricher=lambda _q: empty)


def test_add_custom_drug_from_tabletka_persists(tmp_path: Path):
    repo = DrugRepository(tmp_path / "app.db")
    repo.initialize()
    result = add_custom_drug_from_tabletka(
        repo,
        "Тестоприл",
        enricher=lambda _q: _fake_enrichment(),
    )
    assert result["ok"] is True
    drug = next(item for item in repo.list_drugs() if item["mnn"] == "Testopril")
    assert drug["is_custom"] is True
    assert drug["russian_name"] == "Тестоприл"
    assert "Тестик" in drug["trade_names"]


def test_add_rejects_existing_russian_name(tmp_path: Path):
    repo = DrugRepository(tmp_path / "app.db")
    repo.initialize()
    with pytest.raises(ValueError, match="уже есть"):
        add_custom_drug_from_tabletka(
            repo,
            "Сертралин",
            enricher=lambda _q: TabletkaEnrichment(
                query="Сертралин",
                mnn_text="Сертралин",
                variants=[
                    TabletkaVariant("X", "табл 10мг N30", "Tab.", "10 мг", "N30", 30),
                ],
                form_options=["Tab."],
                dosage_options=["10 мг"],
                form_dosage_map={"Tab.": ["10 мг"]},
                trade_names=["X"],
                default_form="Tab.",
                default_dosage="10 мг",
                default_packaging="N30",
                message="ok",
            ),
        )
