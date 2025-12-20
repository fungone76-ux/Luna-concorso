import json
import os
import random
from typing import Optional, List

from src.domain.models import SessionState, Question, Outcome, TutorName
from src.ai.gemini_client import GeminiClient
from src.ai.prompt_builder import build_question_prompt, PromptBuildConfig
from src.visuals.prompt_compiler import compile_sd_prompt
from src.visuals.sd_client import SDClient
from src.visuals.stage_manager import StageManager


class SessionEngine:
    def __init__(
            self,
            project_root: str,
            gemini: GeminiClient,
            sd_client: SDClient,
            enable_sd: bool = True
    ):
        self.project_root = project_root
        self.gemini = gemini
        self.sd_client = sd_client
        self.enable_sd = enable_sd

        # Gestore dello stage (livelli)
        self.stage_manager = StageManager(step=10, min_stage=1, max_stage=5)

        self.last_image_path: Optional[str] = None

    def start_next_question(self, state: SessionState) -> Question:
        # 1. Seleziona Tutor, Materia
        tutor = "Maria"
        subjects = [
            "Diritto amministrativo", "Logica", "Informatica (TIC)",
            "Inglese A2", "Sicurezza (D.Lgs. 81/2008)",
            "Reati contro la PA", "Pubblico Impiego"
        ]
        subject = random.choice(subjects)

        # 2. Recupera stato attuale
        current_stage = state.stage.get(tutor, 1)
        last_outcome = state.history[-1].outcome if state.history else "neutro"

        # 3. Costruisci Prompt
        cfg = PromptBuildConfig(seed_per_prompt=3, strict_json_only=True)
        prompt_text = build_question_prompt(
            project_root=self.project_root,
            subject=subject,
            tutor=tutor,
            stage=current_stage,
            outcome_hint=last_outcome,
            cfg=cfg
        )

        # 4. Chiama LLM
        response_json = self.gemini.generate_content(prompt_text)

        # 5. Parsing
        try:
            data = json.loads(response_json)
        except json.JSONDecodeError:
            # Fallback banale in caso di errore JSON
            data = {
                "domanda": "Errore generazione JSON.",
                "opzioni": {"A": "Err", "B": "Err", "C": "Err", "D": "Err"},
                "corretta": "A",
                "spiegazione": "Riprova.",
                "tutor": tutor,
                "materia": subject
            }

        q = Question(
            domanda=data.get("domanda", ""),
            opzioni=data.get("opzioni", {}),
            corretta=data.get("corretta", "A"),
            spiegazione=data.get("spiegazione", ""),
            tutor=data.get("tutor", tutor),
            materia=data.get("materia", subject),
            tipo=data.get("tipo", "standard"),
            tags=data.get("tags", []),  # Tags visivi
            visual=data.get("visual", "")  # Descrizione scena
        )
        # Salva spiegazione breve per la GUI (opzionale se non c'è nel JSON)
        q.spiegazione_breve = data.get("spiegazione", "")

        return q

    def apply_answer(self, state: SessionState, question: Question, user_choice: str):
        # 1. Verifica correttezza
        is_correct = (user_choice.upper() == question.corretta.upper())
        outcome = "corretta" if is_correct else "errata"

        # 2. Aggiorna Stage/Punti
        update = self.stage_manager.apply_outcome(state, question.tutor, outcome)

        # 3. Generazione Immagine (se abilitata)
        if self.enable_sd:
            sd_prompt = compile_sd_prompt(
                project_root=self.project_root,
                tutor=question.tutor,
                stage=update.new_stage,  # Usa lo stage (outfit) mantenuto
                is_punish=update.is_punish,  # Aggiungi espressione severa se errata
                question=question
            )

            # Nome file univoco
            import uuid
            filename = f"image_{uuid.uuid4().hex[:6]}.png"
            out_path = os.path.join(self.project_root, "output_images", filename)
            os.makedirs(os.path.dirname(out_path), exist_ok=True)

            self.sd_client.generate_image(
                prompt=sd_prompt.prompt,
                negative_prompt=sd_prompt.negative_prompt,
                output_path=out_path
            )
            self.last_image_path = out_path

        return update

    # --- NUOVI METODI PER SALVATAGGIO/CARICAMENTO ---

    def save_session_to_file(self, state: SessionState, filepath: str):
        """Salva lo stato corrente su file JSON."""
        data = {
            "progress": state.progress,  # Dizionario {tutor: punti}
            "stage": state.stage  # Dizionario {tutor: livello}
        }
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            return True
        except Exception as e:
            print(f"Errore salvataggio: {e}")
            return False

    def load_session_from_file(self, filepath: str) -> Optional[SessionState]:
        """Carica lo stato da file JSON e restituisce un nuovo oggetto SessionState."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            new_state = SessionState()
            # Ripristina i dizionari. Assicuriamoci che le chiavi siano stringhe (JSON standard)
            if "progress" in data:
                new_state.progress = data["progress"]
            if "stage" in data:
                new_state.stage = data["stage"]

            return new_state
        except Exception as e:
            print(f"Errore caricamento: {e}")
            return None