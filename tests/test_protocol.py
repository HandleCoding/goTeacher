from goteacher.katago.protocol import Move, Query, analysis_for_turn


def test_query_serializes_single_line():
    query = Query(
        id="abc",
        moves=[Move("B", "Q4")],
        rules="chinese",
        komi=7.5,
        board_x_size=19,
        board_y_size=19,
        analyze_turns=[1],
        override_settings={"humanSLProfile": "rank_5k"},
    )
    line = query.to_json_line()
    assert line.endswith(b"\n")
    assert line.count(b"\n") == 1
    assert b'"humanSLProfile":"rank_5k"' in line


def test_analysis_for_turn_nested_results():
    response = {"results": [{"turn": 3, "analysis": {"rootInfo": {"visits": 10}}}]}
    assert analysis_for_turn(response, 3)["rootInfo"]["visits"] == 10
