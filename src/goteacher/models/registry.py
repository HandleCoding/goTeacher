from __future__ import annotations

import hashlib
import json
import shutil
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse

from goteacher import config


@dataclass(slots=True)
class ModelRecord:
    name: str
    role: str
    path: str
    sha256: str
    source: str
    size: int


CATALOG: dict[str, dict[str, str]] = {
    "human-b18c384nbt-v0": {
        "role": "human",
        "filename": "b18c384nbt-humanv0.bin.gz",
        "url": "https://github.com/lightvector/KataGo/releases/download/v1.15.0/b18c384nbt-humanv0.bin.gz",
    },
}


def registry_path() -> Path:
    return config.home() / "models" / "registry.json"


def load_registry() -> list[ModelRecord]:
    path = registry_path()
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [ModelRecord(**item) for item in data]


def save_registry(records: list[ModelRecord]) -> None:
    config.ensure_dirs()
    registry_path().parent.mkdir(parents=True, exist_ok=True)
    registry_path().write_text(
        json.dumps([asdict(record) for record in records], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def install_model(source: str, role: str | None = None, expected_sha256: str | None = None) -> ModelRecord:
    config.ensure_dirs()
    entry = CATALOG.get(source)
    if entry:
        role = role or entry["role"]
        url = entry["url"]
        filename = entry["filename"]
        name = source
    else:
        url = source
        parsed = urlparse(source)
        filename = Path(parsed.path).name if parsed.scheme else Path(source).name
        name = Path(filename).stem.replace(".bin", "")
    if role not in {"engine", "human"}:
        raise ValueError("model role must be engine or human")
    target_dir = config.engine_models_dir() if role == "engine" else config.human_models_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / filename
    if urlparse(url).scheme in {"http", "https"}:
        with urllib.request.urlopen(url) as response, target.open("wb") as out:
            shutil.copyfileobj(response, out)
    else:
        shutil.copy2(Path(url).expanduser(), target)
    actual_sha = sha256_file(target)
    if expected_sha256 and actual_sha.lower() != expected_sha256.lower():
        target.unlink(missing_ok=True)
        raise ValueError(f"sha256 mismatch for {target.name}: expected {expected_sha256}, got {actual_sha}")
    record = ModelRecord(name=name, role=role, path=str(target), sha256=actual_sha, source=url, size=target.stat().st_size)
    records = [item for item in load_registry() if not (item.role == role and item.path == str(target))]
    records.append(record)
    save_registry(records)
    return record
