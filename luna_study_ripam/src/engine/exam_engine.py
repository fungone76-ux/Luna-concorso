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
        pool_know = [
            "Diritto amministrativo", "Diritto penale (PA)", "Codice dell'Amministrazione Digitale (CAD)",
            "Diritto dell'Unione Europea", "Contabilità di Stato",
            "Sicurezza (D.Lgs. 81/2008)", "Marketing e comunicazione PA",
            "Beni culturali", "Struttura MIC", "Lavoro pubblico"
        ]
        for _ in range(25): roadmap.append(random.choice(pool_know))
        for _ in range(7): roadmap.append(random.choice(["Logica", "Ragionamento critico-verbale"]))
        for _ in range(8): roadmap.append("Quesiti situazionali")

        return ExamSession(start_time=time.time(), subject_roadmap=roadmap)

    def get_next_question(self, session: ExamSession) -> Optional[Question]:
        if session.current_index >= len(session.subject_roadmap): return None
        if session.current_index < len(session.questions): return session.questions[session.current_index]

        subject = session.subject_roadmap[session.current_index]
        specific_topic = get_random_topic(subject)  # GRANULARITÀ

        cfg = PromptBuildConfig(seed_per_prompt=3, strict_json_only=True)
        prompt = build_question_prompt(
            self.project_root, subject, "Maria", 1, "neutro", cfg,
            specific_topic=specific_topic
        )

        resp = self.gemini.generate_content(prompt)
        clean = resp.replace("```json", "").replace("```", "").strip()
        try:
            data = json.loads(clean)
        except:
            data = {"domanda": "Errore", "opzioni": {}, "corretta": "A", "materia": subject}

        spieg = data.get("spiegazione_breve") or data.get("spiegazione", "")
        q = Question(
            domanda=data.get("domanda", ""),
            opzioni=data.get("opzioni", {}),
            corretta=data.get("corretta", "A"),
            spiegazione=spieg,
            tutor="Maria",
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
                    omit += 1

        final = max(0.0, total)
        passed = final >= 21.0
        status = "IDONEO" if passed else "NON IDONEO"
        rep = f"Punteggio: {final:.2f}/30\nEsito: {status}\n(+{corr} corr / -{wrong} err / {omit} om)"
        return final, passed, rep