"""Интеграционные сценарии: каталог, разбор, валидация, шаблоны."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.db import DrugRepository
from backend.dispense_rules import dispense_step_by_packaging, is_valid_dispense_qty
from backend.seed_loader import load_seed_drugs
from backend.trade_packaging import dosages_for_trade, resolve_mnn_packaging, resolve_trade_packaging
from backend.treatment_parse import parse_treatment_text
from backend.validate import validate_prescription_payload


def _catalog(tmp_path: Path) -> list[dict]:
    repo = DrugRepository(tmp_path / "app.db")
    repo.initialize()
    return repo.list_drugs()


def _base_patient_payload(**overrides):
    payload = {
        "patient_name": "Иванов И. И.",
        "birth_date": "01.01.1990",
        "doctor_name": "Петров П. П.",
        "card_number": "12345",
        "drugs": [],
    }
    payload.update(overrides)
    return payload


class TestSertralinePackagingScenarios:
    def test_stimuloton_trade_100mg_parse(self, tmp_path: Path):
        catalog = _catalog(tmp_path)
        result = parse_treatment_text("Стимулотон 100 мг — по 1 таблетке утром", catalog)
        assert result["ok"] is True
        assert len(result["drugs"]) == 1
        drug = result["drugs"][0]
        assert drug["selectedTrade"] == "Стимулотон"
        assert drug["dosage"] == "100 мг"
        assert drug["packaging"] == "N28"
        assert drug["mode"] == "trade"

    def test_sertraline_mnn_100mg_uses_max_packaging(self, tmp_path: Path):
        catalog = _catalog(tmp_path)
        sertraline = next(item for item in catalog if item["mnn"] == "Sertraline")
        match = resolve_mnn_packaging(sertraline["trade_details"], "100 мг", sertraline["packaging"])
        assert match["packaging"] == "N30"

    def test_trade_to_mnn_packaging_switch(self, tmp_path: Path):
        catalog = _catalog(tmp_path)
        sertraline = next(item for item in catalog if item["mnn"] == "Sertraline")
        details = sertraline["trade_details"]
        trade = resolve_trade_packaging(details, "Стимулотон", "100 мг")
        mnn = resolve_mnn_packaging(details, "100 мг", sertraline["packaging"])
        assert trade["packaging"] == "N28"
        assert mnn["packaging"] == "N30"


class TestQuetiapineTradeDosages:
    def test_kutipin_200_parse_and_pack(self, tmp_path: Path):
        catalog = _catalog(tmp_path)
        result = parse_treatment_text("Кутипин 200 мг на ночь", catalog)
        drug = result["drugs"][0]
        assert drug["selectedTrade"] == "Кутипин 200"
        assert drug["dosage"] == "200 мг"
        assert drug["packaging"] == "N30"
        quetiapine = next(item for item in catalog if item["mnn"] == "Quetiapine")
        assert dosages_for_trade(quetiapine["trade_details"], "Кутипин 200") == ["200 мг"]
        assert resolve_trade_packaging(quetiapine["trade_details"], "Кутипин 200", "25 мг") is None

    def test_kutipin_25_does_not_offer_200(self, tmp_path: Path):
        catalog = _catalog(tmp_path)
        quetiapine = next(item for item in catalog if item["mnn"] == "Quetiapine")
        assert dosages_for_trade(quetiapine["trade_details"], "Кутипин 25") == ["25 мг"]
        assert resolve_trade_packaging(quetiapine["trade_details"], "Кутипин 25", "200 мг") is None


class TestDispenseValidationScenarios:
    def test_valid_sertraline_n28_qty(self, tmp_path: Path):
        payload = _base_patient_payload(
            drugs=[{
                "mnn": "Sertraline",
                "drug_form": "Tab.",
                "dosage": "100 мг",
                "packaging": "N28",
                "dispenseQty": 28,
                "selectedScheme": "утром",
            }],
        )
        result = validate_prescription_payload(payload)
        assert result.ok

    def test_invalid_qty_blocks_print(self):
        payload = _base_patient_payload(
            drugs=[{
                "mnn": "Sertraline",
                "drug_form": "Tab.",
                "dosage": "100 мг",
                "packaging": "N28",
                "dispenseQty": 30,
                "selectedScheme": "утром",
            }],
        )
        result = validate_prescription_payload(payload)
        assert not result.ok
        assert any("кратно 14" in error for error in result.errors)

    def test_manual_qty_rounding_rules(self):
        assert is_valid_dispense_qty(56, "N28")
        assert is_valid_dispense_qty(55, "N28") is False
        assert dispense_step_by_packaging("N28") == 14


class TestTemplateScenarios:
    def test_template_stores_drugs_only(self, tmp_path: Path):
        repo = DrugRepository(tmp_path / "app.db")
        repo.initialize()
        repo.save_template("Тест", {
            "card_number": "999",
            "patient_name": "Секрет",
            "drugs": [{
                "mnn": "Sertraline",
                "russian_name": "Сертралин",
                "dosage": "100 мг",
                "selectedScheme": "утром",
            }],
        })
        stored = repo.get_template("Тест")
        assert "patient_name" not in stored
        assert stored["drugs"][0]["mnn"] == "Sertraline"

    def test_template_empty_rejected(self, tmp_path: Path):
        repo = DrugRepository(tmp_path / "app.db")
        repo.initialize()
        with pytest.raises(ValueError, match="at least one drug"):
            repo.save_template("Пустой", {"drugs": []})


class TestDuplicateMnnScenario:
    def test_titration_three_lines(self, tmp_path: Path):
        catalog = _catalog(tmp_path)
        text = "\n".join([
            "Венлафаксин 37.5 мг — утром",
            "Венлафаксин 75 мг — днём",
            "Венлафаксин 150 мг — вечером",
        ])
        result = parse_treatment_text(text, catalog)
        assert result["ok"] is True
        assert len(result["drugs"]) == 3
        doses = [drug["dosage"] for drug in result["drugs"]]
        assert doses.count("37.5 мг") == 1
        assert doses.count("75 мг") == 1
        assert doses.count("150 мг") == 1


def test_seed_catalog_covers_key_drugs():
    drugs = load_seed_drugs()
    mnns = {item["mnn"] for item in drugs}
    assert {"Sertraline", "Venlafaxine", "Escitalopram", "Quetiapine"} <= mnns
