# src/domain/rules.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class ExamRules:
    """
    Regole prova (derivate dal bando e dal tuo GDD).
    NOTA: il punteggio di soglia è espresso in /30.
    """
    total_questions: int = 40
    time_limit_minutes: int = 60

    # punteggio minimo per idoneità (espresso su scala /30)
    pass_mark_30: float = 21.0

    # punteggi per domanda standard (già applicati in scoring.py)
    correct_points: float = 0.75
    wrong_points: float = -0.25
    omitted_points: float = 0.0

    # situazionali (già applicati in scoring.py)
    situational_effective: float = 0.75
    situational_neutral: float = 0.375
    situational_ineffective: float = 0.0


def time_limit_seconds(rules: ExamRules) -> int:
    return rules.time_limit_minutes * 60


def is_passed(score_30: float, rules: ExamRules) -> bool:
    """Ritorna True se il punteggio raggiunge la soglia."""
    return score_30 >= rules.pass_mark_30


def clamp_score(score_30: float) -> float:
    """
    Clamp del punteggio:
    - può scendere sotto 0 in teoria (molti errori), ma per UI conviene clampare a 0.
    - non clampo a 30 perché il punteggio reale potrebbe teoricamente superare 30? (con questi valori no),
      ma lasciamo libero e clampiamo solo per barra.
    """
    return max(0.0, score_30)


def score_bar(
    score_30: float,
    rules: ExamRules,
    bar_min: float = 0.0,
    bar_max: float = 1.0,
) -> Tuple[float, float]:
    """
    Converte score (/30) in:
    - progress_bar (0..1)
    - pass_line_bar (0..1) posizione della soglia sulla barra

    Utile per UI "barra idoneità".
    """
    score_30 = clamp_score(score_30)

    # assumiamo scala 0..30
    progress = min(30.0, score_30) / 30.0
    pass_line = rules.pass_mark_30 / 30.0

    # rimappa su bar_min..bar_max
    progress_bar = bar_min + (bar_max - bar_min) * progress
    pass_line_bar = bar_min + (bar_max - bar_min) * pass_line

    return progress_bar, pass_line_bar
