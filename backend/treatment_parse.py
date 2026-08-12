"""Разбор текста лечения из дневника / схемы приёма в строки рецепта."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from backend.trade_packaging import resolve_trade_packaging


_SKIP_LINE = re.compile(
    r"^(?:"
    r"лечение|рекомендации|терапия|назначено|принимает|принимать|"
    r"схема(?:\s+при[её]ма)?|препараты|rp\.?|recipe"
    r")\s*:?\s*$",
    re.IGNORECASE,
)

_BULLET = re.compile(r"^\s*(?:[-–—*•]+|\d+[.)]|\(\d+\))\s*")

_FORM_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bтаб\.?\b", re.IGNORECASE), "Tab."),
    (re.compile(r"\btab(?:lets?)?\.?\b", re.IGNORECASE), "Tab."),
    (re.compile(r"\bтаблет(?:к[аи]|ок|ке|ку)?\b", re.IGNORECASE), "Tab."),
    (re.compile(r"\bкапс\.?\b", re.IGNORECASE), "Caps."),
    (re.compile(r"\bcaps?(?:ules?)?\.?\b", re.IGNORECASE), "Caps."),
    (re.compile(r"\bкапсул(?:ы|а|е|у)?\b", re.IGNORECASE), "Caps."),
    (re.compile(r"\bsir(?:up)?\.?\b", re.IGNORECASE), "Sir."),
    (re.compile(r"\bсироп(?:а|е|у)?\b", re.IGNORECASE), "Sir."),
)

_DOSE_RE = re.compile(
    r"(?<!\d)(\d+(?:[.,]\d+)?)\s*(мг|mg|мкг|mcg|г|g)\.?\b",
    re.IGNORECASE,
)

_SCHEME_SPLIT = re.compile(r"\s*[—–−]\s*|\s+[-:]\s+")

_SCHEME_HINT = re.compile(
    r"\b(?:"
    r"по\s+\d|"
    r"утром|вечером|ноч[ьюи]|днём|днем|"
    r"раза?\s+в\s+день|р/?д|"
    r"через\s+день|по\s+потребности|"
    r"на\s+ночь|перед\s+сном|после\s+еды|до\s+еды|"
    r"1/2|½|1[,.]5\s*т|табл|\d+\s*т\b"
    r")\b",
    re.IGNORECASE,
)

_PACK_QTY_RE = re.compile(
    r"(?:\(\s*(?:№|N)\s*(\d+)\s*\)|(?:^|[\s,;])(?:№|N)\s*(\d+)(?=$|[\s);,]|\b))",
    re.IGNORECASE,
)
_PAREN_BLOCK_RE = re.compile(r"\([^)]*\)")

_KIND_PRIORITY = {
    "russian": 0,
    "mnn": 1,
    "alias": 2,
    "trade": 3,
}


def normalize_match_text(value: Any) -> str:
    text = str(value or "").replace("\u00a0", " ").strip().lower()
    text = text.replace("ё", "е")
    text = re.sub(r"[\"'`«»]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_dose(value: Any) -> str:
    raw = str(value or "").strip().lower().replace("ё", "е")
    raw = raw.replace(",", ".")
    raw = re.sub(r"\s+", " ", raw)
    match = _DOSE_RE.search(raw)
    if not match:
        return raw
    amount = match.group(1).replace(",", ".")
    unit = match.group(2).lower()
    unit_map = {"mg": "мг", "mcg": "мкг", "g": "г"}
    unit = unit_map.get(unit, unit)
    if "." in amount:
        amount = amount.rstrip("0").rstrip(".")
    return f"{amount} {unit}"


@dataclass(frozen=True)
class _NameEntry:
    key: str
    drug: dict[str, Any]
    kind: str  # russian | mnn | trade | alias
    display: str


def _word_boundary_pattern(name: str) -> re.Pattern[str]:
    # Точное слово + короткие русские падежные окончания (а/у/ом…), без «догонки»
    # лишними буквами внутри корня (чтобы «флувоксамин» не ел «флувоксин»).
    escaped = re.escape(name)
    if re.search(r"[а-яa-z]$", name, re.IGNORECASE):
        return re.compile(rf"(?<!\w){escaped}(?:[аеуыиояю]|ом|ами|ах)?(?!\w)", re.IGNORECASE)
    return re.compile(rf"(?<!\w){escaped}(?!\w)", re.IGNORECASE)


def build_name_index(catalog: list[dict[str, Any]]) -> list[_NameEntry]:
    entries: list[_NameEntry] = []
    seen: set[tuple[str, str]] = set()

    def add(raw: Any, drug: dict[str, Any], kind: str) -> None:
        display = str(raw or "").strip()
        key = normalize_match_text(display)
        if len(key) < 3:
            return
        marker = (key, str(drug.get("mnn") or ""))
        if marker in seen:
            return
        seen.add(marker)
        entries.append(_NameEntry(key=key, drug=drug, kind=kind, display=display))

    for drug in catalog:
        add(drug.get("russian_name"), drug, "russian")
        add(drug.get("mnn"), drug, "mnn")
        add(drug.get("latin_name"), drug, "mnn")
        for trade in drug.get("trade_names") or []:
            add(trade, drug, "trade")
        for alias in drug.get("search_aliases") or []:
            add(alias, drug, "alias")
        # Латынь без окончания -um/-i часто встречается в дневниках
        latin = str(drug.get("latin_name") or "").strip()
        if latin.lower().endswith("um") and len(latin) > 4:
            add(latin[:-2], drug, "mnn")

    entries.sort(key=lambda item: (-len(item.key), item.key))
    return entries


def split_treatment_lines(text: Any) -> list[str]:
    raw = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    raw = raw.replace("\u00a0", " ")
    chunks: list[str] = []
    for block in raw.split("\n"):
        block = block.strip()
        if not block:
            continue
        # Несколько препаратов через ; на одной строке
        parts = [part.strip() for part in re.split(r"\s*;\s*", block) if part.strip()]
        chunks.extend(parts or [block])

    lines: list[str] = []
    for chunk in chunks:
        line = _BULLET.sub("", chunk).strip(" .")
        if not line:
            continue
        if _SKIP_LINE.match(normalize_match_text(line)):
            continue
        lines.append(line)
    return lines


def extract_form(line: str) -> tuple[str, str]:
    for pattern, form in _FORM_PATTERNS:
        match = pattern.search(line)
        if not match:
            continue
        cleaned = f"{line[:match.start()]} {line[match.end():]}".strip(" ,.;")
        cleaned = re.sub(r"\s+", " ", cleaned)
        return form, cleaned
    return "", line


def extract_dosage(line: str) -> tuple[str, str]:
    match = _DOSE_RE.search(line)
    if not match:
        return "", line
    dosage = normalize_dose(match.group(0))
    cleaned = f"{line[:match.start()]} {line[match.end():]}".strip(" ,.;")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return dosage, cleaned


def extract_scheme(line: str) -> str:
    text = str(line or "").strip(" ,.;")
    if not text:
        return ""

    split = _SCHEME_SPLIT.split(text, maxsplit=1)
    if len(split) == 2 and split[1].strip():
        return split[1].strip(" ,.;")

    hint = _SCHEME_HINT.search(text)
    if hint:
        return text[hint.start() :].strip(" ,.;")

    return text.strip(" ,.;")


def pick_catalog_form(drug: dict[str, Any], requested: str) -> str:
    options = [str(x).strip() for x in (drug.get("form_options") or []) if str(x).strip()]
    if not options:
        default = str(drug.get("drug_form") or "").strip()
        return requested or default
    if requested:
        for option in options:
            if option.lower().rstrip(".") == requested.lower().rstrip("."):
                return option
    return str(drug.get("drug_form") or options[0])


def pick_catalog_dosage(drug: dict[str, Any], requested: str, form: str) -> str:
    form_map = drug.get("form_dosage_map") or {}
    mapped = form_map.get(form) if isinstance(form_map, dict) else None
    options = [str(x).strip() for x in (mapped or drug.get("dosage_options") or []) if str(x).strip()]
    if not options:
        default = str(drug.get("dosage") or "").strip()
        return requested or default

    if requested:
        want = normalize_dose(requested)
        for option in options:
            if normalize_dose(option) == want:
                return option
        # Частичное совпадение по числу (10 vs 10 мг)
        want_num = re.match(r"[\d.]+", want)
        if want_num:
            for option in options:
                if normalize_dose(option).startswith(want_num.group(0)):
                    return option
        return requested

    return str(drug.get("dosage") or options[0])


def extract_pack_qty(text: str) -> tuple[int | None, str]:
    match = _PACK_QTY_RE.search(text or "")
    if not match:
        return None, text
    raw_qty = match.group(1) or match.group(2)
    try:
        qty = int(raw_qty)
    except (TypeError, ValueError):
        return None, text
    cleaned = f"{text[:match.start()]} {text[match.end():]}"
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.;")
    cleaned = re.sub(r"\(\s*\)", " ", cleaned)
    cleaned = re.sub(r"\s+[()]\s*", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.;()")
    return qty, cleaned


def clean_scheme_text(value: Any) -> str:
    text = str(value or "")
    text = _PAREN_BLOCK_RE.sub(" ", text)
    text = re.sub(r"[()]", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" ,.;")
    return text


def strip_parentheticals(text: str) -> str:
    cleaned = _PAREN_BLOCK_RE.sub(" ", text or "")
    return re.sub(r"\s+", " ", cleaned).strip(" ,.;")


def find_drug_in_line(line: str, index: list[_NameEntry]) -> tuple[_NameEntry | None, str]:
    normalized = normalize_match_text(line)
    if not normalized:
        return None, line

    # Берём самое левое совпадение; при равной позиции — МНН/русское имя важнее торгового
    # (чтобы «Кветиапин (Кетилепт, Квентиакс…)» не цеплялся за название в скобках).
    best: tuple[int, int, int, _NameEntry, re.Match[str]] | None = None
    for entry in index:
        pattern = _word_boundary_pattern(entry.key)
        match = pattern.search(normalized)
        if not match:
            continue
        candidate = (
            match.start(),
            _KIND_PRIORITY.get(entry.kind, 9),
            -len(entry.key),
            entry,
            match,
        )
        if best is None or candidate[:3] < best[:3]:
            best = candidate

    if not best:
        return None, line

    entry = best[3]
    source_pattern = _word_boundary_pattern(entry.display if entry.display else entry.key)
    source_match = source_pattern.search(line)
    if source_match:
        remainder = f"{line[:source_match.start()]} {line[source_match.end():]}"
    else:
        remainder = re.sub(_word_boundary_pattern(entry.key), " ", normalized, count=1)
    remainder = strip_parentheticals(remainder)
    remainder = re.sub(r"\s+", " ", remainder).strip(" ,.;")
    return entry, remainder


def drug_payload_from_match(
    entry: _NameEntry,
    *,
    drug_form: str = "",
    dosage: str = "",
    scheme: str = "",
    dispense_qty: int | None = None,
) -> dict[str, Any]:
    drug = entry.drug
    form = pick_catalog_form(drug, drug_form)
    dose = pick_catalog_dosage(drug, dosage, form)
    selected_trade = entry.display if entry.kind == "trade" else ""
    mode = "trade" if selected_trade else "mnn"
    # "packaging" (фасовка) берём из базы и/или trade_details,
    # а "dispenseQty" (D.t.d.) — это количество для выдачи.
    # Их нельзя смешивать: шаг листания D.t.d. зависит именно от фасовки.
    packaging = drug.get("packaging") or ""
    trade_details = drug.get("trade_details") or {}
    if selected_trade and isinstance(trade_details, dict):
        selected_details = resolve_trade_packaging(trade_details, selected_trade, dose) or {}
        packaging = selected_details.get("packaging") or packaging
    payload = {
        "mnn": drug.get("mnn"),
        "russian_name": drug.get("russian_name"),
        "latin_name": drug.get("latin_name"),
        "drug_form": form,
        "dosage": dose,
        "packaging": packaging,
        "trade_names": list(drug.get("trade_names") or []),
        "form_options": list(drug.get("form_options") or []),
        "dosage_options": list(drug.get("dosage_options") or []),
        "form_dosage_map": dict(drug.get("form_dosage_map") or {}),
        "scheme_options": list(drug.get("scheme_options") or []),
        "trade_details": dict(drug.get("trade_details") or {}),
        "selectedTrade": selected_trade,
        "selectedScheme": scheme,
        "mode": mode,
        "matched_as": entry.display,
        "match_kind": entry.kind,
    }
    if dispense_qty is not None:
        payload["dispenseQty"] = dispense_qty
    return payload


def split_head_and_scheme(line: str) -> tuple[str, str]:
    text = str(line or "").strip()
    if not text:
        return "", ""
    split = _SCHEME_SPLIT.split(text, maxsplit=1)
    if len(split) == 2 and split[1].strip():
        return split[0].strip(" ,.;"), split[1].strip(" ,.;")
    return text, ""


def parse_treatment_line(line: str, index: list[_NameEntry]) -> dict[str, Any] | None:
    head, scheme = split_head_and_scheme(line)
    pack_qty, head = extract_pack_qty(head)
    form, head = extract_form(head)
    dosage, head = extract_dosage(head)
    # Скобки с перечнем торговых — не мешают поиску МНН в начале строки
    head_for_match = strip_parentheticals(head) or head
    entry, remainder = find_drug_in_line(head_for_match, index)
    if not entry:
        entry, remainder = find_drug_in_line(head, index)
        if not entry:
            return None

    form2, remainder = extract_form(remainder)
    dose2, remainder = extract_dosage(remainder)
    pack2, remainder = extract_pack_qty(remainder)
    form = form or form2
    dosage = dosage or dose2
    pack_qty = pack_qty or pack2

    if scheme:
        pack3, scheme = extract_pack_qty(scheme)
        pack_qty = pack_qty or pack3
        scheme = strip_parentheticals(scheme) or scheme
    else:
        pack3, remainder = extract_pack_qty(remainder)
        pack_qty = pack_qty or pack3
        scheme = extract_scheme(strip_parentheticals(remainder) or remainder)

    scheme = clean_scheme_text(scheme)
    return drug_payload_from_match(
        entry,
        drug_form=form,
        dosage=dosage,
        scheme=scheme,
        dispense_qty=pack_qty,
    )


def parse_treatment_text(text: Any, catalog: list[dict[str, Any]]) -> dict[str, Any]:
    lines = split_treatment_lines(text)
    if not lines:
        return {
            "ok": False,
            "drugs": [],
            "unmatched": [],
            "message": "Вставьте текст лечения из дневника.",
        }

    index = build_name_index(catalog)
    drugs: list[dict[str, Any]] = []
    unmatched: list[str] = []

    for line in lines:
        parsed = parse_treatment_line(line, index)
        if not parsed:
            unmatched.append(line)
            continue
        drugs.append(parsed)

    if not drugs:
        return {
            "ok": False,
            "drugs": [],
            "unmatched": unmatched,
            "message": "Не удалось определить препараты в тексте.",
        }

    message = f"Определено препаратов: {len(drugs)}"
    if unmatched:
        message += f", не распознано строк: {len(unmatched)}"

    return {
        "ok": True,
        "drugs": drugs,
        "unmatched": unmatched,
        "message": message,
    }
