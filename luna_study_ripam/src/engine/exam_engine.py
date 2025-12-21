import random
import time
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

from src.domain.models import Question
from src.ai.gemini_client import GeminiClient
from src.ai.prompt_builder import build_question_prompt, PromptBuildConfig
from src.engine.scoring import ScoreConfig, evaluate_answer


@dataclass
class ExamSession:
    """Stato della sessione d'esame."""
    questions: List[Question] = field(default_factory=list)
    answers: Dict[int, str] = field(default_factory=dict)  # Indice -> Risposta (A/B/C/D)
    current_index: int = 0
    start_time: float = 0.0
    duration_seconds: int = 60 * 60  # 60 minuti da bando
    is_finished: bool = False

    # Roadmap delle materie da generare (40 totali)
    subject_roadmap: List[str] = field(default_factory=list)


class ExamEngine:
    def __init__(self, project_root: str, gemini: GeminiClient):
        self.project_root = project_root
        self.gemini = gemini
        self.score_config = ScoreConfig()  # Usa i valori di default che corrispondono al bando (+0.75, -0.25, ecc)

    def start_exam(self) -> ExamSession:
        """Inizializza una nuova sessione d'esame con la roadmap delle materie."""
        roadmap = self._generate_ripam_roadmap()
        return ExamSession(
            start_time=time.time(),
            subject_roadmap=roadmap
        )

    def _generate_ripam_roadmap(self) -> List[str]:
        """
        Genera la lista delle 40 materie secondo l'Art. 6 del Bando.
        Profilo ACC/VIG (Codice 01) - Basato sui file disponibili.
        """
        roadmap = []

        # 1. MATERIE COMUNI (10 quesiti)
        pool_common = [
            "Diritto amministrativo", "Diritto penale (PA)", "Codice dell'Amministrazione Digitale (CAD)",
            "Diritto dell'Unione Europea", "Contabilità di Stato", "Inglese A2", "Informatica (TIC)"
        ]
        # Ne estraiamo 10 a caso (con ripetizioni possibili per coprire il numero)
        for _ in range(10):
            roadmap.append(random.choice(pool_common))

        # 2. MATERIE SPECIFICHE CODICE 01 (15 quesiti)
        # Sicurezza, Marketing, Beni Culturali, Struttura MIC
        pool_specific = [
            "Sicurezza (D.Lgs. 81/2008)", "Marketing e comunicazione PA",
            "Beni culturali", "Struttura MIC"
        ]
        for _ in range(15):
            roadmap.append(random.choice(pool_specific))

        # 3. LOGICA E RAGIONAMENTO (7 quesiti)
        pool_logic = ["Logica", "Ragionamento critico-verbale"]
        for _ in range(7):
            roadmap.append(random.choice(pool_logic))

        # 4. SITUAZIONALI (8 quesiti)
        for _ in range(8):
            roadmap.append("Quesiti situazionali")

        return roadmap

    def get_next_question(self, session: ExamSession) -> Optional[Question]:
        """
        Genera la prossima domanda basandosi sulla roadmap.
        Se la domanda esiste già (cache/navigazione indietro), la restituisce.
        """
        if session.current_index >= len(session.subject_roadmap):
            return None  # Fine domande

        # Se abbiamo già generato questa domanda, ritornala
        if session.current_index < len(session.questions):
            return session.questions[session.current_index]

        # Altrimenti genera nuova domanda
        subject = session.subject_roadmap[session.current_index]

        # Configurazione prompt per esame (più formale, no visual art)
        cfg = PromptBuildConfig(seed_per_prompt=3, strict_json_only=True)

        # Usiamo "Maria" come tutor "severo" di default per l'esame, ma il prompt è neutro
        tutor_sim = "Maria"

        import json

        prompt_text = build_question_prompt(
            project_root=self.project_root,
            subject=subject,
            tutor=tutor_sim,
            stage=1,  # Irrilevante per l'esame
            outcome_hint="neutro",
            cfg=cfg
        )

        # Chiamata LLM
        response_json = self.gemini.generate_content(prompt_text)

        # Pulizia JSON
        cleaned_json = response_json
        if "```" in cleaned_json:
            cleaned_json = cleaned_json.replace("```json", "").replace("```", "").strip()

        try:
            data = json.loads(cleaned_json)
        except Exception:
            # Fallback in caso di errore generazione
            data = {
                "domanda": "Errore di connessione al database ministeriale. Passare alla successiva.",
                "opzioni": {"A": "---", "B": "---", "C": "---", "D": "---"},
                "corretta": "A",
                "spiegazione": "N/A",
                "tutor": tutor_sim,
                "materia": subject
            }

        # Parsing adattato per situazionali
        q_type = "situazionale" if subject == "Quesiti situazionali" else "standard"

        q = Question(
            domanda=data.get("domanda", ""),
            opzioni=data.get("opzioni", {}),
            corretta=data.get("corretta", "A"),
            spiegazione=data.get("spiegazione_breve") or data.get("spiegazione", ""),
            tutor=tutor_sim,
            materia=subject,
            tipo=q_type,
            spiegazione_breve=data.get("spiegazione_breve", "")
        )

        # Aggiungi alla lista sessione
        session.questions.append(q)
        return q

    def submit_answer(self, session: ExamSession, answer: str):
        """Registra la risposta dell'utente."""
        session.answers[session.current_index] = answer

    def calculate_result(self, session: ExamSession) -> Tuple[float, bool, str]:
        """
        Calcola il punteggio finale secondo il Bando.
        Return: (punteggio_totale, is_passed, report_text)
        """
        total_score = 0.0

        details = []

        for idx, q in enumerate(session.questions):
            user_ans = session.answers.get(idx)  # None se omessa

            # Usa la logica di scoring.py che contiene già i valori +0.75 / -0.25
            if q.tipo == "situazionale":
                # Simuliamo la efficacy map se non presente nel JSON (l'LLM a volte non la mette nel formato standard)
                # Per semplicità in simulazione: se l'LLM non da efficacia, usiamo la logica standard o random
                # (Qui servirebbe che l'LLM restituisse l'efficacia per ogni opzione, per ora semplifichiamo:
                # Se è la "corretta" indicata dall'LLM = Efficace (+0.75), le altre neutre (+0.375) o inefficaci (0))
                # Dato che il JSON standard ha solo "corretta", assumiamo:
                # Corretta = +0.75
                # Altre = 0 (punizione massima per semplificare o 0.375 statistico)
                # MIGLIORIA: Assumiamo 0 se diversa da corretta per rigore, oppure implementiamo logica fuzzy.
                # Per il bando:
                if user_ans == q.corretta:
                    score = 0.75
                elif user_ans is None:
                    score = 0.0
                else:
                    score = 0.375  # Diamo il beneficio del "neutro" alle sbagliate nei situazionali per non penalizzare troppo
            else:
                # Standard
                if user_ans is None:
                    score = 0.0  # Omessa
                elif user_ans == q.corretta:
                    score = 0.75  # Esatta
                else:
                    score = -0.25  # Errata

            total_score += score

        # Clamp a 0 se negativo (anche se il bando non lo specifica, è prassi non avere voti negativi totali)
        final_score = max(0.0, total_score)

        # Soglia idoneità: 21/30
        is_passed = final_score >= 21.0

        status = "IDONEO" if is_passed else "NON IDONEO"
        report = f"Punteggio Finale: {final_score:.2f}/30\nEsito: {status}"

        return final_score, is_passed, report