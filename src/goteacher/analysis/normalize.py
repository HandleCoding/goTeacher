from __future__ import annotations

from pathlib import Path
from typing import Any

from goteacher.analysis.schema import (
    AnalysisResult,
    Arrays,
    BoardArray,
    Candidate,
    EngineInfo,
    HumanPolicyTop,
    PolicyEntry,
    RequestInfo,
    RootEvaluation,
)
from goteacher.config import AppConfig
from goteacher.katago.protocol import analysis_for_turn
from goteacher.sgf.replay import GameRecord, played_move_at
from goteacher.teaching.scoring import evaluate_played_move, score_teaching

LETTERS = "ABCDEFGHJKLMNOPQRSTUVWXYZ"


def _score_for_player(root_info: dict[str, Any]) -> float | None:
    sl = root_info.get("scoreLead")
    if sl is None:
        return None
    player = root_info.get("currentPlayer")
    return float(sl) if player == "W" else -float(sl)


def _winrate_for_player(root_info: dict[str, Any]) -> float | None:
    wr = root_info.get("winrate")
    if wr is None:
        return None
    player = root_info.get("currentPlayer")
    return float(wr) if player == "W" else 1.0 - float(wr)


def _compute_score_loss(before_root: dict[str, Any], after_root: dict[str, Any]) -> float | None:
    sl_before = _score_for_player(before_root)
    sl_after = _score_for_player(after_root)
    if sl_before is None or sl_after is None:
        return None
    return round(max(0.0, sl_before - sl_after), 4)


def _compute_winrate_loss(before_root: dict[str, Any], after_root: dict[str, Any]) -> float | None:
    wr_before = _winrate_for_player(before_root)
    wr_after = _winrate_for_player(after_root)
    if wr_before is None or wr_after is None:
        return None
    return round(max(0.0, wr_before - wr_after), 6)


def _coord_to_policy_index(coord: str, width: int, height: int) -> int | None:
    if coord == "pass":
        return width * height
    if len(coord) < 2:
        return None
    col_letter = coord[0].upper()
    row_str = coord[1:]
    if col_letter not in LETTERS:
        return None
    col = LETTERS.index(col_letter)
    try:
        row = int(row_str)
    except ValueError:
        return None
    if col < 0 or col >= width or row < 1 or row > height:
        return None
    return (height - row) * width + col


def _prior_from_policy(policy: Any, coord: str, width: int, height: int) -> float | None:
    if policy is None:
        return None
    idx = _coord_to_policy_index(coord, width, height)
    if idx is None or idx >= len(policy):
        return None
    val = policy[idx]
    return float(val) if val >= 0 else None


