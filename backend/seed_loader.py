"""Загрузка и нормализация справочника препаратов из протоколов."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

BENZO_MARKERS = (
    "диазепам", "diazepam", "феназепам", "phenazepam", "клоназепам", "clonazepam",
    "алпразолам", "alprazolam", "лоразепам", "lorazepam",
    "бромазепам", "bromazepam", "нитразепам", "nitrazepam",
    "мидазолам", "midazolam", "оксазепам", "oxazepam", "медазепам", "medazepam",
    "хлордиазепоксид", "бензодиазепин",
)

# Тофизопам (Грандаксин) — «дневной» анксиолитик, оставляем в каталоге по запросу.
BENZO_ALLOWLIST = (
    "тофизопам", "tofisopam", "грандаксин", "grandaxin", "грандопам",
)

CATEGORY_MAP = {
    "ssri antidepressant": "СИОЗС",
    "snri antidepressant": "СИОЗСН",
    "atypical antidepressant": "Антидепрессанты",
    "tricyclic antidepressant": "ТЦА",
    "tetracyclic antidepressant": "Антидепрессанты",
    "typical antipsychotic": "Антипсихотики",
    "atypical antipsychotic": "Антипсихотики",
    "mood stabilizer": "Нормотимики",
    "anticonvulsant": "Нормотимики",
    "anti-dementia": "Деменция",
    "nootropic": "Ноотропы",
    "alcohol dependence": "Зависимости",
    "opioid dependence": "Зависимости",
    "hypnotic": "Сон",
    "anxiolytic": "Анксиолитики",
    "beta blocker": "Сопутствующие",
    "alpha-2 agonist": "Сопутствующие",
    "muscle relaxant": "Сопутствующие",
    "antiparkinsonian": "Сопутствующие",
    "vitamin": "Сопутствующие",
    "hormone": "Сопутствующие",
}

DISALLOWED_FORMS = {"sol.", "sol"}


def _is_benzo(item: dict[str, Any]) -> bool:
    blob = " ".join(
        [
            str(item.get("mnn", "")),
            str(item.get("russian_name", "")),
            str(item.get("latin_name", "")),
            " ".join(item.get("trade_names") or []),
            " ".join(item.get("search_aliases") or []),
            str(item.get("category", "")),
        ]
    ).lower()
    if any(marker in blob for marker in BENZO_ALLOWLIST):
        return False
    return any(marker in blob for marker in BENZO_MARKERS) or blob.endswith("zepam") or "зепам" in blob


def _normalize_category(raw: str) -> str:
    key = str(raw or "").strip().lower()
    if key in CATEGORY_MAP:
        return CATEGORY_MAP[key]
    if "ssri" in key:
        return "СИОЗС"
    if "snri" in key:
        return "СИОЗСН"
    if "tricyclic" in key or "тца" in key:
        return "ТЦА"
    if "antidepress" in key:
        return "Антидепрессанты"
    if "antipsychotic" in key:
        return "Антипсихотики"
    if "mood" in key or "antiepileptic" in key or "anticonvuls" in key:
        return "Нормотимики"
    if "dementia" in key or "nmda" in key or "ache" in key:
        return "Деменция"
    if "nootropic" in key or "adhd" in key or "cognitive" in key:
        return "Ноотропы"
    if "alcohol" in key or "opioid" in key or "dependence" in key or "withdraw" in key:
        return "Зависимости"
    if "hypnotic" in key or "sleep" in key:
        return "Сон"
    if "anxiolytic" in key or "anxiety" in key:
        return "Анксиолитики"
    if "vitamin" in key or "beta" in key or "park" in key or "adjunct" in key or "enuresis" in key or "muscle" in key or "dopamine" in key or "agonist" in key or "eps" in key or "nms" in key:
        return "Сопутствующие"
    return "Прочее"


def _primary_dosage(raw: str, dosage_options: list[str] | None = None) -> str:
    options = [str(x).strip() for x in (dosage_options or []) if str(x).strip()]
    if options:
        return options[0]
    text = str(raw or "")
    # не брать верхнюю границу суточной дозы как единицу выпуска
    if "сут" in text.lower():
        match = re.search(r"(\d+(?:[.,]\d+)?)\s*мг", text, flags=re.I)
        if match:
            return f"{match.group(1).replace(',', '.')} мг"
        return text.split("(")[0].strip() or text
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*(мг|мкг|г|МЕ|ME)", text, flags=re.I)
    if match:
        unit = match.group(2)
        if unit.upper() == "ME":
            unit = "МЕ"
        return f"{match.group(1).replace(',', '.')} {unit}"
    return text.split("(")[0].strip() or text


def _default_schemes(item: dict[str, Any]) -> list[str]:
    schemes = [s for s in (item.get("scheme_options") or []) if str(s).strip()]
    if schemes:
        return schemes[:6]
    form = str(item.get("drug_form") or "Tab.")
    unit = "капсуле" if form.lower().startswith("caps") else "таблетке"
    return [f"по 1 {unit} утром", f"по 1 {unit} вечером", f"по 1/2 {unit} на ночь"]


def _normalize_form_options(item: dict[str, Any], drug_form: str) -> list[str]:
    options = [str(x).strip() for x in (item.get("form_options") or []) if str(x).strip()]
    if drug_form and drug_form not in options:
        options.insert(0, drug_form)
    allowed = [opt for opt in options if opt.lower().strip() not in DISALLOWED_FORMS]
    fallback = drug_form if drug_form and drug_form.lower().strip() not in DISALLOWED_FORMS else "Tab."
    return list(dict.fromkeys(allowed)) or [fallback]


def _normalize_dosage_options(item: dict[str, Any], dosage: str) -> list[str]:
    options = [str(x).strip() for x in (item.get("dosage_options") or []) if str(x).strip()]
    if dosage and dosage not in options:
        options.insert(0, dosage)
    return list(dict.fromkeys(options)) or ([dosage] if dosage else [])


def _normalize_form_dosage_map(
    item: dict[str, Any],
    form_options: list[str],
    dosage_options: list[str],
) -> dict[str, list[str]]:
    raw = item.get("form_dosage_map") or {}
    result: dict[str, list[str]] = {}
    if isinstance(raw, dict):
        for form, doses in raw.items():
            key = str(form).strip()
            if key.lower() in DISALLOWED_FORMS:
                continue
            cleaned = [str(d).strip() for d in (doses or []) if str(d).strip()]
            if key and cleaned:
                result[key] = list(dict.fromkeys(cleaned))
    if not result:
        for form in form_options:
            result[form] = list(dosage_options)
    for form in form_options:
        result.setdefault(form, list(dosage_options))
    return result


def normalize_seed_item(item: dict[str, Any]) -> dict[str, Any] | None:
    if _is_benzo(item):
        return None

    russian = str(item.get("russian_name") or "").strip()
    mnn = str(item.get("mnn") or "").strip()
    if not russian or not mnn:
        return None

    trade_names = [str(x).strip() for x in (item.get("trade_names") or []) if str(x).strip()]
    aliases = [str(x).strip() for x in (item.get("search_aliases") or []) if str(x).strip()]
    aliases = list(dict.fromkeys([*aliases, russian.lower(), mnn.lower(), *(t.lower() for t in trade_names)]))

    dosage_options_raw = [str(x).strip() for x in (item.get("dosage_options") or []) if str(x).strip()]
    dosage = _primary_dosage(item.get("dosage", ""), dosage_options_raw)
    packaging = str(item.get("packaging") or "N30").strip()
    qty_match = re.search(r"(\d+)", packaging)
    dispense_qty = int(qty_match.group(1)) if qty_match else 30

    drug_form = str(item.get("drug_form") or "Tab.").strip() or "Tab."
    if drug_form.lower() in DISALLOWED_FORMS:
        drug_form = "Tab."
    form_options = _normalize_form_options(item, drug_form)
    dosage_options = _normalize_dosage_options(item, dosage)
    form_dosage_map = _normalize_form_dosage_map(item, form_options, dosage_options)
    if drug_form not in form_options and form_options:
        drug_form = form_options[0]
    mapped = form_dosage_map.get(drug_form) or dosage_options
    if dosage not in mapped and mapped:
        dosage = mapped[0]

    trade_details = item.get("trade_details") or {}
    if not trade_details and trade_names:
        trade_details = {
            name: {"packaging": packaging, "dispense_qty": dispense_qty}
            for name in trade_names
        }

    return {
        "category": _normalize_category(item.get("category", "")),
        "mnn": mnn,
        "russian_name": russian,
        "latin_name": str(item.get("latin_name") or "").strip(),
        "drug_form": drug_form,
        "dosage": dosage,
        "packaging": packaging,
        "form_options": form_options,
        "dosage_options": dosage_options,
        "form_dosage_map": form_dosage_map,
        "trade_names": trade_names,
        "trade_details": trade_details,
        "search_aliases": aliases,
        "scheme_options": _default_schemes(item),
        "dispense_qty": dispense_qty,
    }


def load_seed_drugs(path: Path | None = None) -> list[dict[str, Any]]:
    import sys

    candidates: list[Path] = []
    if path is not None:
        candidates.append(Path(path))
    root = Path(__file__).resolve().parents[1]
    candidates.append(root / "data" / "seed_drugs_from_protocols.json")
    if getattr(sys, "frozen", False):
        meipass = Path(getattr(sys, "_MEIPASS", root))
        candidates.append(meipass / "data" / "seed_drugs_from_protocols.json")
        candidates.append(Path(sys.executable).resolve().parent / "data" / "seed_drugs_from_protocols.json")

    seed_path = next((candidate for candidate in candidates if candidate.exists()), candidates[0])
    raw = json.loads(seed_path.read_text(encoding="utf-8"))
    drugs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        normalized = normalize_seed_item(item)
        if not normalized:
            continue
        key = normalized["mnn"].lower()
        if key in seen:
            continue
        seen.add(key)
        drugs.append(normalized)
    return drugs
