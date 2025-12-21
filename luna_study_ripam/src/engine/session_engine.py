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
        self.stage_manager = StageManager(step=5, min_stage=1, max_stage=5)
        self.subject_picker = SubjectPicker()
        self.last_image_path: Optional[str] = None

    def _get_stage_mood(self, stage: int) -> str:
        """Returns the tone instruction based on stage (1-5)."""
        moods = {
            1: "TONE: Professional, cold, institutional. No intimacy.",
            2: "TONE: Flirty, teasing, warm voice. Start hinting at desire.",
            3: "TONE: Seductive, provocative. Use double entendres.",
            4: "TONE: VERY HOT, 'Dirty Talk'. Be vulgar or extremely explicit about desire.",
            5: "TONE: EXTREME, NSFW/PORNOGRAPHIC. No filters. If praising, do it with total submission/ecstasy. If punishing, destroy him verbally."
        }
        return moods.get(stage, moods[1])

    def start_next_question(self, state: SessionState) -> Question:
        recent = [h.tutor for h in state.history[-5:]]
        subject = self.subject_picker.pick(recent_subjects=recent)
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
            data = {"domanda": "Errore lettura dati. Riprova.", "opzioni": {"A": ".", "B": ".", "C": ".", "D": "."},
                    "corretta": "A", "tutor": tutor, "materia": subject}

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

    def get_tutor_response(self, question: Question, user_text: str, has_answered: bool, stage: int = 1) -> str:
        """Free chat with tutor (stage influenced)."""
        try:
            path = os.path.join(self.project_root, "prompts", "tutor_profiles", f"{question.tutor.lower()}.txt")
            with open(path, "r", encoding="utf-8") as f:
                profile = f.read().strip()
        except:
            profile = f"You are {question.tutor}."

        mood_instr = self._get_stage_mood(stage)
        ctx = "USER HAS ANSWERED" if has_answered else "USER HAS NOT ANSWERED YET"

        prompt = f"""
{profile}
{mood_instr}

CONTEXT: {question.domanda}
GAME STATE: {ctx}
USER SAYS: "{user_text}"

INSTRUCTION:
Reply to the user strictly following the TONE for stage {stage}.
Be consistent with your personality but apply the required 'heat' level.
Max 2 sentences.
"""
        return self.gemini.generate_content(prompt)

    def get_answer_feedback(self, question: Question, outcome: str, stage: int) -> str:
        """Generates hot feedback (praise/insult) after an answer."""
        try:
            path = os.path.join(self.project_root, "prompts", "tutor_profiles", f"{question.tutor.lower()}.txt")
            with open(path, "r", encoding="utf-8") as f:
                profile = f.read().strip()
        except:
            profile = f"You are {question.tutor}."

        mood_instr = self._get_stage_mood(stage)
        esito_txt = "CORRECT" if outcome == "corretta" else "WRONG"

        prompt = f"""
{profile}
{mood_instr}

EVENT: The user just gave a {esito_txt} answer.

INSTRUCTION:
Generate an immediate reaction (1 sentence).
- If CORRECT: Praise him, seduce him, or reward him verbally based on the stage tone.
- If WRONG: Insult him, humiliate him, or punish him verbally based on the stage tone.
Do not give technical explanations here, just the emotional/personal reaction.
"""
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
            s.history = [HistoryItem(tutor=x["tutor"], outcome=x["outcome"]) for x in data.get("history", [])]
            return s
        except:
            return None