"""Тесты парсинга пациента, числительных, валидации и латыни."""

from __future__ import annotations

from datetime import date

import pytest

from backend.latin_gen import generate_genitive
from backend.numbers_ru import extract_default_dispense_qty, number_to_words_ru
from backend.patient_parse import (
    calculate_age,
    compose_patient_smart_value,
    format_name_with_initials,
    normalize_birth_date,
    parse_birth_date,
    parse_patient_smart_input,
)
from backend.validate import (
    chunk_drugs,
    duplex_back_index,
    normalize_prescription_payload,
    validate_prescription_payload,
)
from backend.rx_format import form_in_phrase, format_rp_lines


class TestNormalizeBirthDate:
    def test_iso(self):
        assert normalize_birth_date("1983-11-27") == "27.11.1983"

    def test_dotted(self):
        assert normalize_birth_date("27.11.1983") == "27.11.1983"

    def test_slashes(self):
        assert normalize_birth_date("27/11/1983") == "27.11.1983"

    def test_single_digit_day_month(self):
        assert normalize_birth_date("7.8.2000") == "07.08.2000"
        assert normalize_birth_date("27.8.2000") == "27.08.2000"

    def test_empty(self):
        assert normalize_birth_date("") == ""
        assert normalize_birth_date(None) == ""


class TestParseBirthDate:
    def test_valid(self):
        assert parse_birth_date("27.11.1983") == date(1983, 11, 27)

    def test_invalid_calendar(self):
        assert parse_birth_date("32.13.2000") is None
        assert parse_birth_date("31.02.2000") is None

    def test_age(self):
        assert calculate_age("28.07.2000", today=date(2026, 7, 28)) == 26
        assert calculate_age("29.07.2000", today=date(2026, 7, 28)) == 25


class TestPatientName:
    def test_full_fio_to_initials(self):
        assert format_name_with_initials("Иванов Петр Степанович") == "Иванов П.С."

    def test_lowercase_name_parts(self):
        assert format_name_with_initials("Иванов петр семенович") == "Иванов П.С."

    def test_already_initials(self):
        assert format_name_with_initials("Дубяго К.А.") == "Дубяго К.А."

    def test_junk_in_parentheses(self):
        assert format_name_with_initials("Иванов Петр Степановис (орпоп") == "Иванов П.С."

    def test_hyphenated_surname(self):
        assert format_name_with_initials("Салтыков-Щедрин Михаил Евграфович") == "Салтыков-Щедрин М.Е."

    def test_only_surname(self):
        assert format_name_with_initials("Иванов") == "Иванов"

    def test_patronymic_initial_r_kept(self):
        assert format_name_with_initials("Иванов Иван Романович") == "Иванов И.Р."
        assert format_name_with_initials("Иванов И.Р.") == "Иванов И.Р."
        assert format_name_with_initials("Иванов И. Р.") == "Иванов И.Р."
        assert format_name_with_initials("Сидоров С.Р.") == "Сидоров С.Р."

    def test_gr_initials_not_treated_as_birth_year(self):
        assert format_name_with_initials("Иванов Г.Р.") == "Иванов Г.Р."
        assert format_name_with_initials("Иванов Григорий Романович") == "Иванов Г.Р."

    def test_format_initials_is_idempotent(self):
        names = [
            "Иванов Иван Иванович",
            "Иванов Иван Романович",
            "Иванов Григорий Романович",
            "Дубяго К.А.",
            "Салтыков-Щедрин Михаил Евграфович",
        ]
        for name in names:
            once = format_name_with_initials(name)
            assert format_name_with_initials(once) == once


