from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.tabletka_enrich import (
    _names_match,
    _pick_mnn_link,
    enrich_by_russian_name,
    fetch_search_rows,
)

checks = [
    ("Циталопрам", ["ципрамил", "опра"]),
    ("Левомепромазин", ["тизерцин"]),
    ("Амисульприд", ["солиан"]),
    ("Церебролизин", []),
    ("Гопантеновая кислота", ["пантогам"]),
    ("Налтрексон", ["вивитрол", "антаксон"]),
    ("Адаптол", ["мебикар"]),  # wrong russian - test trade
    ("Тетраметилтетраазабициклооктандион", ["адаптол", "мебикар"]),
    ("Фабомотизол", ["афобазол"]),
    ("Клонидин", ["клофелин"]),
    ("Имипрамин", ["мелипрамин"]),
    ("Агомелатин", ["вальдоксан"]),
    ("Гидроксизин", ["атаракс"]),
]

out = []
for russian, aliases in checks:
    rows = fetch_search_rows(russian)
    link, text = _pick_mnn_link(rows, russian)
    enrichment = enrich_by_russian_name(russian, aliases=aliases, pause_sec=0.25)
    out.append(
        {
            "russian": russian,
            "search_rows": len(rows),
            "picked": text,
            "sample_mnn": sorted({r.get("mnn_text") for r in rows if r.get("mnn_text")})[:8],
            "sample_trades": [r.get("trade_name") for r in rows[:5]],
            "match_samples": [
                {"mnn": r.get("mnn_text"), "ok": _names_match(r.get("mnn_text") or "", russian)}
                for r in rows[:8]
                if r.get("mnn_text")
            ],
            "forms": enrichment.form_options,
            "doses": enrichment.dosage_options,
            "trades": enrichment.trade_names[:8],
            "message": enrichment.message,
            "mnn_text": enrichment.mnn_text,
        }
    )

Path(ROOT / "data" / "tabletka_empty_debug.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
)
print("written", len(out))
