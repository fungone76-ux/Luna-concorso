# src/visuals/stage_manager.py
from __future__ import annotations

from dataclasses import dataclass

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

    Modalità implementata (scelta "2"):
    - progress = conteggio risposte CORRETTE per tutor
    - stage = 1 + (progress // step), clamp 1..5
    - punish (errata/omessa): stage = max(1, stage-1) (de-escalation di 1)
    - progress NON viene azzerato in punish (rimane com'è)
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
            # aumenta progress
            new_progress = old_progress + 1
            # ricalcola stage da progress
            new_stage = self._stage_from_progress(new_progress)
        else:
            # punish: de-escalation di 1 stage
            new_progress = old_progress
            new_stage = max(self.min_stage, old_stage - 1)

        # salva nello stato
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
        # stage = 1 + progress//step
        raw = self.min_stage + (max(0, int(progress)) // self.step)
        return max(self.min_stage, min(self.max_stage, raw))
