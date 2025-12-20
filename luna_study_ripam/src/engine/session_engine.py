import json
import os
import random
from typing import Optional, List
import uuid

# Assicurati che models.py sia aggiornato con HistoryItem!
from src.domain.models import SessionState, Question, Outcome, TutorName, HistoryItem
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
        self.stage_manager = StageManager(step=10, min_stage=1, max_stage=5)
        self.last_image_path: Optional[str] = None

    def start_next_question(self, state: SessionState) -> Question:
        tutor = "Maria"
        subjects = [
            "Diritto amministrativo", "Logica", "Informatica (TIC)",
            "Inglese A2", "Sicurezza (D.Lgs. 81/2008)",
            "Reati contro la PA", "Pubblico Impiego"
        ]
        subject = random.choice(subjects)

        current_stage = state.stage.get(tutor, 1)

        last_outcome = "neutro"
        if state.history:
            last_outcome = state.history[-1].outcome

        cfg = PromptBuildConfig(seed_per_prompt=3, strict_json_only=True)
        prompt_text = build_question_prompt(
            project_root=self.project_root,
            subject=subject,
            tutor=tutor,
            stage=current_stage,
            outcome_hint=last_outcome,
            cfg=cfg
        )

        response_json = self.gemini.generate_content(prompt_text)

        # --- FIX: PULIZIA JSON ---
        # Rimuove markdown backticks se presenti
        cleaned_json = response_json
        if "```" in cleaned_json:
            cleaned_json = cleaned_json.replace("```json", "").replace("```", "").strip()
        # -------------------------

        try:
            data = json.loads(cleaned_json)
        except json.JSONDecodeError as e:
            print(f"Errore JSON grezzo: {response_json}")  # Log per debug
            data = {
                "domanda": "Errore lettura dati dall'IA. Riprova.",
                "opzioni": {"A": "...", "B": "...", "C": "...", "D": "..."},
                "corretta": "A",
                "spiegazione": f"Dettaglio errore: {e}",
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
            tags=data.get("tags", []),
            visual=data.get("visual", "")
        )
        q.spiegazione_breve = data.get("spiegazione", "")

        return q

    def apply_answer(self, state: SessionState, question: Question, user_choice: str):
        is_correct = (user_choice.upper() == question.corretta.upper())
        outcome = "corretta" if is_correct else "errata"

        # Aggiorna History
        new_item = HistoryItem(tutor=question.tutor, outcome=outcome)
        state.history.append(new_item)

        # Aggiorna Stage
        update = self.stage_manager.apply_outcome(state, question.tutor, outcome)

        # Genera Immagine
        if self.enable_sd:
            try:
                sd_prompt = compile_sd_prompt(
                    project_root=self.project_root,
                    tutor=question.tutor,
                    stage=update.new_stage,
                    is_punish=update.is_punish,
                    question=question
                )

                filename = f"image_{uuid.uuid4().hex[:6]}.png"
                out_path = os.path.join(self.project_root, "output_images", filename)
                os.makedirs(os.path.dirname(out_path), exist_ok=True)

                self.sd_client.generate_image(
                    prompt=sd_prompt.prompt,
                    negative_prompt=sd_prompt.negative_prompt,
                    output_path=out_path
                )
                self.last_image_path = out_path
            except Exception as e:
                print(f"Errore generazione immagine: {e}")
                self.last_image_path = None

        return update

    def save_session_to_file(self, state: SessionState, filepath: str):
        # Convertiamo HistoryItem in dict per il JSON
        history_data = [{"tutor": h.tutor, "outcome": h.outcome} for h in state.history]
        data = {
            "progress": state.progress,
            "stage": state.stage,
            "history": history_data
        }
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            return True
        except Exception as e:
            print(f"Errore salvataggio: {e}")
            return False

    def load_session_from_file(self, filepath: str) -> Optional[SessionState]:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            new_state = SessionState()
            if "progress" in data: new_state.progress = data["progress"]
            if "stage" in data: new_state.stage = data["stage"]
            if "history" in data:
                new_state.history = [
                    HistoryItem(tutor=x["tutor"], outcome=x["outcome"])
                    for x in data["history"]
                ]
            return new_state
        except Exception as e:
            print(f"Errore caricamento: {e}")
            return None