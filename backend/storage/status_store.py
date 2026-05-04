import json
import os
import threading
from pathlib import Path
from config import settings

_lock = threading.Lock()
_path = Path(os.environ.get("STATUS_DB_PATH", settings.status_db_path))


def _load() -> dict:
    if not _path.exists():
        return {}
    try:
        return json.loads(_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save(data: dict):
    # Écriture atomique : tmp puis rename
    _path.parent.mkdir(parents=True, exist_ok=True)
    tmp = _path.with_suffix(_path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, _path)


def set_status(doc_id: str, **fields):
    with _lock:
        data = _load()
        entry = data.get(doc_id, {})
        entry.update(fields)
        entry["doc_id"] = doc_id
        data[doc_id] = entry
        _save(data)


def get_status(doc_id: str) -> dict | None:
    with _lock:
        return _load().get(doc_id)


def list_all() -> list[dict]:
    with _lock:
        return list(_load().values())


def delete(doc_id: str):
    with _lock:
        data = _load()
        if doc_id in data:
            del data[doc_id]
            _save(data)
