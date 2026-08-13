"""Добавление препарата в каталог по МНН через tabletka.by."""

from __future__ import annotations

import re
from typing import Any

from backend.tabletka_enrich import enrich_by_russian_name, enrichment_to_seed_fields
from backend.trade_packaging import trade_details_from_variants


_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu",
    "я": "ya",
}


def _looks_latin(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9 \-']*", str(value or "").strip()))


def _transliterate_to_mnn(value: str) -> str:
    text = str(value or "").strip().lower().replace("ё", "е")
    out: list[str] = []
    for char in text:
        if char in _TRANSLIT:
            out.append(_TRANSLIT[char])
        elif char.isascii() and char.isalnum():
            out.append(char)
        elif char in {" ", "-", "_"}:
            out.append(" ")
    compact = re.sub(r"\s+", " ", "".join(out)).strip()
    if not compact:
        return "CustomDrug"
    return "".join(part.capitalize() for part in compact.split(" "))


def build_mnn_key(query: str, russian_name: str = "") -> str:
    q = str(query or "").strip()
    if _looks_latin(q):
        return re.sub(r"\s+", " ", q).title().replace(" ", "")
    return _transliterate_to_mnn(russian_name or q)


def payload_from_tabletka_query(query: str, *, enricher=None) -> dict[str, Any]:
    if enricher is None:
        enricher = enrich_by_russian_name
    name = str(query or "").strip()
    if len(name) < 3:
        raise ValueError("Введите МНН (минимум 3 символа).")

    enrichment = enricher(name)
    fields = enrichment_to_seed_fields(enrichment)
    if not fields:
        raise ValueError(
            enrichment.message
            or f"На tabletka.by ничего не найдено по «{name}»."
        )

    russian = str(enrichment.mnn_text or name).strip()
    mnn = build_mnn_key(name, russian)
    variants = (fields.get("tabletka") or {}).get("variants") or []
    trade_details = trade_details_from_variants(variants) or fields.get("trade_details") or {}

    return {
        "category": "Прочее",
        "mnn": mnn,
        "russian_name": russian,
        "latin_name": mnn if _looks_latin(mnn) else russian,
        "drug_form": fields.get("drug_form") or "Tab.",
        "dosage": fields.get("dosage") or "",
        "packaging": fields.get("packaging") or "N30",
        "form_options": fields.get("form_options") or ["Tab."],
        "dosage_options": fields.get("dosage_options") or [],
        "form_dosage_map": fields.get("form_dosage_map") or {},
        "trade_names": fields.get("trade_names") or [],
        "trade_details": trade_details,
        "scheme_options": [
            "по 1 таблетке утром",
            "по 1 таблетке вечером",
            "по 1/2 таблетки на ночь",
        ],
        "search_aliases": list(dict.fromkeys([
            russian.lower(),
            mnn.lower(),
            name.lower(),
            *[str(t).lower() for t in (fields.get("trade_names") or [])],
        ])),
        "tabletka_meta": {
            "mnn_id": enrichment.mnn_id,
            "mnn_text": enrichment.mnn_text,
            "variants_count": len(variants),
            "message": enrichment.message,
        },
    }


def add_custom_drug_from_tabletka(repository: Any, query: str, *, enricher=None) -> dict[str, Any]:
    payload = payload_from_tabletka_query(query, enricher=enricher)
    meta = payload.pop("tabletka_meta", {})
    russian_key = str(payload["russian_name"]).strip().lower().replace("ё", "е")
    for existing in repository.list_drugs():
        existing_ru = str(existing.get("russian_name") or "").strip().lower().replace("ё", "е")
        if existing_ru and existing_ru == russian_key:
            raise ValueError(
                f"«{payload['russian_name']}» уже есть в каталоге "
                f"(МНН: {existing.get('mnn')})."
            )
    saved = repository.upsert_custom_drug(payload)
    return {
        **saved,
        "russian_name": payload["russian_name"],
        "trade_names": payload["trade_names"],
        "dosage_options": payload["dosage_options"],
        "form_options": payload["form_options"],
        "packaging": payload["packaging"],
        "tabletka": meta,
        "message": (
            f"Добавлен «{payload['russian_name']}»: "
            f"{len(payload['trade_names'])} торг., "
            f"{len(payload['dosage_options'])} доз."
        ),
    }
