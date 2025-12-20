# src/engine/session_engine.py
from __future__ import annotations

import random
from typing import Optional

from src.ai.gemini_client import GeminiClient
from src.ai.prompt_builder import PromptBuildConfig, build_question_prompt
from src.ai.response_parser import parse_question_from_llm_json, ResponseParseError
from src.domain.models import (
    SessionState,
    Question,
    TurnResult,
    Outcome,
)
from src.engine.scoring import evaluate_answer, ScoreResult
from src.engine.subject_picker import SubjectPicker
from src.engine.tutor_router import tutor_for_subject

from src.visuals.stage_manager import StageManager
from src.visuals.prompt_compiler import compile_sd_prompt
from src.visuals.sd_client import SDClient, SDConfig


class SessionEngine:
    """
    Loop completo:
    1) Estrae materia con probabilità concorso (SubjectPicker)
    2) Deriva tutor dalla materia (tutor_router)
    3) Costruisce prompt (prompt_builder) usando stage + ultimo esito
    4) Chiama Gemini (GeminiClient) -> JSON
    5) Parse JSON -> Question (response_parser)
    6) apply_answer: scoring bando + stage (Python-only)
    7) (opzionale) SD: genera immagine reward/punish via Automatic1111
    """

    def __init__(
        self,
        project_root: str,
        gemini: GeminiClient,
        subject_picker: Optional[SubjectPicker] = None,
        prompt_cfg: Optional[PromptBuildConfig] = None,
        seed: int = 42,
        # Visuals (SD)
        enable_sd: bool = False,
        sd_client: Optional[SDClient] = None,
        stage_manager: Optional[StageManager] = None,
    ):
        self.project_root = project_root
        self.gemini = gemini
        self.subject_picker = subject_picker or SubjectPicker(seed=seed)
        self.prompt_cfg = prompt_cfg or PromptBuildConfig()
        self.rng = random.Random(seed)

        # Memoria dell'ultimo esito (NON LLM)
        self._last_outcome: Outcome = "corretta"

        # Visuals
        self.enable_sd = bool(enable_sd)
        self.sd = sd_client or SDClient(SDConfig.from_env())
        self.stage_manager = stage_manager or StageManager(step=10, min_stage=1, max_stage=5)

        # Ultima immagine generata (per CLI/GUI)
        self.last_image_path: Optional[str] = None

    def _last_outcome_hint(self) -> Outcome:
        return self._last_outcome

    def start_next_question(self, state: SessionState) -> Question:
        """
        Genera la prossima domanda via LLM.
        Aggiorna state.question_index.
        """
        subject = self.subject_picker.pick()
        tutor = tutor_for_subject(subject)
        stage = state.stage.get(tutor, 1)
        outcome_hint = self._last_outcome_hint()

        prompt = build_question_prompt(
            project_root=self.project_root,
            subject=subject,
            tutor=tutor,
            stage=stage,
            outcome_hint=outcome_hint,
            cfg=self.prompt_cfg,
            rng=self.rng,
        )

        data = self.gemini.generate_json(prompt)

        try:
            q_llm = parse_question_from_llm_json(data)
        except ResponseParseError as e:
            raise RuntimeError(
                f"Parsing fallito per domanda LLM. Materia={subject}, Tutor={tutor}, Stage={stage}. "
                f"Errore: {e}"
            ) from e

        # Forziamo coerenza con estrazione (meno sorprese):
        # MA preserviamo i campi extra che ci servono (difficulty/question_id/spiegazione_breve/tags/visual)
        q = Question(
            tutor=tutor,
            materia=subject,
            tipo=q_llm.tipo,
            domanda=q_llm.domanda,
            opzioni=q_llm.opzioni,
            corretta=q_llm.corretta,
            efficacia=q_llm.efficacia,
            difficulty=q_llm.difficulty,
            question_id=q_llm.question_id,
            spiegazione_breve=q_llm.spiegazione_breve,
            tags=q_llm.tags,
            visual=q_llm.visual,
        )

        state.question_index += 1
        return q

    def apply_answer(
        self,
        state: SessionState,
        question: Question,
        user_choice: Optional[str],
    ) -> TurnResult:
        """
        Applica la risposta utente:
        - punteggio bando
        - stage Python-only (de-escalation in punish)
        - (opzionale) genera immagine SD e salva path in self.last_image_path
        """
        score_res: ScoreResult = evaluate_answer(
            qtype=question.tipo,
            user_choice=user_choice,
            correct_choice=question.corretta,
            efficacy_by_option=question.efficacia,
        )

        # score
        state.score = round(state.score + score_res.delta, 3)

        # stage update (Python-only)
        stage_update = self.stage_manager.apply_outcome(
            state=state,
            tutor=question.tutor,
            outcome=score_res.outcome,
        )

        # memorizza ultimo outcome (per hint nel prompt successivo)
        self._last_outcome = score_res.outcome

        # SD (opzionale): reward/punish
        self.last_image_path = None
        if self.enable_sd:
            try:
                sd_prompt = compile_sd_prompt(
                    project_root=self.project_root,
                    tutor=question.tutor,
                    stage=stage_update.new_stage,
                    is_punish=stage_update.is_punish,
                    question=question,
                )
                print("\n[SD DEBUG] tutor:", question.tutor, "stage:", stage_update.new_stage, "punish:",
                      stage_update.is_punish)
                print("[SD DEBUG] prompt_len:", len(sd_prompt.prompt))
                print("[SD DEBUG] neg_len:", len(sd_prompt.negative_prompt))
                print("[SD DEBUG] PROMPT >>>", sd_prompt.prompt[:800])
                print("[SD DEBUG] NEG >>>", (sd_prompt.negative_prompt or "")[:400])

                # Debug tags/visual effettivi
                print("[SD DEBUG] tags:", getattr(question, "tags", None))
                print("[SD DEBUG] visual:", getattr(question, "visual", None))

                # nome file: tutor + indice domanda
                file_stem = f"{question.tutor.lower()}_{state.question_index:03d}"

                res = self.sd.txt2img(
                    prompt=sd_prompt.prompt,
                    negative_prompt=sd_prompt.negative_prompt,
                    file_stem=file_stem,
                )
                self.last_image_path = res.image_path
            except Exception as e:
                # Non facciamo crashare la sessione se SD fallisce
                self.last_image_path = None
                # Se vuoi, in futuro logghiamo su file. Per ora basta così.
                # print(f"[SD] Errore: {e}")

        return TurnResult(
            tutor=question.tutor,
            outcome=score_res.outcome,
            delta_score=score_res.delta,
            new_score=state.score,
            new_progress=stage_update.new_progress,
            new_stage=stage_update.new_stage,
        )