class TestParsePatientSmartInput:
    def test_basic(self):
        parsed = parse_patient_smart_input("Дубяго К.А. 27.11.1983")
        assert parsed.patient_name == "Дубяго К.А."
        assert parsed.birth_date == "27.11.1983"

    def test_date_first(self):
        parsed = parse_patient_smart_input("27.08.2000 Иванов Петр Семенович")
        assert parsed.patient_name == "Иванов П.С."
        assert parsed.birth_date == "27.08.2000"

    def test_lowercase_and_spaces(self):
        parsed = parse_patient_smart_input("Иванов петр семенович 27.08.2000")
        assert parsed.patient_name == "Иванов П.С."
        assert parsed.birth_date == "27.08.2000"

    def test_junk_text_ignored(self):
        parsed = parse_patient_smart_input("Иванов Петр Степановис (орпоп 27.08.2000")
        assert parsed.patient_name == "Иванов П.С."
        assert parsed.birth_date == "27.08.2000"

    def test_iso_date(self):
        parsed = parse_patient_smart_input("Иванов Иван Иванович 1983-11-27")
        assert parsed.patient_name == "Иванов И.И."
        assert parsed.birth_date == "27.11.1983"

    def test_single_digit_date(self):
        parsed = parse_patient_smart_input("Иванов Пётр 7.8.2000")
        assert parsed.birth_date == "07.08.2000"
        assert parsed.patient_name == "Иванов П."

    def test_comma_and_gr(self):
        parsed = parse_patient_smart_input("Иванов, Петр, г.р. 27.08.2000")
        assert parsed.patient_name == "Иванов П."
        assert parsed.birth_date == "27.08.2000"

    def test_romanovich_initials_with_date(self):
        parsed = parse_patient_smart_input("Иванов Иван Романович 12.05.1977")
        assert parsed.patient_name == "Иванов И.Р."
        assert parsed.birth_date == "12.05.1977"
        assert format_name_with_initials(parsed.patient_name) == "Иванов И.Р."

    def test_already_formatted_r_patronymic_with_date(self):
        parsed = parse_patient_smart_input("Иванов И.Р. 12.05.1977")
        assert parsed.patient_name == "Иванов И.Р."
        assert parsed.birth_date == "12.05.1977"

    def test_compose_roundtrip(self):
        value = compose_patient_smart_value("Иванов П.С.", "27.08.2000", "112567")
        assert value == "Иванов П.С. 27.08.2000 112567"
        parsed = parse_patient_smart_input(value)
        assert parsed.patient_name == "Иванов П.С."
        assert parsed.birth_date == "27.08.2000"
        assert parsed.card_number == "112567"

    def test_age_in_result(self):
        parsed = parse_patient_smart_input("Иванов И.И. 28.07.2000", today=date(2026, 7, 28))
        assert parsed.age == 26

    def test_card_number_plain(self):
        parsed = parse_patient_smart_input("Махсма В.В. 14.03.1998 112567")
        assert parsed.patient_name == "Махсма В.В."
        assert parsed.birth_date == "14.03.1998"
        assert parsed.card_number == "112567"

    def test_card_number_with_slash(self):
        parsed = parse_patient_smart_input("Иванов П.С. 12543/26 27.08.2000")
        assert parsed.patient_name == "Иванов П.С."
        assert parsed.birth_date == "27.08.2000"
        assert parsed.card_number == "12543/26"

    def test_card_number_with_numero_sign(self):
        parsed = parse_patient_smart_input("Иванов И.И. 01.01.1990 № 998877")
        assert parsed.card_number == "998877"
        assert parsed.patient_name == "Иванов И.И."


class TestNumbersRu:
    def test_basic(self):
        assert number_to_words_ru(1) == "один"
        assert number_to_words_ru(30) == "тридцать"
        assert number_to_words_ru(21) == "двадцать один"
        assert number_to_words_ru(100) == "сто"
        assert number_to_words_ru(305) == "триста пять"

    def test_packaging_qty(self):
        assert extract_default_dispense_qty("30 таб.") == 30
        assert extract_default_dispense_qty("без числа") == 1


class TestLatinGen:
    def test_common_endings(self):
        assert generate_genitive("Escitalopramum") == "Escitaloprami"
        assert generate_genitive("Quetiapinum") == "Quetiapini"
        assert generate_genitive("Belladonna") == "Belladonnae"
        assert generate_genitive("Codeinis") == "Codeinis"
        assert generate_genitive("") == ""


