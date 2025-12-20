# src/engine/subject_picker.py
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class SubjectPickerConfig:
    """
    Quote/pesi di estrazione materie.
    I numeri non devono per forza sommare a 40: sono PESI relativi.

    Nota: nel bando si parla di un totale domande e di alcune macro-aree.
    Qui modelliamo in modo pratico:
    - Logica e Situazionali più frequenti
    - le altre distribuite
    """
    weights: Dict[str, float]
    avoid_repeat_window: int = 2       # evita la stessa materia nelle ultime N domande
    soft_reroll_attempts: int = 3      # tentativi per non ripetere (poi accetta)


DEFAULT_WEIGHTS: Dict[str, float] = {
    # blocco "più probabile"
    "Logica": 7.0,
    "Quesiti situazionali": 8.0,

    # informatica/inglese base
    "Informatica (TIC)": 2.0,
    "Inglese A2": 2.0,

    # area giuridico-amministrativa
    "Diritto amministrativo": 6.0,
    "Contratti pubblici": 3.0,
    "Sicurezza (D.Lgs. 81/2008)": 4.0,
    "Diritto penale (PA)": 3.0,
    "Lavoro pubblico": 3.0,
    "Responsabilità del dipendente pubblico": 2.0,

    # area cultura/istituzioni
    "Beni culturali": 4.0,
    "Struttura MIC": 2.0,
    "Diritto dell'Unione Europea": 2.0,
    "Marketing e comunicazione PA": 2.0,

    # CAD / contabilità (meno frequenti ma presenti)
    "Codice dell'Amministrazione Digitale (CAD)": 2.0,
    "Contabilità di Stato": 2.0,
}


class SubjectPicker:
    def __init__(self, cfg: Optional[SubjectPickerConfig] = None, seed: int = 42):
        if cfg is None:
            cfg = SubjectPickerConfig(weights=dict(DEFAULT_WEIGHTS))
        self.cfg = cfg
        self.rng = random.Random(seed)

    def pick(self, recent_subjects: Optional[List[str]] = None) -> str:
        """
        Estrae una materia secondo pesi.
        Se recent_subjects è fornito, prova a evitare ripetizioni ravvicinate.
        """
        recent_subjects = recent_subjects or []
        avoid = set(recent_subjects[-self.cfg.avoid_repeat_window:])

        subjects = list(self.cfg.weights.keys())
        weights = list(self.cfg.weights.values())

        # estrazione ponderata con soft-reroll anti ripetizione
        for _ in range(self.cfg.soft_reroll_attempts):
            chosen = self.rng.choices(subjects, weights=weights, k=1)[0]
            if chosen not in avoid:
                return chosen

        # se dopo N tentativi continua a ripetersi, accetta (meglio che bloccare)
        return self.rng.choices(subjects, weights=weights, k=1)[0]
