"""Собрать новый seed-каталог из фиксированного списка + tabletka.by."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.tabletka_enrich import enrich_by_russian_name, enrichment_to_seed_fields  # noqa: E402

SEED_PATH = ROOT / "data" / "seed_drugs_from_protocols.json"
REPORT_PATH = ROOT / "data" / "tabletka_curated_report.json"

# Бензодиазепины намеренно не включаем.
# (russian_name, mnn, latin_name, category, extra_aliases)
CURATED: list[tuple[str, str, str, str, list[str]]] = [
    ("Пароксетин", "Paroxetine", "Paroxetinum", "SSRI antidepressant", []),
    ("Эсциталопрам", "Escitalopram", "Escitalopramum", "SSRI antidepressant", ["Ципралекс"]),
    ("Флувоксамин", "Fluvoxamine", "Fluvoxaminum", "SSRI antidepressant", []),
    ("Сертралин", "Sertraline", "Sertralinum", "SSRI antidepressant", []),
    ("Флуоксетин", "Fluoxetine", "Fluoxetinum", "SSRI antidepressant", ["Прозак"]),
    ("Вортиоксетин", "Vortioxetine", "Vortioxetinum", "SSRI antidepressant", ["Бринтелликс", "Brintellix"]),
    ("Венлафаксин", "Venlafaxine", "Venlafaxinum", "SNRI antidepressant", []),
    ("Дулоксетин", "Duloxetine", "Duloxetinum", "SNRI antidepressant", []),
    ("Кломипрамин", "Clomipramine", "Clomipraminum", "tricyclic antidepressant", []),
    ("Амитриптилин", "Amitriptyline", "Amitriptylinum", "tricyclic antidepressant", []),
    ("Мапротилин", "Maprotiline", "Maprotilinum", "tetracyclic antidepressant", []),
    ("Миртазапин", "Mirtazapine", "Mirtazapinum", "atypical antidepressant", []),
    ("Прегабалин", "Pregabalin", "Pregabalinum", "anxiolytic", ["Лирика"]),
    ("Габапентин", "Gabapentin", "Gabapentinum", "anticonvulsant", []),
    ("Карбамазепин", "Carbamazepine", "Carbamazepinum", "mood stabilizer", []),
    ("Вальпроевая кислота", "Valproic acid", "Acidum valproicum", "mood stabilizer", ["Депакин"]),
    ("Окскарбазепин", "Oxcarbazepine", "Oxcarbazepinum", "anticonvulsant", []),
    ("Ламотриджин", "Lamotrigine", "Lamotriginum", "mood stabilizer", []),
    ("Хлорпротиксен", "Chlorprothixene", "Chlorprothixenum", "typical antipsychotic", []),
    ("Сульпирид", "Sulpiride", "Sulpiridum", "typical antipsychotic", []),
    ("Оланзапин", "Olanzapine", "Olanzapinum", "atypical antipsychotic", []),
    ("Арипипразол", "Aripiprazole", "Aripiprazolum", "atypical antipsychotic", []),
    ("Рисперидон", "Risperidone", "Risperidonum", "atypical antipsychotic", []),
    ("Кветиапин", "Quetiapine", "Quetiapinum", "atypical antipsychotic", ["Сероквель"]),
    ("Перициазин", "Periciazine", "Periciazinum", "typical antipsychotic", []),
    ("Флупентиксол", "Flupentixol", "Flupentixoli", "typical antipsychotic", []),
    ("Галоперидол", "Haloperidol", "Haloperidolum", "typical antipsychotic", []),
    ("Клозапин", "Clozapine", "Clozapinum", "atypical antipsychotic", []),
    ("Карипразин", "Cariprazine", "Cariprazinum", "atypical antipsychotic", []),
    ("Бисопролол", "Bisoprolol", "Bisoprololum", "beta blocker", []),
    ("Пропранолол", "Propranolol", "Propranololum", "beta blocker", []),
    ("Атенолол", "Atenolol", "Atenololum", "beta blocker", []),
    ("Буспирон", "Buspirone", "Buspironum", "anxiolytic", []),
    ("Тофизопам", "Tofisopam", "Tofisopamum", "anxiolytic", ["Грандаксин", "Grandaxin"]),
    ("Атомоксетин", "Atomoxetine", "Atomoxetinum", "ADHD", ["Страттера", "Strattera"]),
    ("Зопиклон", "Zopiclone", "Zopiclonum", "hypnotic", ["Имован"]),
    ("Фенибут", "Phenibut", "Acidum aminophenylbutyricum", "anxiolytic", ["Анвифен"]),
    ("Мелатонин", "Melatonin", "Melatoninum", "hypnotic", []),
    ("Карбонат лития", "Lithium carbonate", "Lithium carbonicum", "mood stabilizer", []),
]

# Нет в продаже в РБ (tabletka.by) — хранятся в data/archived_drugs.json, не в CURATED.
# Тианептин/Коаксил, Агомелатин/Валдоксан, Гидроксизин/Атаракс, Этифоксин/Стресам, Вилазодон.

# tabletka.by не всегда находит эти МНН — заполняем вручную (только для активных).
MANUAL_FALLBACKS: dict[str, dict] = {}


def _apply_manual_fallback(item: dict, mnn: str) -> bool:
    fields = MANUAL_FALLBACKS.get(mnn)
    if not fields:
        return False
    item.update(fields)
    item["sources"] = list(dict.fromkeys([*(item.get("sources") or []), "manual_fallback"]))
    return True


def _base_item(russian: str, mnn: str, latin: str, category: str, aliases: list[str]) -> dict:
    search_aliases = list(
        dict.fromkeys(
            [
                russian.lower(),
                mnn.lower(),
                *[alias.lower() for alias in aliases if alias],
            ]
        )
    )
    return {
        "category": category,
        "mnn": mnn,
        "russian_name": russian,
        "latin_name": latin,
        "drug_form": "Tab.",
        "dosage": "",
        "packaging": "N30",
        "trade_names": [],
        "search_aliases": search_aliases,
        "scheme_options": [],
        "sources": ["curated_list"],
    }


def build_catalog(pause_sec: float = 0.45) -> tuple[list[dict], dict]:
    seed: list[dict] = []
    report: dict = {"ok": [], "empty": [], "errors": [], "total": len(CURATED)}

    for index, (russian, mnn, latin, category, aliases) in enumerate(CURATED, start=1):
        item = _base_item(russian, mnn, latin, category, aliases)
        print(f"[{index}/{len(CURATED)}] {russian} ({mnn})...", flush=True)
        try:
            enrichment = enrich_by_russian_name(
                russian,
                aliases=[alias for alias in aliases if alias],
                pause_sec=pause_sec,
            )
            fields = enrichment_to_seed_fields(enrichment)
            if fields.get("form_options"):
                item.update({k: v for k, v in fields.items() if not k.startswith("_")})
                if enrichment.mnn_text and enrichment.mnn_text.strip():
                    item["search_aliases"] = list(
                        dict.fromkeys([*item["search_aliases"], enrichment.mnn_text.strip().lower()])
                    )
                report["ok"].append({"mnn": mnn, "russian_name": russian, "variants": len(fields.get("tabletka", {}).get("variants", []))})
                print(f"  OK forms={fields.get('form_options')} doses={fields.get('dosage_options')}", flush=True)
            else:
                report["empty"].append({"mnn": mnn, "russian_name": russian, "message": enrichment.message})
                print(f"  empty: {enrichment.message}", flush=True)
                if _apply_manual_fallback(item, mnn):
                    report["ok"].append({"mnn": mnn, "russian_name": russian, "variants": 0, "manual": True})
                    print(f"  manual fallback applied", flush=True)
        except Exception as exc:  # noqa: BLE001
            report["errors"].append({"mnn": mnn, "russian_name": russian, "error": str(exc)})
            print(f"  ERROR: {exc}", flush=True)
        seed.append(item)
        time.sleep(0.1)

    return seed, report


def main() -> None:
    parser = argparse.ArgumentParser(description="Build curated drug seed from tabletka.by")
    parser.add_argument("--dry-run", action="store_true", help="Не записывать seed на диск")
    args = parser.parse_args()

    seed, report = build_catalog()
    report["written"] = len(seed)

    if not args.dry_run:
        SEED_PATH.write_text(json.dumps(seed, ensure_ascii=False, indent=2), encoding="utf-8")
        REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nWrote {len(seed)} drugs -> {SEED_PATH}", flush=True)
        print(f"Report -> {REPORT_PATH}", flush=True)
    print(json.dumps({"ok": len(report["ok"]), "empty": len(report["empty"]), "errors": len(report["errors"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
