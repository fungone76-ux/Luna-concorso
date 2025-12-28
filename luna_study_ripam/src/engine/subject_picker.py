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

# NUOVO: Sotto-argomenti COMPLETI per TUTTE le materie
SUB_TOPICS: Dict[str, List[str]] = {
    # --- AREA GIURIDICA ---
    "Diritto amministrativo": [
        "Legge 241/90: Principi generali e trasparenza",
        "Il Responsabile del Procedimento (RUP)",
        "Il Diritto di Accesso (Documentale, Civico, Generalizzato)",
        "Il Silenzio della PA (Silenzio assenso e rigetto)",
        "La Conferenza di Servizi",
        "Autotutela: Revoca e Annullamento d'ufficio",
        "Vizi dell'atto amministrativo (Nullità e Annullabilità)"
    ],
    "Diritto penale (PA)": [
        "I reati contro la Pubblica Amministrazione in generale",
        "Peculato e Peculato d'uso",
        "Concussione e Induzione indebita",
        "Corruzione (propria, impropria e in atti giudiziari)",
        "Abuso d'ufficio e Rifiuto di atti d'ufficio",
        "La qualifica di Pubblico Ufficiale e Incaricato di Pubblico Servizio"
    ],
    "Responsabilità del dipendente pubblico": [
        "Responsabilità civile, penale, amministrativa e contabile",
        "La responsabilità disciplinare e il codice di comportamento",
        "Il danno erariale e il ruolo della Corte dei Conti"
    ],
    "Lavoro pubblico": [
        "Diritti e doveri del dipendente pubblico",
        "Il Codice di Comportamento (DPR 62/2013)",
        "Il procedimento disciplinare: fasi e sanzioni",
        "Accesso al pubblico impiego e incompatibilità"
    ],
    "Contratti pubblici": [
        "Il Codice Appalti (D.Lgs 36/2023): Principi guida",
        "Le soglie per l'affidamento diretto",
        "Criteri di aggiudicazione: Prezzo vs Qualità",
        "Il RUP nel nuovo Codice Appalti",
        "Il Fascicolo Virtuale dell'Operatore Economico"
    ],

    # --- AREA CULTURA & MINISTERO ---
    "Beni culturali": [
        "Definizione di Bene Culturale (Codice Urbani)",
        "Tutela vs Valorizzazione: differenze concettuali",
        "Verifica dell'interesse culturale e Vincolo",
        "Soprintendenze e Musei autonomi: competenze",
        "Art Bonus e Mecenatismo culturale"
    ],
    "Struttura MIC": [
        "Organizzazione centrale: Segretariato e Direzioni Generali",
        "Organizzazione periferica: Segretariati Regionali",
        "Le Soprintendenze Archeologia, Belle Arti e Paesaggio",
        "I Musei dotati di autonomia speciale",
        "ALES S.p.A. e gli organismi collegati"
    ],
    "Marketing e comunicazione PA": [
        "Legge 150/2000: URP, Ufficio Stampa e Portavoce",
        "Comunicazione istituzionale vs Comunicazione politica",
        "Strumenti di promozione dei servizi culturali",
        "Social Media Policy nella PA"
    ],

    # --- AREA TECNICA & TRASVERSALE ---
    "Codice dell'Amministrazione Digitale (CAD)": [
        "Il Documento Informatico e le copie",
        "Le Firme Elettroniche (Semplice, Avanzata, Qualificata, Digitale)",
        "La PEC e il Domicilio Digitale",
        "Identità Digitale: SPID, CIE e CNS",
        "Il Responsabile per la Transizione al Digitale (RTD)"
    ],
    "Contabilità di Stato": [
        "Il Bilancio dello Stato: principi e struttura",
        "Le fasi dell'entrata e della spesa",
        "Il Rendiconto generale dello Stato",
        "Competenza e Cassa: differenze"
    ],
    "Diritto dell'Unione Europea": [
        "Le Istituzioni UE: Parlamento, Consiglio, Commissione",
        "Le Fonti del diritto UE: Regolamenti vs Direttive",
        "La Corte di Giustizia dell'Unione Europea",
        "Principi di sussidiarietà e proporzionalità"
    ],
    "Sicurezza (D.Lgs. 81/2008)": [
        "Obblighi del Datore di Lavoro e Delega di funzioni",
        "Figure chiave: RSPP, RLS e Medico Competente",
        "Documento di Valutazione dei Rischi (DVR)",
        "DPI (Dispositivi Protezione Individuale)",
        "Gestione delle emergenze e Primo Soccorso"
    ],

    # --- COMPETENZE BASE & LOGICA ---
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
        "Backup, Privacy e Protezione dati"
    ],
    "Inglese A2": [
        "Verb Tenses: Present Simple & Continuous",
        "Verb Tenses: Past Simple (Regular & Irregular)",
        "Question Words (Who, What, Where, When, How)",
        "Prepositions of Place and Time",
        "Modal Verbs (Can, Must, Should, Have to)",
        "Professional Vocabulary: Office & Meeting",
        "Museum & Tourism Vocabulary"
    ],
    "Quesiti situazionali": [
        "Gestione del conflitto con un collega",
        "Gestione di un utente/visitatore arrabbiato",
        "Priorità tra urgenza e procedura",
        "Rispetto della gerarchia e autonomia",
        "Lavoro in team e collaborazione"
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