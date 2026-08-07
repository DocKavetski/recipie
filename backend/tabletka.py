"""Клиент tabletka.by: поиск и наличие в Минске (best-effort HTML)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
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

    for anchor in soup.select("a[href*='/result/']"):
        href = anchor.get("href") or ""
        match = re.search(r"ls=(\d+)", href)
        if not match:
            continue
        result_id = match.group(1)
        if result_id in seen:
            continue

        # Собираем соседние тексты карточки
        card = anchor.find_parent(["tr", "div", "li", "td"]) or anchor
        texts = [t.strip() for t in card.stripped_strings if t.strip()]
        name = texts[0] if texts else anchor.get_text(" ", strip=True)
        form = ""
        pharmacies_total = None
        for text in texts[1:6]:
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
                url=urljoin(BASE_URL, f"/result/?ls={result_id}&city=minsk"),
            )
        )
        if len(offers) >= limit:
            break

    return offers


def count_minsk_pharmacies(result_id: str) -> int:
    """Сколько аптек Минска показывают наличие для позиции ls=..."""
    session = _session()
    try:
        response = session.get(
            f"{BASE_URL}/result/",
            params={"ls": result_id, "city": "minsk"},
            timeout=25,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        LOGGER.warning("tabletka result failed for ls=%s: %s", result_id, exc)
        return 0

    soup = BeautifulSoup(response.text, "html.parser")
    count = 0
    for row in soup.select("table tr"):
        text = row.get_text(" ", strip=True)
        if "Минск" in text and re.search(r"\d+[.,]\d+\s*р", text):
            count += 1
    if count:
        return count

    # fallback: любые строки таблицы с Минск
    for row in soup.select("table tr"):
        text = row.get_text(" ", strip=True)
        if text.startswith("Минск") or ", Минск" in text or "Минск-" in text:
            if "Добавить" in text or "р." in text:
                count += 1
    return count


def check_availability_minsk(query: str) -> MinskAvailability:
    offers = search_tabletka(query)
    if not offers:
        return MinskAvailability(
            query=query,
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
        # если по Минску 0, но по РБ много — всё же «мало/нет»
        rb = max((o.pharmacies_total or 0) for o in offers[:3])
        if rb > 0:
            status, label = "none", "Нет в Минске"
        else:
            status, label = "none", "Нет"

    return MinskAvailability(
        query=query,
        status=status,
        label=label,
        pharmacies_minsk=minsk_total,
        offers=serialized,
        message=f"Минск: {minsk_total} аптек(и) по топ-позициям tabletka.by",
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
