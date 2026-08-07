"""Probe tabletka.by search HTML for one query."""
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

OUT = Path(__file__).resolve().parents[1] / "data" / "tabletka_probe.json"


def probe(query: str) -> dict:
    r = requests.get(
        "https://tabletka.by/search",
        params={"request": query},
        timeout=30,
        headers=HEADERS,
    )
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    Path(__file__).resolve().parents[1].joinpath("data", "tabletka_search_sample.html").write_text(
        r.text, encoding="utf-8"
    )

    cards = []
    for anchor in soup.select("a[href*='/result/']"):
        href = anchor.get("href") or ""
        m = re.search(r"ls=(\d+)", href)
        if not m:
            continue
        card = anchor.find_parent(["tr", "div", "li", "td"]) or anchor
        texts = [t.strip() for t in card.stripped_strings if t.strip()]
        classes = []
        node = card
        for _ in range(4):
            if hasattr(node, "get") and node.get("class"):
                classes.append(" ".join(node.get("class")))
            node = getattr(node, "parent", None)
            if node is None:
                break
        cards.append(
            {
                "ls": m.group(1),
                "href": href,
                "anchor": anchor.get_text(" ", strip=True),
                "texts": texts[:12],
                "classes": classes,
                "tag": getattr(card, "name", None),
            }
        )
        if len(cards) >= 20:
            break

    # also look for form/dose patterns in page
    doses = sorted(set(re.findall(r"\d+(?:[.,]\d+)?\s*мг", r.text, flags=re.I)))
    forms = sorted(
        set(
            re.findall(
                r"(?:табл(?:етки)?|капс(?:улы)?|р-р|раствор|сироп|капли|сусп(?:ензия)?|"
                r"порошок|амп(?:улы)?|фл(?:аконы)?|гель|мазь|спрей)[^\n<]{0,40}",
                r.text,
                flags=re.I,
            )
        )
    )[:40]

    return {
        "query": query,
        "status": r.status_code,
        "cards_count": len(cards),
        "cards": cards,
        "doses_sample": doses[:40],
        "forms_sample": forms,
    }


if __name__ == "__main__":
    data = probe("венлафаксин")
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("cards", data["cards_count"])
    print(json.dumps(data["cards"][:5], ensure_ascii=False, indent=2))
    print("doses", data["doses_sample"][:15])
