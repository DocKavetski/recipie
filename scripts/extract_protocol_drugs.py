"""Extract drug mentions from protocol PDFs and probe tabletka.by."""

from __future__ import annotations

import json
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
PROTOCOLS = ROOT / "Протоколы"
OUT_DIR = ROOT / "data"

# Common Latin/INN-like tokens and Russian drug name patterns in psychiatric protocols
LATIN_INN = re.compile(r"\b([A-Z][a-z]{2,}(?:um|ine|ide|ate|ole|pam|pine|zine|done|xine|pram|tine)?)\b")
# Cyrillic drug-like words often capitalized in tables
# We'll also match known endings
RU_CANDIDATE = re.compile(
    r"\b([А-ЯЁ][а-яё]{3,}(?:ин|ин[аы]|ол|ол[аы]|ам|ам[аы]|ин[еи]|пин|пин[аы]|зин|зин[аы]|дон|дон[аы]|прам|прам[аы]|тин|тин[аы]|ксан|ксан[аы]|азол|азол[аы]|епин|епин[аы]|идон|идон[аы]|апин|апин[аы]))\b"
)

BENZO_KEYWORDS = {
    "diazepam", "диазепам", "lorazepam", "лоразепам", "clonazepam", "клоназепам",
    "alprazolam", "алпразолам", "bromazepam", "бромазепам", "nitrazepam", "нитразепам",
    "midazolam", "мидазолам", "oxazepam", "оксазепам", "phenazepam", "феназепам",
    "tofisopam", "тофизопам", "grandaxin", "грандаксин", "medazepam", "медазепам",
    "chlordiazepoxide", "хлордиазепоксид", "clorazepate", "клоразепат",
    "flunitrazepam", "флунитразепам", "temazepam", "темазепам", "triazolam", "триазолам",
    "бензодиазепин", "benzodiazepine", "транквилизатор",
}

NOISE = {
    "table", "tablet", "tablets", "form", "dose", "daily", "protocol", "patient", "treatment",
    "disorder", "clinical", "diagnosis", "ministry", "republic", "belarus", "chapter", "annex",
    "приложение", "таблица", "протокол", "лечение", "пациент", "диагноз", "республика",
    "министерство", "здоровья", "беларусь", "глава", "раздел", "пункт", "дней", "сутки",
}


def extract_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def is_benzo(token: str) -> bool:
    low = token.lower()
    return any(k in low for k in BENZO_KEYWORDS) or low.endswith("zepam") or low.endswith("зепам")


def collect_candidates(text: str) -> set[str]:
    found: set[str] = set()
    for match in LATIN_INN.finditer(text):
        token = match.group(1)
        if token.lower() in NOISE or len(token) < 5:
            continue
        if is_benzo(token):
            continue
        found.add(token)
    for match in RU_CANDIDATE.finditer(text):
        token = match.group(1)
        if token.lower() in NOISE or is_benzo(token):
            continue
        found.add(token)
    return found


def probe_tabletka(query: str) -> dict:
    url = "https://tabletka.by/search"
    resp = requests.get(
        url,
        params={"request": query},
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    soup = BeautifulSoup(resp.text, "html.parser")
    results = []
    for a in soup.select("a[href*='/result/']")[:20]:
        href = a.get("href") or ""
        title = a.get_text(" ", strip=True)
        if title:
            results.append({"href": href, "title": title})
    # pharmacies count heuristics
    minsk = len(re.findall(r"Минск", resp.text))
    return {
        "status": resp.status_code,
        "results": results[:10],
        "minsk_mentions": minsk,
        "len": len(resp.text),
    }


def main() -> None:
    all_text_parts = []
    by_file: dict[str, list[str]] = {}
    universe: set[str] = set()

    for pdf in sorted(PROTOCOLS.glob("*.pdf")):
        text = extract_pdf_text(pdf)
        all_text_parts.append(f"===== {pdf.name} =====\n{text}")
        cands = collect_candidates(text)
        by_file[pdf.name] = sorted(cands, key=str.lower)
        universe |= cands

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "protocols_extract.txt").write_text("\n\n".join(all_text_parts), encoding="utf-8")
    (OUT_DIR / "protocol_drug_candidates.json").write_text(
        json.dumps(
            {
                "count": len(universe),
                "drugs": sorted(universe, key=str.lower),
                "by_file": by_file,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"candidates={len(universe)}")
    for item in sorted(universe, key=str.lower)[:40]:
        print("-", item)

    sample = probe_tabletka("эсциталопрам")
    (OUT_DIR / "tabletka_probe.json").write_text(json.dumps(sample, ensure_ascii=False, indent=2), encoding="utf-8")
    print("tabletka probe results", len(sample["results"]), "minsk", sample["minsk_mentions"])


if __name__ == "__main__":
    main()
