from __future__ import annotations

import json
import platform
import shutil
import stat
import subprocess
import tarfile
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from goteacher import config
from goteacher.models.registry import install_model

GITHUB_RELEASES_API = "https://api.github.com/repos/lightvector/KataGo/releases/latest"


@dataclass(slots=True)
class SetupResult:
    katago_binary: str
    engine_model: str | None
    human_model: str | None
    katago_config: str | None


def setup_katago(
    *,
    engine_model: str | None,
    human_model: str | None,
    install_katago: bool,
    install_human: bool,
    generate_config: bool,
    katago_asset_url: str | None = None,
) -> SetupResult:
    config.ensure_dirs()
    cfg = config.load_config()
    if install_katago:
        cfg.katago_binary = str(install_katago_binary(katago_asset_url))
    if engine_model:
        if _is_url(engine_model) or Path(engine_model).expanduser().exists():
            record = install_model(engine_model, role="engine")
            cfg.engine_model = record.path
        else:
            raise ValueError("engine model must be a URL or existing local path")
    if install_human:
        record = install_model(human_model or "human-b18c384nbt-v0", role="human")
        cfg.human_model = record.path
    elif human_model:
        record = install_model(human_model, role="human") if _is_url(human_model) or Path(human_model).expanduser().exists() else None
        cfg.human_model = record.path if record else human_model
    if generate_config and cfg.engine_model:
        cfg.katago_config = str(generate_katago_config(cfg.katago_binary, cfg.engine_model))
    config.save_config(cfg)
    return SetupResult(cfg.katago_binary, cfg.engine_model, cfg.human_model, cfg.katago_config)


def install_katago_binary(asset_url: str | None = None) -> Path:
    url = asset_url or resolve_latest_katago_asset_url()
    with tempfile.TemporaryDirectory(prefix="goteacher-katago-") as tmp:
        archive = Path(tmp) / Path(urlparse(url).path).name
        _download(url, archive)
        extract_dir = Path(tmp) / "extract"
        extract_dir.mkdir()
        _extract_archive(archive, extract_dir)
        binary = _find_katago_binary(extract_dir)
        target = config.katago_bin_dir() / "katago"
        shutil.copy2(binary, target)
        target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return target


def resolve_latest_katago_asset_url() -> str:
    with urllib.request.urlopen(GITHUB_RELEASES_API) as response:
        release = json.load(response)
    assets = release.get("assets", [])
    system = platform.system().lower()
    machine = platform.machine().lower()
    candidates = []
    for asset in assets:
        name = asset.get("name", "").lower()
        url = asset.get("browser_download_url")
        if not url:
            continue
        if system == "darwin" and ("mac" in name or "osx" in name or "darwin" in name):
            candidates.append((name, url))
        elif system == "linux" and "linux" in name:
            candidates.append((name, url))
        elif system == "windows" and ("windows" in name or "win" in name):
            candidates.append((name, url))
    if machine in {"arm64", "aarch64"}:
        preferred = [item for item in candidates if "arm" in item[0] or "aarch" in item[0]]
        if preferred:
            return preferred[0][1]
    if machine in {"x86_64", "amd64"}:
        preferred = [item for item in candidates if "x64" in item[0] or "amd64" in item[0] or "x86" in item[0]]
        if preferred:
            return preferred[0][1]
    if candidates:
        return candidates[0][1]
    raise RuntimeError("could not find a KataGo release asset for this platform; pass --katago-asset-url")


def generate_katago_config(katago_binary: str, engine_model: str) -> Path:
    config.ensure_dirs()
    output = config.katago_configs_dir() / "default.cfg"
    result = subprocess.run(
        [katago_binary, "genconfig", "-model", engine_model, "-output", str(output)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"katago genconfig failed: {(result.stderr or result.stdout).strip()}")
    return output


def _download(url: str, target: Path) -> None:
    with urllib.request.urlopen(url) as response, target.open("wb") as out:
        shutil.copyfileobj(response, out)


def _extract_archive(archive: Path, target: Path) -> None:
    suffixes = "".join(archive.suffixes).lower()
    if suffixes.endswith(".zip"):
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(target)
    elif suffixes.endswith(".tar.gz") or suffixes.endswith(".tgz") or suffixes.endswith(".tar.xz"):
        with tarfile.open(archive) as tf:
            tf.extractall(target)
    else:
        if archive.name == "katago" or "." not in archive.name:
            shutil.copy2(archive, target / "katago")
        else:
            raise RuntimeError(f"unsupported KataGo archive type: {archive.name}")


def _find_katago_binary(root: Path) -> Path:
    names = ["katago", "katago.exe"]
    for path in root.rglob("*"):
        if path.is_file() and path.name in names:
            return path
    raise RuntimeError("downloaded archive did not contain a katago binary")


def _is_url(value: str) -> bool:
    return urlparse(value).scheme in {"http", "https"}
