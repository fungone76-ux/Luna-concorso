# src/engine/session_engine.py
import json
import os
import random
from typing import Optional
import uuid

from src.domain.models import SessionState, Question, HistoryItem
from src.ai.gemini_client import GeminiClient
from src.ai.prompt_builder import build_question_prompt, PromptBuildConfig
from src.visuals.prompt_compiler import compile_sd_prompt
from src.visuals.sd_client import SDClient
from src.visuals.stage_manager import StageManager
from src.engine.subject_picker import SubjectPicker
from src.engine.tutor_router import tutor_for_subject
from src.domain.syllabus import get_random_topic


class SessionEngine:
    def __init__(self, project_root: str, gemini: GeminiClient, sd_client: SDClient, enable_sd: bool = True):
        self.project_root = project_root
        self.gemini = gemini
        self.sd_client = sd_client
        self.enable_sd = enable_sd
        self.stage_manager = StageManager(step=10, min_stage=1, max_stage=5)
        self.subject_picker = SubjectPicker()
        self.last_image_path: Optional[str] = None

    def start_next_question(self, state: SessionState) -> Question:
        recent = [h.tutor for h in state.history[-5:]]
        subject = self.subject_picker.pick(recent_subjects=recent)

        # Topic Specifico
        specific_topic = get_random_topic(subject)

        tutor = tutor_for_subject(subject)
        stage = state.stage.get(tutor, 1)
        last_out = state.history[-1].outcome if state.history else "neutro"

        cfg = PromptBuildConfig(seed_per_prompt=3, strict_json_only=True)
        prompt_text = build_question_prompt(
            self.project_root, subject, tutor, stage, last_out, cfg,
            specific_topic=specific_topic
        )

        resp = self.gemini.generate_content(prompt_text)
        clean_json = resp.replace("```json", "").replace("```", "").strip()

        try:
            data = json.loads(clean_json)
        except:
            data = {"domanda": "Errore API", "opzioni": {"A": ".", "B": ".", "C": ".", "D": "."}, "corretta": "A",
                    "tutor": tutor, "materia": subject}

        spieg = data.get("spiegazione_breve") or data.get("spiegazione", "...")

        q = Question(
            domanda=data.get("domanda", ""),
            opzioni=data.get("opzioni", {}),
            corretta=data.get("corretta", "A"),
            spiegazione=spieg,
            tutor=data.get("tutor", tutor),
            materia=data.get("materia", subject),
            tipo=data.get("tipo", "standard"),
            tags=data.get("tags", []),
            visual=data.get("visual", ""),
            spiegazione_breve=spieg
        )
        return q

    def get_tutor_response(self, question: Question, user_text: str, has_answered: bool) -> str:
        try:
            path = os.path.join(self.project_root, "prompts", "tutor_profiles", f"{question.tutor.lower()}.txt")
            with open(path, "r", encoding="utf-8") as f:
                profile = f.read().strip()
        except:
            profile = f"Sei {question.tutor}."

        ctx = "HAI RISPOSTO" if has_answered else "NON HAI RISPOSTO"
        prompt = f"{profile}\n\nCONTESTO: {question.domanda}\nSTATO: {ctx}\nUSER: {user_text}\nRISPONDI (max 2 frasi):"
        return self.gemini.generate_content(prompt)

    def apply_answer(self, state: SessionState, question: Question, user_choice: str):
        is_correct = (user_choice.upper() == question.corretta.upper())
        outcome = "corretta" if is_correct else "errata"

        state.history.append(HistoryItem(tutor=question.tutor, outcome=outcome))
        update = self.stage_manager.apply_outcome(state, question.tutor, outcome)

        if self.enable_sd:
            try:
                sd_prompt = compile_sd_prompt(self.project_root, question.tutor, update.new_stage, update.is_punish,
                                              question)
                filename = f"img_{uuid.uuid4().hex[:6]}.png"
                out = os.path.join(self.project_root, "output_images", filename)
                os.makedirs(os.path.dirname(out), exist_ok=True)
                self.sd_client.generate_image(sd_prompt.prompt, sd_prompt.negative_prompt, out)
                self.last_image_path = out
            except Exception as e:
                print(e)

        return update

    def save_session_to_file(self, state, filepath):
        try:
            data = {"progress": state.progress, "stage": state.stage,
                    "history": [{"tutor": h.tutor, "outcome": h.outcome} for h in state.history]}
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            return True
        except:
            return False

    def load_session_from_file(self, filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            s = SessionState()
            s.progress = data.get("progress", {})
            s.stage = data.get("stage", {})
            s.history = [HistoryItem(t=x["tutor"], outcome=x["outcome"]) for x in data.get("history", [])]
            return s
        except:
            return None