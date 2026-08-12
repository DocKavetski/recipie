"""Тесты сопоставления торгового названия, дозировки и фасовки."""

from __future__ import annotations

from backend.seed_loader import load_seed_drugs
from backend.trade_packaging import (
    normalize_trade_details,
    resolve_mnn_packaging,
    resolve_trade_packaging,
    trade_details_from_variants,
)


def test_stimuloton_100mg_packaging_from_seed():
    sertraline = next(item for item in load_seed_drugs() if item["mnn"] == "Sertraline")
    details = sertraline["trade_details"]["Стимулотон"]
    assert "100 мг" in details
    assert details["100 мг"]["packaging"] == "N28"
    assert details["100 мг"]["dispense_qty"] == 28
    assert details["50 мг"]["packaging"] == "N30"


def test_resolve_trade_packaging_by_dosage():
    details = normalize_trade_details({
        "Стимулотон": {
            "50 мг": {"packaging": "N30", "dispense_qty": 30, "form": "Tab."},
            "100 мг": {"packaging": "N28", "dispense_qty": 28, "form": "Tab."},
        },
    })
    assert resolve_trade_packaging(details, "Стимулотон", "100 мг") == {
        "packaging": "N28",
        "dispense_qty": 28,
        "form": "Tab.",
    }
    assert resolve_trade_packaging(details, "Стимулотон", "50 мг")["packaging"] == "N30"
    assert resolve_trade_packaging(details, "Стимулотон", "25 мг") is None


def test_resolve_legacy_flat_trade_details():
    details = normalize_trade_details({
        "Стимулотон": {
            "packaging": "N30",
            "dispense_qty": 30,
            "form": "Tab.",
            "dosage": "50 мг",
        },
    })
    assert resolve_trade_packaging(details, "Стимулотон", "50 мг")["packaging"] == "N30"
    assert resolve_trade_packaging(details, "Стимулотон", "100 мг") is None


def test_mnn_mode_uses_max_packaging_for_dosage():
    sertraline = next(item for item in load_seed_drugs() if item["mnn"] == "Sertraline")
    match = resolve_mnn_packaging(sertraline["trade_details"], "100 мг", sertraline["packaging"])
    assert match is not None
    assert match["packaging"] == "N30"
    assert match["dispense_qty"] == 30


def test_mnn_mode_stimuloton_dosage_after_trade_switch():
    details = normalize_trade_details({
        "Стимулотон": {
            "50 мг": {"packaging": "N30", "dispense_qty": 30, "form": "Tab."},
            "100 мг": {"packaging": "N28", "dispense_qty": 28, "form": "Tab."},
        },
        "Сертралин-ЛФ": {
            "100 мг": {"packaging": "N30", "dispense_qty": 30, "form": "Tab."},
        },
    })
    trade = resolve_trade_packaging(details, "Стимулотон", "100 мг")
    assert trade["packaging"] == "N28"
    mnn = resolve_mnn_packaging(details, "100 мг", "N30")
    assert mnn["packaging"] == "N30"
    assert mnn["dispense_qty"] == 30


def test_trade_details_from_variants():
    details = trade_details_from_variants([
        {
            "trade_name": "Стимулотон",
            "dosage": "100 мг",
            "packaging": "N28",
            "dispense_qty": 28,
            "drug_form": "Tab.",
        },
        {
            "trade_name": "Стимулотон",
            "dosage": "50 мг",
            "packaging": "N30",
            "dispense_qty": 30,
            "drug_form": "Tab.",
        },
    ])
    assert details["Стимулотон"]["100 мг"]["packaging"] == "N28"
