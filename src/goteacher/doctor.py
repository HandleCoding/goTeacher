from __future__ import annotations

import subprocess
from dataclasses import asdict

from goteacher.config import AppConfig
from goteacher.katago.engine import require_files


def check_setup(config: AppConfig) -> dict[str, object]:
    checks: list[dict[str, object]] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})

    try:
        result = subprocess.run([config.katago_binary, "version"], capture_output=True, text=True, timeout=5)
        add("katago_binary", result.returncode == 0, (result.stdout or result.stderr).strip())
    except Exception as exc:
        add("katago_binary", False, str(exc))

    for name, path in [
        ("katago_config", config.katago_config),
        ("engine_model", config.engine_model),
        ("human_model", config.human_model),
    ]:
        if path is None and name == "human_model":
            add(name, True, "not configured")
            continue
        try:
            require_files(path)
            add(name, True, str(path))
        except Exception as exc:
            add(name, False, str(exc))

    return {"config": asdict(config), "checks": checks, "ok": all(item["ok"] for item in checks)}
