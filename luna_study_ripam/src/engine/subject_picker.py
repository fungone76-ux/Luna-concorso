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

# NUOVO: Sotto-argomenti per lezioni specifiche
SUB_TOPICS: Dict[str, List[str]] = {
    "Diritto amministrativo": [
        "Legge 241/90: Principi generali e trasparenza",
        "Il Responsabile del Procedimento (RUP)",
        "Il Diritto di Accesso (Documentale, Civico, Generalizzato)",
        "Il Silenzio della PA (Silenzio assenso e rigetto)",
        "La Conferenza di Servizi",
        "Autotutela: Revoca e Annullamento d'ufficio",
        "Vizi dell'atto amministrativo (Nullità e Annullabilità)"
    ],
    "Logica": [
        "Sillogismi e deduzioni logiche",
        "Serie numeriche e alfabetiche",
        "Comprensione verbale e analisi brani",
        "Logica figurale e spaziale",
        "Insiemistica e diagrammi di Venn",
        "Condizioni necessarie e sufficienti"
    ],
    "Informatica (TIC)": [
        "Hardware e Software: definizioni base",
        "Reti di calcolatori, Internet e Cloud",
        "Sicurezza informatica, Malware e Phishing",
        "Il pacchetto Office: Word, Excel, PowerPoint",
        "Posta Elettronica Certificata (PEC) e Firme Digitali"
    ],
    "Inglese A2": [
        "Verb Tenses: Present Simple & Continuous",
        "Verb Tenses: Past Simple (Regular & Irregular)",
        "Question Words (Who, What, Where, When, How)",
        "Prepositions of Place and Time (in, on, at, under)",
        "Modal Verbs (Can, Must, Should, Have to)",
        "Quantifiers (Much, Many, Some, Any, A lot of)",
        "Professional Vocabulary: Office & Meeting",
        "Museum & Tourism Vocabulary",
        "Reading Comprehension: Short Emails"
    ],
    "Beni culturali": [
        "Definizione di Bene Culturale (Codice Urbani)",
        "Tutela vs Valorizzazione: differenze",
        "Verifica dell'interesse culturale e Vincolo",
        "Soprintendenze e Musei autonomi",
        "Art Bonus e Mecenatismo culturale"
    ],
    "Sicurezza (D.Lgs. 81/2008)": [
        "Obblighi del Datore di Lavoro e Delega",
        "Figure chiave: RSPP, RLS e Medico Competente",
        "Documento di Valutazione dei Rischi (DVR)",
        "DPI (Dispositivi Protezione Individuale)",
        "Gestione delle emergenze e Primo Soccorso"
    ],
    "Contratti pubblici": [
        "Il Codice Appalti (D.Lgs 36/2023): Principi guida",
        "Le soglie per l'affidamento diretto",
        "Criteri di aggiudicazione: Prezzo vs Qualità",
        "Il Fascicolo Virtuale dell'Operatore Economico"
    ],
    "Lavoro pubblico": [
        "Diritti e doveri del dipendente pubblico",
        "Il Codice di Comportamento (DPR 62/2013)",
        "Il procedimento disciplinare",
        "Accesso al pubblico impiego (Concorsi)"
    ]
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
        Estrae una materia secondo pesi e, se disponibile, un sotto-argomento.
        - excluded_subjects: materie da NON estrarre mai (es. già superate con >= 8).
        - recent_subjects: materie fatte di recente (soft avoid).
        """
        recent_subjects = recent_subjects or []
        excluded_subjects = set(excluded_subjects or [])

        # 1. Pulisce la history per considerare solo la "macro" materia ai fini dell'avoid
        # (Se l'history contiene "Logica: Sillogismi", noi guardiamo solo "Logica")
        clean_recent = []
        for s in recent_subjects:
            if ":" in s:
                clean_recent.append(s.split(":")[0])
            else:
                clean_recent.append(s)

        # 1b. Pulisce anche le excluded (se per caso contengono i due punti)
        clean_excluded = set()
        for s in excluded_subjects:
            if ":" in s:
                clean_excluded.add(s.split(":")[0])
            else:
                clean_excluded.add(s)

        # 2. Calcola avoid temporaneo
        avoid = set(clean_recent[-self.cfg.avoid_repeat_window:])

        # 3. Filtra le materie disponibili
        available_subjects = [s for s in self.cfg.weights.keys() if s not in clean_excluded]

        if not available_subjects:
            return None

        available_weights = [self.cfg.weights[s] for s in available_subjects]

        chosen_macro = None

        # 4. Estrazione con tentativi di avoid
        for _ in range(self.cfg.soft_reroll_attempts):
            candidate = self.rng.choices(available_subjects, weights=available_weights, k=1)[0]
            if candidate not in avoid:
                chosen_macro = candidate
                break

        if not chosen_macro:
            chosen_macro = self.rng.choices(available_subjects, weights=available_weights, k=1)[0]

        # 5. Selezione del Sotto-Argomento (se esiste)
        if chosen_macro in SUB_TOPICS:
            specific_topic = self.rng.choice(SUB_TOPICS[chosen_macro])
            return f"{chosen_macro}: {specific_topic}"

        return chosen_macro