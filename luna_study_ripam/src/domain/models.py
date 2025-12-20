# src/domain/models.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional


# --- Tipi base ---
TutorName = Literal["Luna", "Stella", "Maria"]
QuestionType = Literal["standard", "situazionale"]
Outcome = Literal["corretta", "errata", "omessa"]
Efficacy = Literal["efficace", "neutra", "inefficace"]


# --- Stato della sessione ---
@dataclass
class SessionState:
    # avanzamento test
    question_index: int = 0
    total_questions: int = 40
    time_left_sec: int = 60 * 60  # 60 minuti
    score: float = 0.0

    # progress & stage per tutor
    progress: Dict[TutorName, int] = field(
        default_factory=lambda: {"Luna": 0, "Stella": 0, "Maria": 0}
    )
    stage: Dict[TutorName, int] = field(
        default_factory=lambda: {"Luna": 1, "Stella": 1, "Maria": 1}
    )

    # anti-ripetizione / audit
    recent_fingerprints: List[str] = field(default_factory=list)
    recent_max: int = 30


# --- Domanda ---
@dataclass(frozen=True)
class Question:
    tutor: TutorName
    materia: str
    tipo: QuestionType

    domanda: str
    opzioni: Dict[str, str]  # {"A": "...", "B": "...", "C": "...", "D": "..."}

    # standard
    corretta: Optional[str] = None  # "A"/"B"/"C"/"D"

    # situazionale
    efficacia: Optional[Dict[str, Efficacy]] = None

    # --- metadata e prompt helper (dal tuo output_schema.json) ---
    difficulty: int = 1
    question_id: str = ""
    spiegazione_breve: str = ""
    tags: List[str] = field(default_factory=list)
    visual: str = ""


# --- Esito turno ---
@dataclass(frozen=True)
class TurnResult:
    tutor: TutorName
    outcome: Outcome

    delta_score: float
    new_score: float

    new_progress: int
    new_stage: int
