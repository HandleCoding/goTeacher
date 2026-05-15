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