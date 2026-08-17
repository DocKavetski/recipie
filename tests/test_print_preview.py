from __future__ import annotations

from backend.print_preview import build_preview_context


def test_build_preview_context_uses_shared_rp_formatting():
    payload = {
        "patient_name": "Иванов Иван Иванович",
        "birth_date": "1980-01-02",
        "doctor_name": "Кавецкий А.С.",
        "drugs": [
            {
                "mode": "mnn",
                "mnn": "Escitalopram",
                "russian_name": "Эсциталопрам",
                "latin_name": "Escitalopramum",
                "drug_form": "Tab.",
                "dosage": "10 мг",
                "dispenseQty": 30,
                "selectedScheme": "1 таб. утром",
            }
        ],
    }

    preview = build_preview_context(payload, "Строка 1\nСтрока 2", "123456789")

    assert preview["stamp_lines"] == ["Строка 1", "Строка 2"]
    assert preview["unp"] == "123456789"
    assert preview["patient_name"] == "Иванов И.И."
    assert preview["birth_date"] == "02.01.1980"
    assert preview["front_batches"][0][0][1] is None
    assert preview["front_batches"][0][0][0]["rp_lines"] == [
        "Escitaloprami 10 мг",
        "D.t.d. № 30 (тридцать) in tab.",
        "S. 1 таб. утром",
    ]
    assert preview["back_filled_batches"][0] == [True, False, False, False]
    assert preview["duplex_back_slot"] == [1, 0, 3, 2]


def test_preview_keeps_patronymic_initial_r():
    preview = build_preview_context(
        {
            "patient_name": "Иванов Иван Романович",
            "birth_date": "12.05.1977",
            "doctor_name": "Кавецкий А.С.",
            "drugs": [],
        },
        "Строка 1",
        "123",
    )
    assert preview["patient_name"] == "Иванов И.Р."

    again = build_preview_context(
        {
            "patient_name": preview["patient_name"],
            "birth_date": "12.05.1977",
            "doctor_name": "Кавецкий А.С.",
            "drugs": [],
        },
        "Строка 1",
        "123",
    )
    assert again["patient_name"] == "Иванов И.Р."
