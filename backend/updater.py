"""Проверка и установка обновлений с GitHub."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from backend.version import (
    APP_VERSION,
    GITHUB_BRANCH,
    GITHUB_OWNER,
    GITHUB_REPO,
    GITHUB_URL,
)

LOGGER = logging.getLogger(__name__)

PROTECTED_DATA = {
    "app.db",
    "autosave.json",
    "settings.json",
}
CODE_DIRS = ("backend", "web", "tests", "scripts")
CODE_FILES = (
    "main.py",
    "requirements.txt",
    "pytest.ini",
    "VERSION",
    "README.md",
    ".gitignore",
)
# В portable-сборке exe занят процессом — его не перезаписываем из zip-ветки.
SKIP_REPLACE_NAMES = {
    "recepty.exe",
    "recepty.exe.old",
    "recepty.exe.new",
}


def app_root() -> Path:
    """Каталог установки: рядом с exe (frozen) или корень репозитория."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


ROOT = app_root()


def _version_tuple(value: str) -> tuple[int, ...]:
    parts = []
    for chunk in str(value or "").strip().split("."):
        try:
            parts.append(int(chunk))
        except ValueError:
            return ()
    return tuple(parts)


def _http_json(url: str, timeout: int = 20) -> Any:
    request = Request(
        url,
        headers={
            "User-Agent": "RecipieUpdater/1.1",
            "Accept": "application/vnd.github+json",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _http_bytes(url: str, timeout: int = 60) -> bytes:
    request = Request(url, headers={"User-Agent": "RecipieUpdater/1.1"})
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def _run_git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd or ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def is_git_checkout() -> bool:
    return (ROOT / ".git").exists() and not getattr(sys, "frozen", False)


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def read_local_version() -> str:
    for candidate in (ROOT / "VERSION", app_root() / "VERSION"):
        if candidate.exists():
            text = candidate.read_text(encoding="utf-8").strip()
            if text:
                return text
    return APP_VERSION


def local_commit_sha() -> str | None:
    if not is_git_checkout():
        return None
    result = _run_git("rev-parse", "HEAD")
    if result.returncode != 0:
        return None
    return (result.stdout or "").strip() or None


def remote_head_commit_via_git() -> dict[str, Any]:
    """Проверка через git (удобно для локальной разработки)."""
    ls = _run_git("ls-remote", "origin", f"refs/heads/{GITHUB_BRANCH}")
    if ls.returncode != 0:
        raise RuntimeError((ls.stderr or ls.stdout or "git ls-remote failed").strip())

    remote_sha = ""
    for line in (ls.stdout or "").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1].endswith(f"/{GITHUB_BRANCH}"):
            remote_sha = parts[0].strip()
            break
    if not remote_sha and (ls.stdout or "").strip():
        remote_sha = (ls.stdout or "").split()[0].strip()
    if not remote_sha:
        raise RuntimeError(f"Ветка origin/{GITHUB_BRANCH} не найдена.")

    message = ""
    date = ""
    show = _run_git("log", "-1", "--format=%s%n%cI", remote_sha)
    if show.returncode == 0 and (show.stdout or "").strip():
        lines = (show.stdout or "").splitlines()
        message = lines[0].strip() if lines else ""
        date = lines[1].strip() if len(lines) > 1 else ""
    else:
        fetch = _run_git("fetch", "--quiet", "origin", GITHUB_BRANCH)
        if fetch.returncode == 0:
            show = _run_git("log", "-1", "--format=%s%n%cI", f"origin/{GITHUB_BRANCH}")
            if show.returncode == 0 and (show.stdout or "").strip():
                lines = (show.stdout or "").splitlines()
                message = lines[0].strip() if lines else ""
                date = lines[1].strip() if len(lines) > 1 else ""

    return {"sha": remote_sha, "message": message, "date": date}


def remote_head_commit_via_api() -> dict[str, Any]:
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/commits/{GITHUB_BRANCH}"
    payload = _http_json(url)
    sha = str(payload.get("sha") or "")
    commit = payload.get("commit") or {}
    message = str((commit.get("message") or "").splitlines()[0] if commit else "")
    date = str(((commit.get("author") or {}).get("date")) if commit else "")
    return {"sha": sha, "message": message, "date": date}


def remote_head_commit() -> dict[str, Any]:
    if is_git_checkout():
        try:
            return remote_head_commit_via_git()
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("git update check failed, fallback to API: %s", exc)
    return remote_head_commit_via_api()


def remote_version_file_via_git() -> str | None:
    show = _run_git("show", f"origin/{GITHUB_BRANCH}:VERSION")
    if show.returncode != 0:
        fetch = _run_git("fetch", "--quiet", "origin", GITHUB_BRANCH)
        if fetch.returncode != 0:
            return None
        show = _run_git("show", f"origin/{GITHUB_BRANCH}:VERSION")
    if show.returncode != 0:
        return None
    text = (show.stdout or "").strip()
    return text or None


def remote_version_file_via_http() -> str | None:
    url = (
        f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/"
        f"{GITHUB_BRANCH}/VERSION"
    )
    try:
        raw = _http_bytes(url, timeout=15).decode("utf-8").strip()
        return raw or None
    except Exception:  # noqa: BLE001
        return None


def remote_version_file() -> str | None:
    if is_git_checkout():
        version = remote_version_file_via_git()
        if version:
            return version
    return remote_version_file_via_http()


def latest_release_asset() -> dict[str, Any] | None:
    """Ищет zip-сборку в последнем GitHub Release (для portable/exe)."""
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
    try:
        payload = _http_json(url)
    except Exception as exc:  # noqa: BLE001
        LOGGER.info("no github release yet: %s", exc)
        return None

    tag = str(payload.get("tag_name") or "").lstrip("v")
    assets = payload.get("assets") or []
    preferred = None
    for asset in assets:
        name = str(asset.get("name") or "").lower()
        if name.endswith(".zip") and ("recept" in name or "recipie" in name or "portable" in name):
            preferred = asset
            break
    if preferred is None:
        for asset in assets:
            if str(asset.get("name") or "").lower().endswith(".zip"):
                preferred = asset
                break
    if not preferred:
        return None
    return {
        "tag": tag,
        "name": preferred.get("name"),
        "url": preferred.get("browser_download_url"),
        "size": preferred.get("size"),
    }


def _friendly_update_error(exc: Exception) -> str:
    text = str(exc)
    lowered = text.lower()
    if "rate limit" in lowered or ("403" in text and "github" in lowered):
        return (
            "GitHub временно ограничил частоту запросов (rate limit). "
            "Проверка обновлений продолжится позже автоматически."
        )
    if "404" in text or "not found" in lowered:
        return (
            "Репозиторий недоступен (проверьте, что он публичный): "
            f"{GITHUB_URL}"
        )
    if "permission denied" in lowered or "errno 13" in lowered:
        return (
            "Нет доступа к файлам установки (часто занят Recepty.exe). "
            "Закройте программу, замените папку из свежего архива вручную "
            f"или повторите обновление после перезапуска. ({exc})"
        )
    return f"Не удалось проверить обновления: {exc}"


def get_update_status() -> dict[str, Any]:
    local_version = read_local_version()
    local_sha = local_commit_sha()
    mode = "git" if is_git_checkout() else ("frozen-overlay" if is_frozen() else "zip")
    status: dict[str, Any] = {
        "ok": True,
        "app_version": local_version,
        "local_commit": local_sha,
        "remote_version": None,
        "remote_commit": None,
        "remote_message": "",
        "remote_date": "",
        "update_available": False,
        "repo_url": GITHUB_URL,
        "branch": GITHUB_BRANCH,
        "mode": mode,
        "release_asset": None,
        "message": "Актуальная версия.",
    }

    remote_version = remote_version_file() or ""
    status["remote_version"] = remote_version or None
    remote_sha = ""

    # Для portable/runtime-zip не требуем API-коммиты: VERSION из raw обычно достаточно
    # и не упирается в лимиты API.
    if is_git_checkout():
        try:
            remote = remote_head_commit()
            remote_sha = remote.get("sha") or ""
            status["remote_commit"] = remote_sha
            status["remote_message"] = remote.get("message") or ""
            status["remote_date"] = remote.get("date") or ""
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("update check failed via commit endpoint: %s", exc)
            if not remote_version:
                status["ok"] = False
                status["message"] = _friendly_update_error(exc)
                return status

    if not is_frozen() and not is_git_checkout():
        release = latest_release_asset()
        if release:
            status["release_asset"] = release
            release_tag = str(release.get("tag") or "").strip()
            if release_tag:
                # Не даём старому ReleaseTag занижать более новую VERSION в main.
                current_remote = _version_tuple(remote_version)
                release_remote = _version_tuple(release_tag)
                if (not current_remote and release_remote) or (release_remote and release_remote > current_remote):
                    remote_version = release_tag
                    status["remote_version"] = remote_version

    if local_sha and remote_sha and is_git_checkout():
        status["update_available"] = local_sha[:12] != remote_sha[:12]
    elif remote_version:
        status["update_available"] = remote_version != local_version
    else:
        status["update_available"] = False

    if status["update_available"]:
        shown = remote_version or (remote_sha[:7] if remote_sha else "новая")
        status["message"] = f"Доступно обновление: {shown}"
    else:
        status["message"] = f"Установлена актуальная версия {local_version}"

    return status


def cleanup_update_artifacts(root: Path | None = None) -> None:
    """Удаляет *.old после успешного перезапуска."""
    base = root or app_root()
    for path in base.glob("*.old"):
        try:
            path.unlink()
        except OSError as exc:
            LOGGER.info("skip cleanup %s: %s", path, exc)


def _safe_copy2(src: Path, dst: Path) -> None:
    """Копирует файл; на Windows умеет обойти занятый exe через rename → .old."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(src, dst)
        return
    except PermissionError:
        if os.name != "nt":
            raise
        pending = dst.with_name(dst.name + ".new")
        old = dst.with_name(dst.name + ".old")
        try:
            if pending.exists():
                pending.unlink()
            shutil.copy2(src, pending)
            if old.exists():
                try:
                    old.unlink()
                except OSError:
                    pass
            # Запущенный exe на Windows обычно можно переименовать.
            dst.rename(old)
            pending.rename(dst)
            return
        except OSError as exc:
            raise PermissionError(
                f"Не удалось заменить занятый файл «{dst.name}». "
                "Закройте Recepty и повторите обновление, либо скопируйте "
                f"«{pending.name}» вручную поверх «{dst.name}». ({exc})"
            ) from exc


def _copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def _apply_source_tree(source_root: Path) -> None:
    root = app_root()
    for name in CODE_DIRS:
        src = source_root / name
        if src.exists():
            _copy_tree(src, root / name)

    for name in CODE_FILES:
        src = source_root / name
        if src.exists():
            _safe_copy2(src, root / name)

    seed_src = source_root / "data" / "seed_drugs_from_protocols.json"
    if seed_src.exists():
        (root / "data").mkdir(parents=True, exist_ok=True)
        _safe_copy2(seed_src, root / "data" / "seed_drugs_from_protocols.json")

    data_src = source_root / "data"
    if data_src.exists():
        for path in data_src.iterdir():
            if not path.is_file():
                continue
            if path.name in PROTECTED_DATA:
                continue
            if path.name.startswith("tabletka_"):
                continue
            if path.name.endswith(".json") or path.name.endswith(".txt"):
                _safe_copy2(path, root / "data" / path.name)


def _apply_zip_update() -> dict[str, Any]:
    zip_url = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/archive/refs/heads/{GITHUB_BRANCH}.zip"
    raw = _http_bytes(zip_url, timeout=120)
    with tempfile.TemporaryDirectory(prefix="recipie-update-") as tmp:
        tmp_path = Path(tmp)
        archive = tmp_path / "update.zip"
        archive.write_bytes(raw)
        with zipfile.ZipFile(archive, "r") as zf:
            zf.extractall(tmp_path)
        extracted_dirs = [p for p in tmp_path.iterdir() if p.is_dir()]
        if not extracted_dirs:
            raise RuntimeError("Архив обновления пуст.")
        _apply_source_tree(extracted_dirs[0])
    return {"method": "zip"}


def _apply_release_zip_update(asset: dict[str, Any], *, replace_exe: bool = False) -> dict[str, Any]:
    url = asset.get("url")
    if not url:
        raise RuntimeError("В релизе нет ссылки на архив.")
    raw = _http_bytes(str(url), timeout=180)
    root = app_root()
    with tempfile.TemporaryDirectory(prefix="recipie-release-") as tmp:
        tmp_path = Path(tmp)
        archive = tmp_path / "release.zip"
        archive.write_bytes(raw)
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()
        with zipfile.ZipFile(archive, "r") as zf:
            zf.extractall(extract_dir)

        # Ищем папку сборки (Recepty / recipie-portable) или корень с exe
        candidates = [extract_dir]
        candidates.extend([p for p in extract_dir.iterdir() if p.is_dir()])
        source = None
        for candidate in candidates:
            if (candidate / "Recepty.exe").exists() or (candidate / "VERSION").exists():
                source = candidate
                break
            if (candidate / "main.py").exists():
                source = candidate
                break
        if source is None:
            raise RuntimeError("Не удалось найти файлы сборки в архиве релиза.")

        # Сохраняем локальные данные
        data_dir = root / "data"
        backup = tmp_path / "data-backup"
        if data_dir.exists():
            shutil.copytree(data_dir, backup)

        # Копируем всё из релиза, не трогая защищённые data-файлы
        for item in source.iterdir():
            target = root / item.name
            if item.name == "data":
                target.mkdir(parents=True, exist_ok=True)
                for data_item in item.iterdir():
                    if data_item.name in PROTECTED_DATA:
                        continue
                    dest = target / data_item.name
                    if data_item.is_dir():
                        _copy_tree(data_item, dest)
                    else:
                        _safe_copy2(data_item, dest)
                continue
            if not replace_exe and item.name.lower() in SKIP_REPLACE_NAMES:
                LOGGER.info("skip locked binary during update: %s", item.name)
                continue
            if item.is_dir():
                _copy_tree(item, target)
            else:
                _safe_copy2(item, target)

        if backup.exists():
            (root / "data").mkdir(parents=True, exist_ok=True)
            for name in PROTECTED_DATA:
                src = backup / name
                if src.exists():
                    _safe_copy2(src, root / "data" / name)

    return {"method": "release-zip", "asset": asset.get("name"), "replaced_exe": replace_exe}


def _apply_git_update() -> dict[str, Any]:
    fetch = _run_git("fetch", "origin", GITHUB_BRANCH)
    if fetch.returncode != 0:
        raise RuntimeError((fetch.stderr or fetch.stdout or "git fetch failed").strip())

    pull = _run_git("pull", "--ff-only", "origin", GITHUB_BRANCH)
    if pull.returncode != 0:
        reset = _run_git("reset", "--hard", f"origin/{GITHUB_BRANCH}")
        if reset.returncode != 0:
            raise RuntimeError((pull.stderr or pull.stdout or "git pull failed").strip())
        return {"method": "git-reset"}
    return {"method": "git-pull"}


def apply_update() -> dict[str, Any]:
    before = get_update_status()
    if not before.get("update_available"):
        return {
            "ok": True,
            "updated": False,
            "needs_restart": False,
            "message": before.get("message") or "Обновление не требуется.",
            "status": before,
        }

    try:
        if is_git_checkout():
            details = _apply_git_update()
        elif is_frozen():
            # Portable: не перезаписываем запущенный Recepty.exe.
            # Кладём свежие backend/web/VERSION рядом с exe (см. bootstrap в main.py).
            details = _apply_zip_update()
            details = {**details, "method": "frozen-overlay"}
        elif before.get("release_asset") and before["release_asset"].get("url"):
            details = _apply_release_zip_update(before["release_asset"], replace_exe=True)
        else:
            details = _apply_zip_update()
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("apply_update failed")
        lowered = str(exc).lower()
        if "permission" in lowered or "errno 13" in lowered:
            message = _friendly_update_error(exc)
        else:
            message = f"Ошибка обновления: {exc}"
        return {
            "ok": False,
            "updated": False,
            "needs_restart": False,
            "message": message,
            "status": before,
        }

    after_version = read_local_version()
    return {
        "ok": True,
        "updated": True,
        "needs_restart": True,
        "message": (
            f"Обновлено до {after_version}. Перезапустите приложение, "
            "чтобы изменения вступили в силу."
        ),
        "details": details,
        "app_version": after_version,
        "status": {
            "app_version": after_version,
            "update_available": False,
            "ok": True,
            "message": f"Установлена актуальная версия {after_version}",
        },
    }


def open_repo_in_browser() -> dict[str, Any]:
    try:
        os.startfile(GITHUB_URL)  # type: ignore[attr-defined]
        return {"ok": True, "url": GITHUB_URL}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "url": GITHUB_URL, "message": str(exc)}
