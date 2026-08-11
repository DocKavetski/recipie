"""Общая геометрия печати формы 1 (PDF + HTML).

На A4 — 4 бланка 2×2. Поле PAGE_MARGIN (~4 мм) со всех сторон листа, чтобы
принтер не обрезал края (непечатаемая зона). Бланки чуть меньше норматива
(101×144.5 мм вместо 105×148), зато всё помещается. Дуплекс L/R сохраняется.
"""

from __future__ import annotations

from reportlab.lib.units import mm

A4_W = 210 * mm
A4_H = 297 * mm
PAGE_MARGIN = 4 * mm
PAGE_MARGIN_X = PAGE_MARGIN
PAGE_MARGIN_Y = PAGE_MARGIN
GUTTER_X = 0
GUTTER_Y = 0
FORM_W = (A4_W - 2 * PAGE_MARGIN_X - GUTTER_X) / 2  # 101 mm
FORM_H = (A4_H - 2 * PAGE_MARGIN_Y - GUTTER_Y) / 2  # 144.5 mm
PAD = 1.8 * mm
CUT_TICK = 4 * mm
CUT_CROSS = 5 * mm
CUT_INSET = 4 * mm


def blank_origins() -> list[tuple[float, float]]:
    """Нижний левый угол каждого бланка (PDF, origin снизу-слева)."""
    left_x = PAGE_MARGIN_X
    right_x = PAGE_MARGIN_X + FORM_W + GUTTER_X
    bottom_y = PAGE_MARGIN_Y
    top_y = PAGE_MARGIN_Y + FORM_H + GUTTER_Y
    return [
        (left_x, top_y),      # 0 верх-лево
        (right_x, top_y),     # 1 верх-право
        (left_x, bottom_y),   # 2 низ-лево
        (right_x, bottom_y),  # 3 низ-право
    ]


def content_box(ox: float, oy: float) -> tuple[float, float, float, float]:
    """left, bottom, width, height области таблицы внутри бланка."""
    return ox + PAD, oy + PAD, FORM_W - 2 * PAD, FORM_H - 2 * PAD
