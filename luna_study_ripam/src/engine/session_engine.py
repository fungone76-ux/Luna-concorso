# src/engine/session_engine.py
import json
import os
import random
import re
from typing import Optional, Tuple
import uuid

from src.domain.models import SessionState, Question, HistoryItem, LessonRecord
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
        moods = {
            1: "TONE: Professional, cold, institutional.",
            2: "TONE: Flirty, teasing, warm voice.",
            3: "TONE: Seductive, provocative.",
            4: "TONE: VERY HOT, 'Dirty Talk'.",
            5: "TONE: EXTREME, NSFW."
        }
        return moods.get(stage, moods[1])

    # --- FASE 1: LEZIONE ---
    def start_new_lesson_block(self, state: SessionState) -> Tuple[str, str]:
        # 1. Identifica le materie già superate con voto >= 8
        passed_topics = [l.topic for l in state.completed_lessons if l.score >= 8]

        # 2. Prendi lo storico completo per evitare ripetizioni immediate
        all_history = [l.topic for l in state.completed_lessons]

        # 3. Estrai la materia escludendo quelle passate
        subject = self.subject_picker.pick(recent_subjects=all_history, excluded_subjects=passed_topics)

        # 4. Gestione "Gioco Finito" (se subject è None)
        if subject is None:
            msg = (
                "COMPLIMENTI! 🏆\n"
                "Hai completato tutte le materie del programma con voto superiore all'8.\n"
                "Sei pronto per il concorso!"
            )
            return msg, ""

        # FIX: Se il subject è composto (es. "Diritto: Accesso atti"), estraiamo la macro-categoria per trovare il tutor corretto
        if ":" in subject:
            macro_subject = subject.split(":")[0].strip()
        else:
            macro_subject = subject

        tutor = tutor_for_subject(macro_subject)
        base_stage = state.stage.get(tutor, 1)

        # Reset
        state.current_topic = subject
        state.current_tutor = tutor
        state.quiz_counter = 0
        state.quiz_score = 0
        state.quiz_results = []
        state.quiz_asked_questions = []

        mood = self._get_stage_mood(base_stage)
        prompt = f"""
Sei {tutor}, un tutor esperto e pragmatico per il concorso 'Ministero della Cultura'.
Argomento: "{subject}".
{mood}

OBIETTIVO:
Fai una lezione discorsiva e coinvolgente su questo argomento (Stile Chat/Podcast).
1. Sii chiaro, diretto e usa esempi pratici.
2. Spiega le leggi fondamentali (es. L.241/90, Codice Urbani) se pertinenti.
3. NON fare domande. Insegna e basta.
4. Formattazione: usa spazi e qualche elenco per rendere il testo leggibile.

Lingua: Italiano.
"""
        response = self.gemini.generate_content(prompt)

        image_path = ""
        if self.enable_sd:
            try:
                # Per l'immagine usiamo un prompt generico legato all'insegnamento
                dummy_q = Question(
                    domanda=f"Teaching {subject}", opzioni={}, corretta="", spiegazione="",
                    tutor=tutor, materia=subject,
                    tags=["holding a pointer", "pointing at whiteboard", "classroom background", "teaching", "glasses"],
                    visual="medium shot, standing near a whiteboard, teaching gesture, confident look"
                )
                sd_prompt = compile_sd_prompt(self.project_root, tutor, base_stage, False, dummy_q)
                filename = f"lesson_{uuid.uuid4().hex[:6]}.png"
                out = os.path.join(self.project_root, "output_images", filename)
                os.makedirs(os.path.dirname(out), exist_ok=True)
                self.sd_client.generate_image(sd_prompt.prompt, sd_prompt.negative_prompt, out)
                image_path = out
                self.last_image_path = out
            except Exception as e:
                print(f"Errore generazione immagine lezione: {e}")

        return response, image_path

    # --- FASE 2: QUIZ ---
    def get_next_quiz_question(self, state: SessionState) -> Question:
        subject = state.current_topic
        tutor = state.current_tutor
        base_stage = state.stage.get(tutor, 1)

        past_questions_txt = "\n- ".join(state.quiz_asked_questions[-6:])
        avoid_instruction = ""
        if past_questions_txt:
            avoid_instruction = f"\n[CONSTRAINT] DO NOT ask about these concepts again: \n- {past_questions_txt}\nGenerate a question on a DIFFERENT aspect of '{subject}'."

        cfg = PromptBuildConfig(seed_per_prompt=3, strict_json_only=True)
        max_retries = 3

        for attempt in range(max_retries):
            # Passiamo l'argomento specifico (es. "Logica: Sillogismi") nel prompt
            prompt_topic = f"{subject}. {avoid_instruction}"
            prompt_text = build_question_prompt(
                self.project_root, subject, tutor, base_stage, "neutro", cfg,
                specific_topic=prompt_topic
            )

            resp = self.gemini.generate_content(prompt_text)
            clean_json = resp.replace("```json", "").replace("```", "").strip()

            try:
                data = json.loads(clean_json)
                if not data.get("domanda") or not data.get("opzioni"): raise ValueError("Dati vuoti")

                valid_opts = [v for k, v in data["opzioni"].items() if v and str(v).strip() != "."]
                if len(valid_opts) < 2: raise ValueError("Opzioni mancanti")

                spieg = data.get("spiegazione_breve") or data.get("spiegazione", "...")
                corr_raw = str(data.get("corretta", "A")).strip().upper()
                if len(corr_raw) > 1: corr_raw = corr_raw[0]

                return Question(
                    domanda=data.get("domanda", ""),
                    opzioni=data.get("opzioni", {}),
                    corretta=corr_raw,
                    spiegazione=spieg,
                    tutor=tutor,
                    materia=subject,
                    tipo="standard",
                    tags=data.get("tags", []),
                    visual=data.get("visual", ""),
                    spiegazione_breve=spieg
                )
            except Exception as e:
                print(f"[ENGINE] Errore generazione quiz (Tentativo {attempt + 1}): {e}")
                continue

        return Question(
            domanda="Errore tecnico generazione domanda. Procedi.",
            opzioni={"A": "Avanti", "B": "Avanti", "C": "Avanti", "D": "Avanti"},
            corretta="A", spiegazione="...", tutor=tutor, materia=subject
        )

    # --- CORE ---
    def apply_answer(self, state: SessionState, question: Question, user_choice: str):
        u_clean = user_choice.strip().upper()[0]
        q_clean = question.corretta.strip().upper()
        if len(q_clean) > 0: q_clean = q_clean[0]

        is_correct = (u_clean == q_clean)
        outcome = "corretta" if is_correct else "errata"

        state.quiz_counter += 1
        if is_correct: state.quiz_score += 1
        state.quiz_results.append(outcome)

        if question.domanda and len(question.domanda) > 10:
            state.quiz_asked_questions.append(question.domanda[:100] + "...")

        state.history.append(HistoryItem(tutor=question.tutor, outcome=outcome))

        base_stage = state.stage.get(question.tutor, 1)
        bonus_stage = state.quiz_score // 2
        visual_stage = min(base_stage + bonus_stage, 5)

        class UpdateResult:
            def __init__(self, outcome, new_stage):
                self.outcome = outcome
                self.new_stage = new_stage
                self.is_punish = (outcome == "errata")

        update = UpdateResult(outcome, visual_stage)

        if self.enable_sd:
            try:
                sd_prompt = compile_sd_prompt(self.project_root, question.tutor, visual_stage, update.is_punish,
                                              question)
                filename = f"quiz_{uuid.uuid4().hex[:6]}.png"
                out = os.path.join(self.project_root, "output_images", filename)
                os.makedirs(os.path.dirname(out), exist_ok=True)
                self.sd_client.generate_image(sd_prompt.prompt, sd_prompt.negative_prompt, out)
                self.last_image_path = out
            except:
                pass

        return update

    # --- FASE 3: PAGELLA ---
    def generate_final_report(self, state: SessionState) -> str:
        score = state.quiz_score
        tutor = state.current_tutor
        topic = state.current_topic

        # SALVA LA LEZIONE NEL REGISTRO
        # Manteniamo lo storico completo senza cancellare le vecchie lezioni
        state.completed_lessons.append(LessonRecord(topic=topic, tutor=tutor, score=score))

        level_up_msg = ""
        if score >= 8:
            current_base = state.stage.get(tutor, 1)
            if current_base < 5:
                state.stage[tutor] = current_base + 1
                level_up_msg = f"\n\n🌟 LEVEL UP! {tutor} è passata allo Stage {state.stage[tutor]}!"
            else:
                level_up_msg = f"\n\n👑 MAX LEVEL! Hai la fiducia totale di {tutor}."

        prompt = f"""
You are {tutor}. The user finished the quiz on "{topic}". Score: {score}/10.
Write a final evaluation (Pagella).
- < 6: Severe, scold them.
- 6-8: Neutral/Encouraging.
- 9-10: Enthusiastic/Seductive.
Language: Italian.
"""
        report_text = self.gemini.generate_content(prompt)
        return report_text + level_up_msg

    # --- UTILS ---
    def get_answer_feedback(self, question: Question, outcome: str, stage: int) -> str:
        path = os.path.join(self.project_root, "prompts", "tutor_profiles", f"{question.tutor.lower()}.txt")
        try:
            profile = open(path, "r", encoding="utf-8").read()
        except:
            profile = f"You are {question.tutor}."
        mood = self._get_stage_mood(stage)
        res = "CORRECT" if outcome == "corretta" else "WRONG"
        return self.gemini.generate_content(f"{profile}\n{mood}\nUser answered {res}. Give a short emotional reaction.")

    def get_tutor_response(self, question, text, has_answered, stage):
        mood = self._get_stage_mood(stage)
        return self.gemini.generate_content(f"You are {question.tutor}. {mood}. User says: '{text}'. Reply in Italian.")

    # --- SAVE / LOAD AGGIORNATI ---
    def save_session_to_file(self, state, filepath):
        try:
            data = {
                "progress": state.progress,
                "stage": state.stage,
                "history": [{"tutor": h.tutor, "outcome": h.outcome} for h in state.history],
                "completed_lessons": [{"topic": l.topic, "tutor": l.tutor, "score": l.score} for l in
                                      state.completed_lessons]
            }
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except:
            pass

    def load_session_from_file(self, filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            s = SessionState()
            s.progress = data.get("progress", {})
            s.stage = data.get("stage", {})
            s.history = [HistoryItem(tutor=x["tutor"], outcome=x["outcome"]) for x in data.get("history", [])]
            s.completed_lessons = [LessonRecord(topic=x["topic"], tutor=x["tutor"], score=x["score"]) for x in
                                   data.get("completed_lessons", [])]
            return s
        except:
            return None