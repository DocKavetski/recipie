"""Тесты правил D.t.d. по фасовке."""

from __future__ import annotations

from backend.dispense_rules import (
    dispense_step_by_packaging,
    is_valid_dispense_qty,
    nearest_multiple,
)


def test_dispense_step_by_packaging():
    assert dispense_step_by_packaging("N28") == 14
    assert dispense_step_by_packaging("N30") == 10
    assert dispense_step_by_packaging("N50") == 10
    assert dispense_step_by_packaging("N14") == 14
    assert dispense_step_by_packaging("N7") == 1


def test_nearest_multiple():
    assert nearest_multiple(93, 10) == 90
    assert nearest_multiple(56, 14) == 56
    assert nearest_multiple(50, 14) == 56
    assert nearest_multiple(0, 14) == 14


def test_is_valid_dispense_qty():
    assert is_valid_dispense_qty(28, "N28")
    assert is_valid_dispense_qty(27, "N28") is False
    assert is_valid_dispense_qty(30, "N30")
    assert is_valid_dispense_qty(25, "N30") is False
