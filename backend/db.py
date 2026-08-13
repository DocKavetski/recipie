import json
import logging
import re
import sqlite3
from pathlib import Path
from typing import Any

from backend.seed_loader import load_seed_drugs
from backend.template_payload import normalize_template_payload


LOGGER = logging.getLogger(__name__)
SEED_DRUGS = load_seed_drugs()


class DrugRepository:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS drugs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    mnn TEXT NOT NULL UNIQUE,
                    russian_name TEXT NOT NULL,
                    latin_name TEXT NOT NULL,
                    drug_form TEXT NOT NULL,
                    dosage TEXT NOT NULL,
                    packaging TEXT NOT NULL,
                    trade_names_json TEXT NOT NULL,
                    search_aliases_json TEXT NOT NULL,
                    scheme_options_json TEXT NOT NULL,
                    trade_details_json TEXT NOT NULL DEFAULT '{}',
                    is_custom INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    card_number TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    payload_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    payload_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS custom_drug_schemes (
                    mnn TEXT PRIMARY KEY,
                    scheme_options_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.commit()

            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(drugs)").fetchall()
            }
            if "trade_details_json" not in columns:
                connection.execute(
                    "ALTER TABLE drugs ADD COLUMN trade_details_json TEXT NOT NULL DEFAULT '{}'"
                )
            if "form_options_json" not in columns:
                connection.execute(
                    "ALTER TABLE drugs ADD COLUMN form_options_json TEXT NOT NULL DEFAULT '[]'"
                )
            if "dosage_options_json" not in columns:
                connection.execute(
                    "ALTER TABLE drugs ADD COLUMN dosage_options_json TEXT NOT NULL DEFAULT '[]'"
                )
            if "form_dosage_map_json" not in columns:
                connection.execute(
                    "ALTER TABLE drugs ADD COLUMN form_dosage_map_json TEXT NOT NULL DEFAULT '{}'"
                )
            if "is_custom" not in columns:
                connection.execute(
                    "ALTER TABLE drugs ADD COLUMN is_custom INTEGER NOT NULL DEFAULT 0"
                )
            connection.commit()

        self.sync_seed_catalog(replace=True)
        self._ensure_runtime_exposes()

    def _ensure_runtime_exposes(self) -> None:
        try:
            from backend.runtime_exposes import register_repository_exposes

            register_repository_exposes(self)
        except Exception:  # noqa: BLE001
            LOGGER.debug("runtime exposes skipped", exc_info=True)

    def sync_seed_catalog(self, replace: bool = True) -> None:
        drugs = load_seed_drugs()
        with self._connect() as connection:
            LOGGER.info("Syncing drugs catalog with %s entries (replace=%s)", len(drugs), replace)
            if replace:
                # Ручные препараты (is_custom=1) сохраняем при обновлении seed.
                connection.execute("DELETE FROM drugs WHERE COALESCE(is_custom, 0) = 0")

            connection.executemany(
                """
                INSERT INTO drugs (
                    category, mnn, russian_name, latin_name, drug_form, dosage, packaging,
                    trade_names_json, search_aliases_json, scheme_options_json, trade_details_json,
                    form_options_json, dosage_options_json, form_dosage_map_json, is_custom
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                ON CONFLICT(mnn) DO UPDATE SET
                    category = excluded.category,
                    russian_name = excluded.russian_name,
                    latin_name = excluded.latin_name,
                    drug_form = excluded.drug_form,
                    dosage = excluded.dosage,
                    packaging = excluded.packaging,
                    trade_names_json = excluded.trade_names_json,
                    search_aliases_json = excluded.search_aliases_json,
                    scheme_options_json = excluded.scheme_options_json,
                    trade_details_json = excluded.trade_details_json,
                    form_options_json = excluded.form_options_json,
                    dosage_options_json = excluded.dosage_options_json,
                    form_dosage_map_json = excluded.form_dosage_map_json
                WHERE COALESCE(drugs.is_custom, 0) = 0
                """,
                [
                    (
                        item["category"],
                        item["mnn"],
                        item["russian_name"],
                        item["latin_name"],
                        item["drug_form"],
                        item["dosage"],
                        item["packaging"],
                        json.dumps(item.get("trade_names", []), ensure_ascii=False),
                        json.dumps(item.get("search_aliases", []), ensure_ascii=False),
                        json.dumps(item.get("scheme_options", []), ensure_ascii=False),
                        json.dumps(item.get("trade_details", {}), ensure_ascii=False),
                        json.dumps(item.get("form_options", []), ensure_ascii=False),
                        json.dumps(item.get("dosage_options", []), ensure_ascii=False),
                        json.dumps(item.get("form_dosage_map", {}), ensure_ascii=False),
                    )
                    for item in drugs
                ],
            )
            connection.commit()

    def list_drugs(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                SELECT
                    drugs.category, drugs.mnn, drugs.russian_name, drugs.latin_name, drugs.drug_form, drugs.dosage, drugs.packaging,
                    drugs.trade_names_json, drugs.search_aliases_json, drugs.scheme_options_json, drugs.trade_details_json,
                    drugs.form_options_json, drugs.dosage_options_json, drugs.form_dosage_map_json,
                    COALESCE(drugs.is_custom, 0) AS is_custom,
                    custom_drug_schemes.scheme_options_json AS custom_scheme_options_json
                FROM drugs
                LEFT JOIN custom_drug_schemes USING (mnn)
                ORDER BY drugs.category, drugs.russian_name
                """
            )
            return [self._row_to_dict(row) for row in cursor.fetchall()]

    def search_drugs(self, query: str) -> list[dict[str, Any]]:
        normalized_query = query.strip().lower()
        if not normalized_query:
            return []

        matches = []
        for drug in self.list_drugs():
            candidates = [
                drug["mnn"],
                drug["russian_name"],
                drug["latin_name"],
                *drug["trade_names"],
                *drug["search_aliases"],
            ]
            if any(normalized_query in value.lower() for value in candidates):
                matches.append(drug)
        return matches

    def save_history_entry(self, payload: dict[str, Any]) -> dict[str, Any]:
        card_number = str(payload.get("card_number", "")).strip()
        if not card_number:
            raise ValueError("Card number is required to save history.")

        with self._connect() as connection:
            connection.execute(
                "INSERT INTO history (card_number, payload_json) VALUES (?, ?)",
                (card_number, json.dumps(payload, ensure_ascii=False)),
            )
            connection.commit()
        return {"ok": True}

    def get_last_history_entry(self, card_number: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                SELECT payload_json
                FROM history
                WHERE card_number = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (card_number.strip(),),
            )
            row = cursor.fetchone()
            return json.loads(row["payload_json"]) if row else None

    def count_history_entries(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS cnt FROM history").fetchone()
            return int(row["cnt"] if row else 0)

    def clear_patient_history(self) -> dict[str, Any]:
        """Удаляет только историю пациентов. Каталог препаратов и шаблоны сохраняются."""
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM history")
            connection.commit()
            deleted = int(cursor.rowcount or 0)
        return {"ok": True, "deleted": deleted, "catalog_preserved": True}

    def save_template(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        template_name = name.strip()
        if not template_name:
            raise ValueError("Template name is required.")

        normalized = normalize_template_payload(payload)
        if not normalized["drugs"]:
            raise ValueError("Template must contain at least one drug.")

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO templates (name, payload_json)
                VALUES (?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    created_at = CURRENT_TIMESTAMP
                """,
                (template_name, json.dumps(normalized, ensure_ascii=False)),
            )
            connection.commit()
        return {"ok": True}

    def list_templates(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            cursor = connection.execute(
                "SELECT name, created_at FROM templates ORDER BY name COLLATE NOCASE"
            )
            return [{"name": row["name"], "created_at": row["created_at"]} for row in cursor.fetchall()]

    def get_template(self, name: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            cursor = connection.execute(
                "SELECT payload_json FROM templates WHERE name = ?",
                (name.strip(),),
            )
            row = cursor.fetchone()
            return json.loads(row["payload_json"]) if row else None

    def delete_template(self, name: str) -> dict[str, Any]:
        template_name = str(name or "").strip()
        if not template_name:
            raise ValueError("Template name is required.")
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM templates WHERE name = ?", (template_name,))
            connection.commit()
        return {"ok": True, "deleted": cursor.rowcount > 0, "name": template_name}

    def upsert_custom_drug(self, payload: dict[str, Any]) -> dict[str, Any]:
        mnn = str(payload.get("mnn") or "").strip()
        russian = str(payload.get("russian_name") or "").strip()
        if not mnn or not russian:
            raise ValueError("МНН и русское название обязательны.")

        latin = str(payload.get("latin_name") or "").strip() or mnn
        drug_form = str(payload.get("drug_form") or "Tab.").strip() or "Tab."
        dosage = str(payload.get("dosage") or "").strip() or "—"
        packaging = str(payload.get("packaging") or "N30").strip() or "N30"
        category = str(payload.get("category") or "Прочее").strip() or "Прочее"
        trade_names = [
            part.strip()
            for part in str(payload.get("trade_names_raw") or payload.get("trade_names") or "").replace(",", ";").split(";")
            if part.strip()
        ]
        if isinstance(payload.get("trade_names"), list):
            trade_names = [str(x).strip() for x in payload["trade_names"] if str(x).strip()]
        form_options = payload.get("form_options") or [drug_form]
        dosage_options = payload.get("dosage_options") or ([dosage] if dosage and dosage != "—" else [])
        form_dosage_map = payload.get("form_dosage_map") or {drug_form: list(dosage_options)}
        scheme_options = payload.get("scheme_options") or [
            "по 1 таблетке утром",
            "по 1 таблетке вечером",
            "по 1/2 таблетки на ночь",
        ]
        search_aliases = list(dict.fromkeys([
            russian.lower(),
            mnn.lower(),
            *[name.lower() for name in trade_names],
        ]))
        trade_details = payload.get("trade_details") or {}
        if trade_names and not trade_details:
            qty_match = re.search(r"(\d+)", packaging)
            qty = int(qty_match.group(1)) if qty_match else 30
            trade_details = {
                name: {
                    dosage: {"packaging": packaging, "dispense_qty": qty, "form": drug_form},
                }
                for name in trade_names
            }

        with self._connect() as connection:
            existing = connection.execute(
                "SELECT is_custom FROM drugs WHERE mnn = ?",
                (mnn,),
            ).fetchone()
            if existing and not int(existing["is_custom"] or 0):
                raise ValueError(f"Препарат «{mnn}» уже есть в системном каталоге.")

            connection.execute(
                """
                INSERT INTO drugs (
                    category, mnn, russian_name, latin_name, drug_form, dosage, packaging,
                    trade_names_json, search_aliases_json, scheme_options_json, trade_details_json,
                    form_options_json, dosage_options_json, form_dosage_map_json, is_custom
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(mnn) DO UPDATE SET
                    category = excluded.category,
                    russian_name = excluded.russian_name,
                    latin_name = excluded.latin_name,
                    drug_form = excluded.drug_form,
                    dosage = excluded.dosage,
                    packaging = excluded.packaging,
                    trade_names_json = excluded.trade_names_json,
                    search_aliases_json = excluded.search_aliases_json,
                    scheme_options_json = excluded.scheme_options_json,
                    trade_details_json = excluded.trade_details_json,
                    form_options_json = excluded.form_options_json,
                    dosage_options_json = excluded.dosage_options_json,
                    form_dosage_map_json = excluded.form_dosage_map_json,
                    is_custom = 1
                """,
                (
                    category,
                    mnn,
                    russian,
                    latin,
                    drug_form,
                    dosage,
                    packaging,
                    json.dumps(trade_names, ensure_ascii=False),
                    json.dumps(search_aliases, ensure_ascii=False),
                    json.dumps(scheme_options, ensure_ascii=False),
                    json.dumps(trade_details, ensure_ascii=False),
                    json.dumps(form_options, ensure_ascii=False),
                    json.dumps(dosage_options, ensure_ascii=False),
                    json.dumps(form_dosage_map, ensure_ascii=False),
                ),
            )
            connection.commit()
        return {"ok": True, "mnn": mnn, "is_custom": True}

    def delete_custom_drug(self, mnn: str) -> dict[str, Any]:
        key = str(mnn or "").strip()
        if not key:
            raise ValueError("MNN is required.")
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM drugs WHERE mnn = ? AND COALESCE(is_custom, 0) = 1",
                (key,),
            )
            connection.commit()
            if cursor.rowcount <= 0:
                raise ValueError("Можно удалять только препараты, добавленные вручную.")
        return {"ok": True, "deleted": True, "mnn": key}

    def save_drug_schemes(self, mnn: str, scheme_options: list[str]) -> dict[str, Any]:
        key = str(mnn or "").strip()
        if not key:
            raise ValueError("MNN is required.")

        cleaned: list[str] = []
        for scheme in scheme_options or []:
            text = str(scheme or "").strip()
            if text and text not in cleaned:
                cleaned.append(text)
        if not cleaned:
            raise ValueError("At least one scheme is required.")

        with self._connect() as connection:
            exists = connection.execute("SELECT 1 FROM drugs WHERE mnn = ?", (key,)).fetchone()
            if not exists:
                raise ValueError("Drug not found.")
            connection.execute(
                """
                INSERT INTO custom_drug_schemes (mnn, scheme_options_json, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(mnn) DO UPDATE SET
                    scheme_options_json = excluded.scheme_options_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (key, json.dumps(cleaned, ensure_ascii=False)),
            )
            connection.commit()
        return {"ok": True, "mnn": key, "scheme_options": cleaned}

    def reset_drug_schemes(self, mnn: str) -> dict[str, Any]:
        key = str(mnn or "").strip()
        if not key:
            raise ValueError("MNN is required.")
        with self._connect() as connection:
            connection.execute("DELETE FROM custom_drug_schemes WHERE mnn = ?", (key,))
            connection.commit()
        return {"ok": True, "mnn": key}

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        keys = set(row.keys())
        form_options = json.loads(row["form_options_json"]) if "form_options_json" in keys else []
        dosage_options = json.loads(row["dosage_options_json"]) if "dosage_options_json" in keys else []
        form_dosage_map = (
            json.loads(row["form_dosage_map_json"]) if "form_dosage_map_json" in keys else {}
        )
        if not form_options and row["drug_form"]:
            form_options = [row["drug_form"]]
        if not dosage_options and row["dosage"]:
            dosage_options = [row["dosage"]]
        if not form_dosage_map:
            form_dosage_map = {form: list(dosage_options) for form in form_options}
        scheme_options = json.loads(row["scheme_options_json"])
        has_custom_scheme = False
        if "custom_scheme_options_json" in keys and row["custom_scheme_options_json"]:
            scheme_options = json.loads(row["custom_scheme_options_json"])
            has_custom_scheme = True
        return {
            "category": row["category"],
            "mnn": row["mnn"],
            "russian_name": row["russian_name"],
            "latin_name": row["latin_name"],
            "drug_form": row["drug_form"],
            "dosage": row["dosage"],
            "packaging": row["packaging"],
            "form_options": form_options,
            "dosage_options": dosage_options,
            "form_dosage_map": form_dosage_map,
            "trade_names": json.loads(row["trade_names_json"]),
            "search_aliases": json.loads(row["search_aliases_json"]),
            "scheme_options": scheme_options,
            "has_custom_scheme": has_custom_scheme,
            "trade_details": json.loads(row["trade_details_json"] or "{}"),
            "is_custom": bool(row["is_custom"]) if "is_custom" in keys else False,
        }
