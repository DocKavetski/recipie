"""Тесты каталога и поиска."""

from __future__ import annotations

from pathlib import Path

from backend.db import DrugRepository
from backend.seed_loader import load_seed_drugs


def test_catalog_search_finds_by_alias(tmp_path: Path):
    repo = DrugRepository(tmp_path / "app.db")
    repo.initialize()
    results = repo.search_drugs("эсциталопрам")
    assert results
    assert any(item["mnn"] == "Escitalopram" for item in results)


def test_catalog_search_trade_name(tmp_path: Path):
    repo = DrugRepository(tmp_path / "app.db")
    repo.initialize()
    results = repo.search_drugs("ципралекс")
    assert results
    assert any(item["mnn"] == "Escitalopram" for item in results)


def test_list_drugs_not_empty(tmp_path: Path):
    repo = DrugRepository(tmp_path / "app.db")
    repo.initialize()
    drugs = repo.list_drugs()
    assert len(drugs) >= 40
    names = " ".join(d["russian_name"].lower() for d in drugs)
    assert "диазепам" not in names
    assert "тофизопам" not in names
    assert "эсциталопрам" in names


def test_catalog_excludes_solution_form():
    drugs = load_seed_drugs()
    for drug in drugs:
        assert str(drug.get("drug_form", "")).lower() not in {"sol.", "sol"}
        for form in drug.get("form_options", []):
            assert str(form).lower() not in {"sol.", "sol"}
