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
        # 1. Materie Tecniche / Giuridiche (circa 25 domande)
        pool_know = [
            "Diritto amministrativo",
            "Diritto penale (PA)",
            "Codice dell'Amministrazione Digitale (CAD)",
            "Diritto dell'Unione Europea",
            "Contabilità di Stato",
            "Sicurezza (D.Lgs. 81/2008)",
            "Marketing e comunicazione PA",
            "Beni culturali",
            "Struttura MIC",
            "Lavoro pubblico",
            "Contratti pubblici",
            "Responsabilità del dipendente pubblico"
        ]

        # Genera roadmap bilanciata
        for _ in range(25):
            roadmap.append(random.choice(pool_know))

        # 2. Logica e Inglese (circa 7 domande)
        pool_logic_eng = ["Logica", "Ragionamento critico-verbale", "Inglese A2", "Informatica (TIC)"]
        for _ in range(7):
            roadmap.append(random.choice(pool_logic_eng))

        # 3. Situazionali (8 domande fisse)
        for _ in range(8):
            roadmap.append("Quesiti situazionali")

        # Mischia la roadmap (tranne le situazionali che spesso sono in blocco, ma qui le lasciamo in fondo o mischiamo tutto?)
        # Di solito nei concorsi sono a blocchi, ma mischiare le prime due sezioni rende l'esame più dinamico.
        # Lasciamo le situazionali in fondo come da prassi RIPAM recente.
        part1 = roadmap[:32]
        random.shuffle(part1)
        final_roadmap = part1 + roadmap[32:]

        return ExamSession(start_time=time.time(), subject_roadmap=final_roadmap)

    def get_next_question(self, session: ExamSession) -> Optional[Question]:
        # Se abbiamo finito le domande previste
        if session.current_index >= len(session.subject_roadmap):
            return None

        # Se la domanda è già stata generata in precedenza (navigazione indietro), la restituiamo
        if session.current_index < len(session.questions):
            return session.questions[session.current_index]

        # --- GENERAZIONE NUOVA DOMANDA ---
        subject = session.subject_roadmap[session.current_index]

        # 1. Scelta del Topic Specifico (Sotto-materia)
        # Se la materia ha sotto-argomenti definiti in subject_picker, ne usiamo uno a caso.
        if subject in SUB_TOPICS:
            specific_topic = f"{subject}: {random.choice(SUB_TOPICS[subject])}"
        else:
            # Fallback al vecchio sistema se non c'è nel dizionario nuovo
            specific_topic = get_random_topic(subject)

        # 2. Scelta del Tutor Corretto
        # Usiamo il router per avere il tutor specialista (es. Stella per Inglese/Logica, Maria per Diritto)
        tutor = tutor_for_subject(subject)

        cfg = PromptBuildConfig(seed_per_prompt=3, strict_json_only=True)

        # Costruiamo il prompt usando il tutor corretto e il topic specifico
        # Difficulty settata a 3 (media) per simulazione esame realistica
        prompt = build_question_prompt(
            self.project_root, subject, tutor, 3, "neutro", cfg,
            specific_topic=specific_topic
        )

        resp = self.gemini.generate_content(prompt)
        clean = resp.replace("```json", "").replace("```", "").strip()

        try:
            data = json.loads(clean)
        except:
            # Fallback in caso di errore JSON
            data = {
                "domanda": "Errore di connessione al database domande.",
                "opzioni": {"A": ".", "B": ".", "C": ".", "D": "."},
                "corretta": "A",
                "materia": subject
            }

        spieg = data.get("spiegazione_breve") or data.get("spiegazione", "")

        # Pulizia della lettera corretta (a volte arriva come "A)" o "A.")
        corr_raw = str(data.get("corretta", "A")).strip().upper()[0]

        q = Question(
            domanda=data.get("domanda", ""),
            opzioni=data.get("opzioni", {}),
            corretta=corr_raw,
            spiegazione=spieg,
            tutor=tutor,  # Tutor corretto!
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
                # Logica Situazionale: Risposta più efficace vs meno efficace
                # Nota: Qui semplifichiamo. Se l'LLM ci dà solo UNA corretta ("corretta": "A"),
                # assumiamo che quella sia la +0.75.
                # Per una logica situazionale pura servirebbe una mappa di efficacia per ogni opzione.
                # Per ora manteniamo la logica base: se azzecchi la "best" prendi il max.
                if ans == q.corretta:
                    total += 0.75
                elif ans:
                    # Se rispondi ma non è la "best", diamo un punteggio neutro (assunzione semplificata)
                    total += 0.375
            else:
                # Logica Standard
                if ans == q.corretta:
                    total += 0.75
                    corr += 1
                elif ans:
                    total -= 0.25
                    wrong += 1
                else:
                    omit += 1  # 0 punti

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