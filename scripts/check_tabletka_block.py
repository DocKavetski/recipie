from __future__ import annotations

import json
from pathlib import Path

import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Accept": "text/html,application/xhtml+xml",
    "Referer": "https://tabletka.by/",
}

queries = ["венлафаксин", "парацетамол", "ципрамил", "аспирин"]
out = []
for q in queries:
    r = requests.get(
        "https://tabletka.by/search",
        params={"request": q},
        timeout=30,
        headers=HEADERS,
    )
    text = r.content.decode(r.encoding or "utf-8", errors="replace")
    out.append(
        {
            "q": q,
            "status": r.status_code,
            "len": len(text),
            "has_result": "/result/?ls=" in text,
            "has_captcha": "captcha" in text.lower() or "cloudflare" in text.lower(),
            "title": text[text.find("<title>") : text.find("</title>") + 8] if "<title>" in text else "",
            "snippet": text[text.find("content-table") : text.find("content-table") + 200] if "content-table" in text else text[2000:2400],
        }
    )
    Path(r"D:\Проекты\Рецепты\data\tabletka_blocked_sample.html").write_text(text, encoding="utf-8")

Path(r"D:\Проекты\Рецепты\data\tabletka_rate_check.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps(out, ensure_ascii=False, indent=2))
