from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

Color = str


@dataclass(slots=True)
class Move:
    color: Color
    point: str

    def as_katago(self) -> list[str]:
        return [self.color, self.point]


@dataclass(slots=True)
class Query:
    id: str
    moves: list[Move]
    rules: str
    board_x_size: int
    board_y_size: int
    komi: float | None = None
    initial_stones: list[Move] = field(default_factory=list)
    initial_player: Color | None = None
    analyze_turns: list[int] = field(default_factory=list)
    max_visits: int | None = None
    include_ownership: bool = True
    include_ownership_stdev: bool = True
    include_policy: bool = True
    override_settings: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        if not self.id:
            raise ValueError("query id is required")
        if not self.rules:
            raise ValueError("rules are required")
        if self.board_x_size <= 0 or self.board_y_size <= 0:
            raise ValueError("board size must be positive")
        payload: dict[str, Any] = {
            "id": self.id,
            "moves": [move.as_katago() for move in self.moves],
            "rules": self.rules,
            "boardXSize": self.board_x_size,
            "boardYSize": self.board_y_size,
        }
        if self.komi is not None:
            payload["komi"] = self.komi
        if self.initial_stones:
            payload["initialStones"] = [move.as_katago() for move in self.initial_stones]
        if self.initial_player:
            payload["initialPlayer"] = self.initial_player
        if self.analyze_turns:
            payload["analyzeTurns"] = self.analyze_turns
        if self.max_visits:
            payload["maxVisits"] = self.max_visits
        if self.include_ownership:
            payload["includeOwnership"] = True
        if self.include_ownership_stdev:
            payload["includeOwnershipStdev"] = True
        if self.include_policy:
            payload["includePolicy"] = True
        if self.override_settings:
            payload["overrideSettings"] = self.override_settings
        return payload

    def to_json_line(self) -> bytes:
        data = json.dumps(self.to_payload(), separators=(",", ":"), ensure_ascii=True)
        if "\n" in data or "\r" in data:
            raise ValueError("query must serialize to one JSON line")
        return (data + "\n").encode("utf-8")


def parse_response_line(line: bytes) -> dict[str, Any]:
    line = line.strip()
    if not line:
        raise ValueError("empty KataGo response")
    return json.loads(line)


def analysis_for_turn(response: dict[str, Any], turn: int | None = None) -> dict[str, Any]:
    results = response.get("results")
    if not results:
        return response
    if turn is None:
        return results[-1].get("analysis", {})
    for item in results:
        if item.get("turn") == turn:
            return item.get("analysis", {})
    raise ValueError(f"analysis for turn {turn} not found")
