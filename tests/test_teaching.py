from goteacher.analysis.schema import Candidate
from goteacher.teaching.scoring import evaluate_played_move, score_teaching, severity_for


def test_severity_thresholds():
    assert severity_for(0.2, 0.005) == "excellent"
    assert severity_for(1.0, 0.02) == "good"
    assert severity_for(2.5, 0.07) == "inaccuracy"
    assert severity_for(6.0, 0.12) == "mistake"
    assert severity_for(9.0, 0.2) == "blunder"


def test_played_move_evaluation():
    candidates = [
        Candidate(move="D16", rankByVisits=1, visits=100, winrate=0.6, scoreLead=3.0, prior=0.08),
        Candidate(move="Q4", rankByVisits=2, visits=50, winrate=0.55, scoreLead=1.0, prior=0.2),
    ]
    played = evaluate_played_move("Q4", candidates)
    assert played.score_loss == 2.0
    assert round(played.winrate_loss, 2) == 0.05
    teaching = score_teaching(played, candidates)
    assert "policy_low_winrate_high" in teaching.categories
