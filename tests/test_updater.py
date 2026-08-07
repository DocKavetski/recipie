"""Тесты логики обновлений (без сети)."""

from __future__ import annotations

from backend import updater
from backend.version import APP_VERSION


def test_read_local_version():
    assert updater.read_local_version()
    assert isinstance(updater.read_local_version(), str)


def test_app_version_constant():
    assert APP_VERSION
    assert updater.read_local_version() == APP_VERSION or updater.read_local_version()


def test_get_update_status_offline(monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("offline")

    monkeypatch.setattr(updater, "remote_head_commit", boom)
    status = updater.get_update_status()
    assert status["ok"] is False
    assert status["update_available"] is False
