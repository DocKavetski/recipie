from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from backend.patient_parse import format_name_with_initials, normalize_birth_date
from backend.rx_format import format_rp_lines
from backend.validate import chunk_drugs, duplex_back_index


# 4 бланка на A4. Поля и желоб подобраны так, чтобы после разреза
# по центру у каждого куска были одинаковые отступы со всех сторон
# (PAGE_MARGIN == GUTTER/2), и лицевая/оборот совпали при дуплексе L/R.
A4_W = 210 * mm
A4_H = 297 * mm
PAGE_MARGIN = 3 * mm
GUTTER = 6 * mm  # = 2 * PAGE_MARGIN
FORM_W = (A4_W - 2 * PAGE_MARGIN - GUTTER) / 2  # 99 mm
FORM_H = (A4_H - 2 * PAGE_MARGIN - GUTTER) / 2  # 142.5 mm
PAD = 1.8 * mm
CUT_TICK = 4 * mm
CUT_CROSS = 5 * mm
CUT_INSET = 0.8 * mm

_FONT_REGISTERED = False
FONT_NAME = "AppSans"
FONT_BOLD = "AppSans-Bold"


def _register_fonts() -> None:
    global _FONT_REGISTERED, FONT_NAME, FONT_BOLD
    if _FONT_REGISTERED:
        return

    candidates = [
        (Path(r"C:\Windows\Fonts\arial.ttf"), Path(r"C:\Windows\Fonts\arialbd.ttf")),
        (Path(r"C:\Windows\Fonts\segoeui.ttf"), Path(r"C:\Windows\Fonts\segoeuib.ttf")),
        (Path(r"C:\Windows\Fonts\times.ttf"), Path(r"C:\Windows\Fonts\timesbd.ttf")),
    ]

    for regular, bold in candidates:
        if regular.exists() and bold.exists():
            pdfmetrics.registerFont(TTFont("AppSans", str(regular)))
            pdfmetrics.registerFont(TTFont("AppSans-Bold", str(bold)))
            FONT_NAME = "AppSans"
            FONT_BOLD = "AppSans-Bold"
            _FONT_REGISTERED = True
            return

    FONT_NAME = "Helvetica"
    FONT_BOLD = "Helvetica-Bold"
    _FONT_REGISTERED = True


def _normalize_birth_date(value):
    return normalize_birth_date(value)


def _format_patient_initials(value):
    return format_name_with_initials(value)


def _today_text() -> str:
    months = [
        "", "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря",
    ]
    now = datetime.now()
    return f"{now.day} {months[now.month]} {now.year} г."


def _wrap(pdf: canvas.Canvas, text: str, font: str, size: float, max_width: float) -> list[str]:
    words = str(text or "").split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if pdf.stringWidth(candidate, font, size) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _content_box(ox: float, oy: float) -> tuple[float, float, float, float]:
    """left, bottom, width, height of printable table area."""
    return ox + PAD, oy + PAD, FORM_W - 2 * PAD, FORM_H - 2 * PAD


def _draw_cell(pdf: canvas.Canvas, x: float, y: float, w: float, h: float) -> None:
    pdf.setLineWidth(0.55)
    pdf.rect(x, y, w, h)


def _draw_paragraphs(
    pdf: canvas.Canvas,
    lines: list[str],
    x: float,
    top: float,
    max_width: float,
    font: str,
    size: float,
    leading: float,
    center: bool = False,
) -> float:
    y = top
    for line in lines:
        for wrapped in _wrap(pdf, line, font, size, max_width):
            pdf.setFont(font, size)
            if center:
                pdf.drawCentredString(x + max_width / 2, y - size, wrapped)
            else:
                pdf.drawString(x, y - size, wrapped)
            y -= leading
    return y


