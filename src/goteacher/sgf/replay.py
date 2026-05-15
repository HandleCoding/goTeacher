from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sgfmill import sgf

from goteacher.katago.protocol import Move


@dataclass(slots=True)
class GameRecord:
    board_size: int
    komi: float | None
    rules: str | None
    initial_stones: list[Move] = field(default_factory=list)
    moves: list[Move] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def parse_sgf_file(path: str | Path) -> GameRecord:
    data = Path(path).read_bytes()
    game = sgf.Sgf_game.from_bytes(data)
    size = game.get_size()
    root = game.get_root()
    komi = _float_prop(root, "KM")
    rules = _text_prop(root, "RU")
    initial_stones: list[Move] = []
    for prop, color in [("AB", "B"), ("AW", "W")]:
        for value in _raw_list_prop(root, prop):
            point = _sgf_point_to_katago(value, size)
            if point:
                initial_stones.append(Move(color, point))
    moves: list[Move] = []
    warnings: list[str] = []
    node = game.get_root()
    while True:
        children = list(node)
        if not children:
            break
        if len(children) > 1:
            warnings.append("sgf_variations_ignored_main_line_only")
        node = children[0]
        color, raw = node.get_move()
        if color is None:
            continue
        moves.append(Move(color.upper(), _sgf_tuple_to_katago(raw, size)))
    return GameRecord(board_size=size, komi=komi, rules=_normalize_rules(rules), initial_stones=initial_stones, moves=moves, warnings=warnings)


def moves_until(record: GameRecord, turn: int) -> list[Move]:
    if turn < 0:
        raise ValueError("turn must be non-negative")
    return record.moves[:turn]


def played_move_at(record: GameRecord, turn: int) -> Move | None:
    if turn <= 0 or turn > len(record.moves):
        return None
    return record.moves[turn - 1]


LETTERS = "ABCDEFGHJKLMNOPQRSTUVWXYZ"


def board_at(record: GameRecord, turn: int) -> list[list[str]]:
    """Return a size×size grid with 'B', 'W', or '.' for each intersection at the given turn."""
    size = record.board_size
    grid: list[list[str]] = [["." for _ in range(size)] for _ in range(size)]
    for stone in record.initial_stones:
        r, c = _katago_to_rc(stone.point, size)
        if r is not None:
            grid[r][c] = stone.color
    for move in record.moves[:turn]:
        if move.point == "pass":
            continue
        r, c = _katago_to_rc(move.point, size)
        if r is None:
            continue
        if move.color == "B":
            _place_black(grid, r, c, size)
        else:
            _place_white(grid, r, c, size)
    return grid


def _katago_to_rc(coord: str, size: int) -> tuple[int, int] | tuple[None, None]:
    if coord == "pass" or len(coord) < 2:
        return None, None
    col_letter = coord[0].upper()
    row_str = coord[1:]
    if col_letter not in LETTERS:
        return None, None
    col = LETTERS.index(col_letter)
    try:
        row_num = int(row_str)
    except ValueError:
        return None, None
    if col < 0 or col >= size or row_num < 1 or row_num > size:
        return None, None
    return size - row_num, col


def _place_black(grid: list[list[str]], row: int, col: int, size: int) -> None:
    grid[row][col] = "B"
    _remove_captures(grid, row, col, "W", size)


def _place_white(grid: list[list[str]], row: int, col: int, size: int) -> None:
    grid[row][col] = "W"
    _remove_captures(grid, row, col, "B", size)


def _remove_captures(grid: list[list[str]], row: int, col: int, opponent: str, size: int) -> None:
    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nr, nc = row + dr, col + dc
        if 0 <= nr < size and 0 <= nc < size and grid[nr][nc] == opponent:
            group, liberties = _flood(grid, nr, nc, opponent, size)
            if liberties == 0:
                for gr, gc in group:
                    grid[gr][gc] = "."


def _flood(grid: list[list[str]], row: int, col: int, color: str, size: int) -> tuple[list[tuple[int, int]], int]:
    visited: set[tuple[int, int]] = set()
    group: list[tuple[int, int]] = []
    liberties = 0
    stack = [(row, col)]
    while stack:
        r, c = stack.pop()
        if (r, c) in visited:
            continue
        visited.add((r, c))
        if grid[r][c] == ".":
            liberties += 1
            continue
        if grid[r][c] != color:
            continue
        group.append((r, c))
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < size and 0 <= nc < size and (nr, nc) not in visited:
                stack.append((nr, nc))
    return group, liberties


def _float_prop(node, name: str) -> float | None:
    try:
        value = node.get(name)
    except KeyError:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _text_prop(node, name: str) -> str | None:
    try:
        value = node.get(name)
    except KeyError:
        return None
    return str(value) if value is not None else None


def _raw_list_prop(node, name: str) -> list[bytes]:
    try:
        values = node.get_raw_list(name)
    except KeyError:
        return []
    return list(values)


def _sgf_point_to_katago(raw: bytes, size: int) -> str:
    if raw in {b"", b"tt"}:
        return "pass"
    text = raw.decode("ascii")
    if len(text) != 2:
        return "pass"
    col = ord(text[0]) - ord("a")
    row = ord(text[1]) - ord("a")
    return _coord_to_katago(col, row, size)


def _sgf_tuple_to_katago(raw: tuple[int, int] | None, size: int) -> str:
    if raw is None:
        return "pass"
    row_from_bottom, col = raw
    letters = "ABCDEFGHJKLMNOPQRSTUVWXYZ"
    if col < 0 or row_from_bottom < 0 or col >= size or row_from_bottom >= size:
        return "pass"
    return f"{letters[col]}{row_from_bottom + 1}"


def _coord_to_katago(col: int, row: int, size: int) -> str:
    letters = "ABCDEFGHJKLMNOPQRSTUVWXYZ"
    if col < 0 or row < 0 or col >= size or row >= size:
        return "pass"
    return f"{letters[col]}{size - row}"


def _normalize_rules(rules: str | None) -> str | None:
    if not rules:
        return None
    lowered = rules.lower()
    if "chinese" in lowered or lowered in {"cn", "zh"}:
        return "chinese"
    if "japanese" in lowered or lowered in {"jp", "ja"}:
        return "japanese"
    if "tromp" in lowered:
        return "tromp-taylor"
    return lowered
