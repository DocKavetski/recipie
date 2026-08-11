import json
from pathlib import Path
from typing import Any

from backend.defaults import DEFAULT_DOCTOR_NAME


DEFAULT_SETTINGS = {
    "doctor_name": DEFAULT_DOCTOR_NAME,
}


class SettingsStore:
    def __init__(self, settings_path: Path):
        self.settings_path = Path(settings_path)
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.autosave_path = self.settings_path.parent / "autosave.json"

    def load(self) -> dict[str, Any]:
        if not self.settings_path.exists():
            self.save(DEFAULT_SETTINGS)
            return dict(DEFAULT_SETTINGS)

        try:
            loaded = json.loads(self.settings_path.read_text(encoding="utf-8"))
            merged = {**DEFAULT_SETTINGS, **loaded}
            # Если локально имя пустое — подставляем встроенное
            if not str(merged.get("doctor_name") or "").strip():
                merged["doctor_name"] = DEFAULT_DOCTOR_NAME
            return merged
        except json.JSONDecodeError:
            self.save(DEFAULT_SETTINGS)
            return dict(DEFAULT_SETTINGS)

    def save(self, settings: dict[str, Any]) -> dict[str, Any]:
        merged = {**DEFAULT_SETTINGS, **settings}
        if not str(merged.get("doctor_name") or "").strip():
            merged["doctor_name"] = DEFAULT_DOCTOR_NAME
        self.settings_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
        return merged

    def update_doctor_name(self, doctor_name: str) -> dict[str, Any]:
        settings = self.load()
        settings["doctor_name"] = doctor_name.strip() or DEFAULT_DOCTOR_NAME
        return self.save(settings)

    def load_autosave(self) -> dict[str, Any]:
        if not self.autosave_path.exists():
            return {}

        try:
            return json.loads(self.autosave_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def save_autosave(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.autosave_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"ok": True}

    def clear_autosave(self) -> dict[str, Any]:
        if self.autosave_path.exists():
            self.autosave_path.unlink()
        return {"ok": True}