def _draw_front(
    pdf: canvas.Canvas,
    ox: float,
    oy: float,
    payload: dict[str, Any],
    stamp_text: str,
    drugs: list[dict[str, Any]],
) -> None:
    left, bottom, width, height = _content_box(ox, oy)
    today = _today_text()

    # Column widths matching HTML: 16.55 / 32.90 / 50.55
    c1 = width * 0.1655
    c2 = width * 0.3290
    c3 = width * 0.5055

    # Row heights: оставляем место под нижнюю строку срока действия и её рамку
    h0, h1, h2, h3, h4, h5 = 25 * mm, 13.5 * mm, 15.5 * mm, 21 * mm, 23 * mm, 23 * mm
    fixed = h0 + h1 + h2 + h3 + h4 + h5
    h_valid = height - fixed
    if h_valid < 8 * mm:
        scale = (height - 8 * mm) / fixed
        h0, h1, h2, h3, h4, h5 = h0 * scale, h1 * scale, h2 * scale, h3 * scale, h4 * scale, h5 * scale
        h_valid = height - (h0 + h1 + h2 + h3 + h4 + h5)
    y = bottom + height

    # --- row 0: stamp | law ---
    y -= h0
    _draw_cell(pdf, left, y, c1 + c2, h0)
    _draw_cell(pdf, left + c1 + c2, y, c3, h0)

    stamp_lines = [line.strip() for line in str(stamp_text).split("\n") if line.strip()]
    _draw_paragraphs(pdf, stamp_lines, left + 1.2 * mm, y + h0 - 1.2 * mm, c1 + c2 - 2.4 * mm, FONT_NAME, 5.4, 6.2)

    law = [
        "Медицинская документация Форма 1",
        "Утверждена",
        "Министерством здравоохранения",
        "Республики Беларусь",
        "УНП организации здравоохранения 191896187",
    ]
    _draw_paragraphs(pdf, law, left + c1 + c2 + 1.2 * mm, y + h0 - 1.2 * mm, c3 - 2.4 * mm, FONT_NAME, 5.4, 6.2)

    # --- row 1: title | dates ---
    y -= h1
    _draw_cell(pdf, left, y, c1 + c2, h1)
    _draw_cell(pdf, left + c1 + c2, y, c3, h1)
    pdf.setFont(FONT_NAME, 11)
    pdf.drawCentredString(left + (c1 + c2) / 2, y + h1 / 2 - 3, "РЕЦЕПТ ВРАЧА")

    date_lines = [
        "Дата выписки рецепта",
        today,
        "Рецепт врача действителен с",
        today,
    ]
    _draw_paragraphs(
        pdf,
        date_lines,
        left + c1 + c2 + 1.2 * mm,
        y + h1 - 1.5 * mm,
        c3 - 2.4 * mm,
        FONT_NAME,
        7.2,
        7.8,
        center=True,
    )

    # --- row 2: person ---
    y -= h2
    _draw_cell(pdf, left, y, width, h2)
    person = [
        f"Фамилия, инициалы пациента  {_format_patient_initials(payload.get('patient_name', ''))}",
        f"Дата рождения  {_normalize_birth_date(payload.get('birth_date', ''))}",
        f"Фамилия, инициалы врача  {payload.get('doctor_name', '')}",
        "(иного медицинского работника)",
    ]
    _draw_paragraphs(pdf, person, left + 1.2 * mm, y + h2 - 1.2 * mm, width - 2.4 * mm, FONT_NAME, 7.2, 7.6)

    # --- rows 3–4: drugs ---
    for row_h, drug in ((h3, drugs[0] if len(drugs) > 0 else None), (h4, drugs[1] if len(drugs) > 1 else None)):
        y -= row_h
        _draw_cell(pdf, left, y, c1, row_h)
        _draw_cell(pdf, left + c1, y, c2 + c3, row_h)
        pdf.setFont(FONT_NAME, 10)
        pdf.drawCentredString(left + c1 / 2, y + row_h / 2 - 3, "Rp:")
        if drug:
            lines = format_rp_lines(drug)
            cursor = y + row_h - 1.5 * mm
            for i, line in enumerate(lines):
                size = 8.5 if i == 0 else 7.5
                font = FONT_BOLD if i == 0 else FONT_NAME
                for wrapped in _wrap(pdf, line, font, size, c2 + c3 - 2.4 * mm)[:3 if i == 2 else 2]:
                    pdf.setFont(font, size)
                    pdf.drawString(left + c1 + 1.2 * mm, cursor - size, wrapped)
                    cursor -= size + 1.2

    # --- row 5: signature (3rd Rp) ---
    y -= h5
    _draw_cell(pdf, left, y, c1, h5)
    _draw_cell(pdf, left + c1, y, c2 + c3, h5)
    pdf.setFont(FONT_NAME, 10)
    pdf.drawCentredString(left + c1 / 2, y + h5 / 2 - 3, "Rp:")
    pdf.setFont(FONT_NAME, 6.5)
    pdf.drawString(left + c1 + 1.5 * mm, y + 8 * mm, "Подпись врача (иного медицинского работника)")
    pdf.drawString(left + c1 + 1.5 * mm, y + 4 * mm, "Печать врача (иного медицинского работника)")

    # --- validity ---
    y -= h_valid
    _draw_cell(pdf, left, y, width, h_valid)
    pdf.setFont(FONT_NAME, 7.2)
    text = "Настоящий рецепт действителен в течение 30 дней, 60 дней"
    pdf.drawCentredString(left + width / 2, y + h_valid / 2 + 1.5, text)
    # strike "30 дней"
    strike = "30 дней"
    full_w = pdf.stringWidth(text, FONT_NAME, 7.2)
    strike_w = pdf.stringWidth(strike, FONT_NAME, 7.2)
    prefix_w = pdf.stringWidth("Настоящий рецепт действителен в течение ", FONT_NAME, 7.2)
    sx = left + width / 2 - full_w / 2 + prefix_w
    pdf.setLineWidth(0.8)
    pdf.line(sx, y + h_valid / 2 + 3, sx + strike_w, y + h_valid / 2 + 4)
    pdf.setFont(FONT_NAME, 6.5)
    pdf.drawCentredString(left + width / 2, y + h_valid / 2 - 5, "(ненужное зачеркнуть)")


