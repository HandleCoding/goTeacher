from __future__ import annotations

from goteacher.analysis.schema import AnalysisResult


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
