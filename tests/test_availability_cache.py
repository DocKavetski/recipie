"""Дневной кэш наличия: один опрос в сутки."""

from __future__ import annotations

from pathlib import Path

from backend.availability_cache import (
    DailyAvailabilityStore,
    build_daily_cache,
    is_fresh,
    lookup_cached,
    today_key,
)
from backend.tabletka import MinskAvailability


def _fake_checker(query, aliases=None):
    return MinskAvailability(
        query=query,
        status="good",
        label="Есть",
        pharmacies_minsk=8,
        offers=[],
        message=f"ok:{query}",
    )


def test_build_and_lookup_daily_cache():
    drugs = [
        {
            "mnn": "Sertraline",
            "russian_name": "Сертралин",
            "latin_name": "Sertralinum",
            "trade_names": ["Стимулотон"],
        }
    ]
    cache = build_daily_cache(drugs, checker=_fake_checker)
    assert cache["date"] == today_key()
    assert len(cache["rows"]) == 1
    assert lookup_cached(cache, "сертралин")["status"] == "good"
    assert lookup_cached(cache, "Стимулотон")["mnn"] == "Sertraline"
    assert is_fresh(cache) is True


def test_store_skips_second_refresh(tmp_path: Path):
    calls = []

    def counting_checker(query, aliases=None):
        calls.append(query)
        return _fake_checker(query, aliases)

    store = DailyAvailabilityStore(tmp_path, checker=counting_checker)
    drugs = [{"mnn": "X", "russian_name": "Икс", "trade_names": []}]
    first = store.ensure_today(drugs)
    if store._thread:
        store._thread.join(timeout=2)
    assert calls == ["Икс"]
    assert store.snapshot()["fresh"] is True
    store.ensure_today(drugs)
    if store._thread:
        store._thread.join(timeout=2)
    assert calls == ["Икс"]
    assert first["ok"] is True
    assert store.lookup("икс")["label"] == "Есть"
