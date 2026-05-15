from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class RequestInfo(BaseModel):
    source: str
    sgf_path: str | None = Field(default=None, alias="sgfPath")
    turn: int
    rules: str
    komi: float
    board_size: tuple[int, int] = Field(alias="boardSize")
    human_profile: str | None = Field(default=None, alias="humanProfile")
    visits: int


class EngineInfo(BaseModel):
    katago_binary: str = Field(alias="katagoBinary")
    engine_model: str | None = Field(default=None, alias="engineModel")
    human_model: str | None = Field(default=None, alias="humanModel")
    config: str | None = None


class RootEvaluation(BaseModel):
    to_play: str | None = Field(default=None, alias="toPlay")
    visits: int = 0
    weight: float | None = None
    winrate: float | None = None
    score_lead: float | None = Field(default=None, alias="scoreLead")
    score_stdev: float | None = Field(default=None, alias="scoreStdev")
    utility: float | None = None
    raw_winrate: float | None = Field(default=None, alias="rawWinrate")
    raw_lead: float | None = Field(default=None, alias="rawLead")
    raw_var_time_left: float | None = Field(default=None, alias="rawVarTimeLeft")
    raw_st_wr_error: float | None = Field(default=None, alias="rawStWrError")
    raw_st_score_error: float | None = Field(default=None, alias="rawStScoreError")
    raw_no_result_prob: float | None = Field(default=None, alias="rawNoResultProb")
    human_winrate: float | None = Field(default=None, alias="humanWinrate")
    human_score_mean: float | None = Field(default=None, alias="humanScoreMean")
    human_score_stdev: float | None = Field(default=None, alias="humanScoreStdev")
    human_st_wr_error: float | None = Field(default=None, alias="humanStWrError")
    human_st_score_error: float | None = Field(default=None, alias="humanStScoreError")
    sym_hash: str | None = Field(default=None, alias="symHash")
    this_hash: str | None = Field(default=None, alias="thisHash")


class Candidate(BaseModel):
    move: str
    rank_by_visits: int = Field(alias="rankByVisits")
    visits: int = 0
    weight: float | None = None
    edge_visits: int | None = Field(default=None, alias="edgeVisits")
    edge_weight: float | None = Field(default=None, alias="edgeWeight")
    winrate: float | None = None
    score_lead: float | None = Field(default=None, alias="scoreLead")
    score_stdev: float | None = Field(default=None, alias="scoreStdev")
    utility: float | None = None
    utility_lcb: float | None = Field(default=None, alias="utilityLcb")
    lcb: float | None = None
    prior: float | None = None
    human_prior: float | None = Field(default=None, alias="humanPrior")
    pv: list[str] = Field(default_factory=list)
    order: int | None = None
    play_selection_value: float | None = Field(default=None, alias="playSelectionValue")


class PlayedMoveEvaluation(BaseModel):
    move: str | None = None
    rank_by_visits: int | None = Field(default=None, alias="rankByVisits")
    score_loss: float | None = Field(default=None, alias="scoreLoss")
    winrate_loss: float | None = Field(default=None, alias="winrateLoss")
    prior: float | None = None
    human_prior: float | None = Field(default=None, alias="humanPrior")


class TeachingSignal(BaseModel):
    key: str
    score: float
    evidence: list[str] = Field(default_factory=list)


class TeachingSummary(BaseModel):
    threshold_version: str = Field(default="v1", alias="thresholdVersion")
    severity: str
    categories: list[str] = Field(default_factory=list)
    signals: list[TeachingSignal] = Field(default_factory=list)
    why_interesting: list[str] = Field(default_factory=list, alias="whyInteresting")


class PolicyEntry(BaseModel):
    move: str
    prior: float
    human_prior: float | None = Field(default=None, alias="humanPrior")


class BoardArray(BaseModel):
    width: int
    height: int
    values: list[float]


class Arrays(BaseModel):
    policy: BoardArray | None = None
    human_policy: BoardArray | None = Field(default=None, alias="humanPolicy")
    ownership: BoardArray | None = None
    ownership_stdev: BoardArray | None = Field(default=None, alias="ownershipStdev")


class HumanPolicyTop(BaseModel):
    entries: list[PolicyEntry] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_version: Literal["goteacher.analysis.v1"] = Field(default="goteacher.analysis.v1", alias="schemaVersion")
    request: RequestInfo
    engine: EngineInfo
    root: RootEvaluation
    played_move_evaluation: PlayedMoveEvaluation = Field(alias="playedMoveEvaluation")
    candidates: list[Candidate]
    human_policy_top: HumanPolicyTop = Field(default_factory=HumanPolicyTop, alias="humanPolicyTop")
    teaching: TeachingSummary
    arrays: Arrays
    warnings: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)