class TestValidate:
    def _payload(self, **overrides):
        base = {
            "card_number": "12543/26",
            "patient_name": "Иванов П.С.",
            "birth_date": "27.08.2000",
            "doctor_name": "Кавецкий А.С.",
            "drugs": [
                {
                    "mnn": "Escitalopram",
                    "drug_form": "Tab.",
                    "dosage": "10 мг",
                    "dispenseQty": 30,
                    "selectedScheme": "по 1 таблетке утром",
                }
            ],
        }
        base.update(overrides)
        return base

    def test_ok(self):
        result = validate_prescription_payload(self._payload())
        assert result.ok
        assert result.errors == []

    def test_missing_patient(self):
        result = validate_prescription_payload(self._payload(patient_name=""))
        assert not result.ok
        assert any("ФИО" in error for error in result.errors)

    def test_missing_birth(self):
        result = validate_prescription_payload(self._payload(birth_date=""))
        assert not result.ok

    def test_invalid_birth(self):
        result = validate_prescription_payload(self._payload(birth_date="32.13.2000"))
        assert not result.ok

    def test_missing_doctor(self):
        result = validate_prescription_payload(self._payload(doctor_name=""))
        assert not result.ok

    def test_missing_drugs(self):
        result = validate_prescription_payload(self._payload(drugs=[]))
        assert not result.ok

    def test_warnings_for_scheme(self):
        drugs = [
            {
                "mnn": "Escitalopram",
                "drug_form": "Tab.",
                "dosage": "10 мг",
                "dispenseQty": 30,
                "selectedScheme": "",
            }
        ]
        result = validate_prescription_payload(self._payload(drugs=drugs))
        assert result.ok
        assert result.warnings

    def test_warnings_for_dispense_step_by_packaging(self):
        drugs = [
            {
                "mnn": "Escitalopram",
                "drug_form": "Tab.",
                "dosage": "10 мг",
                "packaging": "N28",
                "dispenseQty": 20,
                "selectedScheme": "по 1 таблетке утром",
            }
        ]
        result = validate_prescription_payload(self._payload(drugs=drugs))
        assert not result.ok
        assert any("кратно 14" in error for error in result.errors)

    def test_errors_for_dispense_step_by_packaging_50(self):
        drugs = [
            {
                "mnn": "Escitalopram",
                "drug_form": "Tab.",
                "dosage": "10 мг",
                "packaging": "N50",
                "dispenseQty": 93,
                "selectedScheme": "по 1 таблетке утром",
            }
        ]
        result = validate_prescription_payload(self._payload(drugs=drugs))
        assert not result.ok
        assert any("кратно 10" in error for error in result.errors)

    def test_normalize_filters_empty_drugs(self):
        payload = self._payload(drugs=[{"mnn": ""}, {"mnn": "X", "dispenseQty": None}])
        normalized = normalize_prescription_payload(payload)
        assert len(normalized["drugs"]) == 1
        assert normalized["drugs"][0]["dispenseQty"] == 1

    def test_require_card(self):
        result = validate_prescription_payload(self._payload(card_number=""), require_card=True)
        assert not result.ok


class TestChunkAndDuplex:
    def test_chunk(self):
        drugs = [{"mnn": "a"}, {"mnn": "b"}, {"mnn": "c"}]
        chunks = chunk_drugs(drugs, 2)
        assert chunks == [[{"mnn": "a"}, {"mnn": "b"}], [{"mnn": "c"}]]

    def test_duplex_mirror(self):
        assert duplex_back_index(0) == 1
        assert duplex_back_index(1) == 0
        assert duplex_back_index(2) == 3
        assert duplex_back_index(3) == 2


class TestRpFormat:
    def test_form_in_phrase(self):
        assert form_in_phrase("Tab.") == "in tab."
        assert form_in_phrase("Caps.") == "in caps."
        assert form_in_phrase("Sol.") == "in sol."
        assert form_in_phrase("") == "in tab."

    def test_format_rp_lines_mnn(self):
        lines = format_rp_lines(
            {
                "mode": "mnn",
                "latin_name": "Escitalopramum",
                "dosage": "10 мг",
                "drug_form": "Tab.",
                "dispenseQty": 30,
                "selectedScheme": "по 1 таблетке утром",
            }
        )
        assert lines[0] == "Escitaloprami 10 мг"
        assert lines[1].startswith("D.t.d. № 30 (")
        assert lines[1].endswith("in tab.")
        assert lines[2] == "S. по 1 таблетке утром"

    def test_format_rp_lines_caps_trade(self):
        lines = format_rp_lines(
            {
                "mode": "trade",
                "selectedTrade": "Fluoxetine-Teva",
                "dosage": "20 мг",
                "drug_form": "Caps.",
                "dispenseQty": 28,
                "selectedScheme": "по 1 капсуле утром",
            }
        )
        assert lines[0] == "Fluoxetine-Teva 20 мг"
        assert "in caps." in lines[1]
        assert lines[2] == "S. по 1 капсуле утром"


class TestPrintGeometry:
    """Лицевая и оборотная должны делить одну геометрию бланка на A4."""

    def test_sheet_fits_a4_with_equal_cut_margins(self):
        from reportlab.lib.units import mm

        from backend.print_layout import (
            A4_H,
            A4_W,
            FORM_H,
            FORM_W,
            GUTTER_X,
            GUTTER_Y,
            PAGE_MARGIN_X,
            PAGE_MARGIN_Y,
        )

        assert PAGE_MARGIN_X * 2 + FORM_W * 2 + GUTTER_X == pytest.approx(A4_W)
        assert PAGE_MARGIN_Y * 2 + FORM_H * 2 + GUTTER_Y == pytest.approx(A4_H)
        assert FORM_W == pytest.approx(99 * mm)
        assert FORM_H == pytest.approx(143.5 * mm)
        assert PAGE_MARGIN_X == pytest.approx(6 * mm)
        assert PAGE_MARGIN_Y == pytest.approx(5 * mm)

    def test_front_back_content_boxes_register_on_long_edge_duplex(self):
        from backend.print_layout import A4_W, blank_origins, content_box
        from backend.validate import duplex_back_index

        origins = blank_origins()
        for front_idx in range(4):
            ox, oy = origins[front_idx]
            front_left, front_bottom, fw, fh = content_box(ox, oy)
            front_right = front_left + fw

            bx, by = origins[duplex_back_index(front_idx)]
            back_left, back_bottom, bw, bh = content_box(bx, by)
            back_right = back_left + bw

            assert A4_W - back_right == pytest.approx(front_left)
            assert A4_W - back_left == pytest.approx(front_right)
            assert back_bottom == pytest.approx(front_bottom)
            assert back_bottom + bh == pytest.approx(front_bottom + fh)


class TestPdfSmoke:
    def test_generate_pdf(self, tmp_path):
        from backend.pdf_gen import generate_prescription_pdf

        payload = {
            "patient_name": "Иванов П.С.",
            "birth_date": "27.08.2000",
            "doctor_name": "Кавецкий А.С.",
            "drugs": [
                {
                    "mnn": "Escitalopram",
                    "latin_name": "Escitalopramum",
                    "drug_form": "Tab.",
                    "dosage": "10 мг",
                    "dispenseQty": 30,
                    "selectedScheme": "по 1 таблетке утром",
                    "mode": "mnn",
                }
            ],
        }
        stamp = "ООО Тест\nУНП 1"
        path = generate_prescription_pdf(payload, tmp_path, stamp)
        assert path.exists()
        assert path.stat().st_size > 1000

    def test_pdf_keeps_patronymic_initial_r(self, tmp_path):
        from pypdf import PdfReader

        from backend.pdf_gen import generate_prescription_pdf

        payload = {
            "patient_name": "Иванов Иван Романович",
            "birth_date": "12.05.1977",
            "doctor_name": "Кавецкий А.С.",
            "drugs": [
                {
                    "mnn": "Escitalopram",
                    "latin_name": "Escitalopramum",
                    "drug_form": "Tab.",
                    "dosage": "10 мг",
                    "dispenseQty": 30,
                    "selectedScheme": "по 1 таблетке утром",
                    "mode": "mnn",
                }
            ],
        }
        path = generate_prescription_pdf(payload, tmp_path, "ООО Тест")
        text = "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
        compact = text.replace(" ", "").replace("\n", "")
        assert "ИвановИ.Р." in compact
