"""Helpers for restarting the desktop application."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def build_restart_command(
    *,
    frozen: bool | None = None,
    executable: str | None = None,
    script_path: str | None = None,
) -> list[str]:
    is_frozen = bool(getattr(sys, "frozen", False) if frozen is None else frozen)
    exe = executable or sys.executable
    if is_frozen:
        return [exe]
    target = script_path or str(Path(__file__).resolve().parents[1] / "main.py")
    return [exe, target]


def spawn_restart(command: list[str], cwd: str | None = None) -> None:
    subprocess.Popen(command, cwd=cwd or None)  # noqa: S603


def hard_exit(code: int = 0) -> None:
    os._exit(code)
