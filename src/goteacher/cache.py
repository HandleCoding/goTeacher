from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from goteacher import config


def key_for(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def get(key: str) -> dict[str, Any] | None:
    path = _path(key)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def put(key: str, value: dict[str, Any]) -> None:
    config.ensure_dirs()
    path = _path(key)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def stats() -> dict[str, int]:
    path = config.analysis_cache_dir()
    if not path.exists():
        return {"entries": 0, "bytes": 0}
    files = list(path.glob("*.json"))
    return {"entries": len(files), "bytes": sum(item.stat().st_size for item in files)}


def clear() -> int:
    path = config.analysis_cache_dir()
    if not path.exists():
        return 0
    count = 0
    for item in path.glob("*.json"):
        item.unlink()
        count += 1
    return count


def _path(key: str) -> Path:
    return config.analysis_cache_dir() / f"{key}.json"
