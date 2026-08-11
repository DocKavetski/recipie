"""Клиент tabletka.by: поиск и наличие в Минске (best-effort HTML)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

LOGGER = logging.getLogger(__name__)

BASE_URL = "https://tabletka.by"
# id региона «Минск» на tabletka.by (см. li.select-check-item)
MINSK_REGION_ID = "1001"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9",
}


@dataclass
class TabletkaOffer:
    name: str
    form: str
    pharmacies_total: int | None
    result_id: str | None
    url: str | None


@dataclass
class MinskAvailability:
    query: str
    status: str  # good | low | none | unknown
    label: str
    pharmacies_minsk: int
    offers: list[dict[str, Any]]
    message: str = ""


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def _parse_int(text: str) -> int | None:
    match = re.search(r"(\d+)", text.replace("\xa0", " "))
    return int(match.group(1)) if match else None


def _extract_result_id(href: str) -> str | None:
    match = re.search(r"[?&]ls=(\d+)", href or "")
    return match.group(1) if match else None


def _offer_url(result_id: str) -> str:
    return urljoin(BASE_URL, f"/result/?ls={result_id}&region={MINSK_REGION_ID}")


def search_tabletka(query: str, limit: int = 8) -> list[TabletkaOffer]:
    """Поиск препаратов на tabletka.by."""
    q = str(query or "").strip()
    if len(q) < 2:
        return []

    session = _session()
    try:
        response = session.get(f"{BASE_URL}/search", params={"request": q}, timeout=25)
        response.raise_for_status()
    except requests.RequestException as exc:
        LOGGER.warning("tabletka search failed for %s: %s", q, exc)
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    offers: list[TabletkaOffer] = []
    seen: set[str] = set()

    # Основная таблица результатов; запасной путь — любые ссылки с ls=
    anchors = soup.select("table a[href*='ls=']") or soup.select("a[href*='ls=']")
    for anchor in anchors:
        href = anchor.get("href") or ""
        if "/result" not in href:
            continue
        result_id = _extract_result_id(href)
        if not result_id or result_id in seen:
            continue

        card = anchor.find_parent(["tr", "div", "li", "td"]) or anchor
        texts = [t.strip() for t in card.stripped_strings if t.strip()]
        name = texts[0] if texts else anchor.get_text(" ", strip=True)
        form = ""
        pharmacies_total = None
        for text in texts[1:8]:
            low = text.lower()
            if "аптек" in low:
                pharmacies_total = _parse_int(text)
            elif any(token in low for token in ("табл", "капс", "р-р", "мг", "раствор", "сироп")):
                if not form:
                    form = text

        seen.add(result_id)
        offers.append(
            TabletkaOffer(
                name=name,
                form=form,
                pharmacies_total=pharmacies_total,
                result_id=result_id,
                url=_offer_url(result_id),
            )
        )
        if len(offers) >= limit:
            break

    return offers


def _count_pharmacy_rows(html: str) -> int:
    """Считаем строки аптек с ценой. При region=1001 это аптеки Минска."""
    soup = BeautifulSoup(html, "html.parser")
    count = 0
    for row in soup.select("table tr"):
        text = row.get_text(" ", strip=True)
        if not text or text.startswith("Аптека"):
            continue
        if re.search(r"\d+[.,]\d+\s*р", text):
            count += 1
    if count:
        return count

    # fallback без явной цены
    for row in soup.select("table tr"):
        text = row.get_text(" ", strip=True)
        if "Минск" in text and ("Добавить" in text or "р." in text):
            count += 1
    return count


def count_minsk_pharmacies(result_id: str) -> int:
    """Сколько аптек Минска показывают товар для позиции ls=..."""
    session = _session()
    try:
        response = session.get(
            f"{BASE_URL}/result/",
            params={"ls": result_id, "region": MINSK_REGION_ID},
            timeout=25,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        LOGGER.warning("tabletka result failed for ls=%s: %s", result_id, exc)
        return 0

    return _count_pharmacy_rows(response.text)


def _unique_queries(query: str, aliases: Iterable[str] | None = None) -> list[str]:
    values: list[str] = []
    for item in [query, *(aliases or [])]:
        text = str(item or "").strip()
        if text and text not in values:
            values.append(text)
    return values


def check_availability_minsk(
    query: str,
    aliases: Iterable[str] | None = None,
) -> MinskAvailability:
    queries = _unique_queries(query, aliases)
    offers: list[TabletkaOffer] = []
    used_query = query
    for candidate in queries:
        offers = search_tabletka(candidate)
        if offers:
            used_query = candidate
            break

    if not offers:
        return MinskAvailability(
            query=used_query,
            status="unknown",
            label="Нет данных",
            pharmacies_minsk=0,
            offers=[],
            message="На tabletka.by ничего не найдено или сайт недоступен.",
        )

    # Берём лучшие 3 оффера и считаем Минск
    minsk_total = 0
    serialized = []
    for offer in offers[:3]:
        minsk = count_minsk_pharmacies(offer.result_id) if offer.result_id else 0
        minsk_total = max(minsk_total, minsk)
        serialized.append(
            {
                "name": offer.name,
                "form": offer.form,
                "pharmacies_total": offer.pharmacies_total,
                "pharmacies_minsk": minsk,
                "result_id": offer.result_id,
                "url": offer.url,
            }
        )

    if minsk_total >= 5:
        status, label = "good", "Есть"
    elif minsk_total >= 1:
        status, label = "low", "Мало"
    else:
        rb = max((o.pharmacies_total or 0) for o in offers[:3])
        if rb > 0:
            status, label = "none", "Нет в Минске"
        else:
            # region-фильтр уже применён: 0 строк = нет в Минске на выдаче
            status, label = "none", "Нет"

    return MinskAvailability(
        query=used_query,
        status=status,
        label=label,
        pharmacies_minsk=minsk_total,
        offers=serialized,
        message=f"Минск: {minsk_total} аптек(и) по tabletka.by (region={MINSK_REGION_ID})",
    )


def availability_to_dict(result: MinskAvailability) -> dict[str, Any]:
    return {
        "query": result.query,
        "status": result.status,
        "label": result.label,
        "pharmacies_minsk": result.pharmacies_minsk,
        "offers": result.offers,
        "message": result.message,
    }
