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
    """
    weights: Dict[str, float]
    avoid_repeat_window: int = 2  # evita la stessa materia nelle ultime N domande
    soft_reroll_attempts: int = 3  # tentativi per non ripetere (poi accetta)


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

    # CAD / contabilità
    "Codice dell'Amministrazione Digitale (CAD)": 2.0,
    "Contabilità di Stato": 2.0,
}


class SubjectPicker:
    def __init__(self, cfg: Optional[SubjectPickerConfig] = None, seed: int = 42):
        if cfg is None:
            cfg = SubjectPickerConfig(weights=dict(DEFAULT_WEIGHTS))
        self.cfg = cfg
        self.rng = random.Random(seed)

    def pick(self, recent_subjects: Optional[List[str]] = None, excluded_subjects: Optional[List[str]] = None) -> \
    Optional[str]:
        """
        Estrae una materia secondo pesi.
        - excluded_subjects: materie da NON estrarre mai (es. già superate con >= 8).
        - recent_subjects: materie fatte di recente (soft avoid).
        Ritorna None se non ci sono più materie disponibili.
        """
        recent_subjects = recent_subjects or []
        excluded_subjects = set(excluded_subjects or [])

        # Calcola avoid temporaneo (ultime N lezioni)
        avoid = set(recent_subjects[-self.cfg.avoid_repeat_window:])

        # Filtra le materie disponibili: togli quelle escluse
        available_subjects = [s for s in self.cfg.weights.keys() if s not in excluded_subjects]

        # Se non ci sono più materie (tutte completate con >= 8), ritorna None
        if not available_subjects:
            return None

        # Ricostruisce i pesi solo per le materie disponibili
        available_weights = [self.cfg.weights[s] for s in available_subjects]

        # Estrazione ponderata con tentativi per evitare le ripetizioni recenti
        for _ in range(self.cfg.soft_reroll_attempts):
            chosen = self.rng.choices(available_subjects, weights=available_weights, k=1)[0]
            if chosen not in avoid:
                return chosen

        # Se non riesce ad evitare le recenti, estrae comunque dalle disponibili
        return self.rng.choices(available_subjects, weights=available_weights, k=1)[0]