"""Тесты tabletka клиента."""

from __future__ import annotations

import pytest

from backend.tabletka import MinskAvailability, TabletkaOffer, check_availability_minsk, search_tabletka


def test_search_tabletka_falls_back_to_alias(monkeypatch):
    calls: list[str] = []

    def fake_once(_session, query, limit=8):
        calls.append(query)
        if query == "гидроксизин":
            return []
        return [TabletkaOffer(name="Атаракс", form="таблетки 25мг", pharmacies_total=3, result_id="42", url="https://example")]

    monkeypatch.setattr("backend.tabletka._search_tabletka_once", fake_once)
    offers = search_tabletka("гидроксизин", aliases=["Атаракс"])
    assert calls == ["гидроксизин", "Атаракс"]
    assert offers
    assert offers[0].name == "Атаракс"


def test_check_availability_uses_aliases(monkeypatch):
    def fake_search(query, aliases=None, limit=8, **_kwargs):
        if query == "гидроксизин":
            return []
        return [TabletkaOffer(name="Атаракс", form="таблетки 25мг", pharmacies_total=2, result_id="7", url="https://example")]

    monkeypatch.setattr("backend.tabletka.search_tabletka", fake_search)
    monkeypatch.setattr("backend.tabletka.count_minsk_pharmacies", lambda _result_id, **_kwargs: 2)

    result = check_availability_minsk("гидроксизин", aliases=["Атаракс"])
    assert isinstance(result, MinskAvailability)
    assert result.query == "Атаракс"
    assert result.status == "low"
    assert result.pharmacies_minsk == 2


def test_result_page_failure_is_unknown_not_none(monkeypatch):
    monkeypatch.setattr(
        "backend.tabletka.search_tabletka",
        lambda *args, **kwargs: [
            TabletkaOffer(name="Атаракс", form="таблетки 25мг", pharmacies_total=100, result_id="7", url="https://example")
        ],
    )
    monkeypatch.setattr("backend.tabletka.count_minsk_pharmacies", lambda *_a, **_k: None)
    result = check_availability_minsk("атаракс")
    assert result.status == "unknown"
    assert result.label == "Нет данных"


@pytest.mark.network
def test_search_escitalopram():
    offers = search_tabletka("эсциталопрам")
    assert offers
    assert any("сциталопрам" in offer.name.lower() or offer.result_id for offer in offers)


@pytest.mark.network
def test_availability_minsk_returns_status():
    result = check_availability_minsk("эсциталопрам")
    assert result.status in {"good", "low", "none", "unknown"}
    assert result.label
    assert isinstance(result.pharmacies_minsk, int)
