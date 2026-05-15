from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import click

from goteacher import __version__, cache, config
from goteacher.analysis.normalize import normalize_response
from goteacher.doctor import check_setup
from goteacher.katago.engine import EngineConfig, KataGoEngine, require_files
from goteacher.katago.protocol import Query
from goteacher.models.registry import install_model, load_registry
from goteacher.output import render_json, render_markdown
from goteacher.setup import setup_katago
from goteacher.sgf.replay import moves_until, parse_sgf_file


@click.group()
def main() -> None:
    """KataGo-powered Go teaching CLI for agents."""


@main.command()
def version() -> None:
    click.echo(__version__)


@main.command()
@click.option("--install-katago/--no-install-katago", default=True, help="Download and install the latest KataGo binary.")
@click.option("--katago-asset-url", default=None, help="Explicit KataGo release asset URL if auto-detection fails.")
@click.option("--engine-model", default=None, help="Engine model URL or local path to install.")
@click.option("--install-human/--no-install-human", default=True, help="Install the default Human SL model.")
@click.option("--human-model", default=None, help="Human SL catalog name, URL, or local path.")
@click.option("--generate-config/--no-generate-config", default=True, help="Run katago genconfig after engine model install.")
def setup(install_katago: bool, katago_asset_url: str | None, engine_model: str | None, install_human: bool, human_model: str | None, generate_config: bool) -> None:
    """Install KataGo assets and save a working GoTeacher config."""
    try:
        result = setup_katago(
            engine_model=engine_model,
            human_model=human_model,
            install_katago=install_katago,
            install_human=install_human,
            generate_config=generate_config,
            katago_asset_url=katago_asset_url,
        )
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(json.dumps(asdict(result), indent=2, ensure_ascii=False))


@main.command("init")
@click.option("--katago", "katago_binary", default=None, help="Path to KataGo binary.")
@click.option("--engine-model", default=None, help="Path to engine model .bin.gz.")
@click.option("--human-model", default=None, help="Path to Human SL model .bin.gz.")
@click.option("--katago-config", default=None, help="Existing KataGo config path.")
@click.option("--generate-config/--no-generate-config", default=True, help="Run katago genconfig when possible.")
def init_cmd(katago_binary: str | None, engine_model: str | None, human_model: str | None, katago_config: str | None, generate_config: bool) -> None:
    cfg = config.load_config()
    if katago_binary:
        cfg.katago_binary = katago_binary
    if engine_model:
        cfg.engine_model = str(Path(engine_model).expanduser())
    if human_model:
        cfg.human_model = str(Path(human_model).expanduser())
    if katago_config:
        cfg.katago_config = str(Path(katago_config).expanduser())
    config.ensure_dirs()
    if generate_config and cfg.engine_model and not cfg.katago_config:
        output = config.katago_configs_dir() / "default.cfg"
        result = subprocess.run([cfg.katago_binary, "genconfig", "-model", cfg.engine_model, "-output", str(output)], capture_output=True, text=True)
        if result.returncode != 0:
            raise click.ClickException(f"katago genconfig failed: {(result.stderr or result.stdout).strip()}")
        cfg.katago_config = str(output)
    config.save_config(cfg)
    click.echo(f"saved config to {config.config_path()}")


@main.group()
def models() -> None:
    """Manage KataGo model registry."""


@models.command("list")
def models_list() -> None:
    records = load_registry()
    if not records:
        click.echo("no models installed")
        return
    for record in records:
        click.echo(f"{record.role}\t{record.name}\t{record.path}\t{record.sha256[:12]}\t{record.size}")


@models.command("install")
@click.option("--engine", default=None, help="Engine model catalog name, URL, or local path.")
@click.option("--human", default=None, help="Human SL model catalog name, URL, or local path.")
@click.option("--sha256", "expected_sha256", default=None, help="Expected sha256 for downloaded/copied model.")
def models_install(engine: str | None, human: str | None, expected_sha256: str | None) -> None:
    if bool(engine) == bool(human):
        raise click.ClickException("provide exactly one of --engine or --human")
    record = install_model(engine or human or "", role="engine" if engine else "human", expected_sha256=expected_sha256)
    click.echo(json.dumps(asdict(record), indent=2, ensure_ascii=False))


@main.command()
def doctor() -> None:
    click.echo(json.dumps(check_setup(config.load_config()), indent=2, ensure_ascii=False))


@main.group()
def cache_cmd() -> None:
    """Manage analysis cache."""


@cache_cmd.command("stats")
def cache_stats() -> None:
    click.echo(json.dumps(cache.stats(), indent=2))


@cache_cmd.command("clear")
def cache_clear() -> None:
    click.echo(f"removed {cache.clear()} cache entries")


