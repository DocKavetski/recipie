import logging
import sys
from pathlib import Path

import eel

from backend.db import DrugRepository
from backend.pdf_gen import generate_prescription_pdf
from backend.settings import SettingsStore
from backend.tabletka import availability_to_dict, check_availability_minsk, search_tabletka
from backend.updater import apply_update, get_update_status, open_repo_in_browser
from backend.validate import normalize_prescription_payload, validate_prescription_payload
from backend.version import APP_VERSION, GITHUB_URL


DEFAULT_STAMP = (
    "ООО «Центр здорового сна»\n"
    "220012, г. Минск, пр-т Независимости,\n"
    "72А, пом. 1Н. Тел. 017 299-99-92,\n"
    "029 311-88-44, 033 311-01-44.\n"
    "УНП 191896187\n"
    "р/с BY94 PJCB 30120288531000000933\n"
    "БИК PJCBBY2X в ОАО\n"
    "«Приор банк», код 749"
)
DEFAULT_UNP = "191896187"
REPOSITORY = DrugRepository(Path(__file__).resolve().parent / "data" / "app.db")
SETTINGS = SettingsStore(Path(__file__).resolve().parent / "data" / "settings.json")


def resource_path(*parts: str) -> Path:
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base_path.joinpath(*parts)


def writable_path(*parts: str) -> Path:
    base_path = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    return base_path.joinpath(*parts)


def setup_logging() -> None:
    log_file = writable_path("app.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    logging.getLogger(__name__).info("Application starting")


@eel.expose
def ping():
    return {"ok": True, "message": "Eel bridge is active", "version": APP_VERSION}


@eel.expose
def get_app_version_info():
    return {
        "version": APP_VERSION,
        "repo_url": GITHUB_URL,
    }


@eel.expose
def check_app_updates():
    return get_update_status()


@eel.expose
def update_application():
    result = apply_update()
    if result.get("ok") and result.get("updated"):
        try:
            REPOSITORY.sync_seed_catalog(replace=True)
            result["catalog_synced"] = True
        except Exception as exc:  # noqa: BLE001
            result["catalog_synced"] = False
            result["catalog_error"] = str(exc)
    return result


@eel.expose
def open_github_repo():
    return open_repo_in_browser()


@eel.expose
def get_default_stamp():
    return DEFAULT_STAMP


@eel.expose
def get_catalog_drugs():
    return REPOSITORY.list_drugs()


@eel.expose
def search_catalog_drugs(query):
    return REPOSITORY.search_drugs(query)


@eel.expose
def get_app_settings():
    return SETTINGS.load()


@eel.expose
def save_doctor_name(doctor_name):
    return SETTINGS.update_doctor_name(doctor_name)


@eel.expose
def save_autosave(payload):
    return SETTINGS.save_autosave(payload or {})


@eel.expose
def load_autosave():
    return SETTINGS.load_autosave()


@eel.expose
def clear_autosave():
    return SETTINGS.clear_autosave()


@eel.expose
def save_history_entry(payload):
    return REPOSITORY.save_history_entry(payload or {})


@eel.expose
def load_last_history_entry(card_number):
    return REPOSITORY.get_last_history_entry(card_number or "")


@eel.expose
def save_template(name, payload):
    return REPOSITORY.save_template(name or "", payload or {})


@eel.expose
def list_templates():
    return REPOSITORY.list_templates()


@eel.expose
def load_template(name):
    return REPOSITORY.get_template(name or "")


@eel.expose
def search_tabletka_drugs(query):
    offers = search_tabletka(query or "")
    return [
        {
            "name": offer.name,
            "form": offer.form,
            "pharmacies_total": offer.pharmacies_total,
            "result_id": offer.result_id,
            "url": offer.url,
        }
        for offer in offers
    ]


@eel.expose
def check_drug_availability(query):
    return availability_to_dict(check_availability_minsk(query or ""))


@eel.expose
def refresh_catalog_availability(limit=20):
    """Проверка наличия в Минске для первых препаратов каталога."""
    drugs = REPOSITORY.list_drugs()[: max(1, min(int(limit or 20), 40))]
    rows = []
    for drug in drugs:
        result = check_availability_minsk(drug["russian_name"])
        rows.append(
            {
                "mnn": drug["mnn"],
                "russian_name": drug["russian_name"],
                "status": result.status,
                "label": result.label,
                "pharmacies_minsk": result.pharmacies_minsk,
                "message": result.message,
            }
        )
    return {"ok": True, "city": "Минск", "rows": rows}


@eel.expose
def validate_prescription(payload):
    result = validate_prescription_payload(payload or {})
    return result.as_dict()


@eel.expose
def print_prescription(payload):
    normalized = normalize_prescription_payload(payload or {})
    result = validate_prescription_payload(normalized)
    if not result.ok:
        return {"ok": False, "errors": result.errors, "warnings": result.warnings}

    pdf_path = generate_prescription_pdf(
        normalized,
        writable_path("prints"),
        DEFAULT_STAMP,
    )
    return {
        "ok": True,
        "pdf_path": str(pdf_path),
        "warnings": result.warnings,
        "payload": normalized,
    }


def main() -> None:
    setup_logging()
    REPOSITORY.initialize()
    SETTINGS.load()
    web_dir = resource_path("web")
    eel.init(str(web_dir))
    eel.start(
        "index.html",
        size=(1480, 960),
        position=(80, 40),
        disable_cache=True,
    )


if __name__ == "__main__":
    main()
