from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from platformdirs import user_cache_dir, user_config_dir, user_data_dir

APP_NAME = "goteacher"


@dataclass(slots=True)
class AppConfig:
    katago_binary: str = "katago"
    katago_config: str | None = None
    engine_model: str | None = None
    human_model: str | None = None
    default_rules: str = "chinese"
    default_komi: float = 7.5
    default_visits: int = 400
    default_human_profile: str | None = None
    cache_enabled: bool = True


def home() -> Path:
    override = os.environ.get("GOTEACHER_HOME")
    if override:
        return Path(override).expanduser()
    return Path(user_data_dir(APP_NAME, appauthor=False))


def config_dir() -> Path:
    override = os.environ.get("GOTEACHER_HOME")
    if override:
        return Path(override).expanduser() / "config"
    return Path(user_config_dir(APP_NAME, appauthor=False))


def cache_dir() -> Path:
    override = os.environ.get("GOTEACHER_HOME")
    if override:
        return Path(override).expanduser() / "cache"
    return Path(user_cache_dir(APP_NAME, appauthor=False))


def config_path() -> Path:
    return config_dir() / "config.json"


def ensure_dirs() -> None:
    for path in [
        config_dir(),
        home(),
        katago_bin_dir(),
        engine_models_dir(),
        human_models_dir(),
        katago_configs_dir(),
        analysis_cache_dir(),
    ]:
        path.mkdir(parents=True, exist_ok=True)


def katago_bin_dir() -> Path:
    return home() / "bin"


def engine_models_dir() -> Path:
    return home() / "models" / "engine"


def human_models_dir() -> Path:
    return home() / "models" / "human"


def katago_configs_dir() -> Path:
    return home() / "katago-configs"


def analysis_cache_dir() -> Path:
    return cache_dir() / "analysis"


def load_config() -> AppConfig:
    path = config_path()
    if not path.exists():
        return AppConfig()
    data = json.loads(path.read_text(encoding="utf-8"))
    return AppConfig(**data)


def save_config(config: AppConfig) -> None:
    ensure_dirs()
    config_path().write_text(json.dumps(asdict(config), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def resolved_config_dict(config: AppConfig | None = None) -> dict[str, Any]:
    cfg = config or load_config()
    data = asdict(cfg)
    data["paths"] = {
        "config": str(config_path()),
        "data": str(home()),
        "cache": str(cache_dir()),
        "katago_bin": str(katago_bin_dir()),
        "engine_models": str(engine_models_dir()),
        "human_models": str(human_models_dir()),
        "katago_configs": str(katago_configs_dir()),
    }
    return data
