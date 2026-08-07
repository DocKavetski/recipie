"""Тесты tabletka клиента (сеть, best-effort)."""

from __future__ import annotations

import pytest

from backend.tabletka import check_availability_minsk, search_tabletka


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
