"""Дополнительные Eel API, которые можно подхватить из overlay без пересборки exe.

Вызывается из DrugRepository.initialize(), чтобы portable-обновление
backend/ рядом с exe регистрировало новые методы даже со старым main.py внутри сборки.
"""

from __future__ import annotations

import logging
from typing import Any

LOGGER = logging.getLogger(__name__)
_REGISTERED = False


def register_repository_exposes(repository: Any) -> None:
    """Регистрирует API, завязанные на каталог препаратов."""
    global _REGISTERED
    if _REGISTERED:
        return

    try:
        import eel
    except Exception:  # noqa: BLE001
        return

    from backend.seed_loader import load_archived_drugs
    from backend.treatment_parse import parse_treatment_text

    @eel.expose
    def parse_treatment(text):
        return parse_treatment_text(text or "", repository.list_drugs())

    @eel.expose
    def get_archived_drugs():
        return load_archived_drugs()

    _REGISTERED = True
    LOGGER.info("Registered runtime Eel exposes: parse_treatment, get_archived_drugs")
