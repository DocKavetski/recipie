"""Парсинг форм/дозировок/торговых названий с tabletka.by по МНН."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

LOGGER = logging.getLogger(__name__)

BASE_URL = "https://tabletka.by"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9",
}

FORM_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"капс", re.I), "Caps."),
    (re.compile(r"табл", re.I), "Tab."),
    (re.compile(r"р-?р|раствор", re.I), "Sol."),
    (re.compile(r"сироп", re.I), "Sir."),
    (re.compile(r"капл", re.I), "Gtt."),
    (re.compile(r"сусп", re.I), "Susp."),
    (re.compile(r"порош", re.I), "Pulv."),
    (re.compile(r"амп", re.I), "Amp."),
    (re.compile(r"лиоф", re.I), "Lyoph."),
    (re.compile(r"имплант|пластыр", re.I), "Impl."),
]

NON_DRUG_RE = re.compile(
    r"шампун|кондиционер|маска\b|лосьон|бальзам|крем-?маска|паста\b|мыло|гель для душа|"
    r"зубн|космети|волос|уксус ежевик",
    flags=re.I,
)

DOSE_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(мг|мкг|г|ME|МЕ|%)(?!\s*/\s*сут)",
    flags=re.I,
)
PACK_RE = re.compile(r"[N№]\s*(\d+)", flags=re.I)


@dataclass
class TabletkaVariant:
    trade_name: str
    form_raw: str
    drug_form: str
    dosage: str
    packaging: str
    dispense_qty: int
    ls: str | None = None
    producer: str = ""


@dataclass
class TabletkaEnrichment:
    query: str
    mnn_id: str | None = None
    mnn_text: str = ""
    variants: list[TabletkaVariant] = field(default_factory=list)
    form_options: list[str] = field(default_factory=list)
    dosage_options: list[str] = field(default_factory=list)
    form_dosage_map: dict[str, list[str]] = field(default_factory=dict)
    trade_names: list[str] = field(default_factory=list)
    trade_details: dict[str, dict[str, Any]] = field(default_factory=dict)
    default_form: str = ""
    default_dosage: str = ""
    default_packaging: str = ""
    message: str = ""


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def _soup_from_response(response: requests.Response) -> BeautifulSoup:
    encoding = response.encoding or response.apparent_encoding or "utf-8"
    meta = re.search(r'charset=([^\s";]+)', response.text[:2000], flags=re.I)
    if meta:
        encoding = meta.group(1).strip()
    try:
        text = response.content.decode(encoding, errors="replace")
    except LookupError:
        text = response.content.decode("utf-8", errors="replace")
    return BeautifulSoup(text, "html.parser")


def classify_form(form_raw: str) -> str:
    text = str(form_raw or "")
    if not text or NON_DRUG_RE.search(text):
        return ""
    for pattern, abbrev in FORM_RULES:
        if pattern.search(text):
            return abbrev
    return ""


def parse_dosage(form_raw: str) -> str:
    text = str(form_raw or "")
    # предпочитаем мг/мкг как единицу дозировки ЛС
    preferred = re.search(r"(\d+(?:[.,]\d+)?)\s*(мг|мкг)\b", text, flags=re.I)
    match = preferred or DOSE_RE.search(text)
    if not match:
        return ""
    value = match.group(1).replace(",", ".")
    unit = match.group(2)
    if unit.upper() == "ME":
        unit = "МЕ"
    # отсекаем очевидно косметические «дозы» в граммах без мг
    if unit.lower() == "г" and not preferred:
        return ""
    return f"{value} {unit}"


def parse_packaging(form_raw: str) -> tuple[str, int]:
    match = PACK_RE.search(str(form_raw or ""))
    if not match:
        return "", 30
    qty = int(match.group(1))
    return f"N{qty}", qty


def parse_result_rows(soup: BeautifulSoup) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for tr in soup.select("table tr"):
        name_a = tr.select_one("td.name a[href*='/result/']")
        form_a = tr.select_one("td.form a[href*='/result/']")
        if not name_a and not form_a:
            continue
        href = (name_a or form_a).get("href") or ""
        ls_match = re.search(r"ls=(\d+)", href)
        ls = ls_match.group(1) if ls_match else ""
        form_raw = form_a.get_text(" ", strip=True) if form_a else ""
        trade_name = name_a.get_text(" ", strip=True) if name_a else ""
        key = f"{ls}|{trade_name}|{form_raw}"
        if key in seen:
            continue
        seen.add(key)
        mnn_a = tr.select_one("a[href*='/search/mnn/']")
        mnf_a = tr.select_one("a[href*='/search/mnf/']")
        rows.append(
            {
                "ls": ls or None,
                "trade_name": trade_name,
                "form_raw": form_raw,
                "mnn_link": mnn_a.get("href") if mnn_a else None,
                "mnn_text": (mnn_a.get_text(" ", strip=True) if mnn_a else ""),
                "producer": (mnf_a.get_text(" ", strip=True) if mnf_a else ""),
            }
        )
    return rows


def _normalize_name(value: str) -> str:
    text = str(value or "").lower().replace("ё", "е")
    text = re.sub(r"[^a-zа-я0-9]+", " ", text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip()


def _names_match(left: str, right: str) -> bool:
    a = _normalize_name(left)
    b = _normalize_name(right)
    if not a or not b:
        return False
    if a == b:
        return True
    # порядок слов: "вальпроевая кислота" vs "кислота вальпроевая"
    if set(a.split()) == set(b.split()) and len(a.split()) >= 2:
        return True
    # безопасный substring только для длинных имён (избегаем налоксон/налтрексон)
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    if len(shorter) >= 6 and longer.startswith(shorter):
        return True
    return False


def fetch_search_rows(query: str, session: requests.Session | None = None) -> list[dict[str, Any]]:
    sess = session or _session()
    try:
        response = sess.get(f"{BASE_URL}/search", params={"request": query}, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        LOGGER.warning("tabletka search failed for %s: %s", query, exc)
        return []
    return parse_result_rows(_soup_from_response(response))


def fetch_mnn_rows(mnn_link: str, session: requests.Session | None = None) -> list[dict[str, Any]]:
    sess = session or _session()
    url = urljoin(BASE_URL, mnn_link)
    try:
        response = sess.get(url, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        LOGGER.warning("tabletka mnn page failed for %s: %s", mnn_link, exc)
        return []
    return parse_result_rows(_soup_from_response(response))


def _pick_mnn_link(rows: list[dict[str, Any]], russian_name: str) -> tuple[str | None, str]:
    ranked: list[tuple[int, str, str]] = []
    for row in rows:
        link = row.get("mnn_link")
        text = str(row.get("mnn_text") or "")
        if not link or not text:
            continue
        score = 0
        if _normalize_name(text) == _normalize_name(russian_name):
            score += 20
        elif _names_match(text, russian_name):
            score += 10
        if score:
            ranked.append((score, link, text))
    if not ranked:
        return None, ""
    ranked.sort(key=lambda item: item[0], reverse=True)
    return ranked[0][1], ranked[0][2]


def rows_to_enrichment(query: str, rows: list[dict[str, Any]], mnn_id: str | None, mnn_text: str) -> TabletkaEnrichment:
    variants: list[TabletkaVariant] = []
    form_dosage: dict[str, list[str]] = {}
    trade_names: list[str] = []
    trade_details: dict[str, dict[str, Any]] = {}
    pack_counts: dict[str, int] = {}

    for row in rows:
        form_raw = str(row.get("form_raw") or "")
        trade = str(row.get("trade_name") or "").strip()
        if NON_DRUG_RE.search(form_raw) or NON_DRUG_RE.search(trade):
            continue
        if len(trade) > 48:
            continue
        drug_form = classify_form(form_raw)
        dosage = parse_dosage(form_raw)
        packaging, dispense_qty = parse_packaging(form_raw)
        if not drug_form or not dosage:
            continue
        variants.append(
            TabletkaVariant(
                trade_name=trade,
                form_raw=form_raw,
                drug_form=drug_form,
                dosage=dosage,
                packaging=packaging or f"N{dispense_qty}",
                dispense_qty=dispense_qty,
                ls=row.get("ls"),
                producer=str(row.get("producer") or ""),
            )
        )
        form_dosage.setdefault(drug_form, [])
        if dosage not in form_dosage[drug_form]:
            form_dosage[drug_form].append(dosage)
        if trade and trade not in trade_names:
            trade_names.append(trade)
        if trade and dosage:
            trade_bucket = trade_details.setdefault(trade, {})
            if isinstance(trade_bucket, dict):
                trade_bucket[dosage] = {
                    "packaging": packaging or f"N{dispense_qty}",
                    "dispense_qty": dispense_qty,
                    "form": drug_form,
                }
        if packaging:
            pack_counts[packaging] = pack_counts.get(packaging, 0) + 1

    # sort dosages numerically within form
    def dose_key(value: str) -> float:
        match = re.search(r"(\d+(?:\.\d+)?)", value)
        return float(match.group(1)) if match else 0.0

    for form, doses in form_dosage.items():
        form_dosage[form] = sorted(doses, key=dose_key)

    form_options = sorted(form_dosage.keys(), key=lambda f: (0 if f == "Tab." else 1 if f == "Caps." else 2, f))
    dosage_options: list[str] = []
    for form in form_options:
        for dose in form_dosage[form]:
            if dose not in dosage_options:
                dosage_options.append(dose)

    default_form = form_options[0] if form_options else ""
    default_dosage = (form_dosage.get(default_form) or dosage_options or [""])[0]
    default_packaging = ""
    if pack_counts:
        default_packaging = max(pack_counts, key=pack_counts.get)

    mnn_num = None
    if mnn_id:
        match = re.search(r"mnn_id=(\d+)", mnn_id)
        mnn_num = match.group(1) if match else mnn_id

    return TabletkaEnrichment(
        query=query,
        mnn_id=mnn_num,
        mnn_text=mnn_text,
        variants=variants,
        form_options=form_options,
        dosage_options=dosage_options,
        form_dosage_map=form_dosage,
        trade_names=trade_names,
        trade_details=trade_details,
        default_form=default_form,
        default_dosage=default_dosage,
        default_packaging=default_packaging or "N30",
        message=f"Найдено позиций: {len(variants)}" if variants else "Нет разобранных позиций",
    )


def _pick_mnn_link_by_trade(rows: list[dict[str, Any]], trade_query: str) -> tuple[str | None, str]:
    target = _normalize_name(trade_query)
    if len(target) < 3:
        return None, ""
    for row in rows:
        trade = _normalize_name(str(row.get("trade_name") or ""))
        link = row.get("mnn_link")
        text = str(row.get("mnn_text") or "")
        if not link or not text:
            continue
        if trade == target or trade.startswith(target) or target.startswith(trade):
            return link, text
    return None, ""


def enrich_by_russian_name(
    russian_name: str,
    *,
    aliases: list[str] | None = None,
    session: requests.Session | None = None,
    pause_sec: float = 0.35,
) -> TabletkaEnrichment:
    """Ищет МНН на tabletka.by и собирает формы/дозировки/торговые названия."""
    sess = session or _session()
    queries: list[tuple[str, str]] = [("mnn", russian_name)]
    for alias in aliases or []:
        queries.append(("trade", str(alias)))

    seen_q: set[str] = set()
    for mode, query in queries:
        q = str(query or "").strip()
        key = _normalize_name(q)
        if len(key) < 3 or key in seen_q:
            continue
        seen_q.add(key)
        found = fetch_search_rows(q, session=sess)
        time.sleep(pause_sec)
        if not found:
            continue

        if mode == "mnn":
            mnn_link, mnn_text = _pick_mnn_link(found, russian_name)
        else:
            mnn_link, mnn_text = _pick_mnn_link_by_trade(found, q)
            if not mnn_link:
                mnn_link, mnn_text = _pick_mnn_link(found, russian_name)

        if mnn_link:
            mnn_rows = fetch_mnn_rows(mnn_link, session=sess)
            time.sleep(pause_sec)
            rows = mnn_rows or [
                row
                for row in found
                if _names_match(str(row.get("mnn_text") or ""), mnn_text or russian_name)
            ]
            if rows:
                return rows_to_enrichment(russian_name, rows, mnn_link, mnn_text)

        # Препараты без ссылки МНН (например Церебролизин): берём строки с совпадением названия
        direct_rows = [
            row
            for row in found
            if _names_match(str(row.get("trade_name") or ""), russian_name)
            or _names_match(str(row.get("trade_name") or ""), q)
        ]
        if direct_rows:
            return rows_to_enrichment(russian_name, direct_rows, None, russian_name)

    return TabletkaEnrichment(
        query=russian_name,
        message="Не найдено точного МНН на tabletka.by",
    )


def enrichment_to_seed_fields(enrichment: TabletkaEnrichment) -> dict[str, Any]:
    if not enrichment.variants:
        return {}
    return {
        "drug_form": enrichment.default_form,
        "dosage": enrichment.default_dosage,
        "packaging": enrichment.default_packaging,
        "form_options": enrichment.form_options,
        "dosage_options": enrichment.dosage_options,
        "form_dosage_map": enrichment.form_dosage_map,
        "trade_names": enrichment.trade_names,
        "trade_details": enrichment.trade_details,
        "tabletka": {
            "mnn_id": enrichment.mnn_id,
            "mnn_text": enrichment.mnn_text,
            "variants_count": len(enrichment.variants),
            "variants": [
                {
                    "trade_name": v.trade_name,
                    "form_raw": v.form_raw,
                    "drug_form": v.drug_form,
                    "dosage": v.dosage,
                    "packaging": v.packaging,
                    "dispense_qty": v.dispense_qty,
                    "ls": v.ls,
                    "producer": v.producer,
                }
                for v in enrichment.variants
            ],
        },
    }
