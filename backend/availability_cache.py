"""Кэш наличия в Минске: один опрос tabletka.by в сутки при первом запуске."""

from __future__ import annotations

import json
import logging
import threading
from datetime import date
from pathlib import Path
from typing import Any, Callable

from backend.tabletka import availability_to_dict, check_availability_minsk

LOGGER = logging.getLogger(__name__)

CACHE_NAME = "availability_cache.json"


def today_key() -> str:
    return date.today().isoformat()


def cache_path(data_dir: Path) -> Path:
    return Path(data_dir) / CACHE_NAME


def _normalize(value: Any) -> str:
    return str(value or "").strip().lower().replace("ё", "е")


def empty_cache() -> dict[str, Any]:
    return {"date": "", "rows": [], "by_key": {}, "message": ""}


def load_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_cache()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_cache()
    if not isinstance(data, dict):
        return empty_cache()
    rows = data.get("rows") if isinstance(data.get("rows"), list) else []
    by_key = data.get("by_key") if isinstance(data.get("by_key"), dict) else {}
    return {
        "date": str(data.get("date") or ""),
        "rows": rows,
        "by_key": {str(k): v for k, v in by_key.items()},
        "message": str(data.get("message") or ""),
    }


def save_cache(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    cleaned = {
        "date": str(payload.get("date") or ""),
        "rows": list(payload.get("rows") or []),
        "by_key": dict(payload.get("by_key") or {}),
        "message": str(payload.get("message") or ""),
    }
    path.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
    return cleaned


def is_fresh(payload: dict[str, Any] | None, day: str | None = None) -> bool:
    data = payload or {}
    return str(data.get("date") or "") == (day or today_key()) and bool(data.get("rows"))


def has_useful_rows(payload: dict[str, Any] | None) -> bool:
    """Есть ли хоть один реальный статус — не только «Нет данных» после сбоя сети."""
    rows = (payload or {}).get("rows") or []
    return any(str(row.get("status") or "") in {"good", "low", "none"} for row in rows)


def _row_keys(drug: dict[str, Any]) -> list[str]:
    keys = [
        _normalize(drug.get("mnn")),
        _normalize(drug.get("russian_name")),
        _normalize(drug.get("latin_name")),
    ]
    for trade in drug.get("trade_names") or []:
        keys.append(_normalize(trade))
    return [key for key in dict.fromkeys(keys) if key]


def lookup_cached(payload: dict[str, Any] | None, *names: Any) -> dict[str, Any] | None:
    by_key = (payload or {}).get("by_key") or {}
    if not isinstance(by_key, dict):
        return None
    for name in names:
        if isinstance(name, (list, tuple)):
            for item in name:
                hit = by_key.get(_normalize(item))
                if isinstance(hit, dict):
                    return hit
            continue
        hit = by_key.get(_normalize(name))
        if isinstance(hit, dict):
            return hit
    return None


def build_daily_cache(
    drugs: list[dict[str, Any]],
    *,
    checker: Callable[..., Any] = check_availability_minsk,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    by_key: dict[str, dict[str, Any]] = {}
    for drug in drugs:
        aliases = list(drug.get("trade_names") or [])[:4]
        query = str(drug.get("russian_name") or drug.get("mnn") or "").strip()
        if not query:
            continue
        result = availability_to_dict(checker(query, aliases=aliases))
        row = {
            "mnn": drug.get("mnn"),
            "russian_name": drug.get("russian_name"),
            "status": result.get("status") or "unknown",
            "label": result.get("label") or "Нет данных",
            "pharmacies_minsk": result.get("pharmacies_minsk") or 0,
            "message": result.get("message") or "",
        }
        rows.append(row)
        for key in _row_keys(drug):
            by_key[key] = row
    return {
        "date": today_key(),
        "rows": rows,
        "by_key": by_key,
        "message": f"Наличие на {today_key()}: {len(rows)} препаратов.",
    }


class DailyAvailabilityStore:
    """Один опрос каталога в сутки; повторные запуски читают файл."""

    def __init__(self, data_dir: Path, *, checker=check_availability_minsk):
        self.path = cache_path(data_dir)
        self.checker = checker
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._checking = False
        self._pending_force: list[dict[str, Any]] | None = None
        self._cache = load_cache(self.path)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "ok": True,
                "date": self._cache.get("date") or "",
                "fresh": is_fresh(self._cache),
                "checking": self._checking,
                "rows": list(self._cache.get("rows") or []),
                "by_key": dict(self._cache.get("by_key") or {}),
                "message": self._cache.get("message")
                or (
                    "Проверяю наличие на сегодня…"
                    if self._checking
                    else "Наличие ещё не проверялось сегодня."
                ),
            }

    def lookup(self, *names: Any) -> dict[str, Any] | None:
        with self._lock:
            return lookup_cached(self._cache, *names)

    def ensure_today(self, drugs: list[dict[str, Any]], *, force: bool = False) -> dict[str, Any]:
        with self._lock:
            if not force and is_fresh(self._cache) and has_useful_rows(self._cache):
                return self.snapshot()
            if self._checking:
                if force:
                    self._pending_force = list(drugs)
                    self._cache["message"] = "После текущей проверки запущу ещё раз…"
                return self.snapshot()
            self._checking = True
            self._pending_force = None
            self._thread = threading.Thread(
                target=self._refresh,
                args=(list(drugs), force),
                daemon=True,
                name="availability-daily",
            )
            self._thread.start()
        return self.snapshot()

    def _refresh(self, drugs: list[dict[str, Any]], force: bool) -> None:
        try:
            with self._lock:
                if not force and is_fresh(self._cache) and has_useful_rows(self._cache):
                    return
            built = build_daily_cache(drugs, checker=self.checker)
            save_cache(self.path, built)
            with self._lock:
                self._cache = built
            LOGGER.info("Daily availability cache updated: %s rows", len(built["rows"]))
        except Exception:  # noqa: BLE001
            LOGGER.exception("Daily availability refresh failed")
            with self._lock:
                self._cache["message"] = "Не удалось обновить наличие на сегодня."
        finally:
            pending: list[dict[str, Any]] | None = None
            with self._lock:
                self._checking = False
                pending = self._pending_force
                self._pending_force = None
            if pending is not None:
                self.ensure_today(pending, force=True)
