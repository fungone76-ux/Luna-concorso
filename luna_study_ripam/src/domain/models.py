from dataclasses import dataclass, field
from typing import Dict, List, Optional

# Alias per chiarezza
TutorName = str
Outcome = str  # "corretta", "errata", "omessa"


@dataclass
class HistoryItem:
    """Registra l'esito di una singola risposta."""
    tutor: str
    outcome: str


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
    # Campo opzionale per l'interfaccia, non sempre presente nel JSON puro
    spiegazione_breve: str = ""


@dataclass
class SessionState:
    """Lo stato globale della partita."""
    # Mappa Tutor -> Punti (es. {"Maria": 12})
    progress: Dict[TutorName, int] = field(default_factory=dict)

    # Mappa Tutor -> Stage (es. {"Maria": 2})
    stage: Dict[TutorName, int] = field(default_factory=dict)

    # Lista degli ultimi eventi (es. per sapere se l'ultima è stata errata)
    history: List[HistoryItem] = field(default_factory=list)