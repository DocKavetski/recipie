"""Точечная зачистка ложных совпадений после tabletka-обогащения."""

from __future__ import annotations

import json
import re
from pathlib import Path

SEED_PATH = Path(__file__).resolve().parents[1] / "data" / "seed_drugs_from_protocols.json"

# Ручные правки для МНН, где авторазбор дал чужие препараты / косметику / налоксон
FIXES: dict[str, dict] = {
    "Citalopram": {
        "drug_form": "Tab.",
        "dosage": "10 мг",
        "packaging": "табл. 10 мг, 20 мг, 40 мг",
        "form_options": ["Tab."],
        "dosage_options": ["10 мг", "20 мг", "40 мг"],
        "form_dosage_map": {"Tab.": ["10 мг", "20 мг", "40 мг"]},
        "trade_names": ["Ципрамил", "Опра"],
    },
    "Levomepromazine": {
        "drug_form": "Tab.",
        "dosage": "25 мг",
        "packaging": "табл. 25 мг, 50 мг",
        "form_options": ["Tab.", "Sol."],
        "dosage_options": ["25 мг", "50 мг"],
        "form_dosage_map": {"Tab.": ["25 мг", "50 мг"], "Sol.": ["25 мг"]},
        "trade_names": ["Тизерцин"],
    },
    "Acamprosate": {
        "drug_form": "Tab.",
        "dosage": "333 мг",
        "packaging": "табл. 333 мг",
        "form_options": ["Tab."],
        "dosage_options": ["333 мг"],
        "form_dosage_map": {"Tab.": ["333 мг"]},
        "trade_names": ["Кампрал"],
    },
    "Naltrexone": {
        "drug_form": "Tab.",
        "dosage": "50 мг",
        "packaging": "табл. 50 мг; депо 380 мг",
        "form_options": ["Tab.", "Sol."],
        "dosage_options": ["50 мг", "380 мг"],
        "form_dosage_map": {"Tab.": ["50 мг"], "Sol.": ["380 мг"]},
        "trade_names": ["Вивитрол", "Антаксон", "Налтрекс"],
    },
    "Galantamine": {
        "drug_form": "Caps.",
        "dosage": "8 мг",
        "packaging": "капс. 8 мг, 16 мг, 24 мг",
        "form_options": ["Caps.", "Tab.", "Sol."],
        "dosage_options": ["4 мг", "8 мг", "12 мг", "16 мг", "24 мг"],
        "form_dosage_map": {
            "Caps.": ["8 мг", "16 мг", "24 мг"],
            "Tab.": ["4 мг", "8 мг", "12 мг"],
            "Sol.": ["4 мг"],
        },
        "trade_names": ["Реминил", "Нивалин"],
    },
    "Tianeptine": {
        "drug_form": "Tab.",
        "dosage": "12.5 мг",
        "packaging": "табл. 12,5 мг",
        "form_options": ["Tab."],
        "dosage_options": ["12.5 мг"],
        "form_dosage_map": {"Tab.": ["12.5 мг"]},
        "trade_names": ["Коаксил", "Тианептин"],
    },
    "Escitalopram": {
        # убрать чужие имена на всякий случай, оставить эсциталопрам-бренды
        "trade_names_keep": ["Позитива", "Ципралекс", "Элицея", "Эспрам", "Эсциталопрам", "Селектра"],
    },
}


def _details(names: list[str], packaging: str) -> dict:
    qty_match = re.search(r"(\d+)", packaging)
    qty = int(qty_match.group(1)) if qty_match else 30
    return {name: {"packaging": packaging, "dispense_qty": qty} for name in names}


def main() -> None:
    seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    changed = []
    for item in seed:
        mnn = item.get("mnn")
        fix = FIXES.get(mnn)
        if not fix:
            # авто-чистка: дозировки в мл/г без мг — явно мусор
            doses = item.get("dosage_options") or []
            if any(re.search(r"\b(мл|г)\b", str(d)) and "мг" not in str(d) for d in doses):
                item["dosage_options"] = [d for d in doses if re.search(r"мг", str(d), re.I)]
                if item["dosage_options"]:
                    item["dosage"] = item["dosage_options"][0]
                    form = item.get("drug_form") or "Tab."
                    item["form_dosage_map"] = {form: list(item["dosage_options"])}
                    changed.append(mnn)
            continue

        if "trade_names_keep" in fix:
            keep = set(fix["trade_names_keep"])
            item["trade_names"] = [n for n in (item.get("trade_names") or []) if n in keep] or list(fix["trade_names_keep"])
            item["trade_details"] = {
                k: v for k, v in (item.get("trade_details") or {}).items() if k in keep
            }
            changed.append(mnn)
            continue

        for key in (
            "drug_form",
            "dosage",
            "packaging",
            "form_options",
            "dosage_options",
            "form_dosage_map",
            "trade_names",
        ):
            if key in fix:
                item[key] = fix[key]
        item["trade_details"] = _details(item["trade_names"], item["packaging"])
        item.pop("tabletka", None)
        changed.append(mnn)

    SEED_PATH.write_text(json.dumps(seed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("fixed", changed)


if __name__ == "__main__":
    main()
