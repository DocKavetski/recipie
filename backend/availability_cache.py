"""Кэш наличия в Минске: один опрос tabletka.by в сутки при первом запуске."""

from __future__ import annotations

import json
import logging
import threading
from datetime import date
from pathlib import Path
from typing import Any, Callable

from backend.tabletka import _session, availability_to_dict, check_availability_minsk

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


def useful_count(payload: dict[str, Any] | None) -> int:
    rows = (payload or {}).get("rows") or []
    return sum(1 for row in rows if str(row.get("status") or "") in {"good", "low", "none"})


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
    on_progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    by_key: dict[str, dict[str, Any]] = {}
    total = len([d for d in drugs if str(d.get("russian_name") or d.get("mnn") or "").strip()])
    done = 0

    # Один HTTP-сеанс на весь каталог — быстрее и стабильнее на Windows.
    session = None
    wrapped = checker
    if checker is check_availability_minsk:
        session = _session()

        def wrapped(query, aliases=None):  # noqa: ANN001
            return check_availability_minsk(
                query,
                aliases=aliases,
                session=session,
                refine_minsk=False,
            )

    try:
        for drug in drugs:
            aliases = list(drug.get("trade_names") or [])[:4]
            query = str(drug.get("russian_name") or drug.get("mnn") or "").strip()
            if not query:
                continue
            result = availability_to_dict(wrapped(query, aliases=aliases))
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
            done += 1
            if on_progress:
                on_progress(
                    {
                        "date": today_key(),
                        "rows": list(rows),
                        "by_key": dict(by_key),
                        "message": f"Проверяю наличие: {done}/{total}…",
                        "progress": {"done": done, "total": total},
                    }
                )
    finally:
        if session is not None:
            session.close()

    useful = useful_count({"rows": rows})
    if useful:
        message = f"Наличие на {today_key()}: {useful} из {len(rows)} препаратов."
    elif rows:
        message = (
            f"tabletka.by не вернул наличие ({len(rows)} запросов без данных). "
            "Проверьте интернет и нажмите «Проверить наличие» ещё раз."
        )
    else:
        message = "Каталог пуст — нечего проверять."
    return {
        "date": today_key(),
        "rows": rows,
        "by_key": by_key,
        "message": message,
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
        self._progress: dict[str, int] | None = None
        self._cache = load_cache(self.path)

    def _recover_dead_worker(self) -> None:
        if self._checking and not self._worker_alive():
            LOGGER.warning("Availability worker dead with checking=True; resetting")
            self._checking = False
            self._pending_force = None
            self._progress = None
            if not self._cache.get("message"):
                self._cache["message"] = "Проверка прервалась. Нажмите «Проверить наличие»."

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            self._recover_dead_worker()
            return {
                "ok": True,
                "date": self._cache.get("date") or "",
                "fresh": is_fresh(self._cache),
                "checking": self._checking,
                "useful": has_useful_rows(self._cache),
                "rows": list(self._cache.get("rows") or []),
                "by_key": dict(self._cache.get("by_key") or {}),
                "progress": dict(self._progress) if self._progress else None,
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

    def _worker_alive(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _start_worker(self, drugs: list[dict[str, Any]], force: bool) -> None:
        """Настоящий OS-поток: после eel.start gevent патчит threading, и requests блокирует UI."""
        thread_cls = threading.Thread
        try:
            from gevent import monkey

            saved = getattr(monkey, "saved", {}).get("threading") or {}
            if "Thread" in saved:
                thread_cls = saved["Thread"]
        except Exception:
            pass
        self._thread = thread_cls(
            target=self._refresh,
            args=(list(drugs), bool(force)),
            daemon=True,
            name="availability-daily",
        )
        self._thread.start()

    def _probe_first(self, drugs: list[dict[str, Any]]) -> None:
        """Синхронно проверяем 1 препарат, чтобы UI сразу увидел данные или ошибку связи."""
        sample = [drug for drug in drugs if str(drug.get("russian_name") or drug.get("mnn") or "").strip()][:1]
        if not sample:
            self._cache["message"] = "Каталог пуст — нечего проверять."
            return
        try:
            probe = build_daily_cache(sample, checker=self.checker)
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Availability probe failed")
            with self._lock:
                self._cache["message"] = f"Не удалось связаться с tabletka.by: {exc}"
            return
        with self._lock:
            if has_useful_rows(probe):
                self._cache = {
                    "date": probe.get("date") or today_key(),
                    "rows": list(probe.get("rows") or []),
                    "by_key": dict(probe.get("by_key") or {}),
                    "message": "Связь с tabletka.by есть, проверяю остальные препараты…",
                }
                self._progress = {"done": 1, "total": max(len(drugs), 1)}
                return
            self._cache["message"] = (
                probe.get("message")
                or "Не удалось связаться с tabletka.by. Проверьте интернет."
            )

    def ensure_today(self, drugs: list[dict[str, Any]], *, force: bool = False) -> dict[str, Any]:
        with self._lock:
            self._recover_dead_worker()

            if not force and is_fresh(self._cache) and has_useful_rows(self._cache):
                return self.snapshot()
            if self._checking:
                if force:
                    self._pending_force = list(drugs)
                    self._cache["message"] = "После текущей проверки запущу ещё раз…"
                return self.snapshot()
            self._checking = True
            self._pending_force = None
            self._progress = {"done": 0, "total": len(drugs)}
            if force:
                self._cache["message"] = "Принудительная проверка tabletka.by…"
            else:
                self._cache["message"] = "Проверяю наличие на сегодня…"

        # Вне замка: короткий синхронный пробный запрос, затем фон.
        self._probe_first(list(drugs))
        self._start_worker(list(drugs), bool(force))
        return self.snapshot()

    def _publish_progress(self, partial: dict[str, Any]) -> None:
        with self._lock:
            # Показываем промежуточные строки, но не затираем полезный кэш файлом,
            # пока опрос не закончится успешно.
            self._cache = {
                "date": partial.get("date") or self._cache.get("date") or "",
                "rows": list(partial.get("rows") or []),
                "by_key": dict(partial.get("by_key") or {}),
                "message": str(partial.get("message") or self._cache.get("message") or ""),
            }
            progress = partial.get("progress")
            self._progress = dict(progress) if isinstance(progress, dict) else self._progress

    def _refresh(self, drugs: list[dict[str, Any]], force: bool) -> None:
        previous: dict[str, Any] = {}
        try:
            with self._lock:
                previous = {
                    "date": self._cache.get("date") or "",
                    "rows": list(self._cache.get("rows") or []),
                    "by_key": dict(self._cache.get("by_key") or {}),
                    "message": self._cache.get("message") or "",
                }
            built = build_daily_cache(
                drugs,
                checker=self.checker,
                on_progress=self._publish_progress,
            )
            if has_useful_rows(built):
                save_cache(self.path, built)
                with self._lock:
                    self._cache = built
                LOGGER.info(
                    "Daily availability cache updated: %s useful / %s rows",
                    useful_count(built),
                    len(built["rows"]),
                )
            else:
                # Не затираем вчерашний/сегодняшний полезный кэш пустыми «Нет данных».
                keep_previous = has_useful_rows(previous)
                with self._lock:
                    if keep_previous:
                        self._cache = {
                            **previous,
                            "message": (
                                built.get("message")
                                or "tabletka.by не ответил — оставлены предыдущие данные."
                            ),
                        }
                        LOGGER.warning("Availability refresh returned no useful rows; kept previous cache")
                    else:
                        save_cache(self.path, built)
                        self._cache = built
                        LOGGER.warning("Availability refresh returned no useful rows")
        except Exception:  # noqa: BLE001
            LOGGER.exception("Daily availability refresh failed")
            with self._lock:
                if has_useful_rows(previous):
                    self._cache = {
                        **previous,
                        "message": "Не удалось обновить наличие — оставлены предыдущие данные.",
                    }
                else:
                    self._cache["message"] = "Не удалось обновить наличие на сегодня."
        finally:
            pending: list[dict[str, Any]] | None = None
            with self._lock:
                self._checking = False
                self._progress = None
                pending = self._pending_force
                self._pending_force = None
            if pending is not None:
                self.ensure_today(pending, force=True)


_SHARED_STORE: DailyAvailabilityStore | None = None


def shared_store(data_dir: Path | None = None, *, checker=check_availability_minsk) -> DailyAvailabilityStore:
    """Один store на процесс — и для main.py, и для overlay exposes."""
    global _SHARED_STORE
    if _SHARED_STORE is None:
        if data_dir is None:
            raise RuntimeError("Daily availability store is not initialized.")
        _SHARED_STORE = DailyAvailabilityStore(data_dir, checker=checker)
    return _SHARED_STORE
