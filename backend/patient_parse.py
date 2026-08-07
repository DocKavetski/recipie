"""Парсинг ФИО и даты рождения пациента (единый источник правил)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


DATE_PATTERNS = (
    re.compile(r"(?<!\d)(\d{1,2})[./-](\d{1,2})[./-](\d{4})(?!\d)"),
    re.compile(r"(?<!\d)(\d{4})[./-](\d{1,2})[./-](\d{1,2})(?!\d)"),
)

# Сначала формат с годом карты (12543/26), затем длинный номер (112567)
CARD_PATTERNS = (
    re.compile(r"(?<!\d)№?\s*(\d{3,}/\d{2})(?!\d)", re.IGNORECASE),
    re.compile(r"(?<!\d)№?\s*(\d{5,})(?!\d)", re.IGNORECASE),
)


@dataclass(frozen=True)
class ParsedPatient:
    patient_name: str
    birth_date: str
    card_number: str = ""
    full_name: str = ""
    age: int | None = None


def normalize_card_number(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    raw = re.sub(r"^[№#]\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s+", "", raw)
    return raw


def normalize_birth_date(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""

    iso = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if iso:
        return f"{iso.group(3)}.{iso.group(2)}.{iso.group(1)}"

    dotted = re.fullmatch(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", raw)
    if dotted:
        day, month, year = dotted.groups()
        return f"{int(day):02d}.{int(month):02d}.{year}"

    digits = re.sub(r"\D", "", raw)[:8]
    if len(digits) == 8:
        return f"{digits[0:2]}.{digits[2:4]}.{digits[4:8]}"
    if len(digits) >= 1:
        day = digits[0:2]
        month = digits[2:4]
        year = digits[4:8]
        parts = [p for p in (day, month, year) if p]
        return ".".join(parts)
    return raw


def parse_birth_date(value: Any) -> date | None:
    normalized = normalize_birth_date(value)
    match = re.fullmatch(r"(\d{2})\.(\d{2})\.(\d{4})", normalized)
    if not match:
        return None
    day, month, year = map(int, match.groups())
    try:
        return date(year, month, day)
    except ValueError:
        return None


def calculate_age(value: Any, today: date | None = None) -> int | None:
    birth = parse_birth_date(value)
    if not birth:
        return None
    today = today or date.today()
    age = today.year - birth.year
    if (today.month, today.day) < (birth.month, birth.day):
        age -= 1
    return max(age, 0)


def is_initial_token(word: str) -> bool:
    value = (word or "").strip()
    if not value:
        return False
    if re.fullmatch(r"[A-Za-zА-Яа-яЁё]\.?", value):
        return True
    # Уже готовые инициалы: К.А. / К.А / А.Б.В.
    return bool(
        re.fullmatch(r"(?:[A-Za-zА-Яа-яЁё]\.){1,3}", value)
        or re.fullmatch(r"(?:[A-Za-zА-Яа-яЁё]\.){1,2}[A-Za-zА-Яа-яЁё]", value)
    )


def initials_from_part(part: str) -> str:
    value = (part or "").strip()
    if is_initial_token(value):
        letters = re.findall(r"[A-Za-zА-Яа-яЁё]", value)
        return "".join(f"{letter.upper()}." for letter in letters)
    letter = value.replace(".", "")[:1]
    return f"{letter.upper()}." if letter else ""


def is_person_name_word(word: str) -> bool:
    value = (word or "").strip()
    if not value:
        return False
    if is_initial_token(value):
        return True
    return bool(re.fullmatch(r"[A-Za-zА-Яа-яЁё]{2,}(?:-[A-Za-zА-Яа-яЁё]+)*", value))


def capitalize_person_word(word: str) -> str:
    value = (word or "").strip()
    if not value:
        return ""
    if is_initial_token(value):
        return initials_from_part(value)
    return value[:1].upper() + value[1:]


def clean_patient_name_text(text: str) -> str:
    value = str(text or "")
    value = re.sub(r"\([^)]*\)?", " ", value)
    value = re.sub(r"\[[^\]]*\]?", " ", value)
    value = re.sub(r"[()[\]{}<>«»\"'`´]", " ", value)
    value = re.sub(r"[,;|·•]+", " ", value)
    value = re.sub(r"\b(?:г\.?р\.?|года?|р\.?)\b", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+", " ", value).strip(" .,;:/-–—")
    return value.strip()


def extract_person_name_parts(full_name: str) -> list[str]:
    words = [part for part in clean_patient_name_text(full_name).split(" ") if part]
    parts: list[str] = []

    def slot_count(items: list[str]) -> int:
        total = 0
        for part in items:
            letters = re.findall(r"[A-Za-zА-Яа-яЁё]", part)
            if is_initial_token(part) and len(letters) > 1:
                total += len(letters)
            else:
                total += 1
        return total

    for word in words:
        if not is_person_name_word(word):
            if parts:
                break
            continue
        parts.append(word)
        if slot_count(parts) >= 3:
            break
    return parts


def format_name_with_initials(full_name: Any) -> str:
    parts = extract_person_name_parts(str(full_name or ""))
    if not parts:
        return ""

    surname = capitalize_person_word(parts[0])
    if is_initial_token(parts[0]):
        # Нет фамилии — только инициалы
        return initials_from_part(parts[0])

    surname = surname.rstrip(".")
    if len(parts) == 1:
        return surname

    initials = "".join(initials_from_part(part) for part in parts[1:])
    return f"{surname} {initials}".strip()


def compose_patient_smart_value(name: Any, birth_date: Any, card_number: Any = "") -> str:
    return " ".join(
        part
        for part in (
            str(name or "").strip(),
            normalize_birth_date(birth_date),
            normalize_card_number(card_number),
        )
        if part
    )


def extract_card_number(text: str) -> tuple[str, str]:
    """Возвращает (номер_карты, текст_без_номера)."""
    for pattern in CARD_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        card = normalize_card_number(match.group(1))
        remainder = f"{text[:match.start()]} {text[match.end():]}"
        return card, remainder
    return "", text


def parse_patient_smart_input(raw: Any, today: date | None = None) -> ParsedPatient:
    text = str(raw or "").replace("\u00a0", " ")
    text = re.sub(r"[|·•]+", " ", text).strip()

    birth_date = ""
    matched = None
    for pattern in DATE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        matched = match
        g1, g2, g3 = match.groups()
        if len(g1) == 4:
            birth_date = normalize_birth_date(f"{g1}-{g2}-{g3}")
        else:
            birth_date = normalize_birth_date(f"{g1}.{g2}.{g3}")
        break

    if matched:
        text = f"{text[:matched.start()]} {text[matched.end():]}"

    card_number, text = extract_card_number(text)

    name_parts = extract_person_name_parts(text)
    full_name = " ".join(name_parts)
    patient_name = format_name_with_initials(full_name)
    age = calculate_age(birth_date, today=today)

    return ParsedPatient(
        patient_name=patient_name,
        birth_date=birth_date,
        card_number=card_number,
        full_name=full_name,
        age=age,
    )
