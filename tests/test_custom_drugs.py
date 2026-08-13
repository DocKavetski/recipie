"""Ручное добавление препаратов в каталог."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.db import DrugRepository


def test_upsert_custom_drug_persists_across_sync(tmp_path: Path):
    repo = DrugRepository(tmp_path / "app.db")
    repo.initialize()
    seed_count = len(repo.list_drugs())

    result = repo.upsert_custom_drug({
        "mnn": "Custominum",
        "russian_name": "Кастомин",
        "latin_name": "Custominum",
        "drug_form": "Tab.",
        "dosage": "10 мг",
        "packaging": "N28",
        "trade_names_raw": "Кастом; Customix",
        "category": "Прочее",
    })
    assert result["ok"] is True
    assert result["is_custom"] is True

    drugs = repo.list_drugs()
    custom = next(item for item in drugs if item["mnn"] == "Custominum")
    assert custom["is_custom"] is True
    assert custom["russian_name"] == "Кастомин"
    assert "Кастом" in custom["trade_names"]
    assert len(drugs) == seed_count + 1

    repo.sync_seed_catalog(replace=True)
    after = repo.list_drugs()
    assert any(item["mnn"] == "Custominum" and item["is_custom"] for item in after)
    assert len(after) >= seed_count + 1


def test_cannot_overwrite_seed_drug_as_custom(tmp_path: Path):
    repo = DrugRepository(tmp_path / "app.db")
    repo.initialize()
    with pytest.raises(ValueError, match="системном каталоге"):
        repo.upsert_custom_drug({
            "mnn": "Sertraline",
            "russian_name": "Сертралин",
            "dosage": "50 мг",
        })


def test_delete_custom_drug_only(tmp_path: Path):
    repo = DrugRepository(tmp_path / "app.db")
    repo.initialize()
    repo.upsert_custom_drug({
        "mnn": "Deletinum",
        "russian_name": "Делетин",
        "dosage": "5 мг",
    })
    assert repo.delete_custom_drug("Deletinum")["deleted"] is True
    assert all(item["mnn"] != "Deletinum" for item in repo.list_drugs())

    with pytest.raises(ValueError, match="вручную"):
        repo.delete_custom_drug("Sertraline")
