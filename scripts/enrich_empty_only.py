"""Дообогатить только препараты без form_options / пустые по tabletka."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.tabletka_enrich import enrich_by_russian_name, enrichment_to_seed_fields  # noqa: E402
from scripts.enrich_seed_from_tabletka import (  # noqa: E402
    CACHE_PATH,
    SEED_PATH,
    _build_aliases,
    _clean_trade_names,
    _looks_polluted,
    _restore_from_packaging,
    merge_trade_names,
)

REPORT_PATH = ROOT / "data" / "tabletka_enrich_empty_report.json"


def main() -> None:
    seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    cache = json.loads(CACHE_PATH.read_text(encoding="utf-8")) if CACHE_PATH.exists() else {}
    report = {"ok": [], "empty": [], "total_checked": 0}

    for item in seed:
        has_opts = bool(item.get("form_options") and item.get("dosage_options"))
        if has_opts and not _looks_polluted(item):
            continue

        report["total_checked"] += 1
        russian = item["russian_name"]
        mnn = item["mnn"]
        print(f"Retry {russian}...", flush=True)
        time.sleep(0.8)
        enrichment = enrich_by_russian_name(
            russian,
            aliases=_build_aliases(item, russian),
            pause_sec=0.6,
        )
        fields = enrichment_to_seed_fields(enrichment)
        cache[mnn] = {**fields, "_message": enrichment.message, "_mnn_text": enrichment.mnn_text}

        if not fields.get("form_options"):
            _restore_from_packaging(item)
            report["empty"].append({"mnn": mnn, "russian_name": russian, "message": enrichment.message})
            print("  empty -> restored", flush=True)
            continue

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
        report["ok"].append(
            {
                "mnn": mnn,
                "forms": fields["form_options"],
                "dosages": fields["dosage_options"],
                "trades": fields.get("trade_names") or [],
            }
        )
        print(f"  OK {fields['form_options']} {fields['dosage_options']}", flush=True)

    # финальная зачистка загрязнений
    for item in seed:
        if _looks_polluted(item):
            _restore_from_packaging(item)

    SEED_PATH.write_text(json.dumps(seed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": len(report["ok"]), "empty": len(report["empty"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
