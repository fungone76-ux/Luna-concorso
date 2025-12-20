# src/engine/tutor_router.py
from __future__ import annotations

from typing import Dict, Literal


TutorName = Literal["Luna", "Stella", "Maria"]


# Mappa materia -> tutor (coerente con il tuo GDD)
TUTOR_BY_SUBJECT: Dict[str, TutorName] = {
    # --- STELLA: logica/situazionali + informatica/inglese ---
    "Logica": "Stella",
    "Quesiti situazionali": "Stella",
    "Informatica (TIC)": "Stella",
    "Inglese A2": "Stella",
    "Codice dell'Amministrazione Digitale (CAD)": "Stella",

    # --- MARIA: rigore normativo / sicurezza / PA ---
    "Sicurezza (D.Lgs. 81/2008)": "Maria",
    "Diritto amministrativo": "Maria",
    "Contratti pubblici": "Maria",
    "Diritto penale (PA)": "Maria",
    "Lavoro pubblico": "Maria",
    "Responsabilità del dipendente pubblico": "Maria",

    # --- LUNA: cultura/istituzioni ---
    "Beni culturali": "Luna",
    "Struttura MIC": "Luna",
    "Diritto dell'Unione Europea": "Luna",
    "Marketing e comunicazione PA": "Luna",
    "Contabilità di Stato": "Luna",
}


def tutor_for_subject(subject: str) -> TutorName:
    """
    Ritorna la tutor associata alla materia.
    Fallback: Stella (default "neutra" e tecnica).
    """
    return TUTOR_BY_SUBJECT.get(subject, "Stella")
