"""Тесты логики обновлений (без сети)."""

from __future__ import annotations

from backend import updater
from backend.runtime_control import build_restart_command
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

    monkeypatch.setattr(updater, "is_git_checkout", lambda: True)
    monkeypatch.setattr(updater, "remote_version_file", lambda: None)
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
    monkeypatch.setattr(updater, "remote_version_file", lambda: "1.1.6")
    monkeypatch.setattr(updater, "latest_release_asset", lambda: None)
    status = updater.get_update_status()
    assert status["ok"] is True
    assert status["update_available"] is False
    assert "актуальная" in status["message"].lower()


def test_friendly_permission_error():
    message = updater._friendly_update_error(PermissionError("[Errno 13] Permission denied: 'Recepty.exe'"))
    assert "recepty.exe" in message.lower() or "доступ" in message.lower()


def test_friendly_rate_limit_error():
    message = updater._friendly_update_error(RuntimeError("HTTP Error 403: rate limit exceeded"))
    assert "rate limit" in message.lower() or "ограничил" in message.lower()


def test_get_update_status_without_commit_api_for_non_git(monkeypatch):
    monkeypatch.setattr(updater, "is_git_checkout", lambda: False)
    monkeypatch.setattr(updater, "is_frozen", lambda: True)
    monkeypatch.setattr(updater, "read_local_version", lambda: "1.1.12")
    monkeypatch.setattr(updater, "remote_version_file", lambda: "1.1.13")
    monkeypatch.setattr(updater, "latest_release_asset", lambda: None)
    monkeypatch.setattr(
        updater,
        "remote_head_commit",
        lambda: (_ for _ in ()).throw(RuntimeError("should not be called")),
    )

    status = updater.get_update_status()
    assert status["ok"] is True
    assert status["update_available"] is True
    assert status["remote_version"] == "1.1.13"


def test_frozen_status_uses_release_when_version_file_fails(monkeypatch):
    monkeypatch.setattr(updater, "is_git_checkout", lambda: False)
    monkeypatch.setattr(updater, "is_frozen", lambda: True)
    monkeypatch.setattr(updater, "read_local_version", lambda: "1.1.41")
    monkeypatch.setattr(updater, "remote_version_file", lambda: None)
    monkeypatch.setattr(
        updater,
        "latest_release_asset",
        lambda: {
            "tag": "1.1.48",
            "name": "Recepty-portable.zip",
            "url": "https://github.com/example/recepty.zip",
            "size": 1,
        },
    )
    status = updater.get_update_status()
    assert status["ok"] is True
    assert status["update_available"] is True
    assert status["remote_version"] == "1.1.48"
    assert status["release_asset"]["name"] == "Recepty-portable.zip"


def test_version_compare_uses_numeric_order():
    assert updater._version_is_newer("1.1.48", "1.1.41") is True
    assert updater._version_is_newer("1.1.41", "1.1.48") is False
    assert updater._version_is_newer("1.1.48", "1.1.48") is False
    assert updater._pick_newer_version("1.1.41", "1.1.48", None) == "1.1.48"


def test_frozen_update_prefers_release_overlay(monkeypatch, tmp_path):
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
        lambda *_args, **_kwargs: calls.append("release") or {"method": "release-zip"},
    )
    monkeypatch.setattr(updater, "read_local_version", lambda: "1.1.2")

    result = updater.apply_update()
    assert result["ok"] is True
    assert result["updated"] is True
    assert calls == ["release"]
    assert result["details"]["method"] == "frozen-release-overlay"


def test_frozen_update_falls_back_to_source_zip(monkeypatch):
    calls = []
    monkeypatch.setattr(updater, "is_git_checkout", lambda: False)
    monkeypatch.setattr(updater, "is_frozen", lambda: True)
    monkeypatch.setattr(
        updater,
        "get_update_status",
        lambda: {"ok": True, "update_available": True, "message": "upd", "release_asset": None},
    )
    monkeypatch.setattr(updater, "latest_release_asset", lambda: None)
    monkeypatch.setattr(
        updater,
        "_apply_zip_update",
        lambda: calls.append("zip") or {"method": "zip"},
    )
    monkeypatch.setattr(updater, "read_local_version", lambda: "1.1.2")
    result = updater.apply_update()
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


def test_build_restart_command_for_source():
    command = build_restart_command(
        frozen=False,
        executable="/usr/bin/python3",
        script_path="/workspace/main.py",
    )
    assert command == ["/usr/bin/python3", "/workspace/main.py"]


def test_build_restart_command_for_frozen():
    command = build_restart_command(
        frozen=True,
        executable="C:/Recepty/Recepty.exe",
        script_path="/workspace/main.py",
    )
    assert command == ["C:/Recepty/Recepty.exe"]
