"""Дополнительные Eel API, которые можно подхватить из overlay без пересборки exe.

Вызывается из DrugRepository.initialize(), чтобы portable-обновление
backend/ рядом с exe регистрировало новые методы даже со старым main.py внутри сборки.
"""

from __future__ import annotations

import logging
from typing import Any

LOGGER = logging.getLogger(__name__)
_REGISTERED = False
_AVAILABILITY_REGISTERED = False


def register_repository_exposes(repository: Any) -> None:
    """Регистрирует API, завязанные на каталог препаратов."""
    global _REGISTERED
    if _REGISTERED:
        register_availability_exposes(repository)
        return

    try:
        import eel
    except Exception:  # noqa: BLE001
        return

    from backend.custom_drug_add import add_custom_drug_from_tabletka
    from backend.seed_loader import load_archived_drugs
    from backend.treatment_parse import parse_treatment_text

    @eel.expose
    def parse_treatment(text):
        return parse_treatment_text(text or "", repository.list_drugs())

    @eel.expose
    def get_archived_drugs():
        return load_archived_drugs()

    @eel.expose
    def upsert_custom_drug(payload):
        return repository.upsert_custom_drug(payload or {})

    @eel.expose
    def add_drug_from_tabletka(query):
        return add_custom_drug_from_tabletka(repository, query or "")

    @eel.expose
    def delete_custom_drug(mnn):
        return repository.delete_custom_drug(mnn or "")

    _REGISTERED = True
    LOGGER.info(
        "Registered runtime Eel exposes: parse_treatment, get_archived_drugs, "
        "upsert_custom_drug, add_drug_from_tabletka, delete_custom_drug"
    )
    register_availability_exposes(repository)


def register_availability_exposes(repository: Any) -> None:
    """Регистрирует API наличия — важно для старого exe без обновлённого main.py."""
    global _AVAILABILITY_REGISTERED
    if _AVAILABILITY_REGISTERED:
        return

    try:
        import eel
    except Exception:  # noqa: BLE001
        return

    from backend.availability_cache import shared_store

    try:
        store = shared_store(repository.db_path.parent)
    except Exception:  # noqa: BLE001
        LOGGER.debug("availability store unavailable", exc_info=True)
        return

    @eel.expose
    def get_daily_availability():
        return store.snapshot()

    @eel.expose
    def ensure_daily_availability(force=False):
        return store.ensure_today(repository.list_drugs(), force=bool(force))

    @eel.expose
    def refresh_catalog_availability(limit=20, force=False):
        _ = limit
        if force:
            snapshot = store.ensure_today(repository.list_drugs(), force=True)
        else:
            snapshot = store.snapshot()
            if not snapshot.get("checking") and (
                not snapshot.get("fresh")
                or not snapshot.get("useful")
            ):
                snapshot = store.ensure_today(repository.list_drugs())
        return {
            "ok": True,
            "city": "Минск",
            "date": snapshot.get("date"),
            "fresh": snapshot.get("fresh"),
            "checking": snapshot.get("checking"),
            "useful": snapshot.get("useful"),
            "rows": snapshot.get("rows") or [],
            "by_key": snapshot.get("by_key") or {},
            "progress": snapshot.get("progress"),
            "message": snapshot.get("message"),
        }

    _AVAILABILITY_REGISTERED = True
    LOGGER.info(
        "Registered runtime availability exposes: get_daily_availability, "
        "ensure_daily_availability, refresh_catalog_availability"
    )
