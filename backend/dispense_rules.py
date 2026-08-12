"""Правила шага и кратности для D.t.d. по фасовке."""

from __future__ import annotations

from backend.numbers_ru import extract_default_dispense_qty


def dispense_step_by_packaging(packaging: str | None) -> int:
    pack_qty = extract_default_dispense_qty(packaging)
    if pack_qty % 14 == 0:
        return 14
    if pack_qty % 10 == 0:
        return 10
    return 1


def nearest_multiple(value: int | str | None, step: int) -> int:
    numeric = int(str(value or "").strip() or "0")
    if numeric < 1:
        return max(step, 1)
    if step <= 1:
        return numeric
    return max(step, round(numeric / step) * step)


def is_valid_dispense_qty(qty: int | str | None, packaging: str | None) -> bool:
    try:
        qty_num = int(qty)
    except (TypeError, ValueError):
        return False
    if qty_num < 1:
        return False
    step = dispense_step_by_packaging(packaging)
    return step <= 1 or qty_num % step == 0
