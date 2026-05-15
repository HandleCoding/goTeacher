from __future__ import annotations

from goteacher.analysis.schema import Candidate, PlayedMoveEvaluation, TeachingSignal, TeachingSummary


def evaluate_played_move(played_move: str | None, candidates: list[Candidate]) -> PlayedMoveEvaluation:
    if not played_move:
        return PlayedMoveEvaluation(move=None)
    best = candidates[0] if candidates else None
    played = next((candidate for candidate in candidates if candidate.move == played_move), None)
    if played is None:
        return PlayedMoveEvaluation(move=played_move, scoreLoss=None, winrateLoss=None)
    score_loss = None
    winrate_loss = None
    if best and best.score_lead is not None and played.score_lead is not None:
        score_loss = max(0.0, best.score_lead - played.score_lead)
    if best and best.winrate is not None and played.winrate is not None:
        winrate_loss = max(0.0, best.winrate - played.winrate)
    return PlayedMoveEvaluation(
        move=played.move,
        rankByVisits=played.rank_by_visits,
        scoreLoss=score_loss,
        winrateLoss=winrate_loss,
        prior=played.prior,
        humanPrior=played.human_prior,
    )


def score_teaching(played: PlayedMoveEvaluation, candidates: list[Candidate]) -> TeachingSummary:
    if played.move and played.score_loss is None and played.winrate_loss is None:
        severity = "unknown"
        why = ["played_move_not_in_candidates"]
    else:
        severity = severity_for(played.score_loss, played.winrate_loss)
        why = []
    categories: list[str] = []
    signals: list[TeachingSignal] = []
    best = candidates[0] if candidates else None
    if best:
        category = policy_winrate_category(best.prior, best.winrate)
        if category:
            categories.append(category)
        if best.human_prior is not None and best.prior is not None:
            gap = max(0.0, (best.prior or 0.0) - (best.human_prior or 0.0))
            if gap > 0.15:
                signals.append(TeachingSignal(key="engine_human_gap", score=min(1.0, gap), evidence=["engine_prior_gt_human_prior"]))
                why.append("hard_for_human_profile")
        if best.prior is not None and best.prior < 0.1 and (best.winrate or 0) >= 0.55:
            signals.append(TeachingSignal(key="surprise", score=1.0 - best.prior, evidence=["best_move_prior_low"]))
            why.append("policy_low_but_engine_likes")
    if played.score_loss is not None:
        if played.score_loss >= 8:
            why.append("score_loss_gt_8")
        elif played.score_loss >= 3:
            why.append("score_loss_gt_3")
        elif played.score_loss >= 1.5:
            why.append("score_loss_gt_1_5")
    if played.winrate_loss is not None and played.winrate_loss >= 0.08:
        why.append("winrate_loss_gt_8pct")
    return TeachingSummary(severity=severity, categories=categories, signals=signals, whyInteresting=dedupe(why))


def severity_for(score_loss: float | None, winrate_loss: float | None) -> str:
    score = score_loss if score_loss is not None else 0.0
    winrate = winrate_loss if winrate_loss is not None else 0.0
    if score <= 0.5 and winrate <= 0.01:
        return "excellent"
    if score <= 1.5 and winrate <= 0.03:
        return "good"
    if score <= 3.0 or winrate <= 0.08:
        return "inaccuracy"
    if score <= 8.0 or winrate <= 0.18:
        return "mistake"
    return "blunder"


def policy_winrate_category(policy: float | None, winrate: float | None) -> str | None:
    if policy is None or winrate is None:
        return None
    policy_high = policy >= 0.15
    winrate_high = winrate >= 0.52
    if policy_high and winrate_high:
        return "policy_high_winrate_high"
    if policy_high and not winrate_high:
        return "policy_high_winrate_low"
    if not policy_high and winrate_high:
        return "policy_low_winrate_high"
    return "policy_low_winrate_low"


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result
