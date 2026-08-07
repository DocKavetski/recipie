from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.tabletka_enrich import _pick_mnn_link, enrich_by_russian_name, fetch_search_rows

QUERIES = [
    ("акампросат", "Акампросат"),
    ("кампрал", "Акампросат"),
    ("тианептин", "Тианептин"),
    ("коаксил", "Тианептин"),
    ("галантамин", "Галантамин"),
    ("реминил", "Галантамин"),
    ("агомелатин", "Агомелатин"),
    ("вальдоксан", "Агомелатин"),
    ("палиперидон", "Палиперидон"),
    ("инвега", "Палиперидон"),
    ("гидроксизин", "Гидроксизин"),
    ("атаракс", "Гидроксизин"),
    ("этифоксин", "Этифоксин"),
    ("стрезам", "Этифоксин"),
    ("золпидем", "Золпидем"),
    ("ивадал", "Золпидем"),
    ("ривастигмин", "Ривастигмин"),
    ("экселон", "Ривастигмин"),
    ("пиритинол", "Пиритинол"),
    ("энцефабол", "Пиритинол"),
    ("сертиндол", "Сертиндол"),
    ("сердолект", "Сертиндол"),
]

out = []
for query, russian in QUERIES:
    rows = fetch_search_rows(query)
    link, text = _pick_mnn_link(rows, russian)
    sample = [
        {
            "trade": r.get("trade_name"),
            "mnn": r.get("mnn_text"),
            "form": r.get("form_raw"),
        }
        for r in rows[:5]
    ]
    enrichment = None
    if rows:
        enrichment = enrich_by_russian_name(russian, aliases=[query], pause_sec=0.2)
    out.append(
        {
            "query": query,
            "russian": russian,
            "rows": len(rows),
            "picked_mnn": text,
            "picked_link": link,
            "sample": sample,
            "forms": enrichment.form_options if enrichment else [],
            "doses": enrichment.dosage_options if enrichment else [],
            "trades_count": len(enrichment.trade_names) if enrichment else 0,
            "trades": (enrichment.trade_names[:10] if enrichment else []),
            "message": enrichment.message if enrichment else "no rows",
        }
    )
    print(json.dumps(out[-1], ensure_ascii=False), flush=True)

Path(ROOT / "data" / "tabletka_debug_queries.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
)
