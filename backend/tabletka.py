"""Клиент tabletka.by: поиск и наличие в Минске (best-effort HTML)."""

from __future__ import annotations

import logging
import re
import time
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
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Connection": "keep-alive",
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
    match = re.search(r"(\d+)", text.replace("\xa0", " ").replace("\r", " ").replace("\n", " "))
    return int(match.group(1)) if match else None


def _extract_result_id(href: str) -> str | None:
    match = re.search(r"[?&]ls=(\d+)", href or "")
    return match.group(1) if match else None


def _offer_url(result_id: str) -> str:
    return urljoin(BASE_URL, f"/result/?ls={result_id}&region={MINSK_REGION_ID}")


def _pharmacy_total_from_texts(texts: list[str]) -> int | None:
    """«в 3331» и «аптеке» часто приходят разными узлами — склеиваем окно."""
    for index, text in enumerate(texts):
        low = text.lower().replace("\xa0", " ")
        if "аптек" in low:
            direct = _parse_int(text)
            if direct is not None:
                return direct
            if index > 0:
                prev = _parse_int(texts[index - 1])
                if prev is not None:
                    return prev
        match = re.search(r"(\d+)\s*аптек", low)
        if match:
            return int(match.group(1))
    for index in range(len(texts) - 1):
        if "аптек" in texts[index + 1].lower():
            value = _parse_int(texts[index])
            if value is not None:
                return value
    return None


def _get_with_retries(
    session: requests.Session,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    timeout: int = 25,
    attempts: int = 3,
) -> requests.Response | None:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = session.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_error = exc
            LOGGER.warning("tabletka request failed (%s/%s) %s: %s", attempt, attempts, url, exc)
            if attempt < attempts:
                time.sleep(0.6 * attempt)
    if last_error:
        LOGGER.warning("tabletka request exhausted retries for %s: %s", url, last_error)
    return None


def _search_tabletka_once(session: requests.Session, query: str, limit: int = 8) -> list[TabletkaOffer]:
    q = str(query or "").strip()
    if len(q) < 2:
        return []
    response = _get_with_retries(session, f"{BASE_URL}/search", params={"request": q}, timeout=25)
    if response is None:
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

        card = anchor.find_parent("tr") or anchor.find_parent(["div", "li", "td"]) or anchor
        texts = [t.strip() for t in card.stripped_strings if t.strip()]
        name = anchor.get_text(" ", strip=True) or (texts[0] if texts else "")
        form = ""
        pharmacies_total = _pharmacy_total_from_texts(texts)
        for text in texts:
            low = text.lower()
            if any(token in low for token in ("табл", "капс", "р-р", "мг", "раствор", "сироп")):
                if not form and "аптек" not in low:
                    form = text
                    break

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


def search_tabletka(
    query: str,
    aliases: Iterable[str] | None = None,
    limit: int = 8,
    *,
    session: requests.Session | None = None,
) -> list[TabletkaOffer]:
    """Поиск препаратов на tabletka.by с fallback по торговым названиям."""
    own_session = session is None
    session = session or _session()
    merged: list[TabletkaOffer] = []
    seen_ids: set[str] = set()

    try:
        for candidate in _unique_queries(query, aliases):
            for offer in _search_tabletka_once(session, candidate, limit=limit):
                key = offer.result_id or f"{offer.name}|{offer.form}|{offer.url}"
                if key in seen_ids:
                    continue
                seen_ids.add(key)
                merged.append(offer)
                if len(merged) >= limit:
                    return merged
        return merged
    finally:
        if own_session:
            session.close()


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


def count_minsk_pharmacies(result_id: str, *, session: requests.Session | None = None) -> int | None:
    """Сколько аптек Минска показывают товар для позиции ls=...

    None — запрос не удался; 0 — страница открылась, аптек нет.
    """
    own_session = session is None
    session = session or _session()
    try:
        response = _get_with_retries(
            session,
            f"{BASE_URL}/result/",
            params={"ls": result_id, "region": MINSK_REGION_ID},
            timeout=25,
        )
        if response is None:
            return None
        return _count_pharmacy_rows(response.text)
    finally:
        if own_session:
            session.close()


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
    *,
    session: requests.Session | None = None,
) -> MinskAvailability:
    own_session = session is None
    session = session or _session()
    queries = _unique_queries(query, aliases)
    offers: list[TabletkaOffer] = []
    used_query = query
    try:
        for idx, candidate in enumerate(queries):
            offers = search_tabletka(
                candidate,
                aliases=queries[idx + 1 :],
                limit=5,
                session=session,
            )
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

        # Один лучший оффер + запасной — меньше запросов, меньше таймаутов.
        minsk_total = 0
        saw_result_page = False
        serialized = []
        for offer in offers[:2]:
            minsk = count_minsk_pharmacies(offer.result_id, session=session) if offer.result_id else None
            if minsk is None:
                serialized.append(
                    {
                        "name": offer.name,
                        "form": offer.form,
                        "pharmacies_total": offer.pharmacies_total,
                        "pharmacies_minsk": None,
                        "result_id": offer.result_id,
                        "url": offer.url,
                    }
                )
                continue
            saw_result_page = True
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
                break

        if minsk_total >= 5:
            status, label = "good", "Есть"
        elif minsk_total >= 1:
            status, label = "low", "Мало"
        elif not saw_result_page:
            # Поиск сработал, но страницы аптек не открылись — это не «нет в Минске».
            return MinskAvailability(
                query=used_query,
                status="unknown",
                label="Нет данных",
                pharmacies_minsk=0,
                offers=serialized,
                message="Не удалось открыть страницы аптек tabletka.by.",
            )
        else:
            rb = max((o.pharmacies_total or 0) for o in offers[:3])
            if rb > 0:
                status, label = "none", "Нет в Минске"
            else:
                status, label = "none", "Нет"

        return MinskAvailability(
            query=used_query,
            status=status,
            label=label,
            pharmacies_minsk=minsk_total,
            offers=serialized,
            message=f"Минск: {minsk_total} аптек(и) по tabletka.by (region={MINSK_REGION_ID})",
        )
    finally:
        if own_session:
            session.close()


def availability_to_dict(result: MinskAvailability) -> dict[str, Any]:
    return {
        "query": result.query,
        "status": result.status,
        "label": result.label,
        "pharmacies_minsk": result.pharmacies_minsk,
        "offers": result.offers,
        "message": result.message,
    }
