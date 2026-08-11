"""Shared preview context for HTML preview and PDF output."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.patient_parse import format_name_with_initials, normalize_birth_date
from backend.rx_format import format_rp_lines
from backend.validate import chunk_drugs, duplex_back_index


def today_long_text(now: datetime | None = None) -> str:
    months = [
        "",
        "января",
        "февраля",
        "марта",
        "апреля",
        "мая",
        "июня",
        "июля",
        "августа",
        "сентября",
        "октября",
        "ноября",
        "декабря",
    ]
    current = now or datetime.now()
    return f"{current.day} {months[current.month]} {current.year} г."


def _preview_drug(drug: dict[str, Any] | None) -> dict[str, Any] | None:
    if not drug:
        return None
    return {
        "rp_lines": format_rp_lines(drug),
        "packaging": str(drug.get("packaging") or "").strip(),
        "trade_name": str(drug.get("selectedTrade") or "").strip(),
        "mnn": str(drug.get("mnn") or "").strip(),
        "russian_name": str(drug.get("russian_name") or "").strip(),
        "drug_form": str(drug.get("drug_form") or "").strip(),
        "dosage": str(drug.get("dosage") or "").strip(),
    }


def build_preview_context(payload: dict[str, Any], stamp_text: str, unp: str) -> dict[str, Any]:
    drugs = [drug for drug in payload.get("drugs", []) if drug.get("mnn")]
    blanks = chunk_drugs(drugs, size=2)
    front_batches: list[list[dict[str, Any] | None]] = []
    back_filled_batches: list[list[bool]] = []

    for i in range(0, len(blanks), 4):
        batch = [blanks[i + offset] if i + offset < len(blanks) else None for offset in range(4)]
        front_batches.append(batch)
        back_filled_batches.append([bool(batch[idx]) for idx in range(4)])

    return {
        "stamp_lines": [line.strip() for line in str(stamp_text or "").splitlines() if line.strip()],
        "unp": str(unp or "").strip(),
        "today_long": today_long_text(),
        "patient_name": format_name_with_initials(payload.get("patient_name", "")),
        "birth_date": normalize_birth_date(payload.get("birth_date", "")),
        "doctor_name": str(payload.get("doctor_name", "")).strip(),
        "front_batches": [
            [
                [
                    _preview_drug(batch[0] if batch and len(batch) > 0 else None),
                    _preview_drug(batch[1] if batch and len(batch) > 1 else None),
                ]
                if batch
                else None
                for batch in sheet
            ]
            for sheet in front_batches
        ],
        "back_filled_batches": back_filled_batches,
        "duplex_back_slot": [duplex_back_index(i) for i in range(4)],
    }
