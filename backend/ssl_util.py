"""Общие SSL-хелперы для updater / tabletka (portable Windows)."""

from __future__ import annotations

import ssl
from typing import Any


def is_ssl_verify_error(exc: BaseException) -> bool:
    messages = [str(exc)]
    current: BaseException | None = exc
    seen = 0
    while current is not None and seen < 5:
        messages.append(str(current))
        current = current.__cause__ or current.__context__
        seen += 1
    blob = " ".join(messages).lower()
    return (
        isinstance(exc, ssl.SSLError)
        or "certificate verify failed" in blob
        or "local issuer certificate" in blob
        or "unable to get local issuer certificate" in blob
        or "ssl: certificate_verify_failed" in blob
        or "sslerror" in blob
    )


def certifi_bundle() -> str | None:
    try:
        import certifi  # type: ignore

        return certifi.where()
    except Exception:
        return None


def ssl_context() -> ssl.SSLContext | None:
    """SSLContext с CA из certifi; None — системный дефолт."""
    bundle = certifi_bundle()
    if not bundle:
        return None
    try:
        return ssl.create_default_context(cafile=bundle)
    except Exception:
        return None


def ssl_unverified_context() -> ssl.SSLContext:
    try:
        return ssl._create_unverified_context()  # type: ignore[attr-defined]
    except Exception:
        return ssl.create_default_context()
