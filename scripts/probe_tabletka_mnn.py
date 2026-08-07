"""Probe tabletka.by MNN pages and fix encoding."""
from __future__ import annotations

import json
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9",
}
ROOT = Path(__file__).resolve().parents[1] / "data"


def fetch(url: str, params: dict | None = None) -> BeautifulSoup:
    r = requests.get(url, params=params, timeout=30, headers=HEADERS)
    r.raise_for_status()
    # tabletka often serves windows-1251 without correct header
    if not r.encoding or r.encoding.lower() in {"iso-8859-1", "ascii"}:
        r.encoding = r.apparent_encoding or "utf-8"
    # force from content meta if present
    meta = re.search(r'charset=([^\s";]+)', r.text[:2000], flags=re.I)
    if meta:
        r.encoding = meta.group(1).strip()
    return BeautifulSoup(r.content.decode(r.encoding, errors="replace"), "html.parser")


def parse_search_rows(soup: BeautifulSoup) -> list[dict]:
    rows = []
    for tr in soup.select("table tr"):
        name_a = tr.select_one("td.name a[href*='/result/']")
        form_a = tr.select_one("td.form a[href*='/result/']")
        mnn_a = tr.select_one("a[href*='/search/mnn/']")
        mnf_a = tr.select_one("a[href*='/search/mnf/']")
        if not name_a and not form_a:
            continue
        href = (name_a or form_a).get("href") or ""
        ls = re.search(r"ls=(\d+)", href)
        form_text = form_a.get_text(" ", strip=True) if form_a else ""
        rows.append(
            {
                "ls": ls.group(1) if ls else None,
                "trade_name": name_a.get_text(" ", strip=True) if name_a else "",
                "form_raw": form_text,
                "mnn_link": mnn_a.get("href") if mnn_a else None,
                "mnn_text": mnn_a.get_text(" ", strip=True) if mnn_a else "",
                "producer": mnf_a.get_text(" ", strip=True) if mnf_a else "",
            }
        )
    return rows


def main() -> None:
    soup = fetch("https://tabletka.by/search", {"request": "венлафаксин"})
    rows = parse_search_rows(soup)
    mnn_ids = sorted({r["mnn_link"] for r in rows if r.get("mnn_link")})
    out = {"search_rows": rows[:25], "mnn_links": mnn_ids, "total_rows": len(rows)}

    if mnn_ids:
        href = mnn_ids[0]
        if href.startswith("/"):
            href = "https://tabletka.by" + href
        mnn_soup = fetch(href)
        mnn_rows = parse_search_rows(mnn_soup)
        out["mnn_page"] = href
        out["mnn_rows_count"] = len(mnn_rows)
        out["mnn_rows"] = mnn_rows[:40]
        ROOT.joinpath("tabletka_mnn_sample.html").write_bytes(
            requests.get(href, timeout=30, headers=HEADERS).content
        )

    ROOT.joinpath("tabletka_probe_mnn.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("search rows", out["total_rows"], "mnn links", mnn_ids)
    print(json.dumps(rows[:5], ensure_ascii=False, indent=2))
    if "mnn_rows" in out:
        print("mnn rows", out["mnn_rows_count"])
        print(json.dumps(out["mnn_rows"][:8], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
