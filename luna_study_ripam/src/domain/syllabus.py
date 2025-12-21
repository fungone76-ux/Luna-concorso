# src/domain/syllabus.py
from typing import Dict, List
import random

# Argomenti dettagliati basati sui quiz RIPAM reali
SYLLABUS_DETAILED: Dict[str, List[str]] = {
    "Diritto amministrativo": [
        "L. 241/1990: Responsabile del procedimento e conflitti di interesse",
        "L. 241/1990: Accesso agli atti (documentale, civico, generalizzato)",
        "L. 241/1990: Silenzio assenso e conferenza di servizi",
        "Atti amministrativi: elementi essenziali e vizi (nullità/annullabilità)",
        "Poteri di autotutela: revoca e annullamento d'ufficio",
        "DPR 445/2000: Autocertificazioni e dichiarazioni mendaci"
    ],
    "Diritto penale (PA)": [
        "Peculato e Peculato d'uso (art. 314 c.p.)",
        "Concussione e Induzione indebita (art. 317, 319-quater c.p.)",
        "Corruzione: propria, impropria e in atti giudiziari",
        "Abuso d'ufficio e Rifiuto di atti d'ufficio",
        "Differenza tra Pubblico Ufficiale e Incaricato di Pubblico Servizio"
    ],
    "Codice dell'Amministrazione Digitale (CAD)": [
        "Valore legale del documento informatico",
        "Firme elettroniche (FE, FEA, FEQ, Firma Digitale)",
        "PEC, Domicilio Digitale e INAD",
        "SPID, CIE e CNS (Sistemi di identità)",
        "Conservazione a norma e Responsabile della conservazione"
    ],
    "Sicurezza (D.Lgs. 81/2008)": [
        "Obblighi indelegabili del Datore di Lavoro",
        "Ruoli: RSPP, RLS, Preposto, Medico Competente",
        "Documento di Valutazione dei Rischi (DVR)",
        "DPI: classificazione e obblighi di utilizzo",
        "Gestione emergenze e primo soccorso"
    ],
    "Lavoro pubblico": [
        "D.Lgs 165/2001: Privatizzazione e contrattualizzazione",
        "Codice di comportamento (DPR 62/2013): doveri e regali",
        "Procedimento disciplinare: fasi e termini",
        "Whistleblowing nella PA",
        "Accesso al pubblico impiego e riserve"
    ],
    "Contabilità di Stato": [
        "Bilancio dello Stato: annualità, integrità, universalità",
        "Il ciclo della spesa: impegno, liquidazione, ordinazione, pagamento",
        "Residui attivi e passivi",
        "Responsabilità amministrativo-contabile e Corte dei Conti"
    ],
    "Beni culturali": [
        "Codice dei Beni Culturali: definizione di Bene Culturale",
        "Verifica dell'interesse culturale e vincolo",
        "Differenza tra Tutela e Valorizzazione",
        "Soprintendenze e Musei autonomi: competenze",
        "Art Bonus e mecenatismo"
    ],
    "Contratti pubblici": [
        "Codice Appalti (D.Lgs 36/2023): Principi (risultato, fiducia)",
        "RUP: Responsabile Unico del Progetto",
        "Soglie per affidamento diretto e procedure negoziate",
        "Criteri di aggiudicazione: OEPV vs Prezzo più basso",
        "Soccorso istruttorio"
    ],
    "Marketing e comunicazione PA": [
        "L. 150/2000: URP, Ufficio Stampa e Portavoce",
        "Comunicazione istituzionale vs politica",
        "Piano di comunicazione",
        "Accessibilità web e trasparenza"
    ],
    "Struttura MIC": [
        "Organizzazione centrale: Direzioni Generali",
        "Organizzazione periferica: Segretariati Regionali",
        "Musei e Parchi archeologici dotati di autonomia",
        "Competenze del Ministro vs Dirigenti"
    ]
}

def get_random_topic(subject: str) -> str:
    topics = SYLLABUS_DETAILED.get(subject)
    if topics:
        return random.choice(topics)
    return subject