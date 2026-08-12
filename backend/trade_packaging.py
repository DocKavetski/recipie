"""Сопоставление торгового названия и дозировки с фасовкой."""

from __future__ import annotations

import re
from typing import Any


def _normalize_dosage(value: str) -> str:
    text = str(value or "").strip().lower().replace("ё", "е").replace(",", ".")
    match = re.search(r"(\d+(?:\.\d+)?)\s*(мг|мкг|г|me|ме|%)\.?", text)
    if not match:
        return text
    amount = match.group(1).rstrip("0").rstrip(".") if "." in match.group(1) else match.group(1)
    unit = match.group(2)
    if unit.lower() in {"me", "ме"}:
        unit = "МЕ"
    return f"{amount} {unit}"


def _is_nested_trade_entry(entry: dict[str, Any]) -> bool:
    if not isinstance(entry, dict) or not entry:
        return False
    return "packaging" not in entry and "dispense_qty" not in entry


def trade_details_from_variants(variants: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    details: dict[str, dict[str, dict[str, Any]]] = {}
    for variant in variants:
        if not isinstance(variant, dict):
            continue
        trade = str(variant.get("trade_name") or "").strip()
        dosage = str(variant.get("dosage") or "").strip()
        if not trade or not dosage:
            continue
        packaging = str(variant.get("packaging") or "").strip()
        dispense_qty = variant.get("dispense_qty")
        if dispense_qty is None and packaging:
            match = re.search(r"(\d+)", packaging)
            dispense_qty = int(match.group(1)) if match else None
        details.setdefault(trade, {})[dosage] = {
            "packaging": packaging,
            "dispense_qty": dispense_qty,
            "form": str(variant.get("drug_form") or "").strip(),
        }
    return details


def normalize_trade_details(trade_details: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(trade_details, dict):
        return {}

    normalized: dict[str, Any] = {}
    for trade, entry in trade_details.items():
        trade_name = str(trade or "").strip()
        if not trade_name or not isinstance(entry, dict):
            continue
        if _is_nested_trade_entry(entry):
            per_dose: dict[str, dict[str, Any]] = {}
            for dosage, details in entry.items():
                dose = str(dosage or "").strip()
                if not dose or not isinstance(details, dict):
                    continue
                per_dose[dose] = {
                    "packaging": str(details.get("packaging") or "").strip(),
                    "dispense_qty": details.get("dispense_qty"),
                    "form": str(details.get("form") or "").strip(),
                }
            if per_dose:
                normalized[trade_name] = per_dose
            continue

        dosage = str(entry.get("dosage") or "").strip()
        flat = {
            "packaging": str(entry.get("packaging") or "").strip(),
            "dispense_qty": entry.get("dispense_qty"),
            "form": str(entry.get("form") or "").strip(),
        }
        if dosage:
            normalized.setdefault(trade_name, {})[dosage] = flat
        else:
            normalized[trade_name] = flat
    return normalized


def resolve_trade_packaging(
    trade_details: dict[str, Any] | None,
    trade: str,
    dosage: str = "",
) -> dict[str, Any] | None:
    trade_name = str(trade or "").strip()
    if not trade_name or not isinstance(trade_details, dict):
        return None

    entry = trade_details.get(trade_name)
    if not isinstance(entry, dict) or not entry:
        return None

    dose = str(dosage or "").strip()
    normalized_dose = _normalize_dosage(dose)

    if _is_nested_trade_entry(entry):
        if dose and dose in entry and isinstance(entry[dose], dict):
            return dict(entry[dose])
        for key, details in entry.items():
            if _normalize_dosage(key) == normalized_dose and isinstance(details, dict):
                return dict(details)
        return None

    entry_dose = str(entry.get("dosage") or "").strip()
    if entry_dose and dose and _normalize_dosage(entry_dose) != normalized_dose:
        return None
    return dict(entry)