def _draw_back(pdf: canvas.Canvas, ox: float, oy: float) -> None:
    left, bottom, width, height = _content_box(ox, oy)

    # Column ratios from HTML
    ratios = [0.3004, 0.1842, 0.1448, 0.1130, 0.2576]
    cols = [width * r for r in ratios]

    headers = [
        "Наименование лекарственного препарата, его лекарственная форма, дозировка, фасовка",
        "Количество реализованных упаковок",
        "Цена за упаковку, рублей",
        "Сумма, рублей",
        "№ аптеки, адрес, дата реализации и подпись фармацевтического работника",
    ]

    # Высоты строк как в print_blank.css / preview (последняя — остаток)
    h1, h2, h3, h4, h5 = 14 * mm, 9 * mm, 13 * mm, 14 * mm, 10 * mm
    fixed = h1 + h2 + h3 + h4 + h5
    h6 = height - fixed
    if h6 < 28 * mm:
        scale = (height - 28 * mm) / fixed
        h1, h2, h3, h4, h5 = h1 * scale, h2 * scale, h3 * scale, h4 * scale, h5 * scale
        h6 = height - (h1 + h2 + h3 + h4 + h5)
    y = bottom + height

    # header row
    y -= h1
    x = left
    for col_w, header in zip(cols, headers):
        _draw_cell(pdf, x, y, col_w, h1)
        cursor = y + h1 - 1.5 * mm
        for line in _wrap(pdf, header, FONT_NAME, 5.2, col_w - 1.6 * mm)[:5]:
            pdf.setFont(FONT_NAME, 5.2)
            pdf.drawCentredString(x + col_w / 2, cursor - 5.2, line)
            cursor -= 5.8
        x += col_w

    # empty data row
    y -= h2
    x = left
    for col_w in cols:
        _draw_cell(pdf, x, y, col_w, h2)
        x += col_w

    # spacer row (no left/right borders visually — still draw full rect)
    y -= h3
    _draw_cell(pdf, left, y, width, h3)

    # pharmacy number / stamp labels
    y -= h4
    _draw_cell(pdf, left, y, cols[0] + cols[1], h4)
    _draw_cell(pdf, left + cols[0] + cols[1], y, cols[2] + cols[3] + cols[4], h4)
    pdf.setFont(FONT_NAME, 6.5)
    pdf.drawCentredString(left + (cols[0] + cols[1]) / 2, y + h4 / 2 - 2, "Номер лекарственного препарата аптечного изготовления")
    pdf.drawCentredString(left + cols[0] + cols[1] + (cols[2] + cols[3] + cols[4]) / 2, y + h4 / 2 - 2, "Штамп аптеки")

    # roles
    y -= h5
    role_widths = [cols[0], cols[1], cols[2], cols[3] + cols[4]]
    roles = ["Принял", "Приготовил", "Проверил", "Реализовал"]
    x = left
    for col_w, role in zip(role_widths, roles):
        _draw_cell(pdf, x, y, col_w, h5)
        pdf.setFont(FONT_NAME, 6.5)
        pdf.drawCentredString(x + col_w / 2, y + h5 / 2 - 2, role)
        x += col_w

    # signature area
    y -= h6
    x = left
    for col_w in role_widths:
        _draw_cell(pdf, x, y, col_w, h6)
        x += col_w


