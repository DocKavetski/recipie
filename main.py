import logging
import sys
import threading
from pathlib import Path


def _bootstrap_frozen_overrides() -> None:
    """Для portable: свежие backend/web рядом с exe перекрывают встроенные в сборку."""
    if not getattr(sys, "frozen", False):
        return
    root = Path(sys.executable).resolve().parent
    if (root / "backend").is_dir():
        sys.path.insert(0, str(root))


_bootstrap_frozen_overrides()

import eel

from backend.availability_cache import DailyAvailabilityStore
from backend.custom_drug_add import add_custom_drug_from_tabletka
from backend.db import DrugRepository
from backend.defaults import DEFAULT_DOCTOR_NAME, DEFAULT_STAMP, DEFAULT_UNP
from backend.doctor_change import change_doctor as change_doctor_service
from backend.doctor_change import clear_patient_data as clear_patient_data_service
from backend.pdf_gen import generate_prescription_pdf
from backend.print_preview import build_preview_context
from backend.runtime_control import build_restart_command, hard_exit, spawn_restart
from backend.settings import SettingsStore
from backend.seed_loader import load_archived_drugs
from backend.tabletka import search_tabletka
from backend.treatment_parse import parse_treatment_text
from backend.updater import apply_update, cleanup_update_artifacts, get_update_status, open_repo_in_browser
from backend.validate import normalize_prescription_payload, validate_prescription_payload
from backend.version import APP_VERSION, GITHUB_URL
from backend.printer import open_pdf


def resource_path(*parts: str) -> Path:
    if getattr(sys, "frozen", False):
        external = Path(sys.executable).resolve().parent.joinpath(*parts)
        if external.exists():
            return external
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base_path.joinpath(*parts)


def writable_path(*parts: str) -> Path:
    base_path = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    return base_path.joinpath(*parts)


REPOSITORY = DrugRepository(writable_path("data") / "app.db")
SETTINGS = SettingsStore(writable_path("data") / "settings.json")
AVAILABILITY = DailyAvailabilityStore(writable_path("data"))


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


def _restart_process_after_response(delay_sec: float = 0.35) -> None:
    def _do_restart() -> None:
        command = build_restart_command(
            frozen=getattr(sys, "frozen", False),
            executable=sys.executable,
            script_path=str(Path(__file__).resolve()),
        )
        spawn_restart(command, cwd=str(writable_path()))
        hard_exit(0)

    threading.Timer(delay_sec, _do_restart).start()


@eel.expose
def restart_application():
    try:
        _restart_process_after_response()
        return {"ok": True, "message": "Приложение перезапускается…"}
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).exception("restart failed")
        return {"ok": False, "message": str(exc)}


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
def get_archived_drugs():
    return load_archived_drugs()


@eel.expose
def search_catalog_drugs(query):
    return REPOSITORY.search_drugs(query)


@eel.expose
def parse_treatment(text):
    return parse_treatment_text(text or "", REPOSITORY.list_drugs())


@eel.expose
def list_drug_schemes():
    return REPOSITORY.list_drugs()


@eel.expose
def save_drug_schemes(mnn, scheme_options):
    schemes = scheme_options if isinstance(scheme_options, list) else []
    return REPOSITORY.save_drug_schemes(mnn or "", schemes)


@eel.expose
def reset_drug_schemes(mnn):
    return REPOSITORY.reset_drug_schemes(mnn or "")


@eel.expose
def get_app_settings():
    return SETTINGS.load()


@eel.expose
def save_doctor_name(doctor_name):
    return SETTINGS.update_doctor_name(doctor_name)


@eel.expose
def change_doctor(doctor_name):
    """Смена врача: сохраняет ФИО и очищает только историю пациентов.

    Каталог препаратов, шаблоны и пользовательские схемы не затрагиваются.
    """
    return change_doctor_service(
        settings_store=SETTINGS,
        repository=REPOSITORY,
        doctor_name=doctor_name,
    )


@eel.expose
def clear_patient_data():
    """Очистка истории пациентов без затрагивания каталога препаратов."""
    return clear_patient_data_service(settings_store=SETTINGS, repository=REPOSITORY)


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
def delete_template(name):
    return REPOSITORY.delete_template(name or "")


@eel.expose
def upsert_custom_drug(payload):
    return REPOSITORY.upsert_custom_drug(payload or {})


@eel.expose
def add_drug_from_tabletka(query):
    """Добавить препарат в каталог по МНН: данные форм/доз/торговых с tabletka.by."""
    return add_custom_drug_from_tabletka(REPOSITORY, query or "")


@eel.expose
def delete_custom_drug(mnn):
    return REPOSITORY.delete_custom_drug(mnn or "")


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
def get_daily_availability():
    return AVAILABILITY.snapshot()


@eel.expose
def ensure_daily_availability(force=False):
    """Один опрос tabletka.by в сутки — при первом запуске дня."""
    return AVAILABILITY.ensure_today(REPOSITORY.list_drugs(), force=bool(force))


@eel.expose
def check_drug_availability(query, aliases=None):
    alias_list = aliases if isinstance(aliases, list) else []
    cached = AVAILABILITY.lookup(query, alias_list)
    if cached:
        return {
            **cached,
            "query": query,
            "cached": True,
        }
    return {
        "query": query or "",
        "status": "unknown",
        "label": "—",
        "pharmacies_minsk": 0,
        "offers": [],
        "cached": True,
        "message": "Наличие проверяется раз в день при первом запуске.",
    }


@eel.expose
def refresh_catalog_availability(limit=20):
    """Возвращает дневной кэш; limit оставлен для совместимости."""
    _ = limit
    snapshot = AVAILABILITY.snapshot()
    if not snapshot.get("checking") and (
        not snapshot.get("fresh")
        or not any(str(row.get("status") or "") in {"good", "low", "none"} for row in (snapshot.get("rows") or []))
    ):
        snapshot = AVAILABILITY.ensure_today(REPOSITORY.list_drugs())
    return {
        "ok": True,
        "city": "Минск",
        "date": snapshot.get("date"),
        "fresh": snapshot.get("fresh"),
        "checking": snapshot.get("checking"),
        "rows": snapshot.get("rows") or [],
        "message": snapshot.get("message"),
    }


@eel.expose
def open_pdf_for_print(pdf_path):
    try:
        path = open_pdf(pdf_path)
        return {"ok": True, "path": path}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "message": str(exc)}


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
        "preview": build_preview_context(normalized, DEFAULT_STAMP, DEFAULT_UNP),
    }


def main() -> None:
    setup_logging()
    cleanup_update_artifacts()
    REPOSITORY.initialize()
    SETTINGS.load()
    AVAILABILITY.ensure_today(REPOSITORY.list_drugs())
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
