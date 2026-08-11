"""Общая геометрия печати формы 1 (PDF + HTML).

Бланк по нормативу: 105×148 мм. На A4 — 4 бланка 2×2 без зазора,
0.5 мм поля сверху/снизу листа. Разрез по центру → каждый кусок 105×148.5 мм;
лицевая и оборот совмещаются при дуплексе по длинной стороне (L/R).
"""

from __future__ import annotations

from reportlab.lib.units import mm

A4_W = 210 * mm
A4_H = 297 * mm
FORM_W = 105 * mm
FORM_H = 148 * mm
PAGE_MARGIN_X = 0
PAGE_MARGIN_Y = 0.5 * mm
GUTTER_X = 0
GUTTER_Y = 0
PAD = 1.8 * mm
CUT_TICK = 4 * mm
CUT_CROSS = 5 * mm
CUT_INSET = 0.8 * mm

# CSS-строки (без reportlab)
CSS_FORM_W = "105mm"
CSS_FORM_H = "148mm"
CSS_PAGE_PAD_Y = "0.5mm"
CSS_BLANK_PAD = "1.8mm"
CSS_CUT_INSET = "0.8mm"


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