@main.command()
@click.option("--sgf", "sgf_path", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--turn", required=True, type=int)
@click.option("--profile", default=None)
@click.option("--rules", default=None)
@click.option("--komi", default=None, type=float)
@click.option("--visits", default=None, type=int)
@click.option("--format", "fmt", type=click.Choice(["json", "markdown"]), default="json")
@click.option("--no-cache", is_flag=True, default=False)
@click.option("--refresh", is_flag=True, default=False)
def analyze(sgf_path: str, turn: int, profile: str | None, rules: str | None, komi: float | None, visits: int | None, fmt: str, no_cache: bool, refresh: bool) -> None:
    result = asyncio.run(_analyze(sgf_path, turn, profile, rules, komi, visits, no_cache, refresh))
    click.echo(render_json(result) if fmt == "json" else render_markdown(result), nl=False)


@main.command()
@click.option("--sgf", "sgf_path", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--turn", required=True, type=int)
@click.option("--profile", default=None)
@click.option("--visits", default=None, type=int)
def prompt(sgf_path: str, turn: int, profile: str | None, visits: int | None) -> None:
    result = asyncio.run(_analyze(sgf_path, turn, profile, None, None, visits, no_cache=False, refresh=False))
    played = result.played_move_evaluation
    best = result.candidates[0] if result.candidates else None
    lines = [f"请用{profile or '目标棋手'}能理解的方式讲解第 {turn} 手。"]
    if played.move:
        lines.append(f"实战手：{played.move}，损失约 {played.score_loss} 目，胜率损失 {played.winrate_loss}。")
    if best:
        lines.append(f"推荐手：{best.move}，scoreLead={best.score_lead}，prior={best.prior}，humanPrior={best.human_prior}。")
    if result.teaching.why_interesting:
        lines.append("教学重点：" + "、".join(result.teaching.why_interesting) + "。")
    click.echo("\n".join(lines))


@main.command()
@click.option("--sgf", "sgf_path", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--profile", default=None)
@click.option("--max", "max_items", default=8, type=int)
@click.option("--visits-fast", default=150, type=int)
def scan(sgf_path: str, profile: str | None, max_items: int, visits_fast: int) -> None:
    record = parse_sgf_file(sgf_path)
    click.echo(json.dumps({
        "schemaVersion": "goteacher.scan.v1",
        "sgfPath": sgf_path,
        "profile": profile,
        "max": max_items,
        "visitsFast": visits_fast,
        "moves": len(record.moves),
        "note": "scan selection requires KataGo batch analysis; use analyze for exact turns in this MVP",
        "warnings": record.warnings,
    }, indent=2, ensure_ascii=False))


async def _analyze(sgf_path: str, turn: int, profile: str | None, rules: str | None, komi: float | None, visits: int | None, no_cache: bool, refresh: bool):
    cfg = config.load_config()
    record = parse_sgf_file(sgf_path)
    resolved_rules = rules or record.rules or cfg.default_rules
    resolved_komi = komi if komi is not None else (record.komi if record.komi is not None else cfg.default_komi)
    resolved_visits = visits or cfg.default_visits
    resolved_profile = profile or cfg.default_human_profile
    if resolved_profile and not cfg.human_model:
        raise click.ClickException("human profile requires a configured Human SL model; run init with --human-model")
    require_files(cfg.katago_config, cfg.engine_model)
    key_payload = {
        "sgf": str(Path(sgf_path).resolve()),
        "turn": turn,
        "rules": resolved_rules,
        "komi": resolved_komi,
        "visits": resolved_visits,
        "profile": resolved_profile,
        "engine": cfg.engine_model,
        "human": cfg.human_model,
        "schema": "goteacher.analysis.v1",
    }
    key = cache.key_for(key_payload)
    if cfg.cache_enabled and not no_cache and not refresh:
        cached = cache.get(key)
        if cached:
            from goteacher.analysis.schema import AnalysisResult
            return AnalysisResult.model_validate(cached)
    query = Query(
        id=key[:24],
        moves=moves_until(record, turn),
        rules=resolved_rules,
        komi=resolved_komi,
        board_x_size=record.board_size,
        board_y_size=record.board_size,
        initial_stones=record.initial_stones,
        analyze_turns=[turn],
        max_visits=resolved_visits,
        include_ownership=True,
        include_ownership_stdev=True,
        include_policy=True,
        override_settings={"humanSLProfile": resolved_profile} if resolved_profile else {},
    )
    engine = KataGoEngine(EngineConfig(binary=cfg.katago_binary, config_path=cfg.katago_config or "", model_path=cfg.engine_model or "", human_model_path=cfg.human_model))
    try:
        response = await engine.analyze(query)
    finally:
        await engine.close()
    result = normalize_response(response, app_config=cfg, record=record, sgf_path=sgf_path, turn=turn, profile=resolved_profile, visits=resolved_visits, rules=resolved_rules, komi=resolved_komi)
    if cfg.cache_enabled and not no_cache:
        cache.put(key, result.model_dump(by_alias=True, exclude_none=True))
    return result


if __name__ == "__main__":
    main()
