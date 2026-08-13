"""Смена врача с очисткой только пациентских данных."""

from __future__ import annotations

from typing import Any


def change_doctor(
    *,
    settings_store: Any,
    repository: Any,
    doctor_name: str,
) -> dict[str, Any]:
    previous = str((settings_store.load() or {}).get("doctor_name") or "").strip()
    next_name = str(doctor_name or "").strip()
    settings = settings_store.update_doctor_name(next_name)
    cleared = {"deleted": 0, "catalog_preserved": True}
    autosave_cleared = False
    if next_name and next_name != previous:
        cleared = repository.clear_patient_history()
        settings_store.clear_autosave()
        autosave_cleared = True
    return {
        "ok": True,
        "doctor_name": settings.get("doctor_name"),
        "previous_doctor_name": previous,
        "patient_history_cleared": bool(next_name and next_name != previous),
        "history_deleted": cleared.get("deleted", 0),
        "autosave_cleared": autosave_cleared,
        "catalog_preserved": True,
    }


def clear_patient_data(*, settings_store: Any, repository: Any) -> dict[str, Any]:
    cleared = repository.clear_patient_history()
    settings_store.clear_autosave()
    return {
        "ok": True,
        "history_deleted": cleared.get("deleted", 0),
        "autosave_cleared": True,
        "catalog_preserved": True,
    }
