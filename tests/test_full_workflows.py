"""Сквозные сценарии: дневник → каталог → валидация → PDF → история → шаблон."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.availability_cache import DailyAvailabilityStore, lookup_cached
from backend.custom_drug_add import add_custom_drug_from_tabletka, build_mnn_key
from backend.db import DrugRepository
from backend.defaults import DEFAULT_STAMP, DEFAULT_UNP
from backend.dispense_rules import ceil_to_dispense_step, is_valid_dispense_qty
from backend.doctor_change import change_doctor
from backend.numbers_ru import number_to_words_ru
from backend.patient_parse import parse_patient_smart_input
from backend.pdf_gen import generate_prescription_pdf
from backend.print_layout import A4_H, A4_W, FORM_H, FORM_W, PAGE_MARGIN_X, PAGE_MARGIN_Y
from backend.print_preview import build_preview_context
from backend.rx_format import format_rp_lines
from backend.seed_loader import load_seed_drugs
from backend.settings import SettingsStore
from backend.tabletka import MinskAvailability
from backend.tabletka_enrich import TabletkaEnrichment, TabletkaVariant
from backend.treatment_parse import parse_treatment_text
from backend.updater import SKIP_REPLACE_DIRS, SKIP_REPLACE_NAMES, _apply_frozen_overlay_from_source
from backend.validate import (
    chunk_drugs,
    duplex_back_index,
    normalize_prescription_payload,
    validate_prescription_payload,
)


def _repo(tmp_path: Path) -> DrugRepository:
    repo = DrugRepository(tmp_path / "app.db")
    repo.initialize()
    return repo


def _patient(**overrides):
    payload = {
        "patient_name": "Иванов Иван Иванович",
        "birth_date": "01.01.1990",
        "doctor_name": "Кавецкий А.С.",
        "card_number": "12543/26",
        "drugs": [],
    }
    payload.update(overrides)
    return payload


class TestCatalogIntegrity:
    def test_every_seed_drug_has_required_fields(self):
        for drug in load_seed_drugs():
            assert drug.get("mnn")
            assert drug.get("russian_name")
            assert drug.get("latin_name")
            assert drug.get("drug_form")
            assert drug.get("packaging")
            assert isinstance(drug.get("trade_names"), list)
            assert isinstance(drug.get("form_options"), list) and drug["form_options"]
            assert isinstance(drug.get("dosage_options"), list)
            assert isinstance(drug.get("scheme_options"), list)
            assert isinstance(drug.get("trade_details"), dict)
            for form in drug["form_options"]:
                assert isinstance(form, str)
            for dose in drug["dosage_options"]:
                assert isinstance(dose, str)

    def test_search_is_case_and_yo_insensitive(self, tmp_path: Path):
        repo = _repo(tmp_path)
        assert repo.search_drugs("ЭСЦИТАЛОПРАМ")
        assert repo.search_drugs("Ципралекс")
        assert repo.search_drugs("сертралин")
        assert repo.search_drugs(None) == []
        repo.upsert_custom_drug({"mnn": "Greeninum", "russian_name": "Зелёный"})
        assert any(item["mnn"] == "Greeninum" for item in repo.search_drugs("зеленый"))

    def test_every_seed_russian_name_parses(self):
        catalog = load_seed_drugs()
        for drug in catalog:
            parsed = parse_treatment_text(f"{drug['russian_name']} — утром", catalog)
            assert parsed["ok"] is True, drug["russian_name"]
            assert parsed["drugs"][0]["mnn"] == drug["mnn"]


class TestPatientIntakeScenarios:
    def test_smart_line_with_card_and_date(self):
        parsed = parse_patient_smart_input("Петрова Анна Сергеевна 15.03.1985 №12543/26")
        assert parsed.patient_name == "Петрова А.С."
        assert parsed.birth_date == "15.03.1985"
        assert parsed.card_number == "12543/26"

    def test_smart_line_iso_date(self):
        parsed = parse_patient_smart_input("Сидоров П.П. 1988-12-01 112567")
        assert parsed.patient_name == "Сидоров П.П."
        assert parsed.birth_date == "01.12.1988"
        assert parsed.card_number == "112567"


class TestDiaryToPrintWorkflow:
    def test_diary_parse_validate_pdf_and_preview(self, tmp_path: Path):
        catalog = _repo(tmp_path).list_drugs()
        parsed = parse_treatment_text(
            "\n".join([
                "Эсциталопрам 10 мг — по 1 таблетке утром №30",
                "Кветиапин 25 мг на ночь (№28)",
                "Стимулотон 100 мг по 1 таб. утром (№90)",
            ]),
            catalog,
        )
        assert parsed["ok"] is True
        assert len(parsed["drugs"]) == 3

        esc, quet, stim = parsed["drugs"]
        assert esc["mnn"] == "Escitalopram"
        assert esc["dispenseQty"] == 30
        assert quet["mnn"] == "Quetiapine"
        assert is_valid_dispense_qty(quet["dispenseQty"], quet["packaging"])
        assert stim["selectedTrade"] == "Стимулотон"
        assert stim["packaging"] == "N28"
        assert stim["dispenseQty"] == 98

        payload = _patient(drugs=parsed["drugs"])
        normalized = normalize_prescription_payload(payload)
        result = validate_prescription_payload(normalized)
        assert result.ok, result.errors

        pdf_path = generate_prescription_pdf(normalized, tmp_path / "prints", DEFAULT_STAMP)
        assert pdf_path.exists()
        assert pdf_path.stat().st_size > 1000

        preview = build_preview_context(normalized, DEFAULT_STAMP, DEFAULT_UNP)
        assert preview["patient_name"] == "Иванов И.И."
        assert preview["front_batches"][0][0][0]["rp_lines"][1].startswith("D.t.d.")
        assert "D.t.d." not in preview["front_batches"][0][0][0]["rp_lines"][0]
        assert preview["duplex_back_slot"] == [1, 0, 3, 2]

    def test_nine_drugs_make_two_duplex_sheets(self, tmp_path: Path):
        catalog = _repo(tmp_path).list_drugs()
        names = [d["russian_name"] for d in catalog[:9]]
        text = "\n".join(f"{name} — утром" for name in names)
        parsed = parse_treatment_text(text, catalog)
        assert parsed["ok"] is True
        assert len(parsed["drugs"]) >= 8
        blanks = chunk_drugs(parsed["drugs"], 2)
        assert len(blanks) >= 4
        payload = _patient(drugs=parsed["drugs"])
        for drug in payload["drugs"]:
            if not drug.get("dispenseQty"):
                drug["dispenseQty"] = ceil_to_dispense_step(30, drug.get("packaging") or "N30")
        normalized = normalize_prescription_payload(payload)
        result = validate_prescription_payload(normalized)
        assert result.ok, result.errors
        pdf_path = generate_prescription_pdf(normalized, tmp_path / "prints", DEFAULT_STAMP)
        assert pdf_path.exists()
        preview = build_preview_context(normalized, DEFAULT_STAMP, DEFAULT_UNP)
        assert len(preview["front_batches"]) >= 2

    def test_missing_qty_uses_pack_step_not_one(self):
        payload = _patient(drugs=[{
            "mnn": "Sertraline",
            "drug_form": "Tab.",
            "dosage": "50 мг",
            "packaging": "N28",
            "selectedScheme": "утром",
        }])
        normalized = normalize_prescription_payload(payload)
        qty = normalized["drugs"][0]["dispenseQty"]
        assert qty != 1
        assert is_valid_dispense_qty(qty, "N28")
        assert validate_prescription_payload(normalized).ok

    def test_float_qty_and_card_prefix_are_normalized(self):
        payload = _patient(
            card_number="№ 12543/26",
            drugs=[{
                "mnn": "Sertraline",
                "drug_form": "Tab.",
                "dosage": "50 мг",
                "packaging": "N28",
                "dispenseQty": "28.0",
                "selectedScheme": "утром",
            }],
        )
        normalized = normalize_prescription_payload(payload)
        assert normalized["card_number"] == "12543/26"
        assert normalized["drugs"][0]["dispenseQty"] == 28
        assert number_to_words_ru("28.0") == "двадцать восемь"
        assert validate_prescription_payload(normalized).ok

    def test_scheme_strips_leftover_bare_dose(self, tmp_path: Path):
        catalog = _repo(tmp_path).list_drugs()
        parsed = parse_treatment_text("по 1 таблетке утром эсциталопрам 10", catalog)
        assert parsed["ok"] is True
        assert parsed["drugs"][0]["mnn"] == "Escitalopram"
        assert parsed["drugs"][0]["dosage"] == "10 мг"
        assert parsed["drugs"][0]["selectedScheme"] == "по 1 утром"


class TestHistoryAndTemplates:
    def test_history_roundtrip_and_latest_wins(self, tmp_path: Path):
        repo = _repo(tmp_path)
        first = _patient(card_number="77", patient_name="Первый П.П.", drugs=[{"mnn": "Sertraline"}])
        second = _patient(card_number="77", patient_name="Второй В.В.", drugs=[{"mnn": "Escitalopram"}])
        repo.save_history_entry(first)
        repo.save_history_entry(second)
        loaded = repo.get_last_history_entry("77")
        assert loaded["patient_name"] == "Второй В.В."
        assert loaded["drugs"][0]["mnn"] == "Escitalopram"

    def test_history_requires_card(self, tmp_path: Path):
        repo = _repo(tmp_path)
        with pytest.raises(ValueError, match="Card number"):
            repo.save_history_entry({"patient_name": "Без карты", "drugs": []})

    def test_history_finds_card_with_numero_prefix(self, tmp_path: Path):
        repo = _repo(tmp_path)
        repo.save_history_entry(_patient(card_number="№12543/26", drugs=[{"mnn": "Sertraline"}]))
        loaded = repo.get_last_history_entry("12543/26")
        assert loaded is not None
        assert loaded["card_number"] == "12543/26"
        assert repo.get_last_history_entry("№ 12543/26")["drugs"][0]["mnn"] == "Sertraline"
        assert repo.get_last_history_entry("") is None
        assert repo.get_template("") is None

    def test_template_overwrite_and_delete(self, tmp_path: Path):
        repo = _repo(tmp_path)
        repo.save_template("Тревога", {"drugs": [{"mnn": "Sertraline", "russian_name": "Сертралин"}]})
        repo.save_template("Тревога", {"drugs": [{"mnn": "Escitalopram", "russian_name": "Эсциталопрам"}]})
        stored = repo.get_template("Тревога")
        assert stored["drugs"][0]["mnn"] == "Escitalopram"
        names = [item["name"] for item in repo.list_templates()]
        assert "Тревога" in names
        assert repo.delete_template("Тревога")["deleted"] is True
        assert repo.get_template("Тревога") is None


class TestCustomDrugAndDoctorChange:
    def test_custom_drug_survives_seed_sync_and_doctor_change(self, tmp_path: Path):
        repo = _repo(tmp_path)
        fake = TabletkaEnrichment(
            query="Новоприл",
            mnn_id="1",
            mnn_text="Новоприл",
            variants=[
                TabletkaVariant("Новик", "таблетки 10мг N30", "Tab.", "10 мг", "N30", 30),
            ],
            form_options=["Tab."],
            dosage_options=["10 мг"],
            form_dosage_map={"Tab.": ["10 мг"]},
            trade_names=["Новик"],
            default_form="Tab.",
            default_dosage="10 мг",
            default_packaging="N30",
            message="ok",
        )
        added = add_custom_drug_from_tabletka(repo, "Новоприл", enricher=lambda _q: fake)
        assert added["ok"] is True
        repo.sync_seed_catalog(replace=True)
        custom = next(item for item in repo.list_drugs() if item["mnn"] == "Novopril")
        assert custom["is_custom"] is True
        assert "Новик" in custom["trade_names"]

        settings = SettingsStore(tmp_path / "settings.json")
        settings.update_doctor_name("Старый")
        repo.save_history_entry(_patient(card_number="1", drugs=[{"mnn": "Novopril"}]))
        change_doctor(settings_store=settings, repository=repo, doctor_name="Новый")
        assert repo.count_history_entries() == 0
        assert any(item["mnn"] == "Novopril" and item["is_custom"] for item in repo.list_drugs())

    def test_cannot_delete_seed_drug(self, tmp_path: Path):
        repo = _repo(tmp_path)
        with pytest.raises(ValueError, match="добавленные вручную"):
            repo.delete_custom_drug("Sertraline")
        assert any(item["mnn"] == "Sertraline" for item in repo.list_drugs())

    def test_object_like_options_are_sanitized(self, tmp_path: Path):
        repo = _repo(tmp_path)
        repo.upsert_custom_drug({
            "mnn": "Objectinum",
            "russian_name": "Объектин",
            "form_options": [{"name": "Tab."}, "Caps."],
            "dosage_options": [{"dosage": "10 мг"}, "20 мг"],
            "trade_names": [{"trade_name": "Объект"}, "Чистый"],
            "scheme_options": [{"label": "утром"}, "вечером"],
        })
        drug = next(item for item in repo.list_drugs() if item["mnn"] == "Objectinum")
        assert all(isinstance(x, str) for x in drug["form_options"])
        assert "[object Object]" not in " ".join(drug["form_options"])
        assert "Caps." in drug["form_options"]
        assert "20 мг" in drug["dosage_options"]
        assert "Чистый" in drug["trade_names"]

    def test_object_like_schemes_are_rejected(self, tmp_path: Path):
        repo = _repo(tmp_path)
        saved = repo.save_drug_schemes("Sertraline", [{"label": "утром"}, "вечером", "[object Object]"])
        assert saved["scheme_options"] == ["утром", "вечером"]
        drug = next(item for item in repo.list_drugs() if item["mnn"] == "Sertraline")
        assert drug["scheme_options"] == ["утром", "вечером"]


class TestAvailabilityDailyCache:
    def test_lookup_by_trade_and_second_launch_skips_network(self, tmp_path: Path):
        calls: list[str] = []

        def checker(query, aliases=None):
            calls.append(query)
            return MinskAvailability(query, "good", "Есть", 12, [], "ok")

        store = DailyAvailabilityStore(tmp_path, checker=checker)
        drugs = _repo(tmp_path / "db").list_drugs()[:5]
        store.ensure_today(drugs)
        if store._thread:
            store._thread.join(timeout=3)
        assert calls
        first_count = len(calls)
        hit = store.lookup(drugs[0]["mnn"], drugs[0]["russian_name"], drugs[0].get("trade_names"))
        assert hit and hit["status"] == "good"
        store.ensure_today(drugs)
        if store._thread:
            store._thread.join(timeout=3)
        assert len(calls) == first_count


class TestPrintGeometryAndRp:
    def test_blanks_fit_a4_after_wider_margins(self):
        from reportlab.lib.units import mm

        assert PAGE_MARGIN_X * 2 + FORM_W * 2 == pytest.approx(A4_W)
        assert PAGE_MARGIN_Y * 2 + FORM_H * 2 == pytest.approx(A4_H)
        assert PAGE_MARGIN_X == pytest.approx(6 * mm)

    def test_duplex_mirrors_left_right(self):
        assert duplex_back_index(0) == 1
        assert duplex_back_index(1) == 0
        assert duplex_back_index(2) == 3
        assert duplex_back_index(3) == 2

    def test_rp_trade_mode_uses_trade_name(self):
        lines = format_rp_lines({
            "mode": "trade",
            "selectedTrade": "Ципралекс",
            "latin_name": "Escitalopramum",
            "dosage": "10 мг",
            "dispenseQty": 30,
            "drug_form": "Tab.",
            "selectedScheme": "утром",
        })
        assert lines[0].startswith("Ципралекс")
        assert "тридцать" in lines[1]
        assert lines[2] == "S. утром"

    def test_number_words_for_pack_steps(self):
        assert number_to_words_ru(14) == "четырнадцать"
        assert number_to_words_ru(98) == "девяносто восемь"
        assert number_to_words_ru(100) == "сто"


class TestUpdaterOverlaySafety:
    def test_overlay_never_replaces_internal_or_exe(self, tmp_path: Path):
        source = tmp_path / "src"
        root = tmp_path / "dst"
        source.mkdir()
        root.mkdir()
        (source / "_internal").mkdir()
        (source / "_internal" / "locked.dll").write_bytes(b"new")
        (source / "Recepty.exe").write_bytes(b"new-exe")
        (source / "VERSION").write_text("9.9.9\n", encoding="utf-8")
        (source / "backend").mkdir()
        (source / "backend" / "ok.py").write_text("ok\n", encoding="utf-8")
        (root / "_internal").mkdir()
        (root / "_internal" / "locked.dll").write_bytes(b"old")
        updated = _apply_frozen_overlay_from_source(source, root)
        assert "backend" in updated
        assert (root / "_internal" / "locked.dll").read_bytes() == b"old"
        assert not (root / "Recepty.exe").exists()
        assert "recepty.exe" in SKIP_REPLACE_NAMES
        assert "_internal" in SKIP_REPLACE_DIRS


class TestMnnKeyAndParseEdges:
    def test_build_mnn_key_latin_and_russian(self):
        assert build_mnn_key("Sertraline") == "Sertraline"
        assert build_mnn_key("сертралин") == "Sertralin"

    def test_unmatched_and_empty_parse(self, tmp_path: Path):
        catalog = _repo(tmp_path).list_drugs()
        empty = parse_treatment_text("   ", catalog)
        assert empty["ok"] is False
        unknown = parse_treatment_text("Несуществующийпрепарат 5 мг утром", catalog)
        assert unknown["ok"] is False or unknown["drugs"] == []
        assert unknown["unmatched"]
