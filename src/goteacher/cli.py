from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import click

from goteacher import __version__, cache, config
from goteacher.analysis.normalize import normalize_response
from goteacher.doctor import check_setup
from goteacher.katago.engine import EngineConfig, KataGoEngine, require_files
from goteacher.katago.protocol import Move, Query, analysis_for_turn
from goteacher.models.registry import install_model, load_registry
from goteacher.output import render_json, render_markdown
from goteacher.profile import normalize_profile, validate_profile
from goteacher.setup import setup_katago
from goteacher.sgf.replay import GameRecord, moves_until, parse_sgf_file, played_move_at


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
@click.option("--move", default=None, help="Evaluate a specific move at this turn (e.g. D4, pass).")
@click.option("--profile", default=None)
@click.option("--human-explore", default=None, type=float, help="humanSLRootExploreProbWeightless (0-1, try 0.5).")
@click.option("--human-cpuct", default=None, type=float, help="humanSLCpuctPermanent (try 2.0).")
@click.option("--rules", default=None)
@click.option("--komi", default=None, type=float)
@click.option("--visits", default=None, type=int)
@click.option("--format", "fmt", type=click.Choice(["json", "markdown", "board"]), default="json")
@click.option("--no-cache", is_flag=True, default=False)
@click.option("--refresh", is_flag=True, default=False)
def analyze(sgf_path: str, turn: int, move: str | None, profile: str | None, human_explore: float | None, human_cpuct: float | None, rules: str | None, komi: float | None, visits: int | None, fmt: str, no_cache: bool, refresh: bool) -> None:
    result, record = asyncio.run(_analyze(sgf_path, turn, profile, rules, komi, visits, no_cache, refresh, extra_move=move, human_explore=human_explore, human_cpuct=human_cpuct))
    if fmt == "board":
        from goteacher.output import render_board
        click.echo(render_board(result, record), nl=False)
    else:
        click.echo(render_json(result) if fmt == "json" else render_markdown(result), nl=False)


