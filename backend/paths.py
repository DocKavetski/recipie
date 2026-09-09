"""Общие пути приложения (source / portable / PyInstaller)."""

from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_root() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def meipass_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", app_root()))


def resource_path(*parts: str) -> Path:
    """Файл ресурса: сначала overlay рядом с exe, иначе _MEIPASS/исходники."""
    if is_frozen():
        external = app_root().joinpath(*parts)
        if external.exists():
            return external
    return meipass_root().joinpath(*parts)


def writable_path(*parts: str) -> Path:
    return app_root().joinpath(*parts)


def data_search_roots() -> list[Path]:
    """Кандидаты для data/*.json (seed, archive) без дублирования списков."""
    root = app_root()
    meipass = meipass_root()
    return [
        root / "data",
        root.parent / "data",
        meipass / "data",
        Path.cwd() / "data",
    ]