def _blank_origins() -> list[tuple[float, float]]:
    """
    4 бланка на A4 (2x2) с равными полями после разреза по центру:
      [0][1]
      [2][3]
    PAGE_MARGIN == GUTTER/2, поэтому у каждого куска отступ одинаков
    с внешнего края и со стороны реза — лицевая и оборот совпадают.
    """
    left_x = PAGE_MARGIN
    right_x = PAGE_MARGIN + FORM_W + GUTTER
    bottom_y = PAGE_MARGIN
    top_y = PAGE_MARGIN + FORM_H + GUTTER
    return [
        (left_x, top_y),
        (right_x, top_y),
        (left_x, bottom_y),
        (right_x, bottom_y),
    ]


def _draw_cut_guides(pdf: canvas.Canvas) -> None:
    """Короткие метки разреза на краях и маленький крестик в центре."""
    pdf.setDash()
    pdf.setStrokeColorRGB(0.35, 0.35, 0.35)
    pdf.setLineWidth(0.4)

    cx = A4_W / 2
    cy = A4_H / 2

    # метки на краях листа (в поле)
    inset = CUT_INSET
    pdf.line(cx, A4_H - inset, cx, A4_H - inset - CUT_TICK)
    pdf.line(cx, inset, cx, inset + CUT_TICK)
    pdf.line(inset, cy, inset + CUT_TICK, cy)
    pdf.line(A4_W - inset, cy, A4_W - inset - CUT_TICK, cy)

    # маленький крестик в центре между бланками
    half = CUT_CROSS / 2
    pdf.line(cx - half, cy, cx + half, cy)
    pdf.line(cx, cy - half, cx, cy + half)

    pdf.setStrokeColorRGB(0, 0, 0)


def generate_prescription_pdf(payload: dict[str, Any], output_dir: Path, stamp_text: str) -> Path:
    """
    A4, 4 бланка формы 1 (2×2), лицевая + оборотная.
    Дуплекс по длинной стороне: оборот зеркалит лево/право.
    """
    _register_fonts()
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_path = output_dir / f"prescription_{timestamp}.pdf"

    drugs = [drug for drug in payload.get("drugs", []) if drug.get("mnn")]
    if not drugs:
        raise ValueError("No drugs to print.")

    blanks = chunk_drugs(drugs, 2)
    pdf = canvas.Canvas(str(pdf_path), pagesize=(A4_W, A4_H))
    origins = _blank_origins()
    # Дуплекс по длинной стороне: лицевая позиция i ↔ оборот в mirror[i]
    for sheet_index in range(0, len(blanks), 4):
        sheet_blanks = blanks[sheet_index:sheet_index + 4]

        for idx, blank_drugs in enumerate(sheet_blanks):
            if not blank_drugs:
                continue
            ox, oy = origins[idx]
            _draw_front(pdf, ox, oy, payload, stamp_text, blank_drugs)

        _draw_cut_guides(pdf)
        pdf.showPage()

        for idx, blank_drugs in enumerate(sheet_blanks):
            if not blank_drugs:
                continue
            ox, oy = origins[duplex_back_index(idx)]
            _draw_back(pdf, ox, oy)

        _draw_cut_guides(pdf)
        pdf.showPage()

    pdf.save()
    return pdf_path
