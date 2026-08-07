"""Числительные для бланка рецепта."""

from __future__ import annotations

from typing import Any

UNITS = [
    "ноль", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять",
    "десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать", "пятнадцать",
    "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать",
]
TENS = [
    "", "", "двадцать", "тридцать", "сорок", "пятьдесят",
    "шестьдесят", "семьдесят", "восемьдесят", "девяносто",
]
HUNDREDS = [
    "", "сто", "двести", "триста", "четыреста", "пятьсот",
    "шестьсот", "семьсот", "восемьсот", "девятьсот",
]


def number_to_words_ru(value: Any) -> str:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return str(value or "")

    if number < 0:
        return str(number)
    if number < 20:
        return UNITS[number]
    if number < 100:
        tens, units = divmod(number, 10)
        return " ".join(part for part in [TENS[tens], UNITS[units] if units else ""] if part)
    if number < 1000:
        hundreds, remainder = divmod(number, 100)
        remainder_text = number_to_words_ru(remainder) if remainder else ""
        return " ".join(part for part in [HUNDREDS[hundreds], remainder_text] if part)
    return str(number)


def extract_default_dispense_qty(packaging: Any) -> int:
    import re

    match = re.search(r"\d+", str(packaging or ""))
    return int(match.group(0)) if match else 1
