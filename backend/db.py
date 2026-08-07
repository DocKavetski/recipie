import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

from backend.seed_loader import load_seed_drugs


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
                    trade_details_json TEXT NOT NULL DEFAULT '{}'
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
            connection.commit()

        self.sync_seed_catalog(replace=True)

    def sync_seed_catalog(self, replace: bool = True) -> None:
        drugs = load_seed_drugs()
        with self._connect() as connection:
            LOGGER.info("Syncing drugs catalog with %s entries (replace=%s)", len(drugs), replace)
            if replace:
                connection.execute("DELETE FROM drugs")

            connection.executemany(
                """
                INSERT INTO drugs (
                    category, mnn, russian_name, latin_name, drug_form, dosage, packaging,
                    trade_names_json, search_aliases_json, scheme_options_json, trade_details_json,
                    form_options_json, dosage_options_json, form_dosage_map_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    category, mnn, russian_name, latin_name, drug_form, dosage, packaging,
                    trade_names_json, search_aliases_json, scheme_options_json, trade_details_json,
                    form_options_json, dosage_options_json, form_dosage_map_json
                FROM drugs
                ORDER BY category, russian_name
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

    def save_template(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        template_name = name.strip()
        if not template_name:
            raise ValueError("Template name is required.")

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO templates (name, payload_json)
                VALUES (?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    created_at = CURRENT_TIMESTAMP
                """,
                (template_name, json.dumps(payload, ensure_ascii=False)),
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
            "scheme_options": json.loads(row["scheme_options_json"]),
            "trade_details": json.loads(row["trade_details_json"] or "{}"),
        }
