# src/visuals/stage_manager.py
from __future__ import annotations

from dataclasses import dataclass
import math

from src.domain.models import SessionState, TutorName, Outcome


@dataclass(frozen=True)
class StageUpdate:
    tutor: TutorName
    old_progress: int
    old_stage: int
    new_progress: int
    new_stage: int
    is_punish: bool


class StageManager:
    """
    Gestisce progress e stage per ciascuna tutor.

    Nuova Logica (Punti solidi):
    - Progress: +1 se corretta, -1 se errata.
    - Stage: calcolato matematicamente in base a fasce di 10 punti.
      0-10 -> Stage 1
      11-20 -> Stage 2
      etc.
    """

    def __init__(self, step: int = 10, min_stage: int = 1, max_stage: int = 5):
        if step <= 0:
            raise ValueError("step deve essere > 0")
        self.step = step
        self.min_stage = min_stage
        self.max_stage = max_stage

    def apply_outcome(self, state: SessionState, tutor: TutorName, outcome: Outcome) -> StageUpdate:
        old_progress = int(state.progress.get(tutor, 0))
        old_stage = int(state.stage.get(tutor, self.min_stage))

        is_punish = outcome != "corretta"

        if outcome == "corretta":
            # Aumenta progress
            new_progress = old_progress + 1
        else:
            # Decrementa progress (ma non sotto 0)
            new_progress = max(0, old_progress - 1)

        # Calcola lo stage basandosi SOLO sul nuovo punteggio progress
        new_stage = self._stage_from_progress(new_progress)

        # Salva nello stato
        state.progress[tutor] = new_progress
        state.stage[tutor] = new_stage

        return StageUpdate(
            tutor=tutor,
            old_progress=old_progress,
            old_stage=old_stage,
            new_progress=new_progress,
            new_stage=new_stage,
            is_punish=is_punish,
        )

    def _stage_from_progress(self, progress: int) -> int:
        """
        Calcola lo stage in base ai range definiti:
        0-10  -> Stage 1
        11-20 -> Stage 2
        21-30 -> Stage 3
        ...
        """
        # Se progress è 0, siamo a stage 1.
        if progress == 0:
            return self.min_stage

        # Formula: (progress - 1) // step + 1
        # Esempio con step=10:
        # Punti 1..10  -> (0..9)//10 = 0 -> +1 = Stage 1
        # Punti 11..20 -> (10..19)//10 = 1 -> +1 = Stage 2
        raw_stage = ((progress - 1) // self.step) + 1

        # Clamp tra min e max (es. 1 e 5)
        return max(self.min_stage, min(self.max_stage, raw_stage))