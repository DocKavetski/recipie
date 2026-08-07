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
