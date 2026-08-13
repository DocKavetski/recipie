"""Смена врача: очистка пациентов без потери каталога."""

from __future__ import annotations

from pathlib import Path

from backend.db import DrugRepository
from backend.doctor_change import change_doctor, clear_patient_data
from backend.settings import SettingsStore


def test_clear_patient_history_keeps_catalog(tmp_path: Path):
    repo = DrugRepository(tmp_path / "app.db")
    repo.initialize()
    drugs_before = len(repo.list_drugs())
    assert drugs_before >= 30

    repo.save_history_entry({
        "card_number": "1001",
        "patient_name": "Иванов И.И.",
        "drugs": [{"mnn": "Sertraline"}],
    })
    repo.save_history_entry({
        "card_number": "1002",
        "patient_name": "Петров П.П.",
        "drugs": [{"mnn": "Venlafaxine"}],
    })
    repo.save_template("Шаблон", {"drugs": [{"mnn": "Sertraline", "russian_name": "Сертралин"}]})
    assert repo.count_history_entries() == 2

    result = repo.clear_patient_history()
    assert result["ok"] is True
    assert result["deleted"] == 2
    assert result["catalog_preserved"] is True
    assert repo.count_history_entries() == 0
    assert len(repo.list_drugs()) == drugs_before
    assert repo.get_template("Шаблон") is not None


def test_change_doctor_clears_patients_only(tmp_path: Path):
    repo = DrugRepository(tmp_path / "app.db")
    repo.initialize()
    settings = SettingsStore(tmp_path / "settings.json")
    settings.update_doctor_name("Старый Врач")

    repo.save_history_entry({
        "card_number": "55",
        "patient_name": "Сидоров",
        "drugs": [{"mnn": "Escitalopram"}],
    })
    settings.save_autosave({"patient_name": "Сидоров", "drugs": []})
    drugs_before = len(repo.list_drugs())

    result = change_doctor(
        settings_store=settings,
        repository=repo,
        doctor_name="Новый Врач",
    )
    assert result["ok"] is True
    assert result["patient_history_cleared"] is True
    assert result["catalog_preserved"] is True
    assert result["history_deleted"] == 1
    assert result["autosave_cleared"] is True
    assert settings.load()["doctor_name"] == "Новый Врач"
    assert repo.count_history_entries() == 0
    assert settings.load_autosave() == {}
    assert len(repo.list_drugs()) == drugs_before

    again = change_doctor(
        settings_store=settings,
        repository=repo,
        doctor_name="Новый Врач",
    )
    assert again["patient_history_cleared"] is False
    assert again["catalog_preserved"] is True
    assert len(repo.list_drugs()) == drugs_before


def test_clear_patient_data_keeps_catalog(tmp_path: Path):
    repo = DrugRepository(tmp_path / "app.db")
    repo.initialize()
    settings = SettingsStore(tmp_path / "settings.json")

    repo.save_history_entry({
        "card_number": "7",
        "patient_name": "Тест",
        "drugs": [{"mnn": "Quetiapine"}],
    })
    drugs_before = len(repo.list_drugs())
    result = clear_patient_data(settings_store=settings, repository=repo)
    assert result["ok"] is True
    assert result["catalog_preserved"] is True
    assert repo.count_history_entries() == 0
    assert len(repo.list_drugs()) == drugs_before
