"""Дневной кэш наличия: один опрос в сутки."""

from __future__ import annotations

from pathlib import Path

from backend.availability_cache import (
    DailyAvailabilityStore,
    build_daily_cache,
    cache_covers_drugs,
    collect_availability_drugs,
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
    assert calls[0] == "Икс"
    assert calls.count("Икс") >= 1
    first_count = len(calls)
    assert store.snapshot()["fresh"] is True
    store.ensure_today(drugs)
    if store._thread:
        store._thread.join(timeout=2)
    assert len(calls) == first_count
    assert first["ok"] is True
    assert store.lookup("икс")["label"] == "Есть"
    assert "by_key" in store.snapshot()
    assert store.snapshot()["by_key"]["икс"]["status"] == "good"


def test_unknown_cache_is_not_useful_and_force_rechecks(tmp_path: Path):
    calls = []
    state = {"unknown": True}

    def flaky_checker(query, aliases=None):
        calls.append(query)
        if state["unknown"]:
            return MinskAvailability(
                query=query,
                status="unknown",
                label="Нет данных",
                pharmacies_minsk=0,
                offers=[],
                message="unknown",
            )
        return _fake_checker(query, aliases)

    store = DailyAvailabilityStore(tmp_path, checker=flaky_checker)
    drugs = [{"mnn": "Y", "russian_name": "Игрек", "trade_names": ["Торг"]}]
    store.ensure_today(drugs)
    if store._thread:
        store._thread.join(timeout=2)
    assert calls[0] == "Игрек"
    first_count = len(calls)
    assert first_count >= 1
    assert is_fresh(store.snapshot()) is True
    assert has_useful_rows(store.snapshot()) is False

    store.ensure_today(drugs)
    if store._thread:
        store._thread.join(timeout=2)
    second_count = len(calls)
    assert second_count > first_count
    assert has_useful_rows(store.snapshot()) is False

    state["unknown"] = False
    store.ensure_today(drugs, force=True)
    if store._thread:
        store._thread.join(timeout=2)
    assert len(calls) > second_count
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
    assert "Зет" in calls
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
    assert len(calls) >= 2
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


def test_collect_availability_drugs_includes_archive():
    from backend.seed_loader import load_archived_drugs, load_seed_drugs

    catalog = load_seed_drugs()
    archived = load_archived_drugs()
    merged = collect_availability_drugs(catalog)
    assert len(merged) >= len(catalog) + len(archived) - 1
    assert any(item.get("archived") for item in merged)
    assert any(item["mnn"] == "Vilazodone" and item.get("archived") for item in merged)
    assert any(item["mnn"] == "Sertraline" and not item.get("archived") for item in merged)


def test_incomplete_cache_triggers_full_recheck(tmp_path: Path):
    calls = []

    def counting_checker(query, aliases=None):
        calls.append(query)
        return _fake_checker(query, aliases)

    store = DailyAvailabilityStore(tmp_path, checker=counting_checker)
    # Имитируем старый кэш «только 20»: две полезные строки при пяти препаратах.
    partial_drugs = [
        {"mnn": f"M{i}", "russian_name": f"Препарат{i}", "trade_names": []}
        for i in range(2)
    ]
    store.ensure_today(partial_drugs)
    if store._thread:
        store._thread.join(timeout=2)
    assert has_useful_rows(store.snapshot())
    assert len(store.snapshot()["rows"]) == 2

    full_drugs = [
        {"mnn": f"M{i}", "russian_name": f"Препарат{i}", "trade_names": []}
        for i in range(5)
    ]
    assert cache_covers_drugs(store.snapshot(), full_drugs) is False
    before = len(calls)
    store.ensure_today(full_drugs)
    if store._thread:
        store._thread.join(timeout=2)
    assert len(calls) > before
    assert len(store.snapshot()["rows"]) == 5
    assert cache_covers_drugs(store.snapshot(), full_drugs) is True


def test_build_marks_archived_rows():
    drugs = [
        {"mnn": "A", "russian_name": "Активный", "trade_names": [], "archived": False},
        {"mnn": "B", "russian_name": "Архивный", "trade_names": [], "archived": True},
    ]
    cache = build_daily_cache(drugs, checker=_fake_checker)
    by_mnn = {row["mnn"]: row for row in cache["rows"]}
    assert by_mnn["A"]["archived"] is False
    assert by_mnn["B"]["archived"] is True
