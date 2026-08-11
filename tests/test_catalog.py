"""Тесты каталога и поиска."""

from __future__ import annotations

import json
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
    assert len(drugs) >= 35
    names = " ".join(d["russian_name"].lower() for d in drugs)
    assert "диазепам" not in names
    assert "эсциталопрам" in names
    assert "тофизопам" in names
    assert "вилазодон" not in names
    assert "тианептин" not in names
    assert "агомелатин" not in names
    assert "этифоксин" not in names
    assert "гидроксизин" not in names


def test_archived_unavailable_drugs_file():
    archived = json.loads(Path("data/archived_drugs.json").read_text(encoding="utf-8"))
    assert len(archived) >= 5
    mnns = {item["mnn"] for item in archived}
    assert {"Tianeptine", "Agomelatine", "Etifoxine", "Hydroxyzine", "Vilazodone"} <= mnns
    assert all(item.get("archived") for item in archived)
    # Архив не попадает в активный seed
    active = {item["mnn"] for item in load_seed_drugs()}
    assert mnns.isdisjoint(active)

def test_catalog_includes_grandaxin(tmp_path: Path):
    repo = DrugRepository(tmp_path / "app.db")
    repo.initialize()
    results = repo.search_drugs("грандаксин")
    assert results
    assert any(item["mnn"] == "Tofisopam" for item in results)
    drug = next(item for item in repo.list_drugs() if item["mnn"] == "Tofisopam")
    assert "Грандаксин" in drug["trade_names"]
    assert drug["dosage"] == "50 мг"
    assert "Tab." in drug["form_options"]


def test_catalog_includes_atomoxetine(tmp_path: Path):
    repo = DrugRepository(tmp_path / "app.db")
    repo.initialize()
    results = repo.search_drugs("атомоксетин")
    assert results
    assert any(item["mnn"] == "Atomoxetine" for item in results)
    by_trade = repo.search_drugs("страттера")
    assert any(item["mnn"] == "Atomoxetine" for item in by_trade)
    drug = next(item for item in repo.list_drugs() if item["mnn"] == "Atomoxetine")
    assert drug["drug_form"] == "Caps."
    assert "18 мг" in drug["dosage_options"]


def test_load_archived_drugs_for_directory():
    from backend.seed_loader import load_archived_drugs

    archived = load_archived_drugs()
    assert len(archived) >= 5
    assert all(item.get("archived") for item in archived)
    assert any(item["mnn"] == "Vilazodone" for item in archived)
    assert any("Нет в продаже" in item.get("archive_reason", "") for item in archived)


def test_catalog_excludes_solution_form():
    drugs = load_seed_drugs()
    for drug in drugs:
        assert str(drug.get("drug_form", "")).lower() not in {"sol.", "sol"}
        for form in drug.get("form_options", []):
            assert str(form).lower() not in {"sol.", "sol"}


def test_custom_scheme_overrides_persist_across_sync(tmp_path: Path):
    repo = DrugRepository(tmp_path / "app.db")
    repo.initialize()

    original = next(item for item in repo.list_drugs() if item["mnn"] == "Escitalopram")
    assert original["scheme_options"]

    saved = repo.save_drug_schemes("Escitalopram", ["по 1 таблетке утром", "по 1 таблетке вечером"])
    assert saved["ok"] is True

    customized = next(item for item in repo.list_drugs() if item["mnn"] == "Escitalopram")
    assert customized["scheme_options"] == ["по 1 таблетке утром", "по 1 таблетке вечером"]
    assert customized["has_custom_scheme"] is True

    repo.sync_seed_catalog(replace=True)
    after_sync = next(item for item in repo.list_drugs() if item["mnn"] == "Escitalopram")
    assert after_sync["scheme_options"] == ["по 1 таблетке утром", "по 1 таблетке вечером"]
    assert after_sync["has_custom_scheme"] is True

    reset = repo.reset_drug_schemes("Escitalopram")
    assert reset["ok"] is True
    restored = next(item for item in repo.list_drugs() if item["mnn"] == "Escitalopram")
    assert restored["scheme_options"] == original["scheme_options"]
    assert restored["has_custom_scheme"] is False


def test_template_can_be_deleted(tmp_path: Path):
    repo = DrugRepository(tmp_path / "app.db")
    repo.initialize()

    payload = {
        "card_number": "",
        "patient_name": "",
        "birth_date": "",
        "doctor_name": "",
        "drugs": [
            {"mnn": "Venlafaxine", "russian_name": "Венлафаксин", "dosage": "37.5 мг", "selectedScheme": "утром"},
            {"mnn": "Venlafaxine", "russian_name": "Венлафаксин", "dosage": "75 мг", "selectedScheme": "днём"},
            {"mnn": "Venlafaxine", "russian_name": "Венлафаксин", "dosage": "150 мг", "selectedScheme": "вечером"},
        ],
    }
    repo.save_template("Венлафаксин титрация", payload)
    assert repo.get_template("Венлафаксин титрация")

    result = repo.delete_template("Венлафаксин титрация")
    assert result["ok"] is True
    assert result["deleted"] is True
    assert repo.get_template("Венлафаксин титрация") is None
