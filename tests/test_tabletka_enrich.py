"""Юнит-тесты парсера tabletka (без сети)."""

from __future__ import annotations

from bs4 import BeautifulSoup

from backend.seed_loader import load_seed_drugs
from backend.tabletka_enrich import (
    classify_form,
    parse_dosage,
    parse_result_rows,
    rows_to_enrichment,
)


SAMPLE_HTML = """
<table>
<tr>
  <td class="name tooltip-info"><a href="/result/?ls=1">Велаксин</a>
    <a href="/search/mnn/?mnn_id=314">Венлафаксин</a></td>
  <td class="form tooltip-info"><a href="/result/?ls=1">капсулы пролонг действия 75мг N28</a></td>
</tr>
<tr>
  <td class="name tooltip-info"><a href="/result/?ls=2">Велаксин</a>
    <a href="/search/mnn/?mnn_id=314">Венлафаксин</a></td>
  <td class="form tooltip-info"><a href="/result/?ls=2">таблетки 37.5мг N14</a></td>
</tr>
<tr>
  <td class="name tooltip-info"><a href="/result/?ls=3">Алвента</a>
    <a href="/search/mnn/?mnn_id=314">Венлафаксин</a></td>
  <td class="form tooltip-info"><a href="/result/?ls=3">капсулы с модиф. высвобождением 150мг N28</a></td>
</tr>
</table>
"""


def test_classify_and_parse_dosage():
    assert classify_form("капсулы пролонг действия 75мг N28") == "Caps."
    assert classify_form("таблетки 37.5мг N14") == "Tab."
    assert classify_form("шампунь 300мл N1") == ""
    assert parse_dosage("капсулы 75мг N28") == "75 мг"
    assert parse_dosage("маска 500мл N1") == ""


def test_rows_to_enrichment_venlafaxine_like():
    rows = parse_result_rows(BeautifulSoup(SAMPLE_HTML, "html.parser"))
    enrichment = rows_to_enrichment("Венлафаксин", rows, "/search/mnn/?mnn_id=314", "Венлафаксин")
    assert enrichment.form_options == ["Tab.", "Caps."]
    assert enrichment.form_dosage_map["Tab."] == ["37.5 мг"]
    assert enrichment.form_dosage_map["Caps."] == ["75 мг", "150 мг"]
    assert "Велаксин" in enrichment.trade_names
    assert "Алвента" in enrichment.trade_names
    assert "225 мг" not in enrichment.dosage_options


def test_seed_venlafaxine_has_selectable_forms():
    venla = next(d for d in load_seed_drugs() if d["mnn"] == "Venlafaxine")
    assert "Tab." in venla["form_options"]
    assert "Caps." in venla["form_options"]
    assert "37.5 мг" in venla["dosage_options"]
    assert "75 мг" in venla["dosage_options"]
    assert "150 мг" in venla["dosage_options"]
    assert "225 мг" not in venla["dosage_options"]
    assert venla["form_dosage_map"]["Tab."] == ["37.5 мг", "75 мг"]
