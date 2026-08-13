"""Дневной кэш наличия: один опрос в сутки."""

from __future__ import annotations

from pathlib import Path

from backend.availability_cache import (
    DailyAvailabilityStore,
    build_daily_cache,
    has_useful_rows,
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
    assert "by_key" in store.snapshot()
    assert store.snapshot()["by_key"]["икс"]["status"] == "good"


def test_unknown_cache_is_not_useful_and_force_rechecks(tmp_path: Path):
    calls = []

    def flaky_checker(query, aliases=None):
        calls.append(query)
        status = "unknown" if len(calls) == 1 else "good"
        return MinskAvailability(
            query=query,
            status=status,
            label="Нет данных" if status == "unknown" else "Есть",
            pharmacies_minsk=0 if status == "unknown" else 4,
            offers=[],
            message=status,
        )

    store = DailyAvailabilityStore(tmp_path, checker=flaky_checker)
    drugs = [{"mnn": "Y", "russian_name": "Игрек", "trade_names": ["Торг"]}]
    store.ensure_today(drugs)
    if store._thread:
        store._thread.join(timeout=2)
    assert calls == ["Игрек"]
    assert is_fresh(store.snapshot()) is True
    assert has_useful_rows(store.snapshot()) is False

    store.ensure_today(drugs)
    if store._thread:
        store._thread.join(timeout=2)
    assert calls == ["Игрек", "Игрек"]

    store.ensure_today(drugs, force=True)
    if store._thread:
        store._thread.join(timeout=2)
    assert calls == ["Игрек", "Игрек", "Игрек"]
    assert store.lookup("торг")["status"] == "good"


def test_force_recovers_from_dead_worker(tmp_path: Path):
    calls = []

    def counting_checker(query, aliases=None):
        calls.append(query)
        return _fake_checker(query, aliases)

    store = DailyAvailabilityStore(tmp_path, checker=counting_checker)
    drugs = [{"mnn": "Z", "russian_name": "Зет", "trade_names": []}]
    store._checking = True
    store._thread = None
    store.ensure_today(drugs, force=True)
    if store._thread:
        store._thread.join(timeout=2)
    assert calls == ["Зет"]
    assert store.snapshot()["checking"] is False


def test_failed_refresh_keeps_previous_useful_cache(tmp_path: Path):
    calls = []

    def flaky_checker(query, aliases=None):
        calls.append(query)
        if len(calls) == 1:
            return _fake_checker(query, aliases)
        return MinskAvailability(
            query=query,
            status="unknown",
            label="Нет данных",
            pharmacies_minsk=0,
            offers=[],
            message="down",
        )

    store = DailyAvailabilityStore(tmp_path, checker=flaky_checker)
    drugs = [{"mnn": "Keep", "russian_name": "Сохранить", "trade_names": ["Альяс"]}]
    store.ensure_today(drugs)
    if store._thread:
        store._thread.join(timeout=2)
    assert store.lookup("сохранить")["status"] == "good"

    store.ensure_today(drugs, force=True)
    if store._thread:
        store._thread.join(timeout=2)
    assert len(calls) == 2
    assert store.lookup("альяс")["status"] == "good"
    assert store.snapshot()["useful"] is True
    assert "предыдущие" in store.snapshot()["message"] or "не вернул" in store.snapshot()["message"]


def test_progress_published_during_build(tmp_path: Path):
    progress_events = []

    def slowish_checker(query, aliases=None):
        return _fake_checker(query, aliases)

    drugs = [
        {"mnn": "A", "russian_name": "Ааа", "trade_names": []},
        {"mnn": "B", "russian_name": "Ббб", "trade_names": []},
    ]
    cache = build_daily_cache(
        drugs,
        checker=slowish_checker,
        on_progress=lambda partial: progress_events.append(partial["progress"]),
    )
    assert has_useful_rows(cache)
    assert progress_events == [{"done": 1, "total": 2}, {"done": 2, "total": 2}]


def test_pharmacy_total_from_split_texts():
    from backend.tabletka import _pharmacy_total_from_texts

    assert _pharmacy_total_from_texts(["Кетилепт", "табл 25мг", "в 3331", "аптеке"]) == 3331
    assert _pharmacy_total_from_texts(["в 12 аптеках"]) == 12


def test_shared_store_is_singleton(tmp_path: Path):
    import backend.availability_cache as availability_cache

    availability_cache._SHARED_STORE = None
    first = availability_cache.shared_store(tmp_path)
    second = availability_cache.shared_store(tmp_path / "other")
    assert first is second
    availability_cache._SHARED_STORE = None
