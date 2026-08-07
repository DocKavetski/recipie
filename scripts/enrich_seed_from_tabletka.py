"""Обогатить seed_drugs_from_protocols.json данными tabletka.by по МНН."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.tabletka_enrich import enrich_by_russian_name, enrichment_to_seed_fields  # noqa: E402

SEED_PATH = ROOT / "data" / "seed_drugs_from_protocols.json"
REPORT_PATH = ROOT / "data" / "tabletka_enrich_report.json"
CACHE_PATH = ROOT / "data" / "tabletka_enrich_cache.json"

POLLUTED_RE = re.compile(
    r"шампун|кондиционер|маска|лосьон|kaaral|глютамин|орасепт|оросептин",
    flags=re.I,
)


def merge_trade_names(existing: list[str], incoming: list[str]) -> list[str]:
    result: list[str] = []
    for name in [*incoming, *existing]:
        clean = str(name or "").strip()
        if clean and clean not in result and len(clean) <= 48 and not POLLUTED_RE.search(clean):
            result.append(clean)
    return result


def _clean_trade_names(names: list[str]) -> list[str]:
    return [
        name.strip()
        for name in names
        if str(name).strip() and len(str(name).strip()) <= 48 and not POLLUTED_RE.search(str(name))
    ]


def _looks_polluted(item: dict) -> bool:
    blob = " ".join(
        [
            str(item.get("dosage") or ""),
            " ".join(item.get("trade_names") or []),
            " ".join(item.get("form_options") or []),
            " ".join(item.get("dosage_options") or []),
        ]
    )
    if POLLUTED_RE.search(blob):
        return True
    if str(item.get("dosage") or "").endswith(" г"):
        return True
    if len(item.get("trade_names") or []) > 30:
        return True
    return False


def _doses_from_packaging(packaging: str) -> list[str]:
    doses = []
    for match in re.finditer(r"(\d+(?:[.,]\d+)?)\s*мг", str(packaging or ""), flags=re.I):
        dose = f"{match.group(1).replace(',', '.')} мг"
        if dose not in doses:
            doses.append(dose)
    return doses


def _form_from_packaging(packaging: str, current: str) -> str:
    text = str(packaging or "").lower()
    if "капс" in text:
        return "Caps."
    if "табл" in text:
        return "Tab."
    if "р-р" in text or "раствор" in text:
        return "Sol."
    return current or "Tab."


def _restore_from_packaging(item: dict) -> None:
    packaging = str(item.get("packaging") or "")
    # если packaging уже Nxx от ложного прогона — восстанавливаем из scheme/protocol note
    doses = _doses_from_packaging(packaging)
    if not doses:
        for scheme in item.get("scheme_options") or []:
            doses.extend(_doses_from_packaging(str(scheme)))
        doses = list(dict.fromkeys(doses))
    form = _form_from_packaging(packaging, str(item.get("drug_form") or "Tab."))
    if form in {"Spray", "Gel", "Amp.", "Ung."} and "табл" not in packaging.lower():
        form = "Tab."
    item["drug_form"] = form
    item["form_options"] = [form]
    if doses:
        item["dosage"] = doses[0]
        item["dosage_options"] = doses
        item["form_dosage_map"] = {form: doses}
    item["trade_names"] = _clean_trade_names(item.get("trade_names") or [])
    item["trade_details"] = {
        name: {
            "packaging": packaging if not packaging.startswith("N") else "N30",
            "dispense_qty": 30,
        }
        for name in item["trade_names"]
    }
    item.pop("tabletka", None)


def _build_aliases(item: dict, russian: str) -> list[str]:
    aliases: list[str] = []
    for alias in item.get("search_aliases") or []:
        text = str(alias).strip()
        if re.fullmatch(r"[A-Za-z0-9\-\s]+", text):
            continue
        if text.lower() == russian.lower():
            continue
        aliases.append(text)
    for trade in _clean_trade_names(item.get("trade_names") or []):
        if 2 <= len(trade) <= 28:
            aliases.append(trade)
    # unique preserve order
    return list(dict.fromkeys(aliases))[:4]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Игнорировать кеш и пересобрать")
    parser.add_argument("--clear-cache", action="store_true", help="Удалить кеш перед запуском")
    args = parser.parse_args()

    if args.clear_cache and CACHE_PATH.exists():
        CACHE_PATH.unlink()

    seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    cache: dict[str, dict] = {}
    if CACHE_PATH.exists() and not args.force:
        cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))

    report: dict = {"ok": [], "empty": [], "errors": [], "total": len(seed)}
    updated = 0

    for index, item in enumerate(seed, start=1):
        russian = str(item.get("russian_name") or "").strip()
        mnn = str(item.get("mnn") or "").strip()
        key = mnn or russian
        print(f"[{index}/{len(seed)}] {russian} ({mnn})...", flush=True)

        try:
            cached = cache.get(key)
            if cached and cached.get("form_options") and not args.force:
                fields = cached
            else:
                enrichment = enrich_by_russian_name(
                    russian,
                    aliases=_build_aliases(item, russian),
                    pause_sec=0.4,
                )
                fields = enrichment_to_seed_fields(enrichment)
                cache[key] = {
                    **fields,
                    "_message": enrichment.message,
                    "_mnn_text": enrichment.mnn_text,
                }
                CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
                time.sleep(0.15)
        except Exception as exc:  # noqa: BLE001
            report["errors"].append({"mnn": mnn, "russian_name": russian, "error": str(exc)})
            print(f"  ERROR: {exc}", flush=True)
            continue

        if not fields.get("form_options"):
            item.pop("tabletka", None)
            if _looks_polluted(item) or not item.get("dosage_options"):
                _restore_from_packaging(item)
            report["empty"].append(
                {"mnn": mnn, "russian_name": russian, "message": fields.get("_message")}
            )
            print("  empty", flush=True)
            continue

        old_dosage = str(item.get("dosage") or "")
        if "сут" in old_dosage.lower() or "–" in old_dosage or "-" in old_dosage:
            schemes = list(item.get("scheme_options") or [])
            note = f"протокол: {old_dosage}"
            if note not in schemes:
                schemes.insert(0, note)
            item["scheme_options"] = schemes[:6]

        item["drug_form"] = fields["drug_form"]
        item["dosage"] = fields["dosage"]
        item["packaging"] = fields["packaging"]
        item["form_options"] = fields["form_options"]
        item["dosage_options"] = fields["dosage_options"]
        item["form_dosage_map"] = fields["form_dosage_map"]
        item["trade_names"] = merge_trade_names(
            _clean_trade_names(item.get("trade_names") or []),
            fields.get("trade_names") or [],
        )
        item["trade_details"] = fields.get("trade_details") or {}
        item["tabletka"] = fields.get("tabletka") or {}
        updated += 1
        report["ok"].append(
            {
                "mnn": mnn,
                "russian_name": russian,
                "forms": fields["form_options"],
                "dosages": fields["dosage_options"],
                "trades": fields.get("trade_names") or [],
            }
        )
        print(
            f"  OK forms={fields['form_options']} "
            f"doses={fields['dosage_options'][:6]} "
            f"trades={len(fields.get('trade_names') or [])}",
            flush=True,
        )

    SEED_PATH.write_text(json.dumps(seed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report["updated"] = updated
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Updated {updated}/{len(seed)}. Report: {REPORT_PATH}", flush=True)


if __name__ == "__main__":
    main()
