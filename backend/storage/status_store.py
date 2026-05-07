"""Stockage des statuts d'indexation en SQLite.

Avantages vs JSON :
- Transactions ACID : pas de corruption si le process est tué en plein write.
- WAL (Write-Ahead Logging) : lectures non bloquantes pendant les écritures (polling
  toutes les 2 s depuis le frontend sans contention).
- Requête par doc_id en O(log n) via l'index primaire.
- Une seule connexion par thread via threading.local — pas de contention Python.
- Même interface publique que l'ancien store JSON : aucune modification dans le reste du code.
"""
import json
import os
import sqlite3
import threading
from pathlib import Path

from config import settings

_db_path_raw = os.environ.get("STATUS_DB_PATH", settings.status_db_path)

# On accepte aussi bien un chemin .json (rétrocompat) qu'un chemin .db.
# Si l'utilisateur a gardé STATUS_DB_PATH=.../status.json on bascule sur .db à côté.
_raw = Path(_db_path_raw)
DB_PATH = _raw.with_suffix(".db") if _raw.suffix == ".json" else _raw

_local = threading.local()


def _conn() -> sqlite3.Connection:
    """Connexion SQLite par thread, créée à la demande."""
    if not hasattr(_local, "conn") or _local.conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                doc_id  TEXT PRIMARY KEY,
                data    TEXT NOT NULL,          -- JSON du document complet
                updated_at TEXT NOT NULL        -- ISO-8601, pour tris futurs
            )
            """
        )
        conn.commit()
        _local.conn = conn
    return _local.conn


def set_status(doc_id: str, **fields) -> None:
    conn = _conn()
    # Lecture de l'entrée existante puis merge des champs
    row = conn.execute("SELECT data FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()
    entry: dict = json.loads(row["data"]) if row else {}
    entry.update(fields)
    entry["doc_id"] = doc_id
    payload = json.dumps(entry, ensure_ascii=False)
    conn.execute(
        """
        INSERT INTO documents (doc_id, data, updated_at)
        VALUES (?, ?, datetime('now'))
        ON CONFLICT(doc_id) DO UPDATE SET
            data       = excluded.data,
            updated_at = excluded.updated_at
        """,
        (doc_id, payload),
    )
    conn.commit()


def get_status(doc_id: str) -> dict | None:
    row = _conn().execute(
        "SELECT data FROM documents WHERE doc_id = ?", (doc_id,)
    ).fetchone()
    return json.loads(row["data"]) if row else None


def list_all() -> list[dict]:
    rows = _conn().execute(
        "SELECT data FROM documents ORDER BY updated_at DESC"
    ).fetchall()
    return [json.loads(r["data"]) for r in rows]


def delete(doc_id: str) -> None:
    conn = _conn()
    conn.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))
    conn.commit()
