from pathlib import Path

from goteacher.sgf.replay import parse_sgf_file, played_move_at


def test_parse_example_sgf():
    record = parse_sgf_file(Path(__file__).parents[1] / "testdata" / "example.sgf")
    assert record.board_size == 19
    assert record.komi == 7.5
    assert record.rules == "chinese"
    assert len(record.moves) == 5
    assert record.moves[0].point == "Q16"
    assert played_move_at(record, 2).point == "D16"
