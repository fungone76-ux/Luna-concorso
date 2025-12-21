import json
import os
import random
from typing import Optional, List
import uuid

from src.domain.models import SessionState, Question, Outcome, TutorName, HistoryItem
from src.ai.gemini_client import GeminiClient
from src.ai.prompt_builder import build_question_prompt, PromptBuildConfig
from src.visuals.prompt_compiler import compile_sd_prompt
from src.visuals.sd_client import SDClient
from src.visuals.stage_manager import StageManager

# --- NUOVI IMPORT FONDAMENTALI ---
from src.engine.subject_picker import SubjectPicker
from src.engine.tutor_router import tutor_for_subject


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

        # Gestori logica gioco
        self.stage_manager = StageManager(step=10, min_stage=1, max_stage=5)
        self.subject_picker = SubjectPicker()  # Ora usiamo il picker ufficiale!

        self.last_image_path: Optional[str] = None

    def start_next_question(self, state: SessionState) -> Question:
        # 1. ESTRAZIONE DINAMICA MATERIA (Non più lista fissa)
        # Recupera le materie recenti per evitare ripetizioni
        recent_subjects = [h.tutor for h in state.history[-5:]]  # Usiamo la history per dare un contesto (approx)
        subject = self.subject_picker.pick(recent_subjects=[])

        # 2. SELEZIONE TUTOR CORRETTO (Luna, Stella o Maria)
        tutor = tutor_for_subject(subject)

        # 3. Recupera stato attuale del tutor
        current_stage = state.stage.get(tutor, 1)

        last_outcome = "neutro"
        if state.history:
            last_outcome = state.history[-1].outcome

        # 4. Costruisci Prompt
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

        # Pulizia JSON
        cleaned_json = response_json
        if "```" in cleaned_json:
            cleaned_json = cleaned_json.replace("```json", "").replace("```", "").strip()

        try:
            data = json.loads(cleaned_json)
        except json.JSONDecodeError as e:
            print(f"Errore JSON grezzo: {response_json}")
            data = {
                "domanda": "Errore lettura dati dall'IA. Riprova.",
                "opzioni": {"A": "---", "B": "---", "C": "---", "D": "---"},
                "corretta": "A",
                "spiegazione": f"Dettaglio errore: {e}",
                "tutor": tutor,
                "materia": subject
            }

        raw_spiegazione = data.get("spiegazione_breve") or data.get("spiegazione") or "Nessuna spiegazione disponibile."

        q = Question(
            domanda=data.get("domanda", ""),
            opzioni=data.get("opzioni", {}),
            corretta=data.get("corretta", "A"),
            spiegazione=raw_spiegazione,
            tutor=data.get("tutor", tutor),  # Usa il tutor estratto o quello del JSON
            materia=data.get("materia", subject),
            tipo=data.get("tipo", "standard"),
            tags=data.get("tags", []),
            visual=data.get("visual", "")
        )
        q.spiegazione_breve = raw_spiegazione

        return q

    def get_tutor_response(self, question: Question, user_text: str, has_answered: bool) -> str:
        """Genera una risposta del Tutor in chat."""
        tutor_file = f"{question.tutor.lower()}.txt"
        try:
            path = os.path.join(self.project_root, "prompts", "tutor_profiles", tutor_file)
            with open(path, "r", encoding="utf-8") as f:
                tutor_profile = f.read().strip()
        except:
            tutor_profile = f"Sei {question.tutor}."

        if has_answered:
            spoiler_instruction = (
                f"L'utente HA GIÀ RISPOSTO. La risposta corretta è {question.corretta}.\n"
                f"Spiegazione tecnica: {question.spiegazione}.\n"
                "Se l'utente chiede spiegazioni, forniscile in modo chiaro e didattico."
            )
        else:
            spoiler_instruction = (
                "L'utente NON ha ancora risposto.\n"
                "NON RIVELARE la risposta corretta.\n"
                "Se chiedono aiuto, dai un indizio vago o rimproverali."
            )

        prompt = f"""
{tutor_profile}

CONTESTO:
Materia: "{question.materia}"
Domanda: "{question.domanda}"

STATO:
{spoiler_instruction}

INTERAZIONE:
Il candidato dice: "{user_text}"

ISTRUZIONI:
Rispondi al candidato (max 2 frasi). Usa il tuo tono specifico.
"""
        return self.gemini.generate_content(prompt)

    def apply_answer(self, state: SessionState, question: Question, user_choice: str):
        is_correct = (user_choice.upper() == question.corretta.upper())
        outcome = "corretta" if is_correct else "errata"

        new_item = HistoryItem(tutor=question.tutor, outcome=outcome)
        state.history.append(new_item)

        update = self.stage_manager.apply_outcome(state, question.tutor, outcome)

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
        history_data = [{"tutor": h.tutor, "outcome": h.outcome} for h in state.history]
        data = {"progress": state.progress, "stage": state.stage, "history": history_data}
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            return True
        except Exception:
            return False

    def load_session_from_file(self, filepath: str) -> Optional[SessionState]:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            new_state = SessionState()
            if "progress" in data: new_state.progress = data["progress"]
            if "stage" in data: new_state.stage = data["stage"]
            if "history" in data:
                new_state.history = [HistoryItem(tutor=x["tutor"], outcome=x["outcome"]) for x in data["history"]]
            return new_state
        except Exception:
            return None