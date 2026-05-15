from __future__ import annotations

from goteacher.analysis.schema import AnalysisResult
from goteacher.sgf.replay import GameRecord, board_at


def render_json(result: AnalysisResult) -> str:
    return result.model_dump_json(by_alias=True, exclude_none=True, indent=2) + "\n"


def render_markdown(result: AnalysisResult) -> str:
    lines = [
        f"# GoTeacher Analysis: turn {result.request.turn}",
        "",
        f"- Rules: {result.request.rules}",
        f"- Komi: {result.request.komi}",
        f"- To play: {result.root.to_play or 'unknown'}",
        f"- Severity: {result.teaching.severity}",
    ]
    if result.played_move_evaluation.move:
        played = result.played_move_evaluation
        lines.extend([
            "",
            "## Played Move",
            f"- Move: {played.move}",
            f"- Rank by visits: {played.rank_by_visits or 'unknown'}",
            f"- Score loss: {played.score_loss if played.score_loss is not None else 'unknown'}",
            f"- Winrate loss: {played.winrate_loss if played.winrate_loss is not None else 'unknown'}",
        ])
    if result.candidates:
        lines.extend(["", "## Top Candidates"])
        for candidate in result.candidates[:5]:
            lines.append(f"- {candidate.move}: visits={candidate.visits}, winrate={candidate.winrate}, scoreLead={candidate.score_lead}, prior={candidate.prior}, humanPrior={candidate.human_prior}")
    if result.teaching.why_interesting:
        lines.extend(["", "## Teaching Focus"])
        for reason in result.teaching.why_interesting:
            lines.append(f"- {reason}")
    return "\n".join(lines) + "\n"


LETTERS = "ABCDEFGHJKLMNOPQRSTUVWXYZ"


def render_board(result: AnalysisResult, record: GameRecord) -> str:
    grid = board_at(record, result.request.turn)
    size = record.board_size
    phase = _phase_label(result.root.raw_var_time_left)
    sl = result.root.score_lead
    balance = _balance_label(sl, result.root.to_play)
    to_play = _color_cn(result.root.to_play)
    profile = result.request.human_profile or "未知棋力"
    lines = [
        f"当前局面（第{result.request.turn}手，轮到{to_play}棋）",
        "",
    ]
    header = "   " + " ".join(LETTERS[:size])
    lines.append(header)
    for row in range(size):
        row_num = size - row
        cells = []
        for col in range(size):
            v = grid[row][col]
            cells.append("●" if v == "B" else "○" if v == "W" else "·")
        lines.append(f"{row_num:2d} " + " ".join(cells))

    # Ownership territory summary
    if result.arrays.ownership:
        own_vals = result.arrays.ownership.values
        b_territory = sum(1 for v in own_vals if v > 0.7)
        w_territory = sum(1 for v in own_vals if v < -0.7)
        contested = sum(1 for v in own_vals if -0.7 <= v <= 0.7)
        lines.append("")
        lines.append(f"地域：黑方{b_territory}格、白方{w_territory}格、争夺中{contested}格")

    lines.append("")
    lines.append(f"阶段：{phase}（rawVarTimeLeft={result.root.raw_var_time_left}）")
    lines.append(f"形势：{balance}，引擎胜率{result.root.winrate}，scoreLead={result.root.score_lead}")
    if result.root.human_st_wr_error is not None:
        complexity = "高" if result.root.human_st_wr_error > 0.06 else "中等" if result.root.human_st_wr_error > 0.03 else "低"
        lines.append(f"复杂度：{complexity}（humanStWrError={result.root.human_st_wr_error:.3f}）")
    if result.root.human_winrate is not None:
        wr_diff = abs((result.root.winrate or 0) - result.root.human_winrate)
        lines.append(f"引擎胜率={result.root.winrate}，{profile}人类胜率={result.root.human_winrate}，差异={wr_diff:.3f}")

    # Played move evaluation
    if result.played_move_evaluation.move:
        pm = result.played_move_evaluation
        parts = [f"实战手：{pm.move}"]
        if pm.rank_by_visits is not None:
            parts.append(f"排名#{pm.rank_by_visits}")
        if pm.score_loss is not None:
            parts.append(f"损失{pm.score_loss:.2f}目")
        if pm.winrate_loss is not None:
            parts.append(f"胜率损失{pm.winrate_loss:.1%}")
        if pm.prior is not None:
            parts.append(f"引擎prior={pm.prior:.1%}")
        if pm.human_prior is not None:
            parts.append(f"人类prior={pm.human_prior:.1%}")
        parts.append(f"severity={result.teaching.severity}")
        lines.append("")
        lines.append(" ".join(parts))

    # Top 5 candidates comparison
    if result.candidates:
        lines.append("")
        lines.append(f"候选手（{to_play}棋可选）：")
        for c in result.candidates[:5]:
            c_parts = [f"  {c.move}"]
            if c.winrate is not None:
                c_parts.append(f"wr={c.winrate:.3f}")
            if c.score_lead is not None:
                c_parts.append(f"sl={c.score_lead:.2f}")
            if c.prior is not None:
                c_parts.append(f"引擎prior={c.prior:.1%}")
            if c.human_prior is not None:
                c_parts.append(f"人类prior={c.human_prior:.1%}")
            if c.visits:
                c_parts.append(f"visits={c.visits}")
            lines.append(" ".join(c_parts))

    # Human policy top - what humans at this rank typically play
    if result.human_policy_top.entries:
        lines.append("")
        lines.append(f"{profile}人类偏好分布：")
        for entry in result.human_policy_top.entries[:7]:
            parts = [f"  {entry.move}"]
            parts.append(f"人类={entry.human_prior:.1%}")
            if entry.prior is not None:
                parts.append(f"引擎={entry.prior:.1%}")
            lines.append(" ".join(parts))

    # Engine-human gap
    if result.summary.human_vs_engine_gap:
        lines.append("")
        lines.append(f"引擎-人类分歧：{result.summary.human_vs_engine_gap}")

    # Teaching focus
    if result.teaching.why_interesting:
        lines.append("")
        lines.append("教学重点：" + "、".join(result.teaching.why_interesting))

    return "\n".join(lines) + "\n"


def _phase_label(raw_var_time_left: float | None) -> str:
    if raw_var_time_left is None:
        return "未知"
    if raw_var_time_left > 30:
        return "布局"
    if raw_var_time_left > 5:
        return "中盘"
    return "官子"


def _balance_label(score_lead: float | None, to_play: str | None) -> str:
    if score_lead is None:
        return "未知"
    leader = "黑" if score_lead < 0 else "白"
    gap = abs(score_lead)
    if gap < 1:
        return "均衡"
    if gap < 5:
        return f"{leader}方微领{gap:.1f}目"
    if gap < 15:
        return f"{leader}方领先{gap:.1f}目"
    return f"{leader}方大优{gap:.1f}目"


def _color_cn(color: str | None) -> str:
    if color == "B":
        return "黑"
    if color == "W":
        return "白"
    return "未知"
