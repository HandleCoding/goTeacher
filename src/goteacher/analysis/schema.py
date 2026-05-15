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
    winrate: float | None = None
    score_lead: float | None = Field(default=None, alias="scoreLead")
    score_stdev: float | None = Field(default=None, alias="scoreStdev")


class Candidate(BaseModel):
    move: str
    rank_by_visits: int = Field(alias="rankByVisits")
    visits: int = 0
    winrate: float | None = None
    score_lead: float | None = Field(default=None, alias="scoreLead")
    score_stdev: float | None = Field(default=None, alias="scoreStdev")
    prior: float | None = None
    human_prior: float | None = Field(default=None, alias="humanPrior")
    pv: list[str] = Field(default_factory=list)


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


class BoardArray(BaseModel):
    width: int
    height: int
    values: list[float]


class Arrays(BaseModel):
    policy: BoardArray | None = None
    ownership: BoardArray | None = None
    ownership_stdev: BoardArray | None = Field(default=None, alias="ownershipStdev")


class AnalysisResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_version: Literal["goteacher.analysis.v1"] = Field(default="goteacher.analysis.v1", alias="schemaVersion")
    request: RequestInfo
    engine: EngineInfo
    root: RootEvaluation
    played_move_evaluation: PlayedMoveEvaluation = Field(alias="playedMoveEvaluation")
    candidates: list[Candidate]
    teaching: TeachingSummary
    arrays: Arrays
    warnings: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)
