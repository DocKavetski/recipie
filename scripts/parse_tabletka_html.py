from pathlib import Path
from bs4 import BeautifulSoup
import re, json

html = Path(r"D:\Проекты\Рецепты\data\tabletka_result_sample.html").read_text(encoding="utf-8")
soup = BeautifulSoup(html, "html.parser")

info = {
    "title": (soup.title.get_text(strip=True) if soup.title else ""),
    "tables": len(soup.select("table")),
    "ths": [th.get_text(" ", strip=True) for th in soup.select("th")[:30]],
    "selects": [],
    "minsk_rows": [],
}

for sel in soup.select("select"):
    options = [{"value": o.get("value"), "text": o.get_text(" ", strip=True)} for o in sel.select("option")[:40]]
    info["selects"].append({"name": sel.get("name"), "id": sel.get("id"), "options": options})

# table body rows mentioning Minsk
for tr in soup.select("table tr"):
    text = tr.get_text(" ", strip=True)
    if "Минск" in text:
        cells = [td.get_text(" ", strip=True) for td in tr.select("td")]
        info["minsk_rows"].append({"cells": cells, "text": text[:200]})
        if len(info["minsk_rows"]) >= 15:
            break

# any data attributes
attrs = []
for el in soup.select("[data-region], [data-city], [data-id], [data-ls]")[:30]:
    attrs.append({k: el.get(k) for k in el.attrs if k.startswith("data-") or k in {"class", "id", "href"}})
info["data_attrs_sample"] = attrs[:20]

Path(r"D:\Проекты\Рецепты\data\tabletka_parse_info.json").write_text(
    json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8"
)
print("minsk_rows", len(info["minsk_rows"]), "selects", len(info["selects"]))
