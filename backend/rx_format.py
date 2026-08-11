"""Форматирование строк Rp на бланке формы 1."""

from __future__ import annotations

from typing import Any

from backend.latin_gen import generate_genitive
from backend.numbers_ru import number_to_words_ru

# Tab. / Caps. → «in tab.» / «in caps.»; остальные формы — по тому же шаблону.
_FORM_IN = {
    "tab.": "in tab.",
    "tab": "in tab.",
    "caps.": "in caps.",
    "caps": "in caps.",
    "sol.": "in sol.",
    "sol": "in sol.",
    "sir.": "in sir.",
    "sir": "in sir.",
}


def drug_title(drug: dict[str, Any]) -> str:
    if drug.get("mode") == "trade" and drug.get("selectedTrade"):
        return str(drug["selectedTrade"]).strip()
    return generate_genitive(drug.get("latin_name", "")).strip()


def form_in_phrase(drug_form: str | None) -> str:
    raw = str(drug_form or "").strip()
    if not raw:
        return "in tab."
    key = raw.lower().rstrip(".")
    mapped = _FORM_IN.get(f"{key}.") or _FORM_IN.get(key)
    if mapped:
        return mapped
    return f"in {key}."


def format_rp_lines(drug: dict[str, Any]) -> list[str]:
    """
    Классическая выписка:
      1) Название, дозировка
      2) D.t.d. № N (…) in tab.|in caps.
      3) S. схема приёма
    """
    title = drug_title(drug)
    dosage = str(drug.get("dosage") or "").strip()
    name_line = " ".join(part for part in (title, dosage) if part).strip()

    qty = drug.get("dispenseQty", "")
    try:
        qty_words = number_to_words_ru(qty)
    except Exception:  # noqa: BLE001
        qty_words = str(qty)
    dtd = f"D.t.d. № {qty} ({qty_words}) {form_in_phrase(drug.get('drug_form'))}".strip()

    scheme = str(drug.get("selectedScheme") or "").strip()
    sig = f"S. {scheme}".strip() if scheme else "S."

    return [name_line, dtd, sig]