@main.command()
@click.option("--sgf", "sgf_path", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--turn", required=True, type=int)
@click.option("--profile", default=None)
@click.option("--visits", default=None, type=int)
def prompt(sgf_path: str, turn: int, profile: str | None, visits: int | None) -> None:
    result, _record = asyncio.run(_analyze(sgf_path, turn, profile, None, None, visits, no_cache=False, refresh=False))
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
@click.option("--format", "fmt", type=click.Choice(["json", "markdown"]), default="json")
def scan(sgf_path: str, profile: str | None, max_items: int, visits_fast: int, fmt: str) -> None:
    result = asyncio.run(_scan(sgf_path, profile, max_items, visits_fast))
    if fmt == "markdown":
        lines = [f"# GoTeacher Scan: {sgf_path}", ""]
        for m in result["moments"]:
            lines.append(f"## Turn {m['turn']}: {m['move']} ({m['severity']})")
            lines.append(f"- Score loss: {m.get('scoreLoss', 'unknown')}")
            lines.append(f"- Winrate loss: {m.get('winrateLoss', 'unknown')}")
            lines.append(f"- Best move: {m.get('bestMove', 'unknown')}")
            if m.get("whyInteresting"):
                lines.append(f"- Why: {', '.join(m['whyInteresting'])}")
            lines.append("")
        click.echo("\n".join(lines))
    else:
        click.echo(json.dumps(result, indent=2, ensure_ascii=False))


async def _scan(sgf_path: str, profile: str | None, max_items: int, visits_fast: int) -> dict[str, Any]:
    cfg = config.load_config()
    record = parse_sgf_file(sgf_path)
    resolved_rules = record.rules or cfg.default_rules
    resolved_komi = record.komi if record.komi is not None else cfg.default_komi
    resolved_profile = normalize_profile(profile or cfg.default_human_profile)
    if resolved_profile:
        _valid, err = validate_profile(resolved_profile)
        if err:
            raise click.ClickException(err)
        if not cfg.human_model:
            raise click.ClickException("human profile requires a configured Human SL model")
    require_files(cfg.katago_config, cfg.engine_model)
    total_moves = len(record.moves)
    if total_moves == 0:
        return {"schemaVersion": "goteacher.scan.v1", "sgfPath": sgf_path, "moments": [], "moves": 0}
    all_turns = list(range(1, total_moves + 1))
    query = Query(
        id="scan",
        moves=record.moves,
        rules=resolved_rules,
        komi=resolved_komi,
        board_x_size=record.board_size,
        board_y_size=record.board_size,
        initial_stones=record.initial_stones,
        analyze_turns=all_turns,
        max_visits=visits_fast,
        include_ownership=False,
        include_ownership_stdev=False,
        include_policy=True,
        override_settings={"humanSLProfile": resolved_profile} if resolved_profile else {},
    )
    engine = KataGoEngine(EngineConfig(binary=cfg.katago_binary, config_path=cfg.katago_config or "", model_path=cfg.engine_model or "", human_model_path=cfg.human_model))
    try:
        response = await engine.analyze(query)
    finally:
        await engine.close()
    moments: list[dict[str, Any]] = []
    for t in all_turns:
        try:
            analysis = analysis_for_turn(response, t)
        except ValueError:
            continue
        root_info = analysis.get("rootInfo", {})
        if not root_info:
            continue
        prev_analysis = None
        prev_root = {}
        if t > 1:
            try:
                prev_analysis = analysis_for_turn(response, t - 1)
                prev_root = prev_analysis.get("rootInfo", {})
            except ValueError:
                pass
        move_infos = analysis.get("moveInfos", [])
        actual = played_move_at(record, t)
        if not actual:
            continue
        best = next((m for m in move_infos if m.get("order") == 0), move_infos[0] if move_infos else None)
        played_info = next((m for m in move_infos if m.get("move") == actual.point), None)
        score_loss = None
        winrate_loss = None
        if prev_root:
            sl_before = prev_root.get("scoreLead")
            sl_after = root_info.get("scoreLead")
            wr_before = prev_root.get("winrate")
            wr_after = root_info.get("winrate")
            if sl_before is not None and sl_after is not None:
                before_w = float(sl_before) if prev_root.get("currentPlayer") == "W" else -float(sl_before)
                after_w = float(sl_after) if root_info.get("currentPlayer") == "W" else -float(sl_after)
                score_loss = round(max(0.0, before_w - after_w), 2)
            if wr_before is not None and wr_after is not None:
                before_w = float(wr_before) if prev_root.get("currentPlayer") == "W" else 1.0 - float(wr_before)
                after_w = float(wr_after) if root_info.get("currentPlayer") == "W" else 1.0 - float(wr_after)
                winrate_loss = round(max(0.0, before_w - after_w), 4)
        if played_info:
            prior = played_info.get("prior")
            human_prior = played_info.get("humanPrior")
        else:
            prior = None
            human_prior = None
        why: list[str] = []
        severity = severity_for(score_loss, winrate_loss)
        if score_loss is not None:
            if score_loss >= 8:
                why.append("score_loss_gt_8")
            elif score_loss >= 3:
                why.append("score_loss_gt_3")
            elif score_loss >= 1.5:
                why.append("score_loss_gt_1_5")
        if winrate_loss is not None and winrate_loss >= 0.08:
            why.append("winrate_loss_gt_8pct")
        if best and best.get("prior") is not None and best.get("humanPrior") is not None:
            gap = best["prior"] - best["humanPrior"]
            if gap > 0.15:
                why.append("hard_for_human_profile")
        if prior is not None and prior < 0.05:
            why.append("surprise_move")
        interest_score = (score_loss or 0) * 2 + (winrate_loss or 0) * 20
        if interest_score > 0.5 or why:
            moments.append({
                "turn": t,
                "move": actual.point,
                "color": actual.color,
                "severity": severity,
                "scoreLoss": score_loss,
                "winrateLoss": winrate_loss,
                "prior": prior,
                "humanPrior": human_prior,
                "bestMove": best.get("move") if best else None,
                "bestPrior": best.get("prior") if best else None,
                "bestHumanPrior": best.get("humanPrior") if best else None,
                "whyInteresting": why,
                "interestScore": round(interest_score, 2),
            })
    moments.sort(key=lambda m: -m["interestScore"])
    # Space out moments: prefer at least 3 turns apart
    selected: list[dict[str, Any]] = []
    for m in moments:
        if len(selected) >= max_items:
            break
        if all(abs(m["turn"] - s["turn"]) >= 3 for s in selected):
            selected.append(m)
    # Fill remaining if we have room and relaxed spacing
    if len(selected) < max_items:
        for m in moments:
            if m not in selected:
                selected.append(m)
                if len(selected) >= max_items:
                    break
    selected.sort(key=lambda m: m["turn"])
    return {"schemaVersion": "goteacher.scan.v1", "sgfPath": sgf_path, "profile": resolved_profile, "moves": total_moves, "moments": selected}


def severity_for(score_loss: float | None, winrate_loss: float | None) -> str:
    score = score_loss if score_loss is not None else 0.0
    winrate = winrate_loss if winrate_loss is not None else 0.0
    if score <= 0.5 and winrate <= 0.01:
        return "excellent"
    if score <= 1.5 and winrate <= 0.03:
        return "good"
    if score <= 3.0 or winrate <= 0.08:
        return "inaccuracy"
    if score <= 8.0 or winrate <= 0.18:
        return "mistake"
    return "blunder"


def _build_override(profile: str | None, human_explore: float | None, human_cpuct: float | None) -> dict[str, Any]:
    override: dict[str, Any] = {}
    if profile:
        override["humanSLProfile"] = profile
    if human_explore is not None:
        override["humanSLRootExploreProbWeightless"] = human_explore
    if human_cpuct is not None:
        override["humanSLCpuctPermanent"] = human_cpuct
    return override


async def _analyze(sgf_path: str, turn: int, profile: str | None, rules: str | None, komi: float | None, visits: int | None, no_cache: bool, refresh: bool, extra_move: str | None = None, human_explore: float | None = None, human_cpuct: float | None = None) -> tuple[Any, GameRecord]:
    cfg = config.load_config()
    record = parse_sgf_file(sgf_path)
    resolved_rules = rules or record.rules or cfg.default_rules
    resolved_komi = komi if komi is not None else (record.komi if record.komi is not None else cfg.default_komi)
    resolved_visits = visits or cfg.default_visits
    resolved_profile = normalize_profile(profile or cfg.default_human_profile)
    if resolved_profile:
        _valid, err = validate_profile(resolved_profile)
        if err:
            raise click.ClickException(err)
        if not cfg.human_model:
            raise click.ClickException("human profile requires a configured Human SL model; run init with --human-model")
    require_files(cfg.katago_config, cfg.engine_model)
    key_payload = {
        "sgf": str(Path(sgf_path).resolve()),
        "turn": turn,
        "extraMove": extra_move,
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
            return AnalysisResult.model_validate(cached), record
    query_moves = list(moves_until(record, turn))
    analyze_turns = [turn]
    actual = played_move_at(record, turn)
    if extra_move:
        # User wants to evaluate a specific move at this turn's position.
        # moves_until already includes the played move; we add the user's move after it.
        # The turn position already has the actual played move, so we analyze
        # the current turn (before user's move) and turn+1 (after user's move).
        next_color = "W" if actual and actual.color == "B" else "B"
        query_moves.append(Move(next_color, extra_move.upper()))
        analyze_turns.append(turn + 1)
    elif actual and turn > 0:
        # Evaluate the actual played move via rootInfo diff.
        # We need turn-1 (before the move) and turn (after the move).
        analyze_turns.insert(0, turn - 1)
    query = Query(
        id=key[:24],
        moves=query_moves,
        rules=resolved_rules,
        komi=resolved_komi,
        board_x_size=record.board_size,
        board_y_size=record.board_size,
        initial_stones=record.initial_stones,
        analyze_turns=analyze_turns,
        max_visits=resolved_visits,
        include_ownership=True,
        include_ownership_stdev=True,
        include_policy=True,
        override_settings=_build_override(resolved_profile, human_explore, human_cpuct),
    )
    engine = KataGoEngine(EngineConfig(binary=cfg.katago_binary, config_path=cfg.katago_config or "", model_path=cfg.engine_model or "", human_model_path=cfg.human_model))
    try:
        response = await engine.analyze(query)
    finally:
        await engine.close()
    result = normalize_response(response, app_config=cfg, record=record, sgf_path=sgf_path, turn=turn, profile=resolved_profile, visits=resolved_visits, rules=resolved_rules, komi=resolved_komi, extra_move=extra_move)
    if cfg.cache_enabled and not no_cache:
        cache.put(key, result.model_dump(by_alias=True, exclude_none=True))
    return result, record


if __name__ == "__main__":
    main()
