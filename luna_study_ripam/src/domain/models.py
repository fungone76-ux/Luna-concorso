# src/domain/models.py
from dataclasses import dataclass, field
from typing import Dict, List

TutorName = str
Outcome = str


@dataclass
class HistoryItem:
    tutor: str
    outcome: str


@dataclass
class LessonRecord:
    """Memorizza il risultato di una lezione completa."""
    topic: str
    tutor: str
    score: int


@dataclass
class Question:
    domanda: str
    opzioni: Dict[str, str]
    corretta: str
    spiegazione: str
    tutor: str
    materia: str
    tipo: str = "standard"
    tags: List[str] = field(default_factory=list)
    visual: str = ""
    spiegazione_breve: str = ""


@dataclass
class SessionState:
    progress: Dict[TutorName, int] = field(default_factory=dict)
    stage: Dict[TutorName, int] = field(default_factory=dict)
    history: List[HistoryItem] = field(default_factory=list)

    # MASTERCLASS STATE
    current_topic: str = ""
    current_tutor: str = ""
    quiz_counter: int = 0
    quiz_score: int = 0
    quiz_results: List[str] = field(default_factory=list)
    quiz_asked_questions: List[str] = field(default_factory=list)

    # NUOVO: Registro delle lezioni completate
    completed_lessons: List[LessonRecord] = field(default_factory=list)