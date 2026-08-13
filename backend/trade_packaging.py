"""Сопоставление торгового названия и дозировки с фасовкой."""

from __future__ import annotations

import re
from typing import Any


_TRADE_NUMBER_RE = re.compile(r"(?<!\d)(\d+(?:[.,]\d+)?)(?!\d)")


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


def dosages_for_trade(trade_details: dict[str, Any] | None, trade: str) -> list[str]:
    """Дозировки, которые реально есть у конкретного торгового названия."""
    trade_name = str(trade or "").strip()
    if not trade_name or not isinstance(trade_details, dict):
        return []
    entry = trade_details.get(trade_name)
    if not isinstance(entry, dict) or not entry:
        return []
    if _is_nested_trade_entry(entry):
        return [str(dose).strip() for dose in entry if str(dose).strip()]
    dosage = str(entry.get("dosage") or "").strip()
    return [dosage] if dosage else []


def dosage_from_trade_name(trade: str, available: list[str] | None = None) -> str:
    """«Кутипин 200» / «Финлепсин 200 ретард» → дозировка из названия, если она есть в фасовке."""
    text = str(trade or "").strip()
    numbers = [match.group(1).replace(",", ".") for match in _TRADE_NUMBER_RE.finditer(text)]
    options = [str(item).strip() for item in (available or []) if str(item).strip()]
    by_norm = {_normalize_dosage(item): item for item in options}
    for number in reversed(numbers):
        for unit in ("мг", "мкг", "г", "МЕ"):
            key = _normalize_dosage(f"{number} {unit}")
            if key in by_norm:
                return by_norm[key]
        for key, original in by_norm.items():
            if key.startswith(number):
                return original
    if len(options) == 1:
        return options[0]
    if numbers:
        return _normalize_dosage(f"{numbers[-1]} мг")
    return ""


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
    normalized_dose = _normalize_dosage(dose) if dose else ""

    if _is_nested_trade_entry(entry):
        if dose and dose in entry and isinstance(entry[dose], dict):
            return dict(entry[dose])
        if normalized_dose:
            for key, details in entry.items():
                if _normalize_dosage(key) == normalized_dose and isinstance(details, dict):
                    return dict(details)
            return None
        inferred = dosage_from_trade_name(trade_name, [str(key).strip() for key in entry])
        if inferred:
            inferred_norm = _normalize_dosage(inferred)
            for key, details in entry.items():
                if _normalize_dosage(key) == inferred_norm and isinstance(details, dict):
                    return dict(details)
        if len(entry) == 1:
            only = next(iter(entry.values()))
            if isinstance(only, dict):
                return dict(only)
        return None

    entry_dose = str(entry.get("dosage") or "").strip()
    if entry_dose and dose and _normalize_dosage(entry_dose) != normalized_dose:
        return None
    return dict(entry)


def _entry_for_dosage(entry: dict[str, Any], dosage: str) -> dict[str, Any] | None:
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


def _pack_qty(details: dict[str, Any] | None) -> int:
    if not isinstance(details, dict):
        return 0
    qty = details.get("dispense_qty")
    if qty is not None:
        try:
            return int(qty)
        except (TypeError, ValueError):
            pass
    packaging = str(details.get("packaging") or "")
    match = re.search(r"(\d+)", packaging)
    return int(match.group(1)) if match else 0


def resolve_mnn_packaging(
    trade_details: dict[str, Any] | None,
    dosage: str = "",
    fallback_packaging: str = "",
) -> dict[str, Any] | None:
    """Для режима МНН — максимальная фасовка среди торговых вариантов на эту дозу."""
    best: dict[str, Any] | None = None
    best_qty = -1
    if isinstance(trade_details, dict):
        for entry in trade_details.values():
            candidate = _entry_for_dosage(entry, dosage) if isinstance(entry, dict) else None
            if not isinstance(candidate, dict):
                continue
            qty = _pack_qty(candidate)
            if qty > best_qty:
                best_qty = qty
                best = candidate
    if best:
        return dict(best)
    fallback = str(fallback_packaging or "").strip()
    if fallback:
        return {"packaging": fallback, "dispense_qty": _pack_qty({"packaging": fallback})}
    return None