def normalize_response(
    response: dict[str, Any],
    *,
    app_config: AppConfig,
    record: GameRecord,
    sgf_path: str | None,
    turn: int,
    profile: str | None,
    visits: int,
    rules: str,
    komi: float,
    extra_move: str | None = None,
) -> AnalysisResult:
    analysis = analysis_for_turn(response, turn)
    root_info = analysis.get("rootInfo", {})
    move_infos = analysis.get("moveInfos", [])
    candidates = [_candidate_from_move_info(item, index + 1) for index, item in enumerate(move_infos)]
    actual = played_move_at(record, turn)
    played_coord = extra_move or (actual.point if actual else None)
    played = evaluate_played_move(played_coord, candidates)
    width = record.board_size
    height = record.board_size
    if played.move:
        if extra_move:
            # --move: analyzeTurns=[turn, turn+1], current turn is before the move
            next_analysis = analysis_for_turn(response, turn + 1)
            next_root = next_analysis.get("rootInfo", {}) if next_analysis else {}
            if next_root:
                played.score_loss = _compute_score_loss(root_info, next_root)
                played.winrate_loss = _compute_winrate_loss(root_info, next_root)
            if played.prior is None:
                played.prior = _prior_from_policy(analysis.get("policy"), played.move, width, height)
            if played.human_prior is None:
                played.human_prior = _prior_from_policy(analysis.get("humanPolicy"), played.move, width, height)
        else:
            # Normal: analyzeTurns=[turn-1, turn], turn-1 is before the move
            prev_analysis = analysis_for_turn(response, turn - 1) if turn > 0 else None
            prev_root = prev_analysis.get("rootInfo", {}) if prev_analysis else {}
            if played.score_loss is None and prev_root:
                played.score_loss = _compute_score_loss(prev_root, root_info)
                played.winrate_loss = _compute_winrate_loss(prev_root, root_info)
            if played.prior is None:
                played.prior = _prior_from_policy(prev_analysis.get("policy") if prev_analysis else None, played.move, width, height)
            if played.human_prior is None:
                played.human_prior = _prior_from_policy(prev_analysis.get("humanPolicy") if prev_analysis else None, played.move, width, height)
    teaching = score_teaching(played, candidates)
    width = record.board_size
    height = record.board_size
    human_policy_top = _human_policy_top(analysis.get("humanPolicy"), analysis.get("policy"), width, height)
    return AnalysisResult(
        request=RequestInfo(
            source="sgf" if sgf_path else "position",
            sgfPath=sgf_path,
            turn=turn,
            rules=rules,
            komi=komi,
            boardSize=(width, height),
            humanProfile=profile,
            visits=visits,
        ),
        engine=EngineInfo(
            katagoBinary=app_config.katago_binary,
            engineModel=app_config.engine_model,
            humanModel=app_config.human_model,
            config=app_config.katago_config,
        ),
        root=RootEvaluation(
            toPlay=root_info.get("currentPlayer"),
            visits=int(root_info.get("visits") or 0),
            weight=root_info.get("weight"),
            winrate=root_info.get("winrate"),
            scoreLead=root_info.get("scoreLead"),
            scoreStdev=root_info.get("scoreStdev"),
            utility=root_info.get("utility"),
            rawWinrate=root_info.get("rawWinrate"),
            rawLead=root_info.get("rawLead"),
            rawVarTimeLeft=root_info.get("rawVarTimeLeft"),
            rawStWrError=root_info.get("rawStWrError"),
            rawStScoreError=root_info.get("rawStScoreError"),
            rawNoResultProb=root_info.get("rawNoResultProb"),
            humanWinrate=root_info.get("humanWinrate"),
            humanScoreMean=root_info.get("humanScoreMean"),
            humanScoreStdev=root_info.get("humanScoreStdev"),
            humanStWrError=root_info.get("humanStWrError"),
            humanStScoreError=root_info.get("humanStScoreError"),
            symHash=root_info.get("symHash"),
            thisHash=root_info.get("thisHash"),
        ),
        playedMoveEvaluation=played,
        candidates=candidates,
        humanPolicyTop=human_policy_top,
        teaching=teaching,
        arrays=Arrays(
            policy=_board_array(analysis.get("policy"), width, height, policy=True),
            humanPolicy=_board_array(analysis.get("humanPolicy"), width, height, policy=True),
            ownership=_board_array(analysis.get("ownership"), width, height),
            ownershipStdev=_board_array(analysis.get("ownershipStdev"), width, height),
        ),
        warnings=record.warnings,
        raw={"katagoResponseId": response.get("id") or analysis.get("id")},
    )


def _candidate_from_move_info(item: dict[str, Any], rank: int) -> Candidate:
    return Candidate(
        move=item.get("move", ""),
        rankByVisits=rank,
        visits=int(item.get("visits") or 0),
        weight=item.get("weight"),
        edgeVisits=item.get("edgeVisits"),
        edgeWeight=item.get("edgeWeight"),
        winrate=item.get("winrate"),
        scoreLead=item.get("scoreLead"),
        scoreStdev=item.get("scoreStdev"),
        utility=item.get("utility"),
        utilityLcb=item.get("utilityLcb"),
        lcb=item.get("lcb"),
        prior=item.get("prior"),
        humanPrior=item.get("humanPrior"),
        pv=list(item.get("pv") or []),
        order=item.get("order"),
        playSelectionValue=item.get("playSelectionValue"),
    )


def _board_array(values: Any, width: int, height: int, policy: bool = False) -> BoardArray | None:
    if values is None:
        return None
    values = list(values)
    expected = width * height + (1 if policy else 0)
    if len(values) != expected:
        return None
    return BoardArray(width=width, height=height, values=values)


def _human_policy_top(human_policy: Any, engine_policy: Any, width: int, height: int) -> HumanPolicyTop:
    if human_policy is None:
        return HumanPolicyTop()
    hp = list(human_policy)
    ep = list(engine_policy) if engine_policy else []
    if len(hp) != width * height + 1:
        return HumanPolicyTop()
    paired: list[tuple[str, float, float | None]] = []
    for idx in range(width * height):
        col = idx % width
        row = idx // width
        coord = f"{LETTERS[col]}{height - row}"
        hp_val = hp[idx]
        ep_val = ep[idx] if idx < len(ep) else None
        if hp_val < 0:
            continue
        paired.append((coord, float(hp_val), float(ep_val) if ep_val is not None and ep_val >= 0 else None))
    paired.sort(key=lambda x: -x[1])
    entries = [PolicyEntry(move=coord, prior=ep_val if ep_val is not None else 0.0, humanPrior=hp_val) for coord, hp_val, ep_val in paired[:10]]
    return HumanPolicyTop(entries=entries)