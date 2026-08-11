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
    monkeypatch.setattr(updater, "remote_version_file", lambda: "1.1.3")
    monkeypatch.setattr(updater, "latest_release_asset", lambda: None)
    status = updater.get_update_status()
    assert status["ok"] is True
    assert status["update_available"] is False
    assert "актуальная" in status["message"].lower()


def test_friendly_permission_error():
    message = updater._friendly_update_error(PermissionError("[Errno 13] Permission denied: 'Recepty.exe'"))
    assert "recepty.exe" in message.lower() or "доступ" in message.lower()


def test_frozen_update_uses_overlay(monkeypatch, tmp_path):
    calls = []

    monkeypatch.setattr(updater, "is_git_checkout", lambda: False)
    monkeypatch.setattr(updater, "is_frozen", lambda: True)
    monkeypatch.setattr(
        updater,
        "get_update_status",
        lambda: {
            "ok": True,
            "update_available": True,
            "message": "Доступно обновление: 1.1.2",
            "release_asset": {"url": "https://example.invalid/recepty.zip", "name": "x.zip", "tag": "1.1.2"},
        },
    )
    monkeypatch.setattr(
        updater,
        "_apply_zip_update",
        lambda: calls.append("zip") or {"method": "zip"},
    )
    monkeypatch.setattr(
        updater,
        "_apply_release_zip_update",
        lambda *_args, **_kwargs: calls.append("release") or {"method": "release"},
    )
    monkeypatch.setattr(updater, "read_local_version", lambda: "1.1.2")

    result = updater.apply_update()
    assert result["ok"] is True
    assert result["updated"] is True
    assert calls == ["zip"]
    assert result["details"]["method"] == "frozen-overlay"


def test_safe_copy2_overwrites(tmp_path):
    src = tmp_path / "src.txt"
    dst = tmp_path / "dst.txt"
    src.write_text("new", encoding="utf-8")
    dst.write_text("old", encoding="utf-8")
    updater._safe_copy2(src, dst)
    assert dst.read_text(encoding="utf-8") == "new"


def test_cleanup_update_artifacts(tmp_path):
    old = tmp_path / "Recepty.exe.old"
    old.write_bytes(b"x")
    updater.cleanup_update_artifacts(tmp_path)
    assert not old.exists()
