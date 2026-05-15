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
    lines = [
        f"当前局面（第{result.request.turn}手，轮到{_color_cn(result.root.to_play)}棋）",
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
    lines.append("")
    lines.append(f"阶段：{phase}（rawVarTimeLeft={result.root.raw_var_time_left}）")
    lines.append(f"形势：{balance}")
    if result.played_move_evaluation.move:
        pm = result.played_move_evaluation
        loss_str = f"损失约{pm.score_loss}目" if pm.score_loss is not None else "损失未知"
        lines.append(f"实战手：{pm.move}，{loss_str}，severity={result.teaching.severity}")
    if result.candidates:
        best = result.candidates[0]
        hp_str = f"，人类{result.request.human_profile}概率{int((best.human_prior or 0)*100)}%" if best.human_prior is not None else ""
        lines.append(f"推荐手：{best.move}（引擎prior={int((best.prior or 0)*100)}%{hp_str}）")
    if result.root.human_st_wr_error is not None:
        complexity = "高" if result.root.human_st_wr_error > 0.06 else "中等" if result.root.human_st_wr_error > 0.03 else "低"
        lines.append(f"复杂度：{complexity}（humanStWrError={result.root.human_st_wr_error:.3f}）")
    if result.teaching.why_interesting:
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
