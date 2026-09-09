"""Загрузка и нормализация справочника препаратов из протоколов."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from backend.trade_packaging import normalize_trade_details, trade_details_from_variants

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


def _form_unit(item: dict[str, Any]) -> str:
    form = str(item.get("drug_form") or "Tab.")
    return "капсуле" if form.lower().startswith("caps") else "таблетке"


# Типовые схемы приёма для выписки (S.): по классу препарата / МНН.
# Короткие формулировки под бланк формы 1 (поддержка + начало + отмена).
_MAX_SCHEMES = 8
_SCHEMES_BY_MNN: dict[str, list[str]] = {
    # СИОЗС
    "Escitalopram": [
        "по 1 таблетке утром",
        "по 1/2 таблетки утром",
        "по 1 таблетке вечером",
        "начало: по 1/2 таб. утром 7 дней, далее по 1 таб. утром",
        "отмена: по 1/2 таб. утром 7–14 дней, затем отменить",
        "отмена: через день 7–14 дней, затем отменить",
    ],
    "Sertraline": [
        "по 1 таблетке утром",
        "по 1/2 таблетки утром",
        "по 1 таблетке вечером",
        "начало: по 1/2 таб. утром 7 дней, далее по 1 таб. утром",
        "отмена: по 1/2 таб. утром 7–14 дней, затем отменить",
        "отмена: через день 7–14 дней, затем отменить",
    ],
    "Fluoxetine": [
        "по 1 капсуле утром",
        "по 1 капсуле утром (через день)",
        "по 2 капсулы утром",
        "начало: по 1 капс. утром",
        "отмена: по 1 капс. через день 7–14 дней, затем отменить",
        "отмена: по 1 капс. утром ещё 7 дней, затем отменить",
    ],
    "Paroxetine": [
        "по 1 таблетке утром",
        "по 1 таблетке вечером",
        "по 1/2 таблетки утром",
        "начало: по 1/2 таб. утром 7 дней, далее по 1 таб. утром",
        "отмена: по 1/2 таб. утром 7–14 дней, затем через день, затем отменить",
        "отмена: через день 14 дней, затем отменить",
    ],
    "Fluvoxamine": [
        "по 1 таблетке на ночь",
        "по 1 таблетке вечером",
        "по 1/2 таблетки на ночь",
        "по 1 таблетке утром и на ночь",
        "начало: по 1/2 таб. на ночь 7 дней, далее по 1 таб. на ночь",
        "отмена: по 1/2 таб. на ночь 7–14 дней, затем отменить",
        "отмена: через день 7–14 дней, затем отменить",
    ],
    "Vortioxetine": [
        "по 1 таблетке утром",
        "по 1/2 таблетки утром",
        "по 1 таблетке вечером",
        "начало: по 1/2 таб. утром 7 дней, далее по 1 таб. утром",
        "отмена: по 1/2 таб. утром 7–14 дней, затем отменить",
        "отмена: через день 7–14 дней, затем отменить",
    ],
    # СИОЗСН
    "Venlafaxine": [
        "по 1 таблетке утром",
        "по 1 таблетке утром и вечером",
        "по 1/2 таблетки утром",
        "по 1 таблетке вечером",
        "начало: по 1/2 таб. утром 7 дней, далее по 1 таб. утром",
        "отмена: по 1/2 таб. утром 7–14 дней, затем через день, затем отменить",
        "отмена: ступенчато снижать дозу каждые 7 дней",
    ],
    "Duloxetine": [
        "по 1 капсуле утром",
        "по 1 капсуле вечером",
        "по 1 капсуле утром и вечером",
        "начало: по 1 капс. утром",
        "отмена: через день 7–14 дней, затем отменить",
        "отмена: ступенчато снижать дозу каждые 7 дней",
    ],
    # ТЦА / тетрациклические
    "Amitriptyline": [
        "по 1 таблетке на ночь",
        "по 1/2 таблетки на ночь",
        "по 1 таблетке вечером",
        "по 1 таблетке утром и на ночь",
        "начало: по 1/2 таб. на ночь 7 дней, далее по 1 таб. на ночь",
        "отмена: по 1/2 таб. на ночь 7–14 дней, затем отменить",
        "отмена: ступенчато снижать дозу каждые 7 дней",
    ],
    "Clomipramine": [
        "по 1 таблетке на ночь",
        "по 1 таблетке вечером",
        "по 1/2 таблетки на ночь",
        "по 1 таблетке утром и вечером",
        "начало: по 1/2 таб. на ночь 7 дней, далее по 1 таб. на ночь",
        "отмена: по 1/2 таб. на ночь 7–14 дней, затем отменить",
        "отмена: ступенчато снижать дозу каждые 7 дней",
    ],
    "Mirtazapine": [
        "по 1 таблетке на ночь",
        "по 1/2 таблетки на ночь",
        "по 1 таблетке вечером",
        "начало: по 1/2 таб. на ночь 7 дней, далее по 1 таб. на ночь",
        "отмена: по 1/2 таб. на ночь 7–14 дней, затем отменить",
        "отмена: через день 7–14 дней, затем отменить",
    ],
    "Maprotiline": [
        "по 1 таблетке на ночь",
        "по 1 таблетке вечером",
        "по 1/2 таблетки на ночь",
        "начало: по 1/2 таб. на ночь 7 дней, далее по 1 таб. на ночь",
        "отмена: по 1/2 таб. на ночь 7–14 дней, затем отменить",
        "отмена: ступенчато снижать дозу каждые 7 дней",
    ],
    # Антипсихотики
    "Quetiapine": [
        "по 1 таблетке на ночь",
        "по 1/2 таблетки на ночь",
        "по 1 таблетке вечером",
        "по 1 таблетке утром и на ночь",
        "по 1 таблетке 2 раза в день",
        "начало: по 1/2 таб. на ночь 3–7 дней, далее по 1 таб. на ночь",
        "отмена: по 1/2 таб. на ночь 7–14 дней, затем отменить",
    ],
    "Olanzapine": [
        "по 1 таблетке на ночь",
        "по 1/2 таблетки на ночь",
        "по 1 таблетке вечером",
        "по 1 таблетке утром",
        "начало: по 1/2 таб. на ночь, далее по 1 таб. на ночь",
        "отмена: по 1/2 таб. на ночь 7–14 дней, затем отменить",
    ],
    "Risperidone": [
        "по 1 таблетке на ночь",
        "по 1 таблетке вечером",
        "по 1/2 таблетки на ночь",
        "по 1 таблетке утром и вечером",
        "по 1 таблетке 2 раза в день",
        "начало: по 1/2 таб. на ночь 3–7 дней, далее по 1 таб. на ночь",
        "отмена: по 1/2 таб. на ночь 7–14 дней, затем отменить",
    ],
    "Aripiprazole": [
        "по 1 таблетке утром",
        "по 1/2 таблетки утром",
        "по 1 таблетке вечером",
        "начало: по 1/2 таб. утром 7 дней, далее по 1 таб. утром",
        "отмена: по 1/2 таб. утром 7–14 дней, затем отменить",
        "отмена: через день 7–14 дней, затем отменить",
    ],
    "Cariprazine": [
        "по 1 капсуле утром",
        "по 1 капсуле вечером",
        "по 1 капсуле через день",
        "начало: по 1 капс. утром",
        "отмена: через день 7–14 дней, затем отменить",
    ],
    "Haloperidol": [
        "по 1 таблетке на ночь",
        "по 1 таблетке вечером",
        "по 1 таблетке утром и вечером",
        "по 1 таблетке 2 раза в день",
        "по 1 таблетке 3 раза в день",
        "начало: по 1/2–1 таб. на ночь",
        "отмена: ступенчато снижать дозу каждые 7 дней",
    ],
    "Clozapine": [
        "по 1 таблетке на ночь",
        "по 1 таблетке вечером",
        "по 1 таблетке утром и на ночь",
        "по 1/2 таблетки на ночь",
        "начало: по 1/2 таб. на ночь с медленной титрацией",
        "отмена: медленно снижать дозу (не резко)",
    ],
    "Sulpiride": [
        "по 1 таблетке утром",
        "по 1 таблетке утром и днём",
        "по 1 таблетке 2 раза в день",
        "по 1/2 таблетки утром",
        "начало: по 1/2–1 таб. утром",
        "отмена: ступенчато снижать дозу каждые 7 дней",
    ],
    "Chlorprothixene": [
        "по 1 таблетке на ночь",
        "по 1 таблетке вечером",
        "по 1/2 таблетки на ночь",
        "по 1 таблетке утром и на ночь",
        "начало: по 1/2 таб. на ночь, далее по 1 таб. на ночь",
        "отмена: по 1/2 таб. на ночь 7–14 дней, затем отменить",
    ],
    "Flupentixol": [
        "по 1 таблетке утром",
        "по 1/2 таблетки утром",
        "по 1 таблетке утром и днём",
        "начало: по 1/2 таб. утром, далее по 1 таб. утром",
        "отмена: по 1/2 таб. утром 7–14 дней, затем отменить",
    ],
    "Periciazine": [
        "по 1 таблетке на ночь",
        "по 1 таблетке вечером",
        "по 1/2 таблетки на ночь",
        "по 1 таблетке утром и вечером",
        "начало: по 1/2 таб. на ночь, далее по 1 таб. на ночь",
        "отмена: по 1/2 таб. на ночь 7–14 дней, затем отменить",
    ],
    # Нормотимики / антиконвульсанты
    "Lithium carbonate": [
        "по 1 таблетке вечером",
        "по 1 таблетке утром и вечером",
        "по 1 таблетке 2 раза в день",
        "по 2 таблетки вечером",
        "начало: по 1 таб. вечером с контролем уровня Li",
        "отмена: ступенчато снижать дозу под контролем уровня Li",
    ],
    "Valproic acid": [
        "по 1 таблетке вечером",
        "по 1 таблетке утром и вечером",
        "по 1 таблетке 2 раза в день",
        "по 1 таблетке 3 раза в день",
        "начало: по 1 таб. вечером, далее утром и вечером",
        "отмена: ступенчато снижать дозу каждые 7 дней",
    ],
    "Carbamazepine": [
        "по 1 таблетке утром и вечером",
        "по 1 таблетке 2 раза в день",
        "по 1/2 таблетки утром и вечером",
        "по 1 таблетке 3 раза в день",
        "начало: по 1/2 таб. утром и вечером 7 дней, далее по 1 таб. 2 раза в день",
        "отмена: ступенчато снижать дозу каждые 7 дней",
    ],
    "Oxcarbazepine": [
        "по 1 таблетке утром и вечером",
        "по 1 таблетке 2 раза в день",
        "по 1/2 таблетки утром и вечером",
        "по 1 таблетке на ночь",
        "начало: по 1/2 таб. утром и вечером 7 дней, далее по 1 таб. 2 раза в день",
        "отмена: ступенчато снижать дозу каждые 7 дней",
    ],
    "Lamotrigine": [
        "по 1 таблетке утром",
        "по 1 таблетке утром и вечером",
        "по 1/2 таблетки утром",
        "по 1 таблетке вечером",
        "начало: по 1/2 таб. утром 14 дней, далее по 1 таб. утром",
        "начало: медленная титрация (ламотриджин)",
        "отмена: ступенчато снижать дозу каждые 7–14 дней",
    ],
    "Gabapentin": [
        "по 1 капсуле утром и вечером",
        "по 1 капсуле 3 раза в день",
        "по 1 капсуле на ночь",
        "по 1 капсуле 2 раза в день",
        "начало: по 1 капс. на ночь 3–7 дней, далее 2–3 раза в день",
        "отмена: ступенчато снижать дозу каждые 7 дней",
    ],
    "Pregabalin": [
        "по 1 капсуле утром и вечером",
        "по 1 капсуле на ночь",
        "по 1 капсуле 2 раза в день",
        "по 1 капсуле вечером",
        "начало: по 1 капс. на ночь 3–7 дней, далее утром и вечером",
        "отмена: ступенчато снижать дозу каждые 7 дней",
    ],
    # Анксиолитики
    "Buspirone": [
        "по 1 таблетке 2 раза в день",
        "по 1 таблетке 3 раза в день",
        "по 1 таблетке утром и вечером",
        "по 1/2 таблетки 3 раза в день",
        "начало: по 1/2 таб. 2–3 раза в день 7 дней, далее по 1 таб.",
        "отмена: ступенчато снижать дозу каждые 7 дней",
    ],
    "Tofisopam": [
        "по 1 таблетке утром",
        "по 1 таблетке утром и днём",
        "по 1 таблетке 2 раза в день",
        "по 1/2 таблетки утром",
        "начало: по 1/2–1 таб. утром",
        "отмена: по 1/2 таб. утром 7 дней, затем отменить",
    ],
    "Phenibut": [
        "по 1 таблетке 2 раза в день",
        "по 1 таблетке 3 раза в день",
        "по 1 таблетке утром и днём",
        "по 1 таблетке после еды",
        "начало: по 1 таб. 2 раза в день",
        "отмена: ступенчато снижать дозу каждые 7 дней",
    ],
    # Сон
    "Zopiclone": [
        "по 1 таблетке на ночь",
        "по 1/2 таблетки на ночь",
        "по 1 таблетке за 30 мин. до сна",
        "начало: по 1/2–1 таб. на ночь коротким курсом",
        "отмена: по 1/2 таб. на ночь 3–7 дней, затем отменить",
    ],
    "Melatonin": [
        "по 1 таблетке за 30–60 мин. до сна",
        "по 1 таблетке на ночь",
        "по 1/2 таблетки на ночь",
        "начало: по 1 таб. за 30–60 мин. до сна",
        "отмена: можно отменить без снижения",
    ],
    # Ноотропы / ADHD
    "Atomoxetine": [
        "по 1 капсуле утром",
        "по 1 капсуле утром и вечером",
        "по 1 капсуле вечером",
        "начало: по 1 капс. утром",
        "отмена: можно отменить или снизить через день на 7 дней",
    ],
    # Сопутствующие (β-блокаторы)
    "Atenolol": [
        "по 1 таблетке утром",
        "по 1/2 таблетки утром",
        "по 1 таблетке утром и вечером",
        "начало: по 1/2–1 таб. утром",
        "отмена: по 1/2 таб. утром 7 дней, затем отменить",
    ],
    "Bisoprolol": [
        "по 1 таблетке утром",
        "по 1/2 таблетки утром",
        "по 1 таблетке утром (постоянно)",
        "начало: по 1/2–1 таб. утром",
        "отмена: по 1/2 таб. утром 7 дней, затем отменить",
    ],
    "Propranolol": [
        "по 1 таблетке за 30–60 мин. до ситуации",
        "по 1 таблетке 2 раза в день",
        "по 1 таблетке 3 раза в день",
        "по 1/2 таблетки при тревоге",
        "начало: по 1/2–1 таб. 2 раза в день",
        "отмена: ступенчато снижать дозу каждые 7 дней",
    ],
}


def _category_fallback_schemes(category: str, unit: str) -> list[str]:
    key = str(category or "").strip().lower()
    if key in {"сиозс", "сиозсн"}:
        return [
            f"по 1 {unit} утром",
            f"по 1/2 {unit} утром",
            f"по 1 {unit} вечером",
            f"начало: по 1/2 {unit} утром 7 дней, далее по 1 {unit} утром",
            f"отмена: по 1/2 {unit} утром 7–14 дней, затем отменить",
            f"отмена: через день 7–14 дней, затем отменить",
        ]
    if key in {"тца", "антидепрессанты"}:
        return [
            f"по 1 {unit} на ночь",
            f"по 1/2 {unit} на ночь",
            f"по 1 {unit} вечером",
            f"начало: по 1/2 {unit} на ночь 7 дней, далее по 1 {unit} на ночь",
            f"отмена: по 1/2 {unit} на ночь 7–14 дней, затем отменить",
            f"отмена: ступенчато снижать дозу каждые 7 дней",
        ]
    if key == "антипсихотики":
        return [
            f"по 1 {unit} на ночь",
            f"по 1 {unit} вечером",
            f"по 1 {unit} утром",
            f"по 1 {unit} утром и вечером",
            f"начало: по 1/2 {unit} 3–7 дней, далее по 1 {unit}",
            f"отмена: ступенчато снижать дозу каждые 7 дней",
        ]
    if key == "нормотимики":
        return [
            f"по 1 {unit} утром и вечером",
            f"по 1 {unit} 2 раза в день",
            f"по 1 {unit} вечером",
            f"начало: по 1/2–1 {unit} с постепенным повышением",
            f"отмена: ступенчато снижать дозу каждые 7 дней",
        ]
    if key == "анксиолитики":
        return [
            f"по 1 {unit} 2 раза в день",
            f"по 1 {unit} 3 раза в день",
            f"по 1 {unit} утром и вечером",
            f"начало: по 1/2 {unit} 2–3 раза в день",
            f"отмена: ступенчато снижать дозу каждые 7 дней",
        ]
    if key == "сон":
        return [
            f"по 1 {unit} на ночь",
            f"по 1/2 {unit} на ночь",
            f"по 1 {unit} за 30 мин. до сна",
            f"отмена: по 1/2 {unit} на ночь 3–7 дней, затем отменить",
        ]
    if key == "ноотропы":
        return [f"по 1 {unit} утром", f"по 1 {unit} утром и вечером"]
    if key == "сопутствующие":
        return [
            f"по 1 {unit} утром",
            f"по 1/2 {unit} утром",
            f"по 1 {unit} 2 раза в день",
            f"отмена: по 1/2 {unit} утром 7 дней, затем отменить",
        ]
    return [f"по 1 {unit} утром", f"по 1 {unit} вечером", f"по 1 {unit} на ночь"]


def _default_schemes(item: dict[str, Any]) -> list[str]:
    schemes = [str(s).strip() for s in (item.get("scheme_options") or []) if str(s).strip()]
    if schemes:
        return schemes[:_MAX_SCHEMES]
    mnn = str(item.get("mnn") or "").strip()
    by_mnn = _SCHEMES_BY_MNN.get(mnn)
    if by_mnn:
        return list(by_mnn)[:_MAX_SCHEMES]
    unit = _form_unit(item)
    return _category_fallback_schemes(item.get("category", ""), unit)[:_MAX_SCHEMES]


# Справка для вкладки «Схемы»: макс. суточная доза и режим отмены.
# discontinuation: taper | abrupt | optional
_CLINICAL_REF_BY_MNN: dict[str, dict[str, str]] = {
    "Escitalopram": {"max_daily_dose": "20 мг/сут", "discontinuation": "taper"},
    "Sertraline": {"max_daily_dose": "200 мг/сут", "discontinuation": "taper"},
    "Fluoxetine": {"max_daily_dose": "80 мг/сут", "discontinuation": "taper"},
    "Paroxetine": {"max_daily_dose": "50 мг/сут", "discontinuation": "taper"},
    "Fluvoxamine": {"max_daily_dose": "300 мг/сут", "discontinuation": "taper"},
    "Vortioxetine": {"max_daily_dose": "20 мг/сут", "discontinuation": "taper"},
    "Venlafaxine": {"max_daily_dose": "225 мг/сут", "discontinuation": "taper"},
    "Duloxetine": {"max_daily_dose": "120 мг/сут", "discontinuation": "taper"},
    "Clomipramine": {"max_daily_dose": "250 мг/сут", "discontinuation": "taper"},
    "Amitriptyline": {"max_daily_dose": "150 мг/сут", "discontinuation": "taper"},
    "Maprotiline": {"max_daily_dose": "150 мг/сут", "discontinuation": "taper"},
    "Mirtazapine": {"max_daily_dose": "45 мг/сут", "discontinuation": "taper"},
    "Lithium carbonate": {"max_daily_dose": "по уровню Li", "discontinuation": "taper"},
    "Carbamazepine": {"max_daily_dose": "1600 мг/сут", "discontinuation": "taper"},
    "Valproic acid": {"max_daily_dose": "2500 мг/сут", "discontinuation": "taper"},
    "Lamotrigine": {"max_daily_dose": "400 мг/сут", "discontinuation": "taper"},
    "Oxcarbazepine": {"max_daily_dose": "2400 мг/сут", "discontinuation": "taper"},
    "Pregabalin": {"max_daily_dose": "600 мг/сут", "discontinuation": "taper"},
    "Gabapentin": {"max_daily_dose": "3600 мг/сут", "discontinuation": "taper"},
    "Quetiapine": {"max_daily_dose": "800 мг/сут", "discontinuation": "taper"},
    "Olanzapine": {"max_daily_dose": "20 мг/сут", "discontinuation": "taper"},
    "Aripiprazole": {"max_daily_dose": "30 мг/сут", "discontinuation": "taper"},
    "Risperidone": {"max_daily_dose": "16 мг/сут", "discontinuation": "taper"},
    "Clozapine": {"max_daily_dose": "900 мг/сут", "discontinuation": "taper"},
    "Cariprazine": {"max_daily_dose": "6 мг/сут", "discontinuation": "taper"},
    "Haloperidol": {"max_daily_dose": "30 мг/сут", "discontinuation": "taper"},
    "Chlorprothixene": {"max_daily_dose": "600 мг/сут", "discontinuation": "taper"},
    "Sulpiride": {"max_daily_dose": "1600 мг/сут", "discontinuation": "taper"},
    "Periciazine": {"max_daily_dose": "100 мг/сут", "discontinuation": "taper"},
    "Flupentixol": {"max_daily_dose": "18 мг/сут", "discontinuation": "taper"},
    "Buspirone": {"max_daily_dose": "60 мг/сут", "discontinuation": "optional"},
    "Tofisopam": {"max_daily_dose": "300 мг/сут", "discontinuation": "optional"},
    "Phenibut": {"max_daily_dose": "2500 мг/сут", "discontinuation": "taper"},
    "Zopiclone": {"max_daily_dose": "7.5 мг/сут", "discontinuation": "optional"},
    "Melatonin": {"max_daily_dose": "10 мг/сут", "discontinuation": "abrupt"},
    "Bisoprolol": {"max_daily_dose": "10 мг/сут", "discontinuation": "optional"},
    "Propranolol": {"max_daily_dose": "160 мг/сут", "discontinuation": "abrupt"},
    "Atenolol": {"max_daily_dose": "100 мг/сут", "discontinuation": "optional"},
    "Atomoxetine": {"max_daily_dose": "100 мг/сут", "discontinuation": "taper"},
}

_DISCONTINUATION_LABELS = {
    "taper": "Нужна плавная отмена",
    "abrupt": "Можно отменить сразу",
    "optional": "Желательна плавная отмена",
}


def _category_clinical_ref(category: str) -> dict[str, str]:
    key = _normalize_category(category).lower()
    if any(token in key for token in ("антидепресс", "ssri", "snri", "трицикл", "нормотимик", "антипсихот", "антиконвульс")):
        return {"max_daily_dose": "по инструкции", "discontinuation": "taper"}
    if "снотвор" in key or "гипнот" in key:
        return {"max_daily_dose": "по инструкции", "discontinuation": "optional"}
    if "анксиолит" in key:
        return {"max_daily_dose": "по инструкции", "discontinuation": "optional"}
    return {"max_daily_dose": "по инструкции", "discontinuation": "optional"}


def _clinical_ref_for(item: dict[str, Any]) -> dict[str, str]:
    mnn = str(item.get("mnn") or "").strip()
    raw = dict(_CLINICAL_REF_BY_MNN.get(mnn) or _category_clinical_ref(item.get("category", "")))
    if item.get("max_daily_dose"):
        raw["max_daily_dose"] = str(item.get("max_daily_dose")).strip()
    if item.get("discontinuation"):
        raw["discontinuation"] = str(item.get("discontinuation")).strip().lower()
    mode = raw.get("discontinuation") or "optional"
    if mode not in _DISCONTINUATION_LABELS:
        mode = "optional"
    dose = str(raw.get("max_daily_dose") or "по инструкции").strip() or "по инструкции"
    return {
        "max_daily_dose": dose,
        "discontinuation": mode,
        "discontinuation_label": _DISCONTINUATION_LABELS[mode],
    }


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
    if item.get("archived"):
        return None
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
    variants = (item.get("tabletka") or {}).get("variants") or []
    if variants:
        trade_details = trade_details_from_variants(variants)
    else:
        trade_details = normalize_trade_details(trade_details)
    if not trade_details and trade_names:
        trade_details = normalize_trade_details({
            name: {"packaging": packaging, "dispense_qty": dispense_qty, "dosage": dosage}
            for name in trade_names
        })

    clinical_ref = _clinical_ref_for(item)
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
        "max_daily_dose": clinical_ref["max_daily_dose"],
        "discontinuation": clinical_ref["discontinuation"],
        "discontinuation_label": clinical_ref["discontinuation_label"],
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


def _archived_seed_candidates(path: Path | None = None) -> list[Path]:
    import sys

    candidates: list[Path] = []
    if path is not None:
        candidates.append(Path(path))
    root = Path(__file__).resolve().parents[1]
    candidates.append(root / "data" / "archived_drugs.json")
    if getattr(sys, "frozen", False):
        meipass = Path(getattr(sys, "_MEIPASS", root))
        candidates.append(meipass / "data" / "archived_drugs.json")
        candidates.append(Path(sys.executable).resolve().parent / "data" / "archived_drugs.json")
    return candidates


def load_archived_drugs(path: Path | None = None) -> list[dict[str, Any]]:
    """Препараты вне продажи — только для просмотра в справочнике."""
    candidates = _archived_seed_candidates(path)
    archive_path = next((candidate for candidate in candidates if candidate.exists()), None)
    if archive_path is None:
        return []

    raw = json.loads(archive_path.read_text(encoding="utf-8"))
    drugs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        payload = dict(item or {})
        payload["archived"] = True
        # Не через normalize_seed_item: archived там отсекается.
        russian = str(payload.get("russian_name") or "").strip()
        mnn = str(payload.get("mnn") or "").strip()
        if not russian or not mnn:
            continue
        key = mnn.lower()
        if key in seen:
            continue
        seen.add(key)
        drugs.append(
            {
                "category": _normalize_category(payload.get("category", "")),
                "mnn": mnn,
                "russian_name": russian,
                "latin_name": str(payload.get("latin_name") or "").strip(),
                "drug_form": str(payload.get("drug_form") or "Tab.").strip() or "Tab.",
                "dosage": str(payload.get("dosage") or "").strip(),
                "packaging": str(payload.get("packaging") or "").strip(),
                "form_options": list(payload.get("form_options") or ([payload.get("drug_form")] if payload.get("drug_form") else ["Tab."])),
                "dosage_options": list(payload.get("dosage_options") or ([payload.get("dosage")] if payload.get("dosage") else [])),
                "trade_names": [str(x).strip() for x in (payload.get("trade_names") or []) if str(x).strip()],
                "archived": True,
                "archive_reason": str(payload.get("archive_reason") or "Архив").strip(),
            }
        )
    drugs.sort(key=lambda item: (item.get("category") or "", item.get("russian_name") or ""))
    return drugs
