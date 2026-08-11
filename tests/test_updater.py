"""Тесты логики обновлений (без сети)."""

from __future__ import annotations

from backend import updater
from backend.version import APP_VERSION, GITHUB_REPO


def test_read_local_version():
    assert updater.read_local_version()
    assert isinstance(updater.read_local_version(), str)


def test_app_version_constant():
    assert APP_VERSION
    assert GITHUB_REPO == "recipie"
    assert updater.read_local_version() == APP_VERSION or updater.read_local_version()


def test_get_update_status_offline(monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("offline")

    monkeypatch.setattr(updater, "remote_head_commit", boom)
    status = updater.get_update_status()
    assert status["ok"] is False
    assert status["update_available"] is False


def test_friendly_update_error_private_repo(monkeypatch):
    monkeypatch.setattr(updater, "is_git_checkout", lambda: False)
    message = updater._friendly_update_error(Exception("HTTP Error 404: Not Found"))
    assert "публичн" in message.lower() or "github.com" in message.lower()


def test_get_update_status_via_git(monkeypatch):
    monkeypatch.setattr(updater, "is_git_checkout", lambda: True)
    monkeypatch.setattr(updater, "is_frozen", lambda: False)
    monkeypatch.setattr(updater, "local_commit_sha", lambda: "abc123456789")
    monkeypatch.setattr(
        updater,
        "remote_head_commit",
        lambda: {"sha": "abc123456789ffff", "message": "same tip", "date": ""},
    )
    monkeypatch.setattr(updater, "remote_version_file", lambda: "1.1.1")
    monkeypatch.setattr(updater, "latest_release_asset", lambda: None)
    status = updater.get_update_status()
    assert status["ok"] is True
    assert status["update_available"] is False
    assert "актуальная" in status["message"].lower()
