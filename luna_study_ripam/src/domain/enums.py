# src/domain/enums.py
from __future__ import annotations

from enum import Enum


class TutorName(str, Enum):
    LUNA = "Luna"
    STELLA = "Stella"
    MARIA = "Maria"


class QuestionType(str, Enum):
    STANDARD = "standard"
    SITUAZIONALE = "situazionale"


class Outcome(str, Enum):
    CORRETTA = "corretta"
    ERRATA = "errata"
    OMESSA = "omessa"


class Efficacy(str, Enum):
    EFFICACE = "efficace"
    NEUTRA = "neutra"
    INEFFICACE = "inefficace"
