# src/engine/exam_engine.py
import random
import time
import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

from src.domain.models import Question
from src.ai.gemini_client import GeminiClient
from src.ai.prompt_builder import build_question_prompt, PromptBuildConfig
from src.engine.scoring import ScoreConfig
from src.domain.syllabus import get_random_topic
from src.engine.tutor_router import tutor_for_subject
from src.engine.subject_picker import SUB_TOPICS


@dataclass
class ExamSession:
    questions: List[Question] = field(default_factory=list)
    answers: Dict[int, str] = field(default_factory=dict)
    current_index: int = 0
    start_time: float = 0.0
    duration_seconds: int = 3600
    subject_roadmap: List[str] = field(default_factory=list)


class ExamEngine:
    def __init__(self, project_root: str, gemini: GeminiClient):
        self.project_root = project_root
        self.gemini = gemini

    def start_exam(self) -> ExamSession:
        roadmap = []

        # --- BLOCCO 1: 10 QUESITI COMUNI (Art. 6 Bando) ---
        # Include: Amministrativo, Penale, CAD, UE, Contabilità, Inglese, Informatica
        pool_common = [
            "Diritto amministrativo",
            "Diritto penale (PA)",
            "Codice dell'Amministrazione Digitale (CAD)",
            "Diritto dell'Unione Europea",
            "Contabilità di Stato",
            "Inglese A2",  # Spostato qui da Logica (come da bando)
            "Informatica (TIC)",  # Spostato qui da Logica (come da bando)
            "Lavoro pubblico",  # Sottoinsieme di Amministrativo
            "Responsabilità del dipendente pubblico",  # Sottoinsieme di Amministrativo
            "Contratti pubblici"  # Sottoinsieme di Amministrativo
        ]
        # Ne estraiamo 10 garantendo varietà
        for _ in range(10):
            roadmap.append(random.choice(pool_common))

        # --- BLOCCO 2: 15 QUESITI SPECIFICI (Profilo 01 - Accoglienza/Vigilanza) ---
        # Nota: Se stai preparando il Profilo 02, dobbiamo cambiare questa lista.
        pool_specific_01 = [
            "Sicurezza (D.Lgs. 81/2008)",
            "Marketing e comunicazione PA",
            "Beni culturali",  # Elementi di diritto del patrimonio e nozioni
            "Struttura MIC"
        ]
        # Ne estraiamo 15. Dato che sono poche materie, si ripeteranno (es. 4 domande di sicurezza, 4 di beni culturali...)
        for _ in range(15):
            roadmap.append(random.choice(pool_specific_01))

        # --- BLOCCO 3: 7 QUESITI LOGICA ---
        # Solo Logica deduttiva e Ragionamento critico-verbale (NO Inglese/IT qui)
        pool_logic = ["Logica", "Ragionamento critico-verbale"]
        for _ in range(7):
            roadmap.append(random.choice(pool_logic))

        # --- BLOCCO 4: 8 QUESITI SITUAZIONALI ---
        for _ in range(8):
            roadmap.append("Quesiti situazionali")

        # Mischiamo solo i primi tre blocchi (32 domande) per realismo,
        # lasciando i situazionali in fondo o mischiando tutto?
        # Il bando non specifica l'ordine, ma spesso sono raggruppate.
        # Mischiamo tutto tranne i situazionali per rendere l'esame dinamico ma ordinato.
        technical_part = roadmap[:32]
        random.shuffle(technical_part)

        final_roadmap = technical_part + roadmap[32:]  # Situazionali in coda (domande 33-40)

        return ExamSession(start_time=time.time(), subject_roadmap=final_roadmap)

    def get_next_question(self, session: ExamSession) -> Optional[Question]:
        if session.current_index >= len(session.subject_roadmap):
            return None

        if session.current_index < len(session.questions):
            return session.questions[session.current_index]

        # --- GENERAZIONE NUOVA DOMANDA ---
        subject = session.subject_roadmap[session.current_index]

        # 1. Scelta del Topic Specifico
        if subject in SUB_TOPICS:
            specific_topic = f"{subject}: {random.choice(SUB_TOPICS[subject])}"
        else:
            specific_topic = get_random_topic(subject)

        # 2. Scelta del Tutor Corretto
        tutor = tutor_for_subject(subject)

        # Difficulty 3 (Media) per esame standard
        cfg = PromptBuildConfig(seed_per_prompt=3, strict_json_only=True)

        prompt = build_question_prompt(
            self.project_root, subject, tutor, 3, "neutro", cfg,
            specific_topic=specific_topic
        )

        resp = self.gemini.generate_content(prompt)
        clean = resp.replace("```json", "").replace("```", "").strip()

        try:
            data = json.loads(clean)
        except:
            data = {
                "domanda": "Errore di connessione al database domande.",
                "opzioni": {"A": ".", "B": ".", "C": ".", "D": "."},
                "corretta": "A",
                "materia": subject
            }

        spieg = data.get("spiegazione_breve") or data.get("spiegazione", "")
        corr_raw = str(data.get("corretta", "A")).strip().upper()[0]

        q = Question(
            domanda=data.get("domanda", ""),
            opzioni=data.get("opzioni", {}),
            corretta=corr_raw,
            spiegazione=spieg,
            tutor=tutor,
            materia=subject,
            tipo="situazionale" if subject == "Quesiti situazionali" else "standard",
            spiegazione_breve=spieg
        )

        session.questions.append(q)
        return q

    def submit_answer(self, session: ExamSession, answer: str):
        session.answers[session.current_index] = answer

    def calculate_result(self, session: ExamSession) -> Tuple[float, bool, str]:
        total = 0.0
        corr, wrong, omit = 0, 0, 0

        for i, q in enumerate(session.questions):
            ans = session.answers.get(i)

            if q.tipo == "situazionale":
                if ans == q.corretta:
                    total += 0.75
                elif ans:
                    total += 0.375
            else:
                if ans == q.corretta:
                    total += 0.75
                    corr += 1
                elif ans:
                    total -= 0.25
                    wrong += 1
                else:
                    omit += 0  # 0 punti per omessa

        final = max(0.0, total)
        passed = final >= 21.0
        status = "IDONEO" if passed else "NON IDONEO"

        rep = (
            f"--- ESITO ESAME ---\n"
            f"Punteggio: {final:.2f}/30\n"
            f"Esito: {status}\n"
            f"Dettaglio: +{corr} Corrette | -{wrong} Errate | {omit} Omesse"
        )
        return final, passed, rep