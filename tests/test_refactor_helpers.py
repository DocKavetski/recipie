"""Регрессии рефакторинга: пути, SSL-хелперы, публичные API."""

from __future__ import annotations

from pathlib import Path

from backend import paths, ssl_util, tabletka
from backend.seed_loader import default_schemes, load_seed_drugs


def test_paths_app_root_points_at_repo():
    root = paths.app_root()
    assert (root / "VERSION").exists() or (root / "backend").exists()
    assert paths.writable_path("data").name == "data"


def test_data_search_roots_include_repo_data():
    roots = paths.data_search_roots()
    assert any((root / "seed_drugs_from_protocols.json").exists() for root in roots)


def test_ssl_helpers_do_not_crash():
    assert ssl_util.ssl_unverified_context() is not None
    # certifi may or may not be present; just ensure call is safe
    _ = ssl_util.certifi_bundle()
    _ = ssl_util.ssl_context()
    assert ssl_util.is_ssl_verify_error(Exception("certificate verify failed")) is True
    assert ssl_util.is_ssl_verify_error(RuntimeError("offline")) is False


def test_tabletka_make_session_public():
    session = tabletka.make_session()
    assert session is not None
    session.close()


def test_default_schemes_public_alias():
    drugs = load_seed_drugs()
    sample = next(d for d in drugs if d["mnn"] == "Escitalopram")
    schemes = default_schemes({"mnn": "Escitalopram", "category": sample["category"], "drug_form": "Tab."})
    assert schemes
    assert any(s.startswith("начало:") for s in schemes) or any("утром" in s for s in schemes)
