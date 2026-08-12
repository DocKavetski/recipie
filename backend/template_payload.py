"""Нормализация payload шаблонов рецепта."""

from __future__ import annotations

from typing import Any


def normalize_template_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    drugs: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        raw_drugs = payload.get("drugs") or []
        if isinstance(raw_drugs, list):
            for drug in raw_drugs:
                if not isinstance(drug, dict):
                    continue
                mnn = str(drug.get("mnn") or "").strip()
                russian_name = str(drug.get("russian_name") or "").strip()
                if not mnn and not russian_name:
                    continue
                cleaned = {key: value for key, value in drug.items() if key != "availability"}
                drugs.append(cleaned)
    return {"drugs": drugs}
