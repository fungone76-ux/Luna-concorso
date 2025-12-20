# src/engine/scoring.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Literal, Optional


QuestionType = Literal["standard", "situazionale"]
Outcome = Literal["corretta", "errata", "omessa"]
Efficacy = Literal["efficace", "neutra", "inefficace"]


@dataclass(frozen=True)
class ScoreConfig:
    """
    Regole punteggio (bando):
    - standard: corretta +0.75, errata -0.25, omessa 0
    - situazionale: efficace +0.75, neutra +0.375, inefficace 0
    """
    standard_correct: float = 0.75
    standard_wrong: float = -0.25
    standard_omitted: float = 0.0

    situational_effective: float = 0.75
    situational_neutral: float = 0.375
    situational_ineffective: float = 0.0


@dataclass(frozen=True)
class ScoreResult:
    outcome: Outcome
    delta: float


def evaluate_standard_answer(
    user_choice: Optional[str],
    correct_choice: str,
    cfg: ScoreConfig = ScoreConfig(),
) -> ScoreResult:
    """
    user_choice: "A"/"B"/"C"/"D" oppure None/"" per omessa
    correct_choice: "A"/"B"/"C"/"D"
    """
    if not user_choice:
        return ScoreResult(outcome="omessa", delta=cfg.standard_omitted)

    user_choice = user_choice.strip().upper()
    correct_choice = correct_choice.strip().upper()

    if user_choice == correct_choice:
        return ScoreResult(outcome="corretta", delta=cfg.standard_correct)
    return ScoreResult(outcome="errata", delta=cfg.standard_wrong)


def evaluate_situational_answer(
    user_choice: Optional[str],
    efficacy_by_option: Dict[str, Efficacy],
    cfg: ScoreConfig = ScoreConfig(),
) -> ScoreResult:
    """
    Nei situazionali NON serve "corretta": conta l'efficacia dell'opzione scelta.
    efficacy_by_option: {"A":"efficace","B":"neutra","C":"inefficace","D":"neutra"} ecc.
    """
    if not user_choice:
        return ScoreResult(outcome="omessa", delta=cfg.standard_omitted)

    key = user_choice.strip().upper()
    efficacy = efficacy_by_option.get(key)

    if efficacy == "efficace":
        return ScoreResult(outcome="corretta", delta=cfg.situational_effective)

    if efficacy == "neutra":
        # è “neutra”: punti dimezzati rispetto a efficace
        # outcome la trattiamo come errata (non perfetta), ma con delta positivo
        return ScoreResult(outcome="errata", delta=cfg.situational_neutral)

    # inefficace o mancante -> 0
    return ScoreResult(outcome="errata", delta=cfg.situational_ineffective)


def evaluate_answer(
    qtype: QuestionType,
    user_choice: Optional[str],
    correct_choice: Optional[str] = None,
    efficacy_by_option: Optional[Dict[str, Efficacy]] = None,
    cfg: ScoreConfig = ScoreConfig(),
) -> ScoreResult:
    """
    Router unico:
    - standard -> usa correct_choice
    - situazionale -> usa efficacy_by_option
    """
    if qtype == "standard":
        if not correct_choice:
            raise ValueError("correct_choice è obbligatorio per domande standard.")
        return evaluate_standard_answer(user_choice, correct_choice, cfg)

    if not efficacy_by_option:
        raise ValueError("efficacy_by_option è obbligatorio per domande situazionali.")
    return evaluate_situational_answer(user_choice, efficacy_by_option, cfg)


# Test rapido: python -m src.engine.scoring (se hai __init__.py) oppure esegui il file
if __name__ == "__main__":
    cfg = ScoreConfig()

    # standard
    print(evaluate_answer("standard", "A", correct_choice="A", cfg=cfg))  # +0.75
    print(evaluate_answer("standard", "B", correct_choice="A", cfg=cfg))  # -0.25
    print(evaluate_answer("standard", None, correct_choice="A", cfg=cfg))  # 0.0

    # situazionale
    eff = {"A": "efficace", "B": "neutra", "C": "inefficace", "D": "neutra"}
    print(evaluate_answer("situazionale", "A", efficacy_by_option=eff, cfg=cfg))  # +0.75
    print(evaluate_answer("situazionale", "B", efficacy_by_option=eff, cfg=cfg))  # +0.375
    print(evaluate_answer("situazionale", "C", efficacy_by_option=eff, cfg=cfg))  # 0.0
    print(evaluate_answer("situazionale", None, efficacy_by_option=eff, cfg=cfg))  # 0.0
