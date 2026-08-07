from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.tabletka_enrich import enrich_by_russian_name, fetch_search_rows

queries = [
    "циталопрам",
    "ципрамил",
    "тизерцин",
    "солиан",
    "амисульприд",
    "вивитрол",
    "клофелин",
    "мелипрамин",
    "вальдоксан",
    "атаракс",
    "церебролизин",
]
out = []
for q in queries:
    rows = fetch_search_rows(q)
    time.sleep(0.5)
    out.append(
        {
            "q": q,
            "n": len(rows),
            "trades": [r.get("trade_name") for r in rows[:5]],
            "mnns": sorted({r.get("mnn_text") for r in rows if r.get("mnn_text")}),
            "forms": [r.get("form_raw") for r in rows[:5]],
            "has_mnn_link": sum(1 for r in rows if r.get("mnn_link")),
        }
    )
    print(q, len(rows), flush=True)

Path(ROOT / "data" / "tabletka_single_queries.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
)
