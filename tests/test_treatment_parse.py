"""Тесты разбора текста лечения из дневника."""

from __future__ import annotations

from pathlib import Path

from backend.db import DrugRepository
from backend.treatment_parse import (
    normalize_dose,
    parse_treatment_line,
    parse_treatment_text,
    split_treatment_lines,
    build_name_index,
)


def _catalog(tmp_path: Path) -> list[dict]:
    repo = DrugRepository(tmp_path / "app.db")
    repo.initialize()
    return repo.list_drugs()


def test_normalize_dose():
    assert normalize_dose("10 мг") == "10 мг"
    assert normalize_dose("10mg") == "10 мг"
    assert normalize_dose("7,5 мг") == "7.5 мг"
    assert normalize_dose("37.50 мг.") == "37.5 мг"


def test_split_treatment_lines_skips_headers_and_bullets():
    text = """
    Лечение:
    1. Эсциталопрам 10 мг — утром
    - Кветиапин 25 мг на ночь
    """
    lines = split_treatment_lines(text)
    assert lines == [
        "Эсциталопрам 10 мг — утром",
        "Кветиапин 25 мг на ночь",
    ]


def test_parse_scheme_export_format(tmp_path: Path):
    catalog = _catalog(tmp_path)
    text = "Tab. Эсциталопрам 10 мг — по 1 таблетке утром\nCaps. Флуоксетин 20 мг — по 1 капсуле утром"
    result = parse_treatment_text(text, catalog)
    assert result["ok"] is True
    assert len(result["drugs"]) == 2
    first, second = result["drugs"]
    assert first["mnn"] == "Escitalopram"
    assert first["dosage"] == "10 мг"
    assert first["drug_form"] == "Tab."
    assert first["selectedScheme"] == "по 1 таблетке утром"
    assert second["mnn"] == "Fluoxetine"
    assert second["drug_form"] == "Caps."
    assert second["selectedScheme"] == "по 1 капсуле утром"


def test_parse_diary_short_lines(tmp_path: Path):
    catalog = _catalog(tmp_path)
    text = """
    Эсциталопрам 10 мг утром
    Кветиапин 25 мг на ночь
    Зопиклон 7.5 мг на ночь
    """
    result = parse_treatment_text(text, catalog)
    assert result["ok"] is True
    mnns = [drug["mnn"] for drug in result["drugs"]]
    assert mnns == ["Escitalopram", "Quetiapine", "Zopiclone"]
    assert result["drugs"][0]["selectedScheme"] == "утром"
    assert result["drugs"][1]["selectedScheme"] == "на ночь"
    assert result["drugs"][2]["dosage"] == "7.5 мг"


def test_parse_trade_name_sets_trade_mode(tmp_path: Path):
    catalog = _catalog(tmp_path)
    result = parse_treatment_text("Ципралекс 10 мг — по 1 таб. утром", catalog)
    assert result["ok"] is True
    drug = result["drugs"][0]
    assert drug["mnn"] == "Escitalopram"
    assert drug["mode"] == "trade"
    assert drug["selectedTrade"] == "Ципралекс"
    assert drug["selectedScheme"] == "по 1 таб. утром"


def test_parse_russian_genitive(tmp_path: Path):
    catalog = _catalog(tmp_path)
    index = build_name_index(catalog)
    parsed = parse_treatment_line("по 1 таб. эсциталопрама 10 мг утром", index)
    assert parsed is not None
    assert parsed["mnn"] == "Escitalopram"
    assert parsed["dosage"] == "10 мг"
    assert "утром" in parsed["selectedScheme"]


def test_parse_unmatched_lines_reported(tmp_path: Path):
    catalog = _catalog(tmp_path)
    result = parse_treatment_text(
        "Эсциталопрам 10 мг утром\nНеизвестный препарат 5 мг вечером",
        catalog,
    )
    assert result["ok"] is True
    assert len(result["drugs"]) == 1
    assert any("Неизвестный" in line for line in result["unmatched"])


def test_parse_empty_text(tmp_path: Path):
    catalog = _catalog(tmp_path)
    result = parse_treatment_text("   \n", catalog)
    assert result["ok"] is False
    assert result["drugs"] == []


def test_parse_real_diary_style(tmp_path: Path):
    catalog = _catalog(tmp_path)
    text = """
    Флувоксин 100 мг по 1 т на ночь (№90)
    Таб. Кветиапин (Кетилепт, Квентиакс, Кутипин, Кьюпинекс) 200 мг №150 по 1,5т на ночь;
    Таб. Оксетол 300 мг по 1 т на ночь (№90)
    """
    result = parse_treatment_text(text, catalog)
    assert result["ok"] is True
    assert result["unmatched"] == []
    assert len(result["drugs"]) == 3

    fluvox, quet, oxcarb = result["drugs"]
    assert fluvox["mnn"] == "Fluvoxamine"
    assert fluvox["mode"] == "trade"
    assert fluvox["selectedTrade"] == "Флувоксин"
    assert fluvox["dosage"] == "100 мг"
    assert fluvox["dispenseQty"] == 90
    assert "на ночь" in fluvox["selectedScheme"]
    assert "№" not in fluvox["selectedScheme"]

    assert quet["mnn"] == "Quetiapine"
    assert quet["mode"] == "mnn"
    assert quet["dosage"] == "200 мг"
    assert quet["dispenseQty"] == 150
    assert quet["drug_form"] == "Tab."
    assert "1,5" in quet["selectedScheme"] or "1.5" in quet["selectedScheme"]

    assert oxcarb["mnn"] == "Oxcarbazepine"
    assert oxcarb["selectedTrade"] == "Оксетол"
    assert oxcarb["dosage"] == "300 мг"
    assert oxcarb["dispenseQty"] == 90
