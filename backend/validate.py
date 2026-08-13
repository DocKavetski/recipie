"""Валидация данных перед печатью / сохранением."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.patient_parse import (
    format_name_with_initials,
    normalize_birth_date,
    normalize_card_number,
    parse_birth_date,
)
from backend.dispense_rules import ceil_to_dispense_step, dispense_step_by_packaging
from backend.numbers_ru import extract_default_dispense_qty


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    errors: list[str]
    warnings: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "errors": self.errors, "warnings": self.warnings}


def _filled_drugs(payload: dict[str, Any]) -> list[dict[str, Any]]:
    drugs = payload.get("drugs") or []
    return [drug for drug in drugs if str(drug.get("mnn") or "").strip()]


def validate_prescription_payload(payload: dict[str, Any] | None, *, require_card: bool = False) -> ValidationResult:
    data = payload or {}
    errors: list[str] = []
    warnings: list[str] = []

    patient_name = format_name_with_initials(data.get("patient_name", ""))
    birth_date = normalize_birth_date(data.get("birth_date", ""))
    doctor_name = str(data.get("doctor_name") or "").strip()
    card_number = str(data.get("card_number") or "").strip()
    drugs = _filled_drugs(data)

    if not patient_name:
        errors.append("Укажите ФИО пациента.")
    if not birth_date:
        errors.append("Укажите дату рождения.")
    elif parse_birth_date(birth_date) is None:
        errors.append("Дата рождения некорректна.")
    if not doctor_name:
        errors.append("Укажите врача в настройках.")
    if not drugs:
        errors.append("Добавьте хотя бы один препарат.")
    if require_card and not card_number:
        errors.append("Для истории нужен номер карты.")

    for index, drug in enumerate(drugs, start=1):
        if not str(drug.get("drug_form") or "").strip():
            warnings.append(f"Препарат {index}: не указана форма.")
        if not str(drug.get("dosage") or "").strip():
            warnings.append(f"Препарат {index}: не указана дозировка.")
        if not str(drug.get("selectedScheme") or "").strip():
            warnings.append(f"Препарат {index}: не выбрана схема.")
        qty = drug.get("dispenseQty")
        try:
            qty_num = int(qty)
            if qty_num < 1:
                warnings.append(f"Препарат {index}: количество D.t.d. меньше 1.")
                continue
            pack_qty = extract_default_dispense_qty(drug.get("packaging"))
            step = dispense_step_by_packaging(drug.get("packaging"))
            if step > 1 and qty_num % step != 0:
                errors.append(
                    f"Препарат {index}: количество D.t.d. должно быть кратно {step} (фасовка {pack_qty})."
                )
        except (TypeError, ValueError):
            warnings.append(f"Препарат {index}: некорректное количество D.t.d.")

    return ValidationResult(ok=not errors, errors=errors, warnings=warnings)


def normalize_prescription_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    data = dict(payload or {})
    data["patient_name"] = format_name_with_initials(data.get("patient_name", ""))
    data["birth_date"] = normalize_birth_date(data.get("birth_date", ""))
    data["doctor_name"] = str(data.get("doctor_name") or "").strip()
    data["card_number"] = normalize_card_number(data.get("card_number", ""))
    drugs = []
    for drug in data.get("drugs") or []:
        if not str(drug.get("mnn") or "").strip():
            continue
        item = dict(drug)
        raw_qty = item.get("dispenseQty")
        try:
            qty_num = int(str(raw_qty).strip())
        except (TypeError, ValueError):
            try:
                qty_num = int(float(str(raw_qty).strip()))
            except (TypeError, ValueError):
                qty_num = 0
        if qty_num < 1:
            packaging = item.get("packaging")
            item["dispenseQty"] = ceil_to_dispense_step(
                extract_default_dispense_qty(packaging),
                packaging,
            )
        else:
            item["dispenseQty"] = qty_num
        drugs.append(item)
    data["drugs"] = drugs
    return data


def chunk_drugs(drugs: list[dict[str, Any]], size: int = 2) -> list[list[dict[str, Any]]]:
    return [drugs[i:i + size] for i in range(0, len(drugs), size)]


def duplex_back_index(front_index: int) -> int:
    mirror = [1, 0, 3, 2]
    return mirror[front_index]
