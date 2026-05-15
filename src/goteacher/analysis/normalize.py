from __future__ import annotations

from pathlib import Path
from typing import Any

from goteacher.analysis.schema import (
    AnalysisResult,
    Arrays,
    BoardArray,
    Candidate,
    EngineInfo,
    RequestInfo,
    RootEvaluation,
)
from goteacher.config import AppConfig
from goteacher.katago.protocol import analysis_for_turn
from goteacher.sgf.replay import GameRecord, played_move_at
from goteacher.teaching.scoring import evaluate_played_move, score_teaching


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
) -> AnalysisResult:
    analysis = analysis_for_turn(response, turn)
    root_info = analysis.get("rootInfo", {})
    move_infos = analysis.get("moveInfos", [])
    candidates = [_candidate_from_move_info(item, index + 1) for index, item in enumerate(move_infos)]
    actual = played_move_at(record, turn)
    played = evaluate_played_move(actual.point if actual else None, candidates)
    teaching = score_teaching(played, candidates)
    width = record.board_size
    height = record.board_size
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
            winrate=root_info.get("winrate"),
            scoreLead=root_info.get("scoreLead"),
            scoreStdev=root_info.get("scoreStdev"),
        ),
        playedMoveEvaluation=played,
        candidates=candidates,
        teaching=teaching,
        arrays=Arrays(
            policy=_board_array(analysis.get("policy"), width, height, policy=True),
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
        winrate=item.get("winrate"),
        scoreLead=item.get("scoreLead"),
        scoreStdev=item.get("scoreStdev"),
        prior=item.get("prior"),
        humanPrior=item.get("humanPrior"),
        pv=list(item.get("pv") or []),
    )


def _board_array(values: Any, width: int, height: int, policy: bool = False) -> BoardArray | None:
    if values is None:
        return None
    values = list(values)
    expected = width * height + (1 if policy else 0)
    if len(values) != expected:
        return None
    return BoardArray(width=width, height=height, values=values)